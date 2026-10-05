<?php
// Состав имён героев в наборе: мужские и женские порознь, и медиана на страницу.
//
// Мерить имена списком, набранным руками, нельзя: банк движка пополняется, а
// список отстаёт, и наборы теряют на этом тем больше, чем свежее имена в них
// выпадают. Отставший на 26 имён список дал нам 26 различных имён на набор
// против корпусных 35 — отставание, которого нет: полным банком выходит 40
// против 40. Поэтому список читается из самого банка.
//
// Папки передаются аргументами; без аргументов берутся наши последние двадцать
// наборов и оба подкорпуса NEW100 из песочницы замеров.
require_once '/home/user/cladue/engine/src/V5Blocks.php';
$пулы = json_decode((string) file_get_contents('/home/user/cladue/engine/data-v5/pools.json'), true);
$М = array_keys($пулы['общие']['банки']['ИМЯ']);
$Ж = array_keys($пулы['общие']['банки']['ИМЯЖ']);
$ре = function (array $сп) { usort($сп, fn($a, $b) => mb_strlen($b) - mb_strlen($a));
    return '~(?<![А-Яа-яЁё])(' . implode('|', array_map(fn($n) => preg_quote($n, '~'), $сп)) . ')(?![а-яё])~u'; };
$реМ = $ре($М); $реЖ = $ре($Ж);
$набор = function (string $п) use ($реМ, $реЖ): ?array {
    $м = []; $ж = []; $постр = []; $страниц = 0;
    foreach (glob("$п/*.html") as $f) {
        $страниц++;
        $t = strip_tags(preg_replace('~<(script|style)\b.*?</\1>~is', ' ', (string) file_get_contents($f)));
        $см = []; $сж = [];
        if (preg_match_all($реМ, $t, $x)) { foreach ($x[1] as $n) { $м[$n] = true; $см[$n] = true; } }
        if (preg_match_all($реЖ, $t, $x)) { foreach ($x[1] as $n) { $ж[$n] = true; $сж[$n] = true; } }
        $постр[] = count($см) + count($сж);
    }
    if (!$страниц) { return null; }
    sort($постр);
    return ['муж' => count($м), 'жен' => count($ж), 'всего' => count($м) + count($ж),
            'мед.на стр' => $постр[intdiv(count($постр), 2)]];
};
$свод = function (array $папки, string $имя) use ($набор) {
    $с = []; foreach ($папки as $п) { $r = $набор($п); if ($r) { $с[] = $r; } }
    if (!$с) { return; }
    $мед = function (array $v) { sort($v); return $v[intdiv(count($v), 2)]; };
    $дец = function (array $v, float $q) { sort($v); $i = $q * (count($v) - 1); $l = (int) floor($i); $h = (int) ceil($i);
        return $l == $h ? $v[$l] : $v[$l] + ($v[$h] - $v[$l]) * ($i - $l); };
    printf("%-24s (%2d наборов)", $имя, count($с));
    foreach (array_keys($с[0]) as $k) {
        $v = array_column($с, $k);
        printf("  %s %5.1f [%.1f–%.1f]", $k, $мед($v), $дец($v, .1), $дец($v, .9));
    }
    echo "\n";
};
$папки = array_slice($argv, 1);
if ($папки) {
    foreach ($папки as $п) { $свод([$п], basename($п)); }
    exit(0);
}
$СП = getenv('V5_NEW100') ?: '/tmp/claude-0/-home-user-cladue/ea580ece-89cc-5463-b9fe-78c4a0a08b0d/scratchpad';
$свод(array_slice(glob('/home/user/cladue/samples/v5-final/nabor-7*'), -20), 'наши последние 20');
$свод(glob("$СП/new100-obychnye/*"), 'NEW100 обычные');
$свод(glob("$СП/new100-gustye/*"), 'NEW100 густые');
