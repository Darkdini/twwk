#!/usr/bin/env python3
"""Самотесты кодека и сквозной тест записывающего прокси."""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from twwk import proto  # noqa: E402


def test_varint_roundtrip():
    values = [0, 1, 121, 122, 200, 249, 250, 255, 1000, 32767, 32768,
              65535, 65536, 1_000_000, -1, -1000]
    for v in values:
        out = bytearray()
        proto.write_varint(out, v)
        r = proto.ByteReader(bytes(out))
        got = proto.read_varint(r)
        assert got == v, f"varint roundtrip failed: {v} -> {got}"
        assert r.remaining() == 0, f"trailing bytes for {v}"
    print(f"  varint roundtrip OK ({len(values)} values)")


def test_frame_roundtrip():
    payload = bytes(range(40))
    out = bytearray([7])
    proto.write_varint(out, len(payload))
    out += payload
    r = proto.ByteReader(bytes(out))
    frame = proto.try_read_frame(r)
    assert frame is not None
    assert frame.msg_type == 7
    assert frame.payload == payload
    assert r.remaining() == 0
    print("  frame roundtrip OK")


def test_partial_frame():
    payload = bytes(i % 256 for i in range(300))   # длина > 249 -> 2-байтовый varint
    full = bytearray([3])
    proto.write_varint(full, len(payload))
    full += payload
    # дать только половину — try_read_frame должен вернуть None и не сдвинуть pos
    r = proto.ByteReader(bytes(full[: len(full) // 2]))
    assert proto.try_read_frame(r) is None
    assert r.pos == 0
    print("  partial frame handling OK")


def test_legacy_string():
    # 0xE0 (224) -> 224+848 = 1072 = 'а' (кириллица)
    assert proto.decode_legacy_string(bytes([224, 225, 226])) == "абв"
    print("  legacy cyrillic decode OK")


async def _fake_upstream(reader, writer):
    # имитируем сервер: ждём HELLO, отвечаем version=56 flags=0, затем шлём один кадр
    await reader.readexactly(2)
    writer.write(bytes([56, 0]))
    out = bytearray([5])
    proto.write_varint(out, 3)
    out += b"hey"
    writer.write(bytes(out))
    await writer.drain()
    # эхо клиентских данных, чтобы закрылось чисто
    try:
        while await reader.read(1024):
            pass
    except Exception:
        pass
    writer.close()


async def test_proxy_end_to_end():
    from proxy import record_proxy  # noqa

    up = await asyncio.start_server(_fake_upstream, "127.0.0.1", 0)
    up_port = up.sockets[0].getsockname()[1]

    tmp = tempfile.mkdtemp(prefix="twwk_selftest_")

    import types
    Args = types.SimpleNamespace(out=tmp, up_host="127.0.0.1", up_port=up_port)

    counter = [0]
    proxy = await asyncio.start_server(
        lambda r, w: record_proxy.handle_client(r, w, Args, counter),
        "127.0.0.1", 0)
    proxy_port = proxy.sockets[0].getsockname()[1]

    # клиент
    cr, cw = await asyncio.open_connection("127.0.0.1", proxy_port)
    cw.write(proto.HELLO)
    await cw.drain()
    ver = await cr.readexactly(2)
    assert ver == bytes([56, 0]), ver.hex()
    frame_bytes = await cr.readexactly(5)  # type+len+'hey' = 1+1+3
    cw.write(b"")  # отправим клиентский кадр
    out = bytearray([9]); proto.write_varint(out, 2); out += b"ok"
    cw.write(bytes(out)); await cw.drain()
    await asyncio.sleep(0.2)
    cw.close()

    up.close(); proxy.close()
    await up.wait_closed(); await proxy.wait_closed()

    # проверяем, что запись создана
    sessions = os.listdir(tmp)
    assert sessions, "no session dir created"
    sdir = os.path.join(tmp, sessions[0])
    assert os.path.getsize(os.path.join(sdir, "s2c.bin")) > 0
    assert os.path.getsize(os.path.join(sdir, "events.jsonl")) > 0
    print(f"  proxy end-to-end OK (session in {sdir})")


def main():
    print("Running TWWK selftests...")
    test_varint_roundtrip()
    test_frame_roundtrip()
    test_partial_frame()
    test_legacy_string()
    asyncio.run(test_proxy_end_to_end())
    print("ALL TESTS PASSED")


if __name__ == "__main__":
    main()
