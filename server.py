#!/usr/bin/env python3
from __future__ import annotations
"""
WebSocket relay server for shooter.

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

MIN_REACTION_MS   = 80   # below this is physically impossible for a human
RTT_TOLERANCE_MS  = 50   # extra buffer for clock drift / jitter
N_RTT_SAMPLES     = 5    # pings per player; minimum of all samples is used
RTT_PING_INTERVAL = 0.1  # seconds between pings


def gen_code() -> str:
    code = ''.join(random.choices(string.ascii_uppercase, k=4))
    return code if code not in rooms else gen_code()


class Room:
    def __init__(self, code: str):
        self.code = code
        self.players: list = []
        self.state = "waiting"
        self.fires: dict = {}
        self.draw_time: float | None = None
        self._resolve_task = None
        self.prompt_key: str | None = None
        self.player_names: dict = {}
        self.player_rtt: dict = {}         # {player_idx: min rtt_ms so far}
        self.player_rtt_samples: dict = {} # {player_idx: [rtt_ms, ...]}
        self.rematch_votes: set = set()

    async def measure_rtt(self):
        for _ in range(N_RTT_SAMPLES):
            for ws in self.players:
                try:
                    await ws.send(json.dumps({"type": "ping", "t": time.perf_counter()}))
                except Exception:
                    pass
            await asyncio.sleep(RTT_PING_INTERVAL)

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
        self.prompt_key = random.choice(string.ascii_uppercase)
        await self.broadcast({"type": "draw", "key": self.prompt_key})

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

        server_delta_ms = (
            (arrival_time - self.draw_time) * 1000
            if arrival_time is not None and self.draw_time is not None
            else None
        )

        # Anti-cheat: reject physically impossible reaction times only.
        # The min_plausible (RTT-based) check was removed — measured min-RTT
        # is consistently lower than actual RTT at fire time due to network
        # jitter and async send-queue delay, causing systematic false positives
        # against the first player to fire.
        if client_time_ms is not None and client_time_ms < MIN_REACTION_MS:
            self.state = "done"
            winner = 1 - player_idx
            await self.broadcast({
                "type": "cheat",
                "offender": player_idx,
                "winner": winner,
            })
            return

        if client_time_ms is not None:
            reaction_ms = client_time_ms
        elif server_delta_ms is not None:
            reaction_ms = server_delta_ms
        else:
            reaction_ms = float("inf")

        self.fires[player_idx] = reaction_ms

        if len(self.fires) >= len(self.players):
            await self._resolve()
        elif self._resolve_task is None:
            # Grace window: wait up to 300 ms for the other player's shot
            self._resolve_task = asyncio.create_task(self._delayed_resolve())

    async def _delayed_resolve(self):
        await asyncio.sleep(1.0)
        if self.state == "draw":
            await self._resolve()

    async def handle_misfire(self, player_idx: int):
        if self.state not in ("ready", "draw"):
            return
        self.state = "done"
        winner = 1 - player_idx
        await self.broadcast({
            "type": "misfire",
            "offender": player_idx,
            "winner": winner,
        })

    async def _resolve(self):
        if self.state != "draw":
            return
        self.state = "done"
        # Only cancel the pending delayed-resolve task if it isn't the current
        # task — cancelling yourself causes CancelledError at the next await,
        # which would silently abort the broadcast below.
        if self._resolve_task and self._resolve_task is not asyncio.current_task():
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
                room.player_names[0] = msg.get("name", "PLAYER")[:8].upper()
                rooms[code] = room
                player_idx = 0
                await websocket.send(json.dumps({"type": "created", "code": code}))

            elif t == "join":
                code = msg.get("code", "").strip().upper()
                if code not in rooms:
                    await websocket.send(json.dumps({"type": "error", "msg": "ROOM NOT FOUND"}))
                    continue
                room = rooms[code]
                if len(room.players) >= 2:
                    await websocket.send(json.dumps({"type": "error", "msg": "Room full"}))
                    continue
                room.players.append(websocket)
                room.player_names[1] = msg.get("name", "PLAYER")[:8].upper()
                player_idx = 1
                await websocket.send(json.dumps({"type": "joined", "code": code}))
                await room.broadcast({"type": "start", "names": room.player_names})
                asyncio.create_task(room.measure_rtt())
                asyncio.create_task(room.start_round())

            elif t == "fire" and room is not None and player_idx is not None:
                key = msg.get("key", "")
                arrival_time = time.perf_counter()
                if key and room.state in ("draw", "ready") and player_idx not in room.fires:
                    await room.broadcast({"type": "key_pressed", "player": player_idx, "key": key})
                await room.handle_fire(
                    player_idx,
                    client_time_ms=msg.get("client_time_ms"),
                    arrival_time=arrival_time,
                )

            elif t == "misfire" and room is not None and player_idx is not None:
                key = msg.get("key", "")
                if key and room.state in ("ready", "draw"):
                    await room.broadcast({"type": "key_pressed", "player": player_idx, "key": key})
                await room.handle_misfire(player_idx)

            elif t == "pong" and room is not None and player_idx is not None:
                sent_t = msg.get("t")
                if sent_t is not None:
                    rtt_ms = (time.perf_counter() - sent_t) * 1000
                    samples = room.player_rtt_samples.setdefault(player_idx, [])
                    samples.append(rtt_ms)
                    room.player_rtt[player_idx] = min(samples)

            elif t == "rematch_vote" and room is not None and player_idx is not None:
                room.rematch_votes.add(player_idx)
                await room.broadcast({"type": "rematch_vote", "player": player_idx})
                if len(room.rematch_votes) >= len(room.players):
                    room.rematch_votes.clear()
                    await room.broadcast({"type": "start", "names": room.player_names})
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
