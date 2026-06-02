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

  3. login   — верный (побайтовый) реплей записанного S->C: отвечает на
     рукопожатие и шлёт точные байты сервера до экрана логина, попутно
     расшифровывая входящие C->S (опкоды + строки). Самый быстрый способ
     «оживить» клиент до формы логина на нашем сервере.

Запуск:
  python3 server.py login  --session captures/<session> --listen 0.0.0.0:5005
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
from twwk import opcodes  # noqa: E402


def _strings16(b: bytes, mn: int = 3):
    """Извлечь UTF-16BE строки (ASCII/латиница/кириллица) из payload."""
    out, cur, i, n = [], [], 0, len(b)
    while i + 1 < n:
        cp = (b[i] << 8) | b[i + 1]
        if (32 <= cp < 127) or (0x400 <= cp <= 0x4FF):
            cur.append(chr(cp)); i += 2
        else:
            if len(cur) >= mn:
                out.append("".join(cur))
            cur = []; i += 1
    if len(cur) >= mn:
        out.append("".join(cur))
    return out


def describe_frame(frame: "proto.Frame") -> str:
    """Человекочитаемое описание входящего кадра: опкод + строки."""
    p = frame.payload
    op = ""
    if len(p) >= 8:
        src = int.from_bytes(p[0:4], "big", signed=True)
        opc = int.from_bytes(p[4:8], "big", signed=True)
        on = opcodes.OPCODE_TO_NAMES.get(opc)
        sn = opcodes.OPCODE_TO_NAMES.get(src)
        op = (f" src={'|'.join(dict.fromkeys(sn)) if sn else src}"
              f" op={'|'.join(dict.fromkeys(on)) if on else opc}")
    ss = _strings16(p)
    txt = ("  «" + " | ".join(ss[:6]) + "»") if ss else ""
    return f"type={frame.msg_type} len={len(p)}{op}{txt}"


# --------------------------------------------------------------------------
# Режим LOGIN — верный (побайтовый) реплей старта до экрана логина
# --------------------------------------------------------------------------

async def login_log_client(reader):
    """Читает и печатает входящие C->S кадры с расшифровкой."""
    buf = bytearray()
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            buf += data
            while buf:
                if buf[0] == 0xFF:
                    print("  <- C keepalive (0xFF)")
                    del buf[:1]
                    continue
                r = proto.ByteReader(bytes(buf))
                try:
                    frame = proto.try_read_frame(r)
                except ValueError:
                    del buf[:1]
                    continue
                if frame is None:
                    break
                print("  <- C " + describe_frame(frame))
                del buf[:r.pos]
    except (asyncio.IncompleteReadError, ConnectionResetError):
        pass


async def login_handle(reader, writer, s2c_bytes, pace):
    peer = writer.get_extra_info("peername")
    print(f"\n[login] client connected: {peer}")
    try:
        hello = await reader.readexactly(2)
    except asyncio.IncompleteReadError:
        return
    print(f"[login] client HELLO = {hello.hex()}")
    if hello != proto.HELLO:
        print(f"[login] WARN: ждали 38 0f, получили {hello.hex()}")

    # Фоновый разбор того, что шлёт клиент.
    client_task = asyncio.create_task(login_log_client(reader))

    # Верный побайтовый реплей записанного S->C (начинается с рукопожатия
    # 56 15, затем хост-лист, экран загрузки и форма логина).
    print(f"[login] стримлю {len(s2c_bytes)} байт записанного S->C "
          f"(рукопожатие + экран логина)...")
    CHUNK = 1024
    try:
        for i in range(0, len(s2c_bytes), CHUNK):
            writer.write(s2c_bytes[i:i + CHUNK])
            await writer.drain()
            if pace:
                await asyncio.sleep(pace)
        print("[login] весь записанный S->C отправлен; держу соединение открытым")
    except (ConnectionResetError, BrokenPipeError, ConnectionError):
        print(f"[login] {peer} закрыл соединение во время стрима")
    await client_task
    try:
        writer.close()
    except Exception:
        pass
    print(f"[login] {peer} отключился")


def strip_host_frames(s2c: bytes):
    """
    Удаляет из записанного S->C кадры с хост-листом (NWHOST,
    socket://mmog…:5005), чтобы клиент не перезаписал список серверов и не
    ушёл на реальный сервер. Возвращает (отфильтрованные байты, сколько убрано).
    """
    pats = [b"\x00\x35\x00\x30\x00\x30\x00\x35",          # "5005" UTF-16BE
            b"\x00\x73\x00\x6f\x00\x63\x00\x6b\x00\x65"]   # "socke" UTF-16BE
    r = proto.ByteReader(s2c)
    out = bytearray(r.read(2))   # рукопожатие 56 15
    dropped = 0
    while r.remaining() > 0:
        start = r.pos
        try:
            fr = proto.try_read_frame(r)
        except ValueError:
            out += s2c[start:]
            break
        if fr is None:
            out += s2c[start:]
            break
        if any(p in fr.payload for p in pats):
            dropped += 1
            continue
        out += fr.raw
    return bytes(out), dropped


async def login_main(args):
    s2c_path = os.path.join(args.session, "s2c.bin")
    s2c_bytes = open(s2c_path, "rb").read()
    if not args.keep_hosts:
        s2c_bytes, dropped = strip_host_frames(s2c_bytes)
        print(f"[login] вырезано хост-лист кадров (NWHOST): {dropped}")
    host, port = args.listen.rsplit(":", 1)
    server = await asyncio.start_server(
        lambda r, w: login_handle(r, w, s2c_bytes, args.pace),
        host, int(port),
    )
    print(f"[login] listening on {args.listen}")
    print(f"[login] session={args.session}  S->C={len(s2c_bytes)} байт")
    print("[login] наведи клиент (conect.conf -> этот хост:порт) и заходи")
    async with server:
        await server.serve_forever()


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

    lg = sub.add_parser("login", help="верный реплей старта до экрана логина")
    lg.add_argument("--session", required=True, help="папка captures/<session>")
    lg.add_argument("--listen", default="0.0.0.0:5005")
    lg.add_argument("--pace", type=float, default=0.0,
                    help="пауза (сек) между чанками S->C, по умолчанию без пауз")
    lg.add_argument("--keep-hosts", action="store_true",
                    help="НЕ вырезать хост-лист (по умолчанию вырезается, чтобы "
                         "клиент не ушёл на реальный сервер)")

    args = ap.parse_args()
    coro = {"replay": replay_main, "serve": serve_main,
            "login": login_main}[args.mode](args)
    try:
        asyncio.run(coro)
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
