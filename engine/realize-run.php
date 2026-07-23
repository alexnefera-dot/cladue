<?php
declare(strict_types=1);

/**
 * Боевой прогон ОДНОЙ связки без агентов: генерит планы+промпты (Planner),
 * реалайзит 7 страниц одним API-вызовом на страницу (realize.php),
 * затем прогоняет ДЕТЕРМИНИРОВАННЫЕ механические правки (перелинковка-инжектор,
 * бренд→переменные) — то, что не требует модели. Печатает стоимость по токенам.
 *
 *   php realize-run.php --donor=monro --out=/path/run [--seed=prod1] [--effort=medium] \
 *       [--brand-ru=Монрополь --brand-en=Monropol --domain=monropol.com --date="июль 2026"]
 *
 * По умолчанию бренд — переменные %brand_%; realize.php их сохраняет как есть.
 */

$opts = [];
foreach (array_slice($argv, 1) as $a) {
    if (preg_match('/^--([^=]+)=(.*)$/s', $a, $m)) { $opts[$m[1]] = $m[2]; }
}
$donor = $opts['donor'] ?? '';
$out   = rtrim($opts['out'] ?? '', '/');
$seed  = $opts['seed'] ?? 'prod';
$effort= $opts['effort'] ?? 'medium';
if ($donor === '' || $out === '') { fwrite(STDERR, "usage: realize-run.php --donor=<name> --out=<dir> [--seed=..] [--effort=..]\n"); exit(1); }

$ENGINE = __DIR__;
$TYPES = ['main','zerkalo','vhod','registracia','bonus','slots','app'];

// регистр донора (для подсказки реалайзеру и safety-инжектора)
$DONORS = json_decode((string)file_get_contents("$ENGINE/data/donors.json"), true)['sites'];
$reg = $DONORS[$donor]['style']['register'] ?? 'neutral';
$linkTargets = [];
foreach ($TYPES as $t) { $linkTargets[$t] = (int)($DONORS[$donor]['pages'][$t]['intlinks'] ?? 0); }

@mkdir($out, 0777, true);

// 1) планы+промпты (бренд-переменные)
$genFlags = "--all --donor=" . escapeshellarg($donor) . " --brand-var --seed=" . escapeshellarg($seed)
          . " --out-dir=" . escapeshellarg($out) . " --prompt";
exec("php " . escapeshellarg("$ENGINE/generate.php") . " $genFlags 2>/dev/null", $o, $rc);
$nP = count(glob("$out/prompt-*.md"));
fwrite(STDERR, "планы+промпты: $nP  (донор $donor, регистр $reg)\n");
if ($nP < 7) { fwrite(STDERR, "промпты не сгенерились\n"); exit(2); }

// 2) реалайз: 1 API-вызов на страницу
$tin = 0; $tout = 0; $ok = 0;
foreach ($TYPES as $t) {
    $pf = "$out/prompt-$t.md"; $hf = "$out/$t.html";
    if (!is_file($pf)) continue;
    $cmd = "php " . escapeshellarg("$ENGINE/realize.php")
         . " --prompt=" . escapeshellarg($pf) . " --out=" . escapeshellarg($hf)
         . " --effort=" . escapeshellarg($effort) . " --register=" . escapeshellarg($reg);
    exec($cmd . " 2>&1", $line, $rc);
    $last = end($line) ?: '';
    if (preg_match('~in (\d+) / out (\d+)~', $last, $m)) { $tin += (int)$m[1]; $tout += (int)$m[2]; }
    if ($rc === 0 && is_file($hf)) { $ok++; }
    fwrite(STDERR, "  $t: " . ($rc === 0 ? 'ok' : "ошибка($rc)") . "\n");
    $line = [];
}

// 3) детерминированный механический шаг: страховочная перелинковка там,
//    где модель недоставила ссылок (донор-осознанно, без self-ссылок).
if ($ok > 0) {
    $brRu = $opts['brand-ru'] ?? '%brand_name_ru%';
    $brEn = $opts['brand-en'] ?? '%brand_name_en%';
    foreach ($TYPES as $t) {
        $hf = "$out/$t.html"; if (!is_file($hf)) continue;
        $have = preg_match_all('~<a\s+href="/~i', (string)file_get_contents($hf));
        $need = $linkTargets[$t];
        if ($need > 0 && $have < max(1, (int)floor($need * 0.75))) {
            // добить до цели детерминированным инжектором (правит только <p>/<li>)
            exec("php " . escapeshellarg("$ENGINE/inject-links.php") . " "
                . escapeshellarg($hf) . " " . escapeshellarg($hf) . " "
                . escapeshellarg($brRu) . " " . escapeshellarg($brEn) . " '' " . (int)$need . " 2>/dev/null");
            fwrite(STDERR, "  fix $t: перелинковка $have→~$need (механически)\n");
        }
    }
}

$price = $tin/1e6*5 + $tout/1e6*25; // Opus 4.8: $5/$25 за 1M
fwrite(STDERR, sprintf("=== готово: %d/7 страниц | токены in %d / out %d | ~\$%.3f (Opus 4.8) ===\n",
    $ok, $tin, $tout, $price));
