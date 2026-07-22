"""Provide structured observability helpers for the FastAPI application."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


logger = logging.getLogger("task08.observability")
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def utc_timestamp() -> str:
    """
    Return the current UTC timestamp in ISO-8601 format.
    """
    return datetime.now(timezone.utc).isoformat()


def emit_request_log(
    *,
    request_id: str,
    path: str,
    method: str,
    query: str | None,
    latency_ms: float,
    model_used: str | None,
    input_tokens: int,
    output_tokens: int,
    tool_calls: list[str],
    status_code: int,
    error: str | None = None,
) -> None:
    """
    Emit one compact structured JSON log entry to standard output.

    ECS forwards standard output to CloudWatch Logs through the awslogs
    logging driver.
    """

    total_tokens = input_tokens + output_tokens

    log_entry: dict[str, Any] = {
        "event": "agent_request",
        "timestamp": utc_timestamp(),
        "request_id": request_id,
        "path": path,
        "method": method,
        "query": query,
        "latency_ms": round(latency_ms, 2),
        "model_used": model_used,
        "token_count": {
            "input": input_tokens,
            "output": output_tokens,
            "total": total_tokens,
        },
        "tool_calls_made": tool_calls,
        "tool_call_count": len(tool_calls),
        "status_code": status_code,
        "is_success": 1 if 200 <= status_code < 400 else 0,
        "is_client_error": 1 if 400 <= status_code < 500 else 0,
        "is_server_error": 1 if status_code >= 500 else 0,
        "error": error,
    }

    logger.info(
        json.dumps(
            log_entry,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
    )