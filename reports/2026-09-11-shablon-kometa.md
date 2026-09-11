# Подготовка шаблона: Archive.zip (выкачка kometa.1109d.casino)

Найдено в страницах: домен `kometa.1109d.casino`, бренд «Комета» / `Kometa`, папка картинок `kometa`, счётчик метрики `112434350`.

## Замены

| Что | Замен |
|---|---:|
| бренд (рус) | 5140 |
| домен | 2079 |
| даты | 1716 |
| папка картинок | 513 |
| бренд (лат) | 389 |
| путь /ru/ru/… | 312 |
| ссылки без домена | 172 |
| метрика снята | 120 |
| счётчик метрики | 48 |
| картинки слотов | 30 |
| карта сайта | 14 |

## По страницам

| Страница | Замен | Осталось от чужого |
|---|---:|---:|
| app.html | 949 | 0 |
| bonus.html | 966 | 0 |
| info.html | 949 | 0 |
| main.html | 214 | 0 |
| news.html | 928 | 0 |
| obzor.html | 926 | 0 |
| partnery.html | 916 | 0 |
| promo.html | 927 | 0 |
| registracia.html | 943 | 0 |
| slots.html | 935 | 0 |
| vhod.html | 930 | 0 |
| zerkalo.html | 950 | 0 |

## Ссылки на чужие домены

- `fonts.googleapis.com` — 96
- `fonts.gstatic.com` — 36
- `www.google-analytics.com` — 12
- `www.googletagmanager.com` — 12
- `t.me` — 12

## Ссылки не на страницы набора

- `/igrat` — 68
- `/online` — 42
- `/styles.php` — 36
- `//fonts.googleapis.com` — 24
- `/htmlmap` — 13
- `//www.googletagmanager.com` — 12
- `//yandex.ru` — 12
- `//www.googleadservices.com` — 12
- `//fonts.gstatic.com` — 12
- `//www.google-analytics.com` — 12
- `/tableau.json` — 12
- `/rss.xml` — 12
- `/atom.xml` — 12
- `/xmlrpc.php` — 12
- `/manifest.json` — 12
- `/reviews` — 2
- `/en/app/` — 1
- `/en/bonus/` — 1
- `/en/info/` — 1
- `/en/` — 1

## Файлы движка, которые просят страницы

- `styles.php`
- `manifest.json`
- `rss.xml`
- `atom.xml`
- `tableau.json`
- `xmlrpc.php`
- `search`

## Сплошная проверка всех 12 страниц

Следов чужого проекта не осталось: домена, бренда, счётчика, `mc.yandex`, вызова `ym(`, путей `/ru/ru`,
`/slots/NN.jpg`, `htmlmap.html`, относительных путей выкачки и дат с числом — ноль на всех страницах.

Отдельно попался склеенный адрес `https://1109d.casinoslots/23.jpg` (9 штук в `app`, `bonus`, `zerkalo`):
выкачка слепила домен площадки с путём без слэша, поэтому обычная замена домена его не видела.
Правило добавлено: абсолютный адрес, оканчивающийся на `slots/NN.jpg`, переносится в папку картинок.

Ссылки на `/registracia` и `/vhod` оставлены как были — это обычные страницы набора: 391 кнопка,
из них 133 с utm-хвостом. Домен из них снят общим правилом, как из остальных внутренних ссылок.

Переменные разошлись по всем 12 страницам: `%domain_name%` — 2127, `%brand_name_ru%` — 5628,
`%brand_name_en%` — 435, `%directory_img%` — 590, `%date%` — 1716.

## Что осталось разработчику

| Что | Сколько | Где |
|---|---:|---|
| ссылки на `/igrat` | 68 | все страницы |
| ссылки на `/online` | 42 | все, кроме `slots` |
| ссылки на `/reviews` | 2 | `obzor` |
| заглушки `your_…_verification_code` | 24 | по 2 на страницу |
| `dns-prefetch` на рекламные сети (yandex.ru, googleadservices, googletagmanager, google-analytics) | 60 | по 5 на страницу |
| вызов `gtag(` без подключённого счётчика | 12 | по 1 на страницу |
| пустой `https://vk.com/` в `sameAs` | 24 | по 2 на страницу |
| `styles.php` и прочие файлы движка | 36 | по 3 на страницу |

- `hreflang` со слэшем на конце, `canonical` без — расходятся на всех 11 внутренних страницах.
- У событий `startDate` и `endDate` после подстановки дат совпадают: если движок умеет сдвиг, конец сдвинуть на длину акции.

Даты с числом заменены на `%date%` (1716 штук): `datePublished`, `dateModified`, `startDate`, `endDate`,
`uploadDate`, `priceValidUntil`, `validFrom`, `validThrough`, `og:updated_time`, `article:published_time`,
`article:modified_time`, `DC.date` и одна дата в тексте новостей. Год основания `2020` без числа оставлен.
