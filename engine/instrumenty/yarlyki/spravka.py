# -*- coding: utf-8 -*-
"""Справка по типу перед письмом ярлыков: разделы, словарь анкеров и прорезей,
полосы плотностей и длины, порог терминов. Нужна, чтобы писать сразу под
плотности, а не ловить их проходами."""
import collections, json, os, re, subprocess, sys
КОРЕНЬ = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
тип = sys.argv[1]
d = json.load(open(КОРЕНЬ + '/engine/data-v5/pools.json', encoding='utf-8'))
ТЕГИ = re.compile(r'(?s)<[^>]+>')
разд = d['разделы'][тип]
стар = [str(x.get('т', '')) for r in разд.values() for x in r['пункты']]

def php(код, вход):
    r = subprocess.run(['php', '-r', код], input=json.dumps(вход), capture_output=True,
                       text=True, cwd=КОРЕНЬ)
    return json.loads(r.stdout)

тс = sorted(php('require_once "engine/src/PageMetrics.php";$in=json_decode(file_get_contents("php://stdin"),true);'
                '$o=[];foreach($in as $t){$o[]=NicheLexicon::termsTotal($t);}echo json_encode($o);', стар))
дл = sorted(len(ТЕГИ.sub('', x).split()) for x in стар)
print('тип %s: разделов %d, пунктов %d' % (тип, len(разд), len(стар)))
print('порог терминов на пункт (90-й дециль): %d' % тс[int(.9 * (len(тс) - 1))])
print('полоса слов (10–90 дециль): %d–%d' % (дл[int(.10 * (len(дл) - 1))], дл[int(.90 * (len(дл) - 1))]))
HONEST = re.compile(r'\b(минус\w*|недостат\w*|риск\w*|осторожн\w*|не советую|не стоит|проигр\w*'
                    r'|потер\w*|обман\w*|развод\w*|ловушк\w*|подвох\w*|честно говоря|на самом деле'
                    r'|важно понимать)\b', re.I)
для = {'honest': lambda t: len(HONEST.findall(ТЕГИ.sub('', t))),
       'ссылок': lambda t: len(re.findall(r'<a\s', t)),
       'цифр': lambda t: len(re.findall(r'\d', ТЕГИ.sub('', t))),
       'прорезей': lambda t: len(re.findall(r'\{[^}]+\}', t)),
       'strong': lambda t: len(re.findall(r'<strong', t))}
print('\nплотности существующих пунктов и сколько нужно на транш из N:')
for имя, f in для.items():
    ср = sum(f(t) for t in стар) / len(стар)
    print('  %-10s %.3f на пункт  → на 280 пунктов нужно %d–%d'
          % (имя, ср, round(0.7 * ср * 280), round(1.35 * ср * 280)))
пары = collections.Counter()
for т in стар:
    for m in re.finditer(r'<a href="([^"]*)"[^>]*>(.*?)</a>', т):
        пары[(m.group(1), m.group(2))] += 1
print('\nанкеры типа, верх 16:')
for (h, t), n in пары.most_common(16):
    print('  <a href="%s">%s</a>  ×%d' % (h, t, n))
прор = collections.Counter(m.group(0) for т in стар for m in re.finditer(r'\{[^}]+\}', т))
print('\nпрорези:', ', '.join('%s×%d' % (k, v) for k, v in прор.most_common(12)))
print('\nразделы:')
for i, h2 in enumerate(разд):
    print('  %d: %s' % (i, h2))
