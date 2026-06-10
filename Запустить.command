#!/bin/zsh
# Pipboy: двойной клик в Finder — обновить, запустить, открыть браузер
cd "$(dirname "$0")"
echo "→ Обновляю код…"
git pull
echo "→ Останавливаю старый сервер, если был…"
lsof -ti:7777 | xargs kill 2>/dev/null
cd app
( sleep 1.5 && open "http://localhost:7777" ) &
echo "→ Запускаю Pipboy (закроешь это окно — приложение остановится)"
node server.js
