#!/usr/bin/env python3
"""
TWWK сервер — заготовка ("наш сервер").

Два режима:

  1. replay  — воспроизводит записанную сессию: отвечает на рукопожатие
     теми же байтами версии, что прислал реальный сервер, и проигрывает
     все записанные кадры S->C (с таймингами или без). Клиентские кадры
     логируются. Это самый быстрый способ проверить, что клиент в принципе
     «оживает» на нашем сервере.

  2. serve   — каркас живого сервера: принимает HELLO, шлёт version/flags,
     дальше диспетчеризует входящие кадры по типам в обработчики. Сюда
     постепенно переносится логика, разобранная по записям.

Запуск:
  python3 server.py replay --session captures/<session> [--realtime]
  python3 server.py serve  --listen 0.0.0.0:5005 --version 56 --flags 0
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from twwk import proto  # noqa: E402


# --------------------------------------------------------------------------
# Режим REPLAY
# --------------------------------------------------------------------------

def load_session(session_dir: str):
    """Возвращает (server_version, flags, [s2c frame events], events)."""
    events = []
    with open(os.path.join(session_dir, "events.jsonl"), encoding="utf-8") as f:
        for line in f:
            events.append(json.loads(line))
    server_version, flags = proto.MAX_VERSION, 0
    for ev in events:
        if ev.get("kind") == "handshake" and ev.get("dir") == "s2c":
            server_version = ev.get("server_version", server_version)
            flags = ev.get("flags", flags)
            break
    return server_version, flags, events


async def replay_handle(reader, writer, events, server_version, flags, realtime):
    peer = writer.get_extra_info("peername")
    print(f"[replay] client {peer}")

    # Ждём HELLO от клиента.
    hello = await reader.readexactly(2)
    if hello != proto.HELLO:
        print(f"[replay] unexpected hello: {hello.hex()} (ждали 38 0f)")
    writer.write(bytes([server_version & 0xFF, flags & 0xFF]))
    await writer.drain()
    print(f"[replay] sent handshake version={server_version} flags={flags}")

    # Логируем входящие кадры клиента в фоне.
    async def log_client():
        buf = bytearray()
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                buf += data
                while buf:
                    if buf[0] == 0xFF:
                        print("[replay] <- client keepalive")
                        del buf[:1]
                        continue
                    r = proto.ByteReader(bytes(buf))
                    frame = proto.try_read_frame(r)
                    if frame is None:
                        break
                    print(f"[replay] <- client {frame}")
                    del buf[:r.pos]
        except (asyncio.IncompleteReadError, ConnectionResetError):
            pass

    client_task = asyncio.create_task(log_client())

    # Проигрываем записанные кадры S->C.
    prev_t = None
    for ev in events:
        if ev.get("kind") != "frame" or ev.get("dir") != "s2c":
            continue
        if realtime and prev_t is not None:
            delay = (ev.get("t_ms", 0) - prev_t) / 1000.0
            if delay > 0:
                await asyncio.sleep(min(delay, 5.0))
        prev_t = ev.get("t_ms", prev_t)
        out = bytearray([ev["type"]])
        payload = bytes.fromhex(ev["payload_hex"])
        proto.write_varint(out, len(payload))
        out += payload
        writer.write(bytes(out))
        await writer.drain()
        print(f"[replay] -> type={ev['type']} len={len(payload)}")

    print("[replay] all recorded S->C frames sent; keeping connection open")
    await client_task


async def replay_main(args):
    server_version, flags, events = load_session(args.session)
    server = await asyncio.start_server(
        lambda r, w: replay_handle(r, w, events, server_version, flags,
                                   args.realtime),
        *args.listen.rsplit(":", 1)[0:1] + [int(args.listen.rsplit(":", 1)[1])],
    )
    print(f"[replay] listening on {args.listen}, session={args.session}")
    async with server:
        await server.serve_forever()


# --------------------------------------------------------------------------
# Режим SERVE (каркас живого сервера)
# --------------------------------------------------------------------------

# Реестр обработчиков: msg_type -> async def handler(ctx, payload) -> None
HANDLERS = {}


def handler(msg_type: int):
    def deco(fn):
        HANDLERS[msg_type] = fn
        return fn
    return deco


class Conn:
    def __init__(self, reader, writer, version):
        self.reader = reader
        self.writer = writer
        self.version = version

    def send(self, msg_type: int, payload: bytes = b"") -> None:
        out = bytearray([msg_type & 0xFF])
        proto.write_varint(out, len(payload))
        out += payload
        self.writer.write(bytes(out))


async def serve_handle(reader, writer, version, flags):
    peer = writer.get_extra_info("peername")
    print(f"[serve] client {peer}")
    try:
        hello = await reader.readexactly(2)
    except asyncio.IncompleteReadError:
        return
    if hello != proto.HELLO:
        print(f"[serve] bad hello {hello.hex()}, closing")
        writer.close()
        return
    writer.write(bytes([version & 0xFF, flags & 0xFF]))
    await writer.drain()
    conn = Conn(reader, writer, min(version, proto.MAX_VERSION))

    buf = bytearray()
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            buf += data
            while buf:
                if buf[0] == 0xFF:
                    del buf[:1]
                    continue
                r = proto.ByteReader(bytes(buf))
                frame = proto.try_read_frame(r)
                if frame is None:
                    break
                del buf[:r.pos]
                h = HANDLERS.get(frame.msg_type)
                if h:
                    await h(conn, frame.payload)
                else:
                    print(f"[serve] no handler for type={frame.msg_type} "
                          f"len={len(frame.payload)}")
            await writer.drain()
    except (asyncio.IncompleteReadError, ConnectionResetError):
        pass
    print(f"[serve] {peer} disconnected")


async def serve_main(args):
    host, port = args.listen.rsplit(":", 1)
    server = await asyncio.start_server(
        lambda r, w: serve_handle(r, w, args.version, args.flags),
        host, int(port),
    )
    print(f"[serve] listening on {args.listen} version={args.version} "
          f"flags={args.flags}  handlers={sorted(HANDLERS)}")
    async with server:
        await server.serve_forever()


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description="TWWK server (replay / serve)")
    sub = ap.add_subparsers(dest="mode", required=True)

    rp = sub.add_parser("replay", help="воспроизвести записанную сессию")
    rp.add_argument("--session", required=True, help="папка captures/<session>")
    rp.add_argument("--listen", default="0.0.0.0:5005")
    rp.add_argument("--realtime", action="store_true",
                    help="соблюдать исходные тайминги между кадрами")

    sv = sub.add_parser("serve", help="каркас живого сервера")
    sv.add_argument("--listen", default="0.0.0.0:5005")
    sv.add_argument("--version", type=int, default=proto.MAX_VERSION)
    sv.add_argument("--flags", type=int, default=0)

    args = ap.parse_args()
    coro = replay_main(args) if args.mode == "replay" else serve_main(args)
    try:
        asyncio.run(coro)
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
