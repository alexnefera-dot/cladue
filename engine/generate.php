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

$opts = [
    'type' => '', 'brand-ru' => 'Бренд', 'brand-en' => 'Brand',
    'domain' => 'example.win', 'date' => '21 июля 2026', 'seed' => '',
    'out-dir' => '', 'all' => false, 'json' => false, 'prompt' => false, 'both' => false,
];
foreach (array_slice($argv, 1) as $a) {
    if (!str_starts_with($a, '--')) { continue; }
    [$k, $v] = array_pad(explode('=', substr($a, 2), 2), 2, '');
    if (!array_key_exists($k, $opts)) { continue; }
    $opts[$k] = ($v === '') ? true : $v;
}

$mode = $opts['both'] ? 'both' : ($opts['json'] ? 'json' : 'prompt');

$planner = new Planner();
$builder = new PromptBuilder();

$brand = static fn(string $type, string $seed) => [
    'ru' => $opts['brand-ru'], 'en' => $opts['brand-en'],
    'domain' => $opts['domain'], 'date' => $opts['date'],
    'seed' => ($seed !== '' ? $seed : ($opts['domain'] . ':' . $type)),
];

$types = $opts['all'] ? $planner->types() : [$opts['type'] ?: 'main'];

$outDir = is_string($opts['out-dir']) && $opts['out-dir'] !== '' ? rtrim($opts['out-dir'], '/') : '';

foreach ($types as $type) {
    $seed = is_string($opts['seed']) ? $opts['seed'] : '';
    $seedForType = $seed !== '' ? ($seed . ':' . $type) : '';
    $spec = $planner->plan($type, $brand($type, $seedForType));

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
