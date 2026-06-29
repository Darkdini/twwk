# RCE на реальном коде клиента TWWK (Data.fromByteArray)

`ClientData.java` — точная копия логики `J0/g.java` (`Data#fromByteArray`):
`readInt` → цикл `readUTF` + `readObject`. Демонстрирует, что этот паттерн
уязвим: блоб всего 40 байт с «злым» объектом → выполнение кода.

## Запуск
```bash
javac *.java && java MakeBlob
```
Результат (проверено):
- `ClientData.fromByteArray` → `id -> uid=0(root)...`, создан `PWNED_CLIENT.txt`.
- `SafeClientData` (ObjectInputFilter) → `REJECTED`, файл не создан.

## Область риска
- В клиенте эта функция читает блоб из ЛОКАЛЬНОЙ БД WorkManager (`Cursor.getBlob`),
  не из сети → сетевого RCE на клиенте через неё НЕТ.
- Тот же паттерн на СЕРВЕРЕ над вводом клиента = удалённый RCE. Проверить первым.

## Защита
1. Не десериализуй ввод клиента Java-сериализацией; читай поля протокола вручную.
2. Иначе — `ObjectInputFilter` (Java 9+) / белый список `resolveClass`.
3. Лимит размера не спасает (payload = 40 байт). Решает фильтр классов.
4. Сервер — не от root, в песочнице.
