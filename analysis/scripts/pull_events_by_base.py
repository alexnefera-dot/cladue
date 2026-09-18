#!/usr/bin/env python3
"""Журнал пайплайна по базам — единственный способ получить его целиком.

`/v1/events` без фильтра обрывается на первых минутах суток и рапортует «конец»
(`AUDIT_API_17.09.md` §9), поэтому выборка списком получается смещённой: в неё
попадают только базы, чьи события пришлись на начало дня. С фильтром
`content_domain_id` день отдаётся полностью.

Выгрузка возобновляемая: уже выгруженные базы читаются из выходного файла и
пропускаются, так что повтор команды продолжает с места обрыва.

    python3 pull_events_by_base.py <панель.jsonl> <date_from> <date_to> [выход.jsonl]
"""
import os, sys, json, time, random, urllib.request, urllib.parse

BASE  = os.environ.get('DORGEN_BASE', '').rstrip('/')
TOKEN = os.environ.get('DORGEN_TOKEN', '')
GAP   = 2.1          # ~28 запросов в минуту при лимите 30
OUT   = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     '..', 'api', 'dorgen_events_by_base.jsonl')


def get(path, params, tries=8):
    url = f"{BASE}{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {TOKEN}', 'Accept': 'application/json',
        'User-Agent': 'cladue-analytics/1.0'})
    for i in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode())
        except Exception as e:
            if i == tries - 1:
                raise
            print(f"    {type(e).__name__}, попытка {i + 2}", file=sys.stderr, flush=True)
            time.sleep(3 + i * 2)


def main(panel, d1, d2, out=OUT):
    want = set()
    with open(panel, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                cd = json.loads(line).get('content_domain_id')
                if cd:
                    want.add(cd)
    done = set()
    if os.path.exists(out):
        with open(out, encoding='utf-8') as f:
            for line in f:
                try:
                    done.add(json.loads(line)['content_domain_id'])
                except (ValueError, KeyError):
                    pass
        # последняя база могла не досохраниться — перевыгружаем её
        done.discard(max(done) if done else None)
    # порядок перемешивается с фиксированным seed: id баз растут со временем, и
    # выгрузка по возрастанию id дала бы на любой промежуточной точке выборку,
    # смещённую по датам — ровно тот дефект, из-за которого эта выгрузка и
    # понадобилась. С перемешиванием любая точка остановки пригодна для счёта.
    todo = sorted(want - done)
    random.Random(20260918).shuffle(todo)
    print(f"баз всего {len(want)}, уже есть {len(done)}, к выгрузке {len(todo)} "
          f"(порядок перемешан)", flush=True)

    total = 0
    with open(out, 'a', encoding='utf-8') as w:
        for n, cd in enumerate(todo, 1):
            cur = None
            while True:
                p = dict(date_from=d1, date_to=d2, content_domain_id=cd, limit=1000)
                if cur:
                    p['cursor'] = cur
                j = get('/v1/events', p)
                for r in j.get('data', []):
                    w.write(json.dumps(r, ensure_ascii=False) + '\n')
                    total += 1
                cur = (j.get('meta') or {}).get('next_cursor')
                if not cur:
                    break
                time.sleep(GAP)
            w.flush(); os.fsync(w.fileno())
            if n % 25 == 0:
                print(f"  {n}/{len(todo)} баз, {total} событий в этом проходе", flush=True)
            time.sleep(GAP)
    print(f"ГОТОВО: {len(todo)} баз, {total} событий -> {os.path.normpath(out)}")


if __name__ == '__main__':
    if not BASE or not TOKEN:
        raise SystemExit("нужны DORGEN_BASE и DORGEN_TOKEN")
    if len(sys.argv) < 4:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2], sys.argv[3], *(sys.argv[4:5] or []))
