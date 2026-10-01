#!/usr/bin/env python3
"""Аудит рефереров кликов: поиск, свой сайт, пусто, чужие.

Каждый клик относится к одной группе:
  Яндекс        — реферер на домене Яндекса (yandex.*, ya.ru, dzen и т.п.)
  другой поиск  — Google, Bing, Mail, Rambler
  свой сайт     — реферер совпадает с самим сабдоменом (переход внутри дора)
  своя сеть     — реферер на другом нашем сайте (бренд.база.зона)
  нет реферера  — пусто или null (прямой заход, закладка, приложение)
  чужой         — всё остальное; топ таких хостов печатается отдельно

Отдельно считаются боты (is_bot) и наши сайты против чужих кампаний.

    python3 audit_referrerov.py <out.txt> <клики.jsonl:с:по> [ещё...]
"""
import sys, json, collections
from urllib.parse import urlparse

out_p = sys.argv[1]
specs = []
for a in sys.argv[2:]:
    p, lo, hi = (a.split(':') + ['', ''])[:3]
    specs.append((p, lo or '0000', hi or '9999'))
out = []


def P(*a):
    s = ' '.join(str(x) for x in a); print(s, flush=True); out.append(s)


SEARCH = {'google': 'Google', 'bing': 'Bing', 'mail.ru': 'Mail.ru', 'go.mail': 'Mail.ru',
          'rambler': 'Rambler', 'duckduckgo': 'DuckDuckGo', 'yahoo': 'Yahoo'}
G = collections.defaultdict(collections.Counter)      # день -> группа -> клики
B = collections.defaultdict(collections.Counter)      # день -> группа -> боты
FOREIGN = collections.Counter()                       # чужие хосты
YA = collections.Counter()                            # хосты Яндекса
DOM = collections.defaultdict(collections.Counter)    # группа -> уникальные сайты
n = 0
for p, lo, hi in specs:
    for line in open(p, encoding='utf-8'):
        r = json.loads(line)
        d = r['at'][:10]
        if d < lo or d > hi:
            continue
        s = (r.get('subdomain') or '').lower()
        if s.count('.') != 2:          # не наш формат бренд.база.зона
            continue
        n += 1
        ref = (r.get('referer') or '').strip()
        host = (urlparse(ref).hostname or '').lower() if ref else ''
        if not ref or not host:
            g = 'нет реферера'
        elif 'yandex' in host or host == 'ya.ru' or host.endswith('.ya.ru') or 'dzen.ru' in host:
            g = 'Яндекс'; YA[host] += 1
        elif any(k in host for k in SEARCH):
            g = 'другой поиск: ' + next(v for k, v in SEARCH.items() if k in host)
        elif host == s:
            g = 'свой сайт'
        elif 'sitegrator' in host:
            g = 'трекер (sitegrator)'
        elif host.count('.') == 2 and host.rsplit('.', 1)[-1] in ('team', 'lol', 'casino', 'buzz'):
            g = 'своя сеть'
        else:
            g = 'чужой'; FOREIGN[host] += 1
        G[d][g] += 1
        if r.get('is_bot'):
            B[d][g] += 1
        DOM[g][s] += 1

days = sorted(G)
groups = ['Яндекс', 'нет реферера', 'свой сайт', 'трекер (sitegrator)', 'своя сеть', 'чужой']
groups += sorted(g for g in {g for d in G for g in G[d]} if g.startswith('другой поиск'))
P(f'Кликов на сайтах вида бренд.база.зона: {n}. Дни: {days[0]}–{days[-1]}.')
P('\n=== Доля групп по дням (все клики, включая ботов) ===')
P(f'{"день":<12} {"всего":>9} ' + ' '.join(f'{g[:14]:>15}' for g in groups))
for d in days:
    t = sum(G[d].values())
    P(f'{d:<12} {t:>9} ' + ' '.join(f'{G[d][g]:>7} {100*G[d][g]/t:>5.1f}%' for g in groups))
P('\n=== То же без ботов ===')
P(f'{"день":<12} {"живых":>9} ' + ' '.join(f'{g[:14]:>15}' for g in groups))
for d in days:
    t = sum(G[d].values()) - sum(B[d].values())
    P(f'{d:<12} {t:>9} ' + ' '.join(f'{G[d][g]-B[d][g]:>7} {100*(G[d][g]-B[d][g])/t:>5.1f}%' for g in groups))
P('\n=== Доля ботов внутри группы ===')
P(f'{"группа":<22} {"кликов":>9} {"ботов":>9} {"доля":>7} {"сайтов":>8}')
for g in groups:
    tot = sum(G[d][g] for d in days); bot = sum(B[d][g] for d in days)
    if tot:
        P(f'{g:<22} {tot:>9} {bot:>9} {100*bot/tot:>6.1f}% {len(DOM[g]):>8}')
P('\n=== Хосты Яндекса ===')
for h, c in YA.most_common(12):
    P(f'   {h:<30} {c:>9} {100*c/sum(YA.values()):>5.1f}%')
P('\n=== Чужие рефереры, топ-25 ===')
tf = sum(FOREIGN.values())
P(f'   всего чужих: {tf}')
for h, c in FOREIGN.most_common(25):
    P(f'   {h:<44} {c:>8} {100*c/tf:>5.1f}%')
open(out_p, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
