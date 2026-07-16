"""FastAPI wrapper for the observable automotive agent."""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.agent import MODEL, run_agent_with_metadata
from app.observability import emit_request_log


MAX_QUERY_LENGTH = 4000
app = FastAPI(title="Task 08 Observable Automotive AI Agent", version="2.0.0")


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH)


class QueryResponse(BaseModel):
    question: str
    answer: str
    request_id: str


def _default_metadata() -> dict[str, Any]:
    return {
        "model_used": "none",
        "input_tokens": 0,
        "output_tokens": 0,
        "tool_calls_made": [],
    }


async def _query_from_request(request: Request) -> str:
    """Extract the submitted question for the single structured request log."""
    if request.url.path != "/query":
        return request.query_params.get("query", "")

    try:
        body = await request.body()
        payload = json.loads(body) if body else {}
    except (UnicodeDecodeError, json.JSONDecodeError):
        return "<invalid-json>"

    value = payload.get("question", "") if isinstance(payload, dict) else ""
    return value if isinstance(value, str) else json.dumps(value, default=str)


@app.middleware("http")
async def structured_request_logging(request: Request, call_next):
    """Log every HTTP request with a stable JSON schema."""
    started = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    request.state.agent_metadata = _default_metadata()
    request.state.error = None
    query_text = await _query_from_request(request)

    try:
        response = await call_next(request)
    except Exception as exc:  # the API must return a safe response and still log the failure
        request.state.error = f"{type(exc).__name__}: {str(exc)[:300]}"
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
        )

    status_code = response.status_code
    error = request.state.error
    if status_code >= 400 and not error:
        error = f"HTTP {status_code}"

    latency_ms = (time.perf_counter() - started) * 1000
    metadata = request.state.agent_metadata
    emit_request_log(
    request_id=request_id,
    method=request.method,
    path=request.url.path,
    query=query_text,
    latency_ms=latency_ms,
    model_used=metadata["model_used"],
    input_tokens=metadata["input_tokens"],
    output_tokens=metadata["output_tokens"],
    tool_calls=metadata["tool_calls_made"],
    status_code=status_code,
    error=error,
)

    response.headers["X-Request-ID"] = request_id
    return response


@app.get("/")
def root():
    return {
        "message": "Task 08 observable automotive agent is running",
        "docs": "/docs",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/query", response_model=QueryResponse)
async def query(payload: QueryRequest, request: Request):
    question = payload.question.strip()
    if not question:
        request.state.error = "Question must not be blank"
        raise HTTPException(status_code=400, detail="Question must not be blank")

    request.state.agent_metadata["model_used"] = MODEL
    try:
        result = await run_in_threadpool(run_agent_with_metadata, question)
    except Exception as exc:
        request.state.error = f"{type(exc).__name__}: {str(exc)[:300]}"
        raise

    request.state.agent_metadata = {
        "model_used": result.model_used,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "tool_calls_made": result.tool_calls_made,
    }
    return {
        "question": payload.question,
        "answer": result.answer,
        "request_id": request.state.request_id,
    }


@app.post("/test-error", include_in_schema=False)
def test_error(request: Request):
    """Temporarily enabled endpoint used only to demonstrate the alarm."""
    enabled = os.getenv("ENABLE_TEST_ERROR_ENDPOINT", "false").lower() == "true"
    if not enabled:
        request.state.error = "Test error endpoint is disabled"
        raise HTTPException(status_code=404, detail="Not found")

    request.state.error = "Forced test error for CloudWatch alarm demonstration"
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Forced test error",
            "request_id": request.state.request_id,
        },
    )
