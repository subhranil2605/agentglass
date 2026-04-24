# AgentGlass

A local, visual debugger for agentic AI workflows built on **LangGraph** and
**Google Gemini**. Wrap your compiled graph in a single context manager, run it
as usual, and get a live, clickable graph view in your browser with the exact
input and output of every node execution — including every visit of a loop.

No hosted platform. No login. No data leaves your machine.

## Install

```bash
pip install agentglass
```

## Quickstart

```python
from agentglass import trace
from langgraph.graph import StateGraph, END

# ... build your graph as you normally would ...
graph = StateGraph(MyState)
graph.add_node("retrieve", retrieve_fn)
graph.add_node("generate", generate_fn)
graph.set_entry_point("retrieve")
graph.add_edge("retrieve", "generate")
graph.add_edge("generate", END)
compiled = graph.compile()

with trace(compiled, port=8765):
    result = compiled.invoke({"question": "What's the weather in Tokyo?"})
```

A browser tab opens at `http://localhost:8765` showing your graph. As the run
proceeds, nodes light up. Click any node to see exactly what state went in and
what update came out. Nodes inside a loop show a visit-count badge and give you
per-call history in the side panel.

When the run finishes, the server keeps running so you can keep poking around.
Press `Ctrl-C` to exit.

## What's in the MVP

- **Live graph rendering** via Cytoscape.js with a layered DAG layout.
  Conditional edges are dashed; regular edges are solid.
- **Click-to-inspect** any node: input state, output state update, duration,
  and per-execution history for looped nodes.
- **Gemini-aware formatting** of message / content arrays: role badges,
  function-call / function-response pairing, finish-reason warnings.
- **Safe serialization** of arbitrary Python state — Pydantic, LangChain
  messages, dataclasses, numpy arrays, bytes — with per-field size caps.
- **Zero network egress**: everything is local and in-memory.

## What's not in the MVP (yet)

- Diff view between consecutive node executions
- Time-travel / pause-and-edit
- Multi-run comparison
- Persistence (SQLite) — currently in-memory only
- Cost / latency overlays

## License

MIT.