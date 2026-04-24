"""
FastAPI server that exposes the graph structure, historical events, and a
WebSocket stream of live execution events — plus serves the static UI.

The server runs in a dedicated background thread with its own asyncio event
loop, so the user's ``compiled.invoke(...)`` on the main thread proceeds
normally while the UI is live.
"""

from __future__ import annotations

import asyncio
import json
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse

from agentglass.core.store import EventStore

STATIC_DIR = Path(__file__).parent / "static"


class AgentGlassServer:
    def __init__(
        self,
        structure: dict[str, Any],
        store: EventStore,
        host: str = "127.0.0.1",
        port: int = 8765,
    ) -> None:
        self.structure = structure
        self.store = store
        self.host = host
        self.port = port

        self._app = self._build_app()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._server = None  # uvicorn.Server
        self._ready = threading.Event()

    # -------- app wiring --------

    def _build_app(self) -> FastAPI:
        app = FastAPI(title="AgentGlass", docs_url=None, redoc_url=None)

        @app.get("/", response_class=HTMLResponse)
        async def index() -> HTMLResponse:
            index_path = STATIC_DIR / "index.html"
            return HTMLResponse(index_path.read_text(encoding="utf-8"))

        @app.get("/api/graph")
        async def graph() -> JSONResponse:
            return JSONResponse(self.structure)

        @app.get("/api/events")
        async def events(
            node_id: str | None = None,
            run_id: str | None = None,
            limit: int | None = None,
        ) -> JSONResponse:
            if node_id:
                data = self.store.events_for_node(node_id, run_id=run_id, limit=limit)
            else:
                data = self.store.all_events()
                if limit:
                    data = data[-limit:]
            return JSONResponse(data)

        @app.websocket("/ws")
        async def websocket_endpoint(ws: WebSocket) -> None:
            await ws.accept()
            loop = asyncio.get_running_loop()
            q = self.store.subscribe(loop)

            # Replay existing events so a late-connecting client sees history.
            try:
                for ev in self.store.all_events():
                    await ws.send_text(json.dumps(ev, default=str))

                while True:
                    ev = await q.get()
                    await ws.send_text(json.dumps(ev, default=str))
            except WebSocketDisconnect:
                pass
            except Exception:
                pass
            finally:
                self.store.unsubscribe(q)

        return app

    # -------- lifecycle --------

    def start(self) -> None:
        """Start the server in a background thread; return once it's ready."""
        import uvicorn

        config = uvicorn.Config(
            self._app,
            host=self.host,
            port=self.port,
            log_level="warning",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        # uvicorn.Server normally installs signal handlers — that's not safe
        # from a non-main thread. Disable them.
        self._server.install_signal_handlers = lambda: None  # type: ignore[method-assign]

        def _run() -> None:
            loop = asyncio.new_event_loop()
            self._loop = loop
            asyncio.set_event_loop(loop)
            self._ready.set()
            try:
                loop.run_until_complete(self._server.serve())
            finally:
                loop.close()

        t = threading.Thread(target=_run, name="agentglass-server", daemon=True)
        t.start()
        self._thread = t
        self._ready.wait(timeout=5.0)

    def wait(self) -> None:
        """Block the caller until the server thread exits (e.g. Ctrl-C)."""
        while self._thread and self._thread.is_alive():
            try:
                self._thread.join(timeout=0.5)
            except KeyboardInterrupt:
                self.stop()
                raise

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
