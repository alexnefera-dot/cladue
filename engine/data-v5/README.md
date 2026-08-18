# Профиль v5 и выкладки разбора

Разбор корпуса `samples/v5-donors` (38 комплектов, 37 уникальных). Выводы —
`docs/v5-korpus.md`, изменения к рабочему циклу — `HANDOFF.md`, раздел 13.

| файл | что это |
|---|---|
| `profil-v5.json` | приёмочный профиль: 55 полей × 7 типов, полосы, граф, бренд, разметка |
| `profil-v5-tekst.json` | писаная часть профиля — запреты, структура, приёмы, семёрка |
| `pokoleniya/<тип>.txt` | август против нового корпуса, `sravnit-pokoleniya.php` |
| `razbor/korpus*.txt` | инвентарь, блоки, schema.org, сетка ссылок, подстановки |
| `razbor/zhanr*.txt` | жанр: зачин, финал, заголовок, ритм, FAQ, тон, граф |
| `razbor/seo*.txt` | техническая мерка по `SeoMetrics` |
| `razbor/priyomy.txt` | приёмы на 1000 слов: новый корпус, август, наш `v4-final` |

## Пересборка

```bash
php engine/build-profil-v5.php samples/v5-donors engine/data-v5/profil-v5.json \
    --текст=engine/data-v5/profil-v5-tekst.json

# промежуточные выкладки разброса (в репозиторий не кладутся — секунды работы)
for t in main app bonus registracia slots vhod zerkalo; do
  php engine/razbros-korpusa.php samples/v5-donors $t --json > /tmp/v5-$t.json
  php engine/razbros-korpusa.php samples/v4-donors $t --json > /tmp/v4-$t.json
  php engine/sravnit-pokoleniya.php /tmp/v4-$t.json /tmp/v5-$t.json > engine/data-v5/pokoleniya/$t.txt
done
```

Проверка сборщика: на августовском корпусе он обязан воспроизвести
`data-v4/profil-avgust.json` дословно.

```bash
php engine/build-profil-v5.php samples/v4-donors /tmp/avgust.json --школа=проза
```
