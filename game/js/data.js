// ═══════════════════════════════════════════════════════════════════
//  ТРЕТИЙ МИР — ВОЙНА КОРОЛЕЙ  ·  игровые данные
//  Браузерный клон стратегии. Все определения рас, ресурсов,
//  зданий, юнитов и технологий собраны здесь.
// ═══════════════════════════════════════════════════════════════════

// ─── РАСЫ ───────────────────────────────────────────────────────────
const RACES = {
  human: { name:'Люди',  emoji:'🛡️', bonus:'Железо +20%, защита замка +10%',
           color:'#c8a060', prodBonus:{iron:0.20}, castleDef:0.10 },
  elf:   { name:'Эльфы', emoji:'🏹', bonus:'Дерево +20%, скорость армии +15%',
           color:'#5fbf5f', prodBonus:{wood:0.20}, marchSpeed:0.15, fieldAtk:0.10 },
  dwarf: { name:'Гномы', emoji:'⛏️', bonus:'Камень +20%, защита войск +12%',
           color:'#9a9ac0', prodBonus:{stone:0.20}, def:0.12 },
  orc:   { name:'Орки',  emoji:'⚔️', bonus:'Атака ×1.5, но защита −20%',
           color:'#6fae5f', atkMult:1.5, defPenalty:0.20 },
};

// ─── РЕСУРСЫ ─────────────────────────────────────────────────────────
const RES       = ['gold','wood','stone','food','iron','people'];
const RES_LABEL = { gold:'Золото', wood:'Дерево', stone:'Камень', food:'Еда', iron:'Железо', people:'Люди' };
const RES_ICON  = { gold:'🪙', wood:'🪵', stone:'🪨', food:'🌾', iron:'⚙️', people:'👥' };

// ─── ЗДАНИЯ ──────────────────────────────────────────────────────────
// cost   — базовая стоимость 1-го уровня
// time   — базовое время постройки 1-го уровня (сек)
// max    — максимальный уровень
// prod   — { ресурс: базовое производство/час за уровень }
// req    — { зданиеId: уровень } требования для постройки
// Стоимость и время растут как base * 1.6^(level-1).
const BUILDINGS = {
  townhall: { name:'Ратуша', icon:'🏰', max:15, time:90, unique:true,
              cost:{wood:150,stone:150,iron:40},
              desc:'Сердце города. Поднимает лимит уровней других зданий и хранилища.' },
  storage:  { name:'Склад', icon:'📦', max:20, time:50,
              cost:{wood:80,stone:100},
              desc:'Увеличивает максимальный запас ресурсов.' },
  house:    { name:'Жилой дом', icon:'🏠', max:20, time:45,
              cost:{wood:60,stone:40},
              prod:{people:6}, desc:'Прирост населения. Население нужно для обучения войск.' },
  farm:     { name:'Ферма', icon:'🌾', max:25, time:40,
              cost:{wood:50,stone:30},
              prod:{food:90}, desc:'Производит еду. Еда нужна армии (содержание).' },
  sawmill:  { name:'Лесопилка', icon:'🪓', max:25, time:45,
              cost:{wood:40,stone:60},
              prod:{wood:70}, desc:'Добывает дерево.' },
  quarry:   { name:'Каменоломня', icon:'⛰️', max:25, time:45,
              cost:{wood:60,stone:40},
              prod:{stone:65}, desc:'Добывает камень.' },
  mine:     { name:'Рудник', icon:'⚒️', max:25, time:55,
              cost:{wood:80,stone:80},
              prod:{iron:55}, desc:'Добывает железо.' },
  market:   { name:'Рынок', icon:'🏪', max:15, time:70, unique:true, req:{townhall:2},
              cost:{wood:120,stone:80},
              prod:{gold:60}, desc:'Торговля приносит золото и позволяет обменивать ресурсы.' },
  barracks: { name:'Казарма', icon:'⚔️', max:20, time:80, unique:true, req:{townhall:2},
              cost:{wood:100,stone:120,iron:50},
              desc:'Обучение пехоты и стрелков. Уровень ускоряет обучение.' },
  stables:  { name:'Конюшня', icon:'🐎', max:20, time:110, unique:true, req:{townhall:4},
              cost:{wood:150,stone:90,iron:70},
              desc:'Обучение конницы — мощных и быстрых войск.' },
  workshop: { name:'Мастерская', icon:'🔧', max:15, time:130, unique:true, req:{townhall:5},
              cost:{wood:120,stone:180,iron:90},
              desc:'Производство осадных орудий для штурма стен.' },
  smithy:   { name:'Кузница', icon:'🔨', max:20, time:90, unique:true, req:{townhall:3},
              cost:{wood:80,stone:120,iron:80},
              desc:'Открывает военные технологии и усиливает оружие.' },
  wall:     { name:'Стена', icon:'🧱', max:20, time:100, unique:true, req:{townhall:2},
              cost:{wood:80,stone:200,iron:40},
              desc:'Каждый уровень повышает защиту города на 6%.' },
  trap:     { name:'Капканщик', icon:'🪤', max:10, time:120, unique:true, req:{townhall:3},
              cost:{wood:120,stone:80,iron:90},
              desc:'Ловушки перехватывают часть атакующих до начала боя.' },
};

// ─── ЮНИТЫ ───────────────────────────────────────────────────────────
// atk/def/hp — боевые характеристики
// speed      — клеток мира в минуту (выше = быстрее доходит)
// carry      — сколько ресурсов уносит из добычи
// upkeep     — потребление еды/час
// people     — стоимость в населении
const UNITS = {
  // Пехота / стрелки — Казарма
  spearman: { name:'Копейщик', icon:'🗡️', building:'barracks', kind:'infantry',
              atk:18, def:42, hp:40, speed:6, carry:50, upkeep:1, people:1,
              cost:{wood:60,iron:30,food:20}, time:30, req:{barracks:1} },
  swordsman:{ name:'Мечник', icon:'⚔️', building:'barracks', kind:'infantry',
              atk:36, def:30, hp:45, speed:6, carry:55, upkeep:1, people:1,
              cost:{wood:40,iron:70,food:25}, time:40, req:{barracks:2} },
  archer:   { name:'Лучник', icon:'🏹', building:'barracks', kind:'ranged',
              atk:50, def:14, hp:28, speed:7, carry:40, upkeep:1, people:1,
              cost:{wood:80,iron:25,food:20}, time:45, req:{barracks:3} },
  scout:    { name:'Разведчик', icon:'👁️', building:'barracks', kind:'scout',
              atk:8, def:8, hp:18, speed:14, carry:0, upkeep:1, people:1,
              cost:{wood:30,iron:15,food:15}, time:20, req:{barracks:1} },
  // Конница — Конюшня
  knight:   { name:'Рыцарь', icon:'🐎', building:'stables', kind:'cavalry',
              atk:78, def:60, hp:90, speed:11, carry:110, upkeep:3, people:1,
              cost:{wood:60,iron:140,food:80}, time:90, req:{stables:1} },
  champion: { name:'Чемпион', icon:'🏇', building:'stables', kind:'cavalry',
              atk:96, def:78, hp:110, speed:10, carry:90, upkeep:4, people:1,
              cost:{wood:90,iron:180,food:110}, time:130, req:{stables:4} },
  // Осада — Мастерская
  catapult: { name:'Катапульта', icon:'🪨', building:'workshop', kind:'siege',
              atk:160, def:8, hp:55, speed:3, carry:20, upkeep:6, people:2,
              cost:{wood:300,iron:160,food:40}, time:180, req:{workshop:1} },
  ram:      { name:'Таран', icon:'🛗', building:'workshop', kind:'siege',
              atk:120, def:14, hp:70, speed:4, carry:15, upkeep:5, people:2,
              cost:{wood:250,iron:110,food:30}, time:150, req:{workshop:1} },
};

// ─── ТЕХНОЛОГИИ (Кузница) ────────────────────────────────────────────
const TECHS = {
  weapons:  { name:'Острое оружие', icon:'🗡️', cost:{gold:500,iron:300,wood:200}, req:{smithy:2},
              effect:'Атака всех войск +12%', mods:{atk:0.12} },
  armor:    { name:'Прочная броня', icon:'🛡️', cost:{gold:500,iron:300,stone:200}, req:{smithy:3},
              effect:'Защита всех войск +12%', mods:{def:0.12} },
  logistics:{ name:'Логистика', icon:'🐴', cost:{gold:400,food:300,wood:200}, req:{smithy:2},
              effect:'Скорость армии +20%', mods:{speed:0.20} },
  economy:  { name:'Экономика', icon:'📈', cost:{gold:600,stone:300,wood:300}, req:{market:3},
              effect:'Производство всех ресурсов +15%', mods:{prod:0.15} },
  masonry:  { name:'Каменная кладка', icon:'🧱', cost:{gold:500,stone:500}, req:{wall:3},
              effect:'Защита стен +25%', mods:{wall:0.25} },
};

// Глобальные константы мира
const WORLD_SIZE   = 11;   // карта мира WORLD_SIZE × WORLD_SIZE клеток
const TICK_MS      = 1000; // игровой тик
const SPEED_FACTOR = 6;    // ускорение производства/строительства для играбельности

if (typeof module !== 'undefined') module.exports = { RACES, RES, RES_LABEL, RES_ICON, BUILDINGS, UNITS, TECHS, WORLD_SIZE, TICK_MS, SPEED_FACTOR };
