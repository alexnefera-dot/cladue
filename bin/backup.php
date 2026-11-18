<?php

declare(strict_types=1);

/**
 * БЕКАП РАБОЧИХ ДАННЫХ — перенести работу на другой ПК и положить копию в облако.
 *
 * Код в бекап не идёт: он лежит в git и ставится заново (git clone или php bin/setup.php). В архив
 * попадает то, чего в git НЕТ и что есть только на этой машине: config.php, .env, proxies.txt,
 * queries.txt, brands.txt, brand-pairs.txt и вся папка runs/ — база пересечений доменов, история
 * сборов, снимки выдачи, список наших баз из системы запусков, настройки панели и таблица сайтов.
 *
 * Запуск:
 *   php bin/backup.php                      — состояние без скачанных страниц (обычно единицы МБ)
 *   php bin/backup.php --all                — плюс страницы, контент и превью (гигабайты)
 *   php bin/backup.php --no-secrets         — без .env/config.php/proxies.txt и без списка прокси
 *                                             в настройках панели (копия, которую можно передать)
 *   php bin/backup.php --out=/путь/my.zip   — куда положить архив
 *   php bin/backup.php --list               — что попадёт и сколько весит, ничего не создавая
 *   php bin/backup.php --restore=файл.zip   — развернуть бекап в этой папке проекта
 *   php bin/backup.php --restore=… --force  — и перезаписать файлы, которые уже на месте
 *
 * В архиве есть ключи и пароли, поэтому про них говорится вслух при каждом создании.
 */

use YandexSites\Cli\Application;
use YandexSites\Support\Backup;

@ini_set('memory_limit', '1024M');

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

$args = [];
foreach (array_slice($argv, 1) as $arg) {
    if (preg_match('~^--([a-z\-]+)(?:=(.*))?$~', $arg, $m) === 1) {
        $args[$m[1]] = $m[2] ?? '1';
    }
}

if (isset($args['help'])) {
    fwrite(STDOUT, <<<TXT
    Бекап рабочих данных (настройки, ключи, база доменов, история сборов, таблица сайтов).

      php bin/backup.php                      архив состояния (без скачанных страниц)
      php bin/backup.php --all                плюс страницы, контент и превью
      php bin/backup.php --no-secrets         без .env, config.php и proxies.txt
      php bin/backup.php --out=/путь/my.zip   куда положить архив
      php bin/backup.php --list               что попадёт в архив, без создания
      php bin/backup.php --restore=файл.zip   развернуть бекап (--force — перезаписать)
      php bin/backup.php --dir=/путь          другая папка проекта

    TXT);
    exit(0);
}

$projectDir = isset($args['dir']) ? rtrim($args['dir'], '/\\') : $root;
if (!is_dir($projectDir)) {
    fwrite(STDERR, 'Папки проекта нет: ' . $projectDir . "\n");
    exit(2);
}
$withPages = isset($args['all']) || isset($args['pages']);
$withSecrets = !isset($args['no-secrets']);

/** Короткий список корневых файлов архива — чтобы было видно, что настройки и ключи внутри. */
$rootNames = static function (array $files): array {
    return array_values(array_filter(array_keys($files), static fn (string $e): bool => !str_starts_with($e, 'runs/')));
};

/** Подпись к этому списку: про ключи говорим только тогда, когда они действительно внутри. */
$rootLabel = static function (array $names): string {
    return array_intersect($names, Backup::SECRET_FILES) !== [] ? 'настройки и ключи' : 'настройки';
};

/** Строки «не включено»: что осталось за бортом и почему. */
$skippedLines = static function (array $plan): array {
    $why = [
        'pages' => ['страницы и контент', 'восстанавливаются выгрузкой — нужны в архиве, повторите с --all'],
        'cache' => ['кэш выдачи', 'перекачивается сам и живёт 7 дней'],
        'out' => ['вывод CLI (папка out)', 'рабочие файлы запусков из терминала'],
        'logs' => ['логи', 'это не данные'],
        'secrets' => ['ключи и прокси', 'убраны флагом --no-secrets: на новом ПК их придётся вписать заново'],
    ];
    $lines = [];
    foreach ($plan['skipped'] as $bucket => $info) {
        [$label, $note] = $why[$bucket] ?? [$bucket, ''];
        $lines[] = sprintf('  %s — %s, %s (%s)', $label, Backup::files($info['files']), Backup::size($info['bytes']), $note);
    }

    return $lines;
};

if (isset($args['restore'])) {
    $zipFile = trim($args['restore']);
    try {
        $result = Backup::restore($zipFile, $projectDir, isset($args['force']));
    } catch (RuntimeException $e) {
        fwrite(STDERR, $e->getMessage() . "\n");
        exit(2);
    }
    if ($result['written'] === [] && $result['kept'] !== []) {
        fwrite(STDERR, sprintf(
            "Ничего не распаковано: %d файлов уже на месте, в том числе %s.\n"
            . "Повторите с --force, если их нужно перезаписать (данные этой машины будут потеряны).\n",
            count($result['kept']),
            implode(', ', array_slice($result['kept'], 0, 5)) . (count($result['kept']) > 5 ? ' …' : ''),
        ));
        exit(1);
    }
    if ($result['written'] === []) {
        fwrite(STDERR, "В архиве нет ни настроек, ни папки runs — это не бекап этого проекта\n");
        exit(2);
    }
    $bytes = array_sum($result['written']);
    $runs = count(array_filter(array_keys($result['written']), static fn (string $e): bool => str_starts_with($e, 'runs/')));
    fwrite(STDOUT, sprintf(
        "Развёрнуто в %s: %s, %s%s\n",
        $projectDir,
        Backup::files(count($result['written'])),
        Backup::size((int) $bytes),
        $result['overwritten'] > 0 ? sprintf(' (перезаписано %d)', $result['overwritten']) : '',
    ));
    $names = $rootNames($result['written']);
    if ($names !== []) {
        fwrite(STDOUT, '  ' . $rootLabel($names) . ': ' . implode(', ', $names) . "\n");
    }
    if ($runs > 0) {
        fwrite(STDOUT, '  runs/: ' . Backup::files($runs) . " — база доменов, история сборов, снимки выдачи, таблица сайтов\n");
    }
    if ($result['rejected'] !== []) {
        fwrite(STDOUT, sprintf(
            "  пропущено лишнего в архиве: %d (разворачиваем только настройки и runs/, код проекта не трогаем)\n",
            count($result['rejected']),
        ));
    }
    fwrite(STDOUT, "Дальше: php bin/panel.php — панель откроется с прежней базой и таблицей\n");
    exit(0);
}

$plan = Backup::plan($projectDir, $withPages, $withSecrets);
if ($plan['files'] === []) {
    fwrite(STDERR, "Бекапить нечего: в папке проекта нет ни настроек, ни папки runs\n");
    exit(2);
}

if (isset($args['list'])) {
    fwrite(STDOUT, sprintf("Папка проекта: %s\nПопадёт в архив: %s, %s\n", $projectDir, Backup::files($plan['count']), Backup::size($plan['bytes'])));
    $names = $rootNames($plan['files']);
    if ($names !== []) {
        fwrite(STDOUT, '  ' . $rootLabel($names) . ': ' . implode(', ', $names) . "\n");
    }
    $runs = $plan['count'] - count($names);
    if ($runs > 0) {
        fwrite(STDOUT, '  runs/: ' . Backup::files($runs) . " — база доменов, история сборов, снимки выдачи, таблица сайтов\n");
    }
    $lines = $skippedLines($plan);
    if ($lines !== []) {
        fwrite(STDOUT, "Не включено:\n" . implode("\n", $lines) . "\n");
    }
    exit(0);
}

$out = isset($args['out']) ? trim($args['out']) : $projectDir . '/runs/' . Backup::fileName($withPages, $withSecrets);
try {
    $result = Backup::create($projectDir, $out, $withPages, $withSecrets, Application::VERSION);
} catch (RuntimeException $e) {
    fwrite(STDERR, $e->getMessage() . "\n");
    exit(2);
}

fwrite(STDOUT, sprintf(
    "Бекап готов: %s\nВнутри: %s, %s (архив %s)\n",
    $result['zip'],
    Backup::files($result['count']),
    Backup::size($result['bytes']),
    Backup::size($result['zip_bytes']),
));
$names = $rootNames($result['files']);
if ($names !== []) {
    fwrite(STDOUT, '  ' . $rootLabel($names) . ': ' . implode(', ', $names) . "\n");
}
$runs = $result['count'] - count($names);
if ($runs > 0) {
    fwrite(STDOUT, '  runs/: ' . Backup::files($runs) . " — база доменов, история сборов, снимки выдачи, таблица сайтов\n");
}
$lines = $skippedLines($result);
if ($lines !== []) {
    fwrite(STDOUT, "Не включено:\n" . implode("\n", $lines) . "\n");
}
if ($result['secrets'] !== []) {
    fwrite(STDOUT, sprintf(
        "\nВНИМАНИЕ: в архиве есть ключи и пароли — %s. Это нормально для переноса на свой ПК,\n"
        . "но в облаке и общих папках архив доступен всем, у кого есть ссылка. Копия без них:\n"
        . "  php bin/backup.php --no-secrets\n",
        implode(', ', array_keys($result['secrets'])),
    ));
}
if (!$withSecrets) {
    fwrite(STDOUT, sprintf(
        "Ключей в архиве нет: убраны %s, а из настроек панели вырезан список прокси.\n"
        . "Адреса прокси (host:port) в отчётах сбора остаются, пароли — нет.\n",
        implode(', ', Backup::SECRET_FILES),
    ));
}
fwrite(STDOUT, sprintf(
    "\nКак развернуть на другом ПК:\n"
    . "  1) положить код: git clone … или скачать проект и запустить php bin/setup.php\n"
    . "  2) php bin/backup.php --restore=%s\n"
    . "  3) php bin/panel.php\n",
    basename($result['zip']),
));
exit(0);
