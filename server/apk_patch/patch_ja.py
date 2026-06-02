#!/usr/bin/env python3
"""
Идемпотентный патч smali/J/a.smali: оборачивает потоки сокета в логирующие
обёртки сразу после getInputStream()/getOutputStream().

Вставляет после каждого соответствующего `move-result-object v4`:
  invoke-static {v4}, Lz/T;->in|out(...)...
  move-result-object v4
"""

import re
import sys

path = sys.argv[1]
src = open(path, encoding="utf-8").read()

if "Lz/T;->in(" in src or "Lz/T;->out(" in src:
    print("    уже пропатчено, пропускаю")
    sys.exit(0)

patches = [
    (r"(getInputStream\(\)Ljava/io/InputStream;\s*\n(?:\s*\.line \d+\s*\n)*\s*move-result-object v4\n)",
     "\\1\n    invoke-static {v4}, Lz/T;->in(Ljava/io/InputStream;)Ljava/io/InputStream;\n\n    move-result-object v4\n"),
    (r"(getOutputStream\(\)Ljava/io/OutputStream;\s*\n(?:\s*\.line \d+\s*\n)*\s*move-result-object v4\n)",
     "\\1\n    invoke-static {v4}, Lz/T;->out(Ljava/io/OutputStream;)Ljava/io/OutputStream;\n\n    move-result-object v4\n"),
]

for pat, repl in patches:
    src, n = re.subn(pat, repl, src, count=1)
    if n != 1:
        print(f"    ОШИБКА: точка вставки не найдена для {pat[:40]}...")
        sys.exit(1)

open(path, "w", encoding="utf-8").write(src)
print("    J/a.smali пропатчен")
