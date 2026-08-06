#!/usr/bin/env bash
# Пауза: остановить службу и закрыть порт (дырку). Вернуть всё — deploy/resume.sh
# Запускать от root:  bash deploy/pause.sh
set -u
PORT="${PORT:-5050}"
SERVICE="xmlstock-serp"

echo "→ Останавливаю службу $SERVICE и убираю из автозапуска…"
systemctl disable --now "$SERVICE" 2>/dev/null || true

echo "→ Закрываю порт $PORT (удаляю разрешающие правила)…"
while iptables -C INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null; do
  iptables -D INPUT -p tcp --dport "$PORT" -j ACCEPT
done

echo
echo "✓ Готово. Служба остановлена, порт $PORT закрыт (снаружи уже недоступно)."
echo "  Если добавлял правило в ISPmanager → Брандмауэр — выключи/удали его и там."
echo "  Вернуть всё обратно одной командой:  bash deploy/resume.sh"
