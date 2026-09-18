#!/usr/bin/env python3
"""Кто кликает: страна, какой именно поиск, флаг бота — по базам.

Три поля выгрузки кликов не использовались ни разу: `country`, хост в `referer`
и `is_bot`. Между тем это единственное, чем мы вообще можем отличить живого
человека из нашей аудитории от чужого рынка, бота и накрутки — вопрос, который
был задан прямо: «мы не знаем, это боты, люди, яндекс-боты или ддос».

Ключевое различение — **какой именно Яндекс**. Клик с `yandex.com.tr` или
`yandex.kz` приходит с другого рынка: он такой же «поисковый», но нашей
аудиторией не является и конвертировать не может.

    python3 kto_klikaet.py <карта.jsonl> <выход.json> <clicks.jsonl> [ещё...]
"""
import sys, json, collections, re

HOST = re.compile(r'^https?://([^/]+)')


def ya_class(ref):
    """Класс источника: по хосту реферера, а не по подстроке 'yandex'."""
    if not ref:
        return 'нет реферера'
    m = HOST.match(ref)
    h = (m.group(1) if m else '').lower().lstrip('www.')
    if h in ('ya.ru', 'yandex.ru'):
        return 'яндекс RU'
    if h.startswith('yandex.'):
        return 'яндекс ' + h.split('.', 1)[1].upper()
    if 'google.' in h:
        return 'гугл'
    return 'свой сайт' if h.count('.') >= 2 else 'прочее'


def main(map_path, out_path, clicks):
    base = {}
    for line in open(map_path, encoding='utf-8'):
        r = json.loads(line)
        base[r[0]] = r[1]

    per = collections.defaultdict(lambda: collections.Counter())
    tot = collections.Counter()
    ids = {}
    seen = 0
    for p in clicks:
        with open(p, encoding='utf-8') as f:
            for line in f:
                r = json.loads(line)
                s = (r.get('subdomain') or '').lower()
                b = base.get(s)
                if b is None:
                    continue
                seen += 1
                k = ya_class(r.get('referer'))
                c = (r.get('country') or '—')
                bot = bool(r.get('is_bot'))
                per[b][k] += 1
                per[b]['страна ' + c] += 1
                per[b]['бот' if bot else 'не бот'] += 1
                tot[k] += 1
                tot['страна ' + c] += 1
                tot['бот' if bot else 'не бот'] += 1
                if k.startswith('яндекс'):
                    tot['яндекс×' + c] += 1
                    if bot:
                        tot['яндекс-бот×' + c] += 1
                ids[r['clickid']] = (k, c, bot)
        print(f'  {p}: {seen} наших кликов', flush=True)

    json.dump({'per_base': {b: dict(v) for b, v in per.items()},
               'total': dict(tot)},
              open(out_path, 'w', encoding='utf-8'), ensure_ascii=False)
    json.dump({k: v for k, v in ids.items()},
              open(out_path.replace('.json', '_ids.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    print(f'ГОТОВО: {seen} кликов по {len(per)} базам -> {out_path}')


if __name__ == '__main__':
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
