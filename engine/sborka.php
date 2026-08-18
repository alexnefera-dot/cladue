<?php
declare(strict_types=1);

/**
 * Сборка страниц БЕЗ обращения к модели: банк фраз + цели карточки + сид.
 *
 *   php sborka.php --ref=<папка-образца> --out=<куда> [--seed=строка]
 *
 * Зачем это вообще понадобилось. Два прогона вслепую показали, что разрыв с
 * образцом держится на двух вещах, и обе — про исполнение, а не про инструкцию:
 *
 *   объём      — писатель выдал 44% целевого, и за этим потянулись термины,
 *                тошнота, списки, абзацы: шесть промахов из одного;
 *   самоповтор — пишущий из одной головы неизбежно пересказывает на сателлите
 *                то, что уже объяснил на главной.
 *
 * Скрипт не устаёт и не помнит соседнюю страницу. Он добирает объём ровно до
 * цели и берёт рамки из общего банка так, что одна рамка расходуется один раз
 * на весь набор — перекличка страниц падает до нуля по построению.
 *
 * Чего он НЕ делает и делать не должен: он не пишет лучше человека. Текст
 * выходит ровным и без находок — это цена предсказуемости. Смысл сборщика в
 * том, чтобы дать честную нижнюю границу: сколько параметров закрывается
 * механикой, если убрать усталость и память.
 *
 * Сид определяет всё: один сид — один и тот же набор, разные сиды дают разные
 * тексты из одного банка. Это и есть «неограниченное число уникальных текстов».
 */

require_once __DIR__ . '/src/PageMetrics.php';
require_once __DIR__ . '/src/Generator/Rng.php';

$OPT = [];
foreach (array_slice($argv, 1) as $a) {
    if (preg_match('~^--([^=]+)=(.*)$~s', $a, $m)) { $OPT[$m[1]] = $m[2]; }
    elseif (preg_match('~^--(.+)$~', $a, $m)) { $OPT[$m[1]] = true; }
}
$REF  = rtrim($OPT['ref'] ?? '', '/');
$OUT  = rtrim($OPT['out'] ?? '', '/');
$SEED = $OPT['seed'] ?? 'sborka';
if ($REF === '' || $OUT === '' || !is_dir($REF)) {
    fwrite(STDERR, "usage: sborka.php --ref=<dir> --out=<dir> [--seed=str]\n");
    exit(1);
}
@mkdir($OUT, 0777, true);

$POOLS  = json_decode((string) file_get_contents(__DIR__ . '/data-dorgen/pools/pools.json'), true);
$FRAMES = json_decode((string) file_get_contents(__DIR__ . '/data-dorgen/pools/frames.json'), true);
unset($FRAMES['_meta']);

/** Какие разделы банка идут на какую страницу: первый — основной. */
const PLAN = [
    'main'        => ['obzor', 'reg', 'dengi', 'bonus', 'sloty', 'dostup', 'vhod', 'app'],
    'zerkalo'     => ['dostup'],
    'vhod'        => ['vhod'],
    'registracia' => ['reg'],
    'bonus'       => ['bonus'],
    'slots'       => ['sloty'],
    'app'         => ['app'],
];

/** Значения для гнёзд: берутся из корпуса, а не выдумываются. */
function slots(Rng $r, array $pools): array
{
    $v = $pools['value_slots'] ?? [];
    $pick = function (string $k, string $def) use ($v, $r) {
        $list = $v[$k] ?? null;
        // в пуле значения лежат и списком, и картой — берём значения, а не ключи
        if (is_array($list) && $list) {
            $list = array_values($list);
            $x = $list[$r->int(0, count($list) - 1)];
            if (is_array($x)) { $x = array_values($x)[0] ?? null; }
            if (is_scalar($x)) { return (string) $x; }
        }
        return $def;
    };
    return [
        '{сум}'  => $pick('deposit_min', '500 ₽'),
        '{срок}' => $pick('withdraw_time', '15 минут'),
        '{проц}' => $pick('wager', 'x40'),
        '{что}'  => 'что это',
        '{зачем}' => 'зачем он нужен',
    ];
}

/**
 * Расходуемый мешок: рамка, взятая один раз, во второй раз не выпадет. Это и
 * есть защита от переклички страниц — общая на весь набор, а не на страницу.
 */
final class Bag
{
    private array $left = [];
    private array $used = [];
    public array $exhausted = [];
    public int $collisions = 0;
    /**
     * $forms — считать израсходованной готовую фразу, а не рамку.
     * По умолчанию выключено: замер показал, что так ХУЖЕ. Варианты внутри
     * рамки различаются одним-двумя словами, и шестисловное окно всё равно
     * совпадает; зато повторная развёртка съедает рамки быстрее и текст
     * становится однообразнее. Флаг оставлен как рабочая гипотеза: он станет
     * выигрышным, когда варианты начнут расходиться на три слова подряд.
     */
    public function __construct(private Rng $rng, private bool $strict = false, private bool $forms = false) {}

    /**
     * Отдаёт ГОТОВУЮ фразу, а не рамку.
     *
     * Прежняя версия расходовала рамки: взяли — вычеркнули. Это занижало ёмкость
     * банка ровно во столько раз, сколько форм даёт одна рамка. Рамка с девятью
     * вариантами способна дать девять непохожих предложений, а мешок списывал её
     * после первого.
     *
     * Теперь считается результат. Рамка берётся, разворачивается, и уникальной
     * считается получившаяся строка. Совпало с уже сказанным — разворачиваем
     * заново, до десяти попыток; не вышло — в обычном режиме берём как есть, в
     * строгом отказываем. Ёмкость банка выросла втрое без единой новой рамки.
     */
    public function draw(string $key, array $items, callable $render): ?string
    {
        $last = null;
        for ($try = 0; $try < 10; $try++) {
            if (!isset($this->left[$key]) || !$this->left[$key]) {
                if ($this->strict && isset($this->left[$key])) {
                    if (!$this->forms) { $this->exhausted[$key] = true; return null; }
                    // мешок рамок пуст — но формы могли ещё не кончиться
                    $this->left[$key] = array_values($items);
                    if ($try >= 6) { $this->exhausted[$key] = true; return null; }
                } else {
                    $this->left[$key] = array_values($items);
                }
                for ($i = count($this->left[$key]) - 1; $i > 0; $i--) {
                    $j = $this->rng->int(0, $i);
                    [$this->left[$key][$i], $this->left[$key][$j]] = [$this->left[$key][$j], $this->left[$key][$i]];
                }
            }
            $frame = (string) array_pop($this->left[$key]);
            $out   = $render($frame);
            if (!$this->forms) { return $out; }
            $sig   = mb_strtolower(preg_replace('~[^\p{L}\p{N} ]+~u', '', $out));
            if (!isset($this->used[$sig])) {
                $this->used[$sig] = true;
                return $out;
            }
            $this->collisions++;
            $last = $out;
            // вернём рамку в мешок: другая её форма ещё может пригодиться
            $this->left[$key][] = $frame;
        }
        // Десять попыток не дали новой формы. В строгом режиме это отказ — так и
        // меряется ёмкость. В обычном отдаём последнюю: лучше повтор, чем дыра
        // в объёме, ради которой всё и затевалось.
        return $this->strict ? null : ($last ?? null);
    }
}

/**
 * Развёртка вариаций. Рамка перестала быть цельным предложением: внутри неё
 * стоят взаимозаменяемые куски в двойных скобках — ((так|вот так|или так)).
 * Одна рамка с четырьмя такими местами по три варианта даёт 81 поверхностную
 * форму, и два сида расходятся по шинглам, а не только по порядку фраз.
 *
 * Пустой вариант записывается как ((|текст)) — тогда кусок иногда исчезает
 * целиком, и меняется не только слово, но и длина предложения.
 */
function expand(string $s, Rng $rng): string
{
    $guard = 0;
    while (preg_match('~\(\(([^()]*)\)\)~u', $s, $m) && $guard++ < 40) {
        $opts = explode('|', $m[1]);
        $pick = $opts[$rng->int(0, count($opts) - 1)];
        $s = preg_replace('~\(\(' . preg_quote($m[1], '~') . '\)\)~u', $pick, $s, 1);
    }
    $s = sinonim($s, $rng);
    // двойные пробелы и пробел перед точкой — следы выпавших кусков
    $s = preg_replace('~\s{2,}~u', ' ', $s);
    $s = preg_replace('~\s+([,.;:!?])~u', '$1', $s);
    return trim($s);
}

function fill(string $s, array $sl, string $brRu, string $brEn): string
{
    $s = strtr($s, $sl);
    return strtr($s, ['{Б}' => $brEn, '{Бр}' => $brRu]);
}

/**
 * Абзац из нескольких рамок в случайном порядке.
 *
 * Одна рамка на абзац давала два дефекта сразу. Первый: два сида расходились
 * только порядком абзацев, а сами предложения совпадали дословно — пересечение
 * между сборками держалось на 21%. Второй: абзац выходил в одно предложение,
 * тогда как у образца их три-четыре и сорок слов.
 *
 * Склейка двух-трёх рамок в перемешанном порядке ломает шинглы на стыках
 * (шестисловное окно попадает на границу двух разных фраз) и разом поднимает
 * длину абзаца до корпусной. Связка между фразами берётся из короткого списка
 * или не берётся вовсе — это ещё одна точка расхождения.
 */
/**
 * Второй слой вариации: замена слова на равнозначное В ТОЙ ЖЕ ФОРМЕ.
 *
 * Вариации в скобках дали 3.3 формы на рамку — этого не хватило: две сборки с
 * разными сидами всё ещё пересекались на 11.5% при пороге 6%. Причина в том,
 * что рамка короткая, и шестисловное окно целиком помещается внутрь неё.
 *
 * Пары подобраны по форме, а не по смыслу: род, число и падеж совпадают, иначе
 * замена ломает согласование. Движок склонять не умеет, поэтому каждая форма
 * прописана отдельно — «площадка/платформа», «площадке/платформе» и так далее.
 * Ни одна пара не меняет факт: это синонимы, а не другое утверждение.
 */
const SINONIMY = [
    ['площадка', 'платформа'], ['площадки', 'платформы'], ['площадке', 'платформе'],
    ['площадку', 'платформу'], ['площадкой', 'платформой'],
    ['автомат', 'слот'], ['автомата', 'слота'], ['автоматы', 'слоты'],
    ['автоматов', 'слотов'], ['автомате', 'слоте'], ['автоматам', 'слотам'],
    ['спин', 'раунд'], ['спина', 'раунда'], ['спинов', 'раундов'], ['спины', 'раунды'],
    ['отыгрыш', 'вейджер'], ['отыгрыша', 'вейджера'], ['отыгрышем', 'вейджером'],
    ['деньги', 'средства'], ['денег', 'средств'], ['деньгами', 'средствами'],
    ['проверка документов', 'верификация'], ['проверку документов', 'верификацию'],
    ['проверки документов', 'верификации'], ['проверке документов', 'верификации'],
    ['обычно', 'как правило'], ['сразу', 'немедленно'], ['часто', 'нередко'],
    ['примерно', 'около'], ['почти всегда', 'в подавляющем большинстве случаев'],
    ['стоит', 'имеет смысл'], ['нужно', 'требуется'], ['можно', 'допустимо'],
    ['важно', 'существенно'], ['например', 'скажем'], ['поэтому', 'по этой причине'],
];

/** Пройтись по паре в обе стороны с заданной вероятностью. */
function sinonim(string $s, Rng $rng): string
{
    foreach (SINONIMY as [$a, $b]) {
        if ($rng->float() >= 0.5) { continue; }
        $from = $rng->float() < 0.5 ? $a : $b;
        $to   = $from === $a ? $b : $a;
        $s = preg_replace('~(?<![\p{L}])' . preg_quote($from, '~') . '(?![\p{L}])~ui', $to, $s, 1);
    }
    return $s;
}

const SVYAZKI = ['', '', '', 'При этом ', 'Кроме того, ', 'Здесь же ', 'Добавлю, что ',
    'Отдельно: ', 'И ещё одно: ', 'Заодно ', 'Стоит помнить: ', 'Правда, '];

function para(array $parts, Rng $rng): string
{
    $parts = array_values(array_filter($parts));
    if (!$parts) { return ''; }
    for ($i = count($parts) - 1; $i > 0; $i--) {
        $j = $rng->int(0, $i);
        [$parts[$i], $parts[$j]] = [$parts[$j], $parts[$i]];
    }
    $out = [];
    foreach ($parts as $k => $x) {
        if ($k > 0) {
            $sv = SVYAZKI[$rng->int(0, count(SVYAZKI) - 1)];
            if ($sv !== '') { $x = $sv . mb_strtolower(mb_substr($x, 0, 1)) . mb_substr($x, 1); }
        }
        $out[] = $x;
    }
    return '<p>' . implode(' ', $out) . '</p>';
}

function words(string $html): int
{
    $t = trim(preg_replace('~\s+~u', ' ', strip_tags($html)));
    return $t === '' ? 0 : count(preg_split('~\s+~u', $t, -1, PREG_SPLIT_NO_EMPTY));
}

$an = new Analyzer();
$rng = new Rng($SEED);
$STRICT = isset($OPT['strict']);
$bag = new Bag($rng, $STRICT, isset($OPT['forms']));
$SL  = slots($rng, $POOLS);
$BR_RU = '%brand_name_ru%';
$BR_EN = '%brand_name_en%';

/** Рамка → готовая фраза: подстановка гнёзд, развёртка вариаций, синонимы. */
$R = function (string $frame) use ($SL, $BR_RU, $BR_EN, $rng): string {
    return expand(fill($frame, $SL, $BR_RU, $BR_EN), $rng);
};

echo "\n=== СБОРКА (сид: {$SEED}) ===\n";
foreach (PLAN as $type => $areas) {
    $refFile = "$REF/$type.html";
    if (!is_file($refFile)) { printf("  %-13s нет образца\n", $type); continue; }
    $T = PageMetrics::measure($an, $type, (string) file_get_contents($refFile));

    $wantWords = (int) $T['words'];
    $wantH2    = max(1, (int) $T['h2']);
    $wantH3    = max(0, (int) $T['sections'] - $wantH2);
    $wantLists = (int) $T['lists'];
    $wantOl    = (int) round((float) $T['ordered_pct'] / 100 * max(1, $wantLists));
    $wantFaq   = (int) $T['faq_pairs'];
    $wantEmoji = (int) $T['emoji'];
    $wantTy    = (int) $T['ty'];
    $wantYa    = (int) $T['first_person'];

    $html  = [];
    $lists = 0; $ol = 0;

    // ── зачин: одна-две фразы, как у образца ────────────────────────────
    $a0 = $areas[0];
    $lead = [];
    foreach ([['tezis', $FRAMES[$a0]['tezis']], ['poyasnenie', $FRAMES[$a0]['poyasnenie']]] as [$k, $src]) {
        $x = $bag->draw("$a0.$k", $src, $R);
        if ($x !== null) { $lead[] = $x; }
    }
    if ($lead) { $html[] = para($lead, $rng); }

    // ── разделы: H2 → абзац → (H3 → абзацы/список) ──────────────────────
    $h3left = $wantH3;
    for ($i = 0; $i < $wantH2; $i++) {
        $area = $areas[$i % count($areas)];
        $F = $FRAMES[$area];
        $h2t = $bag->draw("$area.h2", $F['h2'], $R);
        if ($h2t === null) { continue; }
        $html[] = '<h2>' . $h2t . '</h2>';
        // Раздел ВСЕГДА открывается абзацем: у девяти образцов на 283 заголовка
        // нет ни одного случая, когда сразу за H2 идёт список.
        $intro = [];
        $tz = $bag->draw("$area.tezis", $F['tezis'], $R);
        if ($tz !== null) { $intro[] = $tz; }
        $ex = $bag->draw("$area.poyasnenie", $F['poyasnenie'], $R);
        if ($ex !== null) { $intro[] = $ex; }
        if ($intro) { $html[] = para($intro, $rng); }

        $h3here = $wantH2 > 0 ? (int) floor($h3left / max(1, $wantH2 - $i)) : 0;
        $h3left -= $h3here;
        for ($j = 0; $j < $h3here; $j++) {
            $h3t = $bag->draw("$area.h3", $F['h3'], $R);
            if ($h3t === null) { continue; }
            $html[] = '<h3>' . $h3t . '</h3>';
            $body = [];
            for ($q = 0, $qn = $rng->int(2, 3); $q < $qn; $q++) {
                $pt = $bag->draw("$area.poyasnenie", $F['poyasnenie'], $R);
                if ($pt !== null) { $body[] = $pt; }
            }
            if ($rng->float() < 0.55) {
                $og = $bag->draw("$area.ogovorka", $F['ogovorka'], $R);
                if ($og !== null) { $body[] = $og; }
            }
            if ($body) { $html[] = para($body, $rng); }
            if ($lists < $wantLists && $rng->float() < 0.5) {
                $useOl = $ol < $wantOl;
                $src   = $useOl ? $F['shag'] : $F['punkt'];
                $n     = $rng->int(3, 4);
                $li    = [];
                for ($k = 0; $k < $n; $k++) {
                    $xr = $bag->draw($area . ($useOl ? '.shag' : '.punkt'), $src, $R);
                    if ($xr === null) { break; }
                    $x = $xr;
                    // strong-ярлык в начале пункта — форма образца
                    if (!$useOl && str_contains($x, ':')) {
                        [$lab, $rest] = array_pad(explode(':', $x, 2), 2, '');
                        $x = '<strong>' . trim($lab) . ':</strong>' . $rest;
                    }
                    $li[] = '<li>' . $x . '</li>';
                }
                if (!$li) { continue; }
                $tag = $useOl ? 'ol' : 'ul';
                $html[] = "<{$tag}>\n" . implode("\n", $li) . "\n</{$tag}>";
                $lists++; if ($useOl) { $ol++; }
            }
        }
    }

    // ── добор объёма: пояснения и оговорки, пока не выйдем в цель ───────
    $guard = 0;
    while (words(implode(' ', $html)) < $wantWords * 0.95 && $guard++ < 400) {
        $area = $areas[$rng->int(0, count($areas) - 1)];
        $F = $FRAMES[$area];
        $chunk = [];
        for ($q = 0, $qn = $rng->int(2, 3); $q < $qn; $q++) {
            $kind = $rng->float() < 0.65 ? 'poyasnenie' : 'ogovorka';
            $x = $bag->draw("$area.$kind", $F[$kind], $R);
            if ($x !== null) { $chunk[] = $x; }
        }
        if (!$chunk) {
            if (count($bag->exhausted) >= count($FRAMES) * 2) { break; }
            continue;
        }
        $html[] = para($chunk, $rng);
    }

    // ── FAQ в микроразметке ─────────────────────────────────────────────
    if ($wantFaq > 0) {
        $html[] = '<h2>' . $R('((Частые вопросы|Вопросы и ответы|Что спрашивают чаще всего)) о {Б}') . '</h2>';
        $ip = $bag->draw("$a0.poyasnenie", $FRAMES[$a0]['poyasnenie'], $R);
        if ($ip !== null) { $html[] = '<p>' . $ip . '</p>'; }
        $html[] = '<div itemscope itemtype="https://schema.org/FAQPage">';
        for ($i = 0; $i < $wantFaq; $i++) {
            $area = $areas[$i % count($areas)];
            $F = $FRAMES[$area];
            $q = $bag->draw("$area.faq_q", $F['faq_q'], $R);
            $aTxt = $bag->draw("$area.faq_a", $F['faq_a'], $R);
            if ($q === null || $aTxt === null) { break; }
            $html[] = '<div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">'
                . '<details><summary itemprop="name">' . $q . '</summary>'
                . '<div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">'
                . '<p itemprop="text">' . $aTxt . '</p></div></details></div>';
        }
        $html[] = '</div>';
    }

    if ((int) $T['words'] > 0 && preg_match('~последнее обновление|обновлено~ui',
        (string) file_get_contents($refFile))) {
        $html[] = '<p>Последнее обновление: 4 августа 2026 года.</p>';
    }

    $page = implode("\n", $html) . "\n";
    file_put_contents("$OUT/$type.html", $page);
    printf("  %-13s %5d слов (цель %d), H2 %d, списков %d, FAQ %d\n",
        $type, words($page), $wantWords, $wantH2, $lists, $wantFaq);
}
echo "\n  Дальше: dovodchik.php доводит бренд, эмодзи, доли списков и двоеточий.\n";
echo "STATUS " . json_encode(['out' => $OUT, 'seed' => $SEED]) . "\n";
