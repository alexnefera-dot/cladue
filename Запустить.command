#!/bin/zsh
# Pipboy: двойной клик в Finder — обновляет код и открывает приложение
# отдельным окном (как настоящая программа), без Electron.
cd "$(dirname "$0")"
echo "→ Обновляю код…"
git pull --quiet 2>/dev/null
echo "→ Останавливаю старый сервер, если был…"
lsof -ti:7777 | xargs kill 2>/dev/null
cd app

URL="http://localhost:7777"
# окно-приложение: Chrome/Brave/Edge в режиме --app дают окно без вкладок и адресной строки.
APP_WINDOW() {
  for B in \
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser" \
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"; do
    if [ -x "$B" ]; then
      "$B" --app="$URL" --window-size=1380,900 >/dev/null 2>&1 &
      return 0
    fi
  done
  return 1
}

( sleep 1.5; APP_WINDOW || open "$URL" ) &
echo "→ Pipboy запущен. Это окно держит приложение — сворачивай, но не закрывай."
node server.js
