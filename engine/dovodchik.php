<?php
declare(strict_types=1);

/**
 * Механический доводчик: правит то, что считается и правится без участия
 * писателя, и НЕ трогает то, где нужен смысл.
 *
 *   php dovodchik.php <папка-с-генерацией> <папка-образца> [--dry]
 *
 * Опыт с картой вслепую показал, где теряется совпадение: не там, где карточка
 * молчит, а там, где она называет число, а писатель его не удерживает. Все
 * промахи первого прохода — вставки бренда, эмодзи, доля нумерованных списков,
 * доля заголовков с двоеточием — это счётные величины, не требующие понимания
 * текста. Их правит скрипт, а внимание писателя остаётся на том, чего скрипт
 * не может: тон, объём, о чём страница.
 *
 * Правится ЧЕТЫРЕ вещи, и все обратимы:
 *
 *   бренд     — доводится число плейсхолдеров в прозе. Имя ВСТАВЛЯЕТСЯ рядом с
 *               опорным словом («каталог %brand%», «касса %brand%») и снимается
 *               оттуда же. Заменять существительное на плейсхолдер нельзя —
 *               ломается падеж;
 *   эмодзи    — маркер в начале пункта списка ставится или снимается;
 *   ol / ul   — список переводится в нумерованный, если его пункты начинаются
 *               с глагола в повелительном наклонении, то есть это порядок
 *               действий, а не перечень; обратно — если нет;
 *   двоеточие — в заголовке H3 ставится или снимается, но только там, где это
 *               не ломает фразу: «Отдача: что означает» ↔ «Отдача — что означает».
 *
 * Всё остальное — объём, тон, призывы, минусы — доводчик не трогает и пишет о
 * них в отчёт: это работа писателя, и подделывать её механикой значит получить
 * нужную цифру при испорченном тексте.
 */

require_once __DIR__ . '/src/PageMetrics.php';

$args = array_values(array_filter(array_slice($argv, 1), fn($a) => $a !== '--dry'));
$DRY  = in_array('--dry', $argv, true);
$DIR  = rtrim($args[0] ?? '', '/');
$REF  = rtrim($args[1] ?? '', '/');
if ($DIR === '' || $REF === '' || !is_dir($DIR) || !is_dir($REF)) {
    fwrite(STDERR, "usage: dovodchik.php <dir> <ref-dir> [--dry]\n");
    exit(1);
}

/**
 * Опорные слова, после которых имя площадки встаёт приложением и ничего не
 * ломает: «каталог %brand%», «касса %brand%», «поддержка %brand%». Именно так
 * имя стоит у образца — не вместо существительного, а рядом с ним. Замена
 * существительного на плейсхолдер («сайт» → «%brand%») ломает падеж, поэтому
 * доводчик только ВСТАВЛЯЕТ.
 */
const HOSTS = ['каталог', 'каталоге', 'касса', 'кассе', 'кассу', 'поддержка',
    'поддержке', 'поддержку', 'кабинет', 'кабинете', 'приложение', 'приложении',
    'зеркало', 'зеркале', 'площадка', 'площадке', 'площадку', 'платформа',
    'платформе'];
// Многозначные слова сюда не входят намеренно. «Три правила» — это правила
// осторожности, а не правила площадки; «раздел» бывает разделом чего угодно;
// «лимит» стоит и в отрыве от имени. Вставка после них даёт грамматически
// верную, но бессмысленную фразу, а это хуже недобора.

/** Пункт списка — шаг, если начинается с глагола в повелительном наклонении. */
function isStep(string $li): bool
{
    $t = trim(preg_replace('~\s+~u', ' ', strip_tags($li)));
    return (bool) preg_match('~^(?:<[^>]+>)*\s*[А-ЯЁA-Z]?[а-яёa-z]*(?:йте?|ите?|ешь|ай|и)\b~u', $t)
        || (bool) preg_match('~^(открой|введи|задай|выбери|подтверди|нажми|проверь|загрузи|дождись|напиши|жми|посчитай|раздели|сравни|запусти|разреши|войди|смени|включи|отправь|скачай|установи|укажи|заполни|сохрани|посмотри|пройди)~ui', $t);
}

$an = new Analyzer();
$total = ['brand' => 0, 'emoji' => 0, 'lists' => 0, 'colon' => 0];

echo "\n=== ДОВОДЧИК ===\n";
foreach (glob("$DIR/*.html") as $f) {
    $type = pathinfo($f, PATHINFO_FILENAME);
    $ref  = "$REF/$type.html";
    if (!is_file($ref)) { printf("  %-13s нет пары в образце\n", $type); continue; }

    $raw  = (string) file_get_contents($f);
    $want = PageMetrics::measure($an, $type, (string) file_get_contents($ref));
    $fix  = [];

    // ── бренд: доводим число латинских вставок ───────────────────────────
    $has  = substr_count($raw, '%brand_name_en%');
    $need = (int) $want['brand_en'];
    if ($need > $has) {
        $add = $need - $has;
        $re  = '~\b(' . implode('|', HOSTS) . ')\b(?!\s*%brand)~ui';
        // Внутрь ссылок не лезем: анкор — отдельный параметр, и его текст
        // задан перелинковкой, а не плотностью бренда.
        $raw = preg_replace_callback('~<p\b[^>]*>.*?</p>~is', function ($m) use (&$add, $re) {
            $parts = preg_split('~(<a\b[^>]*>.*?</a>)~is', $m[0], -1,
                PREG_SPLIT_DELIM_CAPTURE | PREG_SPLIT_NO_EMPTY);
            foreach ($parts as $i => $chunk) {
                if (str_starts_with(strtolower($chunk), '<a')) { continue; }
                $parts[$i] = preg_replace_callback($re, function ($x) use (&$add) {
                    if ($add <= 0) { return $x[0]; }
                    $add--;
                    return $x[0] . ' %brand_name_en%';
                }, $chunk);
            }
            return implode('', $parts);
        }, $raw);
        $done = $need - $has - $add;
        if ($done) { $fix[] = 'бренд +' . $done; $total['brand'] += $done; }
        if ($add > 0) { $fix[] = "бренд НЕ ДОБРАН {$add} — опорных слов не хватило"; }
    } elseif ($need < $has) {
        $drop = $has - $need;
        // Снимаем только приложения в прозе: в заголовках и таблицах имя стоит намеренно.
        $re = '~\b(' . implode('|', HOSTS) . ')\s+%brand_name_en%~ui';
        $raw = preg_replace_callback('~<p\b[^>]*>.*?</p>~is', function ($m) use (&$drop, $re) {
            return preg_replace_callback($re, function ($x) use (&$drop) {
                if ($drop <= 0) { return $x[0]; }
                $drop--;
                return $x[1];
            }, $m[0]);
        }, $raw);
        $done = $has - $need - $drop;
        if ($done) { $fix[] = 'бренд −' . $done; $total['brand'] += $done; }
    }

    // ── эмодзи в маркерах списка ─────────────────────────────────────────
    $emo  = '~(<li>|<td>)\s*([\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}])\s*~u';
    $hasE = preg_match_all($emo, $raw);
    $needE = (int) $want['emoji'];
    $nowE  = preg_match_all('~[\x{1F300}-\x{1FAFF}\x{2600}-\x{27BF}]~u', $raw);
    if ($nowE > $needE && $hasE > 0) {
        $drop = min($hasE, $nowE - $needE);
        $raw = preg_replace_callback($emo, function ($m) use (&$drop) {
            if ($drop <= 0) { return $m[0]; }
            $drop--;
            return $m[1];
        }, $raw);
        $fix[] = 'эмодзи −' . min($hasE, $nowE - $needE);
        $total['emoji'] += min($hasE, $nowE - $needE);
    }

    // ── доля нумерованных списков ────────────────────────────────────────
    preg_match_all('~<(ul|ol)\b[^>]*>(.*?)</\1>~is', $raw, $lm, PREG_SET_ORDER);
    $n = count($lm);
    if ($n > 0) {
        $wantOl = (int) round((float) $want['ordered_pct'] / 100 * $n);
        $isOl   = count(array_filter($lm, fn($x) => strtolower($x[1]) === 'ol'));
        if ($isOl < $wantOl) {
            $turn = $wantOl - $isOl;
            foreach ($lm as $blk) {
                if ($turn <= 0 || strtolower($blk[1]) !== 'ul') { continue; }
                preg_match_all('~<li\b[^>]*>(.*?)</li>~is', $blk[2], $li);
                $steps = count(array_filter($li[1] ?? [], 'isStep'));
                if ($steps < max(1, count($li[1] ?? []) - 1)) { continue; }   // не порядок действий
                $new = preg_replace('~^<ul~i', '<ol', $blk[0]);
                $new = preg_replace('~</ul>$~i', '</ol>', $new);
                $raw = str_replace($blk[0], $new, $raw);
                $turn--;
            }
            $fix[] = 'ul→ol ' . ($wantOl - $isOl - $turn);
            $total['lists'] += $wantOl - $isOl - $turn;
        } elseif ($isOl > $wantOl) {
            $turn = $isOl - $wantOl;
            foreach ($lm as $blk) {
                if ($turn <= 0 || strtolower($blk[1]) !== 'ol') { continue; }
                preg_match_all('~<li\b[^>]*>(.*?)</li>~is', $blk[2], $li);
                if (count(array_filter($li[1] ?? [], 'isStep')) >= count($li[1] ?? [])) { continue; }
                $new = preg_replace('~^<ol~i', '<ul', $blk[0]);
                $new = preg_replace('~</ol>$~i', '</ul>', $new);
                $raw = str_replace($blk[0], $new, $raw);
                $turn--;
            }
            $fix[] = 'ol→ul ' . ($isOl - $wantOl - $turn);
            $total['lists'] += $isOl - $wantOl - $turn;
        }
    }

    // ── двоеточие в H3 ───────────────────────────────────────────────────
    preg_match_all('~<h3\b[^>]*>(.*?)</h3>~is', $raw, $hm, PREG_SET_ORDER);
    $h3 = array_values(array_filter($hm, fn($x) => strip_tags($x[1]) !== ''));
    if ($h3) {
        $wantC = (int) round((float) $want['h3_colon_pct'] / 100 * count($h3));
        $nowC  = count(array_filter($h3, fn($x) => mb_strpos($x[1], ':') !== false));
        if ($nowC < $wantC) {
            $turn = $wantC - $nowC;
            foreach ($h3 as $x) {
                if ($turn <= 0 || mb_strpos($x[1], ':') !== false) { continue; }
                // Двоеточие ставим только там, где фраза сама распадается надвое
                if (!preg_match('~^(.{6,32}?)\s+—\s+(.+)$~u', $x[1], $p)) { continue; }
                $raw = str_replace($x[0], str_replace($x[1], $p[1] . ': ' . $p[2], $x[0]), $raw);
                $turn--;
            }
            $fix[] = 'H3 двоеточие +' . ($wantC - $nowC - $turn);
            $total['colon'] += $wantC - $nowC - $turn;
        } elseif ($nowC > $wantC) {
            $turn = $nowC - $wantC;
            foreach ($h3 as $x) {
                if ($turn <= 0 || mb_strpos($x[1], ':') === false) { continue; }
                if (!preg_match('~^(.+?):\s*(.+)$~u', $x[1], $p)) { continue; }
                $raw = str_replace($x[0], str_replace($x[1], $p[1] . ' — ' . $p[2], $x[0]), $raw);
                $turn--;
            }
            $fix[] = 'H3 двоеточие −' . ($nowC - $wantC - $turn);
            $total['colon'] += $nowC - $wantC - $turn;
        }
    }

    if (!$DRY && $fix) { file_put_contents($f, $raw); }
    printf("  %-13s %s\n", $type, $fix ? implode(', ', $fix) : 'нечего править');
}

printf("\n  ИТОГО правок: бренд %d, эмодзи %d, списки %d, двоеточия %d%s\n",
    $total['brand'], $total['emoji'], $total['lists'], $total['colon'],
    $DRY ? '   (--dry: файлы не тронуты)' : '');
echo "\n  Доводчик НЕ правит: объём, тон обращения, призывы, названные минусы,\n";
echo "  длину заголовков и плотности. Это работа писателя — механика тут даст\n";
echo "  нужную цифру при испорченном тексте.\n";
echo "STATUS " . json_encode($total) . "\n";
