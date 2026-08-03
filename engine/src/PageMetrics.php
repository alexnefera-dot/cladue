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
        'paragraphs' => ['абзацев', 0], 'words_per_para' => ['слов в абзаце', 1],
        'games_named' => ['названий игр', 0], 'providers_named' => ['названий студий', 0],
        'terms_total' => ['профильных терминов', 0],
        'h3_per_h2'  => ['H3 на один H2', 1],
        'h2_len'     => ['слов в заголовке', 1],
        'h2_quest'   => ['заголовков-вопросов %', 1],
        'cta'        => ['прямых призывов', 0],
        'honest'     => ['мест с минусом или риском', 0],
    ];

    public const SIGNALS = ['h3_per_h2', 'h2_len', 'h2_quest', 'cta', 'honest'];

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

        return [
            'brand_in_h' => $inH,
            'brand_first_third' => preg_match_all($brandRe, $head),
            'faq_pairs' => $faqPairs,
            'questions_total' => substr_count($fullText, '?'),
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
            'words_per_para' => $ps ? round($wp / count($ps), 1) : 0,
            'games_named' => NicheLexicon::countGames($prose),
            'providers_named' => NicheLexicon::countProviders($prose),
            'terms_total' => NicheLexicon::termsTotal($prose),
            'terms' => NicheLexicon::termCounts($prose),
        ];
    }
}
