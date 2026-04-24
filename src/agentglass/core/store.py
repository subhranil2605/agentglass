"""
In-memory, thread-safe event store.

Stores execution events keyed by node name so the UI can quickly retrieve all
executions of a given node. Also maintains a chronological list of every event
for the live feed, and a set of asyncio queues for pub/sub (each connected
WebSocket client gets its own queue).
"""

from __future__ import annotations

import asyncio
import threading
from collections import defaultdict
from typing import Any


class EventStore:
    def __init__(self) -> None:
        self._by_node: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._chronological: list[dict[str, Any]] = []
        self._lock = threading.Lock()

        # Pub/sub for live streaming. Each subscriber is an asyncio.Queue.
        # The event loop is captured when the first subscriber attaches, so that
        # the tracer (which typically runs in the main thread / sync context)
        # can schedule puts onto the right loop.
        self._subscribers: list[asyncio.Queue[dict[str, Any]]] = []
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subs_lock = threading.Lock()

    # -- write side (called from the tracer, possibly off the event loop) --

    def push(self, event: dict[str, Any]) -> None:
        with self._lock:
            node = event.get("node")
            if node:
                self._by_node[node].append(event)
            self._chronological.append(event)

        self._fanout(event)

    def _fanout(self, event: dict[str, Any]) -> None:
        with self._subs_lock:
            loop = self._loop
            subs = list(self._subscribers)
        if loop is None or not subs:
            return
        for q in subs:
            # put_nowait is safe to schedule onto the loop from any thread.
            try:
                loop.call_soon_threadsafe(q.put_nowait, event)
            except RuntimeError:
                # Loop was closed — drop silently, the subscriber is dead.
                pass

    # -- read side (called from FastAPI handlers, always on the event loop) --

    def events_for_node(
        self, node: str, run_id: str | None = None, limit: int | None = None
    ) -> list[dict[str, Any]]:
        with self._lock:
            events = list(self._by_node.get(node, []))
        if run_id:
            events = [e for e in events if e.get("run_id") == run_id]
        if limit:
            events = events[-limit:]
        return events

    def all_events(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._chronological)

    def clear(self) -> None:
        with self._lock:
            self._by_node.clear()
            self._chronological.clear()

    # -- pub/sub --

    def subscribe(
        self, loop: asyncio.AbstractEventLoop
    ) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        with self._subs_lock:
            if self._loop is None:
                self._loop = loop
            self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[dict[str, Any]]) -> None:
        with self._subs_lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass
