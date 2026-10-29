<?php
/**
 * Собирает один самодостаточный HTML для просмотра присланных страниц конкурентов.
 *
 *   php engine/instrumenty/prosmotr.php            → reports/prosmotr.html
 *
 * Читает samples/konkurenty/sayt-*: _style.css (общий CSS сайта), _klass.txt
 * (класс обёртки) и страницы *.html. Подставляет бренд-метки, подсвечивает
 * незаменённые плейсхолдеры, считает метрики по каждой странице.
 */

const КОРЕНЬ = __DIR__ . '/../..';
const ВХОД = КОРЕНЬ . '/samples/konkurenty';
const ВЫХОД = КОРЕНЬ . '/reports/prosmotr.html';

const ПОРЯДОК = [
    'main' => 'главная', 'bonus' => 'бонус', 'registracia' => 'регистрация',
    'app' => 'приложение', 'zerkalo' => 'зеркало', 'vhod' => 'вход',
    'slots' => 'слоты', 'novosti' => 'новости', 'info' => 'инфо',
    'promo' => 'промо', 'obzor' => 'обзор', 'partnery' => 'партнёры',
];

const БРЕНД = [
    '%brand_name_ru%' => 'Казино-Икс',
    '%brand_name_en%' => 'CasinoX',
    '%domain_name%' => 'casinox.example',
    '%date%' => '29.10.2026',
];

/** Незаменённые плейсхолдеры — явный дефект вёрстки, подсвечиваем. */
const ДЕФЕКТЫ = ['{slots}', '{vhod}', '{info}', '{news}', '{promo}', 'CASINO_NAME'];

function метрики(string $html): array
{
    $текст = html_entity_decode(strip_tags($html), ENT_QUOTES | ENT_HTML5, 'UTF-8');
    $текст = preg_replace('~\s+~u', ' ', trim($текст));
    $счёт = fn(string $тег) => preg_match_all('~<' . $тег . '\b~i', $html);
    return [
        'слов' => $текст === '' ? 0 : count(preg_split('~\s+~u', $текст)),
        'симв' => mb_strlen($текст),
        'h2' => $счёт('h2'),
        'h3' => $счёт('h3'),
        'абз' => $счёт('p'),
        'табл' => $счёт('table'),
        'ul' => $счёт('ul'),
        'ol' => $счёт('ol'),
        'li' => $счёт('li'),
        'ссылок' => $счёт('a'),
        'цитат' => $счёт('blockquote'),
        'details' => $счёт('details'),
        'картинок' => $счёт('img'),
    ];
}

function подстановка(string $html): string
{
    $html = str_replace(array_keys(БРЕНД), array_values(БРЕНД), $html);
    foreach (ДЕФЕКТЫ as $д) {
        $html = str_replace($д, '<mark class="pr-defekt">' . $д . '</mark>', $html);
    }
    return $html;
}

$сайты = [];
foreach (glob(ВХОД . '/sayt-*', GLOB_ONLYDIR) ?: [] as $каталог) {
    $имя = basename($каталог);
    $класс = trim(@file_get_contents($каталог . '/_klass.txt') ?: '');
    $css = @file_get_contents($каталог . '/_style.css') ?: '';
    $страницы = [];
    foreach (ПОРЯДОК as $файл => $ярлык) {
        $путь = $каталог . '/' . $файл . '.html';
        if (!is_file($путь)) {
            continue;
        }
        $html = file_get_contents($путь);
        $страницы[$файл] = [
            'ярлык' => $ярлык,
            'html' => подстановка($html),
            'метрики' => метрики($html),
        ];
    }
    if ($страницы) {
        $сайты[$имя] = ['класс' => $класс, 'css' => $css, 'страницы' => $страницы];
    }
}

if (!$сайты) {
    fwrite(STDERR, "В " . ВХОД . " нет папок sayt-*\n");
    exit(1);
}

$э = fn(string $s) => htmlspecialchars($s, ENT_QUOTES, 'UTF-8');

ob_start();
?>
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Страницы конкурентов</title>
<style>
:root{--pr-fon:#0e1013;--pr-panel:#15181d;--pr-ramka:#262b33;--pr-tekst:#e6eaf0;--pr-tus:#8d97a5;--pr-akc:#6ea8fe}
:root[data-tema="svet"]{--pr-fon:#f4f6f8;--pr-panel:#fff;--pr-ramka:#d8dde4;--pr-tekst:#15181d;--pr-tus:#5d6775;--pr-akc:#1b5fd8}
*{box-sizing:border-box}
body{margin:0;background:var(--pr-fon);color:var(--pr-tekst);
  font:400 15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.pr-obolochka{display:grid;grid-template-columns:270px minmax(0,1fr);min-height:100vh}
.pr-bok{border-right:1px solid var(--pr-ramka);background:var(--pr-panel);
  padding:16px 14px;position:sticky;top:0;align-self:start;max-height:100vh;overflow:auto}
.pr-bok h1{font-size:15px;margin:0 0 4px}
.pr-bok .pr-pod{color:var(--pr-tus);font-size:12.5px;margin:0 0 14px}
.pr-sayt{font-size:11.5px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--pr-tus);margin:16px 0 7px;padding-top:12px;border-top:1px solid var(--pr-ramka)}
.pr-sayt:first-of-type{border-top:0;padding-top:0;margin-top:0}
.pr-knopka{display:flex;justify-content:space-between;gap:8px;width:100%;text-align:left;
  background:transparent;border:1px solid transparent;border-radius:7px;color:var(--pr-tekst);
  font:inherit;font-size:14px;padding:6px 9px;cursor:pointer}
.pr-knopka:hover{border-color:var(--pr-ramka)}
.pr-knopka[aria-current="true"]{background:color-mix(in srgb,var(--pr-akc) 18%,transparent);
  border-color:color-mix(in srgb,var(--pr-akc) 45%,transparent);font-weight:600}
.pr-knopka span{color:var(--pr-tus);font-size:12px;font-variant-numeric:tabular-nums}
.pr-tema{margin-top:18px;padding-top:12px;border-top:1px solid var(--pr-ramka)}
.pr-tema button{width:100%;background:transparent;border:1px solid var(--pr-ramka);
  border-radius:7px;color:var(--pr-tus);font:inherit;font-size:13px;padding:7px;cursor:pointer}
.pr-glav{padding:20px clamp(14px,3vw,30px) 60px;min-width:0}
.pr-shapka{display:flex;flex-wrap:wrap;gap:10px 18px;align-items:baseline;margin-bottom:12px}
.pr-shapka h2{margin:0;font-size:19px}
.pr-shapka code{color:var(--pr-tus);font-size:12.5px}
.pr-metriki{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:18px}
.pr-metriki b{display:inline-flex;gap:6px;align-items:baseline;background:var(--pr-panel);
  border:1px solid var(--pr-ramka);border-radius:999px;padding:4px 11px;font-weight:600;font-size:13px}
.pr-metriki b i{color:var(--pr-tus);font-style:normal;font-weight:400;font-size:12px}
.pr-ramka{border:1px solid var(--pr-ramka);border-radius:10px;overflow:hidden;background:#101214}
:root[data-tema="svet"] .pr-ramka{background:#0e1013}
.pr-stranica{display:none}
.pr-stranica.pr-vidna{display:block}
.pr-defekt{background:#ff4d6d;color:#fff;padding:0 .28em;border-radius:3px;font-weight:700}
.pr-zaglushka{display:flex;align-items:center;justify-content:center;min-height:120px;
  background:repeating-linear-gradient(45deg,#1b1f26,#1b1f26 10px,#22272f 10px,#22272f 20px);
  border-radius:8px;color:#8d97a5;font-size:12.5px;padding:14px;text-align:center}
@media (max-width:860px){
  .pr-obolochka{grid-template-columns:1fr}
  .pr-bok{position:static;max-height:none;border-right:0;border-bottom:1px solid var(--pr-ramka)}
}
<?php foreach ($сайты as $сайт): ?>
<?= $сайт['css'] ?>

<?php endforeach; ?>
</style>
</head>
<body>
<div class="pr-obolochka">
<nav class="pr-bok">
  <h1>Страницы конкурентов</h1>
  <p class="pr-pod">Всего сайтов: <?= count($сайты) ?>. Бренд-метки подставлены,
     незаменённые плейсхолдеры подсвечены красным.</p>
<?php foreach ($сайты as $имя => $сайт): ?>
  <div class="pr-sayt"><?= $э($имя) ?> · <?= $э($сайт['класс']) ?></div>
<?php foreach ($сайт['страницы'] as $файл => $стр): ?>
  <button class="pr-knopka" data-cel="<?= $э($имя . '/' . $файл) ?>">
    <?= $э($стр['ярлык']) ?><span><?= $стр['метрики']['слов'] ?> сл.</span>
  </button>
<?php endforeach; ?>
<?php endforeach; ?>
  <div class="pr-tema"><button id="pr-tema">Светлая тема</button></div>
</nav>
<main class="pr-glav">
<?php $первая = true; foreach ($сайты as $имя => $сайт): ?>
<?php foreach ($сайт['страницы'] as $файл => $стр): ?>
  <section class="pr-stranica<?= $первая ? ' pr-vidna' : '' ?>" id="pr-<?= $э($имя . '-' . $файл) ?>">
    <div class="pr-shapka">
      <h2><?= $э($имя) ?> — <?= $э($стр['ярлык']) ?></h2>
      <code><?= $э($файл) ?>.html · <?= $э($сайт['класс']) ?></code>
    </div>
    <div class="pr-metriki">
<?php foreach ($стр['метрики'] as $ключ => $знач): ?>
      <b><?= $знач ?><i><?= $э($ключ) ?></i></b>
<?php endforeach; ?>
    </div>
    <div class="pr-ramka">
      <div class="<?= $э($сайт['класс']) ?>"><?= $стр['html'] ?></div>
    </div>
  </section>
<?php $первая = false; endforeach; ?>
<?php endforeach; ?>
</main>
</div>
<script>
const кнопки = [...document.querySelectorAll('.pr-knopka')];
кнопки[0]?.setAttribute('aria-current', 'true');
for (const к of кнопки) {
  к.addEventListener('click', () => {
    for (const д of кнопки) д.removeAttribute('aria-current');
    к.setAttribute('aria-current', 'true');
    const ид = 'pr-' + к.dataset.cel.replace('/', '-');
    for (const с of document.querySelectorAll('.pr-stranica')) {
      с.classList.toggle('pr-vidna', с.id === ид);
    }
    scrollTo({top: 0});
  });
}
const корень = document.documentElement, тумблер = document.getElementById('pr-tema');
тумблер.addEventListener('click', () => {
  const светло = корень.dataset.tema === 'svet';
  корень.dataset.tema = светло ? 'temn' : 'svet';
  тумблер.textContent = светло ? 'Светлая тема' : 'Тёмная тема';
});
// Картинки конкурентов лежат на их домене — подменяем битые заглушкой.
for (const img of document.querySelectorAll('.pr-ramka img')) {
  img.addEventListener('error', () => {
    const з = document.createElement('div');
    з.className = 'pr-zaglushka';
    з.textContent = 'картинка: ' + (img.getAttribute('alt') || img.getAttribute('src') || '—');
    img.replaceWith(з);
  });
}
</script>
</body>
</html>
<?php
$итог = ob_get_clean();
@mkdir(dirname(ВЫХОД), 0777, true);
file_put_contents(ВЫХОД, $итог);

$всего = array_sum(array_map(fn($с) => count($с['страницы']), $сайты));
printf("%s — %d сайтов, %d страниц, %d КБ\n",
    ВЫХОД, count($сайты), $всего, (int) round(strlen($итог) / 1024));
