"""
TWWK wire-protocol codec.

Восстановлено из клиента (Third World War of Kings 3D 2.0.112):
  - y/AbstractC0612d.java  -> чтение varint / строк
  - y/C0611c.java          -> запись varint / строк
  - h/C0274b.java          -> рукопожатие и кадрирование
  - h/AbstractC0273a.java  -> чтение кадра: [type][varlen][payload]

Протокол: сырой TCP, порт 5005, БЕЗ шифрования.

Рукопожатие:
  C -> S: 0x38 0x0F            (байты 56, 15)
  S -> C: [serverVer][flags]   (2 байта)
  Рабочая версия = min(serverVer, 56).

Кадр сообщения (в обе стороны, простой путь):
  [type:1][len:varint][payload: len байт]
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Optional

# --- Константы рукопожатия -------------------------------------------------

HELLO = bytes([56, 15])          # 0x38 0x0F — первый пакет клиента
MAX_VERSION = 56                 # min(serverVer, 56) в e()
KEEPALIVE = bytes([0xFF])        # клиент шлёт 0xFF как keepalive при простое >180с

# Маркеры varint
VARINT_SHORT = 126               # дальше short, значение = short + 32768
VARINT_INT = 127                 # дальше int32 (Byte.MAX_VALUE)


class NeedMoreData(Exception):
    """Брошено, когда в буфере не хватает байт для целого кадра/значения."""


# --- Varint (длины и целые) ------------------------------------------------

def read_varint(buf: "ByteReader") -> int:
    """Чтение целого по схеме клиента (AbstractC0612d.b)."""
    marker = buf.read_s8()
    if marker == VARINT_SHORT:          # 126 -> short + 32768
        return buf.read_s16() + 32768
    if marker == VARINT_INT:            # 127 -> int32
        return buf.read_s32()
    return marker + 128                 # иначе byte + 128


def write_varint(out: bytearray, value: int) -> None:
    """Запись целого по схеме клиента (C0611c.d)."""
    if value < 0:
        out.append(127 & 0xFF)
        out += value.to_bytes(4, "big", signed=True)
    elif value < 250:
        out.append((value - 128) & 0xFF)
    elif value < 65536:
        out.append(126 & 0xFF)
        out += (value - 32768).to_bytes(2, "big", signed=True)
    else:
        out.append(127 & 0xFF)
        out += value.to_bytes(4, "big", signed=True)


# --- Строки (кастомная кодировка кириллицы для версии <= 27) ---------------
# Карта восстановлена из y/AbstractC0612d.a() (декодирование байт -> char).

_DECODE_SPECIAL = {
    165: 1168, 168: 1025, 170: 1028, 175: 1031,
    184: 1105, 186: 1108, 191: 1111,
    178: 1030, 179: 1110, 180: 1169,
}


def decode_legacy_char(b: int) -> str:
    b &= 0xFF
    if b in _DECODE_SPECIAL:
        return chr(_DECODE_SPECIAL[b])
    if 192 <= b <= 255:
        return chr(b + 848)
    return chr(b)


def decode_legacy_string(data: bytes) -> str:
    return "".join(decode_legacy_char(b) for b in data)


# --- Низкоуровневый читатель буфера ----------------------------------------

class ByteReader:
    """Читатель поверх bytes с откатом позиции (для частичных кадров)."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def remaining(self) -> int:
        return len(self.data) - self.pos

    def _need(self, n: int) -> None:
        if self.remaining() < n:
            raise NeedMoreData()

    def read(self, n: int) -> bytes:
        self._need(n)
        out = self.data[self.pos:self.pos + n]
        self.pos += n
        return out

    def read_u8(self) -> int:
        return self.read(1)[0]

    def read_s8(self) -> int:
        v = self.read_u8()
        return v - 256 if v >= 128 else v

    def read_s16(self) -> int:
        return int.from_bytes(self.read(2), "big", signed=True)

    def read_s32(self) -> int:
        return int.from_bytes(self.read(4), "big", signed=True)


# --- Кадр ------------------------------------------------------------------

@dataclass
class Frame:
    msg_type: int           # тип-байт сообщения
    payload: bytes          # тело кадра (без типа и длины)
    raw: bytes              # полные байты кадра (type + len + payload)

    def __repr__(self) -> str:
        return f"Frame(type={self.msg_type}, len={len(self.payload)})"


def try_read_frame(reader: ByteReader) -> Optional[Frame]:
    """
    Попытка прочитать один кадр [type][varlen][payload].
    Возвращает Frame или None если данных не хватает (позиция откатывается).
    """
    start = reader.pos
    try:
        msg_type = reader.read_u8()
        length = read_varint(reader)
        if length < 0 or length > (16 * 1024 * 1024):
            raise ValueError(f"unreasonable frame length {length} for type {msg_type}")
        payload = reader.read(length)
    except NeedMoreData:
        reader.pos = start
        return None
    raw = reader.data[start:reader.pos]
    return Frame(msg_type=msg_type, payload=payload, raw=raw)
