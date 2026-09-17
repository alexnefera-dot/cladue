# Analytics Export API — как пользоваться

Read-only API системы запусков (dorgen-engine).  
Контракт ориентир: `ANALITIKA.html` (блок 1). Режим: **только чтение существующих данных**, без смены бизнес-логики.

**Base path:** `https://<host-админки>/v1`  
**Auth:** `Authorization: Bearer <token>`  
Токен задаётся в `config/app_local.php` → `AnalyticsApi.tokens`.

---

## Общие правила

| | |
|--|--|
| Метод | только `GET` |
| Формат | JSON UTF-8 |
| Время | Europe/Kyiv, ISO-8601 со смещением (`2026-09-15T13:03:11+03:00`) |
| `null` | нет значения → `null` (не `""` / `0` / `"-"`) |
| Хост | lowercase, без схемы и `www` |
| Пагинация | `limit` (default **500**, max **1000**) + opaque `cursor` |
| Окно дат | max **31** день включительно |
| Rate limit | ~30 req/min на токен; max **2** тяжёлых запроса одновременно → иначе `429` |

**Обёртка списков:**

```json
{
  "data": [ ... ],
  "meta": {
    "count": 500,
    "next_cursor": "eyJpZCI6MTIzfQ",
    "generated_at": "2026-09-17T16:20:00+03:00"
  }
}
```

`next_cursor: null` — последняя страница. Следующий запрос: тот же фильтр + `cursor=<next_cursor>`.

**Ошибки:**

```json
{ "error": { "code": "unauthorized", "message": "..." } }
```

`unauthorized` 401 · `invalid_param` 400 · `invalid_range` 400 · `rate_limited` 429 · `internal` 500

---

## Эндпоинты

### 1. `GET /v1/subdomains`

Основная выгрузка: **одна строка = сабдомен** (включая «мёртвые»).

| Параметр | Обяз. | Описание |
|----------|-------|----------|
| `date_from`, `date_to` | да | `YYYY-MM-DD` |
| `date_field` | нет | `domain_created` (default) · `cd_created` · `pipeline_started` |
| `content_domain_id` | нет | только эта база |
| `limit`, `cursor` | нет | пагинация |

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$BASE/v1/subdomains?date_from=2026-09-15&date_to=2026-09-15&date_field=pipeline_started&limit=100"
```

Ключевые поля (есть в ответе): `subdomain`, ids, pipeline/*, `recrawl_sent_at` (из events), schedule, tld/pattern, content_label, brand/*, css + contrast_*, clicks/views sums, ref_link_*.

**Важно про `runtime_*`:** сейчас это **текущие** константы сервера на момент запроса, а не исторический снимок на `pipeline_started` (склад не меняли). `runtime_snapshot_at` = время старта пайплайна только как метка.

Поля `null` намеренно (нет в БД / дорого / вне scope):  
`job_*`, `webmaster_added_at`, `verified_at`, `recrawl_done_at`, `recrawl_wave`, `cf_email_domain`, `cf_cd_*`, `ya_*_seq` / age / hosts_before, pack_date/series, pages_count, brand_release_seq, clicks_7d/30d, …

---

### 2. `GET /v1/traffic`

**Одна строка = сабдомен × дата** (только дни с clicks+views > 0).

Параметры: `date_from`, `date_to`, опц. `subdomain`, `limit`, `cursor`.

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$BASE/v1/traffic?date_from=2026-09-15&date_to=2026-09-16&limit=500"
```

Поля: `subdomain`, `date`, `clicks`, `views`, `country_mix` (из `referral_click_logs`, ключ `null` если страна пустая).

---

### 3. `GET /v1/events`

Сырые события пайплайна, смапленные в enum спеки.

Параметры: `date_from`, `date_to`, опц. `content_domain_id`, `subdomain`, `limit`, `cursor`.

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$BASE/v1/events?date_from=2026-09-16&date_to=2026-09-16&limit=500"
```

| stage/status в БД | `event` в API |
|-------------------|---------------|
| add/success | `host_added` |
| verify/started | `verify_started` |
| verify/success | `verify_ok` |
| verify/failed\|error | `verify_failed` |
| meta/success | `meta_set` |
| recrawl/success | `recrawl_sent` |
| recrawl/quota | `quota_hit` |
| hosts_purge/success | `hosts_purge` |
| */error (прочие) | `error` |

Прочие stage (pipeline/schedule/…) **не отдаются**.  
`subdomain` может быть `null`, если событие без `domain_id` (уровень базы).

---

### 4. `GET /v1/globals`

Текущий снимок констант (не журнал истории).

```bash
curl -sS -H "Authorization: Bearer $TOKEN" \
  "$BASE/v1/globals?on=2026-09-15"
```

Ответ — один объект (не `data[]`). Поле `_note` напоминает про «current, not historical».

---

## Недоступно в v1 (намеренно)

| Эндпоинт / данные | Почему |
|-------------------|--------|
| `/v1/clicks`, `/v1/conversions` | нет clickid-level склада в engine |
| `/v1/botlog`, `/v1/botlog/raw` | нет разобранного access-log хранилища; отдельная фаза |
| Исторический `runtime_*` на момент старта | не пишем snapshot в БД |
| Данные после hard-purge soft-delete | логику удаления не меняли |

---

## Рекомендации потребителю

1. Для аналитики «запуск» берите `date_field=pipeline_started`.  
2. Полное окно ≥6 дней от `recrawl_sent_at` фильтруйте **у себя** (условие 4 спеки).  
3. Не тяните `limit=1000` параллельно десятками воркеров — упрётесь в 429 и нагрузку MySQL.  
4. Секреты (CF keys и т.п.) API не отдаёт.

---

## Быстрая проверка

```bash
export BASE='https://YOUR_HOST'
export TOKEN='…from app_local…'

curl -sS -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer $TOKEN" "$BASE/v1/globals?on=2026-09-15"
# ожидаем 200

curl -sS -H "Authorization: Bearer bad" "$BASE/v1/globals?on=2026-09-15"
# ожидаем 401 unauthorized
```
