# Site Migrator — автоматизация переезда сайтов

Скрипт для рутины при смене домена статических сайтов: ставит **301-редирект в Cloudflare**
и **добавляет + подтверждает права на новый домен в Яндекс.Вебмастере**. Без внешних
зависимостей — нужен только Python 3.8+.

## Что делает скрипт

За один запуск `python migrate.py old-site.ru new-site.ru`:

1. **Cloudflare** — находит зону старого домена, ставит проксируемую DNS-запись (чтобы трафик
   шёл через edge Cloudflare) и создаёт правило **301-редиректа** `old-site.ru` и
   `www.old-site.ru` → `https://new-site.ru` с сохранением пути и query-строки.
2. **Яндекс.Вебмастер** — добавляет новый домен, запрашивает код подтверждения, кладёт
   **TXT-запись `yandex-verification: …`** в DNS нового домена (через Cloudflare) и дожидается
   статуса «права подтверждены».
3. Печатает, что осталось сделать руками.

## Чего скрипт НЕ делает (и почему)

Финальный шаг — **«Переезд сайта»** (назначение нового домена главным зеркалом) — в API
Яндекс.Вебмастера **отсутствует**, он есть только в веб-интерфейсе. Поэтому скрипт его не
трогает и в конце печатает прямое указание, куда нажать.

Это не страшно: Яндекс давно отказался от директивы `Host` и **определяет зеркала
автоматически по 301-редиректу**. Корректный редирект (который ставит скрипт) — это
основная часть работы; кнопка «Переезд» в интерфейсе лишь ускоряет процесс.

## Установка

```bash
git clone <repo-url>
cd cladue
cp .env.example .env      # затем впишите токены (см. ниже)
```

Зависимостей нет — `pip install` не нужен.

## Токены

### Cloudflare API Token

1. https://dash.cloudflare.com/profile/api-tokens → **Create Token** → **Custom token**.
2. Права (Permissions):
   - `Zone` → `Zone` → **Read**
   - `Zone` → `DNS` → **Edit**
   - `Zone` → `Dynamic Redirect` → **Edit**
3. Zone Resources: `Include` → `All zones` (или перечислите нужные).
4. Скопируйте токен в `.env` → `CLOUDFLARE_API_TOKEN`.

> Нужен именно **API Token**, а не Global API Key.

### Яндекс OAuth-токен

1. https://oauth.yandex.ru/client/new — создайте приложение.
   - Платформа: **Веб-сервисы**, Redirect URI: `https://oauth.yandex.ru/verification_code`.
   - Доступы (API Яндекс.Вебмастера): **«Добавление сайтов и управление ими»** и
     **«Подтверждение прав владельца сайта»** (`webmaster:hostadd`, `webmaster:verify`).
2. Возьмите `ClientID` приложения и откройте в браузере:
   `https://oauth.yandex.ru/authorize?response_type=token&client_id=ВАШ_CLIENT_ID`
3. Подтвердите доступ — в адресной строке появится `access_token=…`. Это и есть токен.
4. Впишите его в `.env` → `YANDEX_OAUTH_TOKEN`.

## Использование

```bash
# один сайт
python migrate.py old-site.ru new-site.ru

# пачкой из файла (по строке "old,new")
python migrate.py --batch domains.csv
```

Опции:

| Опция | По умолчанию | Назначение |
|-------|--------------|------------|
| `--verify {dns,html,meta}` | `dns` | способ подтверждения прав в Яндексе |
| `--status-code {301,302,307,308}` | `301` | код редиректа |
| `--timeout СЕК` | `300` | сколько ждать подтверждения прав |

Способы подтверждения:
- **`dns`** (рекомендуется) — TXT-запись добавляется в Cloudflare автоматически. Требует, чтобы
  новый домен тоже был зоной в Cloudflare.
- **`html`** — скрипт покажет имя и содержимое файла `yandex_<код>.html`; загрузите его в корень
  сайта на хостинге и нажмите Enter.
- **`meta`** — скрипт покажет метатег; добавьте его в `<head>` главной страницы и нажмите Enter.

## Требования к доменам

- **Старый домен** уже добавлен как сайт в Cloudflare (его NS указывают на Cloudflare) — иначе
  редирект ставить негде.
- Для `--verify dns` **новый домен** тоже должен быть зоной в Cloudflare. Если его там нет —
  используйте `--verify html` или `--verify meta`.

## Как это устроено

```
cladue/
├── migrate.py            # CLI: разбор аргументов и оркестрация шагов
├── migrator/
│   ├── http.py           # HTTP-клиент на urllib (без зависимостей)
│   ├── config.py         # загрузка .env и проверка токенов
│   ├── cloudflare.py     # зоны, DNS, правило редиректа (Rulesets API)
│   └── yandex.py         # добавление хоста и подтверждение прав (Webmaster API v4)
├── .env.example          # шаблон для токенов
└── domains.example.csv   # пример файла для --batch
```

Повторный запуск для той же пары доменов безопасен (идемпотентность): существующая
проксируемая DNS-запись и TXT не дублируются, прежнее правило редиректа заменяется.

## Безопасность

- `.env` с токенами — в `.gitignore`, в репозиторий не попадает. Никогда не коммитьте токены.
- Cloudflare-токену давайте только три права из инструкции выше, область — нужные зоны.

## Полезные ссылки

- [Cloudflare — редирект домена](https://developers.cloudflare.com/fundamentals/manage-domains/redirect-domain/)
- [Cloudflare — Single Redirects через API](https://developers.cloudflare.com/rules/url-forwarding/single-redirects/create-api/)
- [API Яндекс.Вебмастера — добавление сайта](https://yandex.ru/dev/webmaster/doc/ru/reference/hosts-add-site)
- [API Яндекс.Вебмастера — подтверждение прав](https://yandex.ru/dev/webmaster/doc/ru/reference/host-verification-post)
