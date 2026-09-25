<?php

declare(strict_types=1);

/**
 * Выгрузка НАШИХ запущенных поддоменов из системы запусков dorgen в локальный кэш баз.
 *
 * По кэшу страница «Разбор выдачи» помечает сайты из выдачи как наши: сверяется БАЗА — последние две
 * метки хоста (leebet.4916.team → 4916.team). Каждая база несёт все бренды, поэтому хранить сами
 * поддомены незачем (их ~15 тыс. в сутки), в кэше только базы.
 *
 * Запуск:
 *   php bin/dorgen-sync.php                       — догрузить новые дни (с нахлёстом в сутки)
 *   php bin/dorgen-sync.php --from=2026-01-01     — с указанной даты по сегодня
 *   php bin/dorgen-sync.php --from=… --to=…       — произвольный период (режется по 31 дню сам)
 *   php bin/dorgen-sync.php --days=7              — за последние 7 дней
 *   php bin/dorgen-sync.php --list                — показать, что уже в кэше, без запросов к API
 *
 * Ключ читается из .env (DORGEN_TOKEN) и нигде не печатается.
 */

use YandexSites\Config;
use YandexSites\Dorgen\DorgenClient;
use YandexSites\Dorgen\OwnBases;

$root = dirname(__DIR__);
if (is_file($root . '/vendor/autoload.php')) {
    require $root . '/vendor/autoload.php';
} else {
    spl_autoload_register(static function (string $class) use ($root): void {
        if (str_starts_with($class, 'YandexSites\\')) {
            $path = $root . '/src/' . str_replace('\\', '/', substr($class, strlen('YandexSites\\'))) . '.php';
            if (is_file($path)) {
                require $path;
            }
        }
    });
}

Config::loadDotEnv(getcwd() . '/.env');
Config::loadDotEnv($root . '/.env');

$args = [];
foreach (array_slice($argv, 1) as $arg) {
    if (preg_match('~^--([a-z\-]+)(?:=(.*))?$~', $arg, $m) === 1) {
        $args[$m[1]] = $m[2] ?? '1';
    }
}

$runsDir = (is_dir(getcwd() . '/runs') ? getcwd() : $root) . '/runs';
$cache = OwnBases::inRuns($runsDir);

if (isset($args['help'])) {
    fwrite(STDOUT, "php bin/dorgen-sync.php [--from=ГГГГ-ММ-ДД] [--to=ГГГГ-ММ-ДД] [--days=N] [--list]\n");
    exit(0);
}

if (isset($args['list'])) {
    $state = $cache->load();
    fwrite(STDOUT, sprintf(
        "Кэш баз: %s\nБаз: %d, период %s — %s, обновлён %s\n",
        $runsDir . '/' . OwnBases::FILE,
        count($state['bases']),
        $state['date_from'] !== '' ? $state['date_from'] : '—',
        $state['date_to'] !== '' ? $state['date_to'] : '—',
        $state['updated_at'] !== '' ? $state['updated_at'] : '—',
    ));
    foreach (array_slice(array_keys($state['bases']), 0, 20) as $base) {
        fwrite(STDOUT, '  ' . $base . ' — поддоменов ' . $state['bases'][$base]['subdomains'] . "\n");
    }
    exit(0);
}

$client = DorgenClient::fromEnv();
if ($client === null) {
    fwrite(STDERR, "Не задан " . DorgenClient::TOKEN_ENV . " — впишите ключ в .env рядом с проектом (образец: .env.example)\n");
    exit(2);
}

$today = date('Y-m-d');
$to = isset($args['to']) ? trim($args['to']) : $today;
if (isset($args['days'])) {
    $from = date('Y-m-d', strtotime('-' . max(1, (int) $args['days'] - 1) . ' days', strtotime($to)));
} elseif (isset($args['from'])) {
    $from = trim($args['from']);
} else {
    // Без дат — догружаем только новые дни: кэш помнит, по какой день уже выгружено.
    $from = $cache->nextFrom(date('Y-m-d', strtotime('-7 days')));
}

fwrite(STDOUT, sprintf("Выгружаю наши поддомены за %s — %s…\n", $from, $to));
try {
    $r = $cache->refresh($client, $from, $to);
} catch (Throwable $e) {
    fwrite(STDERR, 'Ошибка выгрузки: ' . $e->getMessage() . "\n");
    exit(1);
}
fwrite(STDOUT, sprintf(
    "Готово: строк %d, баз всего %d (новых %d)%s\n",
    $r['rows'],
    $r['bases'],
    $r['new_bases'],
    $r['new_base_list'] !== [] ? ' — ' . implode(', ', array_slice($r['new_base_list'], 0, 10)) : '',
));
