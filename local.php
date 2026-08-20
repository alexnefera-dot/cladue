<?php
/**
 * local.php — подготовка локальной версии для тестирования.
 *
 * Создаёт config.php под SQLite (никакой MySQL не нужен), заводит демо-кампании
 * и наполняет базу правдоподобной статистикой за 30 дней: клики, боты
 * (Яндекс и прочие), источники, гео, регистрации и депозиты.
 *
 * Запуск:
 *   php local.php          — подготовить (существующий config.php не трогает)
 *   php local.php --reset  — пересоздать всё с нуля (config, база, лог, кэш)
 *
 * Дальше:
 *   php -S localhost:8000 router.php
 *
 * На боевой сервер этот файл заливать не нужно.
 */

if (php_sapi_name() !== 'cli') { http_response_code(403); exit("только из командной строки\n"); }

$reset = in_array('--reset', $argv, true);
$dir   = __DIR__;

function say($s) { echo $s . "\n"; }

// ---------- 1. config.php ----------
$cfgFile = $dir . '/config.php';
if ($reset || !is_file($cfgFile)) {
    if (is_file($cfgFile)) {
        @copy($cfgFile, $cfgFile . '.bak');
        say("старый config.php сохранён как config.php.bak");
    }
    $cfg = <<<'PHP'
<?php
/**
 * config.php — ЛОКАЛЬНАЯ конфигурация для тестирования.
 * База — SQLite в файле, MySQL не нужен.
 */
return [
    'password'         => 'test',                 // пароль входа в панель
    'db_file'          => 'local.sqlite',
    'db_driver'        => 'sqlite',
    'log_bots'         => false,
    'bot_redirect'     => '',
    'retention_days'   => 0,                      // локально ничего не чистим
    'flood_limit'      => 0,
    'flood_window'     => 60,
    'downtime_gap'     => 300,
    'postback_secret'  => 'testsecret',
    'clickid_param'    => 'clickid',
    'postback_domains' => [],                     // пусто = clickid дописывается ко всем
    'db_write'         => true,
    'fallback_offer'   => '',
    'click_log'        => __DIR__ . '/clicks.log',
    'mysql_host' => 'localhost', 'mysql_port' => 3306,
    'mysql_db'   => '', 'mysql_user' => '', 'mysql_pass' => '',
];
PHP;
    file_put_contents($cfgFile, $cfg);
    say("создан config.php (SQLite, пароль панели: test)");
} else {
    say("config.php уже есть — не трогаю (для пересоздания: php local.php --reset)");
}

require_once $dir . '/db.php';

// ---------- 2. чистка при --reset ----------
if ($reset) {
    foreach ([$dir . '/local.sqlite', $dir . '/clicks.log', $dir . '/clicks.log.processing', $dir . '/offers.php'] as $f) @unlink($f);
    foreach (glob($dir . '/cache/*') ?: [] as $f) @unlink($f);
    say("старые данные удалены");
}

$pdo = db();   // создаст таблицы

// ---------- 3. кампании ----------
$campaigns = [
    ['dorgen_engine',     'Fenix RU',    "https://fnx-abs.net/di6viifma"],
    ['cryptoboss_engine', 'CryptoBoss',  "https://cbc-abs.net/aa11bb"],
    ['vodka_engine',      'Vodka Bet',   "https://unlimbot-c.com/vk55"],
    ['zooma_engine',      'Zooma',       "https://hype-combo.com/zm77"],
    // ротация: два оффера, второй с весом 3 (25% / 75%)
    ['split_demo',        'Сплит-тест',  "https://offer-a.example/aaa\nhttps://offer-b.example/bbb|3"],
];
// db.php при создании базы сам заводит кампанию dorgne_fenix, поэтому смотрим
// не на общий счётчик, а на наличие именно демо-кампаний.
$st = $pdo->prepare('SELECT COUNT(*) FROM campaigns WHERE slug = ?');
$st->execute(['split_demo']);
if ((int)$st->fetchColumn() === 0) {
    $added = 0;
    foreach ($campaigns as [$slug, $name, $url]) {
        $err = add_campaign($slug, $name, $url);
        if ($err === null) $added++;
        elseif (strpos($err, 'уже существует') === false) say("! $slug: $err");
    }
    say("заведено демо-кампаний: $added (одна из них — с ротацией офферов)");
} else {
    say("демо-кампании уже есть — пропускаю");
}

// ---------- 4. демо-статистика ----------
$clicksHave = (int)$pdo->query('SELECT COUNT(*) FROM clicks')->fetchColumn();
if ($clicksHave > 0) {
    say("клики уже есть ($clicksHave) — генерацию пропускаю");
} else {
    say("генерирую статистику за 30 дней...");

    $slugs   = array_column($campaigns, 0);
    $sources = ['vodka.c3xw.team', 'dbbet.5623-1.casino', 'kraken.dt63k.team', 'luckybird.731.team',
                'cryptoboss-rcn.top', 'newretro.casino49y.team', 'spincity.216.team', ''];
    $refs    = ['https://yandex.ru/', 'https://ya.ru/', 'https://google.com/', ''];
    $countries = ['RU','RU','RU','RU','RU','RU','DE','FR','NL','LT','KZ','BY'];   // RU преобладает
    $humanUA = [
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
        'Mozilla/5.0 (Linux; Android 13; SM-A536B) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15',
    ];
    $yandexUA = [
        'Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)',
        'Mozilla/5.0 (compatible; YandexImages/3.0; +http://yandex.com/bots)',
        'Mozilla/5.0 (compatible; YandexMetrika/2.0)',
    ];
    $otherBotUA = [
        'Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)',
        'Mozilla/5.0 (compatible; AhrefsBot/7.0; +http://ahrefs.com/robot/)',
        'Mozilla/5.0 (compatible; SemrushBot/7~bl)',
        'Go-http-client/1.1',
        'python-requests/2.31.0',
    ];

    $insClick = $pdo->prepare('INSERT INTO clicks (ts,slug,ip,ua,referer,source,is_bot,clickid,country)
                               VALUES (?,?,?,?,?,?,?,?,?)');
    $insConv  = $pdo->prepare('INSERT INTO conversions (clickid,slug,status,payout,ts,ip)
                               VALUES (?,?,?,?,?,?)');

    $now = time();
    $totalClicks = $totalRegs = $totalDeps = $totalBots = 0;

    $pdo->beginTransaction();
    for ($d = 29; $d >= 0; $d--) {
        $dayStart = strtotime('today') - $d * 86400;
        // к сегодняшнему дню трафика больше — график будет с ростом
        $base   = 60 + (int)((29 - $d) * 3);
        $humans = $base + random_int(-15, 25);
        $bots   = (int)($humans * 0.35) + random_int(0, 10);

        for ($i = 0; $i < $humans; $i++) {
            $slug    = $slugs[array_rand($slugs)];
            $ts      = $dayStart + random_int(0, 86399);
            $ip      = '10.' . random_int(0,255) . '.' . random_int(0,255) . '.' . random_int(1,254);
            $clickid = bin2hex(random_bytes(8));
            $country = $countries[array_rand($countries)];
            $src     = $sources[array_rand($sources)];
            $insClick->execute([$ts, $slug, $ip, $humanUA[array_rand($humanUA)],
                                $refs[array_rand($refs)], $src, 0, $clickid, $country]);
            $totalClicks++;

            // ~4% кликов дают регу, из них ~30% — деп (отдельным событием)
            if (random_int(1, 100) <= 4) {
                $insConv->execute([$clickid, $slug, 'reg', 0, $ts + random_int(60, 3600), $ip]);
                $totalRegs++;
                if (random_int(1, 100) <= 30) {
                    $insConv->execute([$clickid, $slug, 'dep', 0, $ts + random_int(3600, 86400), $ip]);
                    $totalDeps++;
                }
            }
        }

        for ($i = 0; $i < $bots; $i++) {
            $isYandex = random_int(1, 100) <= 55;    // яндекс ходит чаще прочих
            $ua = $isYandex ? $yandexUA[array_rand($yandexUA)] : $otherBotUA[array_rand($otherBotUA)];
            $insClick->execute([$dayStart + random_int(0, 86399), $slugs[array_rand($slugs)],
                                '5.' . random_int(0,255) . '.' . random_int(0,255) . '.' . random_int(1,254),
                                $ua, '', '', 1, bin2hex(random_bytes(8)), 'RU']);
            $totalBots++;
        }
    }

    // несколько «непривязанных» постбеков — клика с таким clickid нет
    for ($i = 0; $i < 7; $i++) {
        $insConv->execute([bin2hex(random_bytes(8)), null, 'reg', 0, $now - random_int(0, 5*86400), '9.9.9.9']);
    }
    $pdo->commit();

    say("  клики людей: $totalClicks");
    say("  боты: $totalBots (Яндекс ~55%)");
    say("  реги: $totalRegs, депы: $totalDeps, непривязанных постбеков: 7");
}

// ---------- 5. кэш офферов и метка импорта ----------
offers_cache_rebuild();
meta_upsert('last_import', time());
if (function_exists('panel_cache_flush')) panel_cache_flush();

// ---------- 6. итог ----------
$cfg = require $cfgFile;
say("");
say("============================================================");
say("  ГОТОВО. Запускай сервер:");
say("");
say("     php -S localhost:8000 router.php");
say("");
say("  Панель:    http://localhost:8000/stats.php");
say("  Пароль:    " . $cfg['password']);
say("");
say("  Редирект:  http://localhost:8000/go/dorgen_engine");
say("  Ротация:   http://localhost:8000/go/split_demo   (обнови несколько раз —");
say("             будет попадать то на offer-a, то на offer-b, примерно 25/75)");
say("");
say("  Постбек (подставь clickid из панели):");
say("     http://localhost:8000/postback.php?key=" . $cfg['postback_secret'] . "&cnv_id=CLICKID&cnv_status=reg");
say("     http://localhost:8000/postback.php?key=" . $cfg['postback_secret'] . "&cnv_id=CLICKID&cnv_status=dep");
say("");
say("  Импорт кликов из лога в базу (то, что на бою делает крон):");
say("     php import.php");
say("============================================================");
