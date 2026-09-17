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

ВОЗОБНОВЛЕНИЕ. Аудит 17.09 намерял 50-75% ответов HTTP 500 на /v1/subdomains,
причём случайных: один и тот же запрос даёт 200, 200, 500, 500, 500. Длинная
выгрузка при таком фоне обрывается гарантированно, поэтому рядом с JSONL живёт
файл состояния <имя>.jsonl.state с курсором и длиной уже записанного.

    python3 pull_api.py subdomains 2026-09-10 2026-09-17   # оборвалось
    python3 pull_api.py subdomains 2026-09-10 2026-09-17   # та же команда — продолжит

Состояние пишется после каждой страницы и только после fsync самих данных, а при
старте файл обрезается ровно по записанной длине. Поэтому обрыв в любой момент —
хоть по Ctrl-C, хоть по питанию — не даёт ни дублей, ни битых строк. Успешная
выгрузка состояние удаляет, так что повтор команды начнёт её заново.
    DORGEN_TRIES=N   — попыток на страницу (по умолчанию 15)
"""
import os, sys, json, time, random, urllib.request, urllib.error, urllib.parse
from datetime import date, timedelta

BASE  = os.environ.get('DORGEN_BASE', '').rstrip('/')
TOKEN = os.environ.get('DORGEN_TOKEN', '')
OUT   = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'api')
LIMIT      = 1000       # максимум по документации
MIN_GAP    = 2.1        # ~28 запросов в минуту, под лимитом 30
MAX_WINDOW = 31         # максимум дней на запрос
TRIES      = int(os.environ.get('DORGEN_TRIES', '15'))

STATS = {'ok': 0, 'err_5xx': 0, 'err_429': 0}


class ApiError(Exception):
    """Страница не взялась за отведённое число попыток."""


def _get(path, params):
    """GET с повтором.

    5xx на этом API случайны и независимы — их повторяем коротко и часто:
    длинный откат тут только теряет время. 429 наоборот означает реальный лимит, по нему
    экспоненциальный откат.
    """
    url = f"{BASE}{path}?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={
        'Authorization': f'Bearer {TOKEN}',
        'Accept': 'application/json',
    })
    slow = 5                                    # откат под 429
    for attempt in range(TRIES):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                STATS['ok'] += 1
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors='replace')[:200]
            last = attempt == TRIES - 1
            if e.code == 429 and not last:
                STATS['err_429'] += 1
                print(f"    429, жду {slow}s", file=sys.stderr)
                time.sleep(slow); slow = min(slow * 2, 120); continue
            if e.code in (500, 502, 503, 504) and not last:
                STATS['err_5xx'] += 1
                d = min(2 + attempt, 8) + random.uniform(0, 0.5)
                print(f"    {e.code} ({attempt + 1}/{TRIES}), жду {d:.1f}s", file=sys.stderr)
                time.sleep(d); continue
            raise ApiError(f"HTTP {e.code} на {path}: {body}")
        except urllib.error.URLError as e:
            # сетевая ошибка повторяется дважды: блокировка политикой не «рассосётся»
            if attempt < 2:
                print(f"    сеть: {e.reason}, жду 4s", file=sys.stderr)
                time.sleep(4); continue
            raise ApiError(f"сеть недоступна: {e.reason}")
    raise ApiError(f"{TRIES} попыток подряд неудачны на {path}")


def chunks(d1, d2):
    """Режем окно на куски по 31 дню."""
    a = date.fromisoformat(d1); b = date.fromisoformat(d2)
    while a <= b:
        c = min(b, a + timedelta(days=MAX_WINDOW - 1))
        yield a.isoformat(), c.isoformat()
        a = c + timedelta(days=1)


def _load_state(fn, key):
    """Состояние прошлого прогона, если оно от этой же команды и файл на месте."""
    p = fn + '.state'
    if not (os.path.exists(p) and os.path.exists(fn)):
        return None
    try:
        st = json.load(open(p, encoding='utf-8'))
    except (ValueError, OSError):
        return None
    if st.get('key') != key:
        print("состояние рядом — от другой команды, начинаю заново", file=sys.stderr)
        return None
    return st


def _save_state(fn, st):
    """Атомарно: чтобы обрыв на самой записи состояния не оставил огрызок."""
    p = fn + '.state'; tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(st, f, ensure_ascii=False)
        f.flush(); os.fsync(f.fileno())
    os.replace(tmp, p)


def dump(ep, d1, d2, **extra):
    if date.fromisoformat(d1) > date.fromisoformat(d2):
        raise SystemExit(f"окно пустое: {d1} позже {d2}")
    os.makedirs(OUT, exist_ok=True)
    fn  = os.path.join(OUT, f"{ep}_{d1}_{d2}.jsonl")
    key = json.dumps([ep, d1, d2, extra, LIMIT], sort_keys=True, ensure_ascii=False)
    win = list(chunks(d1, d2))

    st = _load_state(fn, key)
    if st:
        print(f"возобновляю {fn}: кусок {st['chunk'] + 1}/{len(win)}, "
              f"{st['total']} строк уже на диске", file=sys.stderr)
        f = open(fn, 'r+b')
    else:
        st = {'key': key, 'chunk': 0, 'cursor': None, 'offset': 0, 'total': 0}
        f = open(fn, 'w+b')
    # обрезаем хвост, который мог не досохраниться в момент обрыва
    f.truncate(st['offset']); f.seek(st['offset'])

    try:
        while st['chunk'] < len(win):
            c1, c2 = win[st['chunk']]
            if st['cursor'] is None:
                print(f"{ep} {c1}..{c2}", file=sys.stderr)
            p = dict(extra, date_from=c1, date_to=c2, limit=LIMIT)
            if st['cursor']:
                p['cursor'] = st['cursor']

            t0 = time.time()
            j = _get(f"/v1/{ep}", p)
            rows = j.get('data', [])
            for r in rows:
                f.write((json.dumps(r, ensure_ascii=False) + '\n').encode())
            f.flush(); os.fsync(f.fileno())

            # порядок важен: данные на диске, только потом состояние
            st['total'] += len(rows)
            st['offset'] = f.tell()
            cur = (j.get('meta') or {}).get('next_cursor')
            st['cursor'] = cur
            if not cur:
                st['chunk'] += 1
                st['cursor'] = None
            _save_state(fn, st)

            print(f"  +{len(rows):>5}  всего {st['total']:>7}  "
                  f"cursor={'…' if cur else 'конец'}", file=sys.stderr)
            if st['chunk'] < len(win):
                time.sleep(max(0, MIN_GAP - (time.time() - t0)))
    except (ApiError, KeyboardInterrupt) as e:
        f.close()
        print(f"\nПРЕРВАНО: {e}", file=sys.stderr)
        print(f"{st['total']} строк сохранено в {fn}.", file=sys.stderr)
        print("Повторите ту же команду — продолжу с этого места.", file=sys.stderr)
        raise SystemExit(2)
    f.close()
    if os.path.exists(fn + '.state'):
        os.remove(fn + '.state')    # выгрузка целая, возобновлять нечего

    print(f"-> {fn}  {st['total']} строк")
    print(f"   запросов удачных {STATS['ok']}, повторов по 5xx {STATS['err_5xx']}, "
          f"по 429 {STATS['err_429']}", file=sys.stderr)
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
            'cf_account_id':'номер базы на CF', 'recrawl_sent_at':'волны переобхода',
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
    try:
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
    except ApiError as e:
        raise SystemExit(str(e))
