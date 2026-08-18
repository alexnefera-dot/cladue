# -*- coding: utf-8 -*-
import io, re, collections, sys
def razvedi(f, pool=None):
    """Разводит повторяющиеся анкорные метки, заменяя последние вхождения."""
    s = io.open(f, encoding='utf-8').read()
    a = re.findall(r'<a href="([^"]*)">(.*?)</a>', s)
    c = collections.Counter([(h, t.lower()) for h, t in a])
    pool = pool or {
      '/vhod': ['выписка кабинета', 'сводка операций', 'личный раздел', 'страница акций', 'вход в кабинет', 'раздел безопасности'],
      '/registracia': ['правила анкеты', 'бланк анкеты', 'опись документов', 'условия открытия счёта', 'порядок проверки'],
      '/slots': ['обзор слотов', 'раздел машин', 'паспорт машины', 'перечень тайтлов', 'сводка автоматов'],
      '/zerkalo': ['обвод блокировок', 'список доменов', 'перечень адресов', 'сводка зеркал'],
      '/app': ['страница сборки', 'раздел программы', 'описание пакета'],
    }
    used = set(t for _, t in c)
    done = 0
    for (h, t), n in sorted(c.items(), key=lambda x: -x[1]):
        while n > 1:
            cand = next((x for x in pool.get(h, []) if x not in used), None)
            if not cand: break
            pat = '<a href="%s">%s</a>' % (h, t)
            i = s.rfind(pat)
            if i < 0:
                # попробовать с заглавной
                pat = '<a href="%s">%s</a>' % (h, t[0].upper() + t[1:])
                i = s.rfind(pat)
                if i < 0: break
            s = s[:i] + '<a href="%s">%s</a>' % (h, cand) + s[i+len(pat):]
            used.add(cand); n -= 1; done += 1
    io.open(f, 'w', encoding='utf-8').write(s)
    print('разведено', done)
if __name__ == '__main__':
    razvedi(sys.argv[1])
