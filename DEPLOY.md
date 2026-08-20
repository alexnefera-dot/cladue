# Установка редиректора на новый VPS

Пошаговая инструкция для переезда `sitegrator.com` на отдельный сервер.

---

## 1. Что заказывать

Редиректор нетребователен: пять PHP-файлов и MySQL. Реальная нагрузка — около
2 запросов/сек в среднем и до 41 в пике.

**Минимум:** 2 ядра, 4 ГБ RAM, 40 ГБ SSD.
**С запасом:** 4 ядра, 8 ГБ RAM, 80 ГБ SSD.

ОС: Ubuntu 22.04/24.04 LTS или Debian 12 (проще всего), либо AlmaLinux 9.

**Важно:** ставить только редиректор. Никаких доров на этой машине — весь смысл
переезда в том, чтобы он ни от кого не зависел.

---

## 2. Установка софта (Ubuntu/Debian)

```bash
apt update && apt upgrade -y
apt install -y apache2 mysql-server php8.2 php8.2-mysql php8.2-mbstring \
               php8.2-curl libapache2-mod-php8.2 unzip
a2enmod rewrite
systemctl enable --now apache2 mysql
```

Проверить версию — нужна **8.2 или новее** (в коде есть стрелочные функции,
на PHP 7.2/7.3 он не запустится):

```bash
php -v
```

---

## 3. Файлы

Распаковать архив в корень сайта:

```bash
mkdir -p /var/www/sitegrator
unzip sitegrator-redirector.zip -d /var/www/sitegrator
chown -R www-data:www-data /var/www/sitegrator
```

(на AlmaLinux/CentOS владелец будет `apache:apache`)

---

## 4. База данных

```bash
mysql -e "CREATE DATABASE sitegrator_stats CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
mysql -e "CREATE USER 'sitegrator'@'localhost' IDENTIFIED BY 'ПРИДУМАЙ_ПАРОЛЬ';"
mysql -e "GRANT ALL ON sitegrator_stats.* TO 'sitegrator'@'localhost';"
mysql -e "FLUSH PRIVILEGES;"
```

### Перенос данных со старого сервера

Когда старый сервер поднимется — снять дамп там:

```bash
mysqldump --single-transaction --quick --default-character-set=utf8mb4 \
          -u sitegrator_stats -p sitegrator_stats | gzip > /root/stats.sql.gz
```

Скачать и залить на новый:

```bash
scp root@СТАРЫЙ_IP:/root/stats.sql.gz .
gunzip < stats.sql.gz | mysql -u root sitegrator_stats
```

Заодно забрать накопленные клики, которые ещё не попали в базу:

```bash
scp root@СТАРЫЙ_IP:/var/www/www-root/data/www/sitegrator.com/clicks.log \
    /var/www/sitegrator/clicks.log
chown www-data:www-data /var/www/sitegrator/clicks.log
```

Их дольёт первый же запуск импорта.

Если старый сервер не поднимется вовсе — таблицы создадутся сами при первом
обращении, статистика начнётся с нуля. Кампании тогда придётся завести заново
через панель (или восстановить из `offers.php`, если он сохранился).

---

## 5. config.php

В архиве лежит `config.php.example` — скопировать его и заполнить:

```bash
cd /var/www/sitegrator
cp config.php.example config.php
nano config.php
```

(в архиве нет готового `config.php` намеренно: иначе локальная версия
подхватила бы боевые настройки вместо своих, см. `LOCAL.md`)

Заполнить только эти поля (остальное уже настроено):

```php
'mysql_db'   => 'sitegrator_stats',
'mysql_user' => 'sitegrator',
'mysql_pass' => 'ТОТ_ПАРОЛЬ',
'click_log'  => '/var/www/sitegrator/clicks.log',   // явный путь, общий для go.php и крона
```

Проверить, что режим нормальный (не аварийный):

```php
'db_driver'      => 'mysql',
'db_write'       => true,
'fallback_offer' => '',
```

Пароль панели и `postback_secret` оставить прежними — иначе придётся менять
ссылки постбеков в кабинетах партнёрок.

---

## 6. Apache

```bash
cat > /etc/apache2/sites-available/sitegrator.conf <<'EOF'
<VirtualHost *:80>
    ServerName sitegrator.com
    ServerAlias www.sitegrator.com
    DocumentRoot /var/www/sitegrator

    <Directory /var/www/sitegrator>
        AllowOverride All
        Require all granted
    </Directory>

    ErrorLog  ${APACHE_LOG_DIR}/sitegrator-error.log
    CustomLog ${APACHE_LOG_DIR}/sitegrator-access.log combined
</VirtualHost>
EOF

a2ensite sitegrator
a2dissite 000-default
systemctl reload apache2
```

`AllowOverride All` обязателен — без него не работает `.htaccess`, а в нём
живёт правило `/go/СЛАГ → /go.php?l=СЛАГ`.

### HTTPS

```bash
apt install -y certbot python3-certbot-apache
certbot --apache -d sitegrator.com -d www.sitegrator.com
```

Если домен за Cloudflare в режиме «Full (strict)» — сертификат нужен всё равно.

---

## 7. Крон

```bash
crontab -e
```

Добавить (путь к php проверить через `which php`):

```
0 * * * * /usr/bin/php /var/www/sitegrator/import.php >/dev/null 2>&1
```

Раз в час: переливает `clicks.log` в MySQL, досвязывает конверсии, чистит
старые клики и прогревает кэш панели.

**Проверить вручную первым запуском:**

```bash
sudo -u www-data /usr/bin/php /var/www/sitegrator/import.php
```

Запускать под тем же пользователем, что и веб (`www-data`) — иначе файлы кэша
и `clicks.log` получат владельца root, и панель не сможет их обновлять.

---

## 8. Права

```bash
cd /var/www/sitegrator
touch clicks.log
mkdir -p cache
chown -R www-data:www-data .
chmod 775 cache
```

---

## 9. Проверка до переключения DNS

Пока трафик ещё идёт на старый сервер, проверить новый по IP:

```bash
curl -sI -o /dev/null -w "%{http_code}\n" -H "Host: sitegrator.com" http://НОВЫЙ_IP/go/dorgen_engine
```

Ожидается **302**. Если 404 — не работает `.htaccess` (проверить `AllowOverride All`
и `a2enmod rewrite`). Если 500 — смотреть `/var/log/apache2/sitegrator-error.log`.

Панель: `http://НОВЫЙ_IP/stats.php` с заголовком Host или уже после переключения DNS.

---

## 10. Переключение трафика

Домен за Cloudflare, поэтому переезд бесшовный:

1. Cloudflare → DNS → запись `sitegrator.com` (A-запись)
2. Поменять IP на новый, оранжевое облако оставить включённым
3. TTL стоит Auto — переключение занимает секунды

Старый сервер не выключать ещё сутки: часть постбеков может прийти на него,
пока обновляется кэш DNS у партнёрок.

---

## 11. После переключения

```bash
# редиректы идут
tail -f /var/www/sitegrator/clicks.log

# импорт отработал
sudo -u www-data php /var/www/sitegrator/import.php

# панель открывается и показывает свежие цифры
```

В шапке панели есть плашка «Обновлено: HH:MM» — если она красная с пометкой
«проверь крон», значит импорт не отрабатывает.

---

## 12. Чего НЕ повторять со старого сервера

- **Не ставить сюда доры.** Весь смысл переезда — изоляция.
- **Не включать режим Nginx+PHP-FPM** без переноса правил из `.htaccess`
  (nginx его не читает — редиректы отдадут 404).
- **Не ставить PHP 7.x** — код не запустится.
- Если ставишь ispmanager — после каждой правки настроек сайта проверяй,
  не вписал ли он в конфиг PHP несуществующие расширения (на старом сервере
  `extension=sqlite3.so` писал по строке в error.log на каждый запрос,
  это давало гигабайты логов и постоянный дисковый I/O).

---

## Что где лежит

| файл | назначение |
|------|-----------|
| `go.php` | редирект + запись клика в лог. **Не трогает MySQL** |
| `offers.php` | автогенерируемый кэш слаг→URL (создаётся импортом) |
| `clicks.log` | накопитель кликов между запусками крона |
| `import.php` | крон: лог → MySQL, досвязывание конверсий, очистка, прогрев кэша |
| `stats.php` | панель статистики |
| `postback.php` | приём постбеков от партнёрок |
| `db.php` | общие функции, кэш панели, генерация offers.php |
| `config.php` | настройки (креды БД заполняются на сервере) |
| `cache/` | кэш агрегатов панели (создаётся автоматически) |

Подробности архитектуры и разбор прошлых инцидентов — в `ARCHITECTURE.md`.
