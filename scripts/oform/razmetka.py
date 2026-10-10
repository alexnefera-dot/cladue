#!/usr/bin/env python3
"""Собирает из плоского текста блоки шаблона: герой, колонки, витрину слотов,
джекпоты, ленту выплат, вопросы, призывы. Разметка — та же, что в размеченных
архивах, поэтому к ней подходят стили системы «витрина»."""
import html as H
import os, re, sys

ТЕГ = re.compile(r'(?is)<(h2|h3|p|ul|ol)\b[^>]*>(.*?)</\1>')
ССЫЛКА_БЛОК = re.compile(r'(?is)<p>\s*<a href="([^"]+)"[^>]*>\s*<h3>(.*?)</h3>\s*<p>(.*?)</p>\s*</a>\s*</p>')
КНОПКИ = ('Продолжить', 'Начать', 'Открыть', 'Играть', 'Играть на реальные деньги', 'Создать аккаунт',
          'Бонусы и промо', 'Активировать предложение', 'Смотреть', 'Войти', 'Забрать бонус', 'Регистрация')
ССЫЛКА_КНОПКИ = {'Продолжить': '/registracia', 'Начать': '/vhod', 'Открыть': '/registracia',
                 'Играть': '/slots', 'Играть на реальные деньги': '/registracia', 'Создать аккаунт': '/registracia',
                 'Бонусы и промо': '/bonus', 'Активировать предложение': '/promo', 'Смотреть': '/slots',
                 'Войти': '/vhod', 'Забрать бонус': '/bonus', 'Регистрация': '/registracia'}
ЭМОДЗИ = re.compile(r'^[\W\d_]{1,3}\s')
# Строка карточки слота. Имя слота бывает с четырёхзначного числа («2027 iss»),
# и такая строка подходила под зачин героя — бейдж забирал в иконку год слота.
# Полоса показателей: «<p><strong>4.8/5</strong></p><p>рейтинг выбора</p>» подряд.
# Значение и подпись — одна плитка. Порознь подпись похожа на кнопку и уезжала
# в жёлтую пилюлю, а значение оставалось висеть отдельной строкой над ней.
ЗНАЧЕНИЕ = re.compile(r'(?is)^\s*<!--знач-->\s*(.+?)\s*$')


def показатели(блоки, i):
    """Полоса «значение + подпись» с позиции i: [(значение, подпись)] и где она кончилась.

    Подпись без значения бывает — генератор теряет число («Игроков онлайн» без
    цифры). Такую плитку оставляем с одной подписью: выдумывать значение нельзя,
    выбрасывать текст тоже. Берём её только внутри уже начатой полосы, иначе под
    показатели уедет обычный абзац.
    """
    пары, j = [], i
    while j < len(блоки) and блоки[j][0] == 'p':
        м = ЗНАЧЕНИЕ.match(блоки[j][2])
        if м:
            след = блоки[j + 1] if j + 1 < len(блоки) else None
            if (след and след[0] == 'p' and not ЗНАЧЕНИЕ.match(след[2])
                    and подпись(след[1])):
                пары.append((м.group(1).strip(), след[1])); j += 2
            else:
                пары.append((м.group(1).strip(), '')); j += 1
            continue
        if пары and подпись(блоки[j][1]):
            пары.append(('', блоки[j][1])); j += 1
            continue
        break
    return пары, j


def подпись(t):
    return bool(t) and len(t) <= 44 and not re.search(r'[.!?:;]', t)


СТРОКА_СЛОТА = re.compile(r'(?i)^(?:Играйте в .{1,80} от |.{1,80} [-—–] популярный слот'
                         r'|Слот .{1,80} от провайдера)')
ДЖЕКПОТ = re.compile(r'Прогрессивные джекпоты\s*МЕГА\s*([\d\s ]+₽)\s*СУПЕР\s*([\d\s ]+₽)\s*МИНИ\s*([\d\s ]+₽)'
                     r'(?:\s*Последние выплаты\s*([А-ЯЁ][а-яё]+))?', re.U)
ВЫПЛАТА = re.compile(r'^([\d\s ]+₽)\s*(\S?)\s*(.+?)\s*(\d+\s*(?:мин|час|сек)[^\d]*)$', re.U)
СЛОТ = re.compile(r'^(.+?)\s*Активность 24ч\s*RTP\s*([\d.]+)%\s*(?:Играть\s*(.*))?$', re.U)
ЗНАЧОК = {'High': 'high', 'Medium': 'medium', 'Low': 'low'}


def текст(s):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', s)).strip()


def кнопки(строка):
    """«ПродолжитьНачать» → две кнопки; одиночная надпись → одна."""
    части = [x for x in re.split(r'(?<=[а-яё%])\s*(?=[А-ЯЁ])', строка.strip()) if x.strip()]
    вышло = []
    for i, ч in enumerate(части):
        ч = ч.strip(' .')
        if not ч:
            continue
        href = ССЫЛКА_КНОПКИ.get(ч, '/registracia' if i == 0 else '/slots')
        кл = 'btn-apple btn-apple-primary' if i == 0 else 'btn-apple btn-apple-secondary'
        вышло.append('<a class="%s" href="%s">%s</a>' % (кл, href, H.escape(ч)))
    return вышло


def это_кнопка(t):
    if len(t) > 46 or re.search(r'[.,!?:;—]', t) or not t:
        return False
    части = [x.strip() for x in re.split(r'(?<=[а-яё%])\s*(?=[А-ЯЁ])', t) if x.strip()]
    if not части or len(части) > 2:
        return False
    return all(re.match(r'^[А-ЯЁA-Z]', ч) and len(ч.split()) <= 3 for ч in части)


def не_кнопка_перед_слотом(t, перед_заголовком):
    """Строку перед заголовком в кнопку не превращаем, и подпись вида «HIGH RTP» тоже."""
    return not перед_заголовком and not ЗНАЧОК7.match(t)


def карточка_слота(имя, провайдер, rtp, значок):
    к = ЗНАЧОК.get(значок, 'medium')
    return ('<article class="slot-card"><div class="slot-card-inner">'
            '<div class="slot-poster"><div class="slot-poster-fallback">'
            '<span class="slot-fallback-icon">🎰</span><span class="slot-fallback-name">%s</span></div>'
            '<div class="slot-badge slot-badge-%s">%s</div></div>'
            '<div class="slot-info"><h3 class="slot-name">%s</h3><div class="slot-provider">%s</div></div>'
            '<div class="slot-footer"><div class="slot-rtp"><span class="slot-rtp-label">RTP</span>'
            '<span class="slot-rtp-value">%s%%</span></div>'
            '<a class="slot-play-btn" href="/slots">Играть</a></div>'
            '</div></article>') % (H.escape(имя), к, H.escape(значок or 'Medium'),
                                   H.escape(имя), H.escape(провайдер), rtp)


СЛОТ7 = re.compile(r'^RTP:?\s*([\d.]+)\s*%\s*(?:\d{4})?$', re.U)


ЗНАЧОК7 = re.compile(r'^[A-ZА-ЯЁ][A-ZА-ЯЁ0-9 ]{1,18}$')


def значок7(rtp, метка=''):
    в = метка.upper()
    if 'HIGH' in в or 'ТОП' in в:
        return 'High'
    if 'LOW' in в:
        return 'Low'
    r = float(rtp)
    return 'High' if r >= 96 else ('Medium' if r >= 94 else 'Low')


def как_абзац(блок):
    """Голый текст между тегами — тот же абзац.

    Часть выкачек не заворачивает строки витрины в <p>: «HIGH RTP» и «RTP: 96.5%2021»
    приходят текстом между тегами и попадают в блок «сырьё». Строгий шаг по трём блокам
    на них спотыкался, витрина не собиралась, и название провайдера уезжало в кнопку."""
    тег, текст, сырое = блок
    if тег == 'сырьё' and сырое and '<' not in сырое:
        return ('p', сырое.strip(), сырое.strip())
    return блок


def витрина7(блоки, i, n):
    """Четыре блока на слот: провайдер, имя, «RTP: N% год», описание.

    Отдаёт карточки, описания (их ставим абзацами под витриной, текст не теряем) и куда дошли."""
    карточки, описания, j = [], [], i
    while j + 2 < n:
        метка = ''
        if как_абзац(блоки[j])[0] == 'p' and ЗНАЧОК7.match(как_абзац(блоки[j])[1]):
            метка = как_абзац(блоки[j])[1]; j += 1   # «HIGH RTP» и прочие подписи перед слотом
            if j + 2 >= n:
                break
        пров, имя, rtp = как_абзац(блоки[j]), блоки[j + 1], как_абзац(блоки[j + 2])
        if пров[0] != 'p' or имя[0] != 'h3' or rtp[0] != 'p':
            break
        м = СЛОТ7.match(rtp[1])
        if not м or not пров[1] or len(пров[1].split()) > 4 or СЛОТ7.match(пров[1]):
            break
        карточки.append((имя[1], пров[1], м.group(1), значок7(м.group(1), метка)))
        j += 3
        след = как_абзац(блоки[j]) if j < n else None
        if след and след[0] == 'p' and not СЛОТ7.match(след[1]) and len(след[1].split()) > 4:
            описания.append(след[2])
            j += 1
    return карточки, описания, j


ОБЁРТКА = re.compile(r'(?is)<(h2|h3|p|li)>\s*<strong>(.*?)</strong>\s*</\1>')


def разобрать(html):
    """Файл → список блоков (тег, текст, сырое) плюс отдельно вынутые ссылки-карточки."""
    # Целиком полужирный абзац — это значение показателя. ОБЁРТКА ниже снимает
    # <strong>, поэтому метку ставим до неё; в текст блока она не попадает,
    # а в «сыром» остаётся, и по ней собирается полоса показателей.
    html = re.sub(r'(?is)<p>\s*<strong>([^<]{1,24})</strong>\s*</p>', r'<p><!--знач-->\1</p>', html)
    for _ in range(3):
        html, n = ОБЁРТКА.subn(r'<\1>\2</\1>', html)
        if not n:
            break
    # абзац, обёрнутый вокруг заголовка, — мусор разметки: снимаем вместе с парным закрытием
    html = re.sub(r'(?is)<p>\s*(?=<h[23]\b)', '', html)
    for _ in range(3):
        html, n = re.subn(r'(?is)</p>\s*</p>', '</p>', html)
        if not n:
            break
    ссылки = []

    def вынуть(m):
        заг = текст(m.group(2))
        # Подпись быстрой ссылки — короткая. Длинная означает незакрытый <a> в исходнике,
        # проглотивший целый раздел: такой кусок оставляем как есть.
        if len(заг) > 90:
            return m.group(0)
        ссылки.append((m.group(1), заг, текст(m.group(3))))
        return '\n<!--ссылка%d-->\n' % (len(ссылки) - 1)

    html = ССЫЛКА_БЛОК.sub(вынуть, html)
    блоки = []
    поз = 0
    for m in ТЕГ.finditer(html):
        между = html[поз:m.start()]
        for c in re.findall(r'<!--ссылка(\d+)-->', между):
            блоки.append(('ссылка', ссылки[int(c)], ''))
        остаток = re.sub(r'<!--ссылка\d+-->', '', между).strip()
        if остаток:
            блоки.append(('сырьё', '', остаток))
        блоки.append((m.group(1).lower(), текст(m.group(2)), m.group(2)))
        поз = m.end()
    хвост = html[поз:]
    for c in re.findall(r'<!--ссылка(\d+)-->', хвост):
        блоки.append(('ссылка', ссылки[int(c)], ''))
    остаток = re.sub(r'<!--ссылка\d+-->', '', хвост).strip()
    if остаток:
        блоки.append(('сырьё', '', остаток))
    return блоки


def собрать(блоки, стр):
    out = []
    i, n = 0, len(блоки)
    while i < n:
        тег, t, сырое = блоки[i]

        if тег == 'сырьё':
            out.append(сырое)
            i += 1
            continue

        # ---- быстрые ссылки «По этой теме»
        if тег == 'ссылка':
            груп = []
            while i < n and блоки[i][0] == 'ссылка':
                груп.append(блоки[i][1]); i += 1
            out.append('<nav class="quicklinks-grid">' + ''.join(
                '<a class="quicklink-item" href="%s"><span class="ql-icon">→</span>'
                '<span class="ql-text">%s</span><span class="ql-meta">%s</span></a>'
                % (a, H.escape(b), H.escape(c)) for a, b, c in груп) + '</nav>')
            continue

        # ---- герой: бейдж, заголовок, лид, признаки, кнопки
        if (тег == 'p' and re.match(r'^\d{4}\s+\w', t) and not СТРОКА_СЛОТА.match(t)
                and i + 1 < n and блоки[i + 1][0] == 'h2'):
            бейдж, заг = t, блоки[i + 1][1]
            j = i + 2
            лид = блоки[j][1] if j < n and блоки[j][0] == 'p' else ''
            if лид: j += 1
            черты = []
            if j < n and блоки[j][0] == 'ul':
                черты = [текст(x) for x in re.findall(r'(?is)<li>(.*?)</li>', блоки[j][2])]; j += 1
            кн = []
            if j < n and блоки[j][0] == 'p' and это_кнопка(блоки[j][1]):
                кн = кнопки(блоки[j][1]); j += 1
            out.append(
                '<section class="hero-value"><div class="hero-value-grid"><div class="hero-info">'
                '<div class="hero-badge"><span class="badge-icon">%s</span><span class="badge-text">%s</span></div>'
                '<h2 class="hero-headline">%s</h2><p class="hero-tagline">%s</p>'
                '<ul class="hero-features">%s</ul><div class="hero-actions">%s</div>'
                '</div></div></section>' % (
                    H.escape(бейдж.split()[0]), H.escape(' '.join(бейдж.split()[1:])),
                    H.escape(заг), H.escape(лид),
                    ''.join('<li><span class="feature-icon">%s</span><span>%s</span></li>'
                            % (H.escape(x[:2].strip() or '•'), H.escape(x[2:].strip() or x))
                            for x in черты),
                    ''.join(кн)))
            i = j
            continue

        # ---- колонки ценности: «Что даёт …» + пары h3/p
        if тег == 'h2' and t.startswith('Что даёт'):
            j = i + 1; колонки = []
            while j + 1 < n and блоки[j][0] == 'h3' and блоки[j + 1][0] == 'p' \
                    and not блоки[j][1].startswith('До конца'):
                колонки.append((блоки[j][1], блоки[j + 1][1])); j += 2
            if колонки:
                out.append('<section class="value-pillars"><h2 class="value-pillars-heading">%s</h2>'
                           '<div class="value-pillars-grid">%s</div></section>' % (
                               H.escape(t),
                               ''.join('<div class="value-pillar"><span class="value-pillar-icon">◆</span>'
                                       '<div class="value-pillar-body"><h3 class="value-pillar-title">%s</h3>'
                                       '<p class="value-pillar-desc">%s</p></div></div>'
                                       % (H.escape(a), H.escape(b)) for a, b in колонки)))
                i = j
                continue

        # ---- полоса обратного отсчёта
        if тег == 'h3' and t.startswith('До конца') and i + 1 < n and блоки[i + 1][0] == 'p':
            хвост = блоки[i + 1][1]
            m = re.match(r'^(.*?)(Активировать предложение)$', хвост)
            часы, кн = (m.group(1).strip(), m.group(2)) if m else (хвост, '')
            j = i + 2
            if not кн and j < n and блоки[j][0] == 'p' and это_кнопка(блоки[j][1]):
                кн = блоки[j][1]; j += 1
            out.append('<div class="cta-block"><span class="cta-icon">⏳</span>'
                       '<div class="cta-title">%s</div><p class="cta-subtitle">%s</p>%s</div>'
                       % (H.escape(t.rstrip(':')), H.escape(часы),
                          '<a class="btn btn-primary btn-lg" href="/promo">%s</a>' % H.escape(кн) if кн else ''))
            i = j
            continue

        # ---- витрина слотов: «Игровой каталог …» плюс карточки (два вида разметки)
        if тег == 'h2' and t.startswith('Игровой каталог'):
            j = i + 1
            под = ''
            if j < n and блоки[j][0] == 'p' and not СЛОТ.match(блоки[j][1]):
                под = блоки[j][1]; j += 1
            карточки, значок, имя, хвост = [], '', '', ''
            while j < n:
                тг, тx = блоки[j][0], блоки[j][1]
                if тг == 'p':
                    зн = re.match(r'^(.+?)\s+(High|Medium|Low)$', тx)
                    сл = СЛОТ.match(тx)
                    if сл and имя:
                        карточки.append((имя, сл.group(1).strip(), сл.group(2), значок or 'Medium'))
                        имя = ''; значок = ''; хвост = (сл.group(3) or '').strip()
                        сн = re.match(r'^(.*?)\s*(High|Medium|Low)$', хвост)
                        if сн: значок = сн.group(2); хвост = сн.group(1).strip()
                        j += 1
                        continue
                    if зн and not сл:
                        значок = зн.group(2); j += 1
                        continue
                    if тx in ('Играть', ''):
                        j += 1
                        continue
                    break
                if тг == 'h3':
                    имя = тx; j += 1
                    continue
                break
            if карточки:
                out.append('<section class="slots-dashboard"><div class="slots-dashboard-container">'
                           '<div class="slots-dashboard-header"><div class="slots-dashboard-title-wrap">'
                           '<span class="slots-dashboard-icon">🎲</span><div>'
                           '<h2 class="slots-dashboard-title">%s</h2><p class="slots-dashboard-subtitle">%s</p>'
                           '</div></div></div><div class="slots-grid">%s</div></div></section>'
                           % (H.escape(t), H.escape(под), ''.join(карточка_слота(*к) for к in карточки)))
                if хвост:
                    блоки[j - 1] = ('p', хвост, хвост)   # джекпоты приклеены к последней карточке
                    j -= 1
                i = j
                continue

        # ---- витрина слотов семистраничных: провайдер, имя, «RTP: N% год», описание
        if тег == 'h2':
            карточки, описания, j = витрина7(блоки, i + 1, n)
            под = ''
            if len(карточки) < 2:
                вторые, оп2, j2 = витрина7(блоки, i + 2, n)
                if len(вторые) >= 2 and блоки[i + 1][0] == 'p':
                    карточки, описания, j, под = вторые, оп2, j2, блоки[i + 1][1]
            if len(карточки) >= 2:
                out.append('<section class="slots-dashboard"><div class="slots-dashboard-container">'
                           '<div class="slots-dashboard-header"><div class="slots-dashboard-title-wrap">'
                           '<span class="slots-dashboard-icon">🎲</span><div>'
                           '<h2 class="slots-dashboard-title">%s</h2><p class="slots-dashboard-subtitle">%s</p>'
                           '</div></div></div><div class="slots-grid">%s</div></div></section>'
                           % (H.escape(t), H.escape(под), ''.join(карточка_слота(*к) for к in карточки)))
                out += ['<p>%s</p>' % о for о in описания]
                i = j
                continue

        # ---- джекпоты и лента выплат
        м = ДЖЕКПОТ.search(t) if тег == 'p' else None
        if м:
            до = t[:м.start()].strip()
            if до:
                out.append('<p>%s</p>' % H.escape(до))
            имена = [м.group(4)] if м.group(4) else []
            j = i + 1; суммы = []
            while j < n and блоки[j][0] == 'p':
                в = ВЫПЛАТА.match(блоки[j][1])
                if в:
                    суммы.append((в.group(1).strip(), в.group(2), в.group(3).strip(), в.group(4).strip())); j += 1
                    continue
                if len(блоки[j][1].split()) <= 2 and re.match(r'^[А-ЯЁ][а-яё]+$', блоки[j][1]):
                    имена.append(блоки[j][1]); j += 1
                    continue
                break
            ячейки = ''.join(
                '<div class="jackpot-cell%s"><span class="jackpot-cell-icon">%s</span>'
                '<div class="jackpot-cell-info"><span class="jackpot-cell-name">%s</span>'
                '<span class="jackpot-cell-amount">%s</span></div></div>'
                % (' jackpot-cell-pulse' if k == 0 else '', и, п, H.escape(с.strip()))
                for k, (п, и, с) in enumerate(zip(('МЕГА', 'СУПЕР', 'МИНИ'), ('🏆', '💎', '⭐'),
                                                  (м.group(1), м.group(2), м.group(3)))))
            строки = ''.join(
                '<div class="payout-row payout-row-%s"><span class="payout-row-icon">%s</span>'
                '<span class="payout-row-name">%s</span><span class="payout-row-sep">—</span>'
                '<span class="payout-row-amount">%s</span><span class="payout-row-slot">%s</span>'
                '<span class="payout-row-time">%s</span></div>'
                % ('big' if k % 3 == 2 else 'normal', и or '🎰', H.escape(имена[k] if k < len(имена) else 'Игрок'),
                   H.escape(с), H.escape(г), H.escape(вр))
                for k, (с, и, г, вр) in enumerate(суммы))
            кн = ''
            if j < n and блоки[j][0] == 'p' and это_кнопка(блоки[j][1]):
                кн = '<div class="payout-cta"><a class="payout-btn" href="/registracia">%s</a></div>' % H.escape(блоки[j][1]); j += 1
            out.append('<section class="recent-payouts-block"><div class="jackpot-strip">'
                       '<div class="jackpot-strip-title"><span class="jackpot-strip-icon">◆</span>'
                       '<span>Прогрессивные джекпоты</span></div>'
                       '<div class="jackpot-strip-grid">%s</div></div>'
                       '<div class="payout-feed"><div class="payout-feed-header">'
                       '<span class="payout-feed-dot"></span><span class="payout-feed-title">Последние выплаты</span>'
                       '</div><div class="payout-track"><div class="payout-scroll">%s</div></div>%s</div></section>'
                       % (ячейки, строки, кн))
            i = j
            continue

        # ---- карточка-призыв: заголовок с эмодзи и следом абзацы с эмодзи
        if тег == 'h3' and ЭМОДЗИ.match(t) and i + 1 < n and блоки[i + 1][0] == 'p' and ЭМОДЗИ.match(блоки[i + 1][1]):
            j = i + 1; строки = []
            while j < n and блоки[j][0] == 'p' and ЭМОДЗИ.match(блоки[j][1]):
                строки.append(блоки[j][1]); j += 1
            out.append('<div class="cta-block"><span class="cta-icon">%s</span>'
                       '<div class="cta-title">%s</div>%s</div>'
                       % (H.escape(t[:2].strip()), H.escape(t[2:].strip()),
                          ''.join('<p class="cta-trust">%s</p>' % H.escape(x) for x in строки)))
            i = j
            continue

        # ---- вопросы и ответы: заголовок раздела и пары h3/p
        if тег == 'h2' and (t.startswith('❓') or t.startswith('Частые вопросы') or t.startswith('О портале')):
            j = i + 1; под = ''
            if j < n and блоки[j][0] == 'p' and not ЭМОДЗИ.match(блоки[j][1]) and len(блоки[j][1].split()) < 14:
                под = блоки[j][1]; j += 1
            пары = []
            while j + 1 < n and блоки[j][0] == 'h3' and блоки[j + 1][0] == 'p':
                пары.append((блоки[j][1], блоки[j + 1][2])); j += 2
            if пары:
                out.append('<div class="faq-section glass-card"><h2 class="gradient-text">%s</h2>%s'
                           '<div class="faq-list">%s</div></div>'
                           % (H.escape(t), '<p>%s</p>' % H.escape(под) if под else '',
                              ''.join('<div class="faq-item%s"><h3 class="faq-question">%s</h3>'
                                      '<div class="faq-answer"><p>%s</p></div></div>'
                                      % (' open' if k == 0 else '', H.escape(в), о)
                                      for k, (в, о) in enumerate(пары))))
                i = j
                continue

        # ---- финальный призыв: «… — начни играть» плюс кнопки
        if тег == 'h2' and ('начни играть' in t or 'начни выигрывать' in t):
            j = i + 1; текстик = ''
            if j < n and блоки[j][0] == 'p' and not это_кнопка(блоки[j][1]):
                текстик = блоки[j][1]; j += 1
            кн = []
            if j < n and блоки[j][0] == 'p' and это_кнопка(блоки[j][1]):
                кн = кнопки(блоки[j][1]); j += 1
            out.append('<div class="cta-block"><span class="cta-icon">🚀</span>'
                       '<div class="cta-title">%s</div><p class="cta-subtitle">%s</p>'
                       '<div class="hero-actions">%s</div></div>'
                       % (H.escape(t), H.escape(текстик), ''.join(кн)))
            i = j
            continue

        # ---- абзац, в котором только ссылки: ряд кнопок с их же адресами
        if тег == 'p' and re.search(r'(?is)<a\b', сырое) \
                and re.sub(r'(?is)<a[^>]*>.*?</a>', '', сырое).strip() == '':
            пары = re.findall(r'(?is)<a href="([^"]+)"[^>]*>(.*?)</a>', сырое)
            out.append('<div class="hero-actions">%s</div>' % ''.join(
                '<a class="btn-apple btn-apple-%s" href="%s">%s</a>'
                % ('primary' if k == 0 else 'secondary', a, H.escape(текст(b)))
                for k, (a, b) in enumerate(пары)))
            i += 1
            continue

        # ---- полоса показателей: значение и подпись в одной плитке
        if тег == 'p' and ЗНАЧЕНИЕ.match(сырое):
            пары, j = показатели(блоки, i)
            if len(пары) >= 3:
                out.append('<div class="stats-grid">%s</div>' % ''.join(
                    '<div class="stat-card%s">%s%s</div>'
                    % ('' if з else ' stat-card-text',
                       '<span class="stat-value">%s</span>' % H.escape(з) if з else '',
                       '<span class="stat-label">%s</span>' % H.escape(п) if п else '')
                    for з, п in пары))
                i = j
                continue

        # ---- одиночная строка-кнопка
        # Строка перед заголовком — надзаголовок списка (название провайдера, «HIGH RTP»),
        # а не призыв к действию: кнопкой она быть не может. Так из витрины слотов,
        # которую не удалось собрать, получались огромные пилюли вместо списка.
        перед_заголовком = i + 1 < n and как_абзац(блоки[i + 1])[0] in ('h2', 'h3')
        if тег == 'p' and не_кнопка_перед_слотом(t, перед_заголовком) and это_кнопка(t):
            out.append('<div class="hero-actions">%s</div>' % ''.join(кнопки(t)))
            i += 1
            continue

        # ---- всё остальное как было
        out.append('<%s>%s</%s>' % (тег, сырое, тег))
        i += 1
    return '\n'.join(out).replace('<!--знач-->', '') + '\n'


def обработать(файл):
    стр = os.path.basename(файл)[:-5]
    html = open(файл, encoding='utf-8').read()
    новое = собрать(разобрать(html), стр)
    open(файл, 'w', encoding='utf-8').write(новое)
    return len(re.findall(r'class="(?:hero-value|value-pillars|slots-dashboard|recent-payouts-block|faq-section|cta-block|quicklinks-grid|stats-grid)"', новое))


if __name__ == '__main__':
    корень = sys.argv[1]
    всего = блоков = 0
    for путь, _, файлы in os.walk(корень):
        for f in sorted(файлы):
            if f.endswith('.html'):
                блоков += обработать(os.path.join(путь, f)); всего += 1
    print('страниц %d, собрано блоков %d' % (всего, блоков))
