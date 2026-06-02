#!/usr/bin/env python3
"""
TWWK recording proxy (MITM).

Сидит между игровым клиентом и реальным сервером, прозрачно проксирует
TCP-трафик в обе стороны и ЗАПИСЫВАЕТ всё, что нужно для последующего
воспроизведения на нашем сервере:

  1. Сырой дамп каждого направления (.bin) — это ground truth, без потерь.
  2. Структурный лог JSONL: по событию на каждый chunk (timestamp, dir, hex)
     и по событию на каждый распознанный кадр [type][len][payload].
  3. Детект рукопожатия (0x38 0x0F -> 2 байта ответа сервера).

Как направить клиент на прокси (любой из вариантов):
  A) Распаковать APK, заменить assets/conect.conf на
        socket://<IP_прокси>:5005|socket://<IP_прокси>:5005
     пересобрать (apktool b) и переподписать (apksigner). Прокси при этом
     ходит на настоящий mmog1.com:5005.
  B) DNS/hosts на устройстве: mmog1.com -> IP прокси; прокси с --upstream
     mmog1.com будет резолвить апстрим до старта (или укажите реальный IP).

Зависимостей нет (только стандартная библиотека). Python 3.8+.

Примеры:
  # Слушать 0.0.0.0:5005, форвардить на реальный сервер:
  python3 record_proxy.py --listen 0.0.0.0:5005 --upstream mmog1.com:5005

  # Второй апстрим:
  python3 record_proxy.py --listen 0.0.0.0:5006 --upstream mmog2.com:5005
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone

# Позволяем запускать как скрипт из любой папки.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from twwk import proto  # noqa: E402


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_hostport(s: str, default_port: int = 5005):
    if ":" in s:
        host, port = s.rsplit(":", 1)
        return host, int(port)
    return s, default_port


class SessionRecorder:
    """Запись одной клиент<->сервер сессии в файлы."""

    def __init__(self, out_dir: str, session_id: str):
        self.dir = os.path.join(out_dir, session_id)
        os.makedirs(self.dir, exist_ok=True)
        self.jsonl = open(os.path.join(self.dir, "events.jsonl"), "ab", buffering=0)
        self.raw_c2s = open(os.path.join(self.dir, "c2s.bin"), "ab", buffering=0)
        self.raw_s2c = open(os.path.join(self.dir, "s2c.bin"), "ab", buffering=0)
        self.t0 = time.monotonic()

    def _ms(self) -> float:
        return round((time.monotonic() - self.t0) * 1000, 3)

    def event(self, **fields) -> None:
        fields.setdefault("t_ms", self._ms())
        fields.setdefault("ts", now_iso())
        self.jsonl.write((json.dumps(fields, ensure_ascii=False) + "\n").encode("utf-8"))

    def chunk(self, direction: str, data: bytes) -> None:
        (self.raw_c2s if direction == "c2s" else self.raw_s2c).write(data)
        self.event(kind="chunk", dir=direction, len=len(data), hex=data.hex())

    def frame(self, direction: str, frame: proto.Frame) -> None:
        self.event(
            kind="frame", dir=direction, type=frame.msg_type,
            len=len(frame.payload), payload_hex=frame.payload.hex(),
        )

    def close(self) -> None:
        for f in (self.jsonl, self.raw_c2s, self.raw_s2c):
            try:
                f.close()
            except Exception:
                pass


class DirectionParser:
    """
    Буферизует поток одного направления, выделяет рукопожатие и кадры.
    Если кадрирование «поплывёт» (нестандартный путь записи клиента), мы
    всё равно сохраняем сырые байты — replay строится по .bin, фреймы лишь
    аннотация.
    """

    def __init__(self, recorder: SessionRecorder, direction: str):
        self.rec = recorder
        self.dir = direction
        self.buf = bytearray()
        self.handshake_done = False
        self.frame_sync = True   # пока кадры читаются ровно — аннотируем

    def feed(self, data: bytes) -> None:
        self.rec.chunk(self.dir, data)
        self.buf += data
        self._drain()

    def _drain(self) -> None:
        # Рукопожатие
        if not self.handshake_done:
            if self.dir == "c2s":
                if len(self.buf) >= 2 and bytes(self.buf[:2]) == proto.HELLO:
                    self.rec.event(kind="handshake", dir=self.dir,
                                   detail="client HELLO 38 0F")
                    del self.buf[:2]
                    self.handshake_done = True
                else:
                    return  # ждём ровно hello
            else:  # s2c: ответ сервера — 2 байта version/flags
                if len(self.buf) >= 2:
                    ver, flags = self.buf[0], self.buf[1]
                    self.rec.event(kind="handshake", dir=self.dir,
                                   server_version=ver, flags=flags,
                                   negotiated=min(ver, proto.MAX_VERSION))
                    del self.buf[:2]
                    self.handshake_done = True
                else:
                    return

        if not self.frame_sync:
            return  # просто копим сырьё, кадры больше не парсим

        # Кадры
        while self.buf:
            # keepalive 0xFF (клиент -> сервер) как одиночный байт
            if self.dir == "c2s" and self.buf[0] == 0xFF:
                self.rec.event(kind="keepalive", dir=self.dir)
                del self.buf[:1]
                continue
            reader = proto.ByteReader(bytes(self.buf))
            try:
                frame = proto.try_read_frame(reader)
            except ValueError as e:
                # кадрирование рассинхронизировалось — переключаемся на raw-only
                self.rec.event(kind="frame_desync", dir=self.dir, reason=str(e))
                self.frame_sync = False
                return
            if frame is None:
                return  # не хватает данных, ждём ещё
            self.rec.frame(self.dir, frame)
            del self.buf[:reader.pos]


async def pump(src: asyncio.StreamReader, dst: asyncio.StreamWriter,
               parser: DirectionParser, label: str) -> None:
    try:
        while True:
            data = await src.read(65536)
            if not data:
                break
            parser.feed(data)
            dst.write(data)
            await dst.drain()
    except (ConnectionResetError, BrokenPipeError, asyncio.IncompleteReadError):
        pass
    finally:
        try:
            dst.close()
        except Exception:
            pass


async def handle_client(client_reader, client_writer, args, counter):
    peer = client_writer.get_extra_info("peername")
    session_id = datetime.now().strftime("%Y%m%d-%H%M%S-") + f"{counter[0]:04d}"
    counter[0] += 1
    rec = SessionRecorder(args.out, session_id)
    rec.event(kind="session_open", client=str(peer),
              upstream=f"{args.up_host}:{args.up_port}")
    print(f"[+] {session_id} <- {peer}  ->  {args.up_host}:{args.up_port}")

    try:
        server_reader, server_writer = await asyncio.open_connection(
            args.up_host, args.up_port)
    except OSError as e:
        rec.event(kind="upstream_error", error=str(e))
        rec.close()
        client_writer.close()
        print(f"[!] {session_id} upstream connect failed: {e}")
        return

    p_c2s = DirectionParser(rec, "c2s")
    p_s2c = DirectionParser(rec, "s2c")

    await asyncio.gather(
        pump(client_reader, server_writer, p_c2s, "c2s"),
        pump(server_reader, client_writer, p_s2c, "s2c"),
    )

    rec.event(kind="session_close")
    rec.close()
    print(f"[-] {session_id} closed")


async def main_async(args):
    args.up_host, args.up_port = parse_hostport(args.upstream)
    listen_host, listen_port = parse_hostport(args.listen)
    counter = [0]

    server = await asyncio.start_server(
        lambda r, w: handle_client(r, w, args, counter),
        listen_host, listen_port,
    )
    addrs = ", ".join(str(s.getsockname()) for s in server.sockets)
    print(f"TWWK recording proxy on {addrs} -> {args.up_host}:{args.up_port}")
    print(f"Captures: {os.path.abspath(args.out)}")
    async with server:
        await server.serve_forever()


def main():
    ap = argparse.ArgumentParser(description="TWWK recording MITM proxy")
    ap.add_argument("--listen", default="0.0.0.0:5005",
                    help="host:port для прослушивания (по умолчанию 0.0.0.0:5005)")
    ap.add_argument("--upstream", default="mmog1.com:5005",
                    help="реальный сервер host:port (по умолчанию mmog1.com:5005)")
    ap.add_argument("--out", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "captures"),
        help="папка для записей")
    args = ap.parse_args()
    try:
        asyncio.run(main_async(args))
    except KeyboardInterrupt:
        print("\nbye")


if __name__ == "__main__":
    main()
