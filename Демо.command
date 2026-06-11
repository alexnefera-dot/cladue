#!/bin/zsh
# Pipboy ДЕМО: отдельная база demo.db со всеми тестовыми данными.
# Твоя основная база (data.db) не трогается. Можно запускать параллельно с основной.
cd "$(dirname "$0")"
git pull
lsof -ti:7778 | xargs kill 2>/dev/null
cd app
( sleep 1.5 && open "http://localhost:7778" ) &
echo "→ Запускаю ДЕМО на http://localhost:7778 (база app/demo.db)"
echo "→ Сбросить демо к начальному виду: удали файл app/demo.db и запусти снова"
PIPBOY_DB="$PWD/demo.db" PORT=7778 node server.js
