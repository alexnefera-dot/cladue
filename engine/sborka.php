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
        if (is_array($list) && $list) { return (string) $list[$r->int(0, count($list) - 1)]; }
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
    public array $exhausted = [];
    public function __construct(private Rng $rng, private bool $strict = false) {}

    /** В строгом режиме исчерпанный мешок не пополняется: пусть лучше не хватит
     *  объёма, чем набор начнёт пересказывать сам себя. Так измеряется реальная
     *  ёмкость банка фраз. */
    public function take(string $key, array $items): ?string
    {
        if ($this->strict && isset($this->left[$key]) && !$this->left[$key]) {
            $this->exhausted[$key] = true;
            return null;
        }
        if (!isset($this->left[$key]) || !$this->left[$key]) {
            $this->left[$key] = array_values($items);
            // перетасовка сидом, чтобы порядок зависел от набора
            for ($i = count($this->left[$key]) - 1; $i > 0; $i--) {
                $j = $this->rng->int(0, $i);
                [$this->left[$key][$i], $this->left[$key][$j]] = [$this->left[$key][$j], $this->left[$key][$i]];
            }
        }
        return (string) array_pop($this->left[$key]);
    }
}

function fill(string $s, array $sl, string $brRu, string $brEn): string
{
    $s = strtr($s, $sl);
    return strtr($s, ['{Б}' => $brEn, '{Бр}' => $brRu]);
}

function words(string $html): int
{
    $t = trim(preg_replace('~\s+~u', ' ', strip_tags($html)));
    return $t === '' ? 0 : count(preg_split('~\s+~u', $t, -1, PREG_SPLIT_NO_EMPTY));
}

$an = new Analyzer();
$rng = new Rng($SEED);
$STRICT = isset($OPT['strict']);
$bag = new Bag($rng, $STRICT);
$SL  = slots($rng, $POOLS);
$BR_RU = '%brand_name_ru%';
$BR_EN = '%brand_name_en%';

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
    foreach ([['tezis', $FRAMES[$a0]['tezis']], ['poyasnenie', $FRAMES[$a0]['poyasnenie']]] as [$k, $src]) {
        $x = $bag->take("$a0.$k", $src);
        if ($x !== null) { $html[] = '<p>' . fill($x, $SL, $BR_RU, $BR_EN) . '</p>'; }
    }

    // ── разделы: H2 → абзац → (H3 → абзацы/список) ──────────────────────
    $h3left = $wantH3;
    for ($i = 0; $i < $wantH2; $i++) {
        $area = $areas[$i % count($areas)];
        $F = $FRAMES[$area];
        $h2t = $bag->take("$area.h2", $F['h2']);
        if ($h2t === null) { continue; }
        $html[] = '<h2>' . fill($h2t, $SL, $BR_RU, $BR_EN) . '</h2>';
        // Раздел ВСЕГДА открывается абзацем: у девяти образцов на 283 заголовка
        // нет ни одного случая, когда сразу за H2 идёт список.
        $tz = $bag->take("$area.tezis", $F['tezis']);
        $html[] = '<p>' . fill($tz ?? $bag->take("$area.poyasnenie", $F['poyasnenie']) ?? '—', $SL, $BR_RU, $BR_EN) . '</p>';

        $h3here = $wantH2 > 0 ? (int) floor($h3left / max(1, $wantH2 - $i)) : 0;
        $h3left -= $h3here;
        for ($j = 0; $j < $h3here; $j++) {
            $h3t = $bag->take("$area.h3", $F['h3']);
            if ($h3t === null) { continue; }
            $html[] = '<h3>' . fill($h3t, $SL, $BR_RU, $BR_EN) . '</h3>';
            $pt = $bag->take("$area.poyasnenie", $F['poyasnenie']);
            if ($pt !== null) { $html[] = '<p>' . fill($pt, $SL, $BR_RU, $BR_EN) . '</p>'; }
            if ($rng->float() < 0.45) {
                $og = $bag->take("$area.ogovorka", $F['ogovorka']);
                if ($og !== null) { $html[] = '<p>' . fill($og, $SL, $BR_RU, $BR_EN) . '</p>'; }
            }
            if ($lists < $wantLists && $rng->float() < 0.5) {
                $useOl = $ol < $wantOl;
                $src   = $useOl ? $F['shag'] : $F['punkt'];
                $n     = $rng->int(3, 4);
                $li    = [];
                for ($k = 0; $k < $n; $k++) {
                    $xr = $bag->take($area . ($useOl ? '.shag' : '.punkt'), $src);
                    if ($xr === null) { break; }
                    $x = fill($xr, $SL, $BR_RU, $BR_EN);
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
        $kind = $rng->float() < 0.6 ? 'poyasnenie' : 'ogovorka';
        $x = $bag->take("$area.$kind", $F[$kind]);
        if ($x === null) {
            if (count($bag->exhausted) >= count($FRAMES) * 2) { break; }
            continue;
        }
        $html[] = '<p>' . fill($x, $SL, $BR_RU, $BR_EN) . '</p>';
    }

    // ── FAQ в микроразметке ─────────────────────────────────────────────
    if ($wantFaq > 0) {
        $html[] = '<h2>' . fill('Частые вопросы о {Б}', $SL, $BR_RU, $BR_EN) . '</h2>';
        $ip = $bag->take("$a0.poyasnenie", $FRAMES[$a0]['poyasnenie']);
        if ($ip !== null) { $html[] = '<p>' . fill($ip, $SL, $BR_RU, $BR_EN) . '</p>'; }
        $html[] = '<div itemscope itemtype="https://schema.org/FAQPage">';
        for ($i = 0; $i < $wantFaq; $i++) {
            $area = $areas[$i % count($areas)];
            $F = $FRAMES[$area];
            $qr = $bag->take("$area.faq_q", $F['faq_q']);
            $ar = $bag->take("$area.faq_a", $F['faq_a']);
            if ($qr === null || $ar === null) { break; }
            $q = fill($qr, $SL, $BR_RU, $BR_EN);
            $aTxt = fill($ar, $SL, $BR_RU, $BR_EN);
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
