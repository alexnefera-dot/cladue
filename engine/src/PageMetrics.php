<?php
declare(strict_types=1);

require_once __DIR__ . '/Analyzer.php';
require_once __DIR__ . '/NicheLexicon.php';

/**
 * Мерка одной страницы — та самая, по которой идёт приёмка.
 *
 * Живёт отдельно, потому что у неё два потребителя: приёмка (check-oldstyle)
 * и отчёты для человека. Считай они по своим копиям кода, отчёт однажды
 * показал бы «всё сходится» там, где приёмка видит промах, — на этом проекте
 * такое уже случалось, и каждый раз причиной была расходящаяся мерка.
 */
final class PageMetrics
{
    /** поле => [подпись, дробное ли значение]; последние пять — блок сигналов */
    public const FIELDS = [
        'words' => ['объём слов', 0], 'h2' => ['H2', 0], 'sections' => ['разделов H2+H3', 0],
        'lists' => ['списков', 0], 'strong' => ['strong', 0], 'faq' => ['вопросительных знаков', 0],
        'emoji' => ['эмодзи', 0], 'first_person' => ['«я»', 0], 'vy' => ['«вы»', 0],
        'ty' => ['«ты»', 0],
        'on_topic_pct' => ['заголовков по теме страницы %', 1],
        'speech' => ['реплик в кавычках', 0],
        'compare' => ['бытовых сравнений', 0],
        'myth' => ['зачинов «а на деле»', 0],
        'insider' => ['заявок на закрытое знание', 0],
        'letter' => ['шаблонов обращения', 0],
        'imperatives' => ['императивов', 0], 'numbers_per100' => ['цифр на 100 слов', 1],
        'adj_pct' => ['прилагательных %', 1], 'nausea_acad' => ['тошнота %', 1], 'water' => ['водность %', 1],
        'brand_ru' => ['бренд кириллицей', 0], 'brand_en' => ['бренд латиницей', 0],
        // Общий счёт бренда сходился, а расположение расходилось: у образца
        // имя стоит в заголовках главной и густо идёт в начале страницы, у
        // повторов — размазано ровным слоем. Сумма этого не показывает.
        'brand_in_h' => ['бренд в заголовках', 0],
        'brand_first_third' => ['бренд в первой трети', 0],
        // Приём, который пятнадцать наборов подряд не воспроизвели ни разу:
        // у всех восьми образцов на связку приходится 50–75 пар «вопрос-ответ»,
        // у нас ноль. Не заметили потому, что прежний счётчик вопросов смотрел
        // на текст глазами парсера, а тот не видит блоки FAQ в <div>: на главной
        // образца 16 вопросов, счётчик показывал 3. Эти два считаются по всему
        // тексту страницы.
        'faq_pairs' => ['пар «вопрос-ответ»', 0],
        'questions_total' => ['вопросов в тексте', 0],
        // Опорные формулы и зачин — защита от «синонимизации ради тошноты»:
        // плотность лексики у нас совпадала с образцом, а повтор уходил на
        // служебные слова вместо ключей темы.
        'anchors' => ['опорных формул', 0],
        'opener_name' => ['зачин: имя с категорией', 1],
        'opener_key' => ['зачин: ключ в начале', 1],
        // Число таблиц мы воспроизводили, а таблица выходила другим объектом:
        // у образцов шестнадцать таблиц — шестнадцать разных шапок и три
        // колонки, третья под оценку или сравнение; у нас «Параметр | Значение»
        // сорок три раза на пять наборов и две колонки.
        'table_cols' => ['колонок в таблице', 1],
        'table_uniq_pct' => ['уникальных шапок %', 1],
        // Отзыв с именем, датой и оценкой 1–5. Приём распределяет роли: минус
        // называет не автор, а игрок с оценкой «три из пяти», и автору не
        // приходится критиковать площадку самому. У нас вместо этого цитата с
        // подписью через тире — без оценки и без разметки.
        'reviews_rated' => ['отзывов с оценкой', 0],
        // Все восемь образцов держат 21–42% нумерованных списков: в <ol> идёт
        // порядок действий, в <ul> — перечень без порядка. Наши наборы, все
        // девять семейств подряд, дали 0–2%: счётчик списков складывал ul и ol
        // в одно число, и тип никогда не проверялся.
        'ordered_pct' => ['нумерованных списков %', 1],
        // У образцов три четверти анкоров встречаются ровно один раз: анкор —
        // это слово внутри предложения, в нужном падеже («регистрацию»,
        // «зарегистрировался», «зеркальную ссылку»). У нас — четверть: промпт
        // задаёт анкоры списком с кратностью, и они вставляются словарной
        // формой. Список промпта — это минимальный словарь, а не разнарядка.
        'anchor_once_pct' => ['разовых анкоров %', 1],
        // Ловушка среднего: длина абзаца у нас совпадала с образцом до десятой
        // доли, а разброс был вдвое меньше. У образца абзацы от шести слов до
        // ста сорока — короткая реплика рядом с развёрнутой мыслью; у нас все
        // ровно по средней. Считаем и разброс, и края.
        // Жирным образец открывает пункт — «В надежности:», «Лимиты депозитов:»
        // — а мы выделяем кусок внутри фразы. Эмодзи у образца стоит маркером в
        // начале пункта и почти никогда в заголовке или посреди предложения.
        // H3 совпадали по числу и длине, а строились иначе: у образца четверть
        // подзаголовков начинается вопросительным словом («Что делать, если…»,
        // «Почему выплата идёт дольше»), а двоеточие — примерно в трети. У нас
        // наоборот: двоеточие в двух третях, вопросительных вдвое меньше.
        // Все пять образцов открываются одинаково: абзац с именем, второй
        // абзац, затем список-оглавление с эмодзи-маркерами. Карточка при этом
        // писала «сразу заголовок H2, без списка-паспорта» — проверка искала
        // <ul> в самом начале файла, а он третьим блоком, и всегда отвечала
        // «нет». Приём был не просто не замечен, а прямо запрещён.
        // Словарь фактов. У образцов на весь набор два-шесть разных значений
        // отдачи, и они повторяются; у нас семь-тринадцать — под каждое
        // упоминание своё число. Читатель у образца видит одну и ту же цифру,
        // у нас каждый раз новую.
        'fact_values' => ['разных значений с %', 0],
        'lead_list' => ['список в зачине', 1],
        'h2_opens_para_pct' => ['раздел открыт абзацем %', 1],
        'h3_question_pct' => ['H3 с вопросительного слова %', 1],
        'h3_colon_pct' => ['H3 с двоеточием %', 1],
        'strong_lead_pct' => ['strong в начале блока %', 1],
        'emoji_inline' => ['эмодзи внутри фразы', 0],
        'para_spread' => ['разброс длины абзаца', 1],
        'para_short' => ['коротких абзацев', 0],
        'paragraphs' => ['абзацев', 0], 'words_per_para' => ['слов в абзаце', 1],
        'games_named' => ['названий игр', 0], 'providers_named' => ['названий студий', 0],
        'names_uniq' => ['разных имён игр и студий', 0],
        'terms_total' => ['профильных терминов', 0],
        'h3_per_h2'  => ['H3 на один H2', 1],
        'h2_len'     => ['слов в заголовке', 1],
        'h2_quest'   => ['заголовков-вопросов %', 1],
        'cta'        => ['прямых призывов', 0],
        'honest'     => ['мест с минусом или риском', 0],
    ];

    public const SIGNALS = ['h3_per_h2', 'h2_len', 'h2_quest', 'cta', 'honest'];

    /**
     * Опорные формулы ниши. Список не выдуман: это словосочетания, которые
     * нашлись у ВСЕХ восьми образцов корпуса при поиске общих n-грамм, — то
     * есть скелет жанра, не зависящий от того, дневник это или реклама. Наши
     * наборы держали их на 30–50% от образца, заменяя синонимами ради тошноты:
     * «игровые автоматы» становились «слотами», «бонусы» — «поощрениями».
     */
    public const ANCHORS = [
        '~\bофициальн\w+ сайт~ui',
        '~\bигров\w+ автомат~ui',
        '~\bбонус\w*\s+и\s+промокод~ui',
        '~\bможно ли\b~ui',
        '~\bличн\w+ кабинет~ui',
        '~\bзеркал\w+ сайт~ui',
        '~\bвывод\w*\s+средств~ui',
        '~\bответы на\b~ui',
        '~\bвход в\b~ui',
    ];

    public static function fields(bool $withSignals): array
    {
        $f = self::FIELDS;
        if (!$withSignals) { foreach (self::SIGNALS as $k) { unset($f[$k]); } }
        return $f;
    }

    /** Коридор: |наше − образец| ≤ max(25% образца, 2) для счётных и 0.8 для долей. */
    public static function off($our, $ref, bool $rate): bool
    {
        return abs($our - $ref) > max(0.25 * max(abs($ref), 1), $rate ? 0.8 : 2.0);
    }

    /**
     * @param array $brand ['ru' => 'Настоящее имя', 'en' => 'Real Name'] — для
     *   сохранённых страниц, где бренд написан именем, а не плейсхолдером.
     */
    /** Слова, которыми называется тема каждого типа страницы. */
    private const TOPICS = [
        'bonus'       => ['бонус', 'промокод', 'фрисп', 'акци', 'кэшбэк', 'подар', 'отыгрыш', 'вейджер', 'множител'],
        'app'         => ['прилож', 'скача', 'андроид', 'android', 'ios', 'айфон', 'мобильн', 'apk', 'устройств', 'программ'],
        'zerkalo'     => ['зеркал', 'блокиров', 'обход', 'доступ', 'vpn', 'домен', 'адрес', 'ссылк'],
        'vhod'        => ['вход', 'войти', 'логин', 'личн', 'кабинет', 'парол', 'авториз', 'сесси'],
        'registracia' => ['регистр', 'аккаунт', 'верификац', 'анкет', 'профил', 'документ'],
        'slots'       => ['слот', 'автомат', 'игров', 'каталог', 'провайдер', 'rtp', 'отдач', 'волатильн', 'ставк', 'раунд'],
    ];

    public static function measure(Analyzer $a, string $type, string $raw, array $brand = ['ru' => '', 'en' => '']): array
    {
        $norm = NicheLexicon::unplaceholder($raw);
        $r = $a->run([['name' => $type, 'url' => "/$type", 'html' => $norm, 'keyword' => '', 'lsi' => []]]);
        $m = $r['pages'][0]['metrics']; $s = $r['pages'][0]['stylistics'];

        // Абзацы выбираются по СЫРОМУ html: отсечка в 40 символов должна
        // отбрасывать подписи-чипы, а после подстановки бренда они удлиняются.
        preg_match_all('~<p\b[^>]*>(.*?)</p>~is', $raw, $pm);
        $ps = array_values(array_filter(
            array_map(fn($x) => trim(preg_replace('~\s+~u', ' ', strip_tags($x))), $pm[1] ?? []),
            fn($x) => mb_strlen($x) > 40
        ));
        $wp = 0;
        foreach ($ps as $x) { $wp += count(preg_split('~\s+~u', NicheLexicon::unplaceholder($x), -1, PREG_SPLIT_NO_EMPTY)); }

        $prose = NicheLexicon::prose($norm);
        $flat  = trim(preg_replace('~\s+~u', ' ', strip_tags($norm)));

        $hs = [];
        if (preg_match_all('~<h2[^>]*>(.*?)</h2>~is', $norm, $hm)) {
            foreach ($hm[1] as $h) {
                $x = trim(preg_replace('~\s+~u', ' ', strip_tags($h)));
                if ($x !== '') { $hs[] = $x; }
            }
        }
        $h3n = preg_match_all('~<h3[^>]*>~i', $norm);

        // Где стоит бренд. Считается по СЫРОМУ тексту: у нас это плейсхолдеры,
        // у сохранённого образца — настоящее имя, и обе формы надо ловить.
        $brandRe = '~%brand_name_(?:ru|en)%'
            . ($brand['ru'] !== '' ? '|' . preg_quote($brand['ru'], '~') : '')
            . ($brand['en'] !== '' ? '|' . preg_quote($brand['en'], '~') : '') . '~ui';
        $noScript = preg_replace('~<script\b.*?</script>~is', '', $raw);
        $inH = 0;
        if (preg_match_all('~<h[23][^>]*>(.*?)</h[23]>~is', $noScript, $hh)) {
            foreach ($hh[1] as $x) { $inH += preg_match_all($brandRe, $x); }
        }
        // «Первая часть» — первая треть текста по словам, а не по длине html:
        // разметка распределена неравномерно и сдвигала бы границу.
        $words = preg_split('~\s+~u', trim(preg_replace('~\s+~u', ' ', strip_tags($noScript))), -1, PREG_SPLIT_NO_EMPTY);
        $head  = implode(' ', array_slice($words, 0, max(1, (int) (count($words) / 3))));

        // Пары «вопрос-ответ». Сначала по микроразметке — так их размечают
        // образцы; если её нет, по структуре: заголовок или термин, который
        // кончается вопросительным знаком.
        $faqPairs = preg_match_all('~itemtype="https?://schema\.org/[Qq]uestion"~', $noScript);
        if ($faqPairs === 0) {
            $faqPairs = preg_match_all('~<(h[2-4]|dt|strong)\b[^>]*>[^<]*\?\s*</\1>~iu', $noScript);
        }
        $fullText = trim(preg_replace('~\s+~u', ' ', strip_tags($noScript)));

        $anchors = 0;
        foreach (self::ANCHORS as $re) { $anchors += preg_match_all($re, $fullText); }

        // ── Приёмы голоса ────────────────────────────────────────────────
        // Шесть ходов по отношению к читателю. Раньше они считались только в
        // priyomy.php — каталоге «чем текст действует», который никогда не был
        // приёмочным. Из-за этого пятнадцать наборов подряд писались ровным
        // консультантским тоном, а образец в это время говорил с читателем
        // совсем иначе, и расхождение не попадало ни в один замер.
        //
        // Важно: это НЕ общие черты корпуса. «Свой человек в индустрии» есть
        // только у set242 (3.35 на 1000 слов) и ровно ноль у остальных восьми;
        // обращение на «ты» делит корпус надвое — 0.3–2.0 у четырёх наборов и
        // 14–29 у четырёх других. Поэтому цель берётся из КОНКРЕТНОГО образца,
        // под который пишется карточка, а не усредняется по корпусу.
        $ty = preg_match_all('~\b(ты|тебе|тебя|тобой|твой|твоя|твоё|твои|твоего|твоей|твоих|твоим)\b'
            . '|\b\w+(?:ешь|ишь)\b~ui', $fullText);

        // Держится ли страница своей темы. У образца заголовки регулярно уходят
        // в сторону: slots.html говорит о краш-играх, app.html — о лимитах
        // ответственной игры. Мы держим тему строго по имени файла, и это
        // расхождение не ловил ни один счётчик: линейка меряет плотности, а не
        // то, О ЧЁМ текст. Считаем долю заголовков страницы, где встретилось
        // слово её собственной темы.
        $onTopic = 0.0;
        if (!empty(self::TOPICS[$type])) {
            preg_match_all('~<h[23][^>]*>(.*?)</h[23]>~is', $noScript, $hm2);
            $heads = array_filter(array_map(
                fn($x) => mb_strtolower(trim(preg_replace('~\s+~u', ' ', strip_tags($x)))),
                $hm2[1] ?? []));
            if ($heads) {
                $hit = 0;
                foreach ($heads as $h) {
                    foreach (self::TOPICS[$type] as $w) {
                        if (mb_strpos($h, $w) !== false) { $hit++; break; }
                    }
                }
                $onTopic = round($hit / count($heads) * 100, 1);
            }
        }

        // Форма таблицы: сколько колонок и повторяется ли шапка. Шапкой считаем
        // строку <th>, а где её нет — первую строку таблицы.
        $cols = []; $headers = [];
        if (preg_match_all('~<table\b.*?</table>~is', $noScript, $tm2)) {
            foreach ($tm2[0] as $tbl) {
                preg_match_all('~<th\b[^>]*>(.*?)</th>~is', $tbl, $th);
                $cells = $th[1];
                if (!$cells && preg_match('~<tr\b.*?</tr>~is', $tbl, $fr)) {
                    preg_match_all('~<td\b[^>]*>(.*?)</td>~is', $fr[0], $td);
                    $cells = $td[1];
                }
                if (!$cells) { continue; }
                $cols[] = count($cells);
                $headers[] = mb_strtolower(implode('|', array_map(
                    fn($c) => trim(preg_replace('~\s+~u', ' ', strip_tags($c))), $cells)));
            }
        }

        // Зачин: у всех восьми образцов первое предложение — имя бренда с
        // категорией, а «официальный сайт» стоит в первых полусотне слов.
        $first50 = implode(' ', array_slice(preg_split('~\s+~u', $fullText, -1, PREG_SPLIT_NO_EMPTY), 0, 50));
        $nameRe  = '~^\s*(?:казино\s+|casino\s+)?(?:%brand_name_(?:ru|en)%'
            . ($brand['ru'] !== '' ? '|' . preg_quote($brand['ru'], '~') : '')
            . ($brand['en'] !== '' ? '|' . preg_quote($brand['en'], '~') : '')
            . ')(?:\s+(?:казино|casino))?\s*[.!:—-]~ui';

        return [
            'brand_in_h' => $inH,
            'brand_first_third' => preg_match_all($brandRe, $head),
            'faq_pairs' => $faqPairs,
            'questions_total' => substr_count($fullText, '?'),
            'anchors' => $anchors,
            'ty' => $ty,
            'on_topic_pct' => $onTopic,
            // Реплика в кавычках отдельной единицей: «Мои люди в индустрии
            // говорят, что…». Короткие кавычки («Регистрация», «Лимиты») не
            // считаются — порог в 25 символов отделяет реплику от названия.
            'speech' => preg_match_all('~[«"][^«»"]{25,}[»"]~u', $fullText),
            // Бытовое сравнение: механика объясняется через предмет из быта.
            'compare' => preg_match_all('~(это как\b|как в\s+\w+е\b|словно\b|похоже на\b'
                . '|представь\w*|вроде как|тот же принцип|устроен\w* так же)~ui', $fullText),
            // Зачин «вы думаете X, а на деле Y»: сначала названо ожидание
            // читателя, потом сбито. У образца это способ открыть страницу.
            'myth' => preg_match_all('~(многие думают|принято считать|кажется, что|на первый взгляд'
                . '|вопреки расхожему|распространённое заблуждение|знаете,|казалось бы)~ui', $fullText),
            // Заявка на закрытое знание. Ход спорный по существу, но он есть в
            // образце, а цель — воспроизвести, а не улучшить.
            'insider' => preg_match_all('~(мои люди|свои люди|«свои» люди|своих людей|от своих'
                . '|в индустрии (?:говорят|слышал|знают)|не принято (?:писать|говорить) вслух'
                . '|за кулисами|инсайдер\w*|не все знают|мало кто (?:знает|замечает)|по слухам'
                . '|внутри индустрии|остаётся за кадром)~ui', $fullText),
            // Готовый текст обращения с полями для подстановки.
            'letter' => preg_match_all('~(\[номер\]|\[дата|№\s*\[|тело письма|шаблон обращения'
                . '|текст обращения|прошу проверить и дать|ticket id)~ui', $fullText),
            'opener_name' => preg_match($nameRe, $fullText) ? 1 : 0,
            'opener_key' => preg_match('~официальн~ui', $first50) ? 1 : 0,
            'table_cols' => $cols ? round(array_sum($cols) / count($cols), 1) : 0,
            'table_uniq_pct' => $headers ? round(count(array_unique($headers)) / count($headers) * 100, 1) : 0,
            // По разметке, а где её нет — по формуле «Имя / дата / оценка»
            'anchor_once_pct' => (function () use ($noScript) {
                if (!preg_match_all('~<a\b[^>]*>(.*?)</a>~is', $noScript, $am)) { return 0; }
                $c = [];
                foreach ($am[1] as $x) {
                    $t = mb_strtolower(trim(preg_replace('~\s+~u', ' ', strip_tags($x))));
                    if ($t !== '') { $c[$t] = ($c[$t] ?? 0) + 1; }
                }
                if (!$c) { return 0; }
                return round(count(array_filter($c, fn($n) => $n === 1)) / count($c) * 100, 1);
            })(),
            'ordered_pct' => (function () use ($noScript) {
                $ol = preg_match_all('~<ol\b~i', $noScript);
                $ul = preg_match_all('~<ul\b~i', $noScript);
                return $ol + $ul ? round($ol / ($ol + $ul) * 100, 1) : 0;
            })(),
            'reviews_rated' => preg_match_all('~itemtype="https?://schema\.org/Comment"~i', $noScript)
                ?: preg_match_all('~[А-ЯЁ][а-яё]{2,}\s*/\s*[^/<>]{0,24}/\s*[1-5]\b~u', $fullText),
            'h3_per_h2' => $hs ? round($h3n / count($hs), 1) : 0,
            'h2_len' => $hs ? round(array_sum(array_map(fn($x) => count(preg_split('~\s+~u', $x, -1, PREG_SPLIT_NO_EMPTY)), $hs)) / count($hs), 1) : 0,
            'h2_quest' => $hs ? round(count(array_filter($hs, fn($x) => mb_strpos($x, '?') !== false)) / count($hs) * 100, 1) : 0,
            'cta' => preg_match_all('~\b(зарегистрируйся|играй|жми|получи|забери|активируй|скачай|попробуй|переходи|успей)\b~ui', $flat),
            'honest' => preg_match_all('~\b(минус\w*|недостат\w*|риск\w*|осторожн\w*|не советую|не стоит|проигр\w*|потер\w*|обман\w*|развод\w*|ловушк\w*|подвох\w*|честно говоря|на самом деле|важно понимать)\b~ui', $flat),
            'words' => (int) $m['words_total'], 'h2' => (int) $m['h2_count'],
            'sections' => (int) ($m['h2_count'] + ($m['h3_count'] ?? 0)),
            'lists' => (int) $m['list_count'], 'strong' => (int) $m['strong_count'],
            'faq' => (int) $s['faq_questions'], 'emoji' => (int) $s['emoji'],
            'first_person' => (int) $s['first_person'], 'vy' => (int) $s['second_person'],
            'imperatives' => (int) $s['imperatives'],
            'numbers_per100' => round((float) $s['numbers_per_100w'], 1),
            'adj_pct' => round((float) $s['adj_pct'], 1),
            'nausea_acad' => round((float) $m['nausea_academic'], 1),
            'water' => round((float) $m['water_percent'], 1),
            // Плейсхолдер у нас, настоящее имя у сохранённого референса.
            'brand_ru' => substr_count($raw, '%brand_name_ru%') ?: ($brand['ru'] !== '' ? mb_substr_count(strip_tags($raw), $brand['ru']) : 0),
            'brand_en' => substr_count($raw, '%brand_name_en%') ?: ($brand['en'] !== '' ? mb_substr_count(strip_tags($raw), $brand['en']) : 0),
            'paragraphs' => count($ps),
            'fact_values' => (function () use ($fullText) {
                preg_match_all('~\d{1,3}[.,]\d\s*%~u', $fullText, $fm);
                return count(array_unique($fm[0] ?? []));
            })(),
            // Чем ОТКРЫВАЕТСЯ раздел. У девяти образцов после H2 ни разу — ни
            // одного раза на 283 заголовка — не стоит список: сначала абзац,
            // который вводит в тему, и только потом перечень. У нас раздел
            // начинается со списка в каждом пятом случае. Обёртки div
            // пропускаем: это вёрстка, а не решение о тексте.
            'h2_opens_para_pct' => (function () use ($noScript) {
                preg_match_all('~<(h2|h3|p|ul|ol|table|blockquote|dl)\b~i', $noScript, $bm);
                $seq = array_map('strtolower', $bm[1] ?? []);
                $tot = 0; $para = 0;
                for ($i = 0; $i < count($seq) - 1; $i++) {
                    if ($seq[$i] !== 'h2') { continue; }
                    $tot++;
                    if ($seq[$i + 1] === 'p') { $para++; }
                }
                return $tot ? round($para / $tot * 100, 1) : 0;
            })(),
            'lead_list' => (function () use ($noScript) {
                preg_match_all('~<(h2|h3|p|ul|ol|table|blockquote|dl)\b~i', $noScript, $bm);
                $first = array_map('strtolower', array_slice($bm[1] ?? [], 0, 4));
                return (in_array('ul', $first, true) || in_array('ol', $first, true)) ? 1 : 0;
            })(),
            'h3_question_pct' => (function () use ($noScript) {
                if (!preg_match_all('~<h3\b[^>]*>(.*?)</h3>~is', $noScript, $h3m)) { return 0; }
                $tot = 0; $q = 0;
                foreach ($h3m[1] as $x) {
                    $t = preg_replace('~^[^\w%]+~u', '', trim(preg_replace('~\s+~u', ' ', strip_tags($x))));
                    if ($t === '') { continue; }
                    $tot++;
                    if (preg_match('~^(что|как|почему|где|когда|сколько|кто|куда|можно|зачем|нужно ли|стоит ли|чем)\b~ui', $t)) { $q++; }
                }
                return $tot ? round($q / $tot * 100, 1) : 0;
            })(),
            'h3_colon_pct' => (function () use ($noScript) {
                if (!preg_match_all('~<h3\b[^>]*>(.*?)</h3>~is', $noScript, $h3m)) { return 0; }
                $tot = 0; $c = 0;
                foreach ($h3m[1] as $x) {
                    $t = trim(preg_replace('~\s+~u', ' ', strip_tags($x)));
                    if ($t === '') { continue; }
                    $tot++;
                    if (mb_strpos($t, ':') !== false || mb_strpos($t, '—') !== false) { $c++; }
                }
                return $tot ? round($c / $tot * 100, 1) : 0;
            })(),
            'strong_lead_pct' => (function () use ($noScript) {
                $tot = 0; $lead = 0;
                if (preg_match_all('~<(li|p|dd|td)\b[^>]*>(.*?)</\1>~is', $noScript, $bm, PREG_SET_ORDER)) {
                    foreach ($bm as $b) {
                        $n = preg_match_all('~<strong\b~i', $b[2]);
                        if (!$n) { continue; }
                        $tot += $n;
                        if (preg_match('~^\s*<strong\b~i', $b[2])) { $lead++; }
                    }
                }
                return $tot ? round($lead / $tot * 100, 1) : 0;
            })(),
            'emoji_inline' => (function () use ($noScript) {
                // Эмодзи в начале пункта — это маркер, он у образца и есть.
                // Считаем только те, что стоят ВНУТРИ фразы.
                $any   = '~[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]~u';
                $first = '~^[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]~u';
                $n = 0;
                if (preg_match_all('~<(li|p)\b[^>]*>(.*?)</\1>~is', $noScript, $bm, PREG_SET_ORDER)) {
                    foreach ($bm as $b) {
                        $t = trim(preg_replace('~\s+~u', ' ', strip_tags($b[2])));
                        $all = preg_match_all($any, $t);
                        if (!$all) { continue; }
                        $n += $all - (preg_match($first, $t) ? 1 : 0);
                    }
                }
                return $n;
            })(),
            'para_spread' => (function () use ($ps) {
                if (count($ps) < 2) { return 0; }
                $len = array_map(fn($x) => count(preg_split('~\s+~u', $x, -1, PREG_SPLIT_NO_EMPTY)), $ps);
                $mean = array_sum($len) / count($len);
                $var = 0;
                foreach ($len as $l) { $var += ($l - $mean) ** 2; }
                return round(sqrt($var / count($len)), 1);
            })(),
            'para_short' => count(array_filter($ps,
                fn($x) => count(preg_split('~\s+~u', $x, -1, PREG_SPLIT_NO_EMPTY)) < 15)),
            'words_per_para' => $ps ? round($wp / count($ps), 1) : 0,
            'games_named' => NicheLexicon::countGames($prose),
            'providers_named' => NicheLexicon::countProviders($prose),
            'names_uniq' => NicheLexicon::uniqNames($prose),
            'terms_total' => NicheLexicon::termsTotal($prose),
            'terms' => NicheLexicon::termCounts($prose),
        ];
    }
}
