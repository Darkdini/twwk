#!/usr/bin/env python3
"""
Идемпотентный патч smali/i/i.smali: после разбора сообщения в i.i.c()
вызывает z.T.msg(srcId, opcode, body) -> текстовый лог twwk_msg.txt.

Поля: Li/i;->c:I (srcId), Li/i;->d:I (opcode), Li/i;->e:Ljava/lang/Object; (body).
"""

import re
import sys

path = sys.argv[1]
src = open(path, encoding="utf-8").read()

if "Lz/T;->msg(" in src:
    print("    i/i.smali уже пропатчен, пропускаю")
    sys.exit(0)

# В методе c() поднимаем .locals 1 -> 3
src, n1 = re.subn(
    r"(\.method public c\(Ly/b;\)V\s*\n\s*\.locals )1",
    r"\g<1>3", src, count=1)

# Вставка хука перед завершающим return-void метода c()
hook = (
    "    iput-object p1, p0, Li/i;->e:Ljava/lang/Object;\n\n"
    "    iget v0, p0, Li/i;->c:I\n\n"
    "    iget v1, p0, Li/i;->d:I\n\n"
    "    iget-object v2, p0, Li/i;->e:Ljava/lang/Object;\n\n"
    "    invoke-static {v0, v1, v2}, Lz/T;->msg(IILjava/lang/Object;)V\n"
)
src, n2 = re.subn(
    r"    iput-object p1, p0, Li/i;->e:Ljava/lang/Object;\n",
    hook, src, count=1)

if n1 != 1 or n2 != 1:
    print(f"    ОШИБКА патча i/i.smali (locals={n1}, hook={n2})")
    sys.exit(1)

open(path, "w", encoding="utf-8").write(src)
print("    i/i.smali пропатчен (хук z.T.msg)")
