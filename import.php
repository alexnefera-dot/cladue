<?php
/**
 * import.php — переливает накопленные клики из clicks.log в MySQL.
 *
 * Запускается по крону раз в 5 минут:
 *   /usr/bin/php /var/www/.../sitegrator.com/import.php
 *
 * Логика:
 *   1. Атомарно "забирает" текущий лог (переименовывает clicks.log -> clicks.log.processing),
 *      чтобы go.php тут же начал писать в новый чистый clicks.log и ничего не потерялось.
 *   2. Читает забранный файл построчно, батч-вставкой заливает в MySQL.
 *   3. Удаляет обработанный файл.
 *
 * Если MySQL недоступен — файл .processing остаётся, при следующем запуске
 * докатится. Ничего не теряется.
 *
 * Также обновляет offers.php (кэш офферов), чтобы go.php всегда имел свежие ссылки.
 */

// Запуск только из CLI (крон) или с секретным ключом (ручной вызов).
$cfg = require __DIR__ . '/config.php';
$isCli = (php_sapi_name() === 'cli');
if (!$isCli) {
    // ручной вызов через браузер — только с ключом
    if (($_GET['key'] ?? '') !== ($cfg['postback_secret'] ?? '')) {
        http_response_code(403);
        exit('forbidden');
    }
    header('Content-Type: text/plain; charset=utf-8');
}

require_once __DIR__ . '/db.php';

$logFile = $cfg['click_log'] ?? (sys_get_temp_dir() . '/sitegrator_clicks.log');
$procFile = $logFile . '.processing';

function say($s) {
    echo $s . "\n";
    if (php_sapi_name() !== 'cli') @flush();
}

$t0 = microtime(true);
say("=== import.php " . date('Y-m-d H:i:s') . " ===");

// -------- 0. Обновляем кэш офферов (дёшево, полезно держать свежим) --------
try {
    if (function_exists('offers_cache_rebuild')) {
        $n = offers_cache_rebuild();
        say("offers.php обновлён: $n кампаний");
    }
} catch (Throwable $e) {
    say("! offers.php не обновлён: " . $e->getMessage());
}

// -------- 1. Есть ли что импортировать? --------
$haveProc = is_file($procFile);   // остался с прошлого раза (MySQL был недоступен)?
$haveNew  = is_file($logFile) && filesize($logFile) > 0;

if (!$haveProc && !$haveNew) {
    say("нет новых кликов, выходим");
    exit;
}

// -------- 2. Атомарно забираем текущий лог --------
// Если .processing уже есть (прошлый заход не долил) — сперва дольём его,
// новый лог заберём следующим запуском.
if (!$haveProc && $haveNew) {
    // переименование атомарно в пределах одной ФС; go.php сразу пишет в новый файл
    @rename($logFile, $procFile);
}

if (!is_file($procFile)) {
    say("нечего обрабатывать");
    exit;
}

// -------- 3. Читаем и вставляем батчами --------
$fh = @fopen($procFile, 'r');
if (!$fh) { say("! не открыть $procFile"); exit(1); }

$pdo = db();
$cols = ['ts','slug','ip','ua','referer','source','is_bot','clickid','country'];
$colsSql = implode(',', $cols);
$batchSize = 500;
$buf = [];
$rowN = 0;
$total = 0;
$bad = 0;

$flush = function() use (&$buf, &$rowN, $pdo, $colsSql, $cols) {
    if ($rowN === 0) return;
    $ph = '(' . implode(',', array_fill(0, count($cols), '?')) . ')';
    $vals = implode(',', array_fill(0, $rowN, $ph));
    $st = $pdo->prepare("INSERT INTO clicks ($colsSql) VALUES $vals");
    $st->execute($buf);
    $buf = [];
    $rowN = 0;
};

try {
    $pdo->beginTransaction();
    while (($line = fgets($fh)) !== false) {
        $line = rtrim($line, "\r\n");
        if ($line === '') continue;
        $f = explode("\t", $line);
        if (count($f) < 9) { $bad++; continue; }   // битая строка — пропускаем
        // порядок ровно как пишет go.php
        $buf[] = (int)$f[0];        // ts
        $buf[] = $f[1];             // slug
        $buf[] = $f[2];             // ip
        $buf[] = $f[3];             // ua
        $buf[] = $f[4];             // referer
        $buf[] = $f[5];             // source
        $buf[] = (int)$f[6];        // is_bot
        $buf[] = $f[7];             // clickid
        $buf[] = $f[8];             // country
        $rowN++;
        $total++;
        if ($rowN >= $batchSize) {
            $flush();
            $pdo->commit();
            $pdo->beginTransaction();
        }
    }
    $flush();
    $pdo->commit();
    fclose($fh);

    // -------- 4. Успех — удаляем обработанный файл --------
    @unlink($procFile);

    $dt = round(microtime(true) - $t0, 2);
    say("импортировано: $total кликов" . ($bad ? " (битых строк: $bad)" : "") . ", {$dt}с");

    // -------- 5. Досвязываем конверсии с только что появившимися кликами --------
    // Постбек приходит раньше, чем клик доедет до базы (клик ждёт этого импорта),
    // поэтому в момент постбека он остался с slug = NULL («не привязан»).
    // Теперь клики в базе — подтягиваем привязку.
    try {
        $relinked = relink_conversions(7);
        if ($relinked > 0) say("досвязано конверсий: $relinked");
    } catch (Throwable $e) {
        say("! досвязать конверсии не удалось: " . $e->getMessage());
    }

    // -------- 6. Метка обновления данных — по ней панель сбрасывает свой кэш --------
    // Пока метка не изменилась, панель отдаёт готовые агрегаты из cache/ и не
    // пересчитывает их на каждую перезагрузку.
    try { meta_upsert('last_import', time()); } catch (Throwable $e) { /* не критично */ }

} catch (Throwable $e) {
    // MySQL недоступен/ошибка — откатываемся, .processing остаётся, докатим позже
    if ($pdo->inTransaction()) $pdo->rollBack();
    if (is_resource($fh)) fclose($fh);
    say("! ОШИБКА импорта (докатим при следующем запуске): " . $e->getMessage());
    exit(1);
}
