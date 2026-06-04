/*
 * TLWK crawler — логинится на боевом сервере и СНИМАЕТ ответы всех функций
 * (только чтение) в папку ./tlwk_crawl, плюс сканирует карту. Чтобы не играть
 * месяц вручную. Запуск в Termux:
 *
 *   node crawl.js ЛОГИН ПАРОЛЬ            (карта в радиусе 8)
 *   node crawl.js ЛОГИН ПАРОЛЬ 15         (радиус карты 15)
 *
 * Безопасно: только GET-подобные запросы (info/list/map), с задержками.
 * НИЧЕГО не строит, не удаляет, не пишет. Это твой аккаунт, твои данные.
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const BASE = process.env.TLWK_BASE || 'https://tlwk.ru';
const LOGIN = process.argv[2] || process.env.TLWK_LOGIN;
const PASS = process.argv[3] || process.env.TLWK_PASS;
const MAP_R = parseInt(process.argv[4] || '8', 10);
const OUT = path.join(__dirname, 'tlwk_crawl');
const DELAY = 300; // мс между запросами — вежливо к серверу

if (!LOGIN || !PASS) { console.error('Использование: node crawl.js ЛОГИН ПАРОЛЬ [радиус_карты]'); process.exit(1); }
fs.mkdirSync(path.join(OUT, 'api'), { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
let TOKEN = null;
const seenUid = new Set();
const tiles = {};

async function api(ep, body) {
  const r = await fetch(BASE + ep, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json',
      ...(TOKEN ? { Authorization: 'Bearer ' + TOKEN } : {}) },
    body: JSON.stringify(body || {}),
  });
  const text = await r.text();
  let json = null; try { json = JSON.parse(text); } catch (e) {}
  return { status: r.status, text, json };
}
function saveRaw(name, obj) {
  fs.writeFileSync(path.join(OUT, 'api', name.replace(/[^\w.-]/g, '_') + '.json'),
    JSON.stringify(obj, null, 1));
}
async function grab(label, ep, body) {
  await sleep(DELAY);
  try {
    const res = await api(ep, body);
    saveRaw(label, { ep, body, status: res.status, data: res.json || res.text });
    // собрать uid и тайлы для дальнейшего сэмплинга
    const d = res.json && res.json.data;
    if (d) {
      const arr = [].concat(d.items || [], d.my || [], d.list || []);
      for (const it of arr) {
        if (it && it.uid) seenUid.add(it.uid);
        if (it && it.cid && it.x != null) tiles[it.cid] = it;
      }
    }
    console.log(`  ${label} <- ${res.status} (${res.text.length}b)`);
    return res.json && res.json.data;
  } catch (e) { console.log(`  ${label} ОШИБКА: ${e.message}`); return null; }
}

function jwtPayload(t) { try { return JSON.parse(Buffer.from(t.split('.')[1], 'base64')); } catch (e) { return {}; } }

(async () => {
  let uid, cid;
  if (process.env.TLWK_TOKEN) {
    TOKEN = process.env.TLWK_TOKEN;
    const p = jwtPayload(TOKEN); uid = p.sub; cid = p.cid;
    console.log(`[crawl] использую TLWK_TOKEN: uid=${uid} cid=${cid}`);
  } else {
    console.log(`[crawl] логин ${LOGIN}@${BASE} ...`);
    const lr = await api('/api/login', { login: LOGIN, password: PASS });
    if (!lr.json || !lr.json.data || !lr.json.data.token) {
      console.error('[crawl] логин не удался:', lr.text.slice(0, 200));
      console.error('Если на входе капча — войди в capture-клиент, возьми token из');
      console.error('Download/tlwk/tlwk_capture.txt (строка RESP .../login) и запусти:');
      console.error('  TLWK_TOKEN=<токен> node crawl.js');
      process.exit(1);
    }
    TOKEN = lr.json.data.token;
    uid = lr.json.data.userId; cid = lr.json.data.castleId;
    saveRaw('login', { status: lr.status, data: lr.json.data });
  }
  console.log(`[crawl] вошли: uid=${uid} cid=${cid}`);

  // --- основные функции (чтение) ---
  await grab('user', '/api/user', { info: 1, mailbox: 1, missions: 1, cid });
  await grab('castle_res', '/api/castle/res', { cid });
  const ci = await grab('castle_info', '/api/castle/info', { cid });
  await grab('user_instruction', '/api/user/instruction', {});
  await grab('notepad', '/api/notepad', {});
  await grab('friends_list', '/api/friends/list', { page: 1 });
  await grab('alliance_info', '/api/alliance/info', { aid: -1 });
  await grab('a_forum', '/api/a-forum', { page: 1, alliance_id: -1 });
  await grab('forum', '/api/forum', { page: 1 });
  await grab('army_list', '/api/army/list', { cid });
  await grab('general', '/api/general', {});
  await grab('hall_glory', '/api/hall-glory', { uid: -1 });
  await grab('chat_messages', '/api/chat/messages', {});
  await grab('shop_chest_info', '/api/shop/chest/info', {});
  await grab('reputation_list', '/api/reputation/list', { page: 1 });
  for (const t of ['players', 'castles', 'reputation', 'gift_point', 'alliance', 'empire', 'pairs', 'as_azarta', 'quests'])
    await grab('ratings_' + t, '/api/ratings', { type: t, page: 1 });

  // --- превью построек (без постройки!) для существующих зданий ---
  if (ci && Array.isArray(ci.buildings))
    for (const b of ci.buildings.slice(0, 30))
      await grab('prepare_pid' + (b.pid != null ? b.pid : b.building_id),
        '/api/building/prepare', { cid, pid: String(b.pid != null ? b.pid : b.building_id), action: 'update' });

  // --- карта: скан региона вокруг замка ---
  const me = (ci && ci.info) || {}; const cx = me.x_coord || 78, cy = me.y_coord || 77;
  console.log(`[crawl] скан карты вокруг (${cx},${cy}) радиус ${MAP_R} ...`);
  await grab('map_init', '/api/map', { init: 1, cid });
  let n = 0;
  for (let x = cx - MAP_R; x <= cx + MAP_R; x += 3)
    for (let y = cy - MAP_R; y <= cy + MAP_R; y += 3) {
      await grab('map_' + x + '_' + y, '/api/map', { x: String(x), y: String(y) });
      n++;
    }
  console.log(`[crawl] карта: ${n} запросов, тайлов собрано ${Object.keys(tiles).length}`);

  // --- сэмпл деталей тайлов и профилей (немного, не массово) ---
  const tlist = Object.keys(tiles).slice(0, 40);
  for (const tid of tlist) await grab('mapinfo_' + tid, '/api/map/info', { tid: String(tid), x: -1, y: -1 });
  const ulist = [...seenUid].slice(0, 30);
  for (const u of ulist) await grab('profile_' + u, '/api/user/profile', { uid: u });

  // сводный мир
  fs.writeFileSync(path.join(OUT, 'world.json'),
    JSON.stringify({ items: Object.values(tiles) }, null, 1));

  // упаковка
  try {
    execSync(`tar -czf "${path.join(__dirname, 'tlwk_crawl.tar.gz')}" -C "${__dirname}" tlwk_crawl`);
    console.log(`[crawl] ГОТОВО -> ${path.join(__dirname, 'tlwk_crawl.tar.gz')}`);
  } catch (e) {
    console.log(`[crawl] архив не создал (${e.message}); папка: ${OUT}`);
  }
  console.log('[crawl] загрузи tlwk_crawl.tar.gz (или папку tlwk_crawl) мне.');
})();
