#!/usr/bin/env bash
# Сборка готового набора к выдаче: снять то, что не текст, замерить, собрать
# отчёт и архив. Порядок важен — отчёт строится ПОСЛЕ снятия схемы и чипов,
# иначе в нём остаются числа от файлов, которых уже нет.
#
#   engine/pack-v3.sh <папка-с-набором> <донор> <имя-набора> [корпус]
#
# Пример: engine/pack-v3.sh /tmp/v3f2 7 svyazka-nabor-9 v3-bundle
set -euo pipefail

DIR="${1:?папка с набором}"
DONOR="${2:?донор}"
NAME="${3:?имя набора для архива и отчёта}"
CORPUS="${4:-v3-bundle}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT"

# Черновики реалайзеров рядом с текстом в архив не едут.
rm -f "$DIR"/brief-*.md "$DIR"/*.py 2>/dev/null || true

echo "— снимаем схему и интерфейсные полосы"
php engine/strip-chrome.php "$DIR" | tail -3

echo "— замер"
php engine/compare-v3.php "$DIR" "$DONOR" --corpus="$CORPUS" 2>/dev/null | tail -20

echo "— отчёт"
php engine/build-vs-reference-v3.php "$DIR" "$DONOR" --corpus="$CORPUS" "reports/v3/${NAME}.html" | tail -2

DEST="samples/v3-final/${NAME}"
mkdir -p "$DEST"
cp "$DIR"/*.html "$DEST"/
[ -f "$DIR/meta.json" ] && cp "$DIR/meta.json" "$DEST"/

PACK="/tmp/pack-${NAME}"
rm -rf "$PACK"; mkdir -p "$PACK/${NAME}"
cp "$DIR"/*.html "$PACK/${NAME}"/
[ -f "$DIR/meta.json" ] && cp "$DIR/meta.json" "$PACK/${NAME}"/
cp "reports/v3/${NAME}.html" "$PACK/${NAME}/OTCHET-sravnenie-s-referensom.html"
( cd "$PACK" && zip -qr "/tmp/${NAME}.zip" "${NAME}" )

echo "→ /tmp/${NAME}.zip"
echo "→ reports/v3/${NAME}.html"
echo "→ ${DEST}/"
