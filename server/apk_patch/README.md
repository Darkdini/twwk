# Вшитый в клиент логгер трафика

Патч добавляет в APK невидимый логгер, который записывает **весь** обмен
клиента с сервером в файл на самом телефоне — прокси и ПК не нужны.

## Что делает патч

- Добавляет 3 класса (`smali/z/T.smali`, `TI.smali`, `TO.smali`):
  - `z.TI` — обёртка `InputStream` (логирует данные **от сервера**, метка `S`);
  - `z.TO` — обёртка `OutputStream` (логирует данные **к серверу**, метка `C`);
  - `z.T` — пишет записи в файл.
- Патчит `J/a.smali`: сразу после `socket.getInputStream()` /
  `getOutputStream()` оборачивает потоки в логгеры (единая точка — ловит
  рукопожатие и все кадры).

Доп. разрешения **не нужны**: дамп пишется в приватный каталог приложения.

## Куда пишется дамп

```
/sdcard/Android/data/start.browser.gameTWWK/files/twwk_dump.bin
```
Формат записи: `[1 байт dir 'S'/'C'][4 байта BE длина][данные]` (append).

## Установка на телефон

1. Удалить оригинальную игру (подпись отличается — поверх не встанет).
2. Установить пропатченный APK (разрешить установку из неизвестных источников).
3. Запустить, залогиниться, поиграть — всё пишется в `twwk_dump.bin`.

## Снять дамп с телефона

Приватный каталог приложения виден:
- через системный файловый менеджер: `Android/data/start.browser.gameTWWK/files/`;
- по USB (MTP) — тот же путь;
- через `adb` (если есть ПК позже):
  `adb pull /sdcard/Android/data/start.browser.gameTWWK/files/twwk_dump.bin`

## Разобрать и воспроизвести

```bash
cd server
python3 tools/import_dump.py twwk_dump.bin -o captures/from_device
python3 tools/decode_capture.py captures/from_device/events.jsonl
python3 server.py replay --session captures/from_device   # проиграть нашему серверу
```

## Пересборка патча (если будет новый APK)

```bash
cd server/apk_patch
./build.sh /path/to/original.apk
# -> signed/<name>-aligned-debugSigned.apk
```
