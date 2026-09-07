<?php
/**
 * Сверка чисел страницы: сколько разных значений у величин площадки в прозе,
 * как часто повторяются мантры и короткие фразы, есть ли обрывки без героя.
 *
 * php engine/sverka-v5.php <папка> [<папка> …] [--json] [--страницы]
 *
 * Проза — абзацы, пункты и заголовки вне <section>: виджеты (карточки слотов,
 * прогрессивные джекпоты, «последние выплаты», тематические блоки) не считаются,
 * у них свои цифры по замыслу.
 *
 * На страницу:
 *   package_uniq  — разных процентов пакета/бонуса (кэшбэк, релоад, ревшара, бонус за установку — не считаются)
 *   jackpot_uniq  — разных «N млн» рядом со словом «джекпот»
 *   rtp_spread    — разброс RTP в прозе (макс − мин), rtp_uniq — разных значений
 *   payout_uniq   — разных сроков вывода
 *   mantra_max    — самое частое семейство мантр в одном разделе
 *   short_dup_max — самое частое короткое предложение (до трёх слов) на странице
 *   fragments     — обрывки без героя: короткая фраза с суммой/сроком/«он» в разделе без имени
 *   wager         — множители вейджера
 */
$папки = []; $json = false; $поСтраницам = false;
foreach (array_slice($argv, 1) as $а) {
    if ($а === '--json') { $json = true; continue; }
    if ($а === '--страницы') { $поСтраницам = true; continue; }
    if ($а !== '' && $а[0] !== '-') { $папки[] = rtrim($а, '/'); }
}
if (!$папки) { fwrite(STDERR, "usage: php engine/sverka-v5.php <папка> [<папка> …] [--json] [--страницы]\n"); exit(1); }

const СТРАНИЦЫ = ['main', 'obzor', 'promo', 'news', 'info', 'partnery', 'app', 'bonus', 'registracia', 'slots', 'vhod', 'zerkalo'];
const МАНТРЫ = [
    'гарантий нет'   => '~гаранти[йя]\s+(?:тут\s+|здесь\s+)?(?:нет|никто|не\s+да[её]т)|никаких гарантий|без гарантий~ui',
    'не сюда'        => '~не\s+сюда~ui',
    'движ для смелых'=> '~движ\s+для\s+смелых|для\s+смелых~ui',
    'можно проиграть'=> '~можно\s+(?:и\s+)?проиграть|можешь\s+проиграть|исход\s+в\s+обе\s+стороны~ui',
    'по-честному'    => '~по-честному~ui',
    'не заходи'      => '~не\s+заход[иь]т?е?,?\s+если|если\s+боишься\s+проиграть|если\s+боитесь\s+проиграть~ui',
];
const ЧУЖОЙ_ПРОЦЕНТ = '~к[эе]шб[эе]к|возврат|релоад|ревшар|revshare|revenue|партн[её]р|от\s+дохода|от\s+оборота|установк|засчит|вклад|годовых|быстрее\s+на|ошибок|игроков|конверси|шанс|отдач|rtp|банка|налог|комисси|засчитыва|вклад\s+в\s+отыгрыш|засчёт|зачёт|зачет|второй|третий|повторн|второе|реферал~ui';

$банкИмён = [];
$пулы = __DIR__ . '/data-v5/pools.json';
if (is_file($пулы)) {
    $d = json_decode((string) file_get_contents($пулы), true);
    foreach (['ИМЯ', 'ИМЯЖ'] as $к) { foreach (array_keys($d['общие']['банки'][$к] ?? []) as $и) { $банкИмён[$и] = true; } }
}

/** Проза страницы: список разделов, в каждом — массив фраз (абзацы, пункты, заголовки). */
function свПроза(string $html): array
{
    $html = (string) preg_replace('~<section\b.*?</section>~su', ' ', $html);
    $html = (string) preg_replace('~<(?:script|style)\b.*?</(?:script|style)>~su', ' ', $html);
    $разделы = []; $текущий = ['h2' => '', 'фразы' => []];
    if (preg_match_all('~<(h2|h3|p|li)\b[^>]*>(.*?)</\1>~su', $html, $m, PREG_SET_ORDER)) {
        foreach ($m as $x) {
            $т = html_entity_decode(trim((string) preg_replace('~\s+~u', ' ', strip_tags($x[2]))), ENT_QUOTES | ENT_HTML5, 'UTF-8');
            if ($т === '') { continue; }
            if ($x[1] === 'h2') {
                if ($текущий['фразы'] || $текущий['h2'] !== '') { $разделы[] = $текущий; }
                $текущий = ['h2' => $т, 'фразы' => []];
                continue;
            }
            $текущий['фразы'][] = $т;
        }
    }
    if ($текущий['фразы'] || $текущий['h2'] !== '') { $разделы[] = $текущий; }
    return $разделы;
}

function свСтраница(string $файл, array $банкИмён): array
{
    $html = (string) file_get_contents($файл);
    $разделы = свПроза($html);
    $всё = implode(' ', array_map(fn($р) => $р['h2'] . ' ' . implode(' ', $р['фразы']), $разделы));

    // Проценты пакета.
    $пакеты = [];
    if (preg_match_all('~(?<![\d.,])(\d{2,4})\s*%~u', $всё, $m, PREG_OFFSET_CAPTURE)) {
        foreach ($m[1] as [$v, $поз]) {
            $слева = mb_strtolower(substr($всё, max(0, $поз - 60), $поз - max(0, $поз - 60)));
            $справа = mb_strtolower(substr($всё, $поз, 40));
            if (preg_match(ЧУЖОЙ_ПРОЦЕНТ, $слева) || preg_match('~^\d*\s*%\s*(?:к[эе]шб|возврат|от\s+(?:дохода|оборота|проигр)|revshare|годовых|засчит|банка|партн)~ui', $справа)) { continue; }
            if ((int) $v < 15 || (int) $v > 1000) { continue; }
            $пакеты[(int) $v] = true;
        }
    }
    // Джекпоты в прозе.
    $джекпоты = [];
    if (preg_match_all('~(?<![\d.,])(\d{1,3}(?:\.\d)?)\s*(?:млн|миллион[а-яё]*)~u', $всё, $m, PREG_OFFSET_CAPTURE)) {
        foreach ($m[1] as [$v, $поз]) {
            $окно = mb_strtolower(substr($всё, max(0, $поз - 60), 120));
            if (preg_match('~джекпот|пул|приз|куш|сорва|выигр|потолок|максимум|макс\.|доход|заработ|вытащ|забра~ui', $окно)) {
                if (preg_match('~джекпот|пул|потолок|максимум|приз~ui', $окно)) { $джекпоты[(string) (float) $v] = true; }
            }
        }
    }
    // RTP.
    $rtp = [];
    if (preg_match_all('~(?:rtp|отдач[а-яё]*|возврат[а-яё]*)\D{0,20}?(\d{2}(?:\.\d)?)\s*%~ui', $всё, $m)) { foreach ($m[1] as $v) { $rtp[] = (float) $v; } }
    if (preg_match_all('~(\d{2}(?:\.\d)?)\s*%\s*(?:rtp|отдач|возврат)~ui', $всё, $m)) { foreach ($m[1] as $v) { $rtp[] = (float) $v; } }
    $rtp = array_values(array_unique(array_filter($rtp, fn($x) => $x >= 85 && $x <= 99.9)));
    // Сроки вывода.
    $сроки = [];
    if (preg_match_all('~(?:вывод[а-яё]*|выплат[а-яё]*|деньги|на\s+карту|cashout)[^.;!?]{0,45}?(?:за|около|до|от|в\s+течение|занимает|—)\s*(\d+(?:\s*[–-]\s*\d+)?)\s*(минут|мин\b|часа|часов|час\b|секунд|дня|дней)~ui', $всё, $m, PREG_SET_ORDER)) {
        foreach ($m as $x) { $сроки[preg_replace('~\s+~', '', $x[1]) . mb_substr($x[2], 0, 3)] = true; }
    }
    // Вейджер.
    $вейджер = [];
    if (preg_match_all('~(?:вейджер|вагер|отыгр[а-яё]*|оборот[а-яё]*)[^.]{0,25}?[xх×]\s?(\d{2})(?![\d%])~ui', $всё, $m)) { foreach ($m[1] as $v) { $вейджер[(int) $v] = true; } }
    // Мантры по разделам.
    $мантраМакс = 0; $мантрыВсего = 0;
    foreach ($разделы as $р) {
        $т = $р['h2'] . ' ' . implode(' ', $р['фразы']);
        foreach (МАНТРЫ as $имя => $re) {
            $n = preg_match_all($re, $т);
            $мантрыВсего += $n;
            if ($n > $мантраМакс) { $мантраМакс = $n; }
        }
    }
    // Короткие предложения-повторы.
    $короткие = [];
    foreach ($разделы as $р) {
        foreach ($р['фразы'] as $ф) {
            foreach (preg_split('~(?<=[.!?…])\s+~u', $ф) as $пр) {
                $чист = mb_strtolower(trim((string) preg_replace('~[^\p{L}\s]~u', '', $пр)));
                if ($чист === '') { continue; }
                $слов = count(preg_split('~\s+~u', $чист, -1, PREG_SPLIT_NO_EMPTY));
                if ($слов <= 3) { $короткие[$чист] = ($короткие[$чист] ?? 0) + 1; }
            }
        }
    }
    $короткиеМакс = $короткие ? max($короткие) : 0;
    // Обрывки без героя.
    $обрывки = 0; $примеры = [];
    foreach ($разделы as $р) {
        $былоИмя = (bool) preg_match('~\b(\p{Lu}[а-яё]{2,})\b~u', $р['h2'], $mm) && isset($банкИмён[$mm[1]]);
        foreach ($р['фразы'] as $ф) {
            foreach (preg_split('~(?<=[.!?…])\s+~u', $ф) as $пр) {
                if (preg_match_all('~\b(\p{Lu}[а-яё]{2,})\b~u', $пр, $mm)) {
                    foreach ($mm[1] as $w) { if (isset($банкИмён[$w])) { $былоИмя = true; } }
                }
                $слов = count(preg_split('~\s+~u', trim($пр), -1, PREG_SPLIT_NO_EMPTY));
                if ($слов > 12 || $слов < 2 || $былоИмя) { continue; }
                if (preg_match('~\d[\d\s]*\s*(?:₽|руб|к\b|тыс|млн)|\b(?:он|она|его|её|ему|ей)\b|\b(?:минут|часа|часов|секунд)\b~u', $пр)
                    && preg_match('~\b(?:вывел|вывела|закинул|закинула|прош[её]л|прошла|сел|села|забрал|снял|поднял|принёс|принесла|потратил|ушло|висело|лежало|светил[а-яё]*|показывал|плюс|минус|проиграл|слил|через|было|стало|оказалось|капнуло|пришло|упало|перерыв[а-яё]*|ждал|ждала)\b~ui', $пр)
                    && !preg_match('~^(?:если|можно|можешь|минус|плюс|честно|факт)~ui', trim($пр))) {
                    $обрывки++; if (count($примеры) < 3) { $примеры[] = mb_substr(trim($пр), 0, 60); }
                }
            }
        }
    }
    return [
        'package_uniq' => count($пакеты), 'packages' => implode('/', array_keys($пакеты)),
        'jackpot_uniq' => count($джекпоты), 'jackpots' => implode('/', array_keys($джекпоты)),
        'rtp_uniq' => count($rtp), 'rtp_spread' => $rtp ? round(max($rtp) - min($rtp), 1) : 0,
        'payout_uniq' => count($сроки),
        'mantra_max' => $мантраМакс, 'mantra_total' => $мантрыВсего,
        'short_dup_max' => $короткиеМакс,
        'fragments' => $обрывки, 'fragment_samples' => $примеры,
        'wager' => implode('/', array_keys($вейджер)),
    ];
}

$итог = [];
foreach ($папки as $папка) {
    $строки = [];
    foreach (СТРАНИЦЫ as $с) {
        $ф = "$папка/$с.html";
        if (!is_file($ф)) { continue; }
        $строки[$с] = свСтраница($ф, $банкИмён);
    }
    if (!$строки) { continue; }
    $ср = fn(string $к) => round(array_sum(array_column($строки, $к)) / count($строки), 2);
    $макс = fn(string $к) => max(array_column($строки, $к));
    $итог[basename($папка)] = [
        'страницы' => $строки,
        'package_uniq' => $ср('package_uniq'), 'jackpot_uniq' => $ср('jackpot_uniq'), 'rtp_spread' => $ср('rtp_spread'),
        'payout_uniq' => $ср('payout_uniq'), 'mantra_max' => $ср('mantra_max'), 'mantra_total' => $ср('mantra_total'),
        'short_dup_max' => $ср('short_dup_max'), 'fragments' => array_sum(array_column($строки, 'fragments')),
        'package_max' => $макс('package_uniq'), 'jackpot_max' => $макс('jackpot_uniq'), 'rtp_spread_max' => $макс('rtp_spread'),
        'wager' => implode('|', array_unique(array_filter(array_column($строки, 'wager')))),
    ];
}
if ($json) { echo json_encode($итог, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT), "\n"; exit; }
echo "| набор | пакет/стр (макс) | джекпот/стр (макс) | RTP разброс (макс) | сроков/стр | мантра макс/раздел | мантр/стр | короткий повтор | обрывков | вейджер |\n|---|---|---|---|---|---|---|---|---|---|\n";
foreach ($итог as $имя => $и) {
    printf("| %s | %.1f (%d) | %.1f (%d) | %.1f (%.1f) | %.1f | %.1f | %.0f | %.1f | %d | %s |\n", $имя, $и['package_uniq'], $и['package_max'], $и['jackpot_uniq'], $и['jackpot_max'], $и['rtp_spread'], $и['rtp_spread_max'], $и['payout_uniq'], $и['mantra_max'], $и['mantra_total'], $и['short_dup_max'], $и['fragments'], $и['wager']);
}
if ($поСтраницам) {
    foreach ($итог as $имя => $и) {
        echo "\n$имя\n| стр | пакеты | джекпоты | RTP | сроков | мантра макс | повтор | обрывки |\n|---|---|---|---|---|---|---|---|\n";
        foreach ($и['страницы'] as $с => $x) {
            printf("| %s | %s | %s | %d (%.1f) | %d | %d | %d | %d %s |\n", $с, $x['packages'], $x['jackpots'], $x['rtp_uniq'], $x['rtp_spread'], $x['payout_uniq'], $x['mantra_max'], $x['short_dup_max'], $x['fragments'], $x['fragment_samples'] ? '«' . implode('», «', $x['fragment_samples']) . '»' : '');
        }
    }
}
