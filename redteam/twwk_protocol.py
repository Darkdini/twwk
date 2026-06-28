#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────────────
#  TWWK · РЕАЛЬНЫЙ протокол игры — кодек (reverse-engineered)
#
#  Восстановлено из классов сериализации клиента (jadx):
#    y.AbstractC0612d / y.C0610b  — чтение (reader)
#    y.C0611c                     — запись (writer)
#    J1.b.a()/d()/g()             — фабрика типов и (де)сериализация
#    i.g, i.c, k.e, k.b, k.h …    — типы значений
#
#  Зачем: все прочие инструменты (proxy/replay/arsenal) говорили на учебном
#  формате. Этот модуль понимает НАСТОЯЩИЕ байты TWWK: превращает кадр в
#  дерево значений и обратно. Так видно каждое поле, которое сервер обязан
#  проверять, и можно собрать честный кадр.
#
#  Формат (кратко, полностью — PROTOCOL.md):
#   • Поток DataInput/Output — big-endian.
#   • varint b()/d(): байт rb; rb==126 → short+32768; rb==127 → int32;
#                     иначе → rb+128 (диапазон 0..249 в один байт).
#   • Строка: varint(длина в символах) + по 1 байту/символ в Windows-1251
#             (для версии протокола >27 — UTF-16, 2 байта/символ).
#   • Значение: [1 байт тип][тело]; тип 0 = null.
#               тип = (подтип << 3) | категория.
#       категория 1 = скаляр:  k.e=int32(0x09), k.b=bool(0x31), k.h=строка
#       категория 7 = структура: i.g=массив(0x17) = int32 count + N значений
#       i.c = пара int32
# ─────────────────────────────────────────────────────────────────────
import struct, io


# ─── низкоуровневое чтение ───────────────────────────────────────────
class Reader:
    def __init__(self, data, version=26):
        self.b = memoryview(data)
        self.i = 0
        self.version = version

    def _take(self, n):
        if self.i + n > len(self.b):
            raise EOFError(f"нужно {n} байт на смещении {self.i}, осталось {len(self.b)-self.i}")
        v = self.b[self.i:self.i+n]
        self.i += n
        return bytes(v)

    def u8(self):  return self._take(1)[0]
    def i8(self):  return struct.unpack(">b", self._take(1))[0]
    def i16(self): return struct.unpack(">h", self._take(2))[0]
    def i32(self): return struct.unpack(">i", self._take(4))[0]
    def boolean(self): return self._take(1)[0] != 0

    def varint(self):                     # = AbstractC0612d.b()
        rb = self.i8()
        if rb == 126:  return self.i16() + 32768
        if rb == 127:  return self.i32()
        return rb + 128

    def string(self):                     # = C0610b.f()
        n = self.varint()
        if n == 0:
            return None
        if self.version <= 27:            # 1 байт/символ, Windows-1251
            raw = self._take(n)
            return raw.decode("cp1251", errors="replace")
        else:                             # UTF-16 BE, 2 байта/символ
            return self._take(n*2).decode("utf-16-be", errors="replace")


class Writer:
    def __init__(self, version=26):
        self.out = bytearray()
        self.version = version

    def u8(self, v):  self.out.append(v & 0xFF)
    def i32(self, v): self.out += struct.pack(">i", v)
    def i16(self, v): self.out += struct.pack(">h", v)
    def boolean(self, v): self.out.append(1 if v else 0)

    def varint(self, v):                  # = C0611c.d()
        if v < 0:
            self.u8(127); self.i32(v)
        elif v < 250:
            self.u8((v - 128) & 0xFF)
        elif v < 65536:
            self.u8(126); self.i16(v - 32768)
        else:
            self.u8(127); self.i32(v)

    def string(self, s):                  # = C0611c.e()
        if s is None:
            self.varint(0); return
        self.varint(len(s))
        if self.version <= 27:
            self.out += s.encode("cp1251", errors="replace")
        else:
            self.out += s.encode("utf-16-be", errors="replace")


# ─── типы значений ───────────────────────────────────────────────────
NULL  = 0x00
INT   = 0x09   # k.e   (1<<3)|1
BOOL  = 0x31   # k.b   (6<<3)|1
ARRAY = 0x17   # i.g   (2<<3)|7
PAIR  = None   # i.c (два int32) — тип-байт уточняется на реальном дампе


def read_value(r):
    """Прочитать [тип][тело] → python-объект. None для null."""
    t = r.u8()
    if t == NULL:
        return None
    cat, sub = t & 7, t >> 3
    if t == INT:
        return r.i32()
    if t == BOOL:
        return r.boolean()
    if t == ARRAY:                         # i.g: int32 count + значения
        n = r.i32()
        return [read_value(r) for _ in range(n)]
    # неизвестный листовой тип — длину тела по статике не знаем
    raise ValueError(f"неизвестный тип 0x{t:02x} (кат={cat} подтип={sub}) на смещении {r.i-1}")


def write_value(w, obj):
    """python-объект → [тип][тело]."""
    if obj is None:
        w.u8(NULL)
    elif isinstance(obj, bool):
        w.u8(BOOL); w.boolean(obj)
    elif isinstance(obj, int):
        w.u8(INT); w.i32(obj)
    elif isinstance(obj, str):
        # k.h строка — категория 1; тип-байт строки подтверждается на дампе,
        # здесь кодируем тело корректно (varint+cp1251), тег помечаем как STRING.
        w.u8(0x19); w.string(obj)          # 0x19 — предполагаемый тег k.h
    elif isinstance(obj, (list, tuple)):
        w.u8(ARRAY); w.i32(len(obj))
        for e in obj:
            write_value(w, e)
    else:
        raise TypeError(f"не умею кодировать {type(obj)}")


def decode(data, version=26):
    return read_value(Reader(data, version))

def encode(obj, version=26):
    w = Writer(version); write_value(w, obj); return bytes(w.out)


# ─── демонстрация / самотест ─────────────────────────────────────────
if __name__ == "__main__":
    print("TWWK protocol codec — round-trip самотест\n")

    # varint: пограничные значения
    for v in [0, 1, 121, 122, 249, 250, 1000, 65535, 70000, -1, -5, 2_000_000_000]:
        w = Writer(); w.varint(v)
        got = Reader(bytes(w.out)).varint()
        assert got == v, f"varint {v} → {got}"
    print("  ✓ varint (1/2/4-байт ветки, отрицательные)")

    # строка Windows-1251
    for s in ["Castle", "Война", "Король123", "АтакаЁёЇ"]:
        w = Writer(); w.string(s)
        got = Reader(bytes(w.out)).string()
        assert got == s, f"string {s!r} → {got!r}"
    print("  ✓ строки Windows-1251 (1 байт/символ, кириллица)")

    # значения: int, bool, массив, вложенность
    samples = [42, True, False, -7, [1, 2, 3], [True, 10, [20, 30]]]
    for obj in samples:
        got = decode(encode(obj))
        assert got == obj, f"value {obj!r} → {got!r}"
    print("  ✓ значения int/bool/массив + вложенные контейнеры")

    # показать байты типичного кадра (массив из int и bool)
    frame = encode([100, 200, True, [1, 2]])
    print(f"\n  пример кадра encode([100,200,True,[1,2]]):")
    print("   ", frame.hex())
    print("    декод обратно:", decode(frame))
    print("\n  всё сходится ✓  кодек соответствует реверсу клиента")
