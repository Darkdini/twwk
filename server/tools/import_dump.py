#!/usr/bin/env python3
"""
Импорт дампа, снятого вшитым в клиент логгером (twwk_dump.bin), в формат
сессии прокси (events.jsonl + c2s.bin + s2c.bin), который понимают
decode_capture.py и server.py replay.

Формат записи в twwk_dump.bin (см. smali Lz/T;->w):
  [1 байт dir: 'S'=от сервера / 'C'=к серверу][4 байта BE длина][данные]

Файл лежит на телефоне в приватном каталоге приложения:
  /sdcard/Android/data/start.browser.gameTWWK/files/twwk_dump.bin

Использование:
  python3 import_dump.py twwk_dump.bin -o ../captures/from_device
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from twwk import proto  # noqa: E402

DIR_FROM_SERVER = ord("S")   # s2c
DIR_TO_SERVER = ord("C")     # c2s


def read_records(path: str):
    data = open(path, "rb").read()
    i = 0
    n = len(data)
    while i + 5 <= n:
        d = data[i]
        length = int.from_bytes(data[i + 1:i + 5], "big")
        i += 5
        if i + length > n:
            print(f"[!] усечённая запись на смещении {i-5}, обрываю", file=sys.stderr)
            break
        yield d, data[i:i + length]
        i += length


def main():
    ap = argparse.ArgumentParser(description="Импорт дампа клиента в сессию")
    ap.add_argument("dump", help="twwk_dump.bin с телефона")
    ap.add_argument("-o", "--out", required=True, help="папка сессии на выходе")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    f_jsonl = open(os.path.join(args.out, "events.jsonl"), "w", encoding="utf-8")
    f_c2s = open(os.path.join(args.out, "c2s.bin"), "wb")
    f_s2c = open(os.path.join(args.out, "s2c.bin"), "wb")

    # Аккумуляторы для покадрового разбора каждого направления.
    bufs = {"c2s": bytearray(), "s2c": bytearray()}
    handshake = {"c2s": False, "s2c": False}
    n_chunks = n_frames = 0

    def emit(obj):
        f_jsonl.write(json.dumps(obj, ensure_ascii=False) + "\n")

    emit({"kind": "session_open", "source": "device_dump", "dump": args.dump})

    for d, payload in read_records(args.dump):
        direction = "s2c" if d == DIR_FROM_SERVER else "c2s"
        (f_s2c if direction == "s2c" else f_c2s).write(payload)
        emit({"kind": "chunk", "dir": direction, "len": len(payload),
              "hex": payload.hex()})
        n_chunks += 1

        buf = bufs[direction]
        buf += payload

        # Рукопожатие
        if not handshake[direction]:
            if direction == "c2s":
                if len(buf) >= 2 and bytes(buf[:2]) == proto.HELLO:
                    emit({"kind": "handshake", "dir": "c2s",
                          "detail": "client HELLO 38 0F"})
                    del buf[:2]
                    handshake["c2s"] = True
                else:
                    continue
            else:
                if len(buf) >= 2:
                    ver, flags = buf[0], buf[1]
                    emit({"kind": "handshake", "dir": "s2c",
                          "server_version": ver, "flags": flags,
                          "negotiated": min(ver, proto.MAX_VERSION)})
                    del buf[:2]
                    handshake["s2c"] = True
                else:
                    continue

        # Кадры
        while buf:
            if direction == "c2s" and buf[0] == 0xFF:
                emit({"kind": "keepalive", "dir": "c2s"})
                del buf[:1]
                continue
            reader = proto.ByteReader(bytes(buf))
            try:
                frame = proto.try_read_frame(reader)
            except ValueError as e:
                emit({"kind": "frame_desync", "dir": direction, "reason": str(e)})
                break
            if frame is None:
                break
            emit({"kind": "frame", "dir": direction, "type": frame.msg_type,
                  "len": len(frame.payload), "payload_hex": frame.payload.hex()})
            n_frames += 1
            del buf[:reader.pos]

    emit({"kind": "session_close"})
    for f in (f_jsonl, f_c2s, f_s2c):
        f.close()

    print(f"Импортировано: {n_chunks} chunk'ов, {n_frames} кадров -> {args.out}")
    print(f"  events.jsonl, c2s.bin, s2c.bin")
    print(f"Разбор:   python3 tools/decode_capture.py {args.out}/events.jsonl")
    print(f"Replay:   python3 server.py replay --session {args.out}")


if __name__ == "__main__":
    main()
