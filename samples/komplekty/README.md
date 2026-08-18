# Готовые комплекты (тестовые прогоны)

Комплекты по 7 страниц (`main`, `zerkalo`, `vhod`, `registracia`, `bonus`,
`slots`, `app`), собранные из корпуса и доведённые одним проходом verify-loop.
Бренд/домен/дата — переменные `%brand_name_ru%` / `%brand_name_en%` /
`%domain_name%` / `%date%` (подставляются при выпуске).

| Папка | Донор | Регистр | Совпадение с конкурентом |
|---|---|---|---|
| `monro-seed2/` | monro | экспертный, «я» | 84% |
| `derzkiy-cosmospin/` | cosmospin | дерзкий, «ты», сленг | 84% |

Первый экспертный комплект (тот же донор monro, другой seed) лежит в
`../monro-vs-donor/p1/`. `monro-seed2` и он взаимно уникальны на 99.5%
(пересечение текста 0–0.6%) — один шаблон даёт поток неповторяющегося
контента.

Проверить любой комплект против его донора:

```bash
php engine/compare-vs-donor.php samples/komplekty/derzkiy-cosmospin cosmospin /tmp/report.html
```

Отчёты: `reports/komplekt-monro-seed2.html`, `reports/komplekt-derzkiy.html`.
