#!/bin/zsh
# Пересборка финальной (Release) версии Pipboy и установка в /Applications.
#
# Нужно ТОЛЬКО когда менялись нативные Swift-файлы оболочки (native/Pipboy/*.swift).
# Правки фронта (app/public) пересборки НЕ требуют — приложение само делает
# `git pull` при запуске и грузит свежий фронт. Достаточно переоткрыть Pipboy.
#
# Запуск из корня репозитория:  zsh scripts/rebuild-mac.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "→ свежий код"
git pull --rebase --autostash

echo "→ закрываю запущенный Pipboy"
osascript -e 'tell application "Pipboy" to quit' 2>/dev/null || true

echo "→ сборка Release (xcode-select указывает на CLT, поэтому через DEVELOPER_DIR)"
DD="${TMPDIR:-/tmp}/pipboy-dd"
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild \
  -project native/Pipboy.xcodeproj -scheme Pipboy -configuration Release \
  -derivedDataPath "$DD" build

echo "→ установка в /Applications"
REL="$DD/Build/Products/Release/Pipboy.app"
rm -rf /Applications/Pipboy.app
ditto "$REL" /Applications/Pipboy.app

echo "→ запуск"
open /Applications/Pipboy.app
echo "✓ готово: /Applications/Pipboy.app обновлён ($(stat -f '%Sm' /Applications/Pipboy.app/Contents/MacOS/Pipboy))"
