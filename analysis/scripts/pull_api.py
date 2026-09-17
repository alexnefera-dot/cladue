#!/usr/bin/env python3
"""Выгрузка из Analytics Export API системы запусков (dorgen).

Токен и хост берутся из окружения, в файл не пишутся:
    export DORGEN_BASE='https://dorgen-engine.com'
    export DORGEN_TOKEN='...'

Примеры:
    python3 pull_api.py audit                      # одна страница, отчёт по полям
    python3 pull_api.py globals
    python3 pull_api.py subdomains 2026-09-10 2026-09-17
    python3 pull_api.py events     2026-09-16 2026-09-17

traffic отключён: курсор /v1/traffic сломан, дальше 1000 строк не уйти, а трафик
переедет в отдельное API, которое ещё не реализовано.

Кладёт JSONL в analysis/api/dorgen_<endpoint>_<from>_<to>.jsonl

ВОЗОБНОВЛЕНИЕ. Аудит 17.09 намерял 50-75% ответов HTTP 500 на /v1/subdomains,
причём случайных: один и тот же запрос даёт 200, 200, 500, 500, 500. Длинная
выгрузка при таком фоне обрывается гарантированно, поэтому рядом с JSONL живёт
файл состояния <имя>.jsonl.state с курсором и длиной уже записанного.

    python3 pull_api.py subdomains 2026-09-10 2026-09-17   # оборвалось
    python3 pull_api.py subdomains 2026-09-10 2026-09-17   # та же команда — продолжит

Механизм общий с трекером, он же и описан — analysis/scripts/apidump.py.
    DORGEN_TRIES=N   — попыток на страницу (по умолчанию 15)
"""
import os, sys, json
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from apidump import Source, ApiError, fill_report

BASE  = os.environ.get('DORGEN_BASE', '').rstrip('/')
TOKEN = os.environ.get('DORGEN_TOKEN', '')

LIMIT      = 1000       # максимум по документации
MIN_GAP    = 2.1        # ~28 запросов в минуту, под лимитом 30
MAX_WINDOW = 31         # максимум дней на запрос
TRIES      = int(os.environ.get('DORGEN_TRIES', '15'))


def src():
    return Source('dorgen', BASE, TOKEN, LIMIT, MIN_GAP, MAX_WINDOW, TRIES)


def audit():
    """Одна страница /v1/subdomains: какие поля приходят и что в них."""
    j = src().get('/v1/subdomains', dict(date_from='2026-09-15', date_to='2026-09-15',
                                         date_field='pipeline_started', limit=50))
    rows = j.get('data', [])
    if not rows: raise SystemExit("пусто — нет строк за эту дату")
    fill_report(rows, {
        'brand_id': 'износ бренда', 'ya_account_id': 'нагруженность YA',
        'cf_account_id': 'номер базы на CF', 'recrawl_sent_at': 'волны переобхода',
        'content_label': 'контент как параметр', 'subdomain': 'ключ соединения',
        'content_domain_id': 'группировка по запуску', 'tld': 'зона'})


if __name__ == '__main__':
    if not BASE or not TOKEN:
        raise SystemExit("нужны переменные DORGEN_BASE и DORGEN_TOKEN")
    a = sys.argv[1:] or ['audit']
    try:
        if a[0] == 'audit':   audit()
        elif a[0] == 'globals':
            on = a[1] if len(a) > 1 else str(date.today())
            print(json.dumps(src().get('/v1/globals', dict(on=on)), ensure_ascii=False, indent=1))
        elif a[0] == 'traffic':
            raise SystemExit(
                "traffic выгружать нечем: курсор /v1/traffic отвергается сервером, "
                "который его же выдал, поэтому дальше первых 1000 строк не уйти.\n"
                "Эти 1000 строк — смещённая выборка (первые по дате), анализировать "
                "её нельзя, поэтому файл не пишется вовсе.\n"
                "Трафик переедет в отдельное API, оно ещё не реализовано. "
                "Подробности — analysis/spec/AUDIT_API_17.09.md §2-бис.")
        elif a[0] in ('subdomains', 'events'):
            if len(a) < 3: raise SystemExit(f"использование: pull_api.py {a[0]} <date_from> <date_to>")
            extra = {'date_field': 'pipeline_started'} if a[0] == 'subdomains' else {}
            src().dump(a[0], a[1], a[2], **extra)
        else:
            raise SystemExit(__doc__)
    except ApiError as e:
        raise SystemExit(str(e))
