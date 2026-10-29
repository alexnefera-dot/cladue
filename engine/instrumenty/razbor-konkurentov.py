#!/usr/bin/env python3
# Раскладывает присланные пользователем страницы конкурентов из транскрипта по папкам сайтов.
import json, os, re, sys, hashlib

# Транскрипт сессии, в котором лежат присланные страницы: путь передаётся первым
# аргументом, иначе берётся единственный .jsonl проекта.
TRANS = (sys.argv[1] if len(sys.argv) > 1
         else '/root/.claude/projects/-home-user-cladue/'
              '580c9237-8e67-549d-b11b-3f159fa71245.jsonl')
BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..',
                    'samples', 'konkurenty')

FILE_BY_LABEL = {
    'главная': 'main', 'бонус': 'bonus', 'регистрация': 'registracia',
    'приложение': 'app', 'зеркало': 'zerkalo', 'вход': 'vhod', 'слоты': 'slots',
    'новости': 'novosti', 'инфо': 'info', 'промо': 'promo',
    'обзор': 'obzor', 'партнеры': 'partnery',
}
LABEL_RE = re.compile(
    r'^(?:[^\n]{0,80}?\b)?(' + '|'.join(FILE_BY_LABEL) + r')\s*[-–—]\s*(?=<)', re.S)

def raw_prompts():
    """Текст каждого сообщения пользователя в порядке появления.

    Один и тот же пересланный блок встречается в транскрипте несколько раз,
    поэтому отбрасываем повторы по идентификатору сообщения, а не по тексту:
    разные сайты присылались с дословно совпадающими страницами.
    """
    seen, out = set(), []
    for line in open(TRANS, encoding='utf-8'):
        try:
            o = json.loads(line)
        except Exception:
            continue
        t = key = None
        if o.get('type') == 'attachment':
            a = o.get('attachment') or {}
            if isinstance(a, dict) and a.get('type') == 'queued_command':
                t = a.get('prompt')
                key = a.get('delivery_id') or a.get('source_uuid') or o.get('uuid')
        elif o.get('type') == 'user':
            c = (o.get('message') or {}).get('content')
            if isinstance(c, str):
                t = c
            elif isinstance(c, list):
                t = ''.join(x.get('text', '') for x in c
                            if isinstance(x, dict) and x.get('type') == 'text')
            key = o.get('uuid')
        if not t:
            continue
        key = key or hashlib.sha1(t.encode('utf-8')).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        out.append(t.strip())
    return out

def main():
    pages = []          # (label, html)
    for t in raw_prompts():
        m = LABEL_RE.match(t)
        if not m:
            continue
        label = m.group(1)
        html = t[m.end():].strip()
        pages.append((label, html))

    # Сайт определяется по классу-обёртке; страницы без класса наследуют текущий сайт.
    sites, order, cur = {}, [], None
    for label, html in pages:
        cm = re.search(r'\.(k7-[0-9a-f]{6})\s*\{', html) or re.search(r'class="(k7-[0-9a-f]{6})"', html)
        if cm:
            cur = cm.group(1)
        key = cur or 'bez-klassa'
        if key not in sites:
            sites[key] = {}
            order.append(key)
        sites[key][label] = html

    os.makedirs(BASE, exist_ok=True)
    for n, key in enumerate(order, 1):
        d = os.path.join(BASE, 'sayt-%d' % n)
        os.makedirs(d, exist_ok=True)
        # CSS выносим один раз на сайт
        css = None
        for html in sites[key].values():
            cm = re.match(r'\s*<style>(.*?)</style>', html, re.S)
            if cm:
                css = cm.group(1)
                break
        if css:
            with open(os.path.join(d, '_style.css'), 'w', encoding='utf-8') as f:
                f.write(css)
        with open(os.path.join(d, '_klass.txt'), 'w', encoding='utf-8') as f:
            f.write(key + '\n')
        for label, html in sites[key].items():
            body = re.sub(r'\s*<style>.*?</style>\s*', '', html, count=1, flags=re.S)
            name = FILE_BY_LABEL[label] + '.html'
            with open(os.path.join(d, name), 'w', encoding='utf-8') as f:
                f.write(body.strip() + '\n')
        print('sayt-%d  %s  %2d стр: %s' % (
            n, key, len(sites[key]),
            ' '.join(FILE_BY_LABEL[l] for l in sites[key])))

if __name__ == '__main__':
    main()
