#!/usr/bin/env python3
"""
WebSocket relay server for High Noon Showdown.

Standalone:  python server.py
Embedded:    from server import start_background_server; start_background_server()
Default port: 8765
"""
import asyncio
import json
import random
import string
import threading
import time

import websockets

rooms: dict = {}


def gen_code() -> str:
    code = ''.join(random.choices(string.ascii_uppercase, k=4))
    return code if code not in rooms else gen_code()


class Room:
    def __init__(self, code: str):
        self.code = code
        self.players: list = []
        self.state = "waiting"
        # fires stores {player_idx: reaction_ms} — client-reported for fairness
        self.fires: dict = {}
        self.draw_time: float | None = None
        self._resolve_task = None

    async def broadcast(self, msg: dict):
        data = json.dumps(msg)
        await asyncio.gather(
            *[p.send(data) for p in self.players],
            return_exceptions=True,
        )

    async def start_round(self):
        self.state = "ready"
        self.fires = {}
        self.draw_time = None
        self._resolve_task = None
        await self.broadcast({"type": "ready"})

        delay = random.uniform(1.5, 5.0)
        await asyncio.sleep(delay)

        if self.state != "ready":
            return

        self.state = "draw"
        self.draw_time = time.perf_counter()
        await self.broadcast({"type": "draw"})

        await asyncio.sleep(5.0)
        if self.state == "draw":
            self.state = "timeout"
            await self.broadcast({"type": "timeout"})

    async def handle_fire(self, player_idx: int,
                          client_time_ms: float | None = None,
                          arrival_time: float | None = None):
        if self.state == "ready":
            self.state = "false_start"
            winner = 1 - player_idx
            await self.broadcast({
                "type": "false_start",
                "offender": player_idx,
                "winner": winner,
            })
            return

        if self.state != "draw" or player_idx in self.fires:
            return

        # Use client-reported reaction time for fairness; fall back to
        # server-measured arrival delta if the client didn't send one.
        if client_time_ms is not None:
            reaction_ms = client_time_ms
        elif arrival_time is not None and self.draw_time is not None:
            reaction_ms = (arrival_time - self.draw_time) * 1000
        else:
            reaction_ms = float("inf")

        self.fires[player_idx] = reaction_ms

        if len(self.fires) >= len(self.players):
            await self._resolve()
        elif self._resolve_task is None:
            # Grace window: wait up to 300 ms for the other player's shot
            self._resolve_task = asyncio.create_task(self._delayed_resolve())

    async def _delayed_resolve(self):
        await asyncio.sleep(0.3)
        if self.state == "draw":
            await self._resolve()

    async def _resolve(self):
        if self.state != "draw":
            return
        self.state = "done"
        if self._resolve_task:
            self._resolve_task.cancel()
        winner = min(self.fires, key=self.fires.get)
        times = {str(k): round(v) for k, v in self.fires.items()}
        await self.broadcast({"type": "result", "winner": winner, "times": times})


async def handler(websocket):
    player_idx = None
    room = None
    try:
        async for raw in websocket:
            msg = json.loads(raw)
            t = msg.get("type")

            if t == "create":
                code = gen_code()
                room = Room(code)
                room.players.append(websocket)
                rooms[code] = room
                player_idx = 0
                await websocket.send(json.dumps({"type": "created", "code": code}))

            elif t == "join":
                code = msg.get("code", "").strip().upper()
                if code not in rooms:
                    await websocket.send(json.dumps({"type": "error", "msg": "Room not found"}))
                    continue
                room = rooms[code]
                if len(room.players) >= 2:
                    await websocket.send(json.dumps({"type": "error", "msg": "Room full"}))
                    continue
                room.players.append(websocket)
                player_idx = 1
                await websocket.send(json.dumps({"type": "joined", "code": code}))
                await room.broadcast({"type": "start"})
                asyncio.create_task(room.start_round())

            elif t == "fire" and room is not None and player_idx is not None:
                await room.handle_fire(
                    player_idx,
                    client_time_ms=msg.get("client_time_ms"),
                    arrival_time=time.perf_counter(),
                )

            elif t == "rematch" and room is not None and player_idx == 0:
                room.state = "waiting"
                asyncio.create_task(room.start_round())

    finally:
        if room and websocket in room.players:
            room.players.remove(websocket)
            if not room.players and room.code in rooms:
                del rooms[room.code]
            elif room.players:
                await room.broadcast({"type": "opponent_left"})


def start_background_server(port: int = 8765):
    """Start the relay server in a daemon thread. Safe to call multiple times."""
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def _serve():
            try:
                async with websockets.serve(handler, "0.0.0.0", port):
                    await asyncio.Future()
            except OSError:
                pass  # port already in use — external relay is handling it

        loop.run_until_complete(_serve())

    t = threading.Thread(target=_run, daemon=True)
    t.start()


async def _main():
    host, port = "0.0.0.0", 8765
    print(f"Shootout server listening on ws://{host}:{port}")
    async with websockets.serve(handler, host, port):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(_main())
