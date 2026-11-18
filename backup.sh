#!/bin/bash
# backup.sh — полный бэкап трекера: код панели + дамп базы в один архив.
#
# Запуск на сервере, из каталога панели:
#   bash backup.sh
#
# Кладёт архив в /root/backup/sitegrator-ГГГГ-ММ-ДД-ЧЧММ.tar.gz и оставляет
# последние 7 штук. Пароль базы берётся из config.php и передаётся mysqldump
# через временный файл с правами 600, а не аргументом командной строки:
# аргументы видны любому пользователю в выводе ps.
#
# В архиве лежит config.php с паролем от базы — храни его как секрет.

set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"      # каталог панели
NAME="$(basename "$SRC")"
OUT=/root/backup
TS="$(date +%F-%H%M)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

[ -f "$SRC/config.php" ] || { echo "Не вижу config.php в $SRC — запускай из каталога панели"; exit 1; }

mkdir -p "$OUT"

# ---------- база ----------
DRIVER="$(php -r '$c=require $argv[1]; echo $c["db_driver"] ?? "sqlite";' "$SRC/config.php")"

if [ "$DRIVER" = "mysql" ]; then
    php -r '
      $c = require $argv[1];
      printf("[client]\nhost=%s\nport=%d\nuser=%s\npassword=\"%s\"\n",
        $c["mysql_host"] ?? "localhost", $c["mysql_port"] ?? 3306,
        $c["mysql_user"] ?? "", str_replace("\"","\\\"",$c["mysql_pass"] ?? ""));
    ' "$SRC/config.php" > "$WORK/my.cnf"
    chmod 600 "$WORK/my.cnf"

    DB="$(php -r '$c=require $argv[1]; echo $c["mysql_db"] ?? "";' "$SRC/config.php")"
    [ -n "$DB" ] || { echo "В config.php не указан mysql_db"; exit 1; }

    echo "дамп базы $DB ..."
    # --single-transaction: снимок без блокировки таблиц, трекер продолжает писать
    mysqldump --defaults-extra-file="$WORK/my.cnf" \
              --single-transaction --quick --default-character-set=utf8mb4 \
              "$DB" > "$WORK/db.sql"
else
    echo "база sqlite, копируем файл ..."
    DBF="$(php -r '$c=require $argv[1]; echo $c["db_file"] ?? "stats.sqlite";' "$SRC/config.php")"
    [ -f "$SRC/$DBF" ] && cp "$SRC/$DBF" "$WORK/" || echo "файл базы $DBF не найден, пропускаем"
fi

# ---------- код ----------
echo "архив кода ..."
tar czf "$WORK/panel.tar.gz" -C "$(dirname "$SRC")" "$NAME"

# ---------- один файл ----------
FILE="$OUT/sitegrator-$TS.tar.gz"
tar czf "$FILE" -C "$WORK" .
chmod 600 "$FILE"

# ---------- чистка старых ----------
ls -1t "$OUT"/sitegrator-*.tar.gz 2>/dev/null | tail -n +8 | xargs -r rm -f

echo
echo "готово: $FILE"
du -h "$FILE"
echo
echo "скачать на свой компьютер:"
echo "  scp root@$(hostname -I | awk '{print $1}'):$FILE ~/Downloads/"
