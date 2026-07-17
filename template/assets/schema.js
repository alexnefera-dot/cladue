/* ==========================================================================
   PARAM_SCHEMA — единый реестр параметров (соответствует docs/parameters.md).
   Форма ввода и блок результатов строятся из этого объекта.
   Каждый параметр: { id, label, unit, norm, eval, cat }
     norm  — человекочитаемая норма (строка)
     eval  — (v, page, project) => 'ok' | 'warn' | 'bad' | null
   Фаза 3 (PHP) отдаёт значения по этим же id — рендер не меняется.
   ========================================================================== */

// helpers для порогов
const between = (v, a, b) => v >= a && v <= b;
const band = (v, okMin, okMax, warnMin, warnMax) =>
  between(v, okMin, okMax) ? 'ok' : between(v, warnMin, warnMax) ? 'warn' : 'bad';
const maxBand = (v, ok, warn) => v <= ok ? 'ok' : v <= warn ? 'warn' : 'bad';
const minBand = (v, ok, warn) => v >= ok ? 'ok' : v >= warn ? 'warn' : 'bad';
const boolOk  = v => v ? 'ok' : 'bad';

const PARAM_SCHEMA = [
  { cat: 'Объём и базовые метрики', icon: '📏', params: [
    { id:'words_total',        label:'Всего слов',                unit:'',   norm:'300–3000+', eval:v=>minBand(v,300,150) },
    { id:'chars_no_spaces',    label:'Символов без пробелов',      unit:'',   norm:'≥ 2000',    eval:v=>minBand(v,2000,1000) },
    { id:'words_unique_ratio', label:'Доля уникальных слов',       unit:'%',  norm:'40–70%',    eval:v=>band(v,40,70,30,80) },
    { id:'sentences_total',    label:'Предложений',                unit:'',   norm:'—',         eval:()=>null },
    { id:'sentence_avg_len',   label:'Средняя длина предложения',  unit:'сл.',norm:'10–20',     eval:v=>band(v,10,20,7,28) },
    { id:'paragraphs_total',   label:'Абзацев',                    unit:'',   norm:'—',         eval:()=>null },
    { id:'paragraph_long_count',label:'Абзацев-«простыней» (>100 сл.)',unit:'',norm:'0',        eval:v=>maxBand(v,0,2) },
  ]},

  { cat: 'Тошнота и плотность (Баден-Баден)', icon: '🩺', params: [
    { id:'nausea_classic',  label:'Классическая тошнота',       unit:'',  norm:'< 7',    eval:v=>maxBand(v,7,9) },
    { id:'nausea_academic', label:'Академическая тошнота',      unit:'%', norm:'5–9%',   eval:v=>band(v,5,9,3,12) },
    { id:'keyword_density_max', label:'Макс. плотность ключа',  unit:'%', norm:'< 4%',   eval:v=>maxBand(v,3,4) },
    { id:'kw_exact_ratio',  label:'Доля точных вхождений',      unit:'%', norm:'< 30%',  eval:v=>maxBand(v,30,45) },
  ]},

  { cat: 'Водность', icon: '💧', params: [
    { id:'water_percent', label:'Водность',        unit:'%', norm:'15–30%', eval:v=>band(v,15,30,10,45) },
    { id:'stopword_count',label:'Стоп-слов',       unit:'',  norm:'—',      eval:()=>null },
    { id:'filler_phrases',label:'Речевых штампов',  unit:'',  norm:'минимум',eval:v=>maxBand(v,2,5) },
  ]},

  { cat: 'Естественность (Ципф / YATI)', icon: '📉', params: [
    { id:'zipf_score', label:'Соответствие закону Ципфа', unit:'%', norm:'> 70%', eval:v=>minBand(v,70,55) },
  ]},

  { cat: 'Читабельность', icon: '📖', params: [
    { id:'flesch_reading_ease', label:'Индекс Флеша',       unit:'',  norm:'60–70', eval:v=>band(v,55,75,40,90) },
    { id:'flesch_kincaid_grade',label:'Флеш-Кинкейд (класс)',unit:'', norm:'7–9',   eval:v=>band(v,6,10,4,13) },
    { id:'gunning_fog',         label:'Ганнинг (туманность)',unit:'', norm:'< 12',  eval:v=>maxBand(v,12,15) },
    { id:'readability_avg',     label:'Средний балл читаемости',unit:'',norm:'60–70',eval:v=>band(v,55,75,40,90) },
  ]},

  { cat: 'Ключи и семантика (LSI)', icon: '🎯', params: [
    { id:'kw_exact',     label:'Точных вхождений ключа', unit:'', norm:'1–3 / 1000 сл.', eval:v=>minBand(v,1,0.5) },
    { id:'kw_first_para',label:'Ключ в 1-м абзаце',      unit:'', norm:'да',  eval:boolOk, bool:true },
    { id:'kw_in_title',  label:'Ключ в Title',           unit:'', norm:'да',  eval:boolOk, bool:true },
    { id:'kw_in_h1',     label:'Ключ в H1',              unit:'', norm:'да',  eval:boolOk, bool:true },
    { id:'lsi_coverage', label:'Покрытие LSI-ядра',      unit:'%',norm:'> 60%',eval:v=>minBand(v,60,40) },
  ]},

  { cat: 'Заголовки и структура', icon: '🏷️', params: [
    { id:'h1_count',        label:'Количество H1',        unit:'', norm:'ровно 1', eval:v=>v===1?'ok':'bad' },
    { id:'h1_title_diff',   label:'H1 ≠ Title',           unit:'', norm:'да',      eval:boolOk, bool:true },
    { id:'h2_count',        label:'Количество H2',        unit:'', norm:'≥ 2',     eval:v=>minBand(v,2,1) },
    { id:'heading_hierarchy',label:'Иерархия без пропусков',unit:'',norm:'да',     eval:boolOk, bool:true },
  ]},

  { cat: 'Метатеги', icon: '🔖', params: [
    { id:'title_present', label:'Title заполнен',   unit:'', norm:'да',        eval:boolOk, bool:true },
    { id:'title_len',     label:'Длина Title',      unit:'симв.', norm:'30–65', eval:v=>band(v,30,65,20,70) },
    { id:'desc_present',  label:'Description заполнен',unit:'',norm:'да',       eval:boolOk, bool:true },
    { id:'desc_len',      label:'Длина Description', unit:'симв.', norm:'120–160',eval:v=>band(v,120,160,80,200) },
    { id:'title_duplicate',label:'Дубль Title на проекте',unit:'',norm:'нет',   eval:v=>v?'bad':'ok', bool:true, invert:true },
  ]},

  { cat: 'HTML-техника on-page', icon: '⚙️', params: [
    { id:'text_html_ratio',label:'Соотношение текст/код',unit:'%',norm:'> 15%', eval:v=>minBand(v,15,8) },
    { id:'img_count',      label:'Изображений',         unit:'',  norm:'≥ 1',    eval:v=>minBand(v,1,0) },
    { id:'img_alt_filled', label:'Заполнен alt',        unit:'%', norm:'100%',   eval:v=>minBand(v,100,70) },
    { id:'schema_present', label:'Микроразметка Schema',unit:'',  norm:'есть',   eval:boolOk, bool:true },
    { id:'lang_attr',      label:'Атрибут lang="ru"',   unit:'',  norm:'есть',   eval:boolOk, bool:true },
    { id:'viewport_meta',  label:'Meta viewport',       unit:'',  norm:'есть',   eval:boolOk, bool:true },
  ]},

  { cat: 'Форматирование', icon: '🎨', params: [
    { id:'list_count',    label:'Списков (ul/ol)',   unit:'', norm:'≥ 1',  eval:v=>minBand(v,1,0) },
    { id:'strong_count',  label:'Выделений strong',  unit:'', norm:'умеренно', eval:v=>maxBand(v,15,30) },
    { id:'strong_kw_spam',label:'Переспам выделением ключей', unit:'', norm:'нет', eval:v=>v?'bad':'ok', bool:true, invert:true },
    { id:'media_richness',label:'Индекс мультимедийности', unit:'', norm:'выше = лучше', eval:v=>minBand(v,3,1) },
  ]},

  { cat: 'Типографика', icon: '✒️', params: [
    { id:'double_spaces', label:'Двойные пробелы',    unit:'', norm:'0',   eval:v=>maxBand(v,0,3) },
    { id:'typo_quotes',   label:'Неправильные кавычки',unit:'', norm:'0',   eval:v=>maxBand(v,0,2) },
    { id:'caps_abuse',    label:'Слова капсом',       unit:'', norm:'минимум', eval:v=>maxBand(v,1,4) },
  ]},
];

// Параметры уровня ПРОЕКТА (7 страниц), не отдельной страницы
const PROJECT_PARAMS = {
  linking: [
    { id:'orphan_pages',    label:'Страницы-сироты (нет входящих)', norm:'0', eval:v=>maxBand(v,0,1) },
    { id:'dead_end_pages',  label:'Страницы-тупики (нет исходящих)',norm:'0', eval:v=>maxBand(v,0,1) },
    { id:'avg_internal_links',label:'Внутренних ссылок на странице (сред.)',norm:'2–7',eval:v=>band(v,2,7,1,10) },
    { id:'max_link_depth',  label:'Макс. глубина клика',            norm:'≤ 3', eval:v=>maxBand(v,3,4) },
    { id:'anchor_diversity',label:'Разнообразие анкоров',           norm:'> 60%', eval:v=>minBand(v,60,40) },
  ],
  uniqueness: [
    { id:'internal_uniqueness', label:'Мин. взаимная уникальность страниц', norm:'> 85%', eval:v=>minBand(v,85,70) },
    { id:'dup_paragraphs',      label:'Дублирующихся абзацев между страницами', norm:'0', eval:v=>maxBand(v,0,2) },
  ],
};

// Категории для сводного балла страницы
const SCORE_WEIGHTS = {
  seo:        ['kw_in_title','kw_in_h1','title_len','desc_len','h1_count','kw_first_para','lsi_coverage','img_alt_filled'],
  spam:       ['nausea_classic','nausea_academic','keyword_density_max','kw_exact_ratio','water_percent','strong_kw_spam'],
  readability:['flesch_reading_ease','flesch_kincaid_grade','gunning_fog','sentence_avg_len'],
  structure:  ['h2_count','list_count','heading_hierarchy','media_richness','paragraph_long_count'],
};
