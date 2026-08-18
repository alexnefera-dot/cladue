<?php
declare(strict_types=1);

/**
 * Замер ПРИЁМОВ, а не параметров.
 *
 *   php engine/priyomy-obzor.php <наш.html> <эталон.html>
 *
 * Приёмочный шлюз из 55 полей меряет плотности и доли. Он проходится
 * целиком на странице, где ни одного приёма образца нет: карточки слотов
 * лежат в <div>, а NicheLexicon::prose() читает только <p> и <li>, поэтому
 * семнадцать упоминаний студий у образца считаются как ноль. Отзыв с именем,
 * возрастом и звёздами не попадает под reviews_rated: тот ищет разметку
 * schema.org либо формулу «Имя / дата / оценка». Звезда ★ (U+2605) входит в
 * диапазон эмодзи, поэтому тридцать звёзд в отзывах и тридцать декоративных
 * значков в заголовках дают движку одно и то же число.
 *
 * Этот счётчик смотрит на устройство страницы: сколько карточек, отзывов с
 * оценкой, значков в заголовках, повторов таблицы по валютам и в каком
 * порядке раскрывается бренд.
 */

$our = $argv[1] ?? '';
$ref = $argv[2] ?? '';
if ($our === '' || $ref === '') {
    fwrite(STDERR, "usage: php priyomy-obzor.php <наш.html> <эталон.html>\n");
    exit(1);
}

/** @return array<string,int|string> */
function priyomy(string $raw): array
{
    $body = $raw;
    // если это целая страница — берём статейную часть
    $a = strpos($body, '<!-- INTRO / OFFICIAL -->');
    $b = strpos($body, '<!-- FLOATING WIDGETS -->');
    if ($a !== false && $b !== false) { $body = substr($body, $a, $b - $a); }

    $noTags = preg_replace('~<[^>]+>~', ' ', preg_replace('~(?is)<(script|style)\b.*?</\1>~', ' ', $body));
    $EMO = '[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]';

    // заголовки
    preg_match_all('~(?is)<h([23])\b[^>]*>(.*?)</h\1>~', $body, $hm, PREG_SET_ORDER);
    $heads = array_map(fn($m) => trim(preg_replace('~\s+~u', ' ', strip_tags($m[2]))), $hm);
    $emojiInH = 0;
    foreach ($heads as $h) { $emojiInH += preg_match_all('~' . $EMO . '~u', $h); }

    // карточка слота: имя + студия + RTP или джекпот рядом
    $slots = preg_match_all('~(?is)<(div|li|td)\b[^>]*>\s*(?:<[^>]+>\s*)*<b>[^<]{2,40}</b>.{0,120}?(RTP|Jackpot|Джекпот)~u', $body);
    if ($slots === 0) {
        $slots = preg_match_all('~(?is)class="[^"]*\bslot\b[^"]*"~', $body);
    }

    // отзыв: имя (с возрастом или без) рядом со звёздами
    $revs = preg_match_all('~(?is)class="[^"]*\brev\b[^"]*"~', $body);
    if ($revs === 0) {
        $revs = preg_match_all('~(?is)<b>[А-ЯЁ][а-яё]{2,}(?:,\s*\d{2})?</b>.{0,220}?[★☆]~u', $body);
    }

    // шапки таблиц и повтор по валютам
    preg_match_all('~(?is)<table\b.*?</table>~', $body, $tm);
    $headers = [];
    $cur = [];
    foreach ($tm[0] as $t) {
        preg_match_all('~(?is)<th\b[^>]*>(.*?)</th>~', $t, $th);
        $headers[] = mb_strtolower(implode('|', array_map(fn($x) => trim(strip_tags($x)), $th[1] ?? [])));
        $sym = [];
        foreach (['₽' => 'руб', '$' => 'usd', '€' => 'eur'] as $s => $n) {
            if (mb_strpos($t, $s) !== false) { $sym[] = $n; }
        }
        $cur[] = implode('+', $sym);
    }
    $byCurrency = 0;
    foreach (array_count_values(array_filter($headers)) as $h => $n) {
        if ($n < 2) { continue; }
        $seen = [];
        foreach ($headers as $i => $hh) {
            if ($hh === $h && $cur[$i] !== '') { $seen[$cur[$i]] = 1; }
        }
        if (count($seen) >= 2) { $byCurrency += $n; }
    }

    return [
        'карточек слотов'          => $slots,
        'отзывов с оценкой'        => $revs,
        'звёзд ★☆'                 => preg_match_all('~[★☆]~u', $noTags),
        'плашек-бейджей'           => preg_match_all(
            '~(?is)class="[^"]*(?:\bpill\b|\bbadge\b|-tag\b|-perk\b|-label\b|-chip\b|-mark\b)[^"]*"~',
            $body
        ),
        'эмодзи всего'             => preg_match_all('~' . $EMO . '~u', $noTags),
        'эмодзи в заголовках'      => $emojiInH,
        'таблиц'                   => count($tm[0]),
        'таблиц-повторов по валюте' => $byCurrency,
        'разных шапок'             => count(array_unique($headers)),
        'заголовков «бренд+ключ»'  => preg_match_all(
            '~(феникс|fenix|%brand_name_(?:ru|en)%)\s+\S~iu',
            implode("\n", $heads)
        ),
        'H2+H3'                    => count($heads),
    ];
}

$O = priyomy((string) file_get_contents($our));
$R = priyomy((string) file_get_contents($ref));

printf("%-28s %8s %8s\n", '', 'НАШЕ', 'ЭТАЛОН');
foreach ($R as $k => $v) {
    $o = $O[$k];
    $bad = is_int($v) && is_int($o) && ($v > 0 ? ($o < $v * 0.5 || $o > $v * 2) : $o > 2);
    printf("%-28s %8s %8s  %s\n", $k, (string) $o, (string) $v, $bad ? 'XXXX' : 'ok');
}
