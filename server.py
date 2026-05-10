#!/usr/bin/env python3
"""
Run this on any machine accessible to both players:
    python server.py
Default port: 8765
"""
import asyncio
import json
import random
import string
import time
import websockets

rooms: dict = {}


def gen_code() -> str:
    code = ''.join(random.choices(string.ascii_uppercase, k=4))
    return code if code not in rooms else gen_code()


class Room:
    def __init__(self, code: str):
        self.code = code
        self.players: list = []      # websocket objects
        self.state = "waiting"       # waiting | ready | draw | done
        self.fires: dict = {}        # {player_idx: perf_counter time}
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

    async def handle_fire(self, player_idx: int):
        t = time.perf_counter()

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

        self.fires[player_idx] = t

        if len(self.fires) >= len(self.players):
            await self._resolve()
        elif self._resolve_task is None:
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
        times = {
            str(k): int((v - self.draw_time) * 1000)
            for k, v in self.fires.items()
        }
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
                await room.handle_fire(player_idx)

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


async def main():
    host, port = "0.0.0.0", 8765
    print(f"Shootout server listening on ws://{host}:{port}")
    async with websockets.serve(handler, host, port):
        await asyncio.Future()


if __name__ == "__main__":
    asyncio.run(main())
