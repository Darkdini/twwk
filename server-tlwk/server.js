/*
 * TLWK server — реализация API игры по захваченному контракту (tlwk.ru).
 * Чистый Node (без зависимостей). Формы ответов взяты из реального захвата
 * (server/docs/tlwk_api_capture.txt). Состояние — в state.json.
 *
 * Запуск:  node server.js   (PORT=7777 по умолчанию)
 * Эндпоинты: POST /api/*  (JSON), статика фронта из ./public
 */
'use strict';
const http = require('http');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');
const { makeCaptcha } = require('./captcha');

// недавно выданные коды капчи (TTL 10 мин)
let CAPTCHAS = [];
function issueCaptcha() {
  const { code, img } = makeCaptcha(4);
  CAPTCHAS.push({ code, t: Date.now() });
  if (CAPTCHAS.length > 50) CAPTCHAS.shift();
  return img;
}
function captchaOk(input) {
  if (!input) return false;
  const now = Date.now();
  CAPTCHAS = CAPTCHAS.filter((c) => now - c.t < 600000);
  return CAPTCHAS.some((c) => c.code === String(input).trim());
}

const PORT = process.env.PORT || 7777;
const SECRET = process.env.JWT_SECRET || 'tlwk-dev-secret-change-me';
const STATE_FILE = path.join(__dirname, 'state.json');
const PUBLIC = path.join(__dirname, 'public');

// ---------- состояние ----------
let DB = { nextUid: 5000, nextCid: 78000, users: {}, castles: {} };
try { DB = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')); } catch (e) {}
let saveTimer = null;
function save() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    try { fs.writeFileSync(STATE_FILE, JSON.stringify(DB, null, 1)); } catch (e) {}
  }, 300);
}

// ---------- JWT (HS256) ----------
const b64u = (b) => Buffer.from(b).toString('base64').replace(/=+$/,'').replace(/\+/g,'-').replace(/\//g,'_');
function jwtSign(payload) {
  const h = b64u(JSON.stringify({ typ: 'JWT', alg: 'HS256' }));
  const p = b64u(JSON.stringify(payload));
  const s = b64u(crypto.createHmac('sha256', SECRET).update(h + '.' + p).digest());
  return `${h}.${p}.${s}`;
}
function jwtVerify(token) {
  try {
    const [h, p, s] = token.split('.');
    const exp = b64u(crypto.createHmac('sha256', SECRET).update(h + '.' + p).digest());
    if (s !== exp) return null;
    return JSON.parse(Buffer.from(p, 'base64'));
  } catch (e) { return null; }
}

// ---------- модель ----------
const STARTING_RES = { gold: 1500, wood: 1500, stone: 1500, grain: 1500, iron: 1500, people: 200, energy: 0 };

function makeCastle(cid, uid, race) {
  DB.castles[cid] = {
    cid, uid, type: 0, castle_name: 'Мой замок', rating: 1,
    ...STARTING_RES,
    x_coord: 70 + (cid % 30), y_coord: 70 + (uid % 30),
    capacityWarehouse: 5000, capacityEnergy: 200, capacityHouse: 200, capacityMerchant: 0,
    pearl: 0, busy_dealers: 0, portalBonus: 0,
    // ратуша по умолчанию (building_id 1)
    buildings: [{ building_id: 1, level: 1, in_progress: 0, time_left: 0,
      build_start_time: '0000-00-00 00:00:00', time_build: 0,
      image_path: '/assets/images/game/wizard/buildings/cityhall_0.png', location: 'castle' }],
  };
  return DB.castles[cid];
}
function newCastle(uid, race) { return makeCastle(++DB.nextCid, uid, race).cid; }

// Замок по токену; если состояние сброшено — пересоздаём (устойчивость к rm state.json)
function ensureCastle(ctx) {
  if (!ctx || !ctx.cid) return null;
  return DB.castles[ctx.cid] || makeCastle(ctx.cid, ctx.uid || (ctx.cid % 9000), ctx.race);
}
function ensureUser(ctx) {
  if (!ctx) return null;
  let u = userById(ctx.uid);
  if (!u) {
    u = { uid: ctx.uid, login: 'user' + ctx.uid, password: '', nickname: 'Player' + ctx.uid,
      race: ctx.race || 'Орки', email: '', cid: ctx.cid, reputation: 10, rid: 1 };
    DB.users['user' + ctx.uid] = u; save();
  }
  return u;
}

const MAILBOX = { messages: 0, reports: 0, news: 0, presents: 0, dialogs: 0,
  obychenie: 1, rassilka: 0, medal: 0, chest: 8 };

// ---------- генерация мира ----------
const RACES = ['Орки', 'Эльфы', 'Люди', 'Гномы'];
const CN = ['Папасная', 'Легион', 'Драккар', 'Северный форт', 'Цитадель', 'Оплот',
  'Рубеж', 'Застава', 'Гнездо', 'Вольный город', 'Каменный город', 'Стальград'];
const OA = ['Каменный оазис', 'Смешанный оазис', 'Лесной оазис', 'Железный оазис', 'Золотая жила'];
const NK = ['Wagner', 'Legenda', 'Varg', 'Thorin', 'Eldar', 'Khan', 'Ragnar', 'Bjorn', 'Mira', 'Orion'];
const pick = (a) => a[(Math.random() * a.length) | 0];

function generateWorld() {
  if (DB.world && DB.world.length) return;
  // 1) реальный мир из записи (world.json), как в логах
  try {
    const w = JSON.parse(fs.readFileSync(path.join(__dirname, 'world.json'), 'utf8'));
    const items = (w.items || []).filter((o) => o.t !== 0); // убрать чужой свой замок
    if (items.length) {
      DB.world = items;
      DB.worldInfo = w.info || {};
      save();
      console.log(`[world] загружен из записи: ${items.length} объектов`);
      return;
    }
  } catch (e) {}
  // 2) фолбэк — случайная генерация
  DB.world = [];
  let cid = 100000;
  for (let x = 48; x <= 96; x++) for (let y = 48; y <= 96; y++) {
    if (Math.random() > 0.10) continue;
    cid += 1 + ((Math.random() * 7) | 0);
    if (Math.random() < 0.5) {
      DB.world.push({ r: 200 + ((Math.random() * 3000) | 0), cid, uid: cid % 9000, t: 3,
        cn: pick(CN), x, y, in_process: 0, def: null, batk: 0,
        un: pick(NK) + ((Math.random() * 99) | 0), ur: pick(RACES), pr: 0, al: '', nk: 0, vk: null });
    } else {
      DB.world.push({ r: -900, cid, uid: cid % 9000, t: pick([12, 15, 21]),
        cn: pick(OA), x, y, in_process: 0, def: null, batk: null,
        un: 'Оазис', ur: pick(RACES), pr: 0, al: '', nk: 0, vk: null });
    }
  }
  save();
}

function resourcesOf(c) {
  return {
    user_id: c.uid, type: c.type, castle_name: c.castle_name, rating: c.rating,
    gold: c.gold, wood: c.wood, stone: c.stone, grain: c.grain, iron: c.iron,
    people: c.people, energy: c.energy, x_coord: c.x_coord, y_coord: c.y_coord,
    last_rec_updated: '0000-00-00 00:00:00', in_process: 0, batk: null,
    pearl: c.pearl, busy_dealers: c.busy_dealers, capacityWarehouse: c.capacityWarehouse,
    capacityEnergy: c.capacityEnergy, capacityHouse: c.capacityHouse,
    capacityMerchant: c.capacityMerchant, portalBonus: c.portalBonus,
  };
}

// ---------- helpers ----------
const ok = (data, extra) => ({ success: true, message: '', data, ...(extra || {}) });
const err = (message) => ({ success: false, message, data: null });

function authCastle(req) {
  // токен в заголовке Authorization: Bearer, либо в cookie 'token'
  let tok = null;
  const a = req.headers['authorization'];
  if (a && a.startsWith('Bearer ')) tok = a.slice(7);
  if (!tok && req.headers.cookie) {
    const m = /(?:^|;\s*)token=([^;]+)/.exec(req.headers.cookie);
    if (m) tok = decodeURIComponent(m[1]);
  }
  const p = tok && jwtVerify(tok);
  if (!p) return null;
  return { uid: p.sub, cid: p.cid, race: p.race };
}

// ---------- роутер API ----------
const routes = {
  'POST /api/captcha': (b) => ok({ img: issueCaptcha() }),
  'POST /api/register': (b) => {
    const login = (b.login || '').trim();
    if (!captchaOk(b.captcha)) return err('Неверный код с картинки');
    if (!login || DB.users[login.toLowerCase()]) return err('Логин занят');
    const uid = ++DB.nextUid;
    const cid = newCastle(uid, b.race);
    DB.users[login.toLowerCase()] = {
      uid, login, password: b.password || '', nickname: b.nickname || login,
      race: b.race || 'Орки', email: b.email || '', cid, reputation: 10, rid: 1,
    };
    save();
    const token = jwtSign({ iat: (Date.now() / 1000) | 0, exp: ((Date.now() / 1000) | 0) + 43200,
      cid, sub: uid, rid: 1, race: b.race || 'Орки', lsid: crypto.randomBytes(16).toString('hex') });
    return ok({ token, userId: uid, castleId: cid });
  },
  'POST /api/login': (b) => {
    const u = DB.users[(b.login || '').toLowerCase()];
    if (!u || u.password !== (b.password || '')) return err('Неверный логин или пароль');
    const token = jwtSign({ iat: (Date.now() / 1000) | 0, exp: ((Date.now() / 1000) | 0) + 43200,
      cid: u.cid, sub: u.uid, rid: u.rid, race: u.race, lsid: crypto.randomBytes(16).toString('hex') });
    return ok({ token, userId: u.uid, castleId: u.cid });
  },
  'POST /api/user': (b, ctx) => {
    if (!ctx) return err('auth');
    const u = ensureUser(ctx);
    const c = ensureCastle(ctx);
    return ok({
      userId: ctx.uid, capital: ctx.cid,
      gold: c ? c.gold : 0, wood: c ? c.wood : 0, stone: c ? c.stone : 0,
      grain: c ? c.grain : 0, iron: c ? c.iron : 0, people: c ? c.people : 0,
      info: { nickname: u.nickname, reputation: u.reputation, pearl: 0,
        rasa: u.race, alliance_id: -1, rid: u.rid, alliance: null,
        empire_id: null, empire: null, race: 'ork', showLvl: false, showCastleName: false,
        premium: { premium_id: 0, premium_name: '', end_date: '', duration: 0 },
        permissions: -1, mis_limit: 10, mis_busy: 0, marriage: { free: true } },
      missions: [], mailbox: MAILBOX,
    });
  },
  'POST /api/castle/res': (b, ctx) => {
    const c = ensureCastle(ctx);
    if (!c) return err('Нет замка');
    return ok({ resources: resourcesOf(c) });
  },
  'POST /api/castle/info': (b, ctx) => {
    const c = ensureCastle(ctx);
    if (!c) return err('Нет замка');
    return ok({ buildings: c.buildings, info: resourcesOf(c) });
  },
  'POST /api/building/prepare': (b, ctx) => {
    const c = ensureCastle(ctx);
    if (!c) return err('Нет замка');
    const bld = c.buildings.find((x) => String(x.building_id) === String(b.pid));
    const lvl = bld ? bld.level : 0;
    return ok({ current: c.cid, item: { building_id: b.pid, level: lvl, next: lvl + 1,
      is_completed: true, canTrain: false, canResurrect: false, can_build: true,
      messages: [], isError: false, canUpgrade: true }, action: b.action || 'update' },
      { mailbox: MAILBOX });
  },
  'POST /api/building/create': (b, ctx) => {
    const c = ensureCastle(ctx);
    if (!c) return err('Нет замка');
    if (!c.buildings.find((x) => String(x.building_id) === String(b.bid))) {
      c.buildings.push({ building_id: Number(b.bid), level: 1, in_progress: 0, time_left: 0,
        build_start_time: '0000-00-00 00:00:00', time_build: 0,
        image_path: `/assets/images/game/wizard/buildings/b${b.bid}_0.png`, location: 'castle',
        pid: b.pid });
      save();
    }
    return ok({ current: c.cid }, { mailbox: MAILBOX });
  },
  'POST /api/building/upgrade': (b, ctx) => {
    const c = ensureCastle(ctx);
    if (!c) return err('Нет замка');
    const bld = c.buildings.find((x) => String(x.building_id) === String(b.pid));
    if (bld) { bld.level++; save(); }
    return ok({ current: c.cid }, { mailbox: MAILBOX });
  },
  'POST /api/map': (b, ctx) => {
    generateWorld();
    const mine = Object.values(DB.castles).filter((c) => ctx && c.uid === ctx.uid);
    const my = mine.map((c) => ({ r: c.rating, cid: c.cid, uid: c.uid, t: 0,
      cn: c.castle_name, x: c.x_coord, y: c.y_coord }));
    let items = DB.world || [];
    // если клиент просит регион {x,y} (не init) — отдаём ближние
    if (b && b.x != null && b.y != null && !b.init) {
      const cx = +b.x, cy = +b.y, R = 20;
      items = items.filter((o) => Math.abs(o.x - cx) <= R && Math.abs(o.y - cy) <= R);
    }
    return ok({ my, items });
  },
  'POST /api/map/info': (b, ctx) => {
    generateWorld();
    const tid = b && (b.tid || b.cid);
    // реальные детали из записи
    if (DB.worldInfo && DB.worldInfo[tid]) return ok({ item: DB.worldInfo[tid], trh_enable: true }, { mailbox: MAILBOX });
    const o = (DB.world || []).find((w) => String(w.cid) === String(tid));
    if (!o) return ok({ item: null }, { mailbox: MAILBOX });
    return ok({ item: { castle_type: o.t, user_id: o.uid, castle_name: o.cn,
      castle_rating: o.r < 0 ? 0 : o.r, x_coord: o.x, y_coord: o.y, castle_id: o.cid,
      def: o.def, batk: o.batk, alliance_id: -1, in_process: 0, rasa: o.ur, type: 0,
      nickname: o.un, aliance: o.al || '', empire_id: null, empire: null, prem: 0,
      is_owner: false, missions: [] }, trh_enable: true }, { mailbox: MAILBOX });
  },
  'POST /api/user/profile': (b) => ok({ profile: null }),
  'POST /api/user/instruction': (b) => ok({ steps: [] }),
  'POST /api/friends/list': (b) => ok({ list: [], page: 1 }),
  'POST /api/friends/add': (b) => ok({}),
  'POST /api/messages/create': (b) => ok({}),
  'POST /api/notepad': (b) => ok({ text: '' }),
  'POST /api/hall-glory': (b) => ok({ list: [] }),
  'POST /api/ratings': (b) => ok({ list: [], page: 1, type: b && b.type }),
  'POST /api/alliance/info': (b) => ok({ alliance: null }),
  'POST /api/a-forum': (b) => ok({ topics: [], page: 1 }),
  'POST /api/army/list': (b) => ok({ army: [] }),
  'POST /api/general': (b) => ok({ generals: [] }),
  'POST /api/general/assign': (b) => ok({}),
  'POST /api/reputation/list': (b) => ok({ list: [], page: 1 }),
  'POST /api/forum': (b) => ok({ topics: [], page: 1 }),
  'POST /api/chat/messages': (b) => ok({ messages: [] }),
  'POST /api/shop/chest/info': (b) => ok({ chests: [], list: [] }),
  'POST /api/debug/log': (b) => ok({}),
};

function userById(uid) {
  for (const k in DB.users) if (DB.users[k].uid === uid) return DB.users[k];
  return null;
}

// ---------- статика ----------
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.ico': 'image/x-icon', '.svg': 'image/svg+xml',
  '.json': 'application/json' };

// захваченные ассеты лежат «плоско» (по basename) -> ищем по имени файла
function findAsset(urlPath) {
  const base = path.basename(urlPath.split('?')[0]);
  const direct = path.join(PUBLIC, urlPath.split('?')[0]);
  if (fs.existsSync(direct) && fs.statSync(direct).isFile()) return direct;
  const flat = path.join(PUBLIC, 'assets', base);
  if (fs.existsSync(flat)) return flat;
  return null;
}

function serveStatic(req, res) {
  let p = req.url.split('?')[0];
  if (p === '/' || p === '/app/game' || p === '/app' || p === '/game') p = '/index.html';
  const file = findAsset(p);
  if (file) {
    res.writeHead(200, {
      'Content-Type': MIME[path.extname(file)] || 'application/octet-stream',
      'Access-Control-Allow-Origin': '*',
    });
    fs.createReadStream(file).pipe(res);
    return;
  }
  // SPA-фоллбэк: маршруты без расширения (/app/castle, /app/register…) -> index.html
  const hasExt = /\.[a-z0-9]{2,5}$/i.test(p);
  const idx = path.join(PUBLIC, 'index.html');
  if (!hasExt && fs.existsSync(idx)) {
    res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    fs.createReadStream(idx).pipe(res);
    return;
  }
  res.writeHead(404); res.end('not found');
}

// ---------- сервер ----------
const server = http.createServer((req, res) => {
  const url = req.url.split('?')[0];
  if (req.method === 'POST' && url.startsWith('/api/')) {
    let body = '';
    req.on('data', (d) => { body += d; if (body.length > 1e6) req.destroy(); });
    req.on('end', () => {
      let b = {};
      try { b = body ? JSON.parse(body) : {}; } catch (e) {}
      const handler = routes['POST ' + url];
      res.setHeader('Content-Type', 'application/json; charset=utf-8');
      res.setHeader('Access-Control-Allow-Origin', '*');
      if (!handler) { res.end(JSON.stringify(ok({}))); console.log('[api] ???', url); return; }
      const ctx = authCastle(req);
      let out;
      try { out = handler(b, ctx); } catch (e) { out = err(String(e)); }
      // login/register -> ставим cookie с токеном
      if (out && out.success && out.data && out.data.token) {
        res.setHeader('Set-Cookie', `token=${out.data.token}; Path=/; Max-Age=43200`);
      }
      console.log('[api]', url, JSON.stringify(b).slice(0, 80));
      res.end(JSON.stringify(out));
    });
    return;
  }
  serveStatic(req, res);
});

server.listen(PORT, () => {
  console.log(`TLWK server on http://0.0.0.0:${PORT}`);
  console.log(`Статика: ${PUBLIC} ; состояние: ${STATE_FILE}`);
});
