"""WebSocket client running in a background thread with its own asyncio loop."""
import asyncio
import json
import queue
import threading

import websockets


class NetworkClient:
    def __init__(self):
        self.incoming: queue.Queue = queue.Queue()
        self.connected = False
        self.error: str | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ws = None
        self._out_queue: asyncio.Queue | None = None

    def connect(self, host: str, port: int = 8765):
        self._loop = asyncio.new_event_loop()
        t = threading.Thread(target=self._run, args=(host, port), daemon=True)
        t.start()

    def _run(self, host: str, port: int):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._main(host, port))

    async def _main(self, host: str, port: int):
        uri = f"ws://{host}:{port}"
        try:
            async with websockets.connect(uri, open_timeout=5) as ws:
                self._ws = ws
                self._out_queue = asyncio.Queue()
                self.connected = True
                await asyncio.gather(self._recv_loop(), self._send_loop())
        except Exception as e:
            self.error = str(e)
            self.incoming.put({"type": "connect_error", "msg": str(e)})

    async def _recv_loop(self):
        async for raw in self._ws:
            self.incoming.put(json.loads(raw))

    async def _send_loop(self):
        while True:
            msg = await self._out_queue.get()
            if msg is None:
                break
            await self._ws.send(json.dumps(msg))

    def send(self, msg: dict):
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
