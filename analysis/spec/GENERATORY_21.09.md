# Отдача по генераторам, с поправкой на зону

Правило: разные названия — разные генераторы; меняются только числа —
генератор один; внутри генератора есть варианты (с датой и без, оформление,
картинки).

Замечание про зону принято: генератор мог выглядеть хорошим просто потому, что
его ставили в удачную зону. Поэтому ниже сперва состав зон у каждого
генератора, потом сравнение **внутри одной зоны**, и только на нём строятся
выводы.

Метрика — регистрации в окне трёх суток на сто сайтов. Рядом отдача с клика,
чтобы различать «плохо доходит до поиска» и «плохо конвертит».

---

## Кто в каком генераторе

**NEW** — 343 базы, 70 649 сайтов, 38 наборов:
NEW102оформленобездаты, NEW102оформленосдатой, NEW17_NOimg_withdate_26.08,
NEW17_img_withdate_26.08, NEW20_12pages_nodate_styled_img,
NEW20_12pages_nodate_оформлено, NEW20_12pages_withdate_styled_img,
NEW20_12pages_withdate_оформлено, NEW20_3_12pages_nodate_styled_img,
NEW20_3_12pages_withdate_styled_img, NEW20_3_7pages_nodate_styled_img,
NEW20_3_7pages_withdate_styled_img, NEW20_4_12pages_nodate,
NEW20_4_12pages_withdate, NEW20_4_7pages_nodate, NEW20_4_7pages_withdate,
NEW20_7pages_nodate_styled_img, NEW20_7pages_nodate_оформлено,
NEW20_7pages_withdate_styled_img, NEW20_7pages_withdate_оформлено,
NEW21_12pages_nodate_styled_img, NEW21_12pages_withdate_styled_img,
NEW21_7pages_nodate_styled_img, NEW21_7pages_withdate_styled_img,
NEW33_12pages_nodate+img_25.08, NEW33_12pages_withdate+img_25.08,
NEW33_12pages_withdate_25.08, NEW50_12pages_nodate_01.09,
NEW50_12pages_withdate_01.09, NEW50_2_12pages_nodate_02.09,
NEW50_2_12pages_withdate_02.09, NEW50_2_7pages_withdate,
NEW50_3_12pages_nodate_styled, NEW50_3_12pages_withdate_styled,
NEW50_3_7pages_nodate_styled, NEW50_3_7pages_withdate_styled,
NEW50_7pages_nodate_01.09, NEW50_7pages_withdate_01.09.

**content** — 698 баз, 137 848 сайтов, 21 набор:
content-2026-09-12-12str-oform, content-2026-09-12-7str-oform,
content-2026-09-14-12str-oform, content-2026-09-14-7str-oform-1,
content-2026-09-14-7str-oform-8, content-2026-09-14-7str-oform-9,
content-2026-09-14b-7str-oform-1, content-2026-09-14b-7str-oform-2,
content-2026-09-14c-12str-oform, content-2026-09-14c-7str-oform-1,
content-2026-09-14c-7str-oform-2, content-2026-09-15-12str-oform,
content-2026-09-15-7str-oform-1, content-2026-09-15-7str-oform-2,
content-2026-09-16-12str, content-2026-09-16-7str,
content-2026-09-17-12str-oform, content-2026-09-17-7str-oform-1,
content-2026-09-17-7str-oform-2, content-2026-09-17b-7str-oform,
content-2026-09-19-12str.

**nabory** — 266 баз, 53 871 сайт, 35 наборов:
nabory-490-494_styled_img … nabory-660 (пачки по номерам),
nabory264268_01.09, nabory274283, nabory284293, nabory294303,
nabory400410_styled_img, nabory411420_styled_img, nabory421425_styled_img,
nabory431435_styled_img, nabory436440_styled_img, nabory441443_styled_img,
nabory447451_styled_img, nabory455457_styled_img, nabory461463_styled_img,
nabory464466, nabory470472_styled_img, nabory481483_styled_img_dark,
nabory484486_styled_img.

**archive** — 211 баз, 43 463 сайта, 6 наборов:
archive37строформленоv2часть1, archive37строформленоv2часть2,
archive37строформленоv2часть3, archive412_unique12оформлено,
archive47_unique119оформленочасть1, archive47_unique119оформленочасть2.

**Generator** — 66 баз, 13 595 сайтов, 9 наборов:
Generator_11page_NOimg_25.08, Generator_11page_img_25.08,
Generator_346353_styled_img, Generator_354359_styled_img,
Generator_368369_styled_img, Generator_370382_styled_img,
Generator_385390_styled_img, Generator_392396_styled_img,
ТЕСТ B Generator_11page_NOimg_24.08.

**clean** — clean12_unique11оформлено, clean7_part1_50оформлено.
**Выдача** — Выдача_06.09_12стр, Выдача_06.09_7стр.
**Одиночки:** Generator_11page_test_1…_9 (dorgen com),
Content_script_12page_08.09, script_yandex_12page,
КОНТРОЛЬ NEW50_5_7pages_nodate_21.08, struktura8x7.

Полный список — `analysis/export/generatory_21.09.txt`.

---

## Замечание про зону подтвердилось наполовину

Зоны у генераторов распределены очень неравномерно:

| генератор | сайтов | зоны |
|---|---|---|
| Generator (dorgen com) | 1 854 | `.team` 100% |
| struktura8x7 | 1 648 | `.team` 100% |
| Generator | 13 595 | `.team` 92%, `.lol` 8% |
| КОНТРОЛЬ NEW | 3 707 | `.team` 89%, `.lol` 11% |
| контент не записан | 66 990 | `.team` 77%, `.lol` 13% |
| **NEW** | 70 649 | `.team` 56%, `.lol` 23%, `.casino` 20% |
| clean | 12 566 | `.team` 51%, `.lol` 41%, `.casino` 8% |
| **content** | 137 848 | `.lol` 51%, `.team` 48% |
| **nabory** | 53 871 | `.lol` 51%, `.team` 46% |
| **archive** | 43 463 | `.lol` 44%, `.team` 28%, **`.buzz` 25%** |
| Content script | 2 266 | `.lol` 64%, `.team` 36% |
| script_yandex | 4 326 | `.casino` 76%, `.team` 19% |

`archive` на четверть сидит в `.buzz` — худшей зоне сети. `script_yandex` на
три четверти в `.casino`. `Generator` почти целиком в `.team`.

## Сравнение внутри зоны

### `.team`

| генератор | сайтов | рег | ФД | рег на 100 | рег на 10 тыс. кликов |
|---|---|---|---|---|---|
| Generator (dorgen com) | 1 854 | 8 | 0 | 0.431 | 1.4 |
| контент не записан | 51 423 | 89 | 8 | 0.173 | 1.6 |
| **NEW** | 39 750 | 59 | 12 | **0.148** | 2.6 |
| clean | 6 386 | 8 | 1 | 0.125 | 3.5 |
| КОНТРОЛЬ NEW | 3 295 | 4 | 1 | 0.121 | 0.9 |
| **content** | 66 803 | 58 | 11 | **0.087** | 2.4 |
| Generator | 12 565 | 6 | 0 | 0.048 | 1.2 |
| **nabory** | 24 754 | 6 | 2 | **0.024** | 1.3 |
| **archive** | 12 153 | 2 | 1 | **0.016** | 1.3 |
| struktura8x7 | 1 648 | 0 | 0 | 0.000 | 0.0 |

### `.lol`

| генератор | сайтов | рег | ФД | рег на 100 | рег на 10 тыс. кликов |
|---|---|---|---|---|---|
| **NEW** | 16 479 | 24 | 3 | **0.146** | 3.3 |
| **archive** | 19 157 | 21 | 4 | **0.110** | **5.2** |
| контент не записан | 8 644 | 8 | 0 | 0.093 | 1.9 |
| **content** | 70 221 | 31 | 8 | **0.044** | 1.8 |
| clean | 5 150 | 2 | 1 | 0.039 | 1.8 |
| **nabory** | 27 699 | 10 | 1 | **0.036** | 1.5 |

### `.casino`

| генератор | сайтов | рег | ФД | рег на 100 | рег на 10 тыс. кликов |
|---|---|---|---|---|---|
| **NEW** | 14 420 | 21 | 6 | **0.146** | 2.2 |
| script_yandex | 3 296 | 0 | 0 | 0.000 | 0.0 |

---

## Что зона объясняет, а что нет

**`NEW` — зона ни при чём.** 0.148 в `.team`, 0.146 в `.lol`, 0.146 в
`.casino`. Три зоны, одна цифра до третьего знака. Такой устойчивости больше
нет ни у кого, и это сильный довод, что генератор — настоящая причина, а не
метка.

**`nabory` — зона ни при чём.** 0.024 в `.team`, 0.036 в `.lol`. Плох в обеих.
Разрыв с `NEW` внутри зоны шестикратный в `.team` и четырёхкратный в `.lol` —
больше, чем общий разрыв 4.6, который я приводил раньше. Вывод не смягчился,
а усилился.

**`archive` — зона решает почти всё.** 0.016 в `.team` против 0.110 в `.lol` —
семикратная разница. Общая цифра 0.069 была средним двух несравнимых половин,
и мой вывод «archive плохо индексируется, но отлично конвертит» держался на
этом смешении. Правда в другом: **в `.lol` archive второй после NEW и даёт
лучшую в сети отдачу с клика — 5.2.** В `.team` он мёртв.

**`content` — зона решает половину.** 0.087 в `.team` против 0.044 в `.lol`,
вдвое. При этом `content` наполовину сидит в `.lol`. Значит его общая слабость
(0.065) — отчасти зона, отчасти он сам: даже в `.team` он вдвое хуже `NEW`.

**`Generator` и `script_yandex` судить нельзя.** Первый на 92% в `.team` и там
даёт 0.048, второй на 76% в `.casino` и там ноль на 3296 сайтах. Сравнить их с
остальными вне их зоны не на чем.

---

## Исправленные выводы

| что делать | прирост | на чём держится |
|---|---|---|
| **перевести `nabory` на `NEW`** | +62 рег (+16%) | разрыв 6× в `.team` и 4× в `.lol`, внутри зоны |
| **`archive` перенести из `.team` в `.lol`** | +11 рег | 0.016 против 0.110, те же 12 тыс. сайтов |
| **`content` в `.team` вместо `.lol`** | +30 рег (+8%) | 0.087 против 0.044 на 70 тыс. сайтов |
| у `content` перейти на второе оформление | +42 рег (+11%) | 39 тыс. против 88 тыс. сайтов, не проверено внутри зоны |

Что снимаю: вывод «`archive` — самый большой неиспользованный запас, потому
что у него лучшая отдача с клика». Отдача с клика 3.8 была средним по двум
зонам; в `.team`, где он на 28%, она 1.3. Запас есть, но он в переносе зоны,
а не в разгадке индексации.

Оговорка ко всем числам: регистраций в отдельных клетках — 2, 6, 8, 10. Порядок
величины надёжен, второй знак нет. И перенос объёма считает, что ставка
принимающей группы сохранится, — это допущение.
