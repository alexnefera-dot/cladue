#!/bin/bash
# Синтаксис скриптов конструктора: PHP склеивает JS строками, и любая кавычка
# внутри inline-стиля рвёт его молча — страница отдаётся с битым <script>,
# а `php -l` этого не видит. Проверяются все блоки со скриптом, на сорока
# жребиях каждый: состав строки зависит от сида.
set -e
cd "$(dirname "$0")/../.."
d=$(mktemp -d)
trap 'rm -rf "$d"' EXIT
php -r '
require "engine/src/Generator/Rng.php"; require "engine/src/V5Blocks.php";
$база = (array) (json_decode((string) file_get_contents("engine/data-v5/igry.json"), true)["игры"] ?? []);
$блоки = [
    "vsplyvashki" => static fn (int $с): string => v5BlokVsplyvashek($с, ["Кирилл"], $база),
    "podderzhka"  => static fn (int $с): string => v5BlokPodderzhki($с),
    "tajmer"      => static fn (int $с): string => v5BlokTajmera($с % 2 ? "main" : "bonus", $с),
    "kalkulyator" => static fn (int $с): string => v5BlokKalkulyatora("bonus", $с, 15 + $с % 300),
];
foreach ($блоки as $имя => $как) {
    for ($i = 0; $i < 40; $i++) {
        $b = $как(700000 + $i * 7);
        if ($b === "" || !preg_match_all("~<script>(.*?)</script>~s", $b, $m)) { continue; }
        foreach ($m[1] as $k => $js) { file_put_contents($argv[1] . "/$имя-$i-$k.js", $js); }
    }
}' "$d"
ok=0; bad=0
for f in "$d"/*.js; do
  if node --check "$f" 2>/dev/null; then ok=$((ok+1)); else bad=$((bad+1)); echo "битый: $f"; fi
done
echo "скриптов блоков: годных $ok, битых $bad"
[ "$bad" -eq 0 ]
