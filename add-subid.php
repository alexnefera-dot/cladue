<?php
/**
 * add-subid.php — дописать метку {clickid} в ссылки офферов одной партнёрки.
 *
 * Зачем. Партнёрка возвращает наш идентификатор в постбеке только если он
 * пришёл в её трекинговой ссылке под её же именем параметра. Имя у каждой
 * своё (source_id, sub_id, subid...), поэтому место метки указывается прямо
 * в ссылке кампании — go.php подставит туда клик. Руками править десятки
 * кампаний долго и легко пропустить одну, а пропущенная кампания тихо льёт
 * конверсии без метки.
 *
 * Запуск на сервере, из каталога панели:
 *   php add-subid.php velvet-ray.com source_id            # предпросмотр
 *   php add-subid.php velvet-ray.com source_id --apply    # применить
 *
 * Трогает только кампании, чей оффер ведёт на указанный домен (и его
 * поддомены) и у которых параметра ещё нет. Каждое изменение пишется в
 * offer_history, после правки пересобирается offers.php для go.php.
 */

/**
 * Дописать параметр к одной ссылке.
 * Возвращает новую строку либо null, если строку трогать не надо.
 * Хвост веса ротации ("| 3") сохраняется как есть.
 */
function subid_patch_line($line, $domain, $param) {
    $raw = trim((string)$line);
    if ($raw === '' || $raw[0] === '#') return null;

    $weight = '';
    if (preg_match('~^(.*?)(\s*\|\s*\d+\s*)$~', $raw, $m)) {
        $raw    = trim($m[1]);
        $weight = $m[2];
    }

    // якорь (#...) отрезаем и возвращаем в конец: параметр, дописанный после
    // решётки, в запрос не попадёт — партнёрка его просто не увидит.
    $frag = '';
    if (($h = strpos($raw, '#')) !== false) { $frag = substr($raw, $h); $raw = substr($raw, 0, $h); }

    $host = strtolower((string)parse_url($raw, PHP_URL_HOST));
    if ($host === '') return null;
    // домен покрывает свои поддомены, но не похожие имена:
    // velvet-ray.com совпадёт с go.velvet-ray.com и не совпадёт с notvelvet-ray.com
    if ($host !== $domain && substr($host, -strlen($domain) - 1) !== '.' . $domain) return null;

    if (preg_match('~[?&]' . preg_quote($param, '~') . '=~i', $raw)) return null;  // уже есть

    $sep = (strpos($raw, '?') === false) ? '?' : '&';
    if ($sep === '?' && preg_match('~^https?://[^/?#]+$~', $raw)) $raw .= '/';
    return $raw . $sep . $param . '={clickid}' . $frag . $weight;
}

if (defined('SUBID_LIB_ONLY')) return;   // для тестов: подключить только функцию

if (php_sapi_name() !== 'cli') { http_response_code(403); exit("CLI only\n"); }

$domain = strtolower(trim($argv[1] ?? ''));
$param  = trim($argv[2] ?? '');
$apply  = in_array('--apply', $argv, true);

if (!preg_match('~^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$~', $domain) || !preg_match('~^[A-Za-z0-9_]+$~', $param)) {
    exit("Использование: php add-subid.php ДОМЕН ПАРАМЕТР [--apply]\n"
       . "Пример:        php add-subid.php velvet-ray.com source_id --apply\n");
}

require __DIR__ . '/db.php';

$pdo  = db();
$rows = $pdo->query('SELECT id, slug, offer_url FROM campaigns ORDER BY slug')->fetchAll(PDO::FETCH_ASSOC);

$plan = [];   // [id, slug, старый текст, новый текст]
$ready = 0;   // кампании на этом домене, где метка уже стоит

foreach ($rows as $c) {
    $lines = preg_split('~\R~', (string)$c['offer_url']);
    $out   = $lines;
    $hit   = false;
    $onDomain = false;

    foreach ($lines as $i => $line) {
        $host = strtolower((string)parse_url(trim(preg_replace('~\s*\|\s*\d+\s*$~', '', (string)$line)), PHP_URL_HOST));
        if ($host === $domain || ($host !== '' && substr($host, -strlen($domain) - 1) === '.' . $domain)) $onDomain = true;

        $new = subid_patch_line($line, $domain, $param);
        if ($new !== null) { $out[$i] = $new; $hit = true; }
    }

    if ($hit) $plan[] = [$c['id'], $c['slug'], $c['offer_url'], implode("\n", $out)];
    elseif ($onDomain) $ready++;
}

printf("Домен: %s, параметр: %s\n", $domain, $param);
printf("Всего кампаний: %d | на этом домене метка уже стоит: %d | под правку: %d\n\n",
    count($rows), $ready, count($plan));

foreach ($plan as $p) {
    echo "  " . $p[1] . "\n";
    foreach (preg_split('~\R~', $p[3]) as $k => $l) {
        $was = preg_split('~\R~', $p[2])[$k] ?? '';
        if (trim($was) !== trim($l)) echo "      -> " . trim($l) . "\n";
    }
}

if (!$plan) { echo "Менять нечего.\n"; exit; }

if (!$apply) {
    echo "\nЭто предпросмотр, база не тронута. Применить: добавьте --apply\n";
    exit;
}

$now  = time();
$up   = $pdo->prepare('UPDATE campaigns SET offer_url=?, updated_at=? WHERE id=?');
$hist = $pdo->prepare('INSERT INTO offer_history (slug,old_url,new_url,ts) VALUES (?,?,?,?)');

$pdo->beginTransaction();
foreach ($plan as $p) {
    $up->execute([$p[3], $now, $p[0]]);
    $hist->execute([$p[1], $p[2], $p[3], $now]);
}
$pdo->commit();

$n = offers_cache_rebuild();
printf("\nОбновлено кампаний: %d. Офферов в кэше go.php: %s\n", count($plan), $n < 0 ? 'кэш не трогали' : $n);
