# -*- coding: utf-8 -*-
"""Замер шаблонных параметров набора. Медиана по наборам, не среднее."""
import re, sys, os, glob, statistics, json

TAG = re.compile(r'<[^>]+>')
def text(h): return re.sub(r'\s+',' ', TAG.sub(' ', h)).strip()
def words(t): return [w for w in re.split(r'[^\w%\-]+', t, flags=re.U) if w]

KEYS = {
 'казино': r'\bказино\b', 'слот': r'\bслот\w*', 'бонус': r'\bбонус\w*',
 'джекпот': r'\bджекпот\w*', 'зеркало': r'\bзеркал\w*', 'промокод': r'\bпромокод\w*',
 'регистрация': r'\bрегистрац\w*', 'вход': r'\bвход\w*', 'офиц.сайт': r'официальн\w+ сайт',
 'фриспин': r'\bфриспин\w*|\bбесплатн\w+ вращен\w*', 'вейджер': r'\bвейджер\w*|\bотыгрыш\w*',
 'лицензия': r'\bлицензи\w*', 'кэшбэк': r'\bк[эе]шб[эе]к\w*', 'депозит': r'\bдепозит\w*',
 'вывод': r'\bвывод\w*', 'поддержка': r'\bподдержк\w*', 'турнир': r'\bтурнир\w*',
 'RTP': r'\bRTP\b', 'провайдер': r'\bпровайдер\w*|\bстуди\w+',
}
IMYA = re.compile(r'\b(Алексей|Андрей|Антон|Артём|Артем|Борис|Вадим|Валентин|Василий|Виктор|Виталий|Владимир|Вячеслав|Геннадий|Георгий|Григорий|Даниил|Денис|Дмитрий|Евгений|Егор|Иван|Игорь|Илья|Кирилл|Константин|Леонид|Максим|Марк|Михаил|Никита|Николай|Олег|Павел|Пётр|Петр|Роман|Руслан|Сергей|Станислав|Степан|Тимур|Фёдор|Федор|Юрий|Ярослав|Анна|Алина|Виктория|Дарья|Екатерина|Елена|Ирина|Ксения|Марина|Мария|Наталья|Ольга|Светлана|Татьяна|Юлия)\b')

def nabor(d):
    files = sorted(glob.glob(os.path.join(d,'*.html')))
    if not files: return None
    m = {}
    allw=0; pages=[]
    agg = dict(h2=0,h3=0,p=0,li=0,ul=0,ol=0,a=0,img=0,strong=0,em=0,table=0,button=0,div=0,section=0,span=0,h2len=[],h2q=0,h2colon=0,h2dash=0,liLen=[],pLen=[],anchors=[],addr=[],faq=0,cls=0,styles=0,nums=0,pct=set(),sums=set(),rtp=set(),names=[],ty=0,vy=0,emoji=0,keys={k:0 for k in KEYS},sent=0,brandH=0)
    for f in files:
        h = open(f,encoding='utf-8',errors='ignore').read()
        t = text(h); w = words(t); allw += len(w); pages.append(len(w))
        agg['h2'] += len(re.findall(r'<h2\b',h)); agg['h3'] += len(re.findall(r'<h3\b',h))
        agg['p']  += len(re.findall(r'<p\b',h));  agg['li'] += len(re.findall(r'<li\b',h))
        agg['ul'] += len(re.findall(r'<ul\b',h)); agg['ol'] += len(re.findall(r'<ol\b',h))
        agg['img']+= len(re.findall(r'<img\b',h)); agg['strong'] += len(re.findall(r'<strong\b|<b>',h))
        agg['em'] += len(re.findall(r'<em\b|<i>',h)); agg['table'] += len(re.findall(r'<table\b',h))
        agg['button'] += len(re.findall(r'<button\b',h)); agg['div'] += len(re.findall(r'<div\b',h))
        agg['section'] += len(re.findall(r'<section\b',h)); agg['span'] += len(re.findall(r'<span\b',h))
        agg['cls'] += len(re.findall(r'class="',h)); agg['styles'] += len(re.findall(r'style="',h))
        for m2 in re.findall(r'<h2\b[^>]*>(.*?)</h2>', h, re.S):
            s = text(m2)
            if not s: continue
            agg['h2len'].append(len(s))
            if '?' in s: agg['h2q'] += 1
            if ':' in s: agg['h2colon'] += 1
            if '—' in s or ' - ' in s: agg['h2dash'] += 1
        for m2 in re.findall(r'<li\b[^>]*>(.*?)</li>', h, re.S): agg['liLen'].append(len(words(text(m2))))
        for m2 in re.findall(r'<p\b[^>]*>(.*?)</p>', h, re.S):
            pw = len(words(text(m2)))
            if pw: agg['pLen'].append(pw)
        for href,inner in re.findall(r'<a\b[^>]*href="([^"]*)"[^>]*>(.*?)</a>', h, re.S):
            agg['a'] += 1; agg['anchors'].append(text(inner).lower()); agg['addr'].append(href)
        agg['faq'] += len(re.findall(r'faq-item|faq-question|itemtype="https://schema.org/Question"', h))
        agg['nums'] += len(re.findall(r'\d', t))
        agg['pct'] |= set(re.findall(r'(\d+(?:[.,]\d+)?)\s*%', t))
        agg['sums'] |= set(re.findall(r'(\d[\d\s]{2,})\s*(?:₽|руб)', t))
        agg['rtp'] |= set(re.findall(r'RTP[^\d]{0,12}(\d+(?:[.,]\d+)?)', t))
        agg['names'] += IMYA.findall(t)
        agg['ty'] += len(re.findall(r'\bты\b|\bтебе\b|\bтебя\b|\bтвой\w*|\bиграй\b|\bзаходи\b', t, re.I))
        agg['vy'] += len(re.findall(r'\bвы\b|\bвам\b|\bвас\b|\bваш\w*|\bиграйте\b|\bзаходите\b', t, re.I))
        agg['emoji'] += len(re.findall(r'[\U0001F300-\U0001FAFF☀-➿]', h))
        agg['sent'] += len(re.findall(r'[.!?…](?:\s|$)', t))
        for k,rx in KEYS.items(): agg['keys'][k] += len(re.findall(rx, t, re.I))
    n=len(files); k=allw/1000 or 1
    r = {
      'страниц': n, 'слов в наборе': allw, 'слов на страницу': round(statistics.median(pages)),
      'абзацев на страницу': round(agg['p']/n,1), 'слов в абзаце': round(statistics.median(agg['pLen']),1) if agg['pLen'] else 0,
      'предложений на 100 слов': round(agg['sent']*100/allw,1),
      'h2 на страницу': round(agg['h2']/n,1), 'h3 на h2': round(agg['h3']/max(1,agg['h2']),2),
      'длина h2, знаков': round(statistics.median(agg['h2len'])) if agg['h2len'] else 0,
      'h2 с вопросом, %': round(agg['h2q']*100/max(1,len(agg['h2len'])),1),
      'h2 с двоеточием, %': round(agg['h2colon']*100/max(1,len(agg['h2len'])),1),
      'h2 с тире, %': round(agg['h2dash']*100/max(1,len(agg['h2len'])),1),
      'списков на страницу': round((agg['ul']+agg['ol'])/n,1), 'пунктов в списке': round(agg['li']/max(1,agg['ul']+agg['ol']),1),
      'слов в пункте': round(statistics.median(agg['liLen']),1) if agg['liLen'] else 0,
      'нумерованных списков, %': round(agg['ol']*100/max(1,agg['ul']+agg['ol']),1),
      'ссылок на страницу': round(agg['a']/n,1), 'ссылок на 1000 слов': round(agg['a']/k,1),
      'уникальных анкоров, %': round(len(set(agg['anchors']))*100/max(1,len(agg['anchors'])),1),
      'уникальных адресов': len(set(agg['addr'])),
      'таблиц на набор': agg['table'], 'картинок на страницу': round(agg['img']/n,1),
      'strong на 1000 слов': round(agg['strong']/k,1), 'em на 1000 слов': round(agg['em']/k,1),
      'кнопок на набор': agg['button'], 'эмодзи на страницу': round(agg['emoji']/n,1),
      'FAQ-меток на набор': agg['faq'],
      'div на страницу': round(agg['div']/n,1), 'section на страницу': round(agg['section']/n,1),
      'span на страницу': round(agg['span']/n,1), 'class на страницу': round(agg['cls']/n,1),
      'style на страницу': round(agg['styles']/n,1),
      'цифр на 100 слов': round(agg['nums']*100/allw,1),
      'разных процентов': len(agg['pct']), 'разных сумм': len(agg['sums']), 'разных RTP': len(agg['rtp']),
      'имён на 1000 слов': round(len(agg['names'])/k,2), 'разных имён': len(set(agg['names'])),
      'ты-форм на 1000': round(agg['ty']/k,1), 'вы-форм на 1000': round(agg['vy']/k,1),
      'доля вы, %': round(agg['vy']*100/max(1,agg['ty']+agg['vy']),1),
    }
    for kk,v in agg['keys'].items(): r['кл. «%s» на 1000' % kk] = round(v/k,2)
    return r

def svod(dirs):
    rows=[nabor(d) for d in dirs]; rows=[r for r in rows if r]
    out={}
    for key in rows[0]:
        vals=[r[key] for r in rows]
        out[key]=(round(statistics.median(vals),2), round(min(vals),2), round(max(vals),2),
                  round(statistics.pstdev(vals)/statistics.mean(vals),2) if statistics.mean(vals) else 0)
    return out, len(rows)

def raskryt(uzor):
    """Папки наборов по шаблону пути. `samples/v5-final/nabor-6*` или папка с папками."""
    итог = []
    for d in glob.glob(uzor):
        if not os.path.isdir(d):
            continue
        # указали контейнер, в котором лежат наборы, — берём его содержимое
        if glob.glob(os.path.join(d, '*.html')):
            итог.append(d)
        else:
            итог += [x for x in glob.glob(os.path.join(d, '*')) if os.path.isdir(x)]
    return sorted(итог)

if len(sys.argv) < 3:
    sys.exit('usage: python3 engine/instrumenty/zamer-shablona.py <наши/*> <их/*> [метка1] [метка2]')
A = raskryt(sys.argv[1]); B = raskryt(sys.argv[2])
m1 = sys.argv[3] if len(sys.argv) > 3 else 'A'
m2 = sys.argv[4] if len(sys.argv) > 4 else 'B'
a, na = svod(A); b, nb = svod(B)
print('# наборов: %s — %d, %s — %d' % (m1, na, m2, nb))
print('| параметр | %s: медиана | %s: полоса | %s CV | %s: медиана | %s: полоса | %s CV |'
      % (m1, m1, m1, m2, m2, m2))
print('|---|---|---|---|---|---|---|')
for kk in a:
    x = a[kk]; y = b[kk]
    print('| %s | %s | %s–%s | %s | %s | %s–%s | %s |' % (kk, x[0], x[1], x[2], x[3], y[0], y[1], y[2], y[3]))
