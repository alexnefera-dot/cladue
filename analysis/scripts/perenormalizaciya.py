#!/usr/bin/env python3
"""Пересборка поля `content` в панели после починки нормализатора имён.

Две ошибки в `panel.py` оставляли базы без пака при живом заголовке в журнале:

1. `content_by_domain()` писал `out[d] = (name, day)` без условия. Один домен
   встречается и в недельном файле журнала, и в общем; пустое имя из одного
   затирало настоящее имя из другого.
2. `_norm_content()` срезал дату вместе с номером экземпляра, склеивая
   `..._24.08` и `..._25.08` в одно имя, и пропускал баннеры секций
   («ЗАПУСКИ 24.08.2026 — 42 домена») как имена паков.

Здесь панель переписывается с исправленной картой, без перевыгрузки данных:
`content` = метка API, иначе имя из журнала.

    python3 perenormalizaciya.py <старая-панель.jsonl> <новая-панель.jsonl>
"""
import sys, os, json, collections, importlib.util

SCRIPTS = os.path.dirname(os.path.abspath(__file__))


def load_panel_module():
    spec = importlib.util.spec_from_file_location('panelmod', os.path.join(SCRIPTS, 'panel.py'))
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except SystemExit:
        pass
    return m


def main(old, new):
    reg = load_panel_module().content_by_domain()
    named = sum(1 for v in reg.values() if v[0])
    print('доменов в журнале: %d, из них с разобранным именем: %d' % (len(reg), named))

    ch = collections.Counter()
    base_before, base_after = {}, {}
    with open(old, encoding='utf-8') as fi, open(new, 'w', encoding='utf-8') as fo:
        for line in fi:
            r = json.loads(line)
            b = r.get('content_domain_url')
            before = r.get('content')
            name = reg.get(b, (None, None))[0]
            after = r.get('content_label') or name
            r['content'] = after
            fo.write(json.dumps(r, ensure_ascii=False) + '\n')
            if b:
                base_before.setdefault(b, before)
                base_after.setdefault(b, after)
            if before == after:
                ch['без изменений'] += 1
            elif before is None:
                ch['появилось имя'] += 1
            elif after is None:
                ch['имя пропало'] += 1
            else:
                ch['имя изменилось'] += 1
    print('сайтов:', dict(ch))

    gained = [b for b in base_after if base_before[b] is None and base_after[b] is not None]
    lost = [b for b in base_after if base_before[b] is not None and base_after[b] is None]
    renamed = [b for b in base_after
               if base_before[b] and base_after[b] and base_before[b] != base_after[b]]
    print('баз без имени было: %d, стало: %d'
          % (sum(1 for b in base_before if base_before[b] is None),
             sum(1 for b in base_after if base_after[b] is None)))
    print('  получили имя: %d, потеряли: %d, переименованы: %d'
          % (len(gained), len(lost), len(renamed)))
    if gained:
        c = collections.Counter(base_after[b] for b in gained)
        print('  новые имена:')
        for k, n in c.most_common(20):
            print('    %-46s %3d баз' % (str(k)[:45], n))
    if renamed:
        c = collections.Counter((base_before[b], base_after[b]) for b in renamed)
        print('  переименования:')
        for (a, z), n in c.most_common(20):
            print('    %-34s -> %-34s %3d баз' % (str(a)[:33], str(z)[:33], n))


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
