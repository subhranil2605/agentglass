"""
AgentGlass — a visual debugger for LangGraph + Google Gemini agents.

Usage:
    from agentglass import trace

    graph = build_my_graph()
    compiled = graph.compile()

    with trace(compiled, port=8765):
        result = compiled.invoke({"input": "..."})
"""

from .api.server import AgentGlassServer
from .core.store import EventStore
from .core.tracer import AgentGlassTracer, trace

__version__ = "0.1.0"
__all__ = ["trace", "AgentGlassTracer", "EventStore", "AgentGlassServer"]
