#!/usr/bin/env python3
"""Производные признаки для анализа индексации.

API отдаёт сырые id и таймстемпы, а выводимые из них поля (`ya_launch_seq`,
`ya_hosts_before`, `ya_account_age_days_at_start`, `cf_cd_seq`,
`brand_release_seq`, `recrawl_wave`) приходят пустыми — мануал прямо говорит,
что считать их нужно на своей стороне. Здесь они и считаются, по всей выгрузке
сразу, иначе «первый запуск на аккаунте» зависел бы от границ окна.

Главное из добавленного — **волна переобхода**. Квота Вебмастера 150 URL в
сутки, а сабдоменов в запуске 206: первые 150 уходят сразу, остальные ждут
следующих суток. На выгрузке это видно как разрыв больше часа ровно на 151-й
позиции — во всех проверенных базах без исключения.

    python3 enrich.py <панель.jsonl> <subdomains.jsonl>[,<subs2.jsonl>] <выход.jsonl>
"""
import sys, json, collections
from datetime import datetime

QUOTA = 150          # runtime_quota_per_day, тот же у всех строк выгрузки


def ts(x):
    return datetime.fromisoformat(x) if x else None


def main(panel_path, subs_paths, out_path):
    # 1. сырьё из выгрузки запусков: только то, что нужно для производных
    raw = {}
    for p in subs_paths:
        with open(p, encoding='utf-8') as f:
            for line in f:
                r = json.loads(line)
                raw[r['subdomain'].lower()] = (
                    r.get('content_domain_url'), r.get('recrawl_sent_at'),
                    r.get('ya_account_id'), r.get('cf_account_id'),
                    r.get('brand_id'), r.get('pipeline_started'))
    print(f"строк выгрузки: {len(raw)}")

    # 2. позиция внутри запуска и волна
    by_base = collections.defaultdict(list)
    for sub, (base, rc, *_rest) in raw.items():
        if base and rc:
            by_base[base].append((rc, sub))
    pos, wave = {}, {}
    for base, rows in by_base.items():
        rows.sort()
        for i, (_rc, sub) in enumerate(rows, 1):
            pos[sub] = i
            wave[sub] = 1 if i <= QUOTA else 2

    # 3. порядок запусков на аккаунте: считается по базам, не по сабдоменам
    def account_seq(idx):
        """idx: сабдомен -> id аккаунта. Возвращает seq и хосты-до на уровне базы."""
        firsts = {}          # (аккаунт, база) -> первый pipeline_started
        size = collections.Counter()
        for sub, (base, _rc, ya, cf, _b, ps) in raw.items():
            a = (ya if idx == 'ya' else cf)
            if a is None or base is None:
                continue
            k = (a, base)
            size[k] += 1
            if k not in firsts or (ps or '') < firsts[k]:
                firsts[k] = ps or ''
        per = collections.defaultdict(list)
        for (a, base), t in firsts.items():
            per[a].append((t, base))
        seq, before, gap = {}, {}, {}
        for a, lst in per.items():
            lst.sort()
            hosts = 0
            prev_t = None
            for i, (t, base) in enumerate(lst, 1):
                seq[(a, base)] = i
                before[(a, base)] = hosts
                gap[(a, base)] = ((ts(t) - ts(prev_t)).total_seconds() / 3600
                                  if prev_t and t else None)
                hosts += size[(a, base)]
                prev_t = t
        first_seen = {a: min(t for t, _ in lst) for a, lst in per.items()}
        return seq, before, gap, first_seen

    ya_seq, ya_before, ya_gap, ya_first = account_seq('ya')
    cf_seq, cf_before, cf_gap, _cf_first = account_seq('cf')

    # 4. бренд против себя во времени — единственное допустимое сравнение брендов
    brand_rows = collections.defaultdict(list)
    for sub, (_b, _rc, _ya, _cf, brand, ps) in raw.items():
        if brand is not None and ps:
            brand_rows[brand].append((ps, sub))
    brand_seq = {}
    for brand, lst in brand_rows.items():
        lst.sort()
        seen = {}
        n = 0
        for ps, sub in lst:
            day = ps[:10]
            if day not in seen:
                n += 1
                seen[day] = n
            brand_seq[sub] = seen[day]

    # 5. сколько баз стартовало в тот же день — нагрузка на квоту
    day_bases = collections.defaultdict(set)
    for sub, (base, _rc, _ya, _cf, _b, ps) in raw.items():
        if ps and base:
            day_bases[ps[:10]].add(base)
    day_load = {d: len(v) for d, v in day_bases.items()}

    n = out = 0
    with open(panel_path, encoding='utf-8') as f, open(out_path, 'w', encoding='utf-8') as w:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            n += 1
            sub = r['subdomain'].lower()
            src = raw.get(sub)
            base = r.get('content_domain_url')
            ya, cf, brand = (src[2], src[3], src[4]) if src else (None, None, None)
            r['recrawl_pos'] = pos.get(sub)
            r['recrawl_wave'] = wave.get(sub)
            r['ya_account_id'] = ya
            r['ya_launch_seq'] = ya_seq.get((ya, base))
            r['ya_hosts_before'] = ya_before.get((ya, base))
            r['ya_gap_h'] = ya_gap.get((ya, base))
            r['ya_account_age_h'] = (
                round((ts(r.get('pipeline_started')) - ts(ya_first[ya])).total_seconds() / 3600, 1)
                if ya in ya_first and r.get('pipeline_started') else None)
            r['cf_cd_seq'] = cf_seq.get((cf, base))
            r['cf_hosts_before'] = cf_before.get((cf, base))
            r['brand_release_seq'] = brand_seq.get(sub)
            r['day_load_bases'] = day_load.get((r.get('pipeline_started') or '')[:10])
            r['pipeline_h'] = (
                round((ts(r['pipeline_finished']) - ts(r['pipeline_started'])).total_seconds() / 3600, 2)
                if r.get('pipeline_finished') and r.get('pipeline_started') else None)
            w.write(json.dumps(r, ensure_ascii=False) + '\n')
            out += 1
    print(f"панель: {n} строк -> {out} обогащённых")
    print(f"  волна 2 (за квотой): {sum(1 for v in wave.values() if v == 2)} сабдоменов")
    print(f"  аккаунтов Вебмастера: {len(ya_first)}, CF-аккаунтов: {len({k[0] for k in cf_seq})}")
    print(f"-> {out_path}")


if __name__ == '__main__':
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2].split(','), sys.argv[3])
