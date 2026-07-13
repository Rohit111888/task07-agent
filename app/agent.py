from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic
import os
import json
import contextlib
import io

from app.db_tools import query_cars
from app.graph_search import graph_ranked_search


# ---------------------------------------------------------
# Load API key safely from .env
# ---------------------------------------------------------
env_path = Path(__file__).with_name(".env")
load_dotenv(env_path, override=False)

api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

if not api_key:
    raise ValueError("ANTHROPIC_API_KEY not found. Check your .env file.")

client = Anthropic(api_key=api_key)

MODEL = "claude-opus-4-8"


# ---------------------------------------------------------
# Tool definitions for Anthropic tool-calling
# ---------------------------------------------------------
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


# ---------------------------------------------------------
# Tool execution functions
# ---------------------------------------------------------
def clean_json(data):
    """
    Converts pandas/numpy values into JSON-safe values.
    """
    return json.loads(json.dumps(data, default=str))


def execute_tool(tool_name, tool_input):
    """
    Executes the tool selected by Claude.
    """

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

        # Suppress graph-building debug prints from build_graph.py
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


def serialize_content_blocks(content_blocks):
    """
    Converts Anthropic content block objects into dictionaries
    so they can be sent back in the next API call.
    """
    serialized = []

    for block in content_blocks:
        if hasattr(block, "model_dump"):
            serialized.append(block.model_dump())
        else:
            serialized.append(block)

    return serialized


# ---------------------------------------------------------
# Agent loop
# ---------------------------------------------------------
def run_agent(user_question):
    system_prompt = """
You are a domain AI agent for an automotive analytics dataset.

You have two tools:

1. query_database:
Use this for direct structured filtering, such as:
- Ferrari cars above 700 horsepower
- Porsche vehicles
- hybrid vehicles
- cars within a horsepower range

2. graph_ranked_search:
Use this for graph-based retrieval, such as:
- important vehicles
- influential vehicles
- central vehicles
- similar vehicles
- graph-ranked search
- PageRank or centrality-based ranking

When you receive tool results, write a clear professional answer.
Mention which tool was used and why.
For graph-ranked results, explain that PageRank centrality was used over the automotive similarity graph.
Keep the answer concise but complete.
"""

    messages = [
        {
            "role": "user",
            "content": user_question,
        }
    ]

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        system=system_prompt,
        tools=tools,
        messages=messages,
    )

    tool_results = []

    for block in response.content:
        if block.type == "tool_use":
            print(f"\nClaude selected tool: {block.name}")
            print(f"Tool input: {block.input}")

            result = execute_tool(block.name, block.input)

            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, indent=2),
                }
            )

    # If Claude answered without using a tool
    if not tool_results:
        final_text = ""

        for block in response.content:
            if block.type == "text":
                final_text += block.text

        return final_text

    # Send tool results back to Claude
    messages.append(
        {
            "role": "assistant",
            "content": serialize_content_blocks(response.content),
        }
    )

    messages.append(
        {
            "role": "user",
            "content": tool_results,
        }
    )

    final_response = client.messages.create(
        model=MODEL,
        max_tokens=1200,
        system=system_prompt,
        tools=tools,
        messages=messages,
    )

    final_text = ""

    for block in final_response.content:
        if block.type == "text":
            final_text += block.text

    return final_text


if __name__ == "__main__":
    print("GNN-Enhanced Automotive AI Agent with Anthropic Tool Calling")
    print("Type 'exit' to quit")

    while True:
        question = input("\nAsk a question: ")

        if question.lower().strip() == "exit":
            break

        answer = run_agent(question)

        print("\nClaude Final Response")
        print("-" * 40)
        print(answer)