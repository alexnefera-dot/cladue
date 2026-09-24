<?php
/**
 * api.php — выгрузка кликов и конверсий для внешней аналитики.
 *
 * Два эндпоинта из общего контракта на восемь (остальные шесть — на стороне
 * системы запусков, трекер их данных не знает):
 *
 *   GET /v1/clicks?date_from=2026-09-14&date_to=2026-09-15&limit=1000
 *   GET /v1/conversions?date_from=…&date_to=…&event=fd&cursor=…
 *
 * Авторизация: Authorization: Bearer <token> (или X-Api-Token).
 * Время — ISO 8601 со смещением, пояс Europe/Kyiv, как требует контракт.
 *
 * Панели не касается: своя авторизация, без сессий и кук, не трогает
 * panel_cache, maybe_cleanup и heartbeat. go.php по-прежнему не знает про MySQL.
 *
 * Нагрузка. Это первый компонент, который ходит в MySQL по внешнему запросу,
 * поэтому: пагинация только курсором (OFFSET на 300k строк деградирует),
 * потолок строк и диапазона дат, лимит запросов в минуту и лимит одновременных
 * выгрузок. Сервер не должен лечь из-за выгрузки — это дороже самой выгрузки.
 */

$cfg = require __DIR__ . '/config.php';

header('Content-Type: application/json; charset=utf-8');
header('Cache-Control: no-store');
header('X-Content-Type-Options: nosniff');

/** Ответ-ошибка по контракту и выход. */
function api_fail($httpCode, $code, $message) {
    http_response_code($httpCode);
    echo json_encode(['error' => ['code' => $code, 'message' => $message]],
                     JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

// ---------- 1. Только GET ----------
if (($_SERVER['REQUEST_METHOD'] ?? 'GET') !== 'GET') {
    api_fail(405, 'invalid_param', 'only GET is supported');
}

// ---------- 2. Авторизация ----------
// Apache в режиме CGI часто не пробрасывает заголовок Authorization в PHP —
// поэтому смотрим ещё и переменную из .htaccess, и запасной X-Api-Token.
$auth = $_SERVER['HTTP_AUTHORIZATION']
     ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION']
     ?? '';
$token = '';
if (stripos($auth, 'bearer ') === 0) {
    $token = trim(substr($auth, 7));
} elseif (!empty($_SERVER['HTTP_X_API_TOKEN'])) {
    $token = trim((string)$_SERVER['HTTP_X_API_TOKEN']);
}

$tokens = $cfg['api_tokens'] ?? [];
$label  = null;
if ($token !== '') {
    foreach ($tokens as $name => $secret) {
        // hash_equals — сравнение за постоянное время: обычное === утекает
        // длину совпавшего префикса и позволяет подбирать токен по символу.
        if (is_string($secret) && $secret !== '' && hash_equals($secret, $token)) {
            $label = (string)$name;
            break;
        }
    }
}
if ($label === null) api_fail(401, 'unauthorized', 'invalid or missing token');

// ---------- 3. Лимит запросов в минуту ----------
$cacheDir = __DIR__ . '/cache';
if (!is_dir($cacheDir)) @mkdir($cacheDir, 0775, true);

$ratePerMin = (int)($cfg['api_rate_per_min'] ?? 0);
if ($ratePerMin > 0) {
    $rateFile = $cacheDir . '/.api_rate_' . preg_replace('~[^\w.-]~', '_', $label);
    $minute   = (int)floor(time() / 60);
    $cur      = @json_decode((string)@file_get_contents($rateFile), true);
    if (!is_array($cur) || ($cur['m'] ?? null) !== $minute) $cur = ['m' => $minute, 'n' => 0];
    $cur['n']++;
    @file_put_contents($rateFile, json_encode($cur), LOCK_EX);
    if ($cur['n'] > $ratePerMin) {
        header('Retry-After: ' . (60 - (time() % 60)));
        api_fail(429, 'rate_limited', "over $ratePerMin requests per minute");
    }
}

// ---------- 4. Лимит одновременных выгрузок ----------
// Неблокирующий flock по слотам: если все заняты — сразу 429, а не ожидание.
// Иначе десяток параллельных запросов выест пул соединений MySQL, и вместе с
// ним лягут панель и приём постбеков.
$maxConc = max(1, (int)($cfg['api_max_concurrent'] ?? 2));
$slotFh  = null;
for ($i = 0; $i < $maxConc; $i++) {
    $fh = @fopen($cacheDir . '/.api_slot_' . $i, 'c');
    if ($fh && @flock($fh, LOCK_EX | LOCK_NB)) { $slotFh = $fh; break; }
    if ($fh) fclose($fh);
}
if ($slotFh === null) {
    header('Retry-After: 5');
    api_fail(429, 'rate_limited', "more than $maxConc concurrent exports");
}
register_shutdown_function(function () use ($slotFh) {
    @flock($slotFh, LOCK_UN); @fclose($slotFh);
});

// ---------- 5. Разбор параметров ----------
require_once __DIR__ . '/db.php';   // задаёт Europe/Kyiv и для PHP, и для MySQL-сессии

$ep = (string)($_GET['ep'] ?? '');
if (!in_array($ep, ['clicks', 'conversions'], true)) {
    api_fail(404, 'invalid_param', 'unknown endpoint');
}

$tz = new DateTimeZone('Europe/Kyiv');

/** Начало суток по киевскому времени (unix). */
function api_day_start($date, DateTimeZone $tz) {
    $d = DateTime::createFromFormat('!Y-m-d', $date, $tz);
    $e = DateTime::getLastErrors();
    // getLastErrors() в PHP 8.2+ возвращает false, когда ошибок нет
    if (!$d || (is_array($e) && ($e['warning_count'] || $e['error_count']))) return null;
    return $d->getTimestamp();
}

$dFrom = (string)($_GET['date_from'] ?? '');
$dTo   = (string)($_GET['date_to']   ?? '');
if ($dFrom === '' || $dTo === '') {
    api_fail(400, 'invalid_param', 'date_from and date_to are required (YYYY-MM-DD)');
}
$from = api_day_start($dFrom, $tz);
$to   = api_day_start($dTo,   $tz);
if ($from === null || $to === null) {
    api_fail(400, 'invalid_param', 'dates must be YYYY-MM-DD');
}
$to += 86400;                       // границы включительно: весь день date_to
if ($to <= $from) api_fail(400, 'invalid_range', 'date_to earlier than date_from');

$maxDays = max(1, (int)($cfg['api_max_range_days'] ?? 92));
if (($to - $from) > $maxDays * 86400) {
    api_fail(400, 'invalid_range', "range longer than $maxDays days");
}

$limit = (int)($_GET['limit'] ?? 1000);
if ($limit < 1 || $limit > 5000) $limit = $limit < 1 ? 1000 : 5000;

// Курсор keyset по паре (ts, id). OFFSET не используем: контракт его запрещает,
// и на глубоких страницах он деградирует квадратично.
$curTs = $from; $curId = 0;
if (!empty($_GET['cursor'])) {
    $raw = base64_decode(strtr((string)$_GET['cursor'], '-_', '+/'), true);
    $c   = $raw === false ? null : json_decode($raw, true);
    if (!is_array($c) || !isset($c['ts'], $c['id'])) {
        api_fail(400, 'invalid_param', 'malformed cursor');
    }
    $curTs = max($from, (int)$c['ts']);
    $curId = (int)$c['id'];
}

$subFilter = trim((string)($_GET['subdomain'] ?? ''));

// Ботов по умолчанию НЕ фильтруем. Контракт требует сырые строки, а молчаливый
// отброс — это ровно тот случай, когда «данные придут, расчёт пройдёт, результат
// будет неверным»: по ответу не видно, что часть строк не отдали. Отдаём флаг
// is_bot в каждой строке, а решение оставляем аналитику.
$uaClass = strtolower(trim((string)($_GET['ua_class'] ?? 'all')));
if (!in_array($uaClass, ['all', 'human', 'bot'], true)) {
    api_fail(400, 'invalid_param', 'ua_class must be all, human or bot');
}
// Параметр event означает разное у двух эндпоинтов: у конверсий это рега/ФД,
// у кликов — переход/показ преленда/клик по нему. Проверяем по месту.
$evFilter = strtolower(trim((string)($_GET['event'] ?? '')));
if ($evFilter !== '') {
    $allowed = $ep === 'conversions' ? ['reg', 'fd'] : ['direct', 'view', 'click'];
    if (!in_array($evFilter, $allowed, true)) {
        api_fail(400, 'invalid_param', 'event must be ' . implode(', ', $allowed));
    }
}

// ---------- 6. Запрос ----------
// Фильтр по ts и сортировка по (ts, id) снимаются с одного индекса: вторичный
// индекс InnoDB физически содержит первичный ключ, то есть idx_ts это (ts, id).
// Без этого база отсортировала бы весь диапазон в памяти.
$pdo  = db();
$args = [$from, $to, $curTs, $curTs, $curId];
$keys = 'ts >= ? AND ts < ? AND (ts > ? OR (ts = ? AND id > ?))';

if ($ep === 'clicks') {
    $sql = "SELECT id, ts, clickid, source, referer, country, slug, lp, is_bot, event
            FROM clicks
            WHERE $keys";
    // фильтр по событию (direct / view / click) — см. API.md
    if ($evFilter !== '') {
        // NULL — строки, записанные до появления колонки: обычные переходы
        $sql .= $evFilter === 'direct'
            ? " AND (event IS NULL OR event = 'direct')"
            : ' AND event = ?';
        if ($evFilter !== 'direct') $args[] = $evFilter;
    }
    if ($uaClass === 'human') $sql .= ' AND is_bot = 0';
    if ($uaClass === 'bot')   $sql .= ' AND is_bot = 1';
    if ($subFilter !== '') { $sql .= ' AND source = ?'; $args[] = strtolower($subFilter); }
} else {
    $sql = "SELECT id, ts, clickid, status, slug, sub, ref, country, lp, linked_at
            FROM conversions
            WHERE $keys";
    if ($subFilter !== '') { $sql .= ' AND sub = ?'; $args[] = strtolower($subFilter); }
    if ($evFilter !== '') {
        // reg/fd — нормализованные имена контракта; в базе лежит сырое имя
        // события от партнёрки, поэтому разворачиваем в список синонимов.
        $raw = $evFilter === 'reg'
            ? ['reg', 'registration', 'lead']
            : ['dep', 'deposit', 'sale', 'ftd', 'purchase'];
        $sql .= ' AND status IN (' . implode(',', array_fill(0, count($raw), '?')) . ')';
        foreach ($raw as $r) $args[] = $r;
    }
}
$sql .= ' ORDER BY ts, id LIMIT ' . ($limit + 1);   // +1 — узнать, есть ли следующая страница

$st = $pdo->prepare($sql);
$st->execute($args);

// ---------- 7. Потоковый ответ ----------
// Строки отдаём по одной, не собирая в память: месяц выгрузки — это сотни
// тысяч строк, fetchAll() на них съел бы memory_limit.
$t0 = microtime(true);

/** unix -> ISO 8601 со смещением, Europe/Kyiv. */
function api_at($ts, DateTimeZone $tz) {
    if (!$ts) return null;
    return (new DateTime('@' . (int)$ts))->setTimezone($tz)->format('c');
}
/** Пустая строка — это отсутствие значения, а не значение. Контракт требует null. */
function api_str($v) {
    $v = trim((string)$v);
    return $v === '' ? null : $v;
}
/** Сырое имя события от партнёрки -> reg / fd по классификации панели. */
function api_event($status) {
    $s = strtolower(trim((string)$status));
    if (in_array($s, ['reg', 'registration', 'lead'], true)) return 'reg';
    if (in_array($s, ['dep', 'deposit', 'sale', 'ftd', 'purchase'], true)) return 'fd';
    return null;                     // неизвестное событие: пусть аналитик увидит его в event_raw
}
/** Путь страницы из полного URL реферера (глубина /ru выводится из него). */
function api_path($url) {
    $u = trim((string)$url);
    if ($u === '') return null;
    $p = parse_url($u, PHP_URL_PATH);
    return ($p === null || $p === false || $p === '') ? null : $p;
}

echo '{"data":[';

$n = 0; $last = null; $more = false; $first = true;
while ($row = $st->fetch(PDO::FETCH_ASSOC)) {
    if ($n >= $limit) { $more = true; break; }     // это та самая +1-я строка
    if ($ep === 'clicks') {
        $out = [
            'at'        => api_at($row['ts'], $tz),
            'clickid'   => api_str($row['clickid']),
            'subdomain' => api_str($row['source']),
            'referer'   => api_str($row['referer']),
            'country'   => api_str($row['country']),
            'campaign'  => api_str($row['slug']),
            // Точка входа из поиска. Приходит параметром ?lp= от дор-движка:
            // из реферера её не получить — он показывает страницу, С КОТОРОЙ ушли.
            'landing_path' => api_str($row['lp']),
            // Страница, с которой ушли. Считается из реферера, отдаётся отдельным
            // именем, чтобы её не приняли за landing_path.
            'exit_path' => api_path($row['referer']),
            // Классификация по User-Agent на момент клика (подстроки бот-сигнатур).
            'is_bot'    => (bool)$row['is_bot'],
            // direct — переход сразу на оффер; view — показан преленд;
            // click — нажата кнопка на преленде (тот же clickid, что у view).
            // Один посетитель на кампании с прелендом даёт view + click:
            // считать переходом нужно view, иначе трафик удвоится.
            'event'     => api_str($row['event']) ?? 'direct',
        ];
    } else {
        $ev = api_event($row['status']);
        $out = [
            'at'        => api_at($row['ts'], $tz),
            'event'     => $ev,
            'event_raw' => api_str($row['status']),   // если партнёрка пришлёт новое событие — видно, а не «other»
            'clickid'   => api_str($row['clickid']),
            'subdomain' => api_str($row['sub']),
            'referer'   => api_str($row['ref']),
            'country'   => api_str($row['country']),
            'campaign'  => api_str($row['slug']),
            'landing_path' => api_str($row['lp']),
            'exit_path' => api_path($row['ref']),
            // Партнёрка суммы не присылает, а отмену депозита не присылает вовсе.
            // Отдаём честный null, а не выдуманный 0 / approved.
            'payout'    => null,
            'status'    => null,
            // Момент, когда конверсия связалась с кликом. Заполнен — строка
            // финальная и при повторном запросе не изменится.
            'linked_at' => api_at($row['linked_at'], $tz),
        ];
    }
    echo ($first ? '' : ',') , json_encode($out, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    $first = false;
    $last  = ['ts' => (int)$row['ts'], 'id' => (int)$row['id']];
    $n++;
}

$nextCursor = ($more && $last)
    ? rtrim(strtr(base64_encode(json_encode($last)), '+/', '-_'), '=')
    : null;

// stable_until — время последнего импорта. Всё, что раньше него, уже связано
// с кликами и при повторном запросе того же диапазона вернётся без изменений.
// Свежие конверсии ещё могут дозаписать subdomain, когда клик доедет из лога.
$stable = null;
try { $stable = (int)meta_get('last_import', 0) ?: null; } catch (Throwable $e) {}

echo '],"meta":' , json_encode([
    'count'        => $n,
    'next_cursor'  => $nextCursor,
    'generated_at' => api_at(time(), $tz),
    'stable_until' => api_at($stable, $tz),
    'timezone'     => 'Europe/Kyiv',
], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) , '}';

// ---------- 8. Тонкий лог обращений ----------
// Видно, кто и сколько тянет. С обрезкой по размеру: незакрытый лог уже
// однажды вырос до полутора гигабайт и забил диск.
$logLine = sprintf("%s\t%s\t%s\t%s..%s\t%d\t%dms\n",
    date('c'), $label, $ep, $dFrom, $dTo, $n, (int)round((microtime(true) - $t0) * 1000));
$apiLog = $cacheDir . '/api.log';
if (@filesize($apiLog) > 5 * 1024 * 1024) @unlink($apiLog);
@file_put_contents($apiLog, $logLine, FILE_APPEND | LOCK_EX);
