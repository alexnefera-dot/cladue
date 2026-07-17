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
  return { pages, link, shingle };
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
    const ccPill = cc===undefined ? '<span class="muted">—</span>'
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
      ? `<span class="score-pill bg-ok">${p.brand}</span>`
      : `<span class="score-pill bg-warn">бренд не определён</span>`;

    return `<div class="panel">
      <h3>📄 ${pi+1}. ${p.name} ${brandBadge} <span class="pill">${p.url}</span></h3>
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
function renderRecommendations(data) {
  const recs = [];
  data.pages.forEach((p,i)=>{
    PARAM_SCHEMA.forEach(g=>g.params.forEach(param=>{
      const v=p.metrics[param.id]; if(v===undefined) return;
      const st=param.eval(v,p);
      if(st==='bad') recs.push({lvl:'bad', txt:`Стр. ${i+1} «${p.name}»: ${param.label} = ${v}${param.unit||''} (норма: ${param.norm})`});
    }));
  });
  const proj = data.project || computeProject(data);
  PROJECT_PARAMS.linking.concat(PROJECT_PARAMS.uniqueness).forEach(p=>{
    if(p.eval(proj[p.id])==='bad') recs.push({lvl:'bad', txt:`Проект: ${p.label} = ${proj[p.id]} (норма: ${p.norm})`});
  });
  const el = document.getElementById('recommendations');
  if(!recs.length){ el.innerHTML='<div class="rec ok">Критичных проблем не найдено 🎉</div>'; return; }
  el.innerHTML = `<p class="muted">Найдено проблем уровня «риск»: <b>${recs.length}</b></p>` +
    recs.map(r=>`<div class="rec ${r.lvl}">${r.txt}</div>`).join('');
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
  renderRecommendations(data);
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
  loadBrandsList();
  document.querySelectorAll('.tab').forEach(t=>t.addEventListener('click',()=>switchTab(t.dataset.view)));
  document.getElementById('btn-demo').addEventListener('click', ()=>{ loadData(demoData()); switchTab('results'); });
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
