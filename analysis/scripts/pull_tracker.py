#!/usr/bin/env python3
"""Выгрузка из API трекера (sitegrator): клики и конверсии.

Токен и хост берутся из окружения, в файл не пишутся:
    export TRACKER_BASE='https://sitegrator.com'
    export TRACKER_TOKEN='...'

Примеры:
    python3 pull_tracker.py audit                          # по странице каждого, отчёт
    python3 pull_tracker.py clicks      2026-09-11 2026-09-17
    python3 pull_tracker.py clicks      2026-09-11 2026-09-17 human
    python3 pull_tracker.py conversions 2026-09-11 2026-09-17
    python3 pull_tracker.py conversions 2026-09-11 2026-09-17 fd

Кладёт JSONL в analysis/api/tracker_<endpoint>_<from>_<to>.jsonl

Лимиты трекера мягче, чем у системы запусков: страница до 5000 строк, окно до
92 суток, 60 запросов в минуту. Механизм выгрузки общий — analysis/scripts/apidump.py:
обрыв лечится повтором той же команды, выгрузка продолжится с места обрыва.

Ключ соединения с системой запусков — `subdomain`. Он бывает отравлен: без
параметра `site=` трекер подставляет хост реферера, и в ключ попадает yandex.com
или чужой домен. Аудит это считает, см. analysis/spec/TRACKER_PREFLIGHT_17.09.md.
"""
import os, sys, json
from datetime import date, timedelta
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apidump import Source, ApiError, fill_report

BASE  = os.environ.get('TRACKER_BASE', '').rstrip('/')
TOKEN = os.environ.get('TRACKER_TOKEN', '')

LIMIT      = 5000       # максимум по контракту
MIN_GAP    = 1.05       # ~57 запросов в минуту, под лимитом 60
MAX_WINDOW = 92         # максимум суток на запрос

UA_CLASS = ('all', 'human', 'bot')
EVENTS   = ('reg', 'fd')


def src():
    return Source('tracker', BASE, TOKEN, LIMIT, MIN_GAP, MAX_WINDOW)


def _host(url):
    """Хост из реферера, в нижнем регистре и без www — как ключ у трекера."""
    if not url:
        return None
    h = (urlsplit(url).hostname or '').lower()
    return h[4:] if h.startswith('www.') else h or None


def audit(d1=None, d2=None):
    """По странице каждого эндпоинта: что приходит и в каком состоянии.

    Отвечает на проверки из TRACKER_PREFLIGHT_17.09.md §3 — доля кликов без
    ключа, доля ботов, отравление ключа хостом реферера.
    """
    d2 = d2 or str(date.today())
    d1 = d1 or str(date.fromisoformat(d2) - timedelta(days=6))
    s = src()

    print(f"########## /v1/clicks  {d1}..{d2} ##########\n")
    j = s.get('/v1/clicks', dict(date_from=d1, date_to=d2, limit=1000))
    clicks = j.get('data', [])
    if not clicks:
        print("пусто — нет кликов за этот период\n")
    else:
        fill_report(clicks, {'subdomain': 'ключ соединения', 'clickid': 'связь с конверсией',
                             'is_bot': 'боты не отфильтрованы', 'landing_path': 'глубина входа',
                             'referer': 'доказательство выдачи'})
        n = len(clicks)
        nosub = sum(1 for r in clicks if not r.get('subdomain'))
        bots  = sum(1 for r in clicks if r.get('is_bot'))
        pois  = [r for r in clicks if r.get('subdomain') and r['subdomain'] == _host(r.get('referer'))]
        ya    = sum(1 for r in clicks if 'yandex' in (_host(r.get('referer')) or ''))
        noref = sum(1 for r in clicks if not r.get('referer'))
        print(f"\nКЛЮЧ И КАЧЕСТВО, {n} строк:")
        print(f"  без subdomain (выпадают из соединения) {nosub:>6}  {100*nosub//n}%")
        print(f"  subdomain равен хосту реферера — ОТРАВЛЕН {len(pois):>4}  {100*len(pois)//n}%")
        for r in pois[:5]:
            print(f"      {r['subdomain']}  <- {r.get('referer')}")
        print(f"  is_bot                                 {bots:>6}  {100*bots//n}%")
        print(f"  реферер яндексовый                     {ya:>6}  {100*ya//n}%")
        print(f"  реферер пустой                         {noref:>6}  {100*noref//n}%")

    print(f"\n\n########## /v1/conversions  {d1}..{d2} ##########\n")
    j = s.get('/v1/conversions', dict(date_from=d1, date_to=d2, limit=1000))
    conv = j.get('data', [])
    if not conv:
        print("пусто — нет конверсий за этот период")
    else:
        fill_report(conv, {'subdomain': 'ключ соединения', 'event': 'reg или fd',
                           'event_raw': 'сырое имя от партнёрки', 'linked_at': 'строка финальная',
                           'payout': 'всегда null', 'status': 'всегда null'})
        n = len(conv)
        nosub = sum(1 for r in conv if not r.get('subdomain'))
        nolink = sum(1 for r in conv if not r.get('linked_at'))
        pois = [r for r in conv if r.get('subdomain') and r['subdomain'] == _host(r.get('referer'))]
        ev = {}
        for r in conv:
            ev[r.get('event')] = ev.get(r.get('event'), 0) + 1
        print(f"\nКЛЮЧ И КАЧЕСТВО, {n} строк:")
        print(f"  события: {ev}")
        print(f"  без subdomain (клика в базе нет)       {nosub:>6}  {100*nosub//n}%")
        print(f"  без linked_at (ещё не устоялись)       {nolink:>6}  {100*nolink//n}%")
        print(f"  subdomain равен хосту реферера — ОТРАВЛЕН {len(pois):>4}  {100*len(pois)//n}%")
        for r in pois[:5]:
            print(f"      {r['subdomain']}  <- {r.get('referer')}")
        unknown = [r.get('event_raw') for r in conv if r.get('event') is None and r.get('event_raw')]
        if unknown:
            print(f"  НЕОПОЗНАННЫЕ события от партнёрки: {sorted(set(unknown))}")

    if s.stable_until:
        print(f"\nданные устоялись до {s.stable_until} — окно анализа брать не позже")


if __name__ == '__main__':
    if not BASE or not TOKEN:
        raise SystemExit("нужны переменные TRACKER_BASE и TRACKER_TOKEN")
    a = sys.argv[1:] or ['audit']
    try:
        if a[0] == 'audit':
            audit(*a[1:3])
        elif a[0] == 'clicks':
            if len(a) < 3: raise SystemExit("использование: pull_tracker.py clicks <date_from> <date_to> [all|human|bot]")
            extra = {}
            if len(a) > 3:
                if a[3] not in UA_CLASS: raise SystemExit(f"ua_class: {' | '.join(UA_CLASS)}")
                extra['ua_class'] = a[3]
            src().dump('clicks', a[1], a[2], **extra)
        elif a[0] == 'conversions':
            if len(a) < 3: raise SystemExit("использование: pull_tracker.py conversions <date_from> <date_to> [reg|fd]")
            extra = {}
            if len(a) > 3:
                if a[3] not in EVENTS: raise SystemExit(f"event: {' | '.join(EVENTS)}")
                extra['event'] = a[3]
            src().dump('conversions', a[1], a[2], **extra)
        else:
            raise SystemExit(__doc__)
    except ApiError as e:
        raise SystemExit(str(e))
