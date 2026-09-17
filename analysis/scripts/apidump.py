#!/usr/bin/env python3
"""Общий механизм выгрузки для обоих источников: системы запусков и трекера.

Оба API устроены одинаково: только GET, `Authorization: Bearer`, обёртка
`{"data": [...], "meta": {"next_cursor": …}}`, курсорная пагинация, те же коды
ошибок, пояс Europe/Kyiv. Различаются адрес, токен, темп и предельные размеры
окна и страницы — поэтому здесь они параметры, а не константы.

Вынесено в отдельный файл ради возобновления. Логика с offset, fsync и обрезкой
файла при старте тонкая и уже стоила двух исправлений; в двух копиях следующая
правка неминуемо разойдётся, причём молча.
"""
import os, sys, json, time, random, urllib.request, urllib.error, urllib.parse
from datetime import date, timedelta

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'api')


class ApiError(Exception):
    """Страница не взялась. permanent=True — повторять бесполезно (4xx кроме 429)."""
    def __init__(self, msg, permanent=False):
        super().__init__(msg)
        self.permanent = permanent


class Source:
    """Один источник данных: адрес, токен и его ограничения.

    limit       строк на страницу (dorgen 1000, трекер 5000)
    min_gap     пауза между запросами, чуть больше 60/лимит_в_минуту
    max_window  предельное окно дат на один запрос (dorgen 31, трекер 92)
    """

    # Cloudflare перед трекером отвечает 403 Error 1010 на User-Agent вида
    # Python-urllib/*, с любым другим — нормальный 401/200. Без явного UA
    # выгрузка упала бы на первом же запросе с ошибкой, не относящейся к делу.
    UA = 'cladue-analytics/1.0'

    def __init__(self, name, base, token, limit, min_gap, max_window, tries=15):
        self.name, self.base, self.token = name, base.rstrip('/'), token
        self.limit, self.min_gap, self.max_window, self.tries = limit, min_gap, max_window, tries
        self.stats = {'ok': 0, 'err_5xx': 0, 'err_429': 0}
        self.stable_until = None      # meta.stable_until последнего ответа, если есть

    def get(self, path, params):
        """GET с повтором.

        5xx на этих API случайны и независимы — их повторяем коротко и часто:
        длинный откат тут только теряет время. 429 наоборот означает реальный
        лимит, по нему экспоненциальный откат, с уважением к Retry-After.
        """
        url = f"{self.base}{path}?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/json',
            'User-Agent': self.UA,
        })
        slow = 5
        for attempt in range(self.tries):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    self.stats['ok'] += 1
                    j = json.loads(r.read().decode())
                su = (j.get('meta') or {}).get('stable_until')
                if su:
                    self.stable_until = su
                return j
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors='replace')[:200]
                last = attempt == self.tries - 1
                if e.code == 429 and not last:
                    self.stats['err_429'] += 1
                    wait = e.headers.get('Retry-After')
                    d = int(wait) if (wait or '').isdigit() else slow
                    print(f"    429, жду {d}s", file=sys.stderr)
                    time.sleep(d); slow = min(slow * 2, 120); continue
                if e.code in (500, 502, 503, 504) and not last:
                    self.stats['err_5xx'] += 1
                    d = min(2 + attempt, 8) + random.uniform(0, 0.5)
                    print(f"    {e.code} ({attempt + 1}/{self.tries}), жду {d:.1f}s", file=sys.stderr)
                    time.sleep(d); continue
                raise ApiError(f"HTTP {e.code} на {path}: {body}",
                               permanent=400 <= e.code < 500 and e.code != 429)
            except urllib.error.URLError as e:
                # сетевая ошибка повторяется дважды: блокировка политикой не «рассосётся»
                if attempt < 2:
                    print(f"    сеть: {e.reason}, жду 4s", file=sys.stderr)
                    time.sleep(4); continue
                raise ApiError(f"сеть недоступна: {e.reason}")
        raise ApiError(f"{self.tries} попыток подряд неудачны на {path}")

    def _chunks(self, d1, d2):
        """Режем окно на куски по max_window дней."""
        a = date.fromisoformat(d1); b = date.fromisoformat(d2)
        while a <= b:
            c = min(b, a + timedelta(days=self.max_window - 1))
            yield a.isoformat(), c.isoformat()
            a = c + timedelta(days=1)

    def dump(self, ep, d1, d2, **extra):
        """Выгрузка в JSONL с возобновлением. Повтор той же команды продолжает
        с места обрыва; успешная выгрузка состояние удаляет."""
        if date.fromisoformat(d1) > date.fromisoformat(d2):
            raise SystemExit(f"окно пустое: {d1} позже {d2}")
        os.makedirs(OUT, exist_ok=True)
        fn  = os.path.join(OUT, f"{self.name}_{ep}_{d1}_{d2}.jsonl")
        key = json.dumps([self.name, ep, d1, d2, extra, self.limit],
                         sort_keys=True, ensure_ascii=False)
        win = list(self._chunks(d1, d2))

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
                p = dict(extra, date_from=c1, date_to=c2, limit=self.limit)
                if st['cursor']:
                    p['cursor'] = st['cursor']

                t0 = time.time()
                j = self.get(f"/v1/{ep}", p)
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
                    time.sleep(max(0, self.min_gap - (time.time() - t0)))
        except (ApiError, KeyboardInterrupt) as e:
            f.close()
            print(f"\nПРЕРВАНО: {e}", file=sys.stderr)
            if st['total'] == 0:
                # ни одной строки: пустой файл рядом с состоянием только сбивает с толку
                for junk in (fn, fn + '.state'):
                    if os.path.exists(junk): os.remove(junk)
                print("Ни одной строки не получено, пустой файл не оставляю.", file=sys.stderr)
            else:
                print(f"{st['total']} строк сохранено в {fn}.", file=sys.stderr)
            if isinstance(e, ApiError) and e.permanent:
                print("Ошибка не временная — повтор не поможет, надо разбираться.", file=sys.stderr)
                raise SystemExit(3)
            print("Повторите ту же команду — продолжу с этого места.", file=sys.stderr)
            raise SystemExit(2)
        f.close()
        if os.path.exists(fn + '.state'):
            os.remove(fn + '.state')    # выгрузка целая, возобновлять нечего

        print(f"-> {fn}  {st['total']} строк")
        print(f"   запросов удачных {self.stats['ok']}, повторов по 5xx "
              f"{self.stats['err_5xx']}, по 429 {self.stats['err_429']}", file=sys.stderr)
        if self.stable_until:
            print(f"   данные устоялись до {self.stable_until}", file=sys.stderr)
        return fn


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


def fill_report(rows, need=None):
    """Сколько непустых у каждого поля и пример значения. need — поля, которые
    отдельно вынести в конец списком «есть/нет»."""
    EMPTY = (None, '', [], {})
    keys = sorted({k for r in rows for k in r})
    print(f"строк в выборке: {len(rows)}, полей: {len(keys)}\n")
    print(f"{'поле':<28}{'непустых':>12}  пример")
    for k in keys:
        vals = [r.get(k) for r in rows]
        nn = sum(1 for v in vals if v not in EMPTY)
        ex = next((v for v in vals if v not in EMPTY), None)
        mark = '  <- ' + need[k] if need and k in need else ''
        print(f"{k:<28}{nn:>5}/{len(rows):<6}  {str(ex)[:42]}{mark}")
    if need:
        print("\nКРИТИЧНЫЕ ПОЛЯ:")
        for k, why in need.items():
            nn = sum(1 for r in rows if r.get(k) not in EMPTY)
            print(f"  {'ЕСТЬ ' if nn else 'НЕТ  '}{k:<22}{why}")
