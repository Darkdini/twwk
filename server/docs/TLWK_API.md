# TLWK — карта API (из захвата клиента)

Игра **TLWK** (`tlwk.ru`) — Vue 3 SPA, версия 1.0.44. Клиент — тонкий фронт,
сервер — HTTP **POST + JSON** на `/api/*`. Тот же жанр, что Mirtana.

Захвачено перехватчиком (`tlwk-capture.apk`): полный флоу регистрации +
застройки замка + карты + соц. функций. Ниже — запросы (тела). Ответы
добавляются capture-билдом v3 (`RESP`/`FRESP`).

## Идентификаторы
- `cid` — id замка (пример 78823)
- `uid` — id игрока (пример 5469)
- `pid` — позиция здания в замке; `bid` — тип здания
- расы: «Орки», … (как в Mirtana)

## Эндпоинты
### Аутентификация
```
POST /api/captcha            -> картинка/код капчи
POST /api/register  {login,password,race,nickname,email,captcha,fp,v}
POST /api/login     (предположительно; нужен захват входа)
POST /api/resetpass
```
`fp` — большой fingerprint устройства (screen, nav, canvasHash, webglRenderer…).

### Замок / ресурсы / здания
```
POST /api/castle/res   {cid}                         -> ресурсы замка
POST /api/castle/info  {cid}                          -> состояние замка/зданий
POST /api/user         {info,mailbox,missions,cid}    -> профиль/почта/миссии
POST /api/building/prepare {cid,pid,action:"create|update"}  -> предпросмотр/стоимость
POST /api/building/create  {cid,pid,bid,gem}          -> построить здание bid на позиции pid
POST /api/building/upgrade {cid,pid,gem}              -> улучшить
POST /api/army/list    {cid}
POST /api/general      /  /api/general/assign {name}
```

### Карта / мир
```
POST /api/map      {init,cid} | {x,y}     -> тайлы карты
POST /api/map/info {tid,x,y}              -> инфо тайла/объекта
```

### Социальное
```
POST /api/user/profile     {uid}
POST /api/messages/create  {receiver,message}
POST /api/friends/list     {page}
POST /api/alliance/info    {aid}    /  /api/a-forum {page,alliance_id}
POST /api/reputation/list  {page,nickname}
POST /api/hall-glory       {uid}
POST /api/ratings          {type,page}   type: players|castles|reputation|
                                          gift_point|alliance|empire|pairs|
                                          as_azarta|quests
POST /api/notepad
```

## Наблюдения для сервера
- Чистый REST/JSON — реализуется на любом бэкенде (Node/Mirtana — естественно).
- Игровой цикл: `building/prepare` (показать стоимость) → `building/create`/
  `upgrade` → опрос `castle/res` + `castle/info` + `user`.
- Сессия — по cookie (логин ставит cookie, дальше POST'ы без явного токена).
- Статика: `/assets/app/*.js|*.css` (Vue-бандл), `/assets/images/...` (графика).

## Что ещё нужно
1. Ответы сервера на каждый эндпоинт (capture v3 пишет `RESP`/`FRESP`).
2. Захват **входа** (login) и **капчи**.
3. Графика — capture v3 пишет в `Download/tlwk/assets/`.
