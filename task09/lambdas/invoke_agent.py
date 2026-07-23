"""Read an automotive file from S3 and invoke the deployed agent."""

from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote
from urllib.request import Request, urlopen

import boto3


s3 = boto3.client("s3")

SUPPORTED_EXTENSIONS = {".json", ".csv"}
DEFAULT_INPUT_PREFIX = "incoming/"
DEFAULT_MAX_INPUT_BYTES = 100_000
DEFAULT_MAX_PROMPT_CHARACTERS = 30_000
DEFAULT_AGENT_TIMEOUT_SECONDS = 90


def _extract_s3_location(event: dict[str, Any]) -> tuple[str, str]:
    """Extract the bucket name and object key from an S3 EventBridge event."""
    try:
        detail = event["detail"]
        bucket_name = detail["bucket"]["name"]
        object_key = unquote(detail["object"]["key"])
    except (KeyError, TypeError) as exc:
        raise ValueError(
            "The workflow input is not a valid S3 Object Created event."
        ) from exc

    return bucket_name, object_key


def _download_file(bucket_name: str, object_key: str) -> str:
    """Download a small UTF-8 input file from S3."""
    maximum_bytes = int(
        os.getenv("MAX_INPUT_BYTES", str(DEFAULT_MAX_INPUT_BYTES))
    )

    response = s3.get_object(Bucket=bucket_name, Key=object_key)
    content_length = int(response.get("ContentLength", 0))

    if content_length > maximum_bytes:
        raise ValueError(
            f"Input file is {content_length} bytes; maximum is {maximum_bytes}."
        )

    raw_content = response["Body"].read(maximum_bytes + 1)

    if len(raw_content) > maximum_bytes:
        raise ValueError(f"Input file exceeds {maximum_bytes} bytes.")

    try:
        return raw_content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Input file must use UTF-8 encoding.") from exc


def _parse_json(content: str) -> tuple[str, Any, str | None, bool]:
    """Parse a JSON input file and return its instruction and records."""
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON input: {exc.msg}.") from exc

    default_instruction = (
        "Analyze this automotive dataset, identify important differences, "
        "and provide a concise summary."
    )

    if isinstance(payload, dict):
        instruction = str(payload.get("question") or default_instruction)
        request_id = payload.get("request_id")
        simulate_failure = payload.get("simulate_agent_failure") is True

        records = {
            key: value
            for key, value in payload.items()
            if key
            not in {
                "question",
                "request_id",
                "simulate_agent_failure",
            }
        }
    else:
        instruction = default_instruction
        request_id = None
        simulate_failure = False
        records = payload

    return instruction, records, request_id, simulate_failure


def _parse_csv(content: str) -> tuple[str, list[dict[str, str]], None, bool]:
    """Parse a CSV automotive dataset."""
    reader = csv.DictReader(io.StringIO(content))

    if not reader.fieldnames:
        raise ValueError("CSV input must contain a header row.")

    rows = list(reader)

    if not rows:
        raise ValueError("CSV input must contain at least one data row.")

    instruction = (
        "Analyze this automotive CSV dataset. Identify the vehicle with the "
        "highest horsepower and summarize the important differences."
    )

    return instruction, rows, None, False


def _build_prompt(instruction: str, records: Any) -> str:
    """Combine the requested analysis with the uploaded automotive data."""
    serialized_records = json.dumps(
        records,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    prompt = (
        f"{instruction}\n\n"
        "Use only the following uploaded automotive data when answering:\n"
        f"{serialized_records}"
    )

    maximum_characters = int(
        os.getenv(
            "MAX_PROMPT_CHARACTERS",
            str(DEFAULT_MAX_PROMPT_CHARACTERS),
        )
    )

    if len(prompt) > maximum_characters:
        raise ValueError(
            f"Generated prompt exceeds {maximum_characters} characters."
        )

    return prompt


def _invoke_agent(prompt: str, simulate_failure: bool) -> dict[str, Any]:
    """Send the generated question to the existing HTTPS agent endpoint."""
    endpoint = os.environ["AGENT_ENDPOINT"].rstrip("/")

    if not endpoint.startswith("https://"):
        raise ValueError("AGENT_ENDPOINT must use HTTPS.")

    failure_testing_enabled = (
        os.getenv("ENABLE_FAILURE_TEST", "false").lower() == "true"
    )

    if simulate_failure:
        if not failure_testing_enabled:
            raise ValueError("Controlled failure testing is not enabled.")

        endpoint = f"{endpoint.rsplit('/', 1)[0]}/task09-forced-failure"

    request_body = json.dumps({"question": prompt}).encode("utf-8")

    request = Request(
        endpoint,
        data=request_body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "task09-workflow-lambda/1.0",
        },
        method="POST",
    )

    timeout_seconds = int(
        os.getenv(
            "AGENT_TIMEOUT_SECONDS",
            str(DEFAULT_AGENT_TIMEOUT_SECONDS),
        )
    )

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            response_text = response.read().decode("utf-8")
            status_code = response.status
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Agent returned HTTP {exc.code}: {error_body[:500]}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Agent connection failed: {exc.reason}") from exc

    try:
        response_payload: Any = json.loads(response_text)
    except json.JSONDecodeError:
        response_payload = {"answer": response_text}

    return {
        "status_code": status_code,
        "response": response_payload,
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Process an S3 EventBridge event and return the agent result."""
    bucket_name, object_key = _extract_s3_location(event)

    input_prefix = os.getenv("INPUT_PREFIX", DEFAULT_INPUT_PREFIX)

    if not object_key.startswith(input_prefix):
        raise ValueError(
            f"Object key must begin with the '{input_prefix}' prefix."
        )

    extension = os.path.splitext(object_key)[1].lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file extension '{extension}'. "
            "Only .json and .csv are accepted."
        )

    content = _download_file(bucket_name, object_key)

    if extension == ".json":
        instruction, records, request_id, simulate_failure = _parse_json(
            content
        )
    else:
        instruction, records, request_id, simulate_failure = _parse_csv(
            content
        )

    prompt = _build_prompt(instruction, records)
    agent_result = _invoke_agent(prompt, simulate_failure)

    return {
        "request_id": request_id or context.aws_request_id,
        "source": {
            "bucket": bucket_name,
            "key": object_key,
            "file_type": extension.removeprefix("."),
        },
        "agent_result": agent_result,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }