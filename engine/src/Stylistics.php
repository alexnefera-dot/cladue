<?php
declare(strict_types=1);

/**
 * Стилистика, тон, E-E-A-T и фактура (реестр v2). Эвристики без внешних
 * библиотек — достаточно для профиля «как написан текст» и детекта генерации
 * по шаблону. Работает офлайн.
 */
final class Stylistics
{
    private const AI_CONNECTORS = [
        'таким образом','в свою очередь','стоит отметить','важно отметить','следует отметить',
        'важно понимать','как правило','в целом','кроме того','более того','обратите внимание',
        'необходимо отметить','в конечном счёте','в конечном счете','нельзя не отметить',
    ];
    private const PARASITES = [
        'обычно','как правило','в принципе','собственно','фактически','достаточно часто','зачастую',
    ];
    /** сущности/фактура: категория => regex */
    private const ENTITIES = [
        'Лицензия'      => 'лицензи|cur[aа][cс][aа]o|кюрасао|gaming ?curacao',
        'Провайдеры'    => 'провайдер|netent|pragmatic|evolution|microgaming|yggdrasil|play\'?n ?go|igrosoft|betsoft',
        'Платежи'       => 'visa|mastercard|мир|qiwi|e-?wallet|кошел[её]к',
        'Крипта'        => 'btc|eth|usdt|биткоин|крипто',
        'KYC/AML'       => '\bkyc\b|\baml\b|верификац',
        '2FA'           => '2fa|двухфакторн',
        'RTP'           => '\brtp\b|отдача',
        'Вейджер'       => 'вейджер|отыгрыш',
        'Фриспины'      => 'фриспин|free ?spin|бесплатн\w+ вращени',
        'Джекпот'       => 'джекпот|jackpot',
        'Поддержка 24/7'=> '24/7|круглосуточн|live-?chat|телеграм|telegram',
        'Security-стек' => 'tls|aes|\bcdn\b|ddos|шифрован|ssl',
        'Лимиты/сроки'  => 'мин\w* депозит|минимальн\w+ депозит|вывод\w* (за|в течение|до)|\d+\s*(мин|час)',
    ];

    /** @param string[] $brandNames имена всех брендов базы (для чужих брендов) */
    public static function of(TextMetrics $tm, SeoMetrics $seo, string $brand, array $brandNames): array
    {
        $text = $tm->text;
        $low = mb_strtolower($text, 'UTF-8');
        $wordN = max($tm->wordCount(), 1);
        $headings = mb_strtolower($seo->headingsText(), 'UTF-8');

        // числа / конкретика
        $numbers = preg_match_all('/\d+/u', $text);
        // прилагательные (по окончаниям)
        $adj = preg_match_all('/\b[\p{L}]+(?:ый|ий|ая|яя|ое|ее|ые|ие|ого|его|ому|ыми|ими|ых|их|ой)\b/u', $low);
        // пассив/причастия/возвратные
        $passive = preg_match_all('/\b[\p{L}]+(?:ется|ются|тся|нный|нная|нные|нных|анный|енный)\b/u', $low);
        // лицо и обращение
        $firstP = preg_match_all('/\b(я|мне|меня|мой|моя|мои|моих|моему|проверил|проверила|играю|попробовал|убедился|мой опыт)\b/u', $low);
        // Падежи «ваш» были перечислены не все: «вашем», «вашей», «вашу»,
        // «вашим» мера не видела, и страница с четырьмя обращениями к
        // читателю показывала ноль.
        $secondP = preg_match_all('/\b(вы|вас|вам|вами|ваш(?:а|е|и|его|ему|им|ими|ем|ей|ею|у|их)?)\b/u', $low);
        $imper = preg_match_all('/\b[\p{L}]+(?:йте|ите)\b/u', $low);

        // ИИ-связки и паразиты
        $ai = 0; $aiList = [];
        foreach (self::AI_CONNECTORS as $c) { $n = substr_count($low, $c); if ($n) { $ai += $n; $aiList[$c] = $n; } }
        $parasite = 0;
        foreach (self::PARASITES as $p) { $parasite += substr_count($low, $p); }

        // эмодзи
        $emoji = preg_match_all('/[\x{1F000}-\x{1FAFF}\x{2600}-\x{27BF}\x{2B00}-\x{2BFF}]/u', $text);

        // дата/свежесть
        $dateFresh = (bool) preg_match('/обновлен|последн\w+ обновл|\b20\d{2}\b|\d{1,2}\.\d{1,2}\.\d{2,4}/u', $low);

        // FAQ
        $questions = substr_count($text, '?');
        $faq = $questions >= 3 || (bool) preg_match('/\bfaq\b|вопрос|часто задава/u', $headings);

        // сущности
        $entities = [];
        foreach (self::ENTITIES as $cat => $rx) {
            if (preg_match('#' . $rx . '#u', $low)) { $entities[] = $cat; }  // # делимитер: в паттернах есть «/» (24/7)
        }

        // варианты бренда
        $bl = mb_strtolower($brand, 'UTF-8');
        $variants = [
            'latin'  => preg_match_all('/(?<![\p{L}])' . preg_quote($bl, '/') . '(?![\p{L}])/u', $low),
        ];

        // Чужие бренды (остаток шаблона). Названия игр вырезаются заранее:
        // «Sweet» и «Gold» — сами по себе казино-бренды, и внутри «Sweet
        // Bonanza 1000» и «Wolf Gold» они давали ложное срабатывание. Тайтлы
        // предписаны фактурой промпта, а генерация из-за этого их выбрасывала —
        // два самых частых названия корпуса уходили из текста.
        $lowNoGames = $low;
        if (class_exists('NicheLexicon')) {
            [$provRe, $gameRe] = NicheLexicon::patterns();
            // patterns() отдаёт готовые выражения с разделителями — оборачивать их
            // ещё раз нельзя, иначе шаблон рвётся на первом же «~».
            if ($gameRe !== '') { $lowNoGames = (string) preg_replace($gameRe, ' ', $lowNoGames); }
            if ($provRe !== '') { $lowNoGames = (string) preg_replace($provRe, ' ', $lowNoGames); }
        }
        $foreign = [];
        foreach ($brandNames as $bn) {
            $bnl = mb_strtolower((string) $bn, 'UTF-8');
            if ($bnl === $bl || mb_strlen($bnl, 'UTF-8') < 4) { continue; }
            if (preg_match('/(?<![\p{L}\d])' . preg_quote($bnl, '/') . '(?![\p{L}\d])/u', $lowNoGames)) {
                $foreign[] = $bn;
                if (count($foreign) >= 5) { break; }
            }
        }

        // стиль (эвристика)
        $adjPct = round($adj / $wordN * 100, 1);
        $numPer100 = round($numbers / $wordN * 100, 1);
        $style = self::classifyStyle($firstP, $secondP, $imper, $adjPct, $passive / $wordN * 100);

        return [
            'numbers'          => $numbers,
            'numbers_per_100w' => $numPer100,
            'adj_pct'          => $adjPct,
            'passive_pct'      => round($passive / $wordN * 100, 1),
            'first_person'     => $firstP,
            'second_person'    => $secondP,
            'address'          => $secondP >= 2 ? 'вы' : ($firstP >= 2 ? 'личный опыт' : 'безличное'),
            'imperatives'      => $imper,
            'ai_connectors'    => $ai,
            'ai_connectors_top'=> $aiList,
            'parasites'        => $parasite,
            'emoji'            => $emoji,
            'date_freshness'   => $dateFresh,
            'faq_present'      => $faq,
            'faq_questions'    => $questions,
            'entities'         => $entities,
            'entities_count'   => count($entities),
            'brand_variants'   => $variants,
            'foreign_brands'   => $foreign,
            'style_class'      => $style,
        ];
    }

    private static function classifyStyle(int $fp, int $sp, int $imp, float $adjPct, float $passivePct): string
    {
        if ($fp >= 2) { return 'личный опыт (E-E-A-T)'; }
        if ($imp >= 4 || $sp >= 4) { return 'рекламно-инструктивный'; }
        if ($passivePct >= 3 || $adjPct >= 12) { return 'справочно-описательный'; }
        return 'нейтральный';
    }
}
