"""
Каталог опкодов TWWK.

Опкоды в клиенте задаются именами через o.AbstractC0405c.b(name), который
вычисляет ХЕШ имени (а не порядковый номер):

  base-40 по первым 6 символам, регистронезависимо, минус 2^31:
    a-z / A-Z -> 1..26
    0-9       -> 27..36
    ':'       -> 37
    '\\'      -> 38
    прочее    -> 39
    value = sum(code[i] * 40**i for i<6) - 2**31

i.i.c() читает [srcId:int][opcode:int][body]; opcode сверяется с этой таблицей.
Имена говорят о смысле: MAP3D, SMENU(меню), CLOSE, PAINT, MDOWN/MUP/MCLICK
(мышь/тач), KEY0..9, LEFT/RIGHT/UP/DOWN, NOTIFICATE, PLAY_MUSIC/SOUND,
PROMOT/PROMUP (акции/промо), SOCIAL, GPS_COORDS и т.д.

Архитектура: клиент — тонкий терминал ("MiniBrowserActivity"), сервер гонит
поток UI-команд. Эти опкоды — командный словарь, который должен уметь наш
сервер.
"""

from __future__ import annotations


def opcode(name: str) -> int:
    """Точная реализация o.AbstractC0405c.b()."""
    total = 0
    mul = 1
    for i, ch in enumerate(name):
        if i >= 6:
            break
        if "a" <= ch <= "z":
            code = ord(ch) - ord("`")          # 1..26
        elif "A" <= ch <= "Z":
            code = ord(ch) - ord("@")          # 1..26 (регистронезависимо)
        elif "0" <= ch <= "9":
            code = ord(ch) - 21                 # 27..36
        elif ch == ":":
            code = ord("%")                     # 37
        elif ch == "\\":
            code = ord("&")                     # 38
        else:
            code = ord("'")                     # 39
        total += code * mul
        mul *= 40
    return total - 2147483648


# Имена опкодов в порядке регистрации в o.AbstractC0405c (для справки).
NAMES = [
    "_ALL", "_VIS", "_MOS", "_THIS", "FILES", "SYSTEM", "ANIM", "MEM", "MEMQ",
    "style", "SMS", "SMS", "XFILE", "MEM", "win", "app", "exit", "c0nver",
    "temp", "smiles", "tem1pl", "st1tmp", "ref", "get", "GCM", "GPS", "ROLL",
    "SOUND", "SOCIAL", "", "RUN", "INPTXT", "NWHOST", "SHG", "SHS", "CAMERA",
    "FILEX", "MAP3D", "SMENU", "ADDSML", "ADDWSM", "CSNDMS", "settmp", "setrdw",
    "ADDDIL", "CLOSE", "CLOSD", "HIST0", "HIST1", "HISMAX", "PAINT", "ALL",
    "MDOWN", "MUP", "MCLICK", "MON", "MMOVE", "MMOVI", "MSNRS", "PGSET",
    "PGNEXT", "resb2s", "add", "is", "del", "delAll", "def", "insStr", "max",
    "min", "text", "script", "name", "menuUp", "menuDn", "wPerc", "hPerc",
    "align", "LosFoc", "value0", "value1", "value2", "value", "addlin",
    "INFOIN", "RELOAD", "RELOD", "M2DOWN", "CHANG", "curReset", "GETFIL",
    "SETFIL", "SETDIR", "MPOS", "SL", "SR", "EXCEP", "ADDLIN", "CONSER",
    "KEY0", "KEY1", "KEY2", "KEY3", "KEY4", "KEY5", "KEY6", "KEY7", "KEY8",
    "KEY9", "KEYST", "KEYSH", "LEFT", "RIGHT", "UP", "DOWN", "GCMID", "GCMNID",
    "GCMUID", "GPS_COORDS", "ROLL_UP", "NOTIFICATE", "PLAY_MUSIC", "PLAY_SOUND",
    "PLAY_ALARM", "VOICE", "R_V", "P_V", "S_V", "D_V", "SE_V", "G_V", "PV_V",
    "SOC_PO", "SOCRES", "PROMOT", "PROMDI", "PROMPA", "PROMUP", "PROMEX",
    "PROMCL", "PROMMC",
]


# opcode(int) -> [имена] (возможны коллизии хеша, поэтому список)
def build_table():
    table = {}
    for nm in NAMES:
        table.setdefault(opcode(nm), []).append(nm)
    return table


OPCODE_TO_NAMES = build_table()
NAME_TO_OPCODE = {nm: opcode(nm) for nm in NAMES}


def name_for(op: int) -> str:
    names = OPCODE_TO_NAMES.get(op)
    return "|".join(dict.fromkeys(names)) if names else f"0x{op & 0xFFFFFFFF:08x}"


if __name__ == "__main__":
    print(f"{'OPCODE (int)':>13}  {'hex':>10}  NAME(S)")
    for nm in NAMES:
        op = opcode(nm)
        disp = nm if nm else "(empty)"
        print(f"{op:>13}  {op & 0xFFFFFFFF:#010x}  {disp}")
