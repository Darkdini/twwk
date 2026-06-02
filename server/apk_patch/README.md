# Вшитый в клиент логгер трафика

Патч добавляет в APK невидимый логгер, который записывает **весь** обмен
клиента с сервером в файл на самом телефоне — прокси и ПК не нужны.

## Что делает патч

Два уровня логирования:

**1. Сырой трафик** (классы `z.TI`, `z.TO`, патч `J/a.smali`):
- `z.TI` — обёртка `InputStream` (данные **от сервера**, метка `S`);
- `z.TO` — обёртка `OutputStream` (данные **к серверу**, метка `C`);
- оборачиваются сразу после `socket.getInputStream()` / `getOutputStream()`
  (единая точка — ловит рукопожатие и все кадры).
- Файл: `twwk_dump.bin`, запись `[1 байт dir 'S'/'C'][4 байта BE длина][данные]`.

**2. Семантика сообщений** (метод `z.T.msg`, патч `i/i.smali`):
- после разбора каждого сообщения в `i.i.c()` пишет строку
  `s=<srcId> op=<opcode> body=<класс тела>`;
- Файл: `twwk_msg.txt`. Сопоставляется с именами опкодов через
  `server/twwk/opcodes.py` / `server/docs/OPCODES.md`.

Доп. разрешения **не нужны**: всё пишется в приватный каталог приложения.

## Куда пишется

```
/sdcard/Android/data/start.browser.gameTWWK/files/twwk_dump.bin   # сырой трафик
/sdcard/Android/data/start.browser.gameTWWK/files/twwk_msg.txt    # разобранные сообщения
```

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
