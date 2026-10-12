#!/bin/bash
# Синтаксис скрипта всплывашек: PHP склеивает JS строками, и любая кавычка
# внутри inline-стиля рвёт его молча — страница отдаётся с битым <script>.
# Проверяется на сорока жребиях, потому что состав строки зависит от сида.
set -e
cd "$(dirname "$0")/../.."
d=$(mktemp -d)
trap 'rm -rf "$d"' EXIT
php -r '
require "engine/src/Generator/Rng.php"; require "engine/src/V5Blocks.php";
$база = (array) (json_decode((string) file_get_contents("engine/data-v5/igry.json"), true)["игры"] ?? []);
for ($i = 0; $i < 40; $i++) {
    $b = v5BlokVsplyvashek(700000 + $i * 7, ["Кирилл"], $база);
    if ($b === "" || !preg_match("~<script>(.*)</script>~s", $b, $m)) { continue; }
    file_put_contents($argv[1] . "/t$i.js", $m[1]);
}' "$d"
ok=0; bad=0
for f in "$d"/*.js; do
  if node --check "$f" 2>/dev/null; then ok=$((ok+1)); else bad=$((bad+1)); echo "битый: $f"; fi
done
echo "скриптов всплывашек: годных $ok, битых $bad"
[ "$bad" -eq 0 ]
