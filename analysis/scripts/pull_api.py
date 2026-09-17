#!/usr/bin/env python3
"""Выгрузка из Analytics Export API системы запусков.

Токен и хост берутся из окружения, в файл не пишутся:
    export DORGEN_BASE='https://dorgen-engine.com'
    export DORGEN_TOKEN='...'

Примеры:
    python3 pull_api.py audit                      # одна страница, отчёт по полям
    python3 pull_api.py globals
    python3 pull_api.py subdomains 2026-09-10 2026-09-17
    python3 pull_api.py events     2026-09-16 2026-09-17
    python3 pull_api.py traffic    2026-09-10 2026-09-17

Кладёт JSONL в analysis/api/<endpoint>_<from>_<to>.jsonl
"""
import os, sys, json, time, urllib.request, urllib.error, urllib.parse
from datetime import date, timedelta

BASE  = os.environ.get('DORGEN_BASE', '').rstrip('/')
TOKEN = os.environ.get('DORGEN_TOKEN', '')
OUT   = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'api')
LIMIT      = 1000       # максимум по документации
MIN_GAP    = 2.1        # ~28 запросов в минуту, под лимитом 30
MAX_WINDOW = 31         # максимум дней на запрос

def _get(path, params, tries=5):
    """GET с паузой под rate limit и экспоненциальным откатом на 429/5xx."""
    url = f"{BASE}{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {TOKEN}',
        'Accept': 'application/json',
    })
    delay = 4
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors='replace')[:300]
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                print(f"  HTTP {e.code}, жду {delay}s  {body}", file=sys.stderr)
                time.sleep(delay); delay *= 2; continue
            raise SystemExit(f"HTTP {e.code} на {path}: {body}")
        except urllib.error.URLError as e:
            # сетевая ошибка повторяется дважды: блокировка политикой не «рассосётся»
            if attempt < min(tries, 3) - 1:
                print(f"  сеть: {e.reason}, жду {delay}s", file=sys.stderr)
                time.sleep(delay); delay *= 2; continue
            raise SystemExit(f"сеть недоступна: {e.reason}")

def pages(path, params):
    """Итератор по страницам курсорной пагинации."""
    p = dict(params, limit=LIMIT)
    n = 0
    while True:
        t0 = time.time()
        j = _get(path, p)
        rows = j.get('data', [])
        n += len(rows)
        yield rows
        cur = (j.get('meta') or {}).get('next_cursor')
        print(f"  +{len(rows):>5}  всего {n:>7}  cursor={'…' if cur else 'конец'}", file=sys.stderr)
        if not cur: return
        p = dict(params, limit=LIMIT, cursor=cur)
        time.sleep(max(0, MIN_GAP - (time.time() - t0)))

def chunks(d1, d2):
    """Режем окно на куски по 31 дню."""
    a = date.fromisoformat(d1); b = date.fromisoformat(d2)
    while a <= b:
        c = min(b, a + timedelta(days=MAX_WINDOW - 1))
        yield a.isoformat(), c.isoformat()
        a = c + timedelta(days=1)

def dump(ep, d1, d2, **extra):
    os.makedirs(OUT, exist_ok=True)
    fn = os.path.join(OUT, f"{ep}_{d1}_{d2}.jsonl")
    total = 0
    with open(fn, 'w') as f:
        for c1, c2 in chunks(d1, d2):
            print(f"{ep} {c1}..{c2}", file=sys.stderr)
            for rows in pages(f"/v1/{ep}", dict(date_from=c1, date_to=c2, **extra)):
                for r in rows:
                    f.write(json.dumps(r, ensure_ascii=False) + '\n'); total += 1
    print(f"-> {fn}  {total} строк")
    return fn

def audit():
    """Одна страница /v1/subdomains: какие поля приходят и что в них."""
    j = _get('/v1/subdomains', dict(date_from='2026-09-15', date_to='2026-09-15',
                                    date_field='pipeline_started', limit=50))
    rows = j.get('data', [])
    if not rows: raise SystemExit("пусто — нет строк за эту дату")
    keys = sorted({k for r in rows for k in r})
    print(f"строк в выборке: {len(rows)}, полей: {len(keys)}\n")
    NEED = {'brand_id':'износ бренда', 'ya_account_id':'нагруженность YA',
            'cloudflare_account_id':'номер базы на CF', 'recrawl_sent_at':'волны переобхода',
            'content_label':'контент как параметр', 'subdomain':'ключ соединения',
            'content_domain_id':'группировка по запуску', 'tld':'зона'}
    print(f"{'поле':<40}{'непустых':>10}  пример")
    for k in keys:
        vals = [r.get(k) for r in rows]
        nn = sum(1 for v in vals if v not in (None, '', [], {}))
        ex = next((v for v in vals if v not in (None, '', [], {})), None)
        mark = '  <- ' + NEED[k] if k in NEED else ''
        print(f"{k:<40}{nn:>4}/{len(rows):<5}  {str(ex)[:44]}{mark}")
    print("\nКРИТИЧНЫЕ ПОЛЯ:")
    for k, why in NEED.items():
        nn = sum(1 for r in rows if r.get(k) not in (None, '', [], {}))
        print(f"  {'ЕСТЬ ' if nn else 'НЕТ  '}{k:<26}{why}")

if __name__ == '__main__':
    if not BASE or not TOKEN:
        raise SystemExit("нужны переменные DORGEN_BASE и DORGEN_TOKEN")
    a = sys.argv[1:] or ['audit']
    if a[0] == 'audit':   audit()
    elif a[0] == 'globals':
        print(json.dumps(_get('/v1/globals', dict(on=a[1] if len(a) > 1 else str(date.today()))),
                         ensure_ascii=False, indent=1))
    elif a[0] in ('subdomains', 'traffic', 'events'):
        if len(a) < 3: raise SystemExit(f"использование: pull_api.py {a[0]} <date_from> <date_to>")
        extra = {'date_field': 'pipeline_started'} if a[0] == 'subdomains' else {}
        dump(a[0], a[1], a[2], **extra)
    else:
        raise SystemExit(__doc__)
