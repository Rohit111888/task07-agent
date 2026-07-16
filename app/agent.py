"""Anthropic tool-calling agent with observability metadata."""

from __future__ import annotations

import contextlib
import io
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from app.db_tools import query_cars
from app.graph_search import graph_ranked_search


env_path = Path(__file__).with_name(".env")
load_dotenv(env_path, override=False)

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")
_client: Anthropic | None = None


@dataclass(frozen=True)
class AgentRun:
    """Answer and telemetry collected across one agent execution."""

    answer: str
    model_used: str
    input_tokens: int
    output_tokens: int
    tool_calls_made: list[str]

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


def get_client() -> Anthropic:
    """Create the Anthropic client lazily so health checks need no API call."""
    global _client

    if _client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")
        _client = Anthropic(api_key=api_key)

    return _client


tools = [
    {
        "name": "query_database",
        "description": (
            "Query the structured automotive dataset using filters such as brand, "
            "minimum horsepower, maximum horsepower, and fuel type. Use this for "
            "direct factual filtering questions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "brand": {
                    "type": "string",
                    "description": "Vehicle brand such as Ferrari, Porsche, BMW, Audi, Mercedes-Benz.",
                },
                "min_hp": {
                    "type": "integer",
                    "description": "Minimum horsepower filter.",
                },
                "max_hp": {
                    "type": "integer",
                    "description": "Maximum horsepower filter.",
                },
                "fuel_type": {
                    "type": "string",
                    "description": "Fuel type such as Petrol, Diesel, Hybrid, Electric.",
                },
                "top_n": {
                    "type": "integer",
                    "description": "Number of records to return.",
                },
            },
        },
    },
    {
        "name": "graph_ranked_search",
        "description": (
            "Search the automotive similarity graph and rank results using graph centrality, "
            "especially PageRank. Use this for questions about important, influential, central, "
            "similar, or graph-ranked vehicles."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "User search query.",
                },
                "top_k": {
                    "type": "integer",
                    "description": "Number of graph-ranked results to return.",
                },
            },
            "required": ["query"],
        },
    },
]


def clean_json(data: Any) -> Any:
    """Convert pandas and NumPy values into JSON-safe values."""
    return json.loads(json.dumps(data, default=str))


def execute_tool(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any]:
    """Execute a tool selected by the model."""
    if tool_name == "query_database":
        brand = tool_input.get("brand")
        min_hp = tool_input.get("min_hp")
        max_hp = tool_input.get("max_hp")
        fuel_type = tool_input.get("fuel_type")
        top_n = tool_input.get("top_n", 10)

        results_df = query_cars(
            brand=brand,
            min_hp=min_hp,
            max_hp=max_hp,
            fuel_type=fuel_type,
            top_n=top_n,
        )
        records = results_df.fillna("").to_dict(orient="records")

        return clean_json(
            {
                "tool_used": "query_database",
                "filters": {
                    "brand": brand,
                    "min_hp": min_hp,
                    "max_hp": max_hp,
                    "fuel_type": fuel_type,
                    "top_n": top_n,
                },
                "result_count": len(records),
                "results": records,
            }
        )

    if tool_name == "graph_ranked_search":
        query = tool_input.get("query", "")
        top_k = tool_input.get("top_k", 5)

        with contextlib.redirect_stdout(io.StringIO()):
            results = graph_ranked_search(query=query, top_k=top_k)

        return clean_json(
            {
                "tool_used": "graph_ranked_search",
                "query": query,
                "ranking_signal": "PageRank centrality over automotive similarity graph",
                "result_count": len(results),
                "results": results,
            }
        )

    return {"error": f"Unknown tool: {tool_name}"}


def serialize_content_blocks(content_blocks: list[Any]) -> list[Any]:
    """Convert Anthropic content blocks into dictionaries for the next call."""
    serialized = []
    for block in content_blocks:
        serialized.append(block.model_dump() if hasattr(block, "model_dump") else block)
    return serialized


def _usage(response: Any) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    return (
        int(getattr(usage, "input_tokens", 0) or 0),
        int(getattr(usage, "output_tokens", 0) or 0),
    )


def _text_from(response: Any) -> str:
    return "".join(
        block.text for block in response.content if getattr(block, "type", None) == "text"
    )


def run_agent_with_metadata(user_question: str) -> AgentRun:
    """Run the agent and return the answer plus model, token, and tool metadata."""
    system_prompt = """
You are a domain AI agent for an automotive analytics dataset.

You have two tools:

1. query_database:
Use this for direct structured filtering, such as Ferrari cars above 700
horsepower, Porsche vehicles, hybrid vehicles, or cars in a horsepower range.

2. graph_ranked_search:
Use this for graph-based retrieval, including important, influential, central,
similar, graph-ranked, PageRank, or centrality-based vehicle questions.

When you receive tool results, write a clear professional answer. Mention which
tool was used and why. For graph-ranked results, explain that PageRank centrality
was used over the automotive similarity graph. Keep the answer concise but complete.
"""

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_question}]
    client = get_client()
    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=system_prompt,
        tools=tools,
        messages=messages,
    )

    input_tokens, output_tokens = _usage(response)
    model_used = str(getattr(response, "model", MODEL) or MODEL)
    tool_results = []
    tool_calls_made: list[str] = []

    for block in response.content:
        if block.type == "tool_use":
            tool_calls_made.append(block.name)
            result = execute_tool(block.name, block.input)
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, separators=(",", ":")),
                }
            )

    if not tool_results:
        return AgentRun(
            answer=_text_from(response),
            model_used=model_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            tool_calls_made=tool_calls_made,
        )

    messages.extend(
        [
            {
                "role": "assistant",
                "content": serialize_content_blocks(response.content),
            },
            {"role": "user", "content": tool_results},
        ]
    )

    final_response = client.messages.create(
        model=MODEL,
        max_tokens=1200,
        system=system_prompt,
        tools=tools,
        messages=messages,
    )
    final_input, final_output = _usage(final_response)

    return AgentRun(
        answer=_text_from(final_response),
        model_used=str(getattr(final_response, "model", model_used) or model_used),
        input_tokens=input_tokens + final_input,
        output_tokens=output_tokens + final_output,
        tool_calls_made=tool_calls_made,
    )


def run_agent(user_question: str) -> str:
    """Backward-compatible interface used by the original Task 07 CLI."""
    return run_agent_with_metadata(user_question).answer


if __name__ == "__main__":
    print("GNN-Enhanced Automotive AI Agent with Anthropic Tool Calling")
    print("Type 'exit' to quit")

    while True:
        question = input("\nAsk a question: ")
        if question.lower().strip() == "exit":
            break
        print("\nClaude Final Response")
        print("-" * 40)
        print(run_agent(question))
