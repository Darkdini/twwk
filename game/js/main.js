// ═══════════════════════════════════════════════════════════════════
//  ТОЧКА ВХОДА  ·  Третий мир — Война Королей
//  Экран создания королевства, запуск тика и интерфейса.
// ═══════════════════════════════════════════════════════════════════

(function(){
  const start = document.getElementById('start');
  const app   = document.getElementById('app');

  function showGame(){
    start.style.display='none';
    app.style.display='flex';
    UI.init();
    // основной игровой тик
    setInterval(()=>Engine.tick(), TICK_MS);
    // плавное обновление таймеров между тиками
    setInterval(()=>UI.tickTimers(), 250);
  }

  function showStart(){
    start.style.display='flex';
    app.style.display='none';
    let race='human';
    const raceWrap=document.getElementById('races');
    raceWrap.innerHTML=Object.keys(RACES).map(id=>{
      const r=RACES[id];
      return `<div class="racecard${id==='human'?' sel':''}" data-race="${id}" style="--rc:${r.color}">
        <div class="re">${r.emoji}</div>
        <b>${r.name}</b>
        <small>${r.bonus}</small>
      </div>`;
    }).join('');
    raceWrap.querySelectorAll('.racecard').forEach(el=>{
      el.onclick=()=>{ race=el.dataset.race;
        raceWrap.querySelectorAll('.racecard').forEach(x=>x.classList.toggle('sel',x===el)); };
    });
    document.getElementById('startbtn').onclick=()=>{
      const name=(document.getElementById('kingname').value||'Король').trim().slice(0,20);
      Engine.newGame(name, race);
      showGame();
    };
  }

  // продолжить или начать заново
  if (Engine.load()){
    document.getElementById('resume').style.display='block';
    document.getElementById('resumebtn').onclick=()=>showGame();
    document.getElementById('newbtn').onclick=()=>{ if(confirm('Начать заново? Прогресс будет удалён.')){ Engine.reset(); showStart(); } };
    // показываем стартовый экран с кнопкой продолжения
    showStart();
    document.getElementById('resume').style.display='block';
  } else {
    showStart();
  }

  // глобальная кнопка «меню/сброс» в шапке
  document.getElementById('menubtn')?.addEventListener('click',()=>{
    if (confirm('Выйти в меню? Прогресс сохранён автоматически.')){
      location.reload();
    }
  });
})();
