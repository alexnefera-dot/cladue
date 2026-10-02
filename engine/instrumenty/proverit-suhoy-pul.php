<?php
// Проверка транша. Тошноту считаем не по одной записи — у короткой фразы она
// всегда нулевая, — а по двадцати записям подряд: столько их ложится на одну
// густую страницу, и ровно эта величина завалила прошлую партию (38.5–53.3
// при корпусных 28–40).
require_once 'engine/src/StopWords.php';
require_once 'engine/src/Morphology.php';
require_once 'engine/src/TextMetrics.php';
$старый = json_decode(file_get_contents('engine/data-v5/suhaya-proza-v5.json'), true);
$новый = json_decode(file_get_contents($argv[1] ?? "engine/data-v5/suhaya-proza-v5.json"), true);
$кор = fn(string $w): string => mb_substr($w, 0, 6);
$корни = function(array $зап) use ($кор): array {
    $из = [];
    foreach ($зап as $z) {
        foreach (preg_match_all('~[А-Яа-яЁё]{4,}~u', mb_strtolower($z), $m) ? $m[0] : [] as $w) {
            $из[$кор($w)] = ($из[$кор($w)] ?? 0) + 1;
        }
    }
    return $из;
};
$пачкой = function(array $зап, int $n = 20) {
    // Двадцать записей, как их берёт страница. Окно не одно: движок сортирует
    // пул по сиду, поэтому на страницу попадает любая двадцатка, и замер по
    // первым двадцати позволял подгонять текст под положение окна, а не под
    // настоящую концентрацию. Берём десять окон со сдвигом и отдаём медиану и
    // худшее — судить надо по худшему, его и увидит часть наборов.
    $тош = []; $водн = [];
    $всего = count($зап);
    for ($i = 0; $i < 10; $i++) {
        $от = $всего > $n ? intdiv($i * ($всего - $n), 9) : 0;
        $t = trim(preg_replace('~\{[A-ZА-Я0-9]+\}~u', 'сто',
            implode(' ', array_slice($зап, $от, $n))));
        if ($t === '') { continue; }
        $м = new TextMetrics($t);
        $тош[] = $м->nauseaAcademic(); $водн[] = $м->water();
    }
    sort($тош); sort($водн);
    return [$водн[intdiv(count($водн), 2)], $тош[intdiv(count($тош), 2)], end($тош)];
};
printf("%-13s %4s %6s %9s %11s %8s %9s %7s\n",
    'тип','n','слов','водность','тошнота 20','худшая','корней >2','коротких');
foreach ($новый as $т => $зап) {
    $водн=[]; $длины=[];
    foreach ($зап as $z) {
        $t = trim(preg_replace('~\{[A-ZА-Я0-9]+\}~u', 'сто', $z));
        $м = new TextMetrics($t);
        $водн[] = $м->water();
        $длины[] = count(preg_split('~\s+~u', $t, -1, PREG_SPLIT_NO_EMPTY));
    }
    sort($водн);
    [$вП, $тП, $тХ] = $пачкой($зап);
    $к = $корни($зап); $много = array_filter($к, fn($n) => $n > 2); arsort($много);
    printf("%-13s %4d %6.1f %9.1f %11.1f %8.1f %9d %7d\n", $т, count($зап),
        array_sum($длины)/count($длины), $водн[intdiv(count($водн),2)], $тП, $тХ,
        count($много), count(array_filter($длины, fn($l) => $l < 5)));
    if ($много) {
        $с = [];
        foreach (array_slice($много, 0, 8, true) as $k => $n) { $с[] = $k . ' ' . $n; }
        echo '   корни чаще двух: ' . implode(', ', $с) . "\n";
    }
}
echo "\nдля сравнения — прежний пул:\n";
printf("%-13s %9s %11s %8s\n",'тип','водность','тошнота 20','худшая');
foreach ($старый as $т => $зап) {
    $водн=[];
    foreach ($зап as $z) { $t=trim(preg_replace('~\{[A-ZА-Я0-9]+\}~u','сто',$z)); $м=new TextMetrics($t); $водн[]=$м->water(); }
    sort($водн);
    [$вП, $тП, $тХ] = $пачкой($зап);
    printf("%-13s %9.1f %11.1f %8.1f\n", $т, $водн[intdiv(count($водн),2)], $тП, $тХ);
}
