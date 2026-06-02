#!/usr/bin/env python3
"""
Офлайн-декодер записей прокси.

Берёт events.jsonl сессии (или сырой .bin) и печатает человекочитаемый
разбор кадров: тип, длина, hex, плюс эвристический разбор тела как
последовательности varint/строк.

Использование:
  python3 decode_capture.py ../captures/<session>/events.jsonl
  python3 decode_capture.py --raw ../captures/<session>/s2c.bin --dir s2c
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from twwk import proto  # noqa: E402
from twwk import opcodes  # noqa: E402


def as_message(payload: bytes):
    """
    Кадр канала сообщений = [srcId:int32 BE][opcode:int32 BE][body].
    Если opcode распознан — вернуть подпись, иначе None.
    """
    if len(payload) < 8:
        return None
    src = int.from_bytes(payload[0:4], "big", signed=True)
    op = int.from_bytes(payload[4:8], "big", signed=True)
    names = opcodes.OPCODE_TO_NAMES.get(op)
    if not names:
        return None
    name = "|".join(dict.fromkeys(names))
    body = payload[8:]
    return f"MSG src={src} op={name}  body[{len(body)}]={body.hex()}"


def guess_payload(payload: bytes) -> str:
    """Эвристика: распознать сообщение по опкоду, иначе varint'ы / строки."""
    msg = as_message(payload)
    if msg:
        return msg
    if not payload:
        return "(empty)"
    out = []
    r = proto.ByteReader(payload)
    try:
        while r.remaining() > 0:
            save = r.pos
            try:
                v = proto.read_varint(r)
            except proto.NeedMoreData:
                break
            # если value похоже на длину строки и хватает байт — покажем строку
            if 0 < v <= r.remaining() <= len(payload):
                peek = r.data[r.pos:r.pos + v]
                if all(32 <= b < 127 or b >= 160 for b in peek):
                    s = proto.decode_legacy_string(peek)
                    out.append(f'str("{s}")')
                    r.pos += v
                    continue
            r.pos = save
            out.append(f"varint={proto.read_varint(r)}")
    except Exception:
        pass
    return " ".join(out) if out else f"raw {payload.hex()}"


def decode_events(path: str) -> None:
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            ev = json.loads(line)
            kind = ev.get("kind")
            if kind == "handshake":
                print(f"[{ev['dir']:>3}] HANDSHAKE {ev}")
            elif kind == "frame":
                payload = bytes.fromhex(ev["payload_hex"])
                arrow = "C->S" if ev["dir"] == "c2s" else "S->C"
                print(f"[{ev.get('t_ms','?'):>10} ms] {arrow} type={ev['type']:>3} "
                      f"len={ev['len']:>4}  {guess_payload(payload)}")
            elif kind == "keepalive":
                print(f"[{ev['dir']:>3}] keepalive (0xFF)")
            elif kind in ("session_open", "session_close", "upstream_error",
                          "frame_desync"):
                print(f"--- {kind}: { {k: v for k, v in ev.items() if k != 'kind'} }")


def decode_raw(path: str, direction: str) -> None:
    data = open(path, "rb").read()
    reader = proto.ByteReader(data)
    # пропустить рукопожатие
    if direction == "c2s" and data[:2] == proto.HELLO:
        print("HELLO 38 0F")
        reader.pos = 2
    elif direction == "s2c" and len(data) >= 2:
        print(f"server handshake: version={data[0]} flags={data[1]}")
        reader.pos = 2
    while reader.remaining() > 0:
        if direction == "c2s" and reader.data[reader.pos] == 0xFF:
            print("keepalive (0xFF)")
            reader.pos += 1
            continue
        frame = proto.try_read_frame(reader)
        if frame is None:
            print(f"(+{reader.remaining()} trailing bytes, frame incomplete)")
            break
        print(f"type={frame.msg_type:>3} len={len(frame.payload):>4}  "
              f"{guess_payload(frame.payload)}")


def main():
    ap = argparse.ArgumentParser(description="Decode TWWK captures")
    ap.add_argument("path", help="events.jsonl или .bin файл")
    ap.add_argument("--raw", action="store_true", help="path это сырой .bin")
    ap.add_argument("--dir", choices=["c2s", "s2c"], default="s2c",
                    help="направление для --raw")
    args = ap.parse_args()
    if args.raw:
        decode_raw(args.path, args.dir)
    else:
        decode_events(args.path)


if __name__ == "__main__":
    main()
