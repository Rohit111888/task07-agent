"""Store an automotive-agent workflow result in PostgreSQL RDS."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import boto3
import pg8000.dbapi


secrets_manager = boto3.client("secretsmanager")

_credentials_cache: dict[str, str] | None = None
_VALID_TABLE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _get_database_credentials() -> dict[str, str]:
    """Read the generated RDS username and password from Secrets Manager."""
    global _credentials_cache

    if _credentials_cache is not None:
        return _credentials_cache

    secret_arn = os.environ["DB_SECRET_ARN"]
    response = secrets_manager.get_secret_value(SecretId=secret_arn)

    try:
        credentials = json.loads(response["SecretString"])
        username = credentials["username"]
        password = credentials["password"]
    except (KeyError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            "The database secret must contain username and password."
        ) from exc

    _credentials_cache = {
        "username": str(username),
        "password": str(password),
    }

    return _credentials_cache


def _get_table_name() -> str:
    """Return a validated PostgreSQL results table name."""
    table_name = os.getenv("RESULTS_TABLE", "workflow_results")

    if not _VALID_TABLE_NAME.fullmatch(table_name):
        raise ValueError("RESULTS_TABLE contains unsupported characters.")

    return table_name


def _validate_event(event: dict[str, Any]) -> None:
    """Confirm that the Invoke Agent state returned the required fields."""
    required_fields = {
        "request_id",
        "source",
        "agent_result",
        "processed_at",
    }
    missing_fields = required_fields.difference(event)

    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise ValueError(f"Workflow result is missing fields: {missing}.")

    source = event["source"]

    if not isinstance(source, dict):
        raise ValueError("The source field must be an object.")

    for field in ("bucket", "key", "file_type"):
        if not source.get(field):
            raise ValueError(f"The source field is missing '{field}'.")


def _connect() -> pg8000.dbapi.Connection:
    """Open a PostgreSQL connection using RDS environment settings."""
    credentials = _get_database_credentials()

    return pg8000.dbapi.connect(
        user=credentials["username"],
        password=credentials["password"],
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "5432")),
        database=os.getenv("DB_NAME", "automotive_workflow"),
        timeout=10,
        ssl_context=True,
    )


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Create the results table when needed and store one workflow result."""
    _validate_event(event)

    table_name = _get_table_name()
    request_id = str(event["request_id"])
    source = event["source"]
    agent_result = event["agent_result"]

    status_code = agent_result.get("status_code")
    serialized_result = json.dumps(
        agent_result,
        ensure_ascii=False,
        default=str,
    )

    try:
        processed_at = datetime.fromisoformat(
            str(event["processed_at"]).replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise ValueError("processed_at must be an ISO-8601 timestamp.") from exc

    connection = _connect()

    try:
        cursor = connection.cursor()

        cursor.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id BIGSERIAL PRIMARY KEY,
                request_id VARCHAR(128) NOT NULL UNIQUE,
                source_bucket VARCHAR(255) NOT NULL,
                source_key TEXT NOT NULL,
                file_type VARCHAR(16) NOT NULL,
                agent_status_code INTEGER,
                agent_response JSONB NOT NULL,
                workflow_status VARCHAR(32) NOT NULL,
                processed_at TIMESTAMPTZ NOT NULL,
                stored_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cursor.execute(
            f"""
            INSERT INTO {table_name} (
                request_id,
                source_bucket,
                source_key,
                file_type,
                agent_status_code,
                agent_response,
                workflow_status,
                processed_at
            )
            VALUES (
                %s,
                %s,
                %s,
                %s,
                %s,
                CAST(%s AS JSONB),
                %s,
                %s
            )
            ON CONFLICT (request_id)
            DO UPDATE SET
                source_bucket = EXCLUDED.source_bucket,
                source_key = EXCLUDED.source_key,
                file_type = EXCLUDED.file_type,
                agent_status_code = EXCLUDED.agent_status_code,
                agent_response = EXCLUDED.agent_response,
                workflow_status = EXCLUDED.workflow_status,
                processed_at = EXCLUDED.processed_at,
                stored_at = CURRENT_TIMESTAMP
            RETURNING id, stored_at
            """,
            (
                request_id,
                str(source["bucket"]),
                str(source["key"]),
                str(source["file_type"]),
                int(status_code) if status_code is not None else None,
                serialized_result,
                "SUCCEEDED",
                processed_at,
            ),
        )

        result_id, stored_at = cursor.fetchone()
        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    output = dict(event)
    output["database_record"] = {
        "id": int(result_id),
        "request_id": request_id,
        "table": table_name,
        "stored_at": (
            stored_at.astimezone(timezone.utc).isoformat()
            if hasattr(stored_at, "astimezone")
            else str(stored_at)
        ),
    }

    print(
        json.dumps(
            {
                "event": "task09_result_stored",
                "request_id": request_id,
                "database_record_id": int(result_id),
                "source_key": source["key"],
            }
        )
    )

    return output