#!/usr/bin/env bash
# Вернуть из паузы: открыть порт и запустить службу. Пауза — deploy/pause.sh
# Запускать от root:  bash deploy/resume.sh
set -u
PORT="${PORT:-5050}"
SERVICE="xmlstock-serp"

echo "→ Открываю порт $PORT…"
iptables -C INPUT -p tcp --dport "$PORT" -j ACCEPT 2>/dev/null \
  || iptables -I INPUT -p tcp --dport "$PORT" -j ACCEPT

echo "→ Запускаю службу $SERVICE и возвращаю в автозапуск…"
systemctl enable --now "$SERVICE"

sleep 1
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
if systemctl is-active --quiet "$SERVICE"; then
  echo "✓ Готово. Открывай:  http://${IP:-<IP-сервера>}:$PORT   (логин admin + пароль)"
else
  echo "✗ Служба не поднялась — глянь логи:  journalctl -u $SERVICE -n 30 --no-pager"
fi
echo "  Чтобы правило порта пережило перезагрузку — продублируй TCP $PORT в ISPmanager → Брандмауэр."
