#!/usr/bin/env bash
# Наполняет public/ из захвата: ассеты (assets.zip) + index.html (из tlwk_capture.txt).
# Использование:  ./setup.sh /path/to/assets.zip /path/to/tlwk_capture.txt
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
ZIP="${1:?укажи assets.zip}"
CAP="${2:?укажи tlwk_capture.txt}"
mkdir -p "$HERE/public/assets"

echo "[*] Распаковка ассетов..."
TMP="$(mktemp -d)"
unzip -q "$ZIP" -d "$TMP"
# ассеты лежат плоско в .../assets/ — копируем по basename
find "$TMP" -type f -exec cp {} "$HERE/public/assets/" \;
rm -rf "$TMP"
echo "    ассетов: $(ls "$HERE/public/assets" | wc -l)"

echo "[*] Извлечение index.html из захвата..."
python3 - "$CAP" "$HERE/public/index.html" <<'PY'
import sys
lines=open(sys.argv[1],encoding='utf-8',errors='replace').read().split('\n')
html=None
for i,l in enumerate(lines):
    if l.startswith('URL\thttps://tlwk.ru/app/game'):
        for j in range(i+1,min(i+4,len(lines))):
            if lines[j].startswith('HTML\t'): html=lines[j][5:]; break
        break
if html: open(sys.argv[2],'w',encoding='utf-8').write(html); print('    index.html ок,',len(html),'байт')
else: print('    [!] HTML /app/game не найден — положи index.html вручную')
PY
echo "[+] Готово. Запуск:  node server.js   (открой http://localhost:7777)"
