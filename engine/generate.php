<?php
declare(strict_types=1);

/**
 * CLI-генератор сборочных спек и промптов для реверс-генератора казино-контента.
 *
 * Использование:
 *   php generate.php --type=main --brand-ru=Казиновия --brand-en=Casinovia \
 *       --domain=casinovia.win --date="21 июля 2026" --seed=demo1 [--json|--prompt|--both]
 *
 *   php generate.php --all --brand-ru=... --brand-en=... --domain=... --seed=...
 *       → спеки+промпты по всем 7 типам (в --out-dir, по умолчанию текущая папка)
 *
 * Флаги вывода: --prompt (по умолчанию), --json (сборочная спека), --both.
 */

require_once __DIR__ . '/src/Generator/Planner.php';
require_once __DIR__ . '/src/Generator/PromptBuilder.php';
require_once __DIR__ . '/src/Generator/StyleProfile.php';
require_once __DIR__ . '/src/Generator/Rng.php';

$opts = [
    'type' => '', 'brand-ru' => 'Бренд', 'brand-en' => 'Brand',
    'domain' => 'example.win', 'date' => '21 июля 2026', 'seed' => '',
    'out-dir' => '', 'all' => false, 'json' => false, 'prompt' => false, 'both' => false,
    'donor' => '', 'list-donors' => false, 'register' => '', 'brand-var' => false,
];
foreach (array_slice($argv, 1) as $a) {
    if (!str_starts_with($a, '--')) { continue; }
    [$k, $v] = array_pad(explode('=', substr($a, 2), 2), 2, '');
    if (!array_key_exists($k, $opts)) { continue; }
    $opts[$k] = ($v === '') ? true : $v;
}

$mode = $opts['both'] ? 'both' : ($opts['json'] ? 'json' : 'prompt');

// Бренд-переменная: подставляем шаблон-плейсхолдеры корпуса вместо реального имени
if ($opts['brand-var'] === true) {
    $opts['brand-ru'] = '%brand_name_ru%';
    $opts['brand-en'] = '%brand_name_en%';
    $opts['domain']   = '%domain_name%';
    $opts['date']     = '%date%';
}

$planner = new Planner();
$builder = new PromptBuilder();

// Донор-режим: загрузка пер-сайтовых профилей корпуса
$donors = [];
$donorsPath = __DIR__ . '/data/donors.json';
if (is_file($donorsPath)) {
    $donors = json_decode((string) file_get_contents($donorsPath), true)['sites'] ?? [];
}
if ($opts['list-donors'] === true) {
    fwrite(STDERR, "Доноров: " . count($donors) . "\n");
    foreach ($donors as $n => $d) {
        $mn = $d['pages']['main'] ?? [];
        printf("%-16s main: %d слов, emoji %d, faq %d, fp=%s vy=%s\n",
            $n, $mn['words'] ?? 0, $mn['emoji'] ?? 0, $mn['faq'] ?? 0,
            !empty($d['style']['first_person']) ? '1' : '0', !empty($d['style']['vy']) ? '1' : '0');
    }
    exit(0);
}

// выбор донора: точное имя или 'random' (детерминированно по seed)
$donor = null;
$donorName = is_string($opts['donor']) ? $opts['donor'] : '';
if ($donorName !== '' && $donors !== []) {
    if ($donorName === 'random') {
        $keys = array_keys($donors);
        $r = new Rng('pick-donor:' . ($opts['seed'] ?: $opts['domain']));
        $donorName = $keys[$r->int(0, count($keys) - 1)];
    }
    if (!isset($donors[$donorName])) {
        fwrite(STDERR, "Донор '$donorName' не найден. Список: php generate.php --list-donors\n");
        exit(1);
    }
    $donor = $donors[$donorName];
    $donor['name'] = $donorName;
    fwrite(STDERR, "Донор: $donorName (клонируем его профиль)\n");
}

$brand = static fn(string $type, string $seed) => [
    'ru' => $opts['brand-ru'], 'en' => $opts['brand-en'],
    'domain' => $opts['domain'], 'date' => $opts['date'],
    'seed' => ($seed !== '' ? $seed : ($opts['domain'] . ':' . $type)),
];

$types = $opts['all'] ? $planner->types() : [$opts['type'] ?: 'main'];

$outDir = is_string($opts['out-dir']) && $opts['out-dir'] !== '' ? rtrim($opts['out-dir'], '/') : '';

// Стиль-профиль ГЕНЕРАЦИИ — один на всю связку (тон/манера едины на 7 страницах).
// Seed от бренда/домена (+ --seed, если задан), НЕ от типа страницы.
// В донор-режиме стиль берётся из выбранного сайта-донора.
$genSeed = (is_string($opts['seed']) && $opts['seed'] !== '' ? $opts['seed'] . ':' : '')
    . $opts['brand-ru'] . ':' . $opts['brand-en'] . ':' . $opts['domain'];
$style = $donor !== null
    ? StyleProfile::fromDonor($donor['style'] ?? [], new Rng('donor-style:' . $genSeed))
    : StyleProfile::sample(new Rng('style:' . $genSeed));
// явный override регистра (--register=derzkiy|delovoy|expert|razgovorny|neutral|reklamny)
if (is_string($opts['register']) && $opts['register'] !== '') {
    $style->register = $opts['register'];
    if ($opts['register'] === 'expert') { $style->firstPerson = true; }
    elseif (in_array($opts['register'], ['derzkiy', 'razgovorny'], true)) { $style->firstPerson = false; }
}

foreach ($types as $type) {
    $seed = is_string($opts['seed']) ? $opts['seed'] : '';
    $seedForType = $seed !== '' ? ($seed . ':' . $type) : '';
    $spec = $planner->plan($type, $brand($type, $seedForType), $style, $donor);
    if ($opts['brand-var'] === true) { $spec['brand_var'] = true; }

    $jsonStr = json_encode($spec, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    $promptStr = $builder->build($spec);

    if ($outDir !== '') {
        if (!is_dir($outDir)) { mkdir($outDir, 0777, true); }
        if ($mode !== 'prompt') { file_put_contents("$outDir/spec-$type.json", $jsonStr . "\n"); }
        if ($mode !== 'json')   { file_put_contents("$outDir/prompt-$type.md", $promptStr); }
        fwrite(STDERR, "→ $type: сохранено в $outDir/\n");
        continue;
    }

    if ($mode === 'json') { echo $jsonStr . "\n"; }
    elseif ($mode === 'both') { echo $jsonStr . "\n\n" . $promptStr . "\n"; }
    else { echo $promptStr . "\n"; }
    if (count($types) > 1) { echo str_repeat('─', 60) . "\n"; }
}
