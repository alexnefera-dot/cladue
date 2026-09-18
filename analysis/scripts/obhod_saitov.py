#!/usr/bin/env python3
"""Обход своих сайтов — шаг 2 плана `KAK_MERIT_KONTENT.md`.

Про контент в API нет ни одного признака: `content_label`, `pages_count`,
`page_url_set`, `page_body_len`, `h1_len`, `title_ru_len`, `spintax_branch_count`
пусты у 100% строк. Поэтому лучший и худший пак в рейтинге называются почти
одинаково, и «почему» сказать нечем. Признаки берутся с самих сайтов — они наши,
и ничего, кроме времени, обход не стоит.

Что собирается с каждого сабдомена:

    код ответа, время ответа, редиректы   — жив ли сайт на момент замера
    title, h1, длина текста               — чем отличаются удачные паки
    число внутренних ссылок и страниц     — совпадает ли с «12» в имени
    hreflang, глубина /ru/ru/…            — инфраструктурный отпечаток
    хеш текста главной и внутренних       — самоповтор пака и переиспользование
    robots.txt, sitemap.xml               — одинаковы ли на всей сети

Вежливость. Вся сеть живёт на одном сервере (`87.199.206.213`), поэтому у обхода
общий предел скорости, а не только параллельность: RATE запросов в секунду на
весь обход. По умолчанию 5 — это час на выборку в 18 500 хостов и никакой
нагрузки для сервера, который держит сотни тысяч хостов.

Возобновляемость. Уже обойдённые хосты читаются из выходного файла и
пропускаются, так что повтор команды продолжает с места обрыва. Порядок
перемешан с фиксированным seed: базы создавались по возрастанию id, и обход по
порядку дал бы на любой промежуточной точке выборку, смещённую по датам.

    python3 obhod_saitov.py <панель.jsonl> <выход.jsonl> [сабдоменов_с_базы] [страниц_с_сайта]

    RATE=5          запросов в секунду на весь обход
    WORKERS=8       параллельных соединений
    TIMEOUT=20      секунд на запрос
"""
import os, re, sys, json, time, random, hashlib, threading, collections
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

RATE = float(os.environ.get('RATE', '5'))
WORKERS = int(os.environ.get('WORKERS', '8'))
TIMEOUT = int(os.environ.get('TIMEOUT', '20'))
# заголовки уходят в latin-1, поэтому UA только ASCII: кириллица здесь роняет
# каждый запрос с UnicodeEncodeError ещё до сети
UA = 'cladue-analytics/1.0 (internal audit of own sites)'

_lock = threading.Lock()
_next = [0.0]


def slot():
    """Общий предел скорости на весь обход: сайты стоят на одном сервере."""
    with _lock:
        now = time.monotonic()
        t = max(now, _next[0])
        _next[0] = t + 1.0 / RATE
    if t > now:
        time.sleep(t - now)


def get(url, timeout=TIMEOUT):
    slot()
    req = urllib.request.Request(url, headers={'User-Agent': UA,
                                               'Accept-Language': 'ru,en;q=0.8'})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(400_000)
            return {'code': r.status, 'ms': int((time.monotonic() - t0) * 1000),
                    'final': r.geturl(), 'body': body.decode('utf-8', 'replace'),
                    'bytes': len(body)}
    except urllib.error.HTTPError as e:
        return {'code': e.code, 'ms': int((time.monotonic() - t0) * 1000),
                'final': url, 'body': '', 'bytes': 0}
    except Exception as e:
        return {'code': None, 'ms': int((time.monotonic() - t0) * 1000),
                'final': url, 'body': '', 'bytes': 0,
                'error': type(e).__name__}


TAG = re.compile(r'<(script|style)[^>]*>.*?</\1>', re.S | re.I)
STRIP = re.compile(r'<[^>]+>')
WS = re.compile(r'\s+')


def text_of(html):
    s = TAG.sub(' ', html)
    s = STRIP.sub(' ', s)
    return WS.sub(' ', s).strip()


def one(host, pages_n):
    """Главная плюс несколько внутренних страниц одного сабдомена."""
    url = f'https://{host}/'
    r = get(url)
    out = {'host': host, 'code': r['code'], 'ms': r['ms'], 'bytes': r['bytes'],
           'final': r['final'], 'at': time.strftime('%Y-%m-%dT%H:%M:%S')}
    if 'error' in r:
        out['error'] = r['error']
    html = r['body']
    if not html:
        return out

    t = re.search(r'<title[^>]*>(.*?)</title>', html, re.S | re.I)
    h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S | re.I)
    txt = text_of(html)
    links = set(re.findall(r'href="(/[^"#?]*)"', html))
    out.update({
        'title': WS.sub(' ', STRIP.sub('', t.group(1))).strip()[:300] if t else None,
        'h1': WS.sub(' ', STRIP.sub('', h1.group(1))).strip()[:300] if h1 else None,
        'text_len': len(txt),
        'text_hash': hashlib.sha1(txt.encode()).hexdigest()[:16],
        'links': len(links),
        'hreflang': len(re.findall(r'hreflang=', html, re.I)),
        'ru_depth': max((p.count('/ru/') for p in links), default=0),
        'canonical': (re.search(r'rel="canonical"[^>]*href="([^"]+)"', html, re.I) or
                      [None, None])[1] if 'canonical' in html.lower() else None,
    })

    inner = [p for p in sorted(links) if p not in ('/', '')][:pages_n]
    pages = []
    for p in inner:
        pr = get(f'https://{host}{p}')
        pt = text_of(pr['body'])
        pages.append({'path': p, 'code': pr['code'], 'text_len': len(pt),
                      'hash': hashlib.sha1(pt.encode()).hexdigest()[:16]})
    out['pages'] = pages
    out['pages_ok'] = sum(1 for p in pages if p['code'] == 200)
    out['pages_uniq'] = len({p['hash'] for p in pages if p['code'] == 200})
    return out


def main(panel, out_path, per_base='10', per_site='6'):
    per_base, per_site = int(per_base), int(per_site)
    bysite = collections.defaultdict(list)
    for line in open(panel, encoding='utf-8'):
        r = json.loads(line)
        b = r.get('content_domain_url')
        if b:
            bysite[b].append(r['subdomain'])

    want = []
    rnd = random.Random(20260918)
    for b, subs in bysite.items():
        subs.sort()
        want += rnd.sample(subs, min(per_base, len(subs)))
    rnd.shuffle(want)

    done = set()
    if os.path.exists(out_path):
        for line in open(out_path, encoding='utf-8'):
            try:
                done.add(json.loads(line)['host'])
            except Exception:
                pass
    todo = [h for h in want if h not in done]
    print(f'баз {len(bysite)}, в выборке {len(want)} сабдоменов, '
          f'уже обойдено {len(done)}, осталось {len(todo)}')
    print(f'скорость {RATE}/с, потоков {WORKERS} — примерно '
          f'{len(todo)*(1+per_site)/RATE/60:.0f} минут', flush=True)

    n = 0
    lock = threading.Lock()
    with open(out_path, 'a', encoding='utf-8') as w, \
            ThreadPoolExecutor(max_workers=WORKERS) as pool:
        for res in pool.map(lambda h: one(h, per_site), todo):
            with lock:
                w.write(json.dumps(res, ensure_ascii=False) + '\n')
                n += 1
                if n % 200 == 0:
                    w.flush()
                    os.fsync(w.fileno())
                    print(f'  {n}/{len(todo)}', flush=True)
    print(f'ГОТОВО: {n} сабдоменов -> {out_path}')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:5])
