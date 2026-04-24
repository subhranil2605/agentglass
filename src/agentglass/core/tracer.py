"""
The AgentGlass tracer.

Hooks into LangGraph's callback system to capture:
  - Per-node input/output state
  - Per-node LLM calls: model name, token counts, tool calls made
  - Timing and error info
"""

from __future__ import annotations

import contextlib
import threading
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Iterator
from uuid import uuid4

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from agentglass.graph.graph_extract import extract_structure
from agentglass.core.serialization import serialize
from agentglass.core.store import EventStore


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_tool_calls(response: LLMResult) -> list[dict]:
    calls = []
    try:
        for gen_list in response.generations:
            for gen in gen_list:
                msg = getattr(gen, "message", None)
                if msg is None:
                    continue
                for tc in getattr(msg, "tool_calls", []) or []:
                    calls.append(
                        {
                            "name": tc.get("name", ""),
                            "args": tc.get("args", {}),
                            "id": tc.get("id", ""),
                        }
                    )
                akw = getattr(msg, "additional_kwargs", {}) or {}
                for fc in (
                    akw.get("function_call", [])
                    if isinstance(akw.get("function_call"), list)
                    else ([akw["function_call"]] if akw.get("function_call") else [])
                ):
                    if not any(c["name"] == fc.get("name") for c in calls):
                        calls.append(
                            {
                                "name": fc.get("name", ""),
                                "args": fc.get("arguments", {}),
                                "id": "",
                            }
                        )
    except Exception:
        pass
    return calls


def _extract_token_usage(response: LLMResult) -> dict:
    usage: dict = {"input": None, "output": None, "total": None}
    try:
        meta = response.llm_output or {}
        tok = meta.get("token_usage") or meta.get("usage") or {}
        if tok:
            usage["input"] = (
                tok.get("prompt_tokens")
                or tok.get("input_tokens")
                or tok.get("prompt_token_count")
            )
            usage["output"] = (
                tok.get("completion_tokens")
                or tok.get("output_tokens")
                or tok.get("candidates_token_count")
            )
            usage["total"] = tok.get("total_tokens") or tok.get("total_token_count")
        if not any(usage.values()):
            for gen_list in response.generations:
                for gen in gen_list:
                    msg = getattr(gen, "message", None)
                    um = getattr(msg, "usage_metadata", None) if msg else None
                    if um:

                        def _get(o, k):
                            return (
                                o.get(k) if hasattr(o, "get") else getattr(o, k, None)
                            )

                        usage["input"] = _get(um, "input_tokens")
                        usage["output"] = _get(um, "output_tokens")
                        usage["total"] = _get(um, "total_tokens")
                        if any(v is not None for v in usage.values()):
                            break
        if usage["input"] and usage["output"] and usage["total"] is None:
            usage["total"] = usage["input"] + usage["output"]
    except Exception:
        pass
    return usage


def _extract_model_name(
    serialized: dict, response: LLMResult | None = None
) -> str | None:
    if response:
        meta = response.llm_output or {}
        for key in ("model_name", "model", "engine", "deployment_name"):
            if meta.get(key):
                return str(meta[key])
    for key in ("model_name", "model", "name", "model_id"):
        v = (serialized or {}).get(key)
        if v:
            return str(v)
        kw = (serialized or {}).get("kwargs", {}) or {}
        if kw.get(key):
            return str(kw[key])
    return None


class AgentGlassTracer(BaseCallbackHandler):
    raise_error = False
    ignore_retriever = True
    ignore_agent = True
    ignore_llm = False  # we need LLM callbacks for token/model info

    def __init__(self, event_store: EventStore, node_ids: set[str]):
        self._store = event_store
        self._node_ids = set(node_ids)
        self._runs: dict[str, dict[str, Any]] = {}
        self._runs_lock = threading.Lock()
        self._current_graph_run: str | None = None
        self._llm_parent: dict[str, str] = {}
        self._llm_serialized: dict[str, dict] = {}
        self._llm_lock = threading.Lock()

    def _is_node_run(self, run_name, tags, metadata) -> bool:
        has_step_tag = False
        if tags:
            for t in tags:
                if t.startswith("graph:step:") or t.startswith("langgraph:node:"):
                    has_step_tag = True
                    break
        if not has_step_tag:
            return False
        if metadata and "langgraph_node" in metadata and run_name:
            if run_name != metadata["langgraph_node"]:
                return False
        return True

    def _node_name(self, run_name, tags, metadata, serialized) -> str:
        if metadata and metadata.get("langgraph_node"):
            return str(metadata["langgraph_node"])
        if tags:
            for t in tags:
                if t.startswith("graph:step:"):
                    return t.split("graph:step:", 1)[1]
                if t.startswith("langgraph:node:"):
                    return t.split("langgraph:node:", 1)[1]
        if run_name:
            return run_name
        if serialized:
            return str((serialized or {}).get("name", "unknown"))
        return "unknown"

    # --- node callbacks ---

    def on_chain_start(
        self,
        serialized,
        inputs,
        *,
        run_id,
        parent_run_id=None,
        tags=None,
        metadata=None,
        **kwargs,
    ):
        run_name = kwargs.get("name")
        if parent_run_id is None and self._current_graph_run is None:
            self._current_graph_run = str(run_id)
        if not self._is_node_run(run_name, tags, metadata):
            return
        node = self._node_name(run_name, tags, metadata, serialized)
        execution_id = str(uuid4())
        with self._runs_lock:
            self._runs[str(run_id)] = {
                "execution_id": execution_id,
                "node": node,
                "start_perf": time.perf_counter(),
                "llm_calls": [],
            }
        self._store.push(
            {
                "event_id": str(uuid4()),
                "run_id": self._current_graph_run or str(run_id),
                "execution_id": execution_id,
                "type": "node_start",
                "node": node,
                "input": serialize(inputs),
                "timestamp": _now_iso(),
            }
        )

    def on_chain_end(self, outputs, *, run_id, **kwargs):
        key = str(run_id)
        with self._runs_lock:
            info = self._runs.pop(key, None)
        if info is None:
            if self._current_graph_run == key:
                self._current_graph_run = None
            return
        duration_ms = (time.perf_counter() - info["start_perf"]) * 1000.0
        self._store.push(
            {
                "event_id": str(uuid4()),
                "run_id": self._current_graph_run or key,
                "execution_id": info["execution_id"],
                "type": "node_end",
                "node": info["node"],
                "output": serialize(outputs),
                "timestamp": _now_iso(),
                "duration_ms": round(duration_ms, 2),
                "llm_calls": info.get("llm_calls", []),
            }
        )

    def on_chain_error(self, error, *, run_id, **kwargs):
        key = str(run_id)
        with self._runs_lock:
            info = self._runs.pop(key, None)
        if info is None:
            if self._current_graph_run == key:
                self._current_graph_run = None
            return
        duration_ms = (time.perf_counter() - info["start_perf"]) * 1000.0
        self._store.push(
            {
                "event_id": str(uuid4()),
                "run_id": self._current_graph_run or key,
                "execution_id": info["execution_id"],
                "type": "node_error",
                "node": info["node"],
                "error": {
                    "type": type(error).__name__,
                    "message": str(error),
                    "traceback": "".join(
                        traceback.format_exception(
                            type(error), error, error.__traceback__
                        )
                    ),
                },
                "timestamp": _now_iso(),
                "duration_ms": round(duration_ms, 2),
                "llm_calls": info.get("llm_calls", []),
            }
        )

    # --- LLM callbacks ---

    def on_llm_start(
        self, serialized, prompts, *, run_id, parent_run_id=None, **kwargs
    ):
        rid = str(run_id)
        with self._llm_lock:
            if parent_run_id:
                self._llm_parent[rid] = str(parent_run_id)
            self._llm_serialized[rid] = serialized or {}

    def on_chat_model_start(
        self, serialized, messages, *, run_id, parent_run_id=None, **kwargs
    ):
        rid = str(run_id)
        with self._llm_lock:
            if parent_run_id:
                self._llm_parent[rid] = str(parent_run_id)
            self._llm_serialized[rid] = serialized or {}

    def on_llm_end(self, response: LLMResult, *, run_id, parent_run_id=None, **kwargs):
        rid = str(run_id)
        with self._llm_lock:
            parent_id = self._llm_parent.pop(rid, None) or (
                str(parent_run_id) if parent_run_id else None
            )
            serialized = self._llm_serialized.pop(rid, {})

        model_name = _extract_model_name(serialized, response)
        token_usage = _extract_token_usage(response)
        tool_calls = _extract_tool_calls(response)

        llm_info = {
            "model": model_name,
            "tokens": token_usage,
            "tool_calls": tool_calls,
        }
        if parent_id:
            self._attach_llm_to_node(parent_id, llm_info)

    def _attach_llm_to_node(self, run_id: str, llm_info: dict, depth: int = 0) -> bool:
        if depth > 6:
            return False
        with self._runs_lock:
            info = self._runs.get(run_id)
        if info is not None:
            info["llm_calls"].append(llm_info)
            return True
        with self._llm_lock:
            next_parent = self._llm_parent.get(run_id)
        if next_parent:
            return self._attach_llm_to_node(next_parent, llm_info, depth + 1)
        return False


# --------------------------------------------------------------------------


@contextlib.contextmanager
def trace(
    compiled_graph: Any,
    port: int = 8765,
    host: str = "127.0.0.1",
    open_browser: bool = True,
    block_on_exit: bool = True,
) -> Iterator[Any]:
    from agentglass.api.server import AgentGlassServer

    structure = extract_structure(compiled_graph)
    node_ids = {n["id"] for n in structure["nodes"]} | {
        n["name"] for n in structure["nodes"]
    }

    store = EventStore()
    tracer = AgentGlassTracer(store, node_ids=node_ids)

    try:
        compiled_graph.config = {
            **(getattr(compiled_graph, "config", {}) or {}),
            "callbacks": [
                *((getattr(compiled_graph, "config", {}) or {}).get("callbacks") or []),
                tracer,
            ],
        }
    except Exception:
        pass

    traced_graph = compiled_graph
    try:
        traced_graph = compiled_graph.with_config(callbacks=[tracer])
    except Exception:
        pass

    server = AgentGlassServer(structure=structure, store=store, host=host, port=port)
    server.start()

    url = f"http://{host}:{port}"
    print(f"[agentglass] UI running at {url}")

    if open_browser:
        try:
            import webbrowser

            webbrowser.open(url)
        except Exception:
            pass

    try:
        yield traced_graph
    finally:
        if block_on_exit:
            print("[agentglass] Run finished. Server still running — Ctrl-C to exit.")
            try:
                server.wait()
            except KeyboardInterrupt:
                pass
        server.stop()
