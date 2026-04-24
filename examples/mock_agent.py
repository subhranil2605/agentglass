"""
A no-API-needed example. Simulates a Gemini-style tool-calling agent with a
loop (planner -> tool -> planner -> tool -> generate -> END), emitting
Gemini-shaped message data so you can see the chat-transcript formatting in
the AgentGlass UI.

Run:
    python examples/mock_agent.py
"""
from __future__ import annotations

import time
from typing import Annotated, TypedDict
import operator

from langgraph.graph import END, StateGraph

from agentglass import trace


class State(TypedDict):
    messages: Annotated[list, operator.add]
    iterations: int


def planner(state: State) -> dict:
    """Decide whether to call a tool or finish. Simulates a Gemini model turn."""
    time.sleep(0.4)  # fake latency
    iterations = state.get("iterations", 0)

    if iterations == 0:
        msg = {
            "role": "model",
            "parts": [
                {"text": "I'll need to check the weather in Tokyo first."},
                {"functionCall": {"name": "get_weather", "args": {"city": "Tokyo"}}},
            ],
            "finish_reason": "STOP",
        }
    elif iterations == 1:
        msg = {
            "role": "model",
            "parts": [
                {"text": "And now London."},
                {"functionCall": {"name": "get_weather", "args": {"city": "London"}}},
            ],
            "finish_reason": "STOP",
        }
    else:
        msg = {
            "role": "model",
            "parts": [
                {"text": "Tokyo is cloudy at 18°C; London is rainy at 11°C. "
                         "If you're picking one for a walk today, Tokyo's the call."}
            ],
            "finish_reason": "STOP",
        }

    return {"messages": [msg], "iterations": iterations + 1}


def tool_executor(state: State) -> dict:
    """Execute the latest tool call."""
    time.sleep(0.3)
    last = state["messages"][-1]
    fc = next((p["functionCall"] for p in last["parts"] if "functionCall" in p), None)
    if not fc:
        return {"messages": []}

    city = fc["args"]["city"]
    fake_data = {
        "Tokyo": "Cloudy, 18°C, 70% humidity.",
        "London": "Rainy, 11°C, 85% humidity.",
    }.get(city, "Unknown.")

    response_msg = {
        "role": "tool",
        "parts": [
            {"functionResponse": {"name": fc["name"], "response": {"weather": fake_data}}}
        ],
    }
    return {"messages": [response_msg]}


def should_continue(state: State) -> str:
    last = state["messages"][-1]
    # Continue if the last model message included a function call.
    if last.get("role") == "model":
        for p in last.get("parts", []):
            if "functionCall" in p:
                return "tool"
        return "end"
    return "plan"


def build():
    g = StateGraph(State)
    g.add_node("planner", planner)
    g.add_node("tool_executor", tool_executor)
    g.set_entry_point("planner")
    g.add_conditional_edges(
        "planner",
        should_continue,
        {"tool": "tool_executor", "end": END, "plan": "planner"},
    )
    g.add_edge("tool_executor", "planner")
    return g.compile()


if __name__ == "__main__":
    compiled = build()

    initial = {
        "messages": [
            {"role": "user", "parts": [{"text": "Compare weather in Tokyo and London."}]}
        ],
        "iterations": 0,
    }

    with trace(compiled, port=8765):
        result = compiled.invoke(initial)
        print("\nFinal messages:", len(result["messages"]))