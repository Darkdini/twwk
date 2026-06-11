// ═══════════════════════════════════════════════════════════════════
//  ИГРОВОЙ ДВИЖОК  ·  Третий мир — Война Королей
//  Хранит состояние, считает производство, строительство, обучение,
//  боёвку, мир и простой ИИ соседних королевств.
//  Всё работает в браузере, сохранение — в localStorage.
// ═══════════════════════════════════════════════════════════════════

const SAVE_KEY = 'twwk_save_v1';

const Engine = {
  state: null,
  listeners: [],

  // ── подписка на изменения (для перерисовки UI) ──────────────────
  on(fn){ this.listeners.push(fn); },
  emit(){ for (const fn of this.listeners) fn(this.state); },

  // ── создание нового мира ────────────────────────────────────────
  newGame(name, race){
    const now = Date.now();
    const p = {
      name, race, createdAt: now,
      res: { gold:500, wood:400, stone:400, food:400, iron:200, people:30 },
      buildings: {            // зданиеId -> уровень
        townhall:1, storage:1, house:1, farm:1, sawmill:1, quarry:1, mine:1,
      },
      army: {},               // unitId -> count (гарнизон)
      techs: {},              // techId -> true
      build: null,            // { bldId, ends, level }
      train: null,            // { unitId, count, ends }
      research: null,         // { techId, ends }
      marches: [],            // походы войск
      reports: [],
      col: 5, row: 5,         // позиция игрока на карте мира
    };
    this.state = {
      player: p,
      world: this.genWorld(p),
      lastTick: now,
    };
    this.normalizeArmy();
    this.save();
    this.emit();
  },

  // ── генерация карты мира с ИИ-королевствами и лагерями ───────────
  genWorld(player){
    const tiles = [];
    const rng = mulberry32(Date.now() & 0xffffffff);
    const names = ['Валун','Тёмный Лог','Железный Холм','Солнечный Брод','Вороний Утёс',
                   'Старый Дуб','Кровавый Перевал','Серебряный Дол','Гнилое Болото','Драконий Шпиль'];
    const races = ['human','elf','dwarf','orc'];
    for (let r=0;r<WORLD_SIZE;r++){
      for (let c=0;c<WORLD_SIZE;c++){
        let t = { col:c, row:r, type:'empty' };
        if (c===player.col && r===player.row){ t.type='player'; }
        tiles.push(t);
      }
    }
    const get = (c,r)=>tiles[r*WORLD_SIZE+c];
    // лагеря разбойников/дикарей (нейтральные цели для фарма)
    let placed=0;
    for (let i=0;i<60 && placed<14;i++){
      const c=Math.floor(rng()*WORLD_SIZE), r=Math.floor(rng()*WORLD_SIZE);
      const t=get(c,r);
      if (t.type!=='empty') continue;
      const power = 1 + Math.floor(rng()*4);
      t.type='camp';
      t.name='Лагерь разбойников';
      t.power=power;
      t.garrison=this.campGarrison(power);
      t.loot={ gold:80*power, wood:60*power, stone:60*power, food:50*power, iron:30*power };
      t.respawn=0;
      placed++;
    }
    // ИИ-королевства
    let kdoms=0;
    for (let i=0;i<80 && kdoms<8;i++){
      const c=Math.floor(rng()*WORLD_SIZE), r=Math.floor(rng()*WORLD_SIZE);
      const t=get(c,r);
      if (t.type!=='empty') continue;
      if (Math.abs(c-player.col)+Math.abs(r-player.row) < 2) continue;
      const lvl = 1 + Math.floor(rng()*5);
      t.type='kingdom';
      t.name=names[kdoms%names.length];
      t.race=races[Math.floor(rng()*races.length)];
      t.level=lvl;
      t.wall=Math.floor(rng()*lvl);
      t.garrison=this.kingdomGarrison(lvl);
      t.res={ gold:200*lvl, wood:150*lvl, stone:150*lvl, food:120*lvl, iron:80*lvl };
      kdoms++;
    }
    return { size:WORLD_SIZE, tiles };
  },

  campGarrison(power){
    return { spearman: 8*power, swordsman: 5*power, archer: 4*power };
  },
  kingdomGarrison(lvl){
    return { spearman: 10*lvl, swordsman: 8*lvl, archer: 6*lvl, knight: 2*lvl };
  },

  tile(c,r){ return this.state.world.tiles[r*WORLD_SIZE+c]; },

  // ── гарантировать, что все юниты есть как числа ──────────────────
  normalizeArmy(){
    const a = this.state.player.army;
    for (const u in UNITS) if (a[u]==null) a[u]=0;
  },

  // ═════════════════ ЭКОНОМИКА ════════════════════════════════════
  // производство ресурса/час с учётом зданий, расы, технологий
  rates(){
    const p = this.state.player;
    const out = { gold:0, wood:0, stone:0, food:0, iron:0, people:0 };
    for (const id in p.buildings){
      const lv=p.buildings[id]; const b=BUILDINGS[id];
      if (!b || !b.prod || lv<=0) continue;
      for (const k in b.prod) out[k] += b.prod[k]*lv;
    }
    out.gold += 20; // базовый налог
    // бонус расы
    const race=RACES[p.race];
    if (race.prodBonus) for (const k in race.prodBonus) out[k]*=(1+race.prodBonus[k]);
    // технология экономики
    if (p.techs.economy) for (const k in out) out[k]*=1+TECHS.economy.mods.prod;
    // содержание армии съедает еду
    out.food -= this.upkeep();
    for (const k in out) out[k]=Math.round(out[k]);
    return out;
  },

  upkeep(){
    const p=this.state.player; let f=0;
    for (const u in p.army) f += (UNITS[u]?.upkeep||0)*(p.army[u]||0);
    for (const m of p.marches) for (const u in (m.units||{})) f += (UNITS[u]?.upkeep||0)*m.units[u];
    return f;
  },

  storageCap(){
    const lv=this.state.player.buildings.storage||1;
    const th=this.state.player.buildings.townhall||1;
    return 2000 + lv*1500 + th*500;
  },

  popCap(){
    const h=this.state.player.buildings.house||0;
    const th=this.state.player.buildings.townhall||1;
    return 30 + h*40 + th*10;
  },

  // ── стоимость/время следующего уровня ───────────────────────────
  buildCost(id, lvl){
    const b=BUILDINGS[id]; const mult=Math.pow(1.6,lvl);
    const c={}; for (const k in b.cost) c[k]=Math.round(b.cost[k]*mult);
    return c;
  },
  buildTime(id, lvl){
    const b=BUILDINGS[id];
    const t=b.time*Math.pow(1.5,lvl)/SPEED_FACTOR;
    return Math.max(3, Math.round(t));
  },

  canAfford(cost){
    const r=this.state.player.res;
    for (const k in cost) if ((r[k]||0)<cost[k]) return false;
    return true;
  },
  pay(cost){ const r=this.state.player.res; for (const k in cost) r[k]-=cost[k]; },

  reqMet(id){
    const b=BUILDINGS[id]; if (!b.req) return true;
    for (const k in b.req) if ((this.state.player.buildings[k]||0)<b.req[k]) return false;
    return true;
  },

  // максимально допустимый уровень = ограничен ратушей
  cap(id){
    const b=BUILDINGS[id];
    const th=this.state.player.buildings.townhall||1;
    if (id==='townhall') return b.max;
    return Math.min(b.max, th); // здания не выше уровня ратуши
  },

  // ═════════════════ КОМАНДЫ ИГРОКА ═══════════════════════════════
  startBuild(id){
    const p=this.state.player;
    if (p.build) return this.fail('Уже идёт строительство.');
    if (!BUILDINGS[id]) return this.fail('Нет такого здания.');
    if (!this.reqMet(id)) return this.fail('Не выполнены требования.');
    const cur=p.buildings[id]||0;
    if (cur>=this.cap(id)) return this.fail(cur>=BUILDINGS[id].max?'Достигнут максимум.':'Сначала улучшите Ратушу.');
    const cost=this.buildCost(id,cur);
    if (!this.canAfford(cost)) return this.fail('Недостаточно ресурсов.');
    this.pay(cost);
    p.build={ bldId:id, level:cur+1, ends:Date.now()+this.buildTime(id,cur)*1000 };
    this.save(); this.emit(); return this.okMsg();
  },

  cancelBuild(){
    const p=this.state.player; if (!p.build) return;
    const cost=this.buildCost(p.build.bldId,p.build.level-1);
    for (const k in cost) p.res[k]+=Math.floor(cost[k]*0.6);
    p.build=null; this.save(); this.emit();
  },

  startTrain(unitId, count){
    const p=this.state.player; const u=UNITS[unitId];
    if (!u) return this.fail('Нет такого юнита.');
    if (p.train) return this.fail('Казармы заняты обучением.');
    if ((p.buildings[u.building]||0)<1) return this.fail('Нужно построить '+BUILDINGS[u.building].name+'.');
    if (u.req) for (const k in u.req) if ((p.buildings[k]||0)<u.req[k]) return this.fail('Требуется '+BUILDINGS[k].name+' ур.'+u.req[k]+'.');
    count=Math.max(1,Math.floor(count));
    const need=u.people*count;
    if (this.freePop()<need) return this.fail('Не хватает населения ('+this.freePop()+').');
    const cost={}; for (const k in u.cost) cost[k]=u.cost[k]*count;
    if (!this.canAfford(cost)) return this.fail('Недостаточно ресурсов.');
    this.pay(cost);
    const speed = 1 + (p.buildings[u.building]-1)*0.08; // выше здание — быстрее
    const total = (u.time*count/SPEED_FACTOR)/speed;
    p.train={ unitId, count, ends:Date.now()+Math.max(2,total)*1000 };
    this.save(); this.emit(); return this.okMsg();
  },

  // население, занятое армией
  usedPop(){
    const p=this.state.player; let n=0;
    for (const u in p.army) n += (UNITS[u]?.people||0)*(p.army[u]||0);
    for (const m of p.marches) for (const u in (m.units||{})) n += (UNITS[u]?.people||0)*m.units[u];
    if (p.train) n += (UNITS[p.train.unitId]?.people||0)*p.train.count;
    return n;
  },
  freePop(){ return Math.max(0, Math.floor(this.state.player.res.people) - this.usedPop()); },

  startResearch(techId){
    const p=this.state.player; const t=TECHS[techId];
    if (!t) return this.fail('Нет такой технологии.');
    if (p.techs[techId]) return this.fail('Уже изучено.');
    if (p.research) return this.fail('Кузница занята.');
    for (const k in t.req) if ((p.buildings[k]||0)<t.req[k]) return this.fail('Требуется '+BUILDINGS[k].name+' ур.'+t.req[k]+'.');
    if (!this.canAfford(t.cost)) return this.fail('Недостаточно ресурсов.');
    this.pay(t.cost);
    p.research={ techId, ends:Date.now()+ (120/SPEED_FACTOR)*1000 };
    this.save(); this.emit(); return this.okMsg();
  },

  // ── обмен на рынке: продать ресурс за золото / купить ───────────
  market(sellRes, amount){
    const p=this.state.player;
    if ((p.buildings.market||0)<1) return this.fail('Нужен Рынок.');
    amount=Math.floor(amount);
    if (sellRes==='gold') return this.fail('Золото не продаётся.');
    if ((p.res[sellRes]||0)<amount) return this.fail('Недостаточно ресурса.');
    p.res[sellRes]-=amount;
    p.res.gold+=Math.floor(amount*0.5); // курс 2:1
    this.save(); this.emit(); return this.okMsg();
  },

  // ═════════════════ ВОЕННЫЕ ПОХОДЫ ═══════════════════════════════
  // отправить армию на клетку (attack | scout)
  sendArmy(col, row, units, mode){
    const p=this.state.player;
    const tile=this.tile(col,row);
    if (!tile || tile.type==='player' || tile.type==='empty')
      return this.fail('Здесь некого атаковать.');
    let total=0; for (const u in units) total+=units[u];
    if (total<=0) return this.fail('Выберите войска.');
    for (const u in units){
      if ((p.army[u]||0)<units[u]) return this.fail('Недостаточно войск: '+UNITS[u].name+'.');
    }
    // снять войска из гарнизона
    for (const u in units) p.army[u]-=units[u];
    // скорость = минимум по самому медленному, с бонусами
    let minSpeed=99; for (const u in units) if (units[u]>0) minSpeed=Math.min(minSpeed, UNITS[u].speed);
    const race=RACES[p.race];
    let spdMul = 1 + (race.marchSpeed||0) + (p.techs.logistics?TECHS.logistics.mods.speed:0);
    const dist=Math.abs(col-p.col)+Math.abs(row-p.row);
    const travel=Math.max(4, (dist*8)/(minSpeed*spdMul/4)); // сек
    const march={
      id:Math.random().toString(36).slice(2),
      mode, fromCol:p.col, fromRow:p.row, col, row, units,
      depart:Date.now(),
      arrive:Date.now()+travel*1000,
      ret:false,
    };
    p.marches.push(march);
    this.save(); this.emit(); return this.okMsg();
  },

  // ═════════════════ ОСНОВНОЙ ТИК ═════════════════════════════════
  tick(){
    if (!this.state) return;
    const now=Date.now();
    let dt=(now-this.state.lastTick)/1000;
    if (dt<=0){ return; }
    if (dt>3600) dt=3600; // оффлайн-капа 1 час реального
    this.state.lastTick=now;
    const p=this.state.player;

    // производство ресурсов
    const rates=this.rates();
    const cap=this.storageCap();
    for (const k of RES){
      if (k==='people'){
        p.res.people = Math.min(this.popCap(), p.res.people + rates.people*dt/3600);
      } else {
        p.res[k]+= rates[k]*dt/3600;
        if (k!=='food') p.res[k]=Math.min(cap, p.res[k]);
        if (p.res[k]<0) p.res[k]=0;
      }
    }
    // голод: если еды нет — войска дезертируют
    if (p.res.food<0){
      p.res.food=0;
      this.starve();
    }

    // строительство
    if (p.build && now>=p.build.ends){
      p.buildings[p.build.bldId]=p.build.level;
      this.report('🏗️ Построено: '+BUILDINGS[p.build.bldId].name+' ур.'+p.build.level,'build');
      p.build=null;
    }
    // обучение
    if (p.train && now>=p.train.ends){
      p.army[p.train.unitId]=(p.army[p.train.unitId]||0)+p.train.count;
      this.report('⚔️ Обучено: '+UNITS[p.train.unitId].name+' ×'+p.train.count,'train');
      p.train=null;
    }
    // исследования
    if (p.research && now>=p.research.ends){
      p.techs[p.research.techId]=true;
      this.report('🔬 Изучено: '+TECHS[p.research.techId].name,'tech');
      p.research=null;
    }
    // походы
    for (const m of [...p.marches]){
      if (!m.ret && now>=m.arrive){
        this.resolveMarch(m);
      } else if (m.ret && now>=m.back){
        // войска вернулись домой
        for (const u in m.units) p.army[u]=(p.army[u]||0)+m.units[u];
        if (m.loot) for (const k in m.loot) p.res[k]=Math.min(this.storageCap(), (p.res[k]||0)+m.loot[k]);
        p.marches=p.marches.filter(x=>x!==m);
      }
    }
    // ИИ и возрождение лагерей
    this.worldTick(dt);

    this.emit();
  },

  starve(){
    const p=this.state.player;
    const units=Object.keys(p.army).filter(u=>p.army[u]>0);
    if (!units.length) return;
    const u=units[0];
    const lost=Math.max(1,Math.floor(p.army[u]*0.05));
    p.army[u]-=lost;
    this.report('🍖 Голод! Дезертировало '+lost+' '+UNITS[u].name,'bad');
  },

  // ── разрешение прибытия похода ──────────────────────────────────
  resolveMarch(m){
    const p=this.state.player;
    const tile=this.tile(m.col,m.row);
    if (m.mode==='scout'){
      const info=this.scoutInfo(tile);
      this.report('👁️ Разведка '+(tile.name||'клетки')+': '+info,'scout');
      this.sendBack(m, null);
      return;
    }
    // бой
    if (!tile || (tile.type!=='camp' && tile.type!=='kingdom')){
      this.report('🏳️ Цель исчезла, армия возвращается.','info');
      this.sendBack(m,null); return;
    }
    const defRace = tile.race || 'human';
    const wall = tile.wall||0;
    const result=this.battle(m.units, p.race, tile.garrison||{}, defRace, wall, tile.power||tile.level||1);
    // потери атакующего
    for (const u in m.units){
      const survive=Math.max(0, Math.round(m.units[u]*result.atkSurvive));
      m.units[u]=survive;
    }
    // потери защитника
    for (const u in (tile.garrison||{})){
      tile.garrison[u]=Math.max(0,Math.round(tile.garrison[u]*result.defSurvive));
    }
    let atkAlive=0; for (const u in m.units) atkAlive+=m.units[u];
    let defAlive=0; for (const u in (tile.garrison||{})) defAlive+=tile.garrison[u];

    if (result.win && atkAlive>0){
      // добыча
      const cap=this.marchCarry(m.units);
      const loot={};
      const src = tile.loot || tile.res || {};
      for (const k in src){
        const take=Math.min(src[k]||0, Math.floor(cap/Object.keys(src).length));
        if (take>0){ loot[k]=take; src[k]-=take; }
      }
      this.report('🏆 Победа у '+(tile.name||'цели')+'! Добыча: '+this.fmtLoot(loot),'win');
      if (tile.type==='camp'){
        tile.garrison={}; tile.respawn=Date.now()+ (180/SPEED_FACTOR)*1000;
      }
      this.sendBack(m, loot);
    } else {
      this.report('💀 Поражение у '+(tile.name||'цели')+'. Осталось воинов: '+atkAlive,'bad');
      this.sendBack(m, null);
    }
  },

  marchCarry(units){ let c=0; for (const u in units) c+=(UNITS[u]?.carry||0)*units[u]; return c; },

  sendBack(m, loot){
    m.ret=true; m.loot=loot;
    const dur=(m.arrive-m.depart);
    m.back=Date.now()+Math.max(2000,dur);
  },

  // ── расчёт боя: атака против защиты с учётом HP ──────────────────
  battle(atk, atkRace, def, defRace, wall, power){
    const ar=RACES[atkRace], dr=RACES[defRace];
    const techMul = (this.state.player.techs.weapons?1.12:1);
    // суммарная атака и HP нападающих
    let atkPow=0, atkHP=0;
    for (const u in atk){ if (!atk[u]) continue; const s=UNITS[u];
      let a=s.atk; a*= (ar.atkMult||1); a*=techMul; a*=(1+(ar.fieldAtk||0));
      atkPow+=a*atk[u]; atkHP+=s.hp*atk[u];
    }
    // суммарная защита и HP обороняющихся
    let defPow=0, defHP=0;
    for (const u in def){ if (!def[u]) continue; const s=UNITS[u];
      let d=s.def; d*=(1+(dr.def||0)); d*=(1-(dr.defPenalty||0));
      defPow+=d*def[u]; defHP+=s.hp*def[u];
    }
    // бонус стен и расы защитника-замка
    let wallMul = 1 + wall*0.06*(this.state.player.techs.masonry?1.25:1);
    if (defRace==='human') wallMul += dr.castleDef||0;
    defPow*=wallMul; defHP*=Math.sqrt(wallMul);
    // базовый «пол» обороны лагеря, чтобы пустые цели тоже имели риск
    defPow=Math.max(defPow, power*15);
    defHP =Math.max(defHP,  power*30);

    // моделируем размен: доля урона
    const totalA=atkPow+1, totalD=defPow+1;
    const win = atkPow >= defPow;
    // выжившие = 1 - доля урона, нанесённого противником, нормированная на HP
    const atkLossFrac = Math.min(0.98, defPow / (atkHP+totalD));
    const defLossFrac = Math.min(1, atkPow / (defHP+totalA));
    return {
      win,
      atkSurvive: win ? Math.max(0.25, 1-atkLossFrac*0.6) : Math.max(0, 1-atkLossFrac),
      defSurvive: win ? 0 : Math.max(0.1, 1-defLossFrac*0.7),
    };
  },

  scoutInfo(tile){
    if (tile.type==='camp') return 'разбойники, сила '+(tile.power||1)+', гарнизон '+this.countGarr(tile.garrison);
    if (tile.type==='kingdom') return RACES[tile.race].name+', ур.'+tile.level+', стена '+tile.wall+', гарнизон '+this.countGarr(tile.garrison)+', золота ~'+(tile.res?.gold||0);
    return 'пусто';
  },
  countGarr(g){ let n=0; for (const u in (g||{})) n+=g[u]; return n; },

  // ── мир: возрождение лагерей + рост ИИ ──────────────────────────
  worldTick(dt){
    const now=Date.now();
    for (const t of this.state.world.tiles){
      if (t.type==='camp' && t.respawn && now>=t.respawn){
        t.garrison=this.campGarrison(t.power);
        t.loot={ gold:80*t.power, wood:60*t.power, stone:60*t.power, food:50*t.power, iron:30*t.power };
        t.respawn=0;
      }
      if (t.type==='kingdom' && t.res){
        for (const k in t.res) t.res[k]+= (8*t.level)*dt/3600;
      }
    }
  },

  // ═════════════════ ОТЧЁТЫ / СОХРАНЕНИЕ ══════════════════════════
  report(text, kind='info'){
    this.state.player.reports.unshift({ text, kind, t:Date.now() });
    if (this.state.player.reports.length>50) this.state.player.reports.length=50;
  },

  fail(m){ return { ok:false, error:m }; },
  okMsg(){ return { ok:true }; },

  save(){ try{ localStorage.setItem(SAVE_KEY, JSON.stringify(this.state)); }catch(e){} },
  load(){
    try{
      const raw=localStorage.getItem(SAVE_KEY);
      if (!raw) return false;
      this.state=JSON.parse(raw);
      this.normalizeArmy();
      return true;
    }catch(e){ return false; }
  },
  reset(){ localStorage.removeItem(SAVE_KEY); this.state=null; },

  fmtLoot(l){
    const parts=[]; for (const k in l) if (l[k]>0) parts.push(RES_ICON[k]+Math.round(l[k]));
    return parts.length?parts.join(' '):'ничего';
  },
};

// детерминированный ГСЧ
function mulberry32(a){ return function(){ a|=0; a=a+0x6D2B79F5|0; let t=Math.imul(a^a>>>15,1|a); t=t+Math.imul(t^t>>>7,61|t)^t; return ((t^t>>>14)>>>0)/4294967296; }; }
