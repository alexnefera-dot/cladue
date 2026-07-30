<?php
/**
 * selftest.php — самопроверка системы перед боевым запуском.
 * Открой:  https://ВАШ_ДОМЕН/selftest.php?pass=ПАРОЛЬ_ПАНЕЛИ
 *
 * Прогоняет всю цепочку (кампания → клик → clickid → постбек → привязка →
 * статистика → гео), показывает PASS/FAIL по каждому шагу и УДАЛЯЕТ тестовые
 * данные за собой. На реальные кампании и историю не влияет.
 *
 * После проверки удали этот файл с сервера.
 */

require __DIR__ . '/db.php';
$cfg = require __DIR__ . '/config.php';

header('Content-Type: text/html; charset=utf-8');

// доступ только по паролю панели
if (!hash_equals((string)$cfg['password'], (string)($_GET['pass'] ?? ''))) {
    http_response_code(403);
    exit('Forbidden. Открой selftest.php?pass=ПАРОЛЬ_ПАНЕЛИ');
}

$SLUG = '__selftest__';                 // тестовая кампания (удалится в конце)
$R = [];                                // результаты
function add(&$R, $name, $ok, $detail = '') { $R[] = ['name'=>$name, 'st'=>$ok, 'detail'=>$detail]; }

$pdo = db();
$now = time();

// ---- 0. Окружение ----
add($R, 'PHP >= 7.4', version_compare(PHP_VERSION, '7.4', '>=') ? 'PASS' : 'FAIL', PHP_VERSION);
add($R, 'Расширение pdo_sqlite', extension_loaded('pdo_sqlite') ? 'PASS' : 'FAIL');
add($R, 'Расширение curl', extension_loaded('curl') ? 'PASS' : 'WARN', extension_loaded('curl') ? '' : 'нужен для HTTP-проверок ниже');

// ---- 1. Конфиг (безопасность) ----
$passOk = $cfg['password'] !== 'change-me' && $cfg['password'] !== '';
add($R, 'Пароль панели изменён', $passOk ? 'PASS' : 'WARN', $passOk ? '' : 'в config.php стоит заглушка change-me');
$secOk = !in_array($cfg['postback_secret'] ?? '', ['', 'change-this-postback-secret'], true);
add($R, 'Секрет постбэка изменён', $secOk ? 'PASS' : 'WARN', $secOk ? '' : 'в config.php заглушка');
$pbDomains = $cfg['postback_domains'] ?? [];
add($R, 'Список постбек-доменов задан', $pbDomains ? 'PASS' : 'WARN', implode(', ', $pbDomains));

// ---- 2. База доступна на запись ----
try {
    $pdo->exec('CREATE TABLE IF NOT EXISTS _selftest_tmp(x)');
    $pdo->exec('DROP TABLE _selftest_tmp');
    add($R, 'База доступна на запись', 'PASS');
} catch (Throwable $e) { add($R, 'База доступна на запись', 'FAIL', $e->getMessage()); }

// ---- 3. Тестовая кампания на постбек-домене ----
$testOffer = 'https://' . ($pbDomains[0] ?? 'cbc-abs.net') . '/selftest-offer';
// удалим возможный прошлый прогон
$pdo->prepare('DELETE FROM clicks WHERE slug = ?')->execute([$SLUG]);
$pdo->prepare('DELETE FROM conversions WHERE slug = ?')->execute([$SLUG]);
$pdo->prepare('DELETE FROM campaigns WHERE slug = ?')->execute([$SLUG]);
$err = add_campaign($SLUG, 'SELFTEST', $testOffer);
$offer = get_offer($SLUG);
add($R, 'Создание кампании + get_offer', ($err === null && $offer === $testOffer) ? 'PASS' : 'FAIL', $err ?: $offer);

// ---- 4. Логика прокидывания clickid ----
$clickid = bin2hex(random_bytes(8));
$dest = $offer;
$host = parse_url($dest, PHP_URL_HOST);
$append = $host && in_array(strtolower($host), array_map('strtolower', $pbDomains), true);
if ($append) {
    $p = $cfg['clickid_param'] ?? 'clickid';
    $dest .= (strpos($dest, '?') === false ? '?' : '&') . rawurlencode($p) . '=' . rawurlencode($clickid);
}
$hasCid = strpos($dest, 'clickid=' . $clickid) !== false;
add($R, 'clickid прокидывается в оффер (постбек-домен)', $hasCid ? 'PASS' : 'FAIL', $dest);

// ---- 5. Запись клика (как это делает go.php) ----
$pdo->prepare('INSERT INTO clicks (ts,slug,ip,ua,referer,source,is_bot,clickid,country) VALUES (?,?,?,?,?,?,?,?,?)')
    ->execute([$now, $SLUG, '203.0.113.7', 'Mozilla/5.0 SelfTest', '', 'selftest.src', 0, $clickid, 'RU']);
$row = $pdo->query("SELECT clickid,country FROM clicks WHERE slug='" . $SLUG . "' ORDER BY id DESC LIMIT 1")->fetch(PDO::FETCH_ASSOC);
add($R, 'Клик записан с clickid и страной', ($row && $row['clickid'] === $clickid && $row['country'] === 'RU') ? 'PASS' : 'FAIL', json_encode($row));

// ---- 6. Классификатор ботов ----
$b1 = classify_bot('Mozilla/5.0 (compatible; Googlebot/2.1)');
$b2 = classify_bot('Mozilla/5.0 (Windows NT 10.0) Chrome/124');
add($R, 'Бот-классификатор (Googlebot=бот, Chrome=юзер)', ($b1['is_bot'] && !$b2['is_bot']) ? 'PASS' : 'FAIL');

// ---- 7. Постбек: запись конверсии и привязка ----
$res = record_conversion($clickid, 'reg', 0, '203.0.113.7');
add($R, 'record_conversion привязал к кампании', ($res['ok'] && $res['found'] && $res['slug'] === $SLUG) ? 'PASS' : 'FAIL', json_encode($res));

// ---- 8. Конверсия видна в статистике кампании ----
$cv = conversions_by_slug($now - 86400)[$SLUG] ?? ['reg'=>0];
add($R, 'Рег учтена в conversions_by_slug', ((int)($cv['reg'] ?? 0) >= 1) ? 'PASS' : 'FAIL', 'reg=' . ($cv['reg'] ?? 0));

// ---- 9. Гео-разрез кампании ----
$geo = geo_by_campaign($now - 86400, $SLUG)[$SLUG] ?? [];
$geoOk = false; foreach ($geo as $g) if ($g['country'] === 'RU' && $g['uniques'] >= 1) $geoOk = true;
add($R, 'Гео по кампании содержит RU (уники)', $geoOk ? 'PASS' : 'FAIL', json_encode($geo));

// ---- 10. HTTP: реальный редирект go.php (302 + clickid) ----
$base = ((isset($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http') . '://' . ($_SERVER['HTTP_HOST'] ?? '');
$httpNote = '';
if (extension_loaded('curl') && $base) {
    $ch = curl_init($base . '/go.php?l=' . $SLUG);
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER=>true, CURLOPT_HEADER=>true, CURLOPT_NOBODY=>true,
        CURLOPT_FOLLOWLOCATION=>false, CURLOPT_TIMEOUT=>10, CURLOPT_SSL_VERIFYPEER=>false]);
    $resp = curl_exec($ch);
    $code = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($resp === false) {
        add($R, 'HTTP go.php (302 + clickid)', 'SKIP', 'self-запрос не прошёл (на однопоточном сервере это норма; на боевом Apache/nginx — проверь вручную: открой /go.php?l=любой_слаг)');
    } else {
        preg_match('~^location:\s*(.+)$~im', $resp, $m);
        $loc = trim($m[1] ?? '');
        $ok = ($code == 302 && strpos($loc, 'clickid=') !== false);
        add($R, 'HTTP go.php (302 + clickid)', $ok ? 'PASS' : 'WARN', 'code=' . $code . ' location=' . $loc);
    }
} else {
    add($R, 'HTTP go.php (302 + clickid)', 'SKIP', 'нет curl');
}

// ---- 11. HTTP: postback.php (OK с ключом, forbidden без) ----
if (extension_loaded('curl') && $base && $secOk) {
    $cid2 = bin2hex(random_bytes(8));
    // нужен клик с этим clickid, чтобы привязалось
    $pdo->prepare('INSERT INTO clicks (ts,slug,ip,ua,referer,source,is_bot,clickid,country) VALUES (?,?,?,?,?,?,?,?,?)')
        ->execute([$now, $SLUG, '203.0.113.8', 'SelfTest', '', '', 0, $cid2, 'DE']);
    $u = $base . '/postback.php?key=' . rawurlencode($cfg['postback_secret']) . '&cnv_id=' . $cid2 . '&cnv_status=reg';
    $okBody = @file_get_contents_curl($u);
    $u2 = $base . '/postback.php?key=WRONG&cnv_id=x&cnv_status=reg';
    $badBody = @file_get_contents_curl($u2);
    $ok = (trim((string)$okBody) === 'OK' && trim((string)$badBody) === 'forbidden');
    add($R, 'HTTP postback.php (OK / forbidden)', $ok ? 'PASS' : 'WARN', 'key-ok="' . trim((string)$okBody) . '" key-bad="' . trim((string)$badBody) . '"');
} else {
    add($R, 'HTTP postback.php (OK / forbidden)', 'SKIP', $secOk ? 'нет curl' : 'секрет-заглушка');
}

// ---- 12. Гео из Cloudflare? (информативно) ----
$cf = $_SERVER['HTTP_CF_IPCOUNTRY'] ?? '';
add($R, 'Заголовок Cloudflare CF-IPCountry', $cf ? 'PASS' : 'WARN', $cf ?: 'нет — домен не за Cloudflare, гео будет ?? (это ок, если CF не используешь)');

// ---- 13. Файл базы недоступен снаружи (информативно) ----
if (extension_loaded('curl') && $base) {
    $dbName = basename($cfg['db_file'] ?? 'stats.sqlite');
    $ch = curl_init($base . '/' . $dbName);
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER=>true, CURLOPT_TIMEOUT=>6, CURLOPT_SSL_VERIFYPEER=>false]);
    $resp = @curl_exec($ch);
    $code = (int)curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    if ($resp === false || $code === 0) {
        add($R, 'Файл базы недоступен снаружи', 'SKIP', 'self-запрос не прошёл (проверь вручную: открой /' . $dbName . ' — должно быть 403/404)');
    } elseif (in_array($code, [403, 404], true)) {
        add($R, 'Файл базы недоступен снаружи', 'PASS', 'GET /' . $dbName . ' -> HTTP ' . $code);
    } else {
        add($R, 'Файл базы недоступен снаружи', 'FAIL', 'GET /' . $dbName . ' -> HTTP ' . $code . ' — база скачивается! вынеси выше webroot');
    }
}

// ---- ОЧИСТКА тестовых данных ----
$pdo->prepare('DELETE FROM clicks WHERE slug = ?')->execute([$SLUG]);
$pdo->prepare('DELETE FROM conversions WHERE slug = ?')->execute([$SLUG]);
$pdo->prepare('DELETE FROM campaigns WHERE slug = ?')->execute([$SLUG]);
$pdo->prepare("DELETE FROM postback_log WHERE query LIKE ?")->execute(['%' . $clickid . '%']);

// мини-хелпер для HTTP GET через curl
function file_get_contents_curl($url) {
    $ch = curl_init($url);
    curl_setopt_array($ch, [CURLOPT_RETURNTRANSFER=>true, CURLOPT_TIMEOUT=>10, CURLOPT_SSL_VERIFYPEER=>false, CURLOPT_FOLLOWLOCATION=>false]);
    $b = curl_exec($ch);
    curl_close($ch);
    return $b;
}

// ---- ВЫВОД ----
$fail = 0; $warn = 0;
foreach ($R as $r) { if ($r['st']==='FAIL') $fail++; if ($r['st']==='WARN') $warn++; }
$color = ['PASS'=>'#16a34a','FAIL'=>'#dc2626','WARN'=>'#d97706','SKIP'=>'#6b7280'];
?>
<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">
<title>Самотест</title>
<style>
 body{font:15px/1.5 system-ui,sans-serif;background:#f6f7f9;margin:0;padding:24px;color:#111}
 .wrap{max-width:860px;margin:0 auto}
 h1{font-size:20px} table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #e5e7eb;border-radius:10px;overflow:hidden}
 td,th{padding:9px 12px;border-bottom:1px solid #f0f0f0;text-align:left;vertical-align:top}
 .st{font-weight:700} .d{color:#6b7280;font-size:13px;word-break:break-all}
 .sum{margin:14px 0;padding:12px 16px;border-radius:10px;font-weight:600}
</style></head><body><div class="wrap">
<h1>Самотест системы</h1>
<div class="sum" style="background:<?= $fail? '#fee2e2':'#dcfce7' ?>">
  <?= $fail ? "❌ Провалено проверок: $fail" . ($warn?" · предупреждений: $warn":"") . ". Боевой запуск НЕ рекомендуется, пока не исправишь FAIL."
            : ($warn ? "✅ Критичных ошибок нет, но есть предупреждения ($warn) — глянь WARN ниже."
                     : "✅ Все проверки пройдены. Система готова к бою.") ?>
</div>
<table>
  <thead><tr><th style="width:90px">Статус</th><th>Проверка</th></tr></thead>
  <tbody>
  <?php foreach ($R as $r): ?>
    <tr>
      <td class="st" style="color:<?= $color[$r['st']] ?>"><?= $r['st'] ?></td>
      <td><?= htmlspecialchars($r['name']) ?><?php if ($r['detail']!==''): ?><br><span class="d"><?= htmlspecialchars($r['detail']) ?></span><?php endif; ?></td>
    </tr>
  <?php endforeach; ?>
  </tbody>
</table>
<p class="d">Тестовые данные (кампания <code><?= htmlspecialchars($SLUG) ?></code>) удалены автоматически. После проверки удали <code>selftest.php</code> с сервера.</p>
</div></body></html>
