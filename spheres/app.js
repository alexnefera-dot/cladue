/* Spheres v0.1 — модель «сферы жизни», localStorage, обзор + страницы сфер с редактированием.
   Самостоятельный проект, не зависит от основного Pipboy. */
'use strict';

// ======== сид-данные (правятся в UI, сохраняются в localStorage) ========
const SEED = [
  {id:'money',ic:'💰',col:'#c43f3f',name:'Деньги / FIRE',score:7,type:'рост',hist:[6,6,7,7,7,7],
   dest:'пассивный доход ≥ расходов — свобода не работать ради денег',
   calc:'<b>7/10</b> ← 31% капитала от цели €1.0М + ход проектов',
   ms:[{at:2,t:'Подушка 6 мес',done:1},{at:3,t:'€300к капитала',done:1},{at:4,t:'Норма сбережений 40% + ребаланс',next:1},{at:6,t:'€500к + доход Belgravia'},{at:8,t:'€800к'},{at:10,t:'Пассивный доход ≥ расходов'}],
   next:'поднять норму сбережений до 40% и ребалансировать',forStep:['посчитать текущую норму','продать просевшее, докупить по тезисам','авто-перевод 1-го числа'],
   tasks:[{t:'Belgravia — сдать в аренду',pct:70,b:'soon',d:'показ на неделе'},{t:'Ребаланс портфеля',b:'soon',d:'15.07'},{t:'Закрыть долг другу €500',b:'soon',d:'30.06'},{t:'Поднять норму сбережений до 40%',b:'idle'}],
   fin:[{t:'Портфель',v:'€312 400',pct:31,note:'31% от цели €1.0М'},{t:'Аренда (поток)',v:'€1 800/мес'},{t:'Расход/мес',v:'€3 180',pct:91,note:'из бюджета €3 500'}],
   routines:[{t:'Заносить расходы',streak:12,done:1,wk:[1,1,1,0,1,1,1]}],
   tracking:[{n:'Капитал',tg:'цель €1.0М',u:'€',v:'312к',s:[305,307,306,309,310,311,312]},{n:'Норма сбережений',tg:'цель 40%',u:'%',v:'31',s:[24,26,28,27,30,31,31]}],
   info:[['Тезисы по рынку / макро','фаза: поздний цикл, докупать на просадках']],
   ideas:['Аренда <4% — выгоднее держать в индексе, чем в недвиге','Второй источник дохода к 2027'],
   people:[{t:'Дима (агент)',d:'ведёт показ Belgravia'}]},

  {id:'health',ic:'🏃',col:'#1e9e57',name:'Здоровье / тело',score:6,type:'рост',hist:[5,5,6,6,7,6],
   dest:'энергия 8/10 стабильно, форма, падл без травм',calc:'<b>6/10</b> — ревизия + трекинг сна/энергии',
   ms:[{at:3,t:'Режим сна 7.5ч',done:1},{at:5,t:'Зарядка в рутину',done:1},{at:6,t:'Падл 2×/нед',done:1},{at:7,t:'Растяжка после падла (колено)',next:1},{at:8,t:'10к шагов + силовая'},{at:10,t:'Энергия 8/10 стабильно'}],
   next:'добавить растяжку после падла — бережём колено',forStep:['10 мин растяжки в рутину «после падла»','массаж раз в 2 нед'],
   tasks:[{t:'Падл — лига к сентябрю',pct:40,b:'ok',d:'тренировки 2/нед'},{t:'Наладить сон 7.5ч',pct:55,b:'soon'},{t:'Чек-ап у врача',b:'idle',d:'запланировать'}],
   routines:[{t:'Зарядка / мобилити',streak:18,done:1,wk:[1,1,1,1,0,1,1]},{t:'Витамины + миноксидил',streak:42,done:1,wk:[1,1,1,1,1,1,1]},{t:'10 000 шагов',streak:4,done:0,wk:[1,0,1,1,1,0,0]}],
   tracking:[{n:'Сон',tg:'цель 7.5ч',u:'ч',v:'7.2',s:[7.0,6.5,7.2,6.8,7.5,7.4,7.2]},{n:'Энергия',tg:'',u:'/10',v:'7',s:[6,7,6,7,8,7,7]},{n:'Шаги',tg:'цель 10к',u:'к',v:'8.1',s:[8,6,9,7,11,5,8]},{n:'Вес',tg:'цель 76',u:'кг',v:'77.8',s:[78.4,78.2,78.3,78,77.9,78.1,77.8]}],
   practices:[{t:'Дыхание 5 мин (утро)',streak:9,done:1,wk:[1,1,1,1,1,0,1]},{t:'Растяжка после падла',streak:0,done:0,wk:[0,0,1,0,1,0,0]}],
   info:[['Протокол сна','свет, кофеин до 14:00, режим'],['Падл — техника удара','бэкхенд: разворот корпуса раньше']],
   ideas:['Колено ноет после резких — нужна силовая на стабилизаторы','Сон лучше без экрана за час до'],
   people:[{t:'Аня',d:'партнёр по падлу, вт/чт'}]},

  {id:'support',ic:'🛡',col:'#364656',name:'Опора / быт',score:5,type:'опора',hist:[6,5,5,4,5,5],
   dest:'всё оформлено и под контролем: документы, налоги, обязательства — ничего не горит',
   calc:'<b>5/10</b> — близкий дедлайн (легализация) + 1 устаревший баланс',
   ms:[{at:3,t:'Базовые документы в порядке',done:1},{at:5,t:'Легализация подана',next:1},{at:8,t:'Налоги и пассивы под контролем'},{at:10,t:'Всё оформлено, авто-напоминания'}],
   next:'подать документы на легализацию до 30.06 (12 дней)',forStep:['собрать справки','сделать перевод','записаться на подачу'],
   tasks:[{t:'Легализация — подать документы',b:'fire',d:'30.06 · 12 дн'},{t:'Налоги Q2 — €1 200',b:'soon',d:'15.07'},{t:'Adobe €60 — оставить/отменить',b:'soon',d:'3 дня'},{t:'Обновить баланс Tinkoff',b:'idle',d:'устарел 24 дн'}],
   fin:[{t:'Пассивы/обязательства',v:'€620/мес',note:'аренда офиса, страховки, подписки'},{t:'Балансы счетов',v:'4 счёта',note:'1 устарел (Tinkoff)'}],
   info:[['Чек-лист: документы и сроки','паспорта, ВНЖ, страховки — даты продления']],
   ideas:['Пересматривать подписки раз в квартал','Не держать сроки в голове — всё в чек-лист'],
   calendar:[{t:'Легализация — подача',d:'30.06'},{t:'Налоги Q2',d:'15.07'}]},

  {id:'growth',ic:'📚',col:'#6b4fb5',name:'Развитие',score:5,type:'рост',hist:[4,4,5,5,5,5],
   dest:'испанский B1, системное обучение, навык в монетизацию',calc:'<b>5/10</b> ← 15% курса A2→B1',
   ms:[{at:1,t:'Выбрать курс',done:1},{at:2,t:'20 мин/день в рутину',next:1},{at:5,t:'Сдать A2'},{at:8,t:'Разговорный клуб'},{at:10,t:'Сдать B1'}],
   next:'закрепить 20 минут испанского как ежедневную рутину',forStep:['напоминание 8:00','неделя без пропусков'],
   tasks:[{t:'Испанский — B1',pct:15,b:'soon',d:'ежедневно'},{t:'Сдать тест A2',b:'idle',d:'месяц'}],
   routines:[{t:'Испанский 20 мин',streak:6,done:1,wk:[1,1,0,1,1,1,1]},{t:'Anki карточки',streak:2,done:0,wk:[1,1,0,0,1,0,0]}],
   tracking:[{n:'Минут учёбы',tg:'цель 30',u:'мин',v:'35',s:[20,0,40,30,25,50,35]}],
   info:[['Книги и курсы','курс A2→B1, список книг']],ideas:['После B1 — монетизация навыка']},

  {id:'relations',ic:'❤️',col:'#a87708',name:'Отношения',score:8,type:'рост',hist:[7,7,8,8,8,8],
   dest:'тёплый ближний круг, никого не теряю из виду',calc:'<b>8/10</b> — ревизия + ритм контактов',
   ms:[{at:4,t:'Ритм созвонов',done:1},{at:6,t:'Не пропускать ДР',done:1},{at:8,t:'Встречи с друзьями 2×/мес',next:1},{at:10,t:'Глубокие связи'}],
   next:'созвон с мамой — 3 дня молчания',forStep:['позвонить вечером'],
   tasks:[{t:'Созвон с мамой',b:'soon',d:'3 дня'},{t:'Подарок маме на ДР',b:'idle',d:'21 дн'}],
   people:[{t:'Мама',d:'созвон 3 дн · ДР через 21 дн'}],ideas:['Завести важные даты — не пропускать']},

  {id:'rest',ic:'🌿',col:'#2a76b5',name:'Отдых / энергия',score:4,type:'рост',hist:[5,4,4,4,4,4],
   dest:'восстановление без вины: качественные выходные, хобби, отпуска',calc:'<b>4/10</b> — проседает',
   ms:[{at:2,t:'Выходной без задач',next:1},{at:5,t:'Хобби вне экрана'},{at:8,t:'Отпуск раз в квартал'},{at:10,t:'Стабильное восстановление'}],
   next:'один полный выходной без задач на этой неделе',forStep:['заблокировать субботу'],
   tasks:[{t:'Выходной без задач',b:'idle',d:'суббота'}],
   info:[['Идеи на выходные','веломаршрут, бар, музей']],ideas:['Веломаршрут вдоль реки']},
];

// ======== хранилище ========
const KEY='spheres_v0';
let DB = load() || structuredClone(SEED);
function load(){try{const j=JSON.parse(localStorage.getItem(KEY));return Array.isArray(j)&&j.length?j:null;}catch{return null;}}
function save(){localStorage.setItem(KEY,JSON.stringify(DB));}
const byId=id=>DB.find(s=>s.id===id);

let view='overview';
function go(v){view=v;render();window.scrollTo({top:0});}

// ======== графика ========
function ring(score,col,size=48){const r=size/2-4,C=2*Math.PI*r;
  return `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}"><circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="#eef0f4" stroke-width="5"/><circle cx="${size/2}" cy="${size/2}" r="${r}" fill="none" stroke="${col}" stroke-width="5" stroke-linecap="round" stroke-dasharray="${C*score/10} ${C}" transform="rotate(-90 ${size/2} ${size/2})"/><text x="${size/2}" y="${size/2+5}" text-anchor="middle" style="font:700 ${size*.32}px var(--mono);fill:var(--text)">${score}</text></svg>`;}
function spark(vals,w=78,h=22){if(!vals||!vals.length)return'';const p=2,mn=Math.min(...vals),mx=Math.max(...vals),rng=(mx-mn)||1;const pts=vals.map((v,i)=>[p+i*(w-2*p)/(vals.length-1),h-p-((v-mn)/rng)*(h-2*p)]);return `<svg width="${w}" height="${h}"><polyline fill="none" stroke="#5cb585" stroke-width="1.6" points="${pts.map(p=>p.join(',')).join(' ')}"/><circle cx="${pts.at(-1)[0]}" cy="${pts.at(-1)[1]}" r="2.2" fill="#1e9e57"/></svg>`;}
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const hasFire=s=>(s.tasks||[]).some(t=>t.b==='fire');
const dbadge=t=>`<span class="badge ${t.b||'idle'}">${esc(t.d)||({fire:'горит',soon:'скоро',ok:'идёт',idle:'открыто'})[t.b]}</span>`;

// ======== навбар ========
function navbar(){
  document.getElementById('navin').innerHTML=
    `<div class="nb home ${view==='overview'?'on':''}" data-go="overview">⬚ обзор</div>`+
    DB.map(s=>`<div class="nb ${view===s.id?'on':''}" data-go="${s.id}"><span class="nd" style="background:${s.col}"></span>${s.ic} ${esc(s.name.split(' ')[0])} <span class="ns">${s.score}</span>${hasFire(s)?'<span class="fire"></span>':''}</div>`).join('')+
    `<div class="nb reset" id="resetbtn">↺ сброс</div>`;
  document.querySelectorAll('#navin [data-go]').forEach(b=>b.onclick=()=>go(b.dataset.go));
  document.getElementById('resetbtn').onclick=()=>{if(confirm('Сбросить к демо-данным?')){DB=structuredClone(SEED);save();go('overview');}};
}

// ======== блок-обёртка ========
const blk=(label,src,jump,inner,cls='')=>`<div class="card ${cls}"><div class="clbl">${label}<span class="src">· ${src}</span><span class="go" data-jump="${jump}">работать → ${jump}</span></div>${inner}</div>`;

// ======== страница сферы ========
function renderSphere(s){
  let blocks='';
  blocks+=blk('🧭 Путь к 10','Колесо','Колесо',
    `<div class="roadmap">${s.ms.map(m=>`<div class="rm ${m.done?'done':''} ${m.next?'next':''}"><span class="rk">${m.at}/10</span><span class="rt">${esc(m.t)}</span>${m.next?'<span class="badge soon">ты здесь</span>':(m.done?'<span style="color:var(--green-dim)">✓</span>':'')}</div>`).join('')}</div>`,'roadmap');

  if(s.tasks)blocks+=blk('🎯 Задачи и шаги','Цели','Цели',
    s.tasks.map((t,i)=>`<div class="row"><span class="cb ${t.done?'on':''}" data-chk="tasks:${i}">${t.done?'✓':''}</span><span class="tt ${t.done?'done':''}">${esc(t.t)}</span>${t.pct!=null?`<span class="pbar"><i style="width:${t.pct}%"></i></span><span class="pct">${t.pct}%</span>`:''}${dbadge(t)}</div>`).join('')+
    `<div class="add"><input data-add="task" placeholder="новая задача… (Enter)"><button class="plus" data-addbtn="task">＋</button></div>`);

  if(s.routines)blocks+=blk('↻ Рутины','Рутины','Рутины',
    s.routines.map((r,i)=>`<div class="row"><span class="cb ${r.done?'on':''}" data-chk="routines:${i}">${r.done?'✓':''}</span><span class="tt ${r.done?'done':''}">${esc(r.t)}<div class="wk">${(r.wk||[]).map(d=>`<i class="${d?'on':'miss'}"></i>`).join('')}</div></span><span class="strk">🔥 ${r.streak||0}</span></div>`).join(''));

  if(s.tracking)blocks+=blk('📊 Трекинг · 7 дней','Трекинг','Трекинг',
    s.tracking.map(m=>`<div class="metric"><span class="mn">${esc(m.n)}${m.tg?`<div class="tg">${esc(m.tg)}</div>`:''}</span>${spark(m.s)}<span class="mv">${esc(m.v)}<small>${esc(m.u)}</small></span></div>`).join(''));

  if(s.fin)blocks+=blk('💰 Финансы','Портфель / Финансы','Финансы',
    s.fin.map(f=>`<div class="row"><span class="tt">${esc(f.t)}${f.note?`<div class="s2">${esc(f.note)}</div>`:''}</span>${f.pct!=null?`<span class="pbar"><i style="width:${f.pct}%"></i></span>`:''}<span class="num">${esc(f.v)}</span></div>`).join(''));

  if(s.practices)blocks+=blk('🧠 Практики','Психология','Психология',
    s.practices.map((p,i)=>`<div class="row"><span class="cb ${p.done?'on':''}" data-chk="practices:${i}">${p.done?'✓':''}</span><span class="tt ${p.done?'done':''}">${esc(p.t)}<div class="wk">${(p.wk||[]).map(d=>`<i class="${d?'on':''}"></i>`).join('')}</div></span>${p.streak?`<span class="strk">🔥 ${p.streak}</span>`:''}</div>`).join(''));

  if(s.calendar)blocks+=blk('📅 Календарь','Календарь','Календарь',
    s.calendar.map(c=>`<div class="row"><span class="tt">${esc(c.t)}</span><span class="badge soon">${esc(c.d)}</span></div>`).join(''));
  if(s.people)blocks+=blk('☻ Люди','Люди','Люди',
    s.people.map(p=>`<div class="row"><span class="tt">${esc(p.t)}</span><span class="s2">${esc(p.d)}</span></div>`).join(''));
  if(s.info)blocks+=blk('📝 Инфо','связки на заметки','Инфо',
    s.info.map(([t,sn])=>`<span class="ilink">→ ${esc(t)}<span class="sn">${esc(sn)}</span></span>`).join(''));

  blocks+=blk('💭 Идеи и рассуждения','свободный текст цели','Цели',
    (s.ideas||[]).map(t=>`<div class="idea">${esc(t)}</div>`).join('')+
    `<div class="add"><input data-add="idea" placeholder="новая мысль… (Enter)"><button class="plus" data-addbtn="idea">＋</button></div>`);

  blocks+=blk('🪞 Ревизия','обновляет оценку сферы','Колесо',
    `<div class="review"><div class="scoreset" id="scoreset"></div><textarea data-refl placeholder="что в этой сфере, что подкрутить…">${esc(s.refl||'')}</textarea><span class="saved" id="reflsaved"></span></div>`);

  document.getElementById('page').innerHTML=`
    <div class="hero"><div class="htop">
      <div class="hscore">${ring(s.score,s.col,70)}<div class="hist">${spark(s.hist,70,18)}</div></div>
      <div class="info"><span class="typ">сфера · ${s.type}</span><h1>${s.ic} ${esc(s.name)}</h1>
        <div class="dest" data-edit="dest">🎯 <b>10 = ${esc(s.dest)}</b></div></div></div>
      <div class="track"><div class="rail"></div><div class="fill" style="width:${s.score*10}%"></div>
        ${s.ms.map(m=>`<div class="tick ${m.done?'done':''} ${m.next?'next':''}" style="left:${m.at*10}%"></div>`).join('')}
        <div class="you" style="left:${s.score*10}%">${s.score}</div><div class="z">0</div><div class="t10">10 ✦</div></div>
      <div class="calc">где сейчас: ${s.calc}</div>
      <div class="step"><div class="nx"><span class="l">СЛЕДУЮЩИЙ ШАГ</span><b data-edit="next">${esc(s.next)}</b></div>
        <div><span class="l">ЧТО ДЛЯ НЕГО НАДО</span><ul>${s.forStep.map(f=>`<li>${esc(f)}</li>`).join('')}</ul></div></div>
    </div>
    <div class="blocks">${blocks}</div>
    <div class="foot">Видишь данные тут — действуешь в разделах (ссылка «работать →», в v0.1 заглушка). Оценка/задачи/идеи правятся и сохраняются.</div>`;

  bindSphere(s);
}

function bindSphere(s){
  // галочки задач/рутин/практик
  document.querySelectorAll('[data-chk]').forEach(c=>c.onclick=()=>{
    const [arr,i]=c.dataset.chk.split(':');const it=s[arr][+i];
    it.done=!it.done;
    if(arr==='routines'||arr==='practices')it.streak=(it.streak||0)+(it.done?1:-1);
    save();renderSphere(s);});
  // добавить задачу/идею
  document.querySelectorAll('[data-add]').forEach(inp=>{
    const kind=inp.dataset.add;
    const commit=()=>{const v=inp.value.trim();if(!v)return;
      if(kind==='task')(s.tasks||(s.tasks=[])).push({t:v,b:'idle'});
      else (s.ideas||(s.ideas=[])).push(v);
      save();renderSphere(s);};
    inp.addEventListener('keydown',e=>{if(e.key==='Enter')commit();});});
  document.querySelectorAll('[data-addbtn]').forEach(btn=>btn.onclick=()=>{
    const inp=document.querySelector(`[data-add="${btn.dataset.addbtn}"]`);if(inp&&inp.value.trim()){
      const v=inp.value.trim();if(btn.dataset.addbtn==='task')(s.tasks||(s.tasks=[])).push({t:v,b:'idle'});else (s.ideas||(s.ideas=[])).push(v);save();renderSphere(s);}});
  // редактирование текста (цель/шаг)
  document.querySelectorAll('[data-edit]').forEach(el=>el.onclick=()=>{
    const f=el.dataset.edit;const cur=f==='dest'?s.dest:s.next;
    const v=prompt(f==='dest'?'Цель (10 = …):':'Следующий шаг:',cur);
    if(v!=null&&v.trim()){s[f]=v.trim();save();renderSphere(s);}});
  // ревизия: оценка
  const ss=document.getElementById('scoreset');let sc=s.score;
  ss.innerHTML=[1,2,3,4,5,6,7,8,9,10].map(i=>`<b class="${i<=sc?'on':''}" data-s="${i}">${i}</b>`).join('');
  ss.onclick=e=>{const b=e.target.closest('b');if(!b)return;sc=+b.dataset.s;s.score=sc;
    s.hist=[...(s.hist||[]).slice(-5),sc];save();renderSphere(s);};
  // ревизия: текст
  const ta=document.querySelector('[data-refl]');
  let tmr;ta.addEventListener('input',()=>{clearTimeout(tmr);tmr=setTimeout(()=>{s.refl=ta.value;save();
    const sv=document.getElementById('reflsaved');if(sv){sv.textContent='✓ сохранено';setTimeout(()=>sv.textContent='',1500);}},600);});
  // заглушки переходов
  document.querySelectorAll('[data-jump]').forEach(j=>j.onclick=()=>alert('v0.1: тут будет переход в раздел «'+j.dataset.jump+'» с реальными данными.'));
  document.querySelectorAll('.ilink').forEach(l=>l.onclick=()=>alert('v0.1: откроется заметка в Инфо.'));
}

// ======== обзор ========
function renderOverview(){
  const avg=(DB.reduce((a,s)=>a+s.score,0)/DB.length).toFixed(1),fires=DB.filter(hasFire).length;
  document.getElementById('page').innerHTML=`
    <h1>Сферы жизни</h1>
    <div class="muted" style="margin-bottom:2px">средний баланс <b style="color:var(--text)">${avg}/10</b> · 🔴 ${fires} требуют внимания · клик — полноэкранная страница сферы</div>
    <div class="ovcards">${DB.map(s=>`<div class="ov" data-go="${s.id}">
      <div class="ovt">${ring(s.score,s.col,40)}<div class="ovn">${s.ic} ${esc(s.name)}</div><div class="ovs" style="color:${s.col}">${s.score}</div></div>
      <div class="ovx">→ <b>${esc(s.next)}</b></div>
      <div class="ovbrief">${(s.tasks||[]).slice(0,3).map(t=>`<span class="ovtag">${({fire:'🔴',soon:'⏳',ok:'✓',idle:'•'})[t.b]||'•'} ${esc(t.t)}</span>`).join('')}</div>
    </div>`).join('')}</div>
    <div class="foot">v0.1 · данные в браузере (localStorage). Внутри сферы: путь к 10, задачи, рутины, трекинг, финансы, инфо, идеи, ревизия — правятся и сохраняются.</div>`;
  document.querySelectorAll('#page [data-go]').forEach(b=>b.onclick=()=>go(b.dataset.go));
}

function render(){navbar();view==='overview'?renderOverview():renderSphere(byId(view));}
render();
