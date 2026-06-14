from __future__ import annotations
"""WebSocket client — background thread with its own asyncio loop.

Records the moment each DRAW signal arrives and automatically injects
client_time_ms into fire messages so the server can compare true reaction
times rather than packet-arrival order.
"""
import asyncio
import json
import os
import queue
import threading
import time

import websockets
from dotenv import load_dotenv

load_dotenv()
_SERVER_URL = os.environ.get("SERVER_URL", "ws://164.92.79.212:8765")


class NetworkClient:
    def __init__(self):
        self.incoming: queue.Queue = queue.Queue()
        self.connected = False
        self.error: str | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ws = None
        self._out_queue: asyncio.Queue | None = None
        self._draw_receive_time: float | None = None

    def connect(self, url: str = None):
        """Connect to relay server. Accepts full ws:// URL or bare host string."""
        url = url or _SERVER_URL
        if not url.startswith("ws://") and not url.startswith("wss://"):
            url = f"ws://{url}:8765"
        self._url = url
        self._draw_receive_time = None
        self._loop = asyncio.new_event_loop()
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main())

    async def _main(self):
        try:
            async with websockets.connect(self._url, open_timeout=5) as ws:
                self._ws = ws
                self._out_queue = asyncio.Queue()
                self.connected = True
                await asyncio.gather(self._recv_loop(), self._send_loop())
        except Exception as e:
            self.error = str(e)
            self.incoming.put({"type": "connect_error", "msg": str(e)})

    async def _recv_loop(self):
        async for raw in self._ws:
            msg = json.loads(raw)
            if msg.get("type") == "draw":
                self._draw_receive_time = time.perf_counter()
            elif msg.get("type") == "ping":
                await self._ws.send(json.dumps({"type": "pong", "t": msg["t"]}))
                continue
            self.incoming.put(msg)

    async def _send_loop(self):
        while True:
            msg = await self._out_queue.get()
            if msg is None:
                break
            await self._ws.send(json.dumps(msg))

    def send(self, msg: dict):
        # Automatically stamp fire events with the local reaction time so
        # the server can pick the winner by true reaction speed.
        if msg.get("type") == "fire" and self._draw_receive_time is not None:
            msg = {**msg, "client_time_ms": round(
                (time.perf_counter() - self._draw_receive_time) * 1000
            )}
        if self._loop and self._out_queue is not None:
            asyncio.run_coroutine_threadsafe(self._out_queue.put(msg), self._loop)

    def poll(self) -> dict | None:
        try:
            return self.incoming.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        if self._loop and self._ws:
            asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)
        self.connected = False
