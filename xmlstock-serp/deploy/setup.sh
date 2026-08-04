#!/usr/bin/env bash
# --------------------------------------------------------------------------- #
#  Установка xmlstock-serp как фоновой службы на Linux-VPS (systemd).
#
#  Запуск (из папки проекта, БЕЗ sudo — sudo вызывается только там, где нужно):
#      bash deploy/setup.sh
#
#  Служба слушает 127.0.0.1:PORT (по умолчанию 5050) — только «внутри» сервера,
#  наружу НЕ выставляется. Интерфейс открывается с вашего компьютера через
#  SSH-туннель (команда печатается в конце). Так ваш API-ключ xmlstock не
#  оказывается в открытом доступе.
# --------------------------------------------------------------------------- #
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"      # папка проекта = родитель deploy/
cd "$HERE"
RUN_USER="${SUDO_USER:-$(id -un)}"
PORT="${PORT:-5050}"
AUTH_USER="${AUTH_USER:-admin}"
AUTH_PASS="${AUTH_PASS:-}"                     # задайте, чтобы включить пароль:  AUTH_PASS=... bash deploy/setup.sh
SERVICE_NAME="xmlstock-serp"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "──────────────────────────────────────────────"
echo "  Проект:              $HERE"
echo "  Пользователь службы: $RUN_USER"
echo "  Локальный порт:      $PORT (только 127.0.0.1)"
if [ -n "$AUTH_PASS" ]; then
  echo "  Пароль интерфейса:   включён (пользователь: $AUTH_USER)"
else
  echo "  Пароль интерфейса:   выкл. (задайте AUTH_PASS=... если выставляете наружу)"
fi
echo "──────────────────────────────────────────────"

# необязательные строки авторизации для systemd-юнита
AUTH_ENV=""
if [ -n "$AUTH_PASS" ]; then
  AUTH_ENV="Environment=AUTH_USER=${AUTH_USER}
Environment=AUTH_PASS=${AUTH_PASS}"
fi

# 1) python3
if ! command -v python3 >/dev/null 2>&1; then
  echo "✗ Не найден python3. Установите его и повторите:"
  echo "    Ubuntu/Debian:  sudo apt update && sudo apt install -y python3 python3-venv python3-pip"
  echo "    Alma/CentOS:    sudo dnf install -y python3 python3-pip"
  exit 1
fi

# 2) venv + зависимости (создаём от текущего пользователя, не от root)
if [ ! -d .venv ]; then
  echo "→ Создаю виртуальное окружение (.venv)…"
  if ! python3 -m venv .venv 2>/dev/null; then
    echo "✗ Не удалось создать venv. На Ubuntu/Debian поставьте модуль venv:"
    echo "    sudo apt install -y python3-venv"
    exit 1
  fi
fi
echo "→ Ставлю зависимости (Flask, requests, openpyxl)…"
./.venv/bin/pip install --upgrade pip >/dev/null
./.venv/bin/pip install -r requirements.txt

# 3) systemd-служба
echo "→ Регистрирую службу $SERVICE_FILE (нужен sudo)…"
sudo tee "$SERVICE_FILE" >/dev/null <<UNIT
[Unit]
Description=XMLStock SERP — локальный SEO-инструмент (ТОП, трекер, мониторинг запусков)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$HERE
Environment=HOST=127.0.0.1
Environment=PORT=$PORT
Environment=NO_BROWSER=1
$AUTH_ENV
ExecStart=$HERE/.venv/bin/python $HERE/app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable --now "$SERVICE_NAME"
sleep 1

echo
if sudo systemctl is-active --quiet "$SERVICE_NAME"; then
  echo "✓ Служба запущена и слушает http://127.0.0.1:$PORT (на сервере)."
else
  echo "✗ Служба не поднялась. Смотрите логи:  journalctl -u $SERVICE_NAME -n 40 --no-pager"
  exit 1
fi

cat <<MSG

──────────────────────────────────────────────
  ГОТОВО. Мониторинг работает на сервере 24/7.
──────────────────────────────────────────────

Чтобы открыть интерфейс у СЕБЯ на маке — прокиньте SSH-туннель
(замените <IP-сервера> на адрес VPS):

    ssh -N -L $PORT:localhost:$PORT $RUN_USER@<IP-сервера>

и, не закрывая это окно, откройте в браузере:

    http://localhost:$PORT

Управление службой на сервере:
    sudo systemctl status  $SERVICE_NAME     # состояние
    sudo systemctl restart $SERVICE_NAME     # перезапустить
    sudo systemctl stop    $SERVICE_NAME     # остановить
    journalctl -u $SERVICE_NAME -f           # живые логи

Файлы срезов лежат в:  $HERE/output/
MSG
