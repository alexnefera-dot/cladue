/* ==========================================================================
   app.js — рендер шаблона из PARAM_SCHEMA + демо-данные на 7 страниц.
   В Фазе 3 функция loadData() будет получать реальный JSON от PHP-движка
   (POST формы -> analyze.php -> тот же формат данных). Рендер не меняется.
   ========================================================================== */

const PAGE_COUNT = 7;
// эндпоинты PHP-движка (Фаза 3). Пути относительно template/index.html
const ANALYZE_ENDPOINT = '../engine/analyze.php';
const BRANDS_ENDPOINT = '../engine/brands.php';
const statusText = { ok:'норма', warn:'внимание', bad:'риск' };

/* ---------- ДЕМО-ДАННЫЕ (в Фазе 3 заменяются ответом PHP) ------------------ */
function demoData() {
  const names = ['1win','vavada','1xbet','pinco','leon','arkada','kent'];
  const pages = names.map((name, i) => {
    // псевдо-детерминированный разброс, без Math.random (для стабильности)
    const j = i + 1;
    return {
      name: name+'.html', url: `/${name}.html`, brand: name, keyword: [name],
      metrics: {
        words_total: 1800 - i*180, chars_no_spaces: 11000 - i*1200,
        words_unique_ratio: 62 - i*3, sentences_total: 120 - i*10,
        sentence_avg_len: 14 + (i%3)*4, paragraphs_total: 24 - i,
        paragraph_long_count: i%4,
        nausea_classic: 5.6 + i*0.5, nausea_academic: 7 + i*0.6,
        keyword_density_max: 2.4 + i*0.5,
        water_percent: 22 + i*2, stopword_count: 340 - i*20, filler_phrases: i%5,
        zipf_score: 82 - i*4,
        flesch_reading_ease: 64 - i*4, flesch_kincaid_grade: 8 + (i%3),
        gunning_fog: 11 + i, readability_avg: 63 - i*3,
        clicks_coverage: 72 - i*7, query_coverage: 14 - i,
        queries_found: 240 - i*25, queries_total: 1890 - i*10,
        top_in_title: i!==6, top_in_h1: i!==4, top_in_first_para: i!==3,
        h1_count: i===2 ? 2 : 1, h1_title_diff: i!==5, h2_count: 4 - (i%3),
        heading_hierarchy: i!==1,
        title_present: true, title_len: 58 - i*3, desc_present: i!==6,
        desc_len: 145 - i*8, title_duplicate: i===5,
        text_html_ratio: 18 - i, img_count: 5 - (i%4), img_alt_filled: 100 - i*8,
        schema_present: i<4, lang_attr: true, viewport_meta: true,
        list_count: 3 - (i%3), strong_count: 8 + i*2, strong_kw_spam: i===2,
        media_richness: 5 - (i%4),
        double_spaces: i%3, typo_quotes: i%4, caps_abuse: i%2,
      },
      wordFreq: [[name,18-i],['казино',14],['зеркало',12],['вход',9],['сайт',8],
                 ['официальный',7],['бонус',6],['игра',5],['ставка',4],['онлайн',3]],
      missingQueries: [{q:name+' скачать',clicks:143001-i*9000},{q:'промокод '+name,clicks:120587-i*8000},
                       {q:name+' бонус',clicks:99021-i*7000},{q:name+' регистрация',clicks:88130-i*6000}],
      foundQueries: [{q:name,clicks:453041-i*20000},{q:name+' официальный сайт',clicks:119273-i*8000}],
    };
  });

  // матрица перелинковки 7x7 (1 = ссылка есть)
  const link = [
    [0,1,1,1,1,0,1],
    [1,0,1,0,0,0,1],
    [1,1,0,0,0,0,1],
    [1,0,0,0,1,1,1],
    [1,1,1,0,0,1,1],
    [1,0,0,1,1,0,1],
    [0,0,0,0,0,0,0], // Контакты — тупик (нет исходящих) для демонстрации флага
  ];
  // матрица схожести (шинглы) 7x7, % совпадения
  const shingle = [
    [100,8,7,5,4,6,3],
    [8,100,34,4,3,5,2],   // Услуга А / Услуга Б — высокая схожесть (демо-флаг дублей)
    [7,34,100,3,4,5,2],
    [5,4,3,100,6,7,3],
    [4,3,4,6,100,9,2],
    [6,5,5,7,9,100,3],
    [3,2,2,3,2,3,100],
  ];
  const orientation = {
    brand:   {label:'Брендовые',            share:38.0, clicks:1250000},
    access:  {label:'Доступ / зеркало',     share:29.0, clicks:960000},
    official:{label:'Офиц. сайт',           share:14.0, clicks:460000},
    games:   {label:'Игры / казино',        share:8.0,  clicks:260000},
    bonus:   {label:'Бонусы / промокоды',   share:5.0,  clicks:165000},
    app:     {label:'Приложение / скачать', share:4.0,  clicks:130000},
    registr: {label:'Регистрация / кабинет',share:2.0,  clicks:66000},
  };
  const stylistics = {
    pages: 7, first_person_share: 86, you_address_share: 90, faq_share: 100, date_fresh_share: 100,
    avg_numbers_100w: 2.3, avg_adj_pct: 9.1, avg_imperatives: 6, avg_faq_questions: 9,
    entities: {'Вейджер':6,'Провайдеры':4,'KYC/AML':4,'Лицензия':3,'2FA':3,'Крипта':3,'RTP':2,'Поддержка 24/7':2},
    foreign_brands: {},
  };
  pages.forEach((p,i)=>{ p.stylistics = {
    style_class: i===0?'личный опыт (E-E-A-T)':'рекламно-инструктивный',
    address: i%2? 'вы':'личный опыт', first_person: 8-i, second_person: 3, imperatives: 6+(i%3),
    numbers_per_100w: 2+(i%3), adj_pct: 9, emoji: 12-i, date_freshness:true,
    faq_present:true, faq_questions: 9-(i%3), entities_count: 12-i, foreign_brands: [] }; });
  return { pages, link, shingle, orientation, stylistics, orientationSource:'pages' };
}

/* ---------- вычисление сводных баллов ------------------------------------- */
function pageScore(page) {
  const flatEval = {};
  PARAM_SCHEMA.forEach(g => g.params.forEach(p => {
    const v = page.metrics[p.id];
    flatEval[p.id] = (v===undefined) ? null : p.eval(v, page);
  }));
  const scoreOf = ids => {
    const vals = ids.map(id => flatEval[id]).filter(s => s!==null && s!==undefined);
    if (!vals.length) return null;
    const pts = vals.reduce((a,s)=> a + (s==='ok'?100:s==='warn'?55:10), 0);
    return Math.round(pts / vals.length);
  };
  return {
    seo: scoreOf(SCORE_WEIGHTS.seo),
    spam: scoreOf(SCORE_WEIGHTS.spam),
    readability: scoreOf(SCORE_WEIGHTS.readability),
    structure: scoreOf(SCORE_WEIGHTS.structure),
    total: scoreOf([].concat(...Object.values(SCORE_WEIGHTS))),
  };
}
const scoreColor = s => s>=75 ? 'bg-ok' : s>=50 ? 'bg-warn' : 'bg-bad';

/* ---------- рендер: форма загрузки ---------------------------------------- */
function renderForm() {
  const el = document.getElementById('pages-grid');
  let html = '';
  for (let i=1;i<=PAGE_COUNT;i++){
    html += `
    <div class="page-card">
      <h4><span class="num">${i}</span> Страница ${i}</h4>
      <label>Название / URL страницы</label>
      <input type="text" name="name_${i}" placeholder="напр. Услуга А  ·  /uslugi/a.html">
      <label>Файл (HTML / DOCX)</label>
      <input type="file" name="file_${i}" accept=".html,.htm,.docx,.doc">
      <label>…или вставить контент (HTML/текст)</label>
      <textarea name="content_${i}" placeholder="Вставьте HTML или текст страницы"></textarea>
      <label>Бренд <span class="muted">(необязательно — по умолчанию определяется автоматически)</span></label>
      <input type="text" name="brand_${i}" list="brands-list" placeholder="авто-определение по контенту">
    </div>`;
  }
  el.innerHTML = html;
}

/* ---------- рендер: сводная таблица (scoreboard) -------------------------- */
function renderScoreboard(data) {
  const scores = data.pages.map(pageScore);
  let rows = data.pages.map((p,i)=>{
    const s = scores[i];
    const pill = (v)=> v===null ? '<span class="muted">—</span>'
      : `<span class="score-pill ${scoreColor(v)}">${v}</span>`;
    const cc = p.metrics.clicks_coverage;
    const outBase = p.brand && p.inBase===false;
    const ccPill = outBase ? '<span class="muted" title="бренд вне базы">н/д</span>'
      : cc===undefined ? '<span class="muted">—</span>'
      : `<span class="score-pill ${scoreColor(cc)}">${cc}%</span>`;
    return `<tr>
      <td>${i+1}</td>
      <td><b>${p.name}</b><br><span class="muted" style="font-size:12px">${p.brand||'—'}</span></td>
      <td>${p.metrics.words_total}</td>
      <td>${ccPill}</td>
      <td>${pill(s.seo)}</td>
      <td>${pill(s.spam)}</td>
      <td>${pill(s.readability)}</td>
      <td>${pill(s.structure)}</td>
      <td>${pill(s.total)}</td>
    </tr>`;
  }).join('');
  document.getElementById('scoreboard').innerHTML = `
    <table>
      <thead><tr>
        <th>#</th><th>Страница / бренд</th><th>Слов</th><th>Клики</th>
        <th>SEO</th><th>Антиспам</th><th>Читаемость</th><th>Структура</th><th>Итого</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <div class="legend">
      <span><span class="dot ok"></span> 75–100 норма</span>
      <span><span class="dot warn"></span> 50–74 внимание</span>
      <span><span class="dot bad"></span> 0–49 риск</span>
      <span class="muted">Антиспам: выше балл = ниже риск Баден-Баден</span>
    </div>`;
}

/* ---------- рендер: детальные карточки по страницам ----------------------- */
function renderDetails(data) {
  const wrap = document.getElementById('details');
  wrap.innerHTML = data.pages.map((p,pi)=>{
    const cats = PARAM_SCHEMA.map(g=>{
      const rows = g.params.map(param=>{
        const v = p.metrics[param.id];
        if (v===undefined) return '';
        const st = param.eval(v,p);
        const dot = st ? `<span class="dot ${st}"></span>` : '<span class="dot" style="background:#3a4560"></span>';
        let disp = v;
        if (param.bool) disp = v ? (param.invert?'да ⚠':'да') : (param.invert?'нет':'нет');
        else disp = `${v}${param.unit||''}`;
        return `<div class="p-row">
          ${dot}
          <span class="p-label">${param.label}</span>
          <span class="p-norm">норма: ${param.norm}</span>
          <span class="p-val ${st?('txt-'+st):''}">${disp}</span>
        </div>`;
      }).join('');
      return `<div class="cat">
        <div class="cat-head" onclick="this.nextElementSibling.classList.toggle('hidden')">
          <span>${g.icon}</span> ${g.cat}
        </div>
        <div class="cat-body">${rows}</div>
      </div>`;
    }).join('');
    // топ частотных слов
    const maxFreq = Math.max(...p.wordFreq.map(w=>w[1]));
    const bars = p.wordFreq.map(([w,c])=>`
      <div class="bar-row"><span>${w}</span>
        <div class="bar-track"><div class="bar-fill" style="width:${Math.round(c/maxFreq*100)}%"></div></div>
        <span>${c}</span></div>`).join('');

    // упущенные запросы (готовые рекомендации по трафику)
    const fmt = n => n>=1000 ? Math.round(n/1000)+'k' : n;
    const missing = (p.missingQueries||[]).map(m=>`
      <div class="bar-row" style="grid-template-columns:1fr 60px">
        <span>${m.q}</span><span class="txt-bad">${fmt(m.clicks)}</span></div>`).join('')
      || '<p class="muted">Нет данных (бренд не определён).</p>';

    const brandBadge = p.brand
      ? (p.inBase===false
          ? `<span class="score-pill bg-warn" title="нет в базе запросов — покрытие не считается">${p.brand} · вне базы</span>`
          : `<span class="score-pill bg-ok">${p.brand}</span>`)
      : `<span class="score-pill bg-warn">бренд не определён</span>`;

    const st = p.stylistics;
    const styLine = st ? `<div class="row" style="gap:6px;flex-wrap:wrap;margin:2px 0 12px">
        <span class="pill">${st.style_class||'—'}</span>
        <span class="pill">обращение: ${st.address||'—'}</span>
        <span class="pill">1-е лицо: ${st.first_person}</span>
        <span class="pill">императивы: ${st.imperatives}</span>
        <span class="pill">числа/100: ${st.numbers_per_100w}</span>
        <span class="pill">FAQ: ${st.faq_questions} вопр.</span>
        <span class="pill">сущностей: ${st.entities_count}</span>
        ${st.date_freshness?'<span class="pill">📅 дата</span>':''}
        ${(st.foreign_brands&&st.foreign_brands.length)?`<span class="pill" style="color:var(--bad)">⚠ чужой бренд</span>`:''}
      </div>` : '';

    return `<div class="panel">
      <h3>📄 ${pi+1}. ${p.name} ${brandBadge} <span class="pill">${p.url}</span></h3>
      ${styLine}
      <div class="grid cols-2">
        <div>${cats}</div>
        <div>
          <h4>🚀 Упущенные запросы <span class="muted">(по кликам/мес — что добавить)</span></h4>
          <div class="bars">${missing}</div>
          <h4 style="margin-top:16px">ТОП частотных слов</h4>
          <div class="bars">${bars}</div>
        </div>
      </div>
    </div>`;
  }).join('');
}

/* ---------- рендер: матрицы 7x7 ------------------------------------------- */
function renderMatrix(elId, matrix, names, mode) {
  const head = '<th></th>' + names.map((n,i)=>`<th title="${n}">${i+1}</th>`).join('');
  const rows = matrix.map((row,i)=>{
    const cells = row.map((val,j)=>{
      if (i===j) return `<td style="color:#586074">—</td>`;
      let cls='', txt=val;
      if (mode==='link'){ cls = val? 'bg-ok':''; txt = val?'●':''; }
      else { // shingle similarity
        cls = val>=30?'bg-bad': val>=15?'bg-warn':'bg-ok'; txt = val+'%';
      }
      return `<td class="cell ${cls}">${txt}</td>`;
    }).join('');
    return `<tr><th title="${names[i]}">${i+1}. ${names[i]}</th>${cells}</tr>`;
  }).join('');
  document.getElementById(elId).innerHTML =
    `<table class="matrix"><thead><tr>${head}</tr></thead><tbody>${rows}</tbody></table>`;
}

/* ---------- рендер: проектные метрики перелинковки/уникальности ----------- */
function computeProject(data) {
  const N = data.pages.length;
  const incoming = Array(N).fill(0), outgoing = Array(N).fill(0);
  data.link.forEach((row,i)=>row.forEach((v,j)=>{ if(i!==j&&v){ outgoing[i]++; incoming[j]++; }}));
  const orphan = incoming.filter(x=>x===0).length;
  const deadend = outgoing.filter(x=>x===0).length;
  const avgLinks = (outgoing.reduce((a,b)=>a+b,0)/N);
  // мин. уникальность = 100 - макс. схожесть (вне диагонали)
  let maxSim = 0, dupPara = 0;
  data.shingle.forEach((row,i)=>row.forEach((v,j)=>{ if(i!==j){ maxSim=Math.max(maxSim,v); if(v>=30)dupPara++; }}));
  const minUniq = 100 - maxSim;
  return { orphan_pages:orphan, dead_end_pages:deadend, avg_internal_links:+avgLinks.toFixed(1),
           max_link_depth: 2, anchor_diversity: 72,
           internal_uniqueness: minUniq, dup_paragraphs: Math.round(dupPara/2) };
}

function renderProject(data) {
  // PHP-движок присылает готовый data.project; иначе считаем из матриц
  const vals = data.project || computeProject(data);
  const block = (title, list) => {
    const rows = list.map(p=>{
      const v = vals[p.id]; const st = p.eval(v);
      return `<div class="p-row">
        <span class="dot ${st}"></span>
        <span class="p-label">${p.label}</span>
        <span class="p-norm">норма: ${p.norm}</span>
        <span class="p-val txt-${st}">${v}</span></div>`;
    }).join('');
    return `<div class="panel"><h3>${title}</h3>${rows}</div>`;
  };
  document.getElementById('project-metrics').innerHTML =
    block('🔗 Перелинковка проекта', PROJECT_PARAMS.linking) +
    block('🧬 Внутренняя уникальность', PROJECT_PARAMS.uniqueness);
}

/* ---------- рендер: рекомендации ------------------------------------------ */
// профиль ориентации: горизонтальные полосы долей по интентам
function orientationBars(orientation) {
  const themes = Object.values(orientation||{});
  if (!themes.length) return '<p class="muted">Нет данных (бренд не определён).</p>';
  const max = Math.max(...themes.map(t=>t.share), 1);
  const fmt = n => n>=1000 ? Math.round(n/1000)+'k' : n;
  return `<div class="bars">` + themes.map(t=>`
    <div class="bar-row" style="grid-template-columns:170px 1fr 92px">
      <span>${t.label}</span>
      <div class="bar-track"><div class="bar-fill" style="width:${Math.round(t.share/max*100)}%"></div></div>
      <span>${t.share}% · ${fmt(t.clicks)}</span>
    </div>`).join('') + `</div>`;
}

function renderOrientation(data) {
  const el = document.getElementById('orientation');
  if (!el) return;
  const note = data.orientationSource==='pages'
    ? 'Бренд(ы) вне базы — ориентация посчитана по интентам страниц (взвешено объёмом текста).'
    : 'Распределение кликов покрытых запросов базы по смысловым кластерам.';
  el.innerHTML = `<p class="muted">На что ориентирован набор. ${note}</p>` + orientationBars(data.orientation);
}

// шкала доли 0–100% строкой
function shareRow(label, val, unit='%') {
  return `<div class="bar-row" style="grid-template-columns:200px 1fr 54px">
    <span>${label}</span>
    <div class="bar-track"><div class="bar-fill" style="width:${Math.min(100,val)}%"></div></div>
    <span>${val}${unit}</span></div>`;
}

function renderStylistics(data) {
  const el = document.getElementById('stylistics');
  if (!el) return;
  const s = data.stylistics;
  if (!s) { el.innerHTML = '<p class="muted">Нет данных стилистики.</p>'; return; }
  const shares = `<div class="bars">`
    + shareRow('Первое лицо / «мой опыт»', s.first_person_share)
    + shareRow('Обращение «вы»', s.you_address_share)
    + shareRow('FAQ на странице', s.faq_share)
    + shareRow('Дата-стамп / свежесть', s.date_fresh_share)
    + `</div>`;
  const avgs = `<div class="row" style="margin-top:12px;gap:14px;flex-wrap:wrap">
    <span class="pill">чисел/100 слов: <b>${s.avg_numbers_100w}</b></span>
    <span class="pill">прилагательных: <b>${s.avg_adj_pct}%</b></span>
    <span class="pill">императивов/стр: <b>${s.avg_imperatives}</b></span>
    <span class="pill">вопросов FAQ/стр: <b>${s.avg_faq_questions}</b></span></div>`;
  const ents = Object.keys(s.entities||{});
  const entHtml = ents.length
    ? `<h4 style="margin:16px 0 6px">Фактура / сущности (страниц с фактом)</h4>
       <div class="row" style="gap:6px;flex-wrap:wrap">`
       + ents.map(e=>`<span class="pill">${e} · ${s.entities[e]}</span>`).join('') + `</div>`
    : '';
  const foreign = Object.keys(s.foreign_brands||{});
  const foreignHtml = foreign.length
    ? `<div class="rec bad" style="margin-top:14px">⚠ Чужие бренды в тексте (остаток шаблона): <b>${foreign.join(', ')}</b></div>`
    : `<div class="rec ok" style="margin-top:14px">Чужих брендов не найдено — генерация чистая.</div>`;
  el.innerHTML = `<p class="muted">Как написан набор: тон, обращение, обязательные блоки и фактура. Доли — по страницам набора.</p>`
    + shares + avgs + entHtml + foreignHtml;
}

/* ========================================================================== */
/*  РЕЖИМ СРАВНЕНИЯ КОНКУРЕНТОВ (набор A vs набор B)                           */
/* ========================================================================== */

const COMPARE_ENDPOINT = '../engine/compare.php';

// метрики для таблицы «рядом»; dir: up = больше лучше, down = меньше лучше, bool
const COMPARE_METRICS = [
  {id:'clicks_coverage',    label:'Покрытие по кликам',  unit:'%', dir:'up'},
  {id:'query_coverage',     label:'Покрытие запросов',   unit:'%', dir:'up'},
  {id:'queries_found',      label:'Найдено запросов',    unit:'',  dir:'up'},
  {id:'words_total',        label:'Объём (слов)',        unit:'',  dir:'up'},
  {id:'nausea_academic',    label:'Академ. тошнота',     unit:'%', dir:'down'},
  {id:'water_percent',      label:'Водность',            unit:'%', dir:'down'},
  {id:'keyword_density_max',label:'Плотность гл. ключа', unit:'%', dir:'down'},
  {id:'flesch_reading_ease',label:'Читаемость (Флеш)',   unit:'',  dir:'up'},
  {id:'h2_count',           label:'Подзаголовков H2',    unit:'',  dir:'up'},
  {id:'img_alt_filled',     label:'Alt заполнен',        unit:'%', dir:'up'},
  {id:'top_in_title',       label:'Гл. запрос в Title',  unit:'',  dir:'bool'},
];

// -1 = выигрывает A, 1 = B, 0 = ничья
function cmpWinner(a, b, dir) {
  if (a===undefined || b===undefined) return 0;
  if (dir==='bool') return a===b ? 0 : (a ? -1 : 1);
  if (a===b) return 0;
  return dir==='up' ? (a>b?-1:1) : (a<b?-1:1);
}

function renderCompareForm() {
  const ccard = (prefix, i) => `
    <div class="page-card">
      <h4><span class="num">${i}</span> ${prefix==='a_'?'A':'B'} · Страница ${i}</h4>
      <label>Название / URL</label>
      <input type="text" name="${prefix}name_${i}" placeholder="напр. /1win.html">
      <label>Файл (HTML/DOCX)</label>
      <input type="file" name="${prefix}file_${i}" accept=".html,.htm,.docx,.doc">
      <label>…или вставить контент</label>
      <textarea name="${prefix}content_${i}" placeholder="HTML или текст"></textarea>
      <label>Бренд <span class="muted">(необязательно, авто)</span></label>
      <input type="text" name="${prefix}brand_${i}" list="brands-list" placeholder="авто">
    </div>`;
  const grid = pfx => Array.from({length:PAGE_COUNT}, (_,k)=>ccard(pfx,k+1)).join('');
  document.getElementById('setA-grid').innerHTML = `<div class="pages-grid">${grid('a_')}</div>`;
  document.getElementById('setB-grid').innerHTML = `<div class="pages-grid">${grid('b_')}</div>`;
}

// таблица метрик «рядом» для пары страниц
function compareMetricTable(ma, mb) {
  const arrow = w => w===0 ? '<span class="muted">=</span>'
    : w<0 ? '<span class="txt-ok">◀ A</span>' : '<span class="txt-ok">B ▶</span>';
  const cell = (v, param) => v===undefined ? '—'
    : (param.dir==='bool' ? (v?'да':'нет') : `${v}${param.unit}`);
  const rows = COMPARE_METRICS.map(p=>{
    const a=ma[p.id], b=mb[p.id], w=cmpWinner(a,b,p.dir);
    let delta='';
    if(p.dir!=='bool' && a!==undefined && b!==undefined){
      const d=Math.round((b-a)*10)/10; delta = (d>0?'+':'')+d+p.unit;
    }
    return `<tr>
      <td>${p.label}</td>
      <td class="${w<0?'txt-ok':''}" style="text-align:right;font-weight:700">${cell(a,p)}</td>
      <td class="${w>0?'txt-ok':''}" style="text-align:right;font-weight:700">${cell(b,p)}</td>
      <td style="text-align:right" class="muted">${delta}</td>
      <td style="text-align:center">${arrow(w)}</td>
    </tr>`;
  }).join('');
  return `<table>
    <thead><tr><th>Метрика</th><th style="text-align:right">A (ты)</th>
      <th style="text-align:right">B (конкурент)</th><th style="text-align:right">Δ (B−A)</th><th>Лучше</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
}

// стилистика A vs B рядом (по страницам пары)
const STY_ROWS = [
  {id:'style_class', label:'Стиль'},
  {id:'address', label:'Обращение'},
  {id:'first_person', label:'Первое лицо', dir:'up'},
  {id:'imperatives', label:'Императивы', dir:'up'},
  {id:'numbers_per_100w', label:'Числа/100 слов', dir:'up'},
  {id:'faq_questions', label:'FAQ (вопросов)', dir:'up'},
  {id:'entities_count', label:'Сущностей', dir:'up'},
  {id:'emoji', label:'Эмодзи', dir:'up'},
];
function styCompare(sa, sb) {
  if (!sa || !sb) return '<p class="muted">Нет данных стилистики.</p>';
  const arrow = w => w===0 ? '<span class="muted">=</span>'
    : w<0 ? '<span class="txt-ok">◀ A</span>' : '<span class="txt-ok">B ▶</span>';
  const rows = STY_ROWS.map(r=>{
    const a=sa[r.id], b=sb[r.id];
    let w=0;
    if(r.dir && typeof a==='number' && typeof b==='number') w = a===b?0:(a>b?-1:1);
    return `<tr><td>${r.label}</td>
      <td class="${w<0?'txt-ok':''}" style="text-align:right;font-weight:600">${a}</td>
      <td class="${w>0?'txt-ok':''}" style="text-align:right;font-weight:600">${b}</td>
      <td style="text-align:center">${r.dir?arrow(w):''}</td></tr>`;
  }).join('');
  const fa = (sa.foreign_brands||[]).length, fb = (sb.foreign_brands||[]).length;
  const foreign = `<tr><td>Чужие бренды</td>
    <td class="${fa?'txt-bad':'txt-ok'}" style="text-align:right">${fa||'нет'}</td>
    <td class="${fb?'txt-bad':'txt-ok'}" style="text-align:right">${fb||'нет'}</td><td></td></tr>`;
  return `<table><thead><tr><th>Стиль-метрика</th><th style="text-align:right">A</th>
    <th style="text-align:right">B</th><th>Лучше</th></tr></thead><tbody>${rows}${foreign}</tbody></table>`;
}

function gapList(gap, cls) {
  const fmt = n => n>=1000 ? Math.round(n/1000)+'k' : n;
  if(!gap || !gap.length) return '<p class="muted">Разрыва нет.</p>';
  return `<div class="bars">` + gap.slice(0,12).map(g=>`
    <div class="bar-row" style="grid-template-columns:1fr 64px">
      <span>${g.q}</span><span class="${cls}">${fmt(g.clicks)}</span></div>`).join('') + `</div>`;
}

function renderCompare(res) {
  document.getElementById('compare-empty').classList.add('hidden');
  const box = document.getElementById('compare-results');
  box.classList.remove('hidden');

  // 1) ориентация наборов рядом
  let html = `<div class="panel"><h3>🎯 На что ориентированы наборы</h3>
    <div class="grid cols-2">
      <div><h4 style="color:var(--accent-2)">A · Ты</h4>${orientationBars(res.a.orientation)}</div>
      <div><h4 style="color:var(--accent)">B · Конкурент</h4>${orientationBars(res.b.orientation)}</div>
    </div></div>`;

  // 2) пары по брендам
  if(!res.pairs.length){
    html += `<div class="panel empty">Общих брендов у наборов не найдено — сравнивать попарно нечего. Проверьте, что страницы про одни и те же бренды.</div>`;
  }
  const pairWord = res.pairedBy==='page' ? 'Страница' : 'Бренд';
  res.pairs.forEach(pair=>{
    const pa = res.a.pages[pair.aIndex], pb = res.b.pages[pair.bIndex];
    const gaps = (pair.gapBnotA.length || pair.gapAnotB.length)
      ? `<div class="grid cols-2" style="margin-top:14px">
          <div><h4>🚀 Закрывает конкурент (B), а ты нет</h4>${gapList(pair.gapBnotA,'txt-bad')}</div>
          <div><h4>✅ Закрываешь ты (A), а конкурент нет</h4>${gapList(pair.gapAnotB,'txt-ok')}</div>
        </div>` : '';
    html += `<div class="panel">
      <h3>⚔️ ${pairWord}: ${pair.brand}
        <span class="pill">A: ${pa.name}${pa.brand?' · '+pa.brand:''}</span>
        <span class="pill">B: ${pb.name}${pb.brand?' · '+pb.brand:''}</span></h3>
      ${compareMetricTable(pa.metrics, pb.metrics)}
      <h4 style="margin:16px 0 6px">✍️ Стилистика рядом</h4>
      ${styCompare(pa.stylistics, pb.stylistics)}
      ${gaps}
    </div>`;
  });

  // 3) непарные бренды
  if((res.onlyA&&res.onlyA.length)||(res.onlyB&&res.onlyB.length)){
    html += `<div class="panel"><h3>Бренды без пары</h3>
      <p>Только у тебя (A): <b>${res.onlyA.join(', ')||'—'}</b></p>
      <p>Только у конкурента (B): <b>${res.onlyB.join(', ')||'—'}</b></p></div>`;
  }
  box.innerHTML = html;
}

function demoCompare() {
  const d = demoData();
  const sty = (fp,num,faq,ent)=>({style_class:fp>=3?'личный опыт (E-E-A-T)':'рекламно-инструктивный',
    address:fp>=3?'личный опыт':'вы', first_person:fp, second_person:4, imperatives:12,
    numbers_per_100w:num, faq_questions:faq, entities_count:ent, emoji:20, date_freshness:true, foreign_brands:[]});
  const mk = (cov,st)=>({name:'1win.html', brand:'1win', stylistics:st, metrics:{
    clicks_coverage:cov, query_coverage:cov/5, queries_found:Math.round(cov*4),
    words_total:1500+cov*5, nausea_academic:8, water_percent:24, keyword_density_max:2.6,
    flesch_reading_ease:60, h2_count:3, img_alt_filled:90, top_in_title:true }});
  return {
    pairedBy:'brand',
    a:{pages:[mk(60,sty(8,6,9,13))], orientation:d.orientation},
    b:{pages:[mk(76,sty(1,12,0,11))], orientation:{
      brand:{label:'Брендовые',share:34,clicks:1100000}, access:{label:'Доступ / зеркало',share:28,clicks:900000},
      bonus:{label:'Бонусы / промокоды',share:12,clicks:390000}, app:{label:'Приложение / скачать',share:10,clicks:320000},
      registr:{label:'Регистрация / кабинет',share:9,clicks:290000}, games:{label:'Игры / казино',share:7,clicks:230000}}},
    pairs:[{brand:'1win', aIndex:0, bIndex:0,
      gapBnotA:[{q:'1win casino',clicks:423448},{q:'1win регистрация',clicks:317347},{q:'1win скачать',clicks:143001},{q:'промокод 1win',clicks:120587}],
      gapAnotB:[{q:'1win зеркало сайта',clicks:45000}]}],
    onlyA:[], onlyB:['vavada']
  };
}

async function submitCompare(btn) {
  const form = document.getElementById('compare-form');
  const old = btn.textContent; btn.textContent='⏳ Сравнение…'; btn.disabled=true;
  try {
    const res = await fetch(COMPARE_ENDPOINT, {method:'POST', body:new FormData(form)});
    const json = await res.json();
    if(json.error) throw new Error(json.error);
    renderCompare(json);
  } catch(err) {
    alert('Не удалось сравнить: '+err.message+'\n\nЗапустите PHP-сервер (php -S localhost:8000) или нажмите «Демо-сравнение».');
  } finally { btn.textContent=old; btn.disabled=false; }
}

/* ---------- инициализация ------------------------------------------------- */
let CURRENT_DATA = null;
function loadData(data) {
  CURRENT_DATA = data;
  document.getElementById('results-empty').classList.add('hidden');
  document.getElementById('results-body').classList.remove('hidden');
  renderScoreboard(data);
  renderDetails(data);
  renderMatrix('matrix-link', data.link, data.pages.map(p=>p.name), 'link');
  renderMatrix('matrix-shingle', data.shingle, data.pages.map(p=>p.name), 'shingle');
  renderProject(data);
  renderOrientation(data);
  renderStylistics(data);
}

function switchTab(id) {
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active', t.dataset.view===id));
  document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active', v.id==='view-'+id));
}

async function loadBrandsList() {
  try {
    const res = await fetch(BRANDS_ENDPOINT);
    const brands = await res.json();
    const dl = document.getElementById('brands-list');
    dl.innerHTML = brands.map(b=>`<option value="${b.name}">${b.name} · ${b.queries} запр.</option>`).join('');
  } catch (e) { /* без сервера datalist просто пуст — не критично */ }
}

document.addEventListener('DOMContentLoaded', ()=>{
  renderForm();
  renderCompareForm();
  loadBrandsList();
  document.querySelectorAll('.tab').forEach(t=>t.addEventListener('click',()=>switchTab(t.dataset.view)));
  document.getElementById('btn-demo').addEventListener('click', ()=>{ loadData(demoData()); switchTab('results'); });
  document.getElementById('btn-compare-demo').addEventListener('click', ()=>{ renderCompare(demoCompare()); });
  document.getElementById('btn-compare').addEventListener('click', (e)=>{ e.preventDefault(); submitCompare(e.currentTarget); });
  document.getElementById('btn-analyze').addEventListener('click', async (e)=>{
    e.preventDefault();
    const form = document.getElementById('analyze-form');
    const btn = e.currentTarget;
    const old = btn.textContent;
    btn.textContent = '⏳ Анализ…'; btn.disabled = true;
    try {
      const res = await fetch(ANALYZE_ENDPOINT, { method:'POST', body: new FormData(form) });
      const json = await res.json();
      if (json.error) throw new Error(json.error);
      loadData(json); switchTab('results');
    } catch (err) {
      alert('Не удалось выполнить анализ: ' + err.message +
        '\n\nУбедитесь, что запущен локальный PHP:\n  php -S localhost:8000 -t .' +
        '\nи открыт http://localhost:8000/template/index.html' +
        '\n\nПока можно нажать «Показать демо-данные».');
    } finally {
      btn.textContent = old; btn.disabled = false;
    }
  });
});
