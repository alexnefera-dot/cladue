<?php
/**
 * db.php — подключение к базе, схема и функции работы с кампаниями.
 * Подключается из go.php (редирект) и stats.php (панель).
 *
 * Структура: КАМПАНИЯ (стабильный слаг = рефка) -> ОФЕР (URL, можно менять).
 * Смена офера пишется в offer_history, чтобы была история.
 */

// Единый часовой пояс для всей системы (панель, график, границы суток, API).
// Europe/Kyiv — так требует контракт выгрузки для аналитики: обе системы
// (трекер и система запусков) обязаны отдавать время в одном поясе, иначе
// лаги между кликом и конверсией считаются неверно и без всякой ошибки.
//
// Раньше стояла Europe/Moscow. Летом пояса совпадают (+03:00), но с конца
// октября Киев уходит на +02:00 — именно поэтому пояс задаётся здесь и
// в MySQL-сессии (см. db()) одновременно. Разъедутся — шапка панели
// разойдётся с графиком на границе суток.
@date_default_timezone_set('Europe/Kyiv');

/**
 * Возвращает драйвер текущего подключения: 'sqlite' или 'mysql'.
 * Используется в местах, где SQL несовместим (только даты).
 */
function db_driver() {
    $cfg = require __DIR__ . '/config.php';
    return ($cfg['db_driver'] ?? 'sqlite') === 'mysql' ? 'mysql' : 'sqlite';
}

/**
 * SQL-выражение "форматировать unix-timestamp $col в YYYY-MM-DD (локальное время)".
 * Работает и в SQLite (strftime), и в MySQL (FROM_UNIXTIME).
 */
function sql_day($col) {
    return db_driver() === 'mysql'
        ? "DATE(FROM_UNIXTIME($col))"
        : "strftime('%Y-%m-%d', $col, 'unixepoch', 'localtime')";
}

/**
 * INSERT-OR-REPLACE в таблицу meta(k,v). В SQLite — INSERT OR REPLACE,
 * в MySQL — INSERT ... ON DUPLICATE KEY UPDATE.
 */
function meta_upsert($k, $v) {
    if (db_driver() === 'mysql') {
        db()->prepare('INSERT INTO meta (k, v) VALUES (?, ?)
                       ON DUPLICATE KEY UPDATE v = VALUES(v)')->execute([$k, (string)$v]);
    } else {
        db()->prepare('INSERT OR REPLACE INTO meta (k, v) VALUES (?, ?)')
            ->execute([$k, (string)$v]);
    }
}

function db() {
    static $pdo = null;
    if ($pdo !== null) return $pdo;

    $cfg = require __DIR__ . '/config.php';
    $driver = ($cfg['db_driver'] ?? 'sqlite') === 'mysql' ? 'mysql' : 'sqlite';

    if ($driver === 'mysql') {
        // -------- MySQL --------
        $host = $cfg['mysql_host'] ?? '127.0.0.1';
        $port = (int)($cfg['mysql_port'] ?? 3306);
        $name = $cfg['mysql_db']   ?? '';
        $user = $cfg['mysql_user'] ?? '';
        $pass = $cfg['mysql_pass'] ?? '';
        $dsn  = "mysql:host=$host;port=$port;dbname=$name;charset=utf8mb4";
        $pdo  = new PDO($dsn, $user, $pass, [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_EMULATE_PREPARES   => false,
            PDO::MYSQL_ATTR_INIT_COMMAND => 'SET NAMES utf8mb4',
        ]);
        // Пояс сессии должен совпадать с PHP, иначе FROM_UNIXTIME посчитает дату
        // иначе, чем date(), и шапка панели разойдётся с графиком.
        // Именованный пояс требует залитых таблиц mysql.time_zone_name — если их
        // нет, SET бросит ошибку, и мы откатываемся на текущий офсет из PHP.
        // Офсет следует переходу на зимнее время сам (date('P') отдаёт +03:00
        // летом и +02:00 зимой), поэтому запасной вариант тоже корректен.
        try {
            $pdo->exec("SET time_zone = 'Europe/Kyiv'");
        } catch (Throwable $e) {
            $pdo->exec("SET time_zone = '" . date('P') . "'");
        }
        db_ensure_schema($pdo, 'mysql');
    } else {
        // -------- SQLite --------
        $pdo = new PDO('sqlite:' . __DIR__ . '/' . $cfg['db_file']);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        // при блокировке базы ждать до 5 сек (а не висеть до CGI-таймаута и валить весь бэкенд)
        $pdo->setAttribute(PDO::ATTR_TIMEOUT, 5);
        $pdo->exec('PRAGMA busy_timeout = 5000');
        $pdo->exec('PRAGMA journal_mode = WAL');     // читатели не блокируют писателя
        $pdo->exec('PRAGMA synchronous = NORMAL');   // быстрее записи, безопасно при WAL
        $pdo->exec('PRAGMA wal_autocheckpoint = 400');
        db_ensure_schema($pdo, 'sqlite');
    }
    return $pdo;
}

/**
 * Создать таблицы, если их ещё нет — но не на каждом запросе.
 *
 * Раньше db() гнал CREATE TABLE IF NOT EXISTS для всех семи таблиц при КАЖДОМ
 * подключении. На боевой MySQL это ~0.7с накладных расходов на каждый запрос
 * страницы и на каждый постбек. Теперь после успешного создания ставится
 * маркер-файл, и дальше схема не трогается.
 *
 * Если маркер удалить (или снести каталог cache/), схема просто проверится
 * заново — CREATE TABLE IF NOT EXISTS идемпотентен, данные не страдают.
 */
function db_ensure_schema(PDO $pdo, $driver) {
    $marker = __DIR__ . '/cache/.schema_' . $driver;
    if (is_file($marker)) return;

    $driver === 'mysql' ? db_create_tables_mysql($pdo) : db_create_tables_sqlite($pdo);
    if ($driver === 'mysql') db_ensure_indexes_mysql($pdo);

    cache_dir();
    if (@file_put_contents($marker, (string)time()) !== false) {
        cache_fix_owner($marker, 0664);
    }
}

/**
 * Досоздать индексы на уже существующих таблицах MySQL.
 *
 * CREATE TABLE IF NOT EXISTS для существующей таблицы не делает ничего — новый
 * индекс из схемы выше на боевой базе сам не появится. Поэтому индексы, которые
 * добавлялись после первого деплоя, проверяются отдельно.
 *
 * Вызывается только когда нет маркера схемы (после обновления файлов) — то есть
 * один раз на деплой, не на каждый запрос. MySQL не умеет CREATE INDEX IF NOT
 * EXISTS, поэтому сначала смотрим information_schema.
 */
function db_ensure_indexes_mysql(PDO $pdo) {
    $wanted = [
        ['conversions', 'idx_conv_ts',      'ts'],
        ['conversions', 'idx_conv_slug_ts', 'slug, ts'],
        ['clicks',      'idx_slug_ts',      'slug, ts'],
    ];
    $st = $pdo->prepare('SELECT COUNT(*) FROM information_schema.statistics
                         WHERE table_schema = DATABASE() AND table_name = ? AND index_name = ?');
    foreach ($wanted as [$table, $index, $cols]) {
        try {
            $st->execute([$table, $index]);
            if ((int)$st->fetchColumn() > 0) continue;
            // ALGORITHM=INPLACE: таблица остаётся доступной на запись, постбеки
            // и импорт не встают на время построения индекса.
            $pdo->exec("ALTER TABLE `$table` ADD INDEX `$index` ($cols), ALGORITHM=INPLACE, LOCK=NONE");
        } catch (Throwable $e) {
            // нет прав на information_schema/ALTER — не повод ронять панель,
            // всё продолжит работать, просто медленнее
        }
    }

    // Колонки, добавленные после первого деплоя. Та же история, что с индексами:
    // CREATE TABLE IF NOT EXISTS их на живой таблице не создаст.
    $wantedCols = [
        ['clicks',      'lp',        'VARCHAR(255) NULL'],
        ['clicks',      'event',     'VARCHAR(16) NULL'],
        ['campaigns',   'prelander', 'VARCHAR(64) NULL'],
        ['campaigns',   'prelander_slots', 'TEXT NULL'],
        ['conversions', 'sub',       'VARCHAR(190) NULL'],
        ['conversions', 'ref',       'TEXT NULL'],
        ['conversions', 'country',   'VARCHAR(8) NULL'],
        ['conversions', 'lp',        'VARCHAR(255) NULL'],
        ['conversions', 'linked_at', 'INT NULL'],
    ];
    $stc = $pdo->prepare('SELECT COUNT(*) FROM information_schema.columns
                          WHERE table_schema = DATABASE() AND table_name = ? AND column_name = ?');
    foreach ($wantedCols as [$table, $col, $type]) {
        try {
            $stc->execute([$table, $col]);
            if ((int)$stc->fetchColumn() > 0) continue;
            $pdo->exec("ALTER TABLE `$table` ADD COLUMN `$col` $type, ALGORITHM=INPLACE, LOCK=NONE");
        } catch (Throwable $e) {
            // см. выше
        }
    }

    // conversions.ref создавалась как VARCHAR(255) — расширяем до TEXT, чтобы
    // длинный URL дора не обрезался в снимке конверсии (в clicks он уже TEXT).
    try {
        $stt = $pdo->prepare("SELECT data_type FROM information_schema.columns
                              WHERE table_schema = DATABASE() AND table_name = 'conversions' AND column_name = 'ref'");
        $stt->execute();
        $t = strtolower((string)$stt->fetchColumn());
        if ($t !== '' && $t !== 'text') $pdo->exec('ALTER TABLE conversions MODIFY `ref` TEXT NULL');
    } catch (Throwable $e) {
        // см. выше
    }
}

/**
 * Дозаполнить снимок клика в старых строках конверсий (sub/ref/country/lp).
 *
 * Разовая операция после добавления колонок: у конверсий, записанных до правки,
 * поля пустые, хотя клики для них в базе ещё есть. Без этого вся история до
 * деплоя ушла бы в выгрузку без сабдомена.
 *
 * Идёт пачками и только из CLI (крон) — на живой базе это UPDATE по сотням
 * тысяч строк, из веба такое запускать нельзя. Возвращает число заполненных.
 */
function conversions_backfill($batch = 2000, $maxBatches = 500) {
    if (php_sapi_name() !== 'cli') return 0;
    $pdo   = db();
    $batch = max(100, (int)$batch);

    // Идём окнами по первичному ключу, а не LIMIT'ом: многотабличный UPDATE
    // в MySQL LIMIT не принимает вовсе, а окно по id ещё и ложится на PRIMARY.
    $maxId = (int)$pdo->query('SELECT COALESCE(MAX(id),0) FROM conversions')->fetchColumn();
    if ($maxId === 0) return 0;

    if (db_driver() === 'mysql') {
        $sql = "UPDATE conversions cv
                JOIN clicks c ON c.clickid = cv.clickid
                SET cv.slug = COALESCE(cv.slug, c.slug), cv.sub = c.source,
                    cv.ref = c.referer, cv.country = c.country, cv.lp = c.lp,
                    cv.linked_at = cv.ts
                WHERE cv.linked_at IS NULL AND cv.clickid <> ''
                  AND cv.id >= ? AND cv.id < ?";
    } else {
        $sql = "UPDATE conversions
                SET slug      = COALESCE(slug, (SELECT c.slug FROM clicks c WHERE c.clickid = conversions.clickid ORDER BY c.id DESC LIMIT 1)),
                    sub       = (SELECT c.source  FROM clicks c WHERE c.clickid = conversions.clickid ORDER BY c.id DESC LIMIT 1),
                    ref       = (SELECT c.referer FROM clicks c WHERE c.clickid = conversions.clickid ORDER BY c.id DESC LIMIT 1),
                    country   = (SELECT c.country FROM clicks c WHERE c.clickid = conversions.clickid ORDER BY c.id DESC LIMIT 1),
                    lp        = (SELECT c.lp      FROM clicks c WHERE c.clickid = conversions.clickid ORDER BY c.id DESC LIMIT 1),
                    linked_at = ts
                WHERE linked_at IS NULL AND clickid <> ''
                  AND EXISTS (SELECT 1 FROM clicks c WHERE c.clickid = conversions.clickid)
                  AND id >= ? AND id < ?";
    }

    $st    = $pdo->prepare($sql);
    $total = 0;
    for ($from = 1, $i = 0; $from <= $maxId && $i < $maxBatches; $from += $batch, $i++) {
        $st->execute([$from, $from + $batch]);
        $total += $st->rowCount();
    }
    return $total;
}

/** Создание таблиц под MySQL (InnoDB, utf8mb4). Идемпотентно. */
function db_create_tables_mysql(PDO $pdo) {
    $pdo->exec('CREATE TABLE IF NOT EXISTS campaigns (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        slug VARCHAR(190) NOT NULL UNIQUE,
        name VARCHAR(255) NOT NULL DEFAULT "",
        offer_url TEXT NOT NULL,
        prelander VARCHAR(64) NULL,
        prelander_slots TEXT NULL,
        created_at INT NOT NULL,
        updated_at INT NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4');

    $pdo->exec('CREATE TABLE IF NOT EXISTS clicks (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        ts INT NOT NULL,
        slug VARCHAR(190) NOT NULL,
        ip VARCHAR(64) NULL,
        ua TEXT NULL,
        referer TEXT NULL,
        source VARCHAR(190) NULL,
        is_bot TINYINT UNSIGNED NOT NULL DEFAULT 0,
        clickid VARCHAR(64) NULL,
        country VARCHAR(8) NULL,
        lp VARCHAR(255) NULL,
        event VARCHAR(16) NULL,
        INDEX idx_slug (slug),
        INDEX idx_ts (ts),
        INDEX idx_slug_ts (slug, ts),
        INDEX idx_clickid (clickid),
        INDEX idx_src (source)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4');

    $pdo->exec('CREATE TABLE IF NOT EXISTS conversions (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        clickid VARCHAR(64) NOT NULL,
        slug VARCHAR(190) NULL,
        status VARCHAR(32) NULL,
        payout DECIMAL(10,2) NOT NULL DEFAULT 0,
        ts INT NOT NULL,
        ip VARCHAR(64) NULL,
        sub VARCHAR(190) NULL,
        ref TEXT NULL,
        country VARCHAR(8) NULL,
        lp VARCHAR(255) NULL,
        linked_at INT NULL,
        INDEX idx_conv_clickid (clickid),
        INDEX idx_conv_slug_ts (slug, ts),
        INDEX idx_conv_ts (ts)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4');

    $pdo->exec('CREATE TABLE IF NOT EXISTS postback_log (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        ts INT NOT NULL,
        ip VARCHAR(64) NULL,
        query TEXT NULL,
        outcome VARCHAR(32) NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4');

    $pdo->exec('CREATE TABLE IF NOT EXISTS offer_history (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        slug VARCHAR(190) NOT NULL,
        old_url TEXT NULL,
        new_url TEXT NULL,
        ts INT NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4');

    $pdo->exec('CREATE TABLE IF NOT EXISTS meta (
        k VARCHAR(64) NOT NULL PRIMARY KEY,
        v TEXT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4');

    $pdo->exec('CREATE TABLE IF NOT EXISTS gaps (
        id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
        start_ts INT NOT NULL,
        end_ts INT NOT NULL,
        seconds INT NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4');
}

/** Создание таблиц под SQLite. Оставлено ровно как было. */
function db_create_tables_sqlite(PDO $pdo) {
    // клики (как и раньше — старые данные не трогаем)
    $pdo->exec('CREATE TABLE IF NOT EXISTS clicks (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        ts      INTEGER NOT NULL,
        slug    TEXT    NOT NULL,
        ip      TEXT, ua TEXT, referer TEXT
    )');
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_slug ON clicks(slug)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_ts   ON clicks(ts)');

    // миграция: метка источника (?s=...) — добавляем, если её ещё нет
    $cols = $pdo->query("PRAGMA table_info(clicks)")->fetchAll(PDO::FETCH_COLUMN, 1);
    if (!in_array('source', $cols, true)) {
        $pdo->exec('ALTER TABLE clicks ADD COLUMN source TEXT');
    }
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_src ON clicks(source)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_slug_ts ON clicks(slug, ts)');

    // миграция: пометка бота (0/1) — добавляем, если ещё нет
    $cols = $pdo->query("PRAGMA table_info(clicks)")->fetchAll(PDO::FETCH_COLUMN, 1);
    if (!in_array('is_bot', $cols, true)) {
        $pdo->exec('ALTER TABLE clicks ADD COLUMN is_bot INTEGER NOT NULL DEFAULT 0');
    }
    // миграция: наш clickid для постбэка
    if (!in_array('clickid', $cols, true)) {
        $pdo->exec('ALTER TABLE clicks ADD COLUMN clickid TEXT');
    }
    // миграция: страна по IP (из заголовка Cloudflare CF-IPCountry)
    if (!in_array('country', $cols, true)) {
        $pdo->exec('ALTER TABLE clicks ADD COLUMN country TEXT');
    }
    // миграция: путь страницы входа (?lp=... от дор-движка) — для аналитики
    if (!in_array('lp', $cols, true)) {
        $pdo->exec('ALTER TABLE clicks ADD COLUMN lp TEXT');
    }
    // миграция: событие клика — direct / view (показан преленд) / click (клик на преленде)
    if (!in_array('event', $cols, true)) {
        $pdo->exec('ALTER TABLE clicks ADD COLUMN event TEXT');
    }
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_clickid ON clicks(clickid)');

    // конверсии из постбэка партнёрки
    $pdo->exec('CREATE TABLE IF NOT EXISTS conversions (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        clickid TEXT NOT NULL,
        slug    TEXT,
        status  TEXT,
        payout  REAL DEFAULT 0,
        ts      INTEGER NOT NULL,
        ip      TEXT
    )');
    // миграция: снимок данных клика в строку конверсии (см. relink_conversions)
    $cvCols = $pdo->query("PRAGMA table_info(conversions)")->fetchAll(PDO::FETCH_COLUMN, 1);
    foreach (['sub' => 'TEXT', 'ref' => 'TEXT', 'country' => 'TEXT',
              'lp' => 'TEXT', 'linked_at' => 'INTEGER'] as $col => $type) {
        if (!in_array($col, $cvCols, true)) {
            $pdo->exec("ALTER TABLE conversions ADD COLUMN $col $type");
        }
    }
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_conv_clickid ON conversions(clickid)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_conv_slug_ts ON conversions(slug, ts)');
    $pdo->exec('CREATE INDEX IF NOT EXISTS idx_conv_ts ON conversions(ts)');

    // сырой лог постбеков (все входящие запросы на postback.php, для отладки)
    $pdo->exec('CREATE TABLE IF NOT EXISTS postback_log (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        ts      INTEGER NOT NULL,
        ip      TEXT,
        query   TEXT,
        outcome TEXT
    )');

    // существовала ли таблица кампаний ДО этого запуска?
    $fresh = !$pdo->query(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='campaigns'"
    )->fetchColumn();

    $pdo->exec('CREATE TABLE IF NOT EXISTS campaigns (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        slug       TEXT NOT NULL UNIQUE,
        name       TEXT NOT NULL DEFAULT "",
        offer_url  TEXT NOT NULL,
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    )');
    // миграция: выбранный преленд кампании ('' / NULL — редирект сразу, как раньше)
    $cmpCols = $pdo->query("PRAGMA table_info(campaigns)")->fetchAll(PDO::FETCH_COLUMN, 1);
    if (!in_array('prelander', $cmpCols, true)) {
        $pdo->exec('ALTER TABLE campaigns ADD COLUMN prelander TEXT');
    }
    if (!in_array('prelander_slots', $cmpCols, true)) {
        $pdo->exec('ALTER TABLE campaigns ADD COLUMN prelander_slots TEXT');
    }

    $pdo->exec('CREATE TABLE IF NOT EXISTS offer_history (
        id      INTEGER PRIMARY KEY AUTOINCREMENT,
        slug    TEXT NOT NULL,
        old_url TEXT, new_url TEXT,
        ts      INTEGER NOT NULL
    )');

    $pdo->exec('CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT)');

    // журнал «окон тишины» (разрывы heartbeat) — возможные простои
    $pdo->exec('CREATE TABLE IF NOT EXISTS gaps (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        start_ts  INTEGER NOT NULL,
        end_ts    INTEGER NOT NULL,
        seconds   INTEGER NOT NULL
    )');

    // при первом создании переносим уже работающую кампанию,
    // чтобы существующая рефка sitegrator.com/go/dorgne_fenix не сломалась
    if ($fresh) {
        $now = time();
        $st = $pdo->prepare('INSERT OR IGNORE INTO campaigns
            (slug, name, offer_url, created_at, updated_at) VALUES (?,?,?,?,?)');
        $st->execute(['dorgne_fenix', 'Dorgne Fenix',
                      'https://fnx-abs.org/di6viifma', $now, $now]);
    }
}

/** URL офера по слагу кампании (для редиректа). null — если кампании нет. */
function get_offer($slug) {
    $st = db()->prepare('SELECT offer_url FROM campaigns WHERE slug = ?');
    $st->execute([$slug]);
    $url = $st->fetchColumn();
    return $url === false ? null : $url;
}

/**
 * Перестроить файл-кэш офферов offers.php из таблицы campaigns.
 * go.php читает офферы отсюда, НЕ из MySQL — поэтому редиректор не зависит от базы.
 * Вызывается при любом изменении кампаний и периодически из import.php (крон).
 * Возвращает количество кампаний в кэше.
 */
function offers_cache_rebuild() {
    $rows = db()->query('SELECT slug, offer_url FROM campaigns')->fetchAll(PDO::FETCH_KEY_PAIR);
    $file = __DIR__ . '/offers.php';

    // ЗАЩИТА ОТ ПОТЕРИ ТРАФИКА.
    // offers.php — единственный источник ссылок для go.php. Если база вернёт
    // пустой список (сбой, пустая/подменённая база, недокачанный дамп), а крон
    // перезапишет им файл, то ВСЕ рефки начнут отдавать 404 — тихо, до того как
    // это заметят. Поэтому из крона (CLI) пустым списком рабочий кэш не затираем.
    // Из панели пустой список допустим: там это осознанное действие человека
    // (удалил последнюю кампанию).
    $newN = is_array($rows) ? count($rows) : 0;
    if ($newN === 0 && php_sapi_name() === 'cli') {
        $cur  = is_file($file) ? @include $file : null;
        $curN = is_array($cur) ? count($cur) : 0;
        if ($curN > 0) return -1;   // -1 = не обновляли, файл оставлен как был
    }

    // Разворачиваем поле оффера в формат для go.php:
    //   одна ссылка          -> строка (как было раньше, совместимо со старым offers.php)
    //   несколько (ротация)  -> [[url, вес], ...]
    $map = [];
    foreach ($rows as $slug => $urlText) {
        $list = parse_offer_urls($urlText);
        if (!$list) continue;
        $map[$slug] = (count($list) === 1 && $list[0][1] === 1) ? $list[0][0] : $list;
    }

    $php = "<?php\n// АВТОГЕНЕРАЦИЯ. Не редактировать вручную — перезапишется.\n"
         . "// Обновлено: " . date('Y-m-d H:i:s') . "\n"
         . "// Значение: строка = один оффер; массив [[url,вес],...] = ротация.\n"
         . "return " . var_export($map, true) . ";\n";
    $tmp  = $file . '.tmp';
    // пишем во временный и атомарно переименовываем — go.php никогда не увидит полу-записанный файл
    if (@file_put_contents($tmp, $php, LOCK_EX) !== false) {
        @rename($tmp, $file);
        if (function_exists('opcache_invalidate')) @opcache_invalidate($file, true);
    }
    return is_array($rows) ? count($rows) : 0;
}

function valid_slug($s) { return (bool)preg_match('/^[A-Za-z0-9_-]+$/', (string)$s); }

/**
 * Привести слаг к чистому виду.
 *
 * В панель его почти всегда вставляют готовой ссылкой, скопированной из списка
 * кампаний или из дора: https://sitegrator.com/go/banda_engine — и валидация
 * ругалась «только латиница, цифры, _ и -». Вырезаем сам слаг, чтобы не
 * заставлять руками стирать домен.
 *
 * Понимает: полную ссылку с /go/, ссылку с параметрами и хвостовым слэшем,
 * а также просто слаг (тогда возвращает его как есть).
 */
function normalize_slug($s) {
    $s = trim((string)$s);
    if ($s === '') return $s;
    if (preg_match('~/go/([A-Za-z0-9_-]+)~', $s, $m)) return $m[1];   // .../go/СЛАГ
    $s = preg_replace('~[?#].*$~', '', $s);                           // хвост с параметрами
    return trim($s, "/ \t");
}
function valid_url($u)  { return (bool)preg_match('~^https?://~i', (string)$u); }

/**
 * Привести домен к чистому виду: из ссылки вырезать хост.
 *   https://combohub.live/aeiyvj8egg?x=1  ->  combohub.live
 *   www.partner.com/                      ->  partner.com
 *   partner.com                           ->  partner.com
 * Возвращает '' если это не похоже на домен.
 */
function normalize_domain($s) {
    $s = strtolower(trim((string)$s));
    if ($s === '') return '';
    $s = preg_replace('~^[a-z]+://~', '', $s);   // протокол
    $s = preg_replace('~[/?#].*$~', '', $s);     // путь и параметры
    $s = preg_replace('~^www\.~', '', $s);       // www — домен покрывает поддомены
    $s = trim($s, '. ');
    return preg_match('~^[a-z0-9]([a-z0-9\-.]*[a-z0-9])?\.[a-z]{2,}$~', $s) ? $s : '';
}

/**
 * Whitelist доменов, к ссылкам которых go.php дописывает clickid.
 *
 * Хранится в файле postback_domains.php, а не в базе: go.php читает его на
 * каждом клике и не имеет права трогать MySQL. Файл генерируется панелью,
 * как offers.php. Пока файла нет — работает список из config.php, поэтому
 * старая настройка продолжает действовать без миграции.
 */
function postback_domains_get() {
    $file = __DIR__ . '/postback_domains.json';
    if (is_file($file)) {
        $list = json_decode((string)@file_get_contents($file), true);
        if (is_array($list)) return array_values($list);
    }
    $cfg = require __DIR__ . '/config.php';
    return array_values($cfg['postback_domains'] ?? []);
}

/**
 * Сохранить whitelist. На вход — текст (по домену на строку, можно ссылками).
 * Возвращает ['saved'=>N, 'skipped'=>[строки, которые не разобрались]].
 */
function postback_domains_save($text) {
    $out = $skipped = [];
    foreach (preg_split('~[\r\n,]+~', (string)$text) as $line) {
        $line = trim($line);
        if ($line === '' || $line[0] === '#') continue;
        $d = normalize_domain($line);
        if ($d === '') { $skipped[] = $line; continue; }
        if (!in_array($d, $out, true)) $out[] = $d;
    }
    sort($out);

    // JSON, а не PHP-файл: go.php читает его напрямую через file_get_contents,
    // без include. Иначе opcache отдавал бы старую копию списка до истечения
    // revalidate_freq, а при validate_timestamps=0 — вообще никогда, и правка
    // из панели молча не применялась бы.
    $file = __DIR__ . '/postback_domains.json';
    $tmp  = $file . '.tmp';
    // как offers.php: пишем во временный и переименовываем, чтобы go.php
    // никогда не прочитал полу-записанный файл
    if (@file_put_contents($tmp, json_encode($out, JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT), LOCK_EX) !== false) {
        @rename($tmp, $file);
        if (function_exists('cache_fix_owner')) cache_fix_owner($file, 0664);
    }
    return ['saved' => count($out), 'skipped' => $skipped];
}

/**
 * Разобрать поле оффера в список ссылок для ротации.
 *
 * В поле можно указать несколько ссылок — по одной на строку. Тогда go.php
 * будет распределять между ними трафик. Необязательный вес после «|»:
 *
 *   https://a.com/abc          — вес 1
 *   https://b.com/xyz|3        — вес 3 (получит втрое больше трафика)
 *
 * Возвращает [[url, weight], ...]. Для одной ссылки — список из одного элемента.
 */
function parse_offer_urls($text) {
    $out = [];
    foreach (preg_split('~[\r\n]+~', (string)$text) as $line) {
        $line = trim($line);
        if ($line === '' || $line[0] === '#') continue;
        $w = 1;
        if (preg_match('~^(.*?)\s*\|\s*(\d+)\s*$~', $line, $m)) {
            $line = trim($m[1]);
            $w    = max(1, (int)$m[2]);
        }
        if ($line !== '') $out[] = [$line, $w];
    }
    return $out;
}

/** Проверка поля оффера: непустое и каждая ссылка начинается с http. */
function valid_offer_urls($text) {
    $list = parse_offer_urls($text);
    if (!$list) return false;
    foreach ($list as $o) if (!valid_url($o[0])) return false;
    return true;
}

/** Добавить кампанию. Возвращает null при успехе или текст ошибки. */
function add_campaign($slug, $name, $url) {
    $slug = normalize_slug($slug);   // принимаем и готовую ссылку .../go/СЛАГ
    $name = trim((string)$name);
    $url  = trim((string)$url);
    if (!valid_slug($slug)) return 'Слаг "' . $slug . '": только латиница, цифры, _ и -';
    if (!valid_offer_urls($url)) return 'Кампания "' . $slug . '": каждая ссылка должна начинаться с http';
    $now = time();
    try {
        db()->prepare('INSERT INTO campaigns (slug,name,offer_url,created_at,updated_at)
                       VALUES (?,?,?,?,?)')
            ->execute([$slug, $name, $url, $now, $now]);
    } catch (PDOException $e) {
        return 'Слаг "' . $slug . '" уже существует';
    }
    offers_cache_rebuild();   // обновляем кэш для go.php
    return null;
}

/** Сменить офер у кампании (по id). Пишет историю. */
function update_offer($id, $url) {
    $url = trim((string)$url);
    if (!valid_offer_urls($url)) return 'URL офера: каждая ссылка должна начинаться с http';
    $pdo = db();
    $st = $pdo->prepare('SELECT slug, offer_url FROM campaigns WHERE id = ?');
    $st->execute([(int)$id]);
    $c = $st->fetch(PDO::FETCH_ASSOC);
    if (!$c) return 'Кампания не найдена';
    if ($c['offer_url'] === $url) return null; // не изменилось
    $now = time();
    $pdo->prepare('UPDATE campaigns SET offer_url=?, updated_at=? WHERE id=?')
        ->execute([$url, $now, (int)$id]);
    $pdo->prepare('INSERT INTO offer_history (slug,old_url,new_url,ts) VALUES (?,?,?,?)')
        ->execute([$c['slug'], $c['offer_url'], $url, $now]);
    offers_cache_rebuild();   // обновляем кэш для go.php
    return null;
}

/** Переименовать кампанию. */
function rename_campaign($id, $name) {
    db()->prepare('UPDATE campaigns SET name=?, updated_at=? WHERE id=?')
        ->execute([trim((string)$name), time(), (int)$id]);
    return null;
}

/** Удалить кампанию (клики в логе остаются). */
function delete_campaign($id) {
    db()->prepare('DELETE FROM campaigns WHERE id = ?')->execute([(int)$id]);
    offers_cache_rebuild();   // обновляем кэш для go.php
    return null;
}

/** Массовый импорт. Формат строки: slug | offer_url | name(необязательно) */
function bulk_import($text) {
    $added = 0; $errors = [];
    foreach (preg_split('/\r\n|\r|\n/', (string)$text) as $line) {
        $line = trim($line);
        if ($line === '' || $line[0] === '#') continue;
        $parts = array_map('trim', explode('|', $line));
        $slug = $parts[0] ?? '';
        $url  = $parts[1] ?? '';
        $name = $parts[2] ?? '';
        $err = add_campaign($slug, $name, $url);
        if ($err === null) $added++; else $errors[] = $err;
    }
    return [$added, $errors];
}

/** Хост (домен) из URL. '' если не разобрался. */
function host_of($url) {
    $h = parse_url(trim((string)$url), PHP_URL_HOST);
    return $h ?: '';
}

/** Проверка домена: латиница/цифры/точка/дефис, опционально :порт. */
function valid_host($h) {
    return (bool)preg_match('~^[A-Za-z0-9.-]+(:\d+)?$~', (string)$h);
}

/** Сколько кампаний на каждом домене офера (для подсказки в панели). */
function domain_stats() {
    $rows = db()->query('SELECT offer_url FROM campaigns')->fetchAll(PDO::FETCH_COLUMN);
    $m = [];
    foreach ($rows as $u) {
        $h = host_of($u);
        if ($h === '') continue;
        $m[$h] = ($m[$h] ?? 0) + 1;
    }
    arsort($m);
    return $m;
}

/**
 * Массовая замена домена во ВСЕХ кампаниях.
 * Меняется только домен (host), путь/параметры/порт остаются как есть.
 * Совпадение строгое: cbc-abs.net не заденет cbc-abs.network.
 * Возвращает ['changed'=>N] либо ['err'=>'...'].
 */
function replace_domain($old, $new) {
    // если вставили со схемой/слэшем — оставим только хост
    $old = preg_replace('~^https?://~i', '', trim((string)$old));
    $old = preg_replace('~[/?#].*$~', '', (string)$old);
    $new = preg_replace('~^https?://~i', '', trim((string)$new));
    $new = preg_replace('~[/?#].*$~', '', (string)$new);

    if (!valid_host($old) || !valid_host($new))
        return ['err' => 'Домен: только латиница, цифры, точка и дефис'];
    if (strcasecmp($old, $new) === 0)
        return ['err' => 'Старый и новый домен совпадают'];

    $pdo  = db();
    $now  = time();
    $re   = '~^(https?://)' . preg_quote($old, '~') . '(?=[:/?#]|$)~i';
    $rows = $pdo->query('SELECT id, slug, offer_url FROM campaigns')->fetchAll(PDO::FETCH_ASSOC);

    $up   = $pdo->prepare('UPDATE campaigns SET offer_url=?, updated_at=? WHERE id=?');
    $hist = $pdo->prepare('INSERT INTO offer_history (slug,old_url,new_url,ts) VALUES (?,?,?,?)');

    $changed = 0;
    $pdo->beginTransaction();
    foreach ($rows as $c) {
        $newUrl = preg_replace($re, '$1' . $new, $c['offer_url']);
        if ($newUrl !== null && $newUrl !== $c['offer_url']) {
            $up->execute([$newUrl, $now, $c['id']]);
            $hist->execute([$c['slug'], $c['offer_url'], $newUrl, $now]);
            $changed++;
        }
    }
    $pdo->commit();
    if ($changed > 0) offers_cache_rebuild();   // обновляем кэш для go.php
    return ['changed' => $changed];
}

/**
 * Проверка всех кампаний: дергает URL оферов (параллельно, curl_multi).
 * Возвращает массив строк кампаний с полями code (HTTP) и err.
 * Проверяются уникальные URL (один URL на нескольких кампаниях — один запрос).
 */
function check_campaign_links() {
    $rows = db()->query('SELECT id, slug, name, offer_url FROM campaigns ORDER BY name, slug')
                ->fetchAll(PDO::FETCH_ASSOC);
    if (!$rows) return [];

    // уникальные URL (у кампании в ротации их несколько — проверяем каждую)
    $urls = [];
    foreach ($rows as $r)
        foreach (parse_offer_urls($r['offer_url']) as $o) $urls[$o[0]] = true;
    $urls = array_keys($urls);

    $UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
        . '(KHTML, like Gecko) Chrome/124 Safari/537.36';
    $results = []; // url => ['code'=>int,'err'=>str]

    if (function_exists('curl_multi_init')) {
        foreach (array_chunk($urls, 20) as $batch) {     // по 20 параллельно
            $mh = curl_multi_init();
            $hs = [];
            foreach ($batch as $u) {
                $ch = curl_init();
                curl_setopt_array($ch, [
                    CURLOPT_URL            => $u,
                    CURLOPT_FOLLOWLOCATION => true,
                    CURLOPT_MAXREDIRS      => 5,
                    CURLOPT_TIMEOUT        => 10,
                    CURLOPT_CONNECTTIMEOUT => 6,
                    CURLOPT_SSL_VERIFYPEER => false,
                    CURLOPT_SSL_VERIFYHOST => 0,
                    CURLOPT_RETURNTRANSFER => true,
                    CURLOPT_USERAGENT      => $UA,
                ]);
                curl_multi_add_handle($mh, $ch);
                $hs[] = ['ch' => $ch, 'url' => $u];
            }
            do {
                $st = curl_multi_exec($mh, $running);
                if ($running) curl_multi_select($mh, 1.0);
            } while ($running > 0 && $st === CURLM_OK);

            foreach ($hs as $h) {
                $results[$h['url']] = [
                    'code' => (int)curl_getinfo($h['ch'], CURLINFO_HTTP_CODE),
                    'err'  => curl_error($h['ch']),
                ];
                curl_multi_remove_handle($mh, $h['ch']);
                curl_close($h['ch']);
            }
            curl_multi_close($mh);
        }
    } else {
        // запасной путь без curl_multi (медленнее)
        foreach ($urls as $u) {
            if (!function_exists('curl_init')) { $results[$u] = ['code'=>0,'err'=>'на сервере нет php-curl']; continue; }
            $ch = curl_init();
            curl_setopt_array($ch, [
                CURLOPT_URL=>$u, CURLOPT_FOLLOWLOCATION=>true, CURLOPT_MAXREDIRS=>5,
                CURLOPT_TIMEOUT=>10, CURLOPT_CONNECTTIMEOUT=>6,
                CURLOPT_SSL_VERIFYPEER=>false, CURLOPT_SSL_VERIFYHOST=>0,
                CURLOPT_RETURNTRANSFER=>true, CURLOPT_USERAGENT=>$UA,
            ]);
            curl_exec($ch);
            $results[$u] = ['code'=>(int)curl_getinfo($ch,CURLINFO_HTTP_CODE),'err'=>curl_error($ch)];
            curl_close($ch);
        }
    }

    // Итог по кампании. Если офферов несколько (ротация) — показываем первую
    // проблемную ссылку: одна битая в ротации льёт часть трафика в никуда.
    foreach ($rows as &$r) {
        $list = parse_offer_urls($r['offer_url']);
        $bad  = null;
        foreach ($list as $o) {
            $res = $results[$o[0]] ?? ['code'=>0,'err'=>'нет curl'];
            $ok  = ($res['err'] === '' && $res['code'] >= 200 && $res['code'] < 400);
            if (!$ok) { $bad = [$o[0], $res]; break; }
        }
        if ($bad === null) {
            $res = $results[$list[0][0] ?? ''] ?? ['code'=>0,'err'=>'нет curl'];
            $r['code'] = $res['code'];
            $r['err']  = $res['err'];
        } else {
            $r['code'] = $bad[1]['code'];
            $r['err']  = (count($list) > 1 ? 'ссылка ' . $bad[0] . ': ' : '') . $bad[1]['err'];
        }
    }
    return $rows;
}

/**
 * Разбивка переходов по источникам.
 * Источник = метка ?s=... если есть; иначе домен реферера; иначе «прямой».
 * Возвращает [ ['slug','src','tagged'(bool),'clicks','uniques'], ... ] по убыванию кликов.
 */
function source_breakdown($slug = null) {
    $sql = 'SELECT slug, COALESCE(source,"") src, COALESCE(referer,"") ref,
                   COUNT(*) c, COUNT(DISTINCT ip) u
            FROM clicks';
    $args = [];
    if ($slug !== null) { $sql .= ' WHERE slug = ?'; $args[] = $slug; }
    $sql .= ' GROUP BY slug, source, referer';
    $st = db()->prepare($sql);
    $st->execute($args);

    $agg = [];
    foreach ($st->fetchAll(PDO::FETCH_ASSOC) as $r) {
        $tagged = $r['src'] !== '';
        $label  = $tagged ? $r['src'] : (host_of($r['ref']) ?: '(прямой / нет реферера)');
        $k = $r['slug'] . "\x00" . $label;
        if (!isset($agg[$k]))
            $agg[$k] = ['slug'=>$r['slug'],'src'=>$label,'tagged'=>$tagged,'clicks'=>0,'uniques'=>0];
        $agg[$k]['clicks']  += (int)$r['c'];
        $agg[$k]['uniques'] += (int)$r['u'];
    }
    $out = array_values($agg);
    usort($out, function ($a, $b) {
        return $b['clicks'] <=> $a['clicks'] ?: strcmp($a['slug'], $b['slug']);
    });
    return $out;
}

/**
 * Сменить оффер сразу у всех кампаний, чей слаг начинается с префикса.
 * Удобно когда под один оффер заведено много ссылок-под-сайты:
 *   1go_engine, 1go_engine_s001, 1go_engine_s002 ...  -> префикс "1go_engine"
 * Возвращает ['matched'=>N,'changed'=>M] либо ['err'=>...].
 */
function update_offer_by_prefix($prefix, $url) {
    $prefix = trim((string)$prefix);
    $url    = trim((string)$url);
    if (!valid_slug($prefix)) return ['err' => 'Префикс: только латиница, цифры, _ и -'];
    if (!valid_url($url))     return ['err' => 'URL офера должен начинаться с http'];

    $pdo  = db();
    $now  = time();
    // экранируем _ и % (в слагах есть _, а это шаблон LIKE)
    $like = str_replace(['\\', '%', '_'], ['\\\\', '\\%', '\\_'], $prefix) . '%';
    $sel  = $pdo->prepare("SELECT id, slug, offer_url FROM campaigns WHERE slug LIKE ? ESCAPE '\\'");
    $sel->execute([$like]);
    $rows = $sel->fetchAll(PDO::FETCH_ASSOC);

    $up   = $pdo->prepare('UPDATE campaigns SET offer_url=?, updated_at=? WHERE id=?');
    $hist = $pdo->prepare('INSERT INTO offer_history (slug,old_url,new_url,ts) VALUES (?,?,?,?)');
    $changed = 0;
    $pdo->beginTransaction();
    foreach ($rows as $c) {
        if ($c['offer_url'] === $url) continue;
        $up->execute([$url, $now, $c['id']]);
        $hist->execute([$c['slug'], $c['offer_url'], $url, $now]);
        $changed++;
    }
    $pdo->commit();
    if ($changed > 0) offers_cache_rebuild();   // обновляем кэш для go.php
    return ['matched' => count($rows), 'changed' => $changed];
}

/**
 * Определение бота по User-Agent.
 * Возвращает ['is_bot'=>bool, 'name'=>'google|yandex|bing|...|other|'].
 * Известные поисковики/краулеры/соцсети + общие признаки автоматики.
 */
function classify_bot($ua) {
    $ua = strtolower(trim((string)$ua));
    if ($ua === '') return ['is_bot' => true, 'name' => 'no-ua'];

    // именованные боты (для возможной детализации)
    $named = [
        'google'    => ['googlebot','adsbot-google','mediapartners-google','apis-google','feedfetcher-google','google-inspectiontool','storebot-google','google-read-aloud','google favicon'],
        'yandex'    => ['yandexbot','yandeximages','yandexmetrika','yandex.com/bots','yandexaccessibilitybot','yandex'],
        'bing'      => ['bingbot','msnbot','bingpreview','adidxbot'],
        'mailru'    => ['mail.ru_bot','mailru'],
        'duckduck'  => ['duckduckbot'],
        'baidu'     => ['baiduspider'],
        'yahoo'     => ['slurp'],
        'social'    => ['facebookexternalhit','facebot','twitterbot','telegrambot','tgbot','whatsapp','vkshare','viber','skypeuripreview','discordbot','slackbot','linkedinbot'],
        'seo'       => ['ahrefsbot','semrushbot','mj12bot','dotbot','dataforseo','blexbot','rogerbot','screaming frog'],
        'ai'        => ['gptbot','ccbot','claudebot','claude-web','anthropic','perplexitybot','amazonbot','bytespider','applebot','petalbot','google-extended'],
    ];
    foreach ($named as $name => $needles)
        foreach ($needles as $n)
            if (strpos($ua, $n) !== false) return ['is_bot' => true, 'name' => $name];

    // общие признаки автоматизированных клиентов
    $generic = ['bot','crawl','spider','scrapy','curl','wget','python','java/','go-http','okhttp',
                'headless','phantom','puppeteer','playwright','http-client','httpclient','libwww',
                'axios','node-fetch','ruby','perl','lighthouse','monitoring','uptime','pingdom'];
    foreach ($generic as $n)
        if (strpos($ua, $n) !== false) return ['is_bot' => true, 'name' => 'other'];

    return ['is_bot' => false, 'name' => ''];
}

/**
 * Лёгкий файловый счётчик ботов — увеличивается при пропуске записи (log_bots=false).
 * Хранит два числа: сегодня (сбрасывается в 00:00) и всего.
 * Не использует SQLite, чтобы не создавать конкуренцию за базу.
 */
function bots_counter_file() {
    $dir = sys_get_temp_dir() . '/rdr_bots';
    if (!is_dir($dir)) @mkdir($dir, 0700, true);
    return $dir . '/count';
}
function bots_counter_inc() {
    $f = bots_counter_file();
    $fp = @fopen($f, 'c+');
    if (!$fp) return;
    @flock($fp, LOCK_EX);
    $data = stream_get_contents($fp);
    $today = date('Y-m-d');
    $day = $today; $c_today = 0; $c_total = 0;
    if ($data && strpos($data, ' ') !== false) {
        [$day, $c_today, $c_total] = array_pad(explode(' ', trim($data)), 3, 0);
        if ($day !== $today) { $day = $today; $c_today = 0; }
    }
    $c_today++; $c_total++;
    @ftruncate($fp, 0); rewind($fp); @fwrite($fp, $day . ' ' . $c_today . ' ' . $c_total);
    @flock($fp, LOCK_UN); @fclose($fp);
}
function bots_counter_read() {
    $f = bots_counter_file();
    if (!is_file($f)) return ['today' => 0, 'total' => 0];
    $data = @file_get_contents($f);
    if (!$data || strpos($data, ' ') === false) return ['today' => 0, 'total' => 0];
    [$day, $c_today, $c_total] = array_pad(explode(' ', trim($data)), 3, 0);
    if ($day !== date('Y-m-d')) $c_today = 0;
    return ['today' => (int)$c_today, 'total' => (int)$c_total];
}

/**
 * Разбивка по источникам (source) для кампании за период.
 * Возвращает [ ['source'=>'mysite.com','clicks'=>N,'uniques'=>M,'regs'=>K], ... ]
 * отсортировано по uniques DESC.
 * source берётся из ?s= (или Referer) в go.php; клики без source группируются
 * под меткой "(прямые)".
 */
function sources_by_campaign($slug, $from, $to = null) {
    // Группируем по паре (источник, путь): один и тот же сабдомен даёт клики
    // с разной вложенностью, и это разные строки. Уровень считаем из пути
    // в PHP — в SQL сегменты пришлось бы считать по-разному под MySQL и SQLite.
    // $slug === null — по всем кампаниям сразу (сводка на главной).
    $sql = "SELECT COALESCE(NULLIF(source,''),'(прямые)') AS src, lp,
                   COUNT(*) AS clicks,
                   COUNT(DISTINCT ip) AS uniques
            FROM clicks
            WHERE is_bot = 0 AND " . sql_visit() . " AND ts >= ?";
    $args = [$from];
    if ($to !== null)   { $sql .= ' AND ts < ?';  $args[] = $to; }
    if ($slug !== null) { $sql .= ' AND slug = ?'; $args[] = $slug; }
    $sql .= ' GROUP BY src, lp';
    $st = db()->prepare($sql);
    $st->execute($args);

    $rows = [];
    foreach ($st->fetchAll(PDO::FETCH_ASSOC) as $r) {
        $depth = ($r['lp'] === null || $r['lp'] === '') ? -1 : ru_depth($r['lp']);
        $key   = $r['src'] . "\x00" . $depth;
        if (!isset($rows[$key])) {
            $rows[$key] = ['src' => $r['src'], 'depth' => $depth,
                           'clicks' => 0, 'uniques' => 0, 'regs' => 0, 'deps' => 0];
        }
        $rows[$key]['clicks']  += (int)$r['clicks'];
        // уники складываются по разным путям: один ip мог зайти с двух уровней.
        // Расхождение в пределах единиц, ради точности пришлось бы тянуть все ip.
        $rows[$key]['uniques'] += (int)$r['uniques'];
    }
    if (!$rows) return [];

    // Реги и депы берём из снимка в строке конверсии (sub/lp), без JOIN к кликам:
    // так быстрее и не рвётся, когда retention удалит старые клики.
    $sqlR = "SELECT COALESCE(NULLIF(sub,''),'(прямые)') AS src, lp,
                    SUM(CASE WHEN status IN('reg','registration','lead') THEN 1 ELSE 0 END) AS regs,
                    SUM(CASE WHEN status IN('dep','deposit','sale','ftd','purchase') THEN 1 ELSE 0 END) AS deps
             FROM conversions
             WHERE ts >= ?";
    $argsR = [$from];
    if ($to !== null)   { $sqlR .= ' AND ts < ?';  $argsR[] = $to; }
    if ($slug !== null) { $sqlR .= ' AND slug = ?'; $argsR[] = $slug; }
    $sqlR .= ' GROUP BY src, lp';
    $st = db()->prepare($sqlR);
    $st->execute($argsR);
    foreach ($st->fetchAll(PDO::FETCH_ASSOC) as $r) {
        $depth = ($r['lp'] === null || $r['lp'] === '') ? -1 : ru_depth($r['lp']);
        $key   = $r['src'] . "\x00" . $depth;
        if (!isset($rows[$key])) continue;   // конверсия без кликов в периоде
        $rows[$key]['regs'] += (int)$r['regs'];
        $rows[$key]['deps'] += (int)$r['deps'];
    }

    $rows = array_values($rows);
    usort($rows, function ($a, $b) {
        return [$b['uniques'], $b['clicks']] <=> [$a['uniques'], $a['clicks']];
    });
    return $rows;
}

/**
 * Корневой домен из источника: последние две метки.
 *   dbbet.5623-1.casino -> 5623-1.casino
 *   kraken.dt63k.team   -> dt63k.team
 *   cryptoboss22.top    -> cryptoboss22.top (уже корень)
 *   (прямые)            -> (прямые)  (спецметка не трогается)
 * Для составных TLD (.co.uk) неточно, но в нашем наборе таких нет.
 */
function source_root($src) {
    if ($src === '' || $src === '(прямые)') return '(прямые)';
    $parts = explode('.', $src);
    $n = count($parts);
    if ($n <= 2) return $src;                    // уже корень или без точки
    return $parts[$n - 2] . '.' . $parts[$n - 1]; // последние две метки
}

/**
 * Показы и клики преленда за период: сколько дошло до кнопки.
 * Ради этой цифры преленд и разводится на два события — без неё непонятно,
 * помогает он или просто вставляет лишний шаг перед оффером.
 */
function prelander_stats($slug, $from, $to = null) {
    // Показ записан на саму кампанию, а клик — уже на ту, куда ведёт блок.
    // Связывает их общий clickid, по нему и считаем: сколько показов дошло
    // до кнопки. Внешний набор мал (только преленды), idx_clickid справляется.
    $w  = ' ts >= ?' . ($to !== null ? ' AND ts < ?' : '');
    $a1 = $to !== null ? [$slug, $from, $to] : [$slug, $from];
    $st = db()->prepare("SELECT COUNT(*) FROM clicks
                         WHERE slug = ? AND event = 'view' AND is_bot = 0 AND $w");
    $st->execute($a1);
    $v = (int)$st->fetchColumn();

    $a2 = $to !== null ? [$from, $to, $slug] : [$from, $slug];
    $w2 = ' c.ts >= ?' . ($to !== null ? ' AND c.ts < ?' : '');
    $st = db()->prepare("SELECT COUNT(*) FROM clicks c
                         WHERE c.event = 'click' AND $w2
                           AND EXISTS (SELECT 1 FROM clicks v
                                       WHERE v.clickid = c.clickid AND v.event = 'view' AND v.slug = ?)");
    $st->execute($a2);
    $c = (int)$st->fetchColumn();

    // Входящие: переходы, ПРИШЕДШИЕ на эту кампанию с чужого преленда.
    // В визитах они не считаются (иначе один посетитель дал бы два клика —
    // на преленде и здесь), но конверсии садятся именно сюда, и без этой
    // цифры страница выглядела бы как «реги есть, трафика нет».
    $st = db()->prepare("SELECT COUNT(*) FROM clicks WHERE slug = ? AND event = 'click' AND $w");
    $st->execute($a1);
    $in = (int)$st->fetchColumn();

    return ['views' => $v, 'clicks' => $c, 'incoming' => $in,
            'ctr' => $v ? round($c * 100 / $v, 1) : 0.0];
}

/**
 * SQL-условие «строка — это визит, а не нажатие кнопки на преленде».
 *
 * С прелендом на одного посетителя приходится ДВЕ строки: показ (view) и клик
 * по кнопке (click). Во всех сводках клик считать нельзя — иначе цифры
 * удвоятся на кампаниях с прелендом и разойдутся с теми, где его нет.
 * NULL — это строки, записанные до появления колонки: обычные переходы.
 */
function sql_visit($alias = '') {
    $p = $alias !== '' ? $alias . '.' : '';
    return "({$p}event IS NULL OR {$p}event <> 'click')";
}

/**
 * Назначить кампании преленд (или снять его пустым значением).
 * Имя шаблона проверяем по списку файлов: в базу не должно попасть ничего,
 * из чего потом сложится путь к постороннему файлу.
 */
function set_prelander($id, $tpl) {
    $id  = (int)$id;
    $tpl = preg_replace('~[^\w.\-]~', '', (string)$tpl);
    if ($tpl !== '' && !in_array($tpl, prelander_templates(), true)) $tpl = '';
    db()->prepare('UPDATE campaigns SET prelander = ?, updated_at = ? WHERE id = ?')
        ->execute([$tpl !== '' ? $tpl : null, time(), $id]);
    return true;
}

/**
 * Слоты преленда: какая кампания стоит за каждым блоком страницы.
 * Хранятся JSON-ом в campaigns.prelander_slots: {"1":"7k","2":"faro","3":"leebet"}.
 * Слот указывает на ГОТОВУЮ кампанию, а не на строку оффера — значит у блока
 * своя рефка, свой оффер, свой whitelist и своя статистика.
 */
function prelander_slots_get($raw) {
    $v = json_decode((string)$raw, true);
    if (!is_array($v)) return ['title' => '', 'slots' => []];
    // старый формат — плоская карта {"1":"7k"}; приводим к новому
    if (!isset($v['slots'])) {
        $slots = [];
        foreach ($v as $n => $slug) if (is_scalar($slug)) $slots[(int)$n] = ['slug' => (string)$slug];
        return ['title' => '', 'slots' => $slots];
    }
    return ['title' => (string)($v['title'] ?? ''), 'slots' => (array)$v['slots']];
}

/**
 * Сохранить настройку преленда: заголовок страницы и параметры блоков.
 * $slots — [номер => ['slug'=>…, 'name'=>…, 'logo'=>…]]. Пустые поля означают
 * «как в шаблоне»: значения по умолчанию лежат в самом шаблоне, а не в коде.
 */
function set_prelander_slots($id, array $slots, $title = '') {
    $known = db()->query('SELECT slug FROM campaigns')->fetchAll(PDO::FETCH_COLUMN);
    // Кампанию-носитель в слот не пускаем: подпись была бы от одного бренда,
    // а ссылка вела бы обратно на сам преленд. У посетителя без JS (адрес
    // приходит без cid) это замкнулось бы в петлю показ -> показ.
    $self = (string)db()->query('SELECT slug FROM campaigns WHERE id = ' . (int)$id)->fetchColumn();
    $clean = [];
    foreach ($slots as $n => $row) {
        $n = (int)$n;
        if ($n < 1 || $n > 9) continue;
        $row  = (array)$row;
        $slug = normalize_slug((string)($row['slug'] ?? ''));
        if ($slug !== '' && !in_array($slug, $known, true)) $slug = '';
        if ($slug !== '' && $slug === $self) $slug = '';
        $name = trim(mb_substr((string)($row['name'] ?? ''), 0, 80));
        $logo = trim(mb_substr((string)($row['logo'] ?? ''), 0, 500));
        // картинка только по http(s) или data: — чтобы в разметку не попало
        // произвольное значение и не превратилось в чужой скрипт
        if ($logo !== '' && !preg_match('~^(https?://|data:image/|/)~i', $logo)) $logo = '';
        if ($slug === '' && $name === '' && $logo === '') continue;
        $clean[$n] = ['slug' => $slug, 'name' => $name, 'logo' => $logo];
    }
    $conf = ['title' => trim(mb_substr((string)$title, 0, 200)), 'slots' => $clean];
    db()->prepare('UPDATE campaigns SET prelander_slots = ?, updated_at = ? WHERE id = ?')
        ->execute([json_encode($conf, JSON_UNESCAPED_UNICODE), time(), (int)$id]);
    return $conf;
}

/**
 * Манифест шаблона: имя для списка, заголовок и подписи блоков по умолчанию.
 * Лежит комментариями в начале файла — шаблон сам себя описывает, и добавить
 * новый можно, ничего не правя в коде.
 */
function prelander_meta($tpl) {
    $file = prelanders_dir() . '/' . preg_replace('~[^\w.\-]~', '', (string)$tpl) . '.html';
    $meta = ['name' => (string)$tpl, 'title' => '', 'slots' => []];
    if (!is_file($file)) return $meta;
    $head = (string)@file_get_contents($file, false, null, 0, 2048);
    if (preg_match('~<!--\s*prelander:name\s+(.+?)\s*-->~u', $head, $m)) $meta['name'] = trim($m[1]);
    if (preg_match('~<!--\s*prelander:title\s+(.+?)\s*-->~u', $head, $m)) $meta['title'] = trim($m[1]);
    if (preg_match_all('~<!--\s*prelander:slot(\d+)\s+(.+?)\s*-->~u', $head, $m, PREG_SET_ORDER)) {
        foreach ($m as $x) $meta['slots'][(int)$x[1]] = trim($x[2]);
    }
    return $meta;
}

/** Каталог шаблонов прелендов (исходники) и готовых страниц (out/). */
function prelanders_dir() { return __DIR__ . '/prelanders'; }

/**
 * Список доступных шаблонов прелендов: имена *.html в prelanders/, без out/.
 */
function prelander_templates() {
    $out = [];
    foreach (glob(prelanders_dir() . '/*.html') ?: [] as $f) {
        $out[] = basename($f, '.html');
    }
    sort($out);
    return $out;
}

/**
 * Собрать готовую страницу преленда для одной кампании.
 *
 * Страница генерируется ЗАРАНЕЕ и лежит статикой — её отдаёт Apache, а не PHP.
 * В этом весь смысл: 87 КБ на каждый показ через PHP съели бы сервер, на котором
 * и так крутятся доры. Готовый файл одинаков для всех посетителей, поэтому его
 * кэширует ещё и Cloudflare — до сервера показы почти не доходят.
 *
 * Уникальность появляется не в странице, а в момент клика: кнопки ведут на
 * /go/СЛАГ?slot=N, где go.php и выдаёт clickid.
 */
function prelander_build_one($slug, $tpl, $title = '', array $slots = []) {
    $slug = normalize_slug($slug);
    $tpl  = preg_replace('~[^\w.\-]~', '', (string)$tpl);
    if ($slug === '' || $tpl === '') return false;

    $src = prelanders_dir() . '/' . $tpl . '.html';
    if (!is_file($src)) return false;
    $html = (string)@file_get_contents($src);
    if ($html === '') return false;

    $outDir = prelanders_dir() . '/out';
    if (!is_dir($outDir)) { @mkdir($outDir, 0775, true); cache_fix_owner($outDir, 0775); }

    // Значения по умолчанию берём из самого шаблона: пустое поле в настройке
    // означает «оставить как в шаблоне», а не «стереть».
    $meta  = prelander_meta($tpl);
    $conf  = ['title' => '', 'slots' => []];
    if (isset($slots['slots'])) { $conf = $slots; }
    elseif ($slots)             { foreach ($slots as $n => $v) $conf['slots'][$n] = is_array($v) ? $v : ['slug' => $v]; }

    $pageTitle = $conf['title'] !== '' ? $conf['title']
               : ($meta['title'] !== '' ? $meta['title'] : ($title !== '' ? $title : $slug));

    $map = [
        '{{GO}}'    => '/go/' . $slug,
        '{{TITLE}}' => htmlspecialchars($pageTitle, ENT_QUOTES, 'UTF-8'),
        '{{SLUG}}'  => htmlspecialchars($slug, ENT_QUOTES, 'UTF-8'),
    ];

    // Ссылка блока — рефка выбранной кампании. Ничего не выбрано — блок ведёт
    // на саму кампанию с ?slot=N, как было до появления выбора.
    for ($n = 1; $n <= 9; $n++) {
        $row    = (array)($conf['slots'][$n] ?? $conf['slots'][(string)$n] ?? []);
        $target = normalize_slug((string)($row['slug'] ?? ''));
        $nm     = (string)($row['name'] ?? '');
        if ($nm === '') $nm = $meta['slots'][$n] ?? '';      // подпись из шаблона
        $map["{{GO$n}}"]   = $target !== '' ? '/go/' . $target : '/go/' . $slug . '?slot=' . $n;
        $map["{{NAME$n}}"] = htmlspecialchars($nm, ENT_QUOTES, 'UTF-8');
        // текстовый логотип: первое слово подписи сверху, «CASINO» снизу
        $word = mb_strtoupper(trim(explode(' ', $nm)[0] ?? ''), 'UTF-8');
        $map["{{LOGO{$n}TOP}}"] = htmlspecialchars($word, ENT_QUOTES, 'UTF-8');
        $map["{{LOGO{$n}BOT}}"] = 'CASINO';
    }
    $html = strtr($html, $map);

    // Картинка блока: задана — подменяем содержимое логотипа, не задана —
    // остаётся то, что нарисовано в шаблоне.
    for ($n = 1; $n <= 9; $n++) {
        $row  = (array)($conf['slots'][$n] ?? $conf['slots'][(string)$n] ?? []);
        $logo = (string)($row['logo'] ?? '');
        if ($logo === '') continue;
        $alt  = htmlspecialchars((string)($row['name'] ?? ''), ENT_QUOTES, 'UTF-8');
        $img  = '<img src="' . htmlspecialchars($logo, ENT_QUOTES, 'UTF-8') . '" alt="' . $alt
              . '" style="max-width:100%;max-height:100%;object-fit:contain">';
        $html = preg_replace('~<!--LOGO' . $n . '-->.*?<!--/LOGO' . $n . '-->~s',
                             '<!--LOGO' . $n . '-->' . $img . '<!--/LOGO' . $n . '-->', $html, 1);
    }

    $file = $outDir . '/' . $slug . '.html';
    $tmp  = $file . '.tmp';
    // пишем во временный и переименовываем: посетитель никогда не увидит полуфайл
    if (@file_put_contents($tmp, $html, LOCK_EX) === false) return false;
    @rename($tmp, $file);
    cache_fix_owner($file, 0664);
    return true;
}

/**
 * Пересобрать карту прелендов и все готовые страницы.
 *
 * Карта — отдельный файл prelanders.php, а не поле в offers.php: формат офферов
 * трогать не стали, чтобы деплой не мог сломать отдачу рефок. go.php читает обе
 * карты из opcache, диск при этом не дёргается.
 * Возвращает число кампаний с прелендом.
 */
function prelanders_cache_rebuild() {
    $rows = db()->query("SELECT slug, name, prelander, prelander_slots FROM campaigns
                         WHERE prelander IS NOT NULL AND prelander <> ''")->fetchAll(PDO::FETCH_ASSOC);
    $map = [];
    foreach ($rows as $r) {
        $slots = prelander_slots_get($r['prelander_slots'] ?? '');   // ['title'=>…, 'slots'=>…]
        if (prelander_build_one($r['slug'], $r['prelander'], (string)$r['name'], $slots)) {
            $map[$r['slug']] = $r['prelander'];
        }
    }

    // ЗАЩИТА ОТ ПОТЕРИ СТРАНИЦ.
    // Подчищаем страницы кампаний, у которых преленд выключили, — но только
    // если пересборка вообще что-то собрала. Пустая карта означает не «всё
    // выключили», а чаще сбой: пропал шаблон, база отдала пусто, слетела
    // настройка. Один такой заход сносил рабочую страницу, и рефка начинала
    // вести на 404. Лишний файл в out/ никому не мешает: go.php ведёт на
    // преленд только по карте.
    $existing = glob(prelanders_dir() . '/out/*.html') ?: [];
    if ($map || !$existing) {
        foreach ($existing as $f) {
            if (!isset($map[basename($f, '.html')])) @unlink($f);
        }
    }

    $file = __DIR__ . '/prelanders.php';
    $php  = "<?php\n// АВТОГЕНЕРАЦИЯ. Не редактировать вручную — перезапишется.\n"
          . "// Обновлено: " . date('Y-m-d H:i:s') . "\n"
          . "// Карта: слаг => имя шаблона преленда.\n"
          . "return " . var_export($map, true) . ";\n";
    $tmp = $file . '.tmp';
    if (@file_put_contents($tmp, $php, LOCK_EX) !== false) {
        @rename($tmp, $file);
        // без сброса opcache go.php продолжил бы видеть старую карту — на этом
        // уже обжигались с whitelist доменов
        if (function_exists('opcache_invalidate')) @opcache_invalidate($file, true);
    }
    return count($map);
}

/**
 * Уровень вложенности пути: сколько сегментов «ru» в нём встречается.
 * /ru/ru/ru/bonus -> 3, /bonus -> 0. Число сегментов, а не длина пути:
 * именно так считает вложенность аналитика (ru_depth).
 */
function ru_depth($path) {
    $n = 0;
    foreach (explode('/', trim((string)$path, '/')) as $seg) {
        if (strtolower($seg) === 'ru') $n++;
    }
    return $n;
}

/**
 * Источники кампании, СГРУППИРОВАННЫЕ по корневому домену.
 * Возвращает массив групп, отсортированных по uniques DESC:
 * [
 *   [ 'root'=>'5623-1.casino', 'clicks'=>N, 'uniques'=>M, 'regs'=>K,
 *     'subs'=>[ ['source'=>'dbbet.5623-1.casino','clicks'=>..,'uniques'=>..,'regs'=>..], ... ] ],
 *   ...
 * ]
 * subs отсортированы по uniques DESC. Если в группе один поддомен и он равен
 * корню — subs всё равно содержит его (для единообразия раскрытия).
 */
function sources_grouped_by_campaign($slug, $from, $to = null) {
    $flat = sources_by_campaign($slug, $from, $to);
    if (!$flat) return [];

    $groups = [];
    foreach ($flat as $r) {
        $root = source_root($r['src']);
        if (!isset($groups[$root])) {
            $groups[$root] = ['root' => $root, 'clicks' => 0, 'uniques' => 0, 'regs' => 0, 'deps' => 0, 'subs' => []];
        }
        $groups[$root]['clicks']  += (int)$r['clicks'];
        $groups[$root]['uniques'] += (int)$r['uniques'];
        $groups[$root]['regs']    += (int)$r['regs'];
        $groups[$root]['deps']    += (int)($r['deps'] ?? 0);
        $groups[$root]['subs'][]  = [
            'source'  => $r['src'],
            'depth'   => (int)($r['depth'] ?? -1),
            'clicks'  => (int)$r['clicks'],
            'uniques' => (int)$r['uniques'],
            'regs'    => (int)$r['regs'],
            'deps'    => (int)($r['deps'] ?? 0),
        ];
    }

    // сортировка групп по uniques, и поддоменов внутри — тоже
    $groups = array_values($groups);
    usort($groups, fn($a, $b) => $b['uniques'] <=> $a['uniques'] ?: $b['clicks'] <=> $a['clicks']);
    foreach ($groups as &$g) {
        usort($g['subs'], fn($a, $b) => $b['uniques'] <=> $a['uniques'] ?: $b['clicks'] <=> $a['clicks']);
    }
    unset($g);
    return $groups;
}

/**
 * Разбивка ботов по типам для кампании за период (переклассификация UA на лету).
 * Возвращает [ ['name'=>'google','count'=>N], ... ] по убыванию.
 */
/**
 * Боты за период: Яндекс отдельно, все остальные вместе.
 *
 * Яндекс вынесен отдельно потому, что он ходит по дорам постоянно и его объём
 * говорит об индексации, а не о качестве трафика — мешать его с прочими ботами
 * в одной цифре бессмысленно.
 *
 * Считается одним проходом (SUM/CASE), без вытаскивания UA в PHP: на боевой
 * базе строк много, а GROUP BY ua по TEXT-полю дорогой.
 *
 * Возвращает ['yandex'=>N, 'other'=>N, 'total'=>N].
 */
function bots_split($from, $to = null) {
    $sql = "SELECT
              SUM(CASE WHEN LOWER(ua) LIKE '%yandex%' THEN 1 ELSE 0 END)     AS yandex,
              SUM(CASE WHEN LOWER(ua) NOT LIKE '%yandex%' THEN 1 ELSE 0 END) AS other
            FROM clicks WHERE is_bot = 1 AND ts >= ?";
    $args = [$from];
    if ($to !== null) { $sql .= ' AND ts < ?'; $args[] = $to; }
    $st = db()->prepare($sql);
    $st->execute($args);
    $r = $st->fetch(PDO::FETCH_ASSOC) ?: [];
    $y = (int)($r['yandex'] ?? 0);
    $o = (int)($r['other'] ?? 0);
    return ['yandex' => $y, 'other' => $o, 'total' => $y + $o];
}

function bot_breakdown($slug, $from, $to = null) {
    $sql = 'SELECT ua, COUNT(*) c FROM clicks WHERE slug = ? AND is_bot = 1 AND ts >= ?';
    $args = [$slug, $from];
    if ($to !== null) { $sql .= ' AND ts < ?'; $args[] = $to; }
    $sql .= ' GROUP BY ua';
    $st = db()->prepare($sql);
    $st->execute($args);
    $agg = [];
    foreach ($st->fetchAll(PDO::FETCH_ASSOC) as $r) {
        $info = classify_bot($r['ua']);
        $name = $info['name'] !== '' ? $info['name'] : 'other';
        $agg[$name] = ($agg[$name] ?? 0) + (int)$r['c'];
    }
    arsort($agg);
    $out = [];
    foreach ($agg as $name => $c) $out[] = ['name' => $name, 'count' => $c];
    return $out;
}

/**
 * Анти-флуд по IP. Возвращает true, если клик в пределах лимита (можно писать),
 * false — если IP превысил лимит за окно (флуд: редирект делаем, в базу НЕ пишем).
 * Использует APCu (если есть) или файловый счётчик во временной папке.
 */
function flood_check($ip, $limit, $window) {
    $limit  = (int)$limit;
    $window = max(1, (int)$window);
    if ($limit <= 0 || $ip === '') return true;   // выключено
    $now = time();
    $key = 'rdr_flood_' . md5($ip);

    // быстрый путь: APCu (общая память, без диска)
    if (function_exists('apcu_fetch')) {
        $rec = apcu_fetch($key);
        if (!is_array($rec) || ($rec['w'] + $window) <= $now) {
            apcu_store($key, ['w' => $now, 'c' => 1], $window);
            return true;
        }
        $rec['c']++;
        apcu_store($key, $rec, $window);
        return $rec['c'] <= $limit;
    }

    // фолбэк: файловый счётчик (один файл на IP)
    $dir = sys_get_temp_dir() . '/rdr_flood';
    if (!is_dir($dir)) @mkdir($dir, 0700, true);
    // редкая уборка старых файлов (1% запросов)
    if (mt_rand(1, 100) === 1) {
        foreach ((array)@glob($dir . '/*') as $old)
            if (@filemtime($old) < $now - 3600) @unlink($old);
    }
    $f = $dir . '/' . md5($ip);
    $fp = @fopen($f, 'c+');
    if (!$fp) return true;                          // не смогли — не мешаем юзеру
    @flock($fp, LOCK_EX);
    $w = $now; $c = 0;
    $data = stream_get_contents($fp);
    if ($data && strpos($data, ' ') !== false) {
        [$w0, $c0] = explode(' ', trim($data));
        if ((int)$w0 + $window > $now) { $w = (int)$w0; $c = (int)$c0; }
    }
    $c++;
    @ftruncate($fp, 0); rewind($fp); @fwrite($fp, $w . ' ' . $c);
    @flock($fp, LOCK_UN); @fclose($fp);
    return $c <= $limit;
}

/**
 * Автоочистка: удаляет клики старше retention_days.
 * Срабатывает не чаще раза в сутки (метка last_cleanup в meta).
 *
 * ВАЖНО про нагрузку. Раньше эта функция вызывалась из панели и удаляла всё
 * одним DELETE: юзер, открывший статистику, ждал удаления десятков тысяч
 * строк (вплоть до таймаута PHP), а сам DELETE держал блокировки InnoDB и
 * конфликтовал с импортом, который пишет в ту же таблицу.
 *
 * Теперь:
 *   - чистим ТОЛЬКО из CLI (крон), веб-запросы сразу выходят;
 *   - удаляем пачками по $batch строк, чтобы транзакции были короткими;
 *   - за один заход удаляем не больше $maxBatches пачек, остальное догонит
 *     следующий запуск. Так очистка никогда не растягивается надолго.
 */
function maybe_cleanup($retentionDays, $batch = 5000, $maxBatches = 20) {
    $retentionDays = (int)$retentionDays;
    if ($retentionDays <= 0) return 0;
    if (php_sapi_name() !== 'cli') return 0;          // из панели не чистим

    $pdo  = db();
    $last = (int)($pdo->query("SELECT v FROM meta WHERE k='last_cleanup'")->fetchColumn() ?: 0);
    if (time() - $last < 86400) return 0;             // уже чистили сегодня

    $cutoff = time() - $retentionDays * 86400;
    $batch  = max(100, (int)$batch);

    if (db_driver() === 'mysql') {
        $st = $pdo->prepare('DELETE FROM clicks WHERE ts < ? LIMIT ' . $batch);
    } else {
        // SQLite собирается без SQLITE_ENABLE_UPDATE_DELETE_LIMIT — режем подзапросом
        $st = $pdo->prepare('DELETE FROM clicks WHERE id IN
                             (SELECT id FROM clicks WHERE ts < ? LIMIT ' . $batch . ')');
    }

    $total = 0;
    for ($i = 0; $i < $maxBatches; $i++) {
        $st->execute([$cutoff]);
        $n = $st->rowCount();
        $total += $n;
        if ($n < $batch) break;                       // старых больше нет
    }

    meta_upsert('last_cleanup', time());
    return $total;
}

/**
 * Простые геттер/сеттер для таблицы meta.
 */
function meta_get($k, $default = null) {
    $st = db()->prepare('SELECT v FROM meta WHERE k = ?');
    $st->execute([$k]);
    $v = $st->fetchColumn();
    return $v === false ? $default : $v;
}
function meta_set($k, $v) {
    meta_upsert($k, $v);
}

/**
 * Кэш тяжёлых агрегатов панели.
 *
 * Клики попадают в базу только при импорте (крон, раз в час), поэтому
 * пересчитывать сводки/график/гео на КАЖДУЮ перезагрузку панели незачем:
 * до следующего импорта результат не изменится. Замер на боевой базе
 * (889k кликов) показал 6.4с на одну перезагрузку, из них 45% — график
 * за 30 дней и 23% — сводка по кампаниям.
 *
 * Ключ кэша включает метку последнего импорта (meta.last_import), поэтому
 * после каждого импорта кэш инвалидируется сам, а между импортами живёт.
 * $ttl — страховка на случай, если метки нет (старая база / импорт не писал).
 *
 * Файлы лежат в cache/ и создаются веб-процессом (панель). Крон эти функции
 * не вызывает, так что конфликта прав root/www-root нет.
 */
define('PANEL_CACHE_VER', 3);   // 2 — депы; 3 — из daily_stats убрана RU-разбивка

/**
 * Выровнять владельца файла/каталога кэша по владельцу config.php.
 *
 * Кэш пишут два разных пользователя: панель под www-root и крон (прогрев) под
 * root. Если файл останется root-овым, панель не сможет его перезаписать и кэш
 * «застынет». Проверку «я root?» не делаем через posix_geteuid() — расширения
 * posix на сервере нет; chown/chgrp просто вернут false у непривилегированного
 * процесса, и это нормально.
 */
function cache_fix_owner($path, $mode) {
    $owner = @fileowner(__DIR__ . '/config.php');
    $group = @filegroup(__DIR__ . '/config.php');
    if ($owner !== false) @chown($path, $owner);
    if ($group !== false) @chgrp($path, $group);
    @chmod($path, $mode);
}

/** Каталог кэша (создаётся при первом обращении, с правами под веб-процесс). */
function cache_dir() {
    $dir = __DIR__ . '/cache';
    if (!is_dir($dir)) {
        @mkdir($dir, 0775, true);
        cache_fix_owner($dir, 0775);
    }
    // содержимое кэша наружу не отдаём (на случай, если корневой .htaccess не применится)
    $ht = $dir . '/.htaccess';
    if (!is_file($ht) && @file_put_contents($ht, "Require all denied\n") !== false) {
        cache_fix_owner($ht, 0664);
    }
    return $dir;
}

function panel_cache($key, callable $build, $ttl = 3600) {
    static $stamp = null;
    $dir = cache_dir();

    if ($stamp === null) {
        try { $stamp = (string)(int)meta_get('last_import', 0); }
        catch (Throwable $e) { $stamp = '0'; }
    }

    // PANEL_CACHE_VER — версия структуры кэшируемых данных. Бампать, когда в
    // агрегаты добавляются новые поля: иначе после деплоя панель прочитает
    // старый файл, где этих полей ещё нет.
    $safe = preg_replace('~[^\w.-]~', '_', (string)$key);
    $file = $dir . '/' . $safe . '_v' . PANEL_CACHE_VER . '_' . $stamp . '.cache';

    if (is_file($file) && (time() - (int)@filemtime($file)) < $ttl) {
        $raw = @file_get_contents($file);
        if ($raw !== false) {
            $val = @unserialize($raw);
            if ($val !== false || $raw === 'b:0;') return $val;   // false — валидное значение
        }
    }

    $val = $build();
    @file_put_contents($file, serialize($val), LOCK_EX);
    cache_fix_owner($file, 0664);

    // подчищаем версии этого же ключа от прошлых импортов и прошлых версий схемы
    foreach (glob($dir . '/' . $safe . '_v*.cache') ?: [] as $old) {
        if ($old !== $file) @unlink($old);
    }
    return $val;
}

/** Сбросить кэш панели целиком (после правки кампаний, очистки истории и т.п.). */
function panel_cache_flush() {
    foreach (glob(__DIR__ . '/cache/*.cache') ?: [] as $f) @unlink($f);
}

/**
 * Прогрев кэша панели — считает тяжёлые агрегаты заранее.
 *
 * Вызывается из import.php сразу после импорта: метка last_import только что
 * сменилась, значит весь кэш инвалидирован, и первый заход в панель иначе ждал
 * бы полного пересчёта (на боевой базе это ~12 секунд — вплоть до таймаута).
 * Крон считает это за себя, и панель всегда открывается из готового кэша.
 *
 * Ключи и аргументы должны совпадать с тем, что запрашивает stats.php.
 * Возвращает число прогретых ключей.
 */
function panel_cache_warm($budgetSec = 30) {
    $t0         = microtime(true);
    $now        = time();
    $todayStart = strtotime('today');
    $pdo        = db();

    $periods = [
        'today'     => [$todayStart,          $now + 1],
        'yesterday' => [$todayStart - 86400,  $todayStart],
        '7d'        => [$now - 7  * 86400,    $now + 1],
        '30d'       => [$now - 30 * 86400,    $now + 1],
    ];

    // сводка по кампаниям — тот же запрос, что в stats.php
    $summary = function ($from, $to) use ($pdo) {
        return function () use ($pdo, $from, $to) {
            $st = $pdo->prepare("
                SELECT cl.slug, COALESCE(c.name,'') AS name,
                       SUM(CASE WHEN cl.is_bot=0 THEN 1 ELSE 0 END)                       AS humans,
                       COUNT(DISTINCT CASE WHEN cl.is_bot=0 THEN cl.ip END)               AS uniques,
                       COUNT(DISTINCT CASE WHEN cl.is_bot=0 AND cl.country='RU' THEN cl.ip END) AS uniques_ru,
                       SUM(CASE WHEN cl.is_bot=1 THEN 1 ELSE 0 END)                       AS bots,
                       MAX(cl.ts)                                                         AS last_ts
                FROM clicks cl
                LEFT JOIN campaigns c ON c.slug = cl.slug
                WHERE cl.ts >= ? AND cl.ts < ? AND " . sql_visit('cl') . "
                GROUP BY cl.slug
                ORDER BY humans DESC, bots DESC
            ");
            $st->execute([$from, $to]);
            return $st->fetchAll(PDO::FETCH_ASSOC);
        };
    };

    // Порядок = приоритет. Сначала то, что открывается почти всегда (главная за
    // «сегодня» + график), потом вкладка настроек, и только потом длинные периоды.
    // Если бюджет времени выйдет — остаток посчитается лениво при первом открытии.
    $jobs = [];
    [$f, $t] = $periods['today'];
    $jobs[] = ['summary_today', $summary($f, $t)];
    $jobs[] = ['geo_today',     fn() => geo_stats($f, $t)];
    $jobs[] = ['geocamp_today', fn() => geo_by_campaign($f, null, $t)];
    $jobs[] = ['bots_today',    fn() => bots_split($f, $t)];
    $jobs[] = ['daily30',       fn() => daily_stats(30)];
    $jobs[] = ['health',        fn() => service_health()];
    $jobs[] = ['lastbycamp',    fn() => $pdo->query(
        "SELECT cl.slug, COALESCE(c.name,'') name, MAX(cl.ts) last
         FROM clicks cl LEFT JOIN campaigns c ON c.slug=cl.slug
         GROUP BY cl.slug ORDER BY last DESC LIMIT 30")->fetchAll(PDO::FETCH_ASSOC)];
    [$f, $t] = $periods['today'];
    $jobs[] = ['convslug_today', fn() => conversions_by_slug($f, $t)];
    $jobs[] = ['srcall_today',   fn() => sources_grouped_by_campaign(null, $f, $t)];
    foreach (['yesterday', '7d', '30d'] as $key) {
        [$pf, $pt] = $periods[$key];
        $jobs[] = ["summary_$key",  $summary($pf, $pt)];
        $jobs[] = ["geo_$key",      fn() => geo_stats($pf, $pt)];
        $jobs[] = ["geocamp_$key",  fn() => geo_by_campaign($pf, null, $pt)];
        $jobs[] = ["bots_$key",     fn() => bots_split($pf, $pt)];
        $jobs[] = ["convslug_$key", fn() => conversions_by_slug($pf, $pt)];
        $jobs[] = ["srcall_$key",   fn() => sources_grouped_by_campaign(null, $pf, $pt)];
    }

    $done = $skipped = 0;
    $budgetLeft = function () use ($budgetSec, $t0) {
        return $budgetSec <= 0 || (microtime(true) - $t0) < $budgetSec;
    };

    foreach ($jobs as [$key, $build]) {
        if (!$budgetLeft()) { $skipped++; continue; }
        panel_cache($key, $build);
        $done++;
    }

    // Прогрев страниц кампаний. Открытие кампании за 7/30 дней — самые тяжёлые
    // запросы панели (COUNT DISTINCT ip и GROUP BY по всем кликам кампании), и
    // без прогрева первый заход ждал бы несколько секунд. Греем только топ
    // кампаний по трафику и только пока есть бюджет: сводки выше по приоритету,
    // и если время вышло — остальное досчитается лениво, сервер не нагружаем.
    $topSlugs = [];
    $summary7d = $budgetLeft()
        ? (array)panel_cache('summary_7d', $summary($periods['7d'][0], $periods['7d'][1]))
        : [];
    foreach ($summary7d as $row) {
        $topSlugs[] = (string)$row['slug'];
        if (count($topSlugs) >= 5) break;
    }
    foreach ($topSlugs as $slug) {
        foreach (['today', '7d', '30d'] as $pk) {
            if (!$budgetLeft()) { $skipped++; continue 2; }
            [$pf, $pt] = $periods[$pk];
            $dkey = preg_replace('~[^\w.-]~', '_', $slug) . '_' . $pk;
            panel_cache("dsum_$dkey", function () use ($pdo, $slug, $pf, $pt) {
                $st = $pdo->prepare("SELECT
                        SUM(CASE WHEN is_bot=0 THEN 1 ELSE 0 END) AS humans,
                        COUNT(DISTINCT CASE WHEN is_bot=0 THEN ip END) AS uniques,
                        COUNT(DISTINCT CASE WHEN is_bot=0 AND country='RU' THEN ip END) AS uniques_ru,
                        SUM(CASE WHEN is_bot=1 THEN 1 ELSE 0 END) AS bots
                    FROM clicks WHERE slug = ? AND ts >= ? AND ts < ? AND " . sql_visit() . "");
                $st->execute([$slug, $pf, $pt]);
                return $st->fetch(PDO::FETCH_ASSOC) ?: ['humans'=>0,'uniques'=>0,'uniques_ru'=>0,'bots'=>0];
            });
            panel_cache("dcnt_$dkey", function () use ($pdo, $slug, $pf, $pt) {
                $st = $pdo->prepare('SELECT COUNT(*) FROM clicks WHERE slug = ? AND ts >= ? AND ts < ? AND ' . sql_visit());
                $st->execute([$slug, $pf, $pt]);
                return (int)$st->fetchColumn();
            });
            panel_cache("dgeo_$dkey", function () use ($slug, $pf, $pt) {
                $g = geo_by_campaign($pf, $slug, $pt);
                return $g[$slug] ?? [];
            });
            panel_cache("dsrc_$dkey", fn() => sources_grouped_by_campaign($slug, $pf, $pt));
            $done += 4;
        }
    }

    return ['warmed' => $done, 'skipped' => $skipped, 'sec' => round(microtime(true) - $t0, 1)];
}

/**
 * Heartbeat: отметка «сервис жив». Пишется не чаще раза в минуту (дёшево).
 * Если между прошлой отметкой и сейчас прошло >= $gapThreshold секунд —
 * значит был разрыв (возможный простой), и он записывается в журнал gaps
 * задним числом, как только сервис снова ожил и пришёл запрос.
 */
function heartbeat($gapThreshold = 300) {
    $now = time();
    if (meta_get('first_seen') === null) meta_set('first_seen', $now);
    $last = (int)meta_get('hb_last', 0);
    $gapThreshold = max(60, (int)$gapThreshold);

    if ($last > 0 && ($now - $last) >= $gapThreshold) {
        // обнаружено окно тишины между $last и $now
        db()->prepare('INSERT INTO gaps (start_ts, end_ts, seconds) VALUES (?,?,?)')
            ->execute([$last, $now, $now - $last]);
        // не разрастаться: храним последние 300 записей.
        // Пишем в два шага, потому что MySQL не поддерживает LIMIT в подзапросе.
        $keepFrom = (int)db()->query('SELECT id FROM gaps ORDER BY id DESC LIMIT 1 OFFSET 299')->fetchColumn();
        if ($keepFrom > 0) {
            db()->exec("DELETE FROM gaps WHERE id < $keepFrom");
        }
    }
    if ($now - $last >= 60) meta_set('hb_last', $now);
}

/**
 * Журнал окон тишины (возможных простоев), новые сверху.
 */
function recent_gaps($limit = 100) {
    $limit = max(1, min(500, (int)$limit));
    return db()->query("SELECT start_ts, end_ts, seconds FROM gaps ORDER BY id DESC LIMIT $limit")
               ->fetchAll(PDO::FETCH_ASSOC);
}

/**
 * Сводка здоровья сервиса для раздела «Настройки».
 */
function service_health() {
    $pdo = db();
    $now = time();
    $lastClick    = (int)($pdo->query('SELECT MAX(ts) FROM clicks')->fetchColumn() ?: 0);
    $lastPostback = (int)($pdo->query('SELECT MAX(ts) FROM conversions')->fetchColumn() ?: 0);
    return [
        'now'           => $now,
        'first_seen'    => (int)meta_get('first_seen', $now),
        'hb_last'       => (int)meta_get('hb_last', 0),
        'last_click'    => $lastClick,
        'last_postback' => $lastPostback,
        'total_clicks'  => (int)($pdo->query('SELECT COUNT(*) FROM clicks')->fetchColumn() ?: 0),
        'total_conv'    => (int)($pdo->query('SELECT COUNT(*) FROM conversions')->fetchColumn() ?: 0),
    ];
}

/**
 * Клики по дням за последние $days дней: [ ['d'=>'2026-06-10','humans'=>..,'uniques'=>..,'bots'=>..], ... ].
 * Пустые дни заполняются нулями, чтобы график был непрерывным.
 */
function daily_stats($days = 30) {
    $days = max(1, (int)$days);
    $from = time() - $days * 86400;
    $dayExpr = sql_day('ts');
    $st = db()->prepare("
        SELECT $dayExpr AS d,
               SUM(CASE WHEN is_bot=0 THEN 1 ELSE 0 END)      AS humans,
               COUNT(DISTINCT CASE WHEN is_bot=0 THEN ip END) AS uniques,
               SUM(CASE WHEN is_bot=1 THEN 1 ELSE 0 END)      AS bots
        FROM clicks WHERE ts >= ? AND " . sql_visit() . "
        GROUP BY d
    ");
    $st->execute([$from]);
    $byDay = [];
    foreach ($st->fetchAll(PDO::FETCH_ASSOC) as $r) $byDay[$r['d']] = $r;

    // реги и депы по дням — общие и RU-подсчёт через привязку по clickid.
    // Считаются независимо: у одного игрока и рег, и деп — две отдельные строки.
    $rg = db()->prepare("SELECT $dayExpr d,
                                SUM(CASE WHEN status IN('reg','registration','lead') THEN 1 ELSE 0 END) regs,
                                SUM(CASE WHEN status IN('dep','deposit','sale','ftd','purchase') THEN 1 ELSE 0 END) deps
                         FROM conversions WHERE ts >= ? GROUP BY d");
    $rg->execute([$from]);
    $regByDay = $depByDay = [];
    foreach ($rg->fetchAll(PDO::FETCH_ASSOC) as $r) {
        $regByDay[$r['d']] = (int)$r['regs'];
        $depByDay[$r['d']] = (int)$r['deps'];
    }

    // RU-разбивка здесь не считается: график её больше не показывает, а она
    // требовала JOIN conversions×clicks и COUNT(DISTINCT ... country='RU')
    // по всей таблице кликов — самый дорогой кусок этого запроса.
    // RU-колонки в сводке по кампаниям считаются отдельно (conversions_by_slug).

    $out = [];
    for ($i = $days - 1; $i >= 0; $i--) {
        $d = date('Y-m-d', time() - $i * 86400);
        $out[] = [
            'd'       => $d,
            'humans'  => (int)($byDay[$d]['humans']  ?? 0),
            'uniques' => (int)($byDay[$d]['uniques'] ?? 0),
            'bots'    => (int)($byDay[$d]['bots']    ?? 0),
            'regs'    => (int)($regByDay[$d] ?? 0),
            'deps'    => (int)($depByDay[$d] ?? 0),
        ];
    }
    return $out;
}

/**
 * Последние принятые постбеки (с гео по клику).
 */
function recent_conversions($limit = 50, $offset = 0, $from = null, $to = null) {
    $limit  = max(1, min(500, (int)$limit));
    $offset = max(0, (int)$offset);

    $where = '';
    $args  = [];
    if ($from !== null) { $where .= ' WHERE cv.ts >= ?'; $args[] = $from;
        if ($to !== null) { $where .= ' AND cv.ts < ?'; $args[] = $to; } }

    // Данные клика тянем подзапросами по clickid (idx_clickid): их 4 на строку,
    // но страница показывает десятки записей, а не тысячи — на замерах это единицы мс.
    // Страну, источник, реферер и путь берём из снимка в самой строке конверсии:
    // он сделан на момент привязки и переживает удаление старых кликов. Подзапрос
    // остаётся запасным вариантом для строк, записанных до появления снимка.
    $st = db()->prepare("SELECT cv.ts, cv.clickid, cv.status, cv.payout, cv.slug, cv.ip AS postback_ip, cv.lp,
                          COALESCE(cv.country, (SELECT country FROM clicks WHERE clickid = cv.clickid ORDER BY id DESC LIMIT 1)) AS country,
                          COALESCE(cv.sub,     (SELECT source  FROM clicks WHERE clickid = cv.clickid ORDER BY id DESC LIMIT 1)) AS source,
                          COALESCE(cv.ref,     (SELECT referer FROM clicks WHERE clickid = cv.clickid ORDER BY id DESC LIMIT 1)) AS referer,
                          (SELECT ua       FROM clicks WHERE clickid = cv.clickid ORDER BY id DESC LIMIT 1) AS ua,
                          (SELECT ip       FROM clicks WHERE clickid = cv.clickid ORDER BY id DESC LIMIT 1) AS ip
                        FROM conversions cv $where
                        ORDER BY cv.ts DESC, cv.id DESC LIMIT $limit OFFSET $offset");
    $st->execute($args);
    return $st->fetchAll(PDO::FETCH_ASSOC);
}

/** Сколько всего конверсий за период — для пагинации. */
function conversions_count($from = null, $to = null) {
    $sql  = 'SELECT COUNT(*) FROM conversions';
    $args = [];
    if ($from !== null) { $sql .= ' WHERE ts >= ?'; $args[] = $from;
        if ($to !== null) { $sql .= ' AND ts < ?'; $args[] = $to; } }
    $st = db()->prepare($sql);
    $st->execute($args);
    return (int)$st->fetchColumn();
}

/**
 * Все конверсии за период для выгрузки в CSV — без подзапросов на строку.
 * Данные клика подтягиваются одним JOIN, иначе на тысячах строк выгрузка
 * превратилась бы в тысячи отдельных запросов.
 */
function conversions_export($from, $to = null) {
    // Страна, источник, реферер и путь — из снимка в строке конверсии, с откатом
    // на данные клика для строк, записанных до появления снимка.
    $sql = "SELECT cv.ts, cv.status, cv.clickid, cv.slug, cv.lp,
                   COALESCE(c.name,'') AS name,
                   COALESCE(cv.country, cl.country) AS country,
                   COALESCE(cv.sub,     cl.source)  AS source,
                   COALESCE(cv.ref,     cl.referer) AS referer,
                   cl.ip AS user_ip, cv.ip AS postback_ip
            FROM conversions cv
            LEFT JOIN clicks cl ON cl.clickid = cv.clickid
            LEFT JOIN campaigns c ON c.slug = cv.slug
            WHERE cv.ts >= ?";
    $args = [$from];
    if ($to !== null) { $sql .= ' AND cv.ts < ?'; $args[] = $to; }
    $sql .= ' ORDER BY cv.ts DESC';
    $st = db()->prepare($sql);
    $st->execute($args);
    return $st;   // возвращаем курсор: выгрузка идёт построчно, без загрузки всего в память
}

/**
 * Принудительная очистка истории: удаляет клики, конверсии и лог постбеков.
 * Кампании и историю смены оферов НЕ трогает.
 */
function clear_history() {
    $pdo = db();
    $clicks = $pdo->exec('DELETE FROM clicks');
    $conv   = $pdo->exec('DELETE FROM conversions');
    $pdo->exec('DELETE FROM postback_log');
    return ['clicks' => (int)$clicks, 'conversions' => (int)$conv];
}

/** Записать в сырой лог факт обращения к postback.php (любой исход). */
function log_postback($ip, $query, $outcome) {
    try {
        $pdo = db();
        $pdo->prepare('INSERT INTO postback_log (ts, ip, query, outcome) VALUES (?,?,?,?)')
            ->execute([time(), substr((string)$ip, 0, 64), substr((string)$query, 0, 500), substr((string)$outcome, 0, 32)]);
        // не разрастаемся: держим последние 500
        $pdo->exec('DELETE FROM postback_log WHERE id <= (SELECT MAX(id) - 500 FROM postback_log)');
    } catch (Throwable $e) { /* лог не критичен */ }
}

/** Последние записи сырого лога постбеков. */
function recent_postback_log($n = 50) {
    $n = max(1, min(200, (int)$n));
    return db()->query("SELECT ts, ip, query, outcome FROM postback_log ORDER BY id DESC LIMIT $n")->fetchAll(PDO::FETCH_ASSOC);
}

/**
 * Гео-разрез по кампаниям (только люди): slug => [ ['country','uniques','clicks'], ... ]
 * Отсортировано по уникам. Если задан $slug — только эта кампания.
 */
function geo_by_campaign($from, $slug = null, $to = null) {
    $sql = "SELECT slug, COALESCE(NULLIF(country,''),'??') AS country,
                   COUNT(DISTINCT ip) AS uniques, COUNT(*) AS clicks
            FROM clicks WHERE ts >= ? AND is_bot = 0 AND " . sql_visit() . "";
    $args = [$from];
    if ($to !== null) { $sql .= ' AND ts < ?'; $args[] = $to; }
    if ($slug !== null) { $sql .= ' AND slug = ?'; $args[] = $slug; }
    $sql .= ' GROUP BY slug, country ORDER BY uniques DESC, clicks DESC';
    $st = db()->prepare($sql);
    $st->execute($args);
    $out = [];
    foreach ($st->fetchAll(PDO::FETCH_ASSOC) as $r) {
        $out[$r['slug']][] = ['country'=>$r['country'], 'uniques'=>(int)$r['uniques'], 'clicks'=>(int)$r['clicks']];
    }
    return $out;
}

/**
 * Гео-статистика по странам за период (с $from):
 * [ ['country'=>'RU','humans'=>..,'uniques'=>..,'bots'=>..], ... ] по убыванию.
 * Страна берётся из заголовка Cloudflare CF-IPCountry (двухбуквенный код).
 */
function geo_stats($from, $to = null) {
    $sql = "
        SELECT COALESCE(NULLIF(country,''),'??') AS country,
               SUM(CASE WHEN is_bot=0 THEN 1 ELSE 0 END)      AS humans,
               COUNT(DISTINCT CASE WHEN is_bot=0 THEN ip END) AS uniques,
               SUM(CASE WHEN is_bot=1 THEN 1 ELSE 0 END)      AS bots
        FROM clicks WHERE ts >= ? AND " . sql_visit() . "";
    $args = [$from];
    if ($to !== null) { $sql .= ' AND ts < ?'; $args[] = $to; }
    $sql .= ' GROUP BY country ORDER BY humans DESC, bots DESC';
    $st = db()->prepare($sql);
    $st->execute($args);
    return $st->fetchAll(PDO::FETCH_ASSOC);
}

/** Двухбуквенный код страны -> эмодзи-флаг (RU -> 🇷🇺). Без зависимости от mbstring. */
function country_flag($cc) {
    $cc = strtoupper(trim((string)$cc));
    if (!preg_match('~^[A-Z]{2}$~', $cc)) return "\xF0\x9F\x8F\xB3"; // 🏳
    $cp = function ($n) {  // code point -> UTF-8
        return chr(0xF0 | ($n >> 18)) . chr(0x80 | (($n >> 12) & 0x3F))
             . chr(0x80 | (($n >> 6) & 0x3F)) . chr(0x80 | ($n & 0x3F));
    };
    return $cp(0x1F1E6 + ord($cc[0]) - 65) . $cp(0x1F1E6 + ord($cc[1]) - 65);
}

/**
 * Записать конверсию из постбэка. Привязываем к клику по clickid (берём его slug).
 * Возвращает ['ok'=>bool,'found'=>bool,'slug'=>?].
 */
function record_conversion($clickid, $status, $payout, $ip, $raw = '') {
    $clickid = substr(preg_replace('~[^\w.\-]~', '', (string)$clickid), 0, 64);
    $status  = substr(preg_replace('~[^\w.\-]~', '', (string)$status), 0, 32) ?: 'conv';
    $payout  = (float)$payout;
    if ($clickid === '') return ['ok' => false, 'found' => false, 'slug' => null];

    $pdo = db();
    // Данные клика снимаем в строку конверсии сразу (не только slug): выгрузка
    // для аналитики не должна зависеть от того, жив ли ещё клик — retention его
    // однажды удалит. Если клик ещё не доехал из лога, всё это допишет
    // relink_conversions() при ближайшем импорте.
    $st = $pdo->prepare('SELECT slug, source, referer, country, lp FROM clicks
                         WHERE clickid = ? ORDER BY id DESC LIMIT 1');
    $st->execute([$clickid]);
    $cl    = $st->fetch(PDO::FETCH_ASSOC);
    $found = $cl !== false;

    $pdo->prepare('INSERT INTO conversions (clickid, slug, status, payout, ts, ip, sub, ref, country, lp, linked_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)')
        ->execute([
            $clickid, $found ? $cl['slug'] : null, $status, $payout, time(), substr((string)$ip, 0, 64),
            $found ? $cl['source']  : null,
            $found ? $cl['referer'] : null,
            $found ? $cl['country'] : null,
            $found ? $cl['lp']      : null,
            $found ? time()         : null,
        ]);

    return ['ok' => true, 'found' => $found, 'slug' => $found ? $cl['slug'] : null];
}

/**
 * Досвязать конверсии с кликами (лечит «не привязан»).
 *
 * Постбек почти всегда приходит РАНЬШЕ, чем клик доедет до MySQL: go.php пишет
 * клик в clicks.log, а import.php переливает лог в базу по крону (раз в час).
 * В момент постбека record_conversion() клика ещё не видит и ставит slug = NULL —
 * в панели это «не привязан». Клик появляется в базе позже, но привязка сама
 * не пересчитывалась — конверсия оставалась непривязанной навсегда.
 *
 * Функция проходит по конверсиям с пустым slug и подставляет slug клика с тем же
 * clickid. Вызывается из import.php сразу после заливки кликов — то есть ровно
 * тогда, когда в базе появились новые клики, к которым можно привязаться.
 *
 * $sinceDays — глубина просмотра (0 = вся история). Ограничение нужно, чтобы
 * часовой крон не перебирал таблицу целиком; для разовой ретро-привязки
 * вызывать с 0.
 *
 * Возвращает число досвязанных конверсий.
 */
function relink_conversions($sinceDays = 7) {
    $pdo   = db();
    $args  = [];
    $since = null;
    if ($sinceDays > 0) $since = time() - (int)$sinceDays * 86400;

    // Вместе со slug снимаем в строку конверсии и данные клика (sub/ref/country).
    // Это снимок на момент привязки, а не ссылка: выгрузка для аналитики обязана
    // при повторном запросе того же диапазона отдавать те же строки, а чистка
    // старых кликов по retention иначе обнулила бы конверсии задним числом.
    // linked_at — отметка «строка финальная», по ней аналитик видит, что тут
    // больше ничего не изменится.
    if (db_driver() === 'mysql') {
        $sql = "UPDATE conversions cv
                JOIN clicks c ON c.clickid = cv.clickid
                SET cv.slug = c.slug, cv.sub = c.source, cv.ref = c.referer,
                    cv.country = c.country, cv.lp = c.lp, cv.linked_at = ?
                WHERE cv.linked_at IS NULL AND cv.clickid <> ''";
        $args[] = time();
        if ($since !== null) { $sql .= ' AND cv.ts >= ?'; $args[] = $since; }
    } else {
        // SQLite не умеет UPDATE ... JOIN — коррелированный подзапрос
        $sql = "UPDATE conversions
                SET slug      = (SELECT c.slug    FROM clicks c WHERE c.clickid = conversions.clickid ORDER BY c.id DESC LIMIT 1),
                    sub       = (SELECT c.source  FROM clicks c WHERE c.clickid = conversions.clickid ORDER BY c.id DESC LIMIT 1),
                    ref       = (SELECT c.referer FROM clicks c WHERE c.clickid = conversions.clickid ORDER BY c.id DESC LIMIT 1),
                    country   = (SELECT c.country FROM clicks c WHERE c.clickid = conversions.clickid ORDER BY c.id DESC LIMIT 1),
                    lp        = (SELECT c.lp      FROM clicks c WHERE c.clickid = conversions.clickid ORDER BY c.id DESC LIMIT 1),
                    linked_at = ?
                WHERE linked_at IS NULL AND clickid <> ''
                  AND EXISTS (SELECT 1 FROM clicks c WHERE c.clickid = conversions.clickid)";
        $args[] = time();
        if ($since !== null) { $sql .= ' AND ts >= ?'; $args[] = $since; }
    }

    $st = $pdo->prepare($sql);
    $st->execute($args);
    return $st->rowCount();
}

/**
 * ИТОГО конверсий за период — ВСЕ, включая непривязанные к кампании (slug IS NULL).
 * Возвращает ['reg'=>N,'dep'=>N,'reg_ru'=>N,'dep_ru'=>N,'reg_unlinked'=>N,'dep_unlinked'=>N,'payout'=>S].
 * Используется для счётчиков в шапке (чтобы совпадали с графиком и таблицей постбеков).
 *
 * Реги и депы считаются НЕЗАВИСИМО по своему status: у одного игрока приходят
 * два постбека (reg и dep) — это две строки в conversions, и деп ничего не
 * отнимает у регов.
 */
function conversions_totals($from, $to = null) {
    $sql = "SELECT
              SUM(CASE WHEN status IN('reg','registration','lead') THEN 1 ELSE 0 END) AS reg,
              SUM(CASE WHEN status IN('dep','deposit','sale','ftd','purchase') THEN 1 ELSE 0 END) AS dep,
              SUM(CASE WHEN status IN('reg','registration','lead') AND (slug IS NULL OR slug='') THEN 1 ELSE 0 END) AS reg_unlinked,
              SUM(CASE WHEN status IN('dep','deposit','sale','ftd','purchase') AND (slug IS NULL OR slug='') THEN 1 ELSE 0 END) AS dep_unlinked,
              COALESCE(SUM(payout),0) AS payout
            FROM conversions WHERE ts >= ?";
    $args = [$from];
    if ($to !== null) { $sql .= ' AND ts < ?'; $args[] = $to; }
    $st = db()->prepare($sql);
    $st->execute($args);
    $r = $st->fetch(PDO::FETCH_ASSOC) ?: [];

    // RU-реги и RU-депы (привязанные к RU-клику) — одним запросом
    $sqlRu = "SELECT
                SUM(CASE WHEN cv.status IN('reg','registration','lead') THEN 1 ELSE 0 END) AS reg_ru,
                SUM(CASE WHEN cv.status IN('dep','deposit','sale','ftd','purchase') THEN 1 ELSE 0 END) AS dep_ru
              FROM conversions cv
              JOIN clicks cl ON cl.clickid = cv.clickid
              WHERE cv.ts >= ? AND cl.country='RU'";
    $argsRu = [$from];
    if ($to !== null) { $sqlRu .= ' AND cv.ts < ?'; $argsRu[] = $to; }
    $st = db()->prepare($sqlRu);
    $st->execute($argsRu);
    $ru = $st->fetch(PDO::FETCH_ASSOC) ?: [];

    return [
        'reg'          => (int)($r['reg'] ?? 0),
        'dep'          => (int)($r['dep'] ?? 0),
        'reg_ru'       => (int)($ru['reg_ru'] ?? 0),
        'dep_ru'       => (int)($ru['dep_ru'] ?? 0),
        'reg_unlinked' => (int)($r['reg_unlinked'] ?? 0),
        'dep_unlinked' => (int)($r['dep_unlinked'] ?? 0),
        'payout'       => (float)($r['payout'] ?? 0),
    ];
}

/**
 * Конверсии по кампаниям за период (с $from):
 * [slug => ['reg'=>N,'dep'=>N,'other'=>N,'payout'=>S]].
 */
function conversions_by_slug($from, $to = null) {
    // общие реги/депы по кампаниям
    $sql = "
        SELECT slug,
               SUM(CASE WHEN status IN('reg','registration','lead') THEN 1 ELSE 0 END) AS reg,
               SUM(CASE WHEN status IN('dep','deposit','sale','ftd','purchase') THEN 1 ELSE 0 END) AS dep,
               SUM(CASE WHEN status NOT IN('reg','registration','lead','dep','deposit','sale','ftd','purchase') THEN 1 ELSE 0 END) AS other,
               COALESCE(SUM(payout),0) AS payout
        FROM conversions
        WHERE ts >= ? AND slug IS NOT NULL";
    $args = [$from];
    if ($to !== null) { $sql .= ' AND ts < ?'; $args[] = $to; }
    $sql .= ' GROUP BY slug';
    $st = db()->prepare($sql);
    $st->execute($args);
    $out = [];
    foreach ($st->fetchAll(PDO::FETCH_ASSOC) as $r)
        $out[$r['slug']] = [
            'reg'=>(int)$r['reg'], 'dep'=>(int)$r['dep'],
            'other'=>(int)$r['other'], 'payout'=>(float)$r['payout'],
            'reg_ru'=>0, 'dep_ru'=>0,
        ];

    // RU-реги и RU-депы: привязка через clickid → country='RU'
    $sqlRu = "SELECT cl.slug,
                     SUM(CASE WHEN cv.status IN('reg','registration','lead') THEN 1 ELSE 0 END) AS reg_ru,
                     SUM(CASE WHEN cv.status IN('dep','deposit','sale','ftd','purchase') THEN 1 ELSE 0 END) AS dep_ru
              FROM conversions cv
              JOIN clicks cl ON cl.clickid = cv.clickid
              WHERE cv.ts >= ? AND cl.country='RU'";
    $argsRu = [$from];
    if ($to !== null) { $sqlRu .= ' AND cv.ts < ?'; $argsRu[] = $to; }
    $sqlRu .= ' GROUP BY cl.slug';
    $st = db()->prepare($sqlRu);
    $st->execute($argsRu);
    foreach ($st->fetchAll(PDO::FETCH_ASSOC) as $r) {
        if (isset($out[$r['slug']])) {
            $out[$r['slug']]['reg_ru'] = (int)$r['reg_ru'];
            $out[$r['slug']]['dep_ru'] = (int)$r['dep_ru'];
        }
    }
    return $out;
}
