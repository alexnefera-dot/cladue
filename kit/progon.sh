#!/usr/bin/env bash
# Полный прогон по папке с шаблонами. Отчёты складываются в ./otchet/
#
#   ./progon.sh <папка-с-шаблонами> [--pages main,slots,bonus] [--porog 6]
#
# Шаг 0 отбирает наборы нашего конструктора по сигнатуре блоков; все посторонние
# шаблоны из дальнейшего замера исключаются и перечисляются в 00-otbor.txt.
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="${1:?укажите папку с шаблонами: ./progon.sh OLD50}"
shift || true
OUT="otchet"
mkdir -p "$OUT"
PY=${PYTHON:-python3}

# --porog адресован только отбору, остальным скриптам его передавать не нужно
POROG=()
REST=()
while [ $# -gt 0 ]; do
  case "$1" in
    --porog) POROG=(--porog "$2"); shift 2 ;;
    *) REST+=("$1"); shift ;;
  esac
done
set -- ${REST[@]+"${REST[@]}"}

echo "→ отбор наборов по сигнатуре движка"
$PY "$KIT/otbor.py" "$SRC" --out "$OUT/nabory.txt" ${POROG[@]+"${POROG[@]}"} | tee "$OUT/00-otbor.txt"
ONLY=(--only-file "$OUT/nabory.txt")

echo "→ проверка структуры"
$PY "$KIT/proverka.py" "$SRC" "${ONLY[@]}" | tee "$OUT/01-proverka.txt"

echo "→ замер (медиана / полоса / CV)"
$PY "$KIT/zamer.py"   "$SRC" "${ONLY[@]}" "$@" > "$OUT/02-zamer.md"

echo "→ бренд по поверхностям"
$PY "$KIT/brend.py"   "$SRC" "${ONLY[@]}" "$@" > "$OUT/03-brend.md"

echo "→ пересечения по шинглам"
$PY "$KIT/shingly.py" "$SRC" "${ONLY[@]}" "$@" > "$OUT/04-shingly.md"

echo "→ блоки и варианты"
$PY "$KIT/bloki.py"   "$SRC" "${ONLY[@]}" --seq > "$OUT/05-bloki.md"

echo
echo "Готово. Отчёты в $OUT/:"
ls -la "$OUT"
