#!/usr/bin/env bash
#
# Сборка пропатченного APK с вшитым логгером трафика.
#
# Требуется: java (17+). apktool.jar и uber-apk-signer.jar скачиваются ниже,
# либо положите их рядом и пропустите загрузку.
#
# Использование:
#   ./build.sh /path/to/original.apk
#
# Результат: signed/<name>-aligned-debugSigned.apk
#
set -euo pipefail

APK="${1:?укажите путь к оригинальному APK}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$HERE/work"
TOOLS="$HERE/tools"

APKTOOL_URL="https://github.com/iBotPeaches/Apktool/releases/download/v2.10.0/apktool_2.10.0.jar"
SIGNER_URL="https://github.com/patrickfav/uber-apk-signer/releases/download/v1.3.0/uber-apk-signer-1.3.0.jar"

mkdir -p "$TOOLS"
[ -f "$TOOLS/apktool.jar" ] || curl -sSL -o "$TOOLS/apktool.jar" "$APKTOOL_URL"
[ -f "$TOOLS/uber-apk-signer.jar" ] || curl -sSL -o "$TOOLS/uber-apk-signer.jar" "$SIGNER_URL"

rm -rf "$WORK"
echo "[*] Распаковка APK..."
java -jar "$TOOLS/apktool.jar" d -f -o "$WORK" "$APK"

echo "[*] Копирование smali-логгера (z/T, z/TI, z/TO)..."
mkdir -p "$WORK/smali/z"
cp "$HERE/smali/z/"*.smali "$WORK/smali/z/"

echo "[*] Патч J/a.smali (обёртка потоков сокета)..."
python3 "$HERE/patch_ja.py" "$WORK/smali/J/a.smali"

echo "[*] Сборка APK..."
OUT_UNSIGNED="$HERE/patched-unsigned.apk"
java -jar "$TOOLS/apktool.jar" b "$WORK" -o "$OUT_UNSIGNED"

echo "[*] Подпись..."
java -jar "$TOOLS/uber-apk-signer.jar" -a "$OUT_UNSIGNED" --allowResign -o "$HERE/signed"

echo "[+] Готово: $HERE/signed/"
ls -la "$HERE/signed/"
