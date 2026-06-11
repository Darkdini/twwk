// ═══════════════════════════════════════════════════════════════════
//  ИНТЕРФЕЙС  ·  Третий мир — Война Королей
//  Рендерит экраны (Город · Армия · Мир · Отчёты) и обрабатывает ввод.
// ═══════════════════════════════════════════════════════════════════

const UI = {
  tab: 'city',
  selTile: null,   // выбранная клетка мира
  marchUnits: {},  // черновик армии для похода

  init(){
    Engine.on(()=>this.render());
    this.bindTabs();
    this.render();
    document.getElementById('toast-x')?.addEventListener('click',()=>this.hideToast());
  },

  bindTabs(){
    document.querySelectorAll('.tab').forEach(el=>{
      el.addEventListener('click',()=>{ this.tab=el.dataset.tab; this.render(); });
    });
  },

  toast(msg, bad){
    const t=document.getElementById('toast');
    t.textContent=msg;
    t.className='toast show'+(bad?' bad':'');
    clearTimeout(this._tt);
    this._tt=setTimeout(()=>t.className='toast',2200);
  },
  hideToast(){ document.getElementById('toast').className='toast'; },

  // ── верхняя панель ресурсов ─────────────────────────────────────
  renderTop(){
    const p=Engine.state.player;
    const rates=Engine.rates();
    const cap=Engine.storageCap();
    const bar=document.getElementById('resbar');
    bar.innerHTML = RES.map(k=>{
      const v=Math.floor(p.res[k]);
      const rate=rates[k];
      const extra = k==='people' ? ' / '+Engine.popCap()
                  : k==='food'   ? '' : '';
      const rateStr = (rate>=0?'+':'')+rate+'/ч';
      const warn = (k!=='people'&&k!=='food'&&v>=cap)?' style="color:#ff8"':'';
      return `<div class="res" title="${RES_LABEL[k]} ${rateStr}">
        <span class="ri">${RES_ICON[k]}</span>
        <b${warn}>${v}${extra}</b>
        <small class="${rate<0?'neg':''}">${rateStr}</small></div>`;
    }).join('');
    document.getElementById('whoami').textContent =
      `${RACES[p.race].emoji} ${p.name} · ${RACES[p.race].name}`;
  },

  render(){
    if (!Engine.state) return;
    this.renderTop();
    document.querySelectorAll('.tab').forEach(el=>
      el.classList.toggle('active', el.dataset.tab===this.tab));
    const root=document.getElementById('screen');
    if (this.tab==='city')   root.innerHTML=this.cityHTML();
    if (this.tab==='army')   root.innerHTML=this.armyHTML();
    if (this.tab==='world')  root.innerHTML=this.worldHTML();
    if (this.tab==='reports')root.innerHTML=this.reportsHTML();
    this.wire();
  },

  // ─────────────────────────── ГОРОД ─────────────────────────────
  cityHTML(){
    const p=Engine.state.player;
    let queue='';
    if (p.build){
      const b=BUILDINGS[p.build.bldId];
      queue += this.timerCard('🏗️ Строительство', b.icon+' '+b.name+' → ур.'+p.build.level, p.build.ends, 'cancelBuild');
    }
    if (p.train){
      const u=UNITS[p.train.unitId];
      queue += this.timerCard('⚔️ Обучение', u.icon+' '+u.name+' ×'+p.train.count, p.train.ends);
    }
    if (p.research){
      const t=TECHS[p.research.techId];
      queue += this.timerCard('🔬 Исследование', t.icon+' '+t.name, p.research.ends);
    }

    const cards=Object.keys(BUILDINGS).map(id=>{
      const b=BUILDINGS[id]; const lv=p.buildings[id]||0;
      const built=lv>0;
      const reqOk=Engine.reqMet(id);
      const atMax=lv>=b.max;
      const capped=lv>=Engine.cap(id) && !atMax;
      const cost=Engine.buildCost(id,lv);
      const afford=Engine.canAfford(cost);
      let costStr=Object.keys(cost).map(k=>`<span class="${(p.res[k]||0)<cost[k]?'lack':''}">${RES_ICON[k]}${cost[k]}</span>`).join(' ');
      let prodStr='';
      if (b.prod){ prodStr=Object.keys(b.prod).map(k=>`${RES_ICON[k]}+${b.prod[k]*(lv||1)}/ч`).join(' '); }
      let btn;
      if (!reqOk){
        const r=Object.keys(b.req).map(k=>BUILDINGS[k].name+' '+b.req[k]).join(', ');
        btn=`<button class="b-build" disabled>🔒 ${r}</button>`;
      } else if (atMax){
        btn=`<button class="b-build" disabled>Максимум</button>`;
      } else if (capped){
        btn=`<button class="b-build" disabled>Нужна Ратуша выше</button>`;
      } else {
        const dis=(!afford||p.build)?'disabled':'';
        const t=Engine.buildTime(id,lv);
        btn=`<button class="b-build" data-build="${id}" ${dis}>${built?'Улучшить':'Построить'} · ${this.dur(t)}</button>`;
      }
      return `<div class="card ${built?'':'dim'}">
        <div class="card-h"><span class="bi">${b.icon}</span>
          <div><b>${b.name}</b>${built?` <span class="lv">ур.${lv}</span>`:''}</div></div>
        <div class="card-d">${b.desc||''}</div>
        ${prodStr?`<div class="card-prod">${prodStr}</div>`:''}
        <div class="card-cost">${costStr}</div>
        ${btn}
      </div>`;
    }).join('');

    return `${queue?`<div class="queue">${queue}</div>`:''}
      <h2>🏰 Город</h2>
      <div class="grid">${cards}</div>`;
  },

  timerCard(title, what, ends, cancelFn){
    const left=Math.max(0,(ends-Date.now())/1000);
    return `<div class="tcard">
      <div class="tc-h">${title}</div>
      <div class="tc-w">${what}</div>
      <div class="tc-t" data-timer="${ends}">${this.dur(left)}</div>
      ${cancelFn?`<button class="b-cancel" data-cancel="${cancelFn}">✖ Отменить</button>`:''}
    </div>`;
  },

  // ─────────────────────────── АРМИЯ ─────────────────────────────
  armyHTML(){
    const p=Engine.state.player;
    const free=Engine.freePop();
    // обучение
    const trainCards=Object.keys(UNITS).map(id=>{
      const u=UNITS[id]; const have=p.army[id]||0;
      const bLv=p.buildings[u.building]||0;
      let locked = bLv<1;
      let reqTxt='Нужно: '+BUILDINGS[u.building].name;
      if (!locked && u.req) for (const k in u.req) if ((p.buildings[k]||0)<u.req[k]){ locked=true; reqTxt='Нужно: '+BUILDINGS[k].name+' ур.'+u.req[k]; }
      const cost=Object.keys(u.cost).map(k=>`${RES_ICON[k]}${u.cost[k]}`).join(' ');
      return `<div class="card ${locked?'dim':''}">
        <div class="card-h"><span class="bi">${u.icon}</span>
          <div><b>${u.name}</b> <span class="lv">×${have}</span></div></div>
        <div class="ustat">⚔${u.atk} 🛡${u.def} ❤${u.hp} 🐾${u.speed} 🎒${u.carry}</div>
        <div class="card-cost">${cost} 👥${u.people} · ${this.dur(Math.round(u.time/SPEED_FACTOR))}</div>
        ${locked
          ? `<button class="b-build" disabled>🔒 ${reqTxt}</button>`
          : `<div class="trainrow">
               <input type="number" min="1" value="1" class="tnum" data-num="${id}">
               <button class="b-train" data-train="${id}" ${p.train?'disabled':''}>Обучить</button>
             </div>`}
      </div>`;
    }).join('');

    // технологии
    const techCards=Object.keys(TECHS).map(id=>{
      const t=TECHS[id]; const done=p.techs[id];
      let ok=true,reqTxt='';
      for (const k in t.req) if ((p.buildings[k]||0)<t.req[k]){ ok=false; reqTxt='Нужно: '+BUILDINGS[k].name+' ур.'+t.req[k]; }
      const cost=Object.keys(t.cost).map(k=>`${RES_ICON[k]}${t.cost[k]}`).join(' ');
      return `<div class="card ${done?'':ok?'':'dim'}">
        <div class="card-h"><span class="bi">${t.icon}</span><div><b>${t.name}</b></div></div>
        <div class="card-d">${t.effect}</div>
        ${done?`<button class="b-build" disabled>✓ Изучено</button>`
          : ok?`<div class="card-cost">${cost}</div><button class="b-tech" data-tech="${id}" ${p.research?'disabled':''}>Изучить · ${this.dur(Math.round(120/SPEED_FACTOR))}</button>`
              :`<button class="b-build" disabled>🔒 ${reqTxt}</button>`}
      </div>`;
    }).join('');

    return `<h2>⚔️ Армия <span class="sub">свободного населения: ${free}</span></h2>
      <h3>Обучение войск</h3>
      <div class="grid">${trainCards}</div>
      <h3>Кузница — технологии</h3>
      <div class="grid">${techCards}</div>`;
  },

  // ─────────────────────────── МИР ───────────────────────────────
  worldHTML(){
    const p=Engine.state.player;
    const W=Engine.state.world;
    let cells='';
    for (let r=0;r<W.size;r++){
      for (let c=0;c<W.size;c++){
        const t=Engine.tile(c,r);
        let cls='wt', label='';
        if (t.type==='player'){ cls+=' wt-me'; label='🏰'; }
        else if (t.type==='kingdom'){ cls+=' wt-k'; label=RACES[t.race].emoji; }
        else if (t.type==='camp'){ cls+=' wt-camp'; label=(t.garrison&&Engine.countGarr(t.garrison)>0)?'🏴':'·'; }
        else label='';
        const sel=(this.selTile&&this.selTile.col===c&&this.selTile.row===r)?' wt-sel':'';
        cells+=`<div class="${cls}${sel}" data-cell="${c},${r}" title="${t.name||''}">${label}</div>`;
      }
    }
    // походы в пути
    let marches='';
    if (p.marches.length){
      marches='<div class="marches">'+p.marches.map(m=>{
        const left=Math.max(0,(( m.ret?m.back:m.arrive)-Date.now())/1000);
        const dir=m.ret?'↩ возврат':(m.mode==='scout'?'👁 разведка':'⚔ поход');
        let n=0; for (const u in m.units) n+=m.units[u];
        return `<div class="mtag" data-timer="${m.ret?m.back:m.arrive}">${dir} → (${m.col},${m.row}) · ${n} воин. · ${this.dur(left)}</div>`;
      }).join('')+'</div>';
    }

    return `<h2>🗺️ Мир <span class="sub">твой замок в центре</span></h2>
      ${marches}
      <div class="worldwrap"><div class="world" style="--n:${W.size}">${cells}</div></div>
      <div id="tilepanel">${this.tilePanelHTML()}</div>`;
  },

  tilePanelHTML(){
    const t=this.selTile; if (!t) return '<div class="hint">Выбери клетку на карте.</div>';
    const tile=Engine.tile(t.col,t.row);
    const p=Engine.state.player;
    if (tile.type==='player') return '<div class="hint">🏰 Твой замок. Здесь твой гарнизон.</div>';
    if (tile.type==='empty')  return '<div class="hint">Пустая земля.</div>';
    let info='';
    if (tile.type==='camp'){
      const alive=Engine.countGarr(tile.garrison);
      info=`<b>🏴 ${tile.name}</b> · сила ${tile.power}<br>
        Гарнизон: ${alive>0?alive+' воинов':'<i>разбит, возрождается…</i>'}<br>
        Добыча: ${Object.keys(tile.loot||{}).map(k=>RES_ICON[k]+tile.loot[k]).join(' ')||'—'}`;
    } else if (tile.type==='kingdom'){
      info=`<b>${RACES[tile.race].emoji} ${tile.name}</b> · ${RACES[tile.race].name} ур.${tile.level}<br>
        Стена: ${tile.wall} · Гарнизон: ${Engine.countGarr(tile.garrison)} воинов<br>
        Казна: ${Object.keys(tile.res||{}).map(k=>RES_ICON[k]+Math.floor(tile.res[k])).join(' ')}`;
    }
    // выбор войск
    const army=p.army;
    const rows=Object.keys(UNITS).filter(u=>(army[u]||0)>0).map(u=>{
      const have=army[u]||0; const cur=this.marchUnits[u]||0;
      return `<div class="selrow">
        <span>${UNITS[u].icon} ${UNITS[u].name}</span>
        <span class="have">из ${have}</span>
        <input type="number" min="0" max="${have}" value="${cur}" class="mnum" data-munit="${u}">
        <button class="b-all" data-all="${u}">всё</button>
      </div>`;
    }).join('') || '<div class="hint">Нет войск в гарнизоне. Обучи армию во вкладке «Армия».</div>';

    return `<div class="tpanel">
      <div class="tinfo">${info}</div>
      <div class="selarmy">${rows}</div>
      <div class="tbtns">
        <button class="b-attack" data-attack="${t.col},${t.row}">⚔️ Атаковать</button>
        <button class="b-scout" data-scout="${t.col},${t.row}">👁️ Разведать</button>
      </div>
    </div>`;
  },

  // ────────────────────────── ОТЧЁТЫ ─────────────────────────────
  reportsHTML(){
    const p=Engine.state.player;
    if (!p.reports.length) return '<h2>📜 Отчёты</h2><div class="hint">Пока пусто. Стройся, обучай войска и иди в поход!</div>';
    const items=p.reports.map(r=>{
      const time=new Date(r.t).toLocaleTimeString('ru-RU',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
      return `<div class="rep rep-${r.kind}"><span class="rt">${time}</span> ${r.text}</div>`;
    }).join('');
    return `<h2>📜 Отчёты <button class="b-clear" id="clearrep">очистить</button></h2><div class="replist">${items}</div>`;
  },

  // ───────────────────── обработчики событий ─────────────────────
  wire(){
    const q=s=>document.querySelectorAll(s);
    q('[data-build]').forEach(b=>b.onclick=()=>this.act(Engine.startBuild(BTN(b,'build'))));
    q('[data-cancel]').forEach(b=>b.onclick=()=>{ Engine.cancelBuild(); });
    q('[data-train]').forEach(b=>b.onclick=()=>{
      const id=BTN(b,'train');
      const n=document.querySelector(`.tnum[data-num="${id}"]`);
      this.act(Engine.startTrain(id, +(n?.value||1)));
    });
    q('[data-tech]').forEach(b=>b.onclick=()=>this.act(Engine.startResearch(BTN(b,'tech'))));
    q('[data-cell]').forEach(b=>b.onclick=()=>{
      const [c,r]=BTN(b,'cell').split(',').map(Number);
      this.selTile={col:c,row:r}; this.marchUnits={}; this.render();
    });
    q('[data-munit]').forEach(inp=>inp.oninput=()=>{
      const u=inp.dataset.munit; this.marchUnits[u]=Math.max(0,Math.min(+inp.value||0, Engine.state.player.army[u]||0));
    });
    q('[data-all]').forEach(b=>b.onclick=()=>{
      const u=BTN(b,'all'); this.marchUnits[u]=Engine.state.player.army[u]||0; this.render();
    });
    q('[data-attack]').forEach(b=>b.onclick=()=>{
      const [c,r]=BTN(b,'attack').split(',').map(Number);
      this.act(Engine.sendArmy(c,r,this.cleanMarch(),'attack'));
      this.marchUnits={};
    });
    q('[data-scout]').forEach(b=>b.onclick=()=>{
      const [c,r]=BTN(b,'scout').split(',').map(Number);
      const sc=Object.fromEntries(Object.entries(this.cleanMarch()));
      // если ничего не выбрано — шлём 1 разведчика, если есть
      if (!Object.keys(sc).length && (Engine.state.player.army.scout||0)>0) sc.scout=1;
      this.act(Engine.sendArmy(c,r,sc,'scout'));
      this.marchUnits={};
    });
    document.getElementById('clearrep')?.addEventListener('click',()=>{
      Engine.state.player.reports=[]; Engine.save(); this.render();
    });
  },

  cleanMarch(){ const o={}; for (const u in this.marchUnits) if (this.marchUnits[u]>0) o[u]=this.marchUnits[u]; return o; },

  act(res){
    if (!res) return;
    if (res.ok) this.toast('Готово ✓');
    else this.toast(res.error||'Ошибка', true);
  },

  // живое обновление таймеров без полной перерисовки
  tickTimers(){
    document.querySelectorAll('[data-timer]').forEach(el=>{
      const ends=+el.dataset.timer;
      const left=Math.max(0,(ends-Date.now())/1000);
      const txt=this.dur(left);
      if (el.classList.contains('mtag')) el.innerHTML=el.innerHTML.replace(/·\s*[\d:чмс]+\s*$/, '· '+txt);
      else el.textContent=txt;
    });
  },

  dur(s){
    s=Math.max(0,Math.round(s));
    if (s>=3600){ const h=Math.floor(s/3600),m=Math.floor(s%3600/60); return h+'ч '+m+'м'; }
    if (s>=60){ const m=Math.floor(s/60),ss=s%60; return m+'м '+ss+'с'; }
    return s+'с';
  },
};

function BTN(el, key){ return el.dataset[key]; }
