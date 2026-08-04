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
HOST="${HOST:-127.0.0.1}"                      # 127.0.0.1 = только туннель; 0.0.0.0 = доступ по домен:порт (PUBLIC=1)
[ "${PUBLIC:-0}" = "1" ] && HOST="0.0.0.0"
AUTH_USER="${AUTH_USER:-admin}"
AUTH_PASS="${AUTH_PASS:-}"                     # задайте, чтобы включить пароль:  AUTH_PASS=... bash deploy/setup.sh
SERVICE_NAME="xmlstock-serp"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "──────────────────────────────────────────────"
echo "  Проект:              $HERE"
echo "  Пользователь службы: $RUN_USER"
if [ "$HOST" = "0.0.0.0" ]; then
  echo "  Доступ:              наружу по адресу домен:$PORT (открыт для интернета)"
else
  echo "  Доступ:              только 127.0.0.1:$PORT (через SSH-туннель)"
fi
if [ -n "$AUTH_PASS" ]; then
  echo "  Пароль интерфейса:   включён (пользователь: $AUTH_USER)"
else
  echo "  Пароль интерфейса:   выкл. (задайте AUTH_PASS=... если выставляете наружу)"
fi
echo "──────────────────────────────────────────────"
if [ "$HOST" = "0.0.0.0" ] && [ -z "$AUTH_PASS" ]; then
  echo "⚠ Внимание: доступ открыт наружу БЕЗ пароля. Кто угодно сможет пользоваться"
  echo "  инструментом и вашим ключом xmlstock. Лучше: PUBLIC=1 AUTH_PASS=... bash deploy/setup.sh"
  echo
fi

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
Environment=HOST=$HOST
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

echo
echo "──────────────────────────────────────────────"
echo "  ГОТОВО. Мониторинг работает на сервере 24/7."
echo "──────────────────────────────────────────────"
echo
if [ "$HOST" = "0.0.0.0" ]; then
  SRV_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  cat <<MSG
Интерфейс доступен прямо по адресу (порт $PORT смотрит наружу):

    http://${SRV_IP:-<IP-сервера>}:$PORT
    http://твой-домен:$PORT        (если домен указывает A-записью на этот сервер)

⚠ ОБЯЗАТЕЛЬНО откройте порт $PORT в фаерволе, иначе не откроется:
    • ISPmanager: «Настройки → Брандмауэр» → разрешить TCP $PORT
    • либо в консоли:
        sudo ufw allow $PORT/tcp                                   # Ubuntu/Debian
        sudo firewall-cmd --permanent --add-port=$PORT/tcp && sudo firewall-cmd --reload   # Alma/CentOS
MSG
else
  cat <<MSG
Открой интерфейс у СЕБЯ на маке через SSH-туннель (замените <IP-сервера>):

    ssh -N -L $PORT:localhost:$PORT $RUN_USER@<IP-сервера>

и в браузере:  http://localhost:$PORT
MSG
fi
cat <<MSG

Управление службой:
    sudo systemctl status  $SERVICE_NAME
    sudo systemctl restart $SERVICE_NAME
    sudo systemctl stop    $SERVICE_NAME
    journalctl -u $SERVICE_NAME -f

Файлы срезов:  $HERE/output/
MSG
