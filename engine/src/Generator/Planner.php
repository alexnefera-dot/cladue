<?php
declare(strict_types=1);

require_once __DIR__ . '/Rng.php';

/**
 * Планировщик страницы: по (тип, бренд, домен, дата, seed) сэмплирует
 * детерминированную «сборочную спеку» — что и в каком количестве собрать.
 *
 * Ничего не выдумывает: тянет из engine/data/profile.json (распределения
 * корпуса), engine/data/pools/pools.json (сущности/темы/значения/стиль) и
 * samples/fact-pool/<тип>.txt (12,5k добытых тезисов — как семена для
 * перефраза, не для копирования). Все числа берутся ИЗ коридоров корпуса
 * (tri по [p10,med,p90]) — «воспроизвести, не превзойти».
 */
final class Planner
{
    private array $profile;
    private array $pools;
    private string $factDir;

    public function __construct(?string $dataDir = null, ?string $factDir = null)
    {
        $dataDir ??= __DIR__ . '/../../data';
        $this->profile = $this->loadJson($dataDir . '/profile.json');
        $this->pools   = $this->loadJson($dataDir . '/pools/pools.json');
        $this->factDir = $factDir ?? (__DIR__ . '/../../../samples/fact-pool');
    }

    private function loadJson(string $path): array
    {
        $raw = @file_get_contents($path);
        if ($raw === false) {
            throw new RuntimeException("Не найден файл данных: $path");
        }
        $data = json_decode($raw, true);
        if (!is_array($data)) {
            throw new RuntimeException("Битый JSON: $path");
        }
        return $data;
    }

    public function types(): array
    {
        return array_keys($this->profile['types']);
    }

    /**
     * @return array сборочная спека (см. generate.php для формата вывода)
     */
    public function plan(string $type, array $brand): array
    {
        if (!isset($this->profile['types'][$type])) {
            throw new RuntimeException("Неизвестный тип страницы: $type");
        }
        $P = $this->profile['types'][$type];
        $brandRu = $brand['ru']     ?? 'Бренд';
        $brandEn = $brand['en']     ?? 'Brand';
        $domain  = $brand['domain'] ?? 'example.win';
        $date    = $brand['date']   ?? '21 июля 2026';
        $seed    = $brand['seed']   ?? ($domain . ':' . $type);
        $rng     = new Rng($seed);

        // 1. Числовые цели — все из коридоров корпуса
        $targets = [
            'words'          => $rng->triInt($P['words']),
            'h2'             => $rng->triInt($P['h2']),
            'sections_total' => $rng->triInt($P['sections']),
            'lists'          => $rng->triInt($P['lists']),
            'tables'         => $rng->triInt($P['tables']),
            'quotes'         => $rng->triInt($P['quotes']),
            'strong'         => $rng->triInt($P['strong']),
            'faq_count'      => $rng->triInt($P['faq']),
            'entities'       => $rng->triInt($P['entities']),
            'numbers_per100' => round($rng->tri((float) $P['numbers_per100'][0], (float) $P['numbers_per100'][1], (float) $P['numbers_per100'][2]), 1),
            'emoji_body'     => $rng->triInt($P['emoji_body']),
            'adj_pct'        => round($rng->tri((float) $P['adj_pct'][0], (float) $P['adj_pct'][1], (float) $P['adj_pct'][2]), 1),
            'brand_ru'       => max(1, (int) round($P['brand_ru'] * $rng->range(0.7, 1.3))),
            'brand_en'       => max(1, (int) round($P['brand_en'] * $rng->range(0.7, 1.3))),
        ];

        // 2. Тон — булевы доли из корпуса
        $vy = $rng->chance((float) $P['p_vy']);
        $fp = $rng->chance((float) $P['p_first_person']);
        $addressModes = $this->pools['style']['address_modes'] ?? ['нейтрально-описательный'];
        $tone = [
            'vy'             => $vy,
            'first_person'   => $fp,
            'address_mode'   => $fp ? 'личный опыт (первое лицо)' : ($vy ? 'обращение на «вы»' : 'нейтрально-описательный'),
            'nausea_acad'    => round($rng->tri((float) $P['nausea_acad'][0], (float) $P['nausea_acad'][1], (float) $P['nausea_acad'][2]), 1),
            'water'          => round($rng->tri((float) $P['water'][0], (float) $P['water'][1], (float) $P['water'][2]), 1),
            'key_density'    => round($rng->tri((float) $P['key_density'][0], (float) $P['key_density'][1], (float) $P['key_density'][2]), 2),
        ];

        // 3. Тематический набор секций (Бернулли по вероятностям корпуса)
        $themes = $this->selectThemes($P['sections_pool'], $rng);

        // 4. Раздать sections_total заголовков по темам (популярные несут больше H3)
        $headingsBudget = max(count($themes) + 1, $targets['sections_total']);
        $sectionPlan = $this->distributeHeadings($themes, $P['sections_pool'], $headingsBudget, $rng);

        // 5. Собрать сами секции с фактами/сущностями/значениями/блоками
        $factPool = $this->loadFactPool($type);
        $topicPool = $this->pools['topics'][$type] ?? [];
        $crossTopics = $this->crossTopics();

        $sections = [];
        $sections[] = [
            'role' => 'opener',
            'hint' => str_replace(['{Бренд}'], [$brandRu], (string) ($this->pools['style']['opener'] ?? '«{Бренд}. …»')),
        ];

        $h2left = $targets['h2'];
        $tablesLeft = max(1, $targets['tables']);   // ≥1 таблица — инвариант
        $quotesLeft = max(1, $targets['quotes']);    // ≥1 цитата — инвариант
        $listsLeft  = max(1, $targets['lists']);
        $usedTopics = [];

        $idx = 0;
        foreach ($sectionPlan as $entry) {
            $theme = $entry['theme'];
            if ($theme === 'FAQ — вопросы-ответы') { continue; } // FAQ добавим отдельно в конце
            $res = $this->themeResources($theme);
            $level = $h2left > 0 ? 'H2' : 'H3';
            if ($level === 'H2') { $h2left--; }

            // тема-фраза (без дублей в пределах страницы, до 4 попыток)
            $topic = null;
            for ($try = 0; $try < 4; $try++) {
                if ($theme === 'ПРОЧЕЕ / креатив') {
                    $cand = $rng->chance(0.35) ? $rng->pick($crossTopics) : $rng->pick($topicPool ?: $crossTopics);
                } else {
                    $cand = $rng->pick($topicPool ?: [$theme]) ?? $theme;
                }
                if ($cand !== null && !in_array($cand, $usedTopics, true)) { $topic = $cand; break; }
                $topic = $cand;
            }
            $usedTopics[] = $topic;

            // заголовок: 80% креатив
            $headingStyle = $rng->weighted($this->profile['heading_pattern_weights']);
            $headingPattern = $rng->pick($this->pools['style']['heading_patterns'] ?? ['{Тема}']);

            // прикреплённый блок с учётом инвариантов и остатков
            $block = $this->pickBlock($res, $rng, $tablesLeft, $quotesLeft, $listsLeft);
            if (str_starts_with($block, 'table')) { $tablesLeft--; }
            elseif ($block === 'quote') { $quotesLeft--; }
            elseif ($block === 'list') { $listsLeft--; }

            // сущности
            $ents = [];
            foreach ($res['entities'] as $poolKey) {
                $pool = $this->pools['entities'][$poolKey] ?? [];
                if ($pool === []) { continue; }
                $ents = array_merge($ents, $rng->sample($pool, $rng->int(1, 3)));
            }
            $ents = array_slice($ents, 0, 5);

            // значения
            $vals = [];
            foreach ($res['values'] as $slotKey) {
                $vals[$slotKey] = $this->sampleValue($slotKey, $rng);
            }

            // семена фактов (перефразировать, НЕ копировать)
            $facts = $this->seedFacts($factPool, $rng, $rng->int(2, 3));

            $idx++;
            $sections[] = [
                'idx'            => $idx,
                'theme'          => $theme,
                'level'          => $level,
                'topic'          => $topic,
                'fact_category'  => $res['fact'],
                'heading_style'  => $headingStyle,
                'heading_pattern'=> $headingPattern,
                'block'          => $block,
                'entities'       => array_values(array_unique($ents)),
                'values'         => $vals,
                'fact_seeds'     => $facts,
            ];
        }

        // 5b. Догарантировать инварианты блоков: ≥1 таблица и ≥1 цитата на странице
        $this->ensureBlock($sections, 'table:спецификация', $tablesLeft, $rng);
        $this->ensureBlock($sections, 'quote', $quotesLeft, $rng);

        // 6. FAQ — гарантированная секция
        $faqFrames = $this->pools['style']['faq_frames'] ?? array_keys($this->profile['faq_frame_weights']);
        $faqPlan = [];
        for ($i = 0; $i < $targets['faq_count']; $i++) {
            $faqPlan[] = $rng->weighted($this->profile['faq_frame_weights']);
        }
        $sections[] = [
            'role'   => 'faq',
            'count'  => $targets['faq_count'],
            'frames' => $faqPlan,
        ];

        return [
            'type'      => $type,
            'brand'     => ['ru' => $brandRu, 'en' => $brandEn],
            'domain'    => $domain,
            'date'      => $date,
            'seed'      => $seed,
            'targets'   => $targets,
            'tone'      => $tone,
            'semantics' => $P['sem_clusters'],
            'invariants'=> $this->pools['style']['invariants'] ?? [],
            'sections'  => $sections,
        ];
    }

    /** Бернулли-выбор тем по вероятностям; FAQ и креатив — всегда */
    private function selectThemes(array $pool, Rng $rng): array
    {
        $chosen = [];
        foreach ($pool as [$name, $p]) {
            if ($name === 'FAQ — вопросы-ответы' || $name === 'ПРОЧЕЕ / креатив') {
                $chosen[] = $name;
                continue;
            }
            if ($rng->chance((float) $p)) { $chosen[] = $name; }
        }
        if (!in_array('ПРОЧЕЕ / креатив', $chosen, true)) { $chosen[] = 'ПРОЧЕЕ / креатив'; }
        return $chosen;
    }

    /** Раздать бюджет заголовков по темам: базово по 1, остаток — взвешенно (популярным больше) */
    private function distributeHeadings(array $themes, array $pool, int $budget, Rng $rng): array
    {
        $probMap = [];
        foreach ($pool as [$name, $p]) { $probMap[$name] = (float) $p; }

        $plan = [];
        foreach ($themes as $t) { $plan[$t] = 1; }
        $used = count($plan);
        $extra = max(0, $budget - $used);

        // веса для распределения остатка: креатив тянет львиную долю H3
        $weights = [];
        foreach ($themes as $t) {
            if ($t === 'FAQ — вопросы-ответы') { continue; }
            $weights[$t] = $t === 'ПРОЧЕЕ / креатив' ? 4.0 : ($probMap[$t] ?? 0.2);
        }
        for ($i = 0; $i < $extra; $i++) {
            $t = $rng->weighted($weights);
            $plan[$t] = ($plan[$t] ?? 0) + 1;
        }

        // развернуть в плоский список секций, перемешать порядок (кроме FAQ — он в конце)
        $flat = [];
        foreach ($plan as $theme => $n) {
            if ($theme === 'FAQ — вопросы-ответы') { continue; }
            for ($j = 0; $j < $n; $j++) { $flat[] = ['theme' => $theme]; }
        }
        $rng->shuffle($flat);
        return $flat;
    }

    /** Сопоставление темы -> ресурсы (сущности/значения/факт-категория/блок-склонность) */
    private function themeResources(string $theme): array
    {
        $t = mb_strtolower($theme);
        $has = static fn(string $sub) => mb_strpos($t, $sub) !== false;

        // дефолт
        $r = ['entities' => [], 'values' => [], 'fact' => 'shared', 'block_bias' => null];

        if ($has('слот') || $has('игр') || $has('live') || $has('джекпот') || $has('rtp')) {
            $r = ['entities' => ['games_slots', 'providers'], 'values' => ['rtp', 'games_count', 'providers_count'], 'fact' => 'slots', 'block_bias' => 'table:игры'];
            if ($has('live')) { $r['entities'] = ['games_live', 'providers']; }
            if ($has('провайдер')) { $r['entities'] = ['providers', 'games_slots']; }
        } elseif ($has('платеж') || $has('вывод')) {
            $r = ['entities' => ['payments', 'crypto', 'currencies'], 'values' => ['deposit_min', 'withdraw_time', 'withdraw_limit', 'verify_time'], 'fact' => 'shared', 'block_bias' => 'table:спецификация'];
        } elseif ($has('бонус') || $has('отыгрыш') || $has('промокод') || $has('кэшбэк') || $has('фриспин') || $has('лояльн') || $has('турнир')) {
            $r = ['entities' => ['games_slots'], 'values' => ['bonus_percent', 'freespins', 'wager', 'max_bet_wager', 'cashback_percent'], 'fact' => 'bonus', 'block_bias' => 'list'];
        } elseif ($has('зеркал') || $has('доступ') || $has('vpn') || $has('блокиров')) {
            $r = ['entities' => ['support_channels'], 'values' => [], 'fact' => 'zerkalo', 'block_bias' => 'list'];
        } elseif ($has('вход') || $has('авториз') || $has('парол') || $has('2fa')) {
            $r = ['entities' => ['security_tech', 'support_channels'], 'values' => [], 'fact' => 'vhod', 'block_bias' => 'list'];
        } elseif ($has('регистрац') || $has('верифик') || $has('kyc')) {
            $r = ['entities' => [], 'values' => ['age', 'verify_time'], 'fact' => 'registracia', 'block_bias' => 'table:шаги'];
        } elseif ($has('приложен') || $has('android') || $has('ios') || $has('apk') || $has('мобиль')) {
            $r = ['entities' => ['security_tech'], 'values' => ['android_version', 'ios_version', 'apk_size'], 'fact' => 'app', 'block_bias' => 'table:спецификация'];
        } elseif ($has('безопас') || $has('лиценз')) {
            $r = ['entities' => ['licenses', 'security_tech'], 'values' => ['age'], 'fact' => 'shared', 'block_bias' => 'table:спецификация'];
        } elseif ($has('поддержк')) {
            $r = ['entities' => ['support_channels'], 'values' => ['support_response'], 'fact' => 'shared', 'block_bias' => 'list'];
        } elseif ($has('обзор') || $has('характеристик')) {
            $r = ['entities' => ['licenses', 'providers', 'payments'], 'values' => ['deposit_min', 'withdraw_time', 'providers_count', 'games_count', 'rtp'], 'fact' => 'shared', 'block_bias' => 'table:спецификация'];
        } elseif ($has('отзыв') || $has('опыт') || $has('дневник') || $has('хронолог')) {
            $r = ['entities' => [], 'values' => [], 'fact' => 'shared', 'block_bias' => 'quote'];
        } elseif ($has('проблем')) {
            $r = ['entities' => [], 'values' => [], 'fact' => 'shared', 'block_bias' => 'table:проблема-решение'];
        } elseif ($has('ответственн')) {
            $r = ['entities' => ['support_channels'], 'values' => ['age'], 'fact' => 'shared', 'block_bias' => 'list'];
        }
        return $r;
    }

    /** Выбор прикреплённого блока с учётом инвариантов (гарантируем ≥1 таблицу/цитату) */
    private function pickBlock(array $res, Rng $rng, int $tablesLeft, int $quotesLeft, int $listsLeft): string
    {
        // склонность темы имеет приоритет, но не жёстко
        if ($tablesLeft > 0 && $res['block_bias'] !== null && str_starts_with($res['block_bias'], 'table') && $rng->chance(0.7)) {
            return $res['block_bias'];
        }
        if ($quotesLeft > 0 && $res['block_bias'] === 'quote' && $rng->chance(0.7)) {
            return 'quote';
        }
        $choice = $rng->weighted($this->profile['block_attach_weights']);
        if ($choice === 'table') {
            if ($tablesLeft <= 0) { return 'list'; }
            $tt = $rng->weighted($this->profile['table_type_weights']);
            return 'table:' . $tt;
        }
        if ($choice === 'quote' && $quotesLeft <= 0) { return 'none'; }
        if ($choice === 'list' && $listsLeft <= 0) { return 'none'; }
        return $choice;
    }

    /** Если нужного блока (table/quote) нет ни в одной секции — конвертировать одну «none» */
    private function ensureBlock(array &$sections, string $block, int $needLeft, Rng $rng): void
    {
        $kind = str_starts_with($block, 'table') ? 'table' : $block;
        foreach ($sections as $s) {
            if (isset($s['block']) && str_starts_with((string) $s['block'], $kind)) { return; }
        }
        // не нашли — ищем секцию с 'none' (или любую контентную) и ставим блок
        $cand = [];
        foreach ($sections as $i => $s) {
            if (!isset($s['block'])) { continue; }
            if ($s['block'] === 'none') { $cand[] = $i; }
        }
        if ($cand === []) {
            foreach ($sections as $i => $s) { if (isset($s['block'])) { $cand[] = $i; } }
        }
        if ($cand === []) { return; }
        $pick = $cand[$rng->int(0, count($cand) - 1)];
        $sections[$pick]['block'] = $block;
    }

    /** Сэмпл одного значения из числового слота */
    private function sampleValue(string $slotKey, Rng $rng): string
    {
        $slot = $this->pools['value_slots'][$slotKey] ?? null;
        if ($slot === null) { return ''; }
        if (isset($slot['range'])) {
            [$a, $b] = $slot['range'];
            $v = $rng->range((float) $a, (float) $b);
            return number_format($v, 1, '.', '') . '%';
        }
        $pool = $slot['pool'] ?? [];
        if ($pool === []) { return ''; }
        // лёгкое смещение к weighted_to, если задано
        if (isset($slot['weighted_to']) && in_array($slot['weighted_to'], $pool, true) && $rng->chance(0.5)) {
            return (string) $slot['weighted_to'];
        }
        return (string) $rng->pick($pool);
    }

    /** Семена фактов из добытого пула (для перефраза, не для копирования) */
    private function seedFacts(array $pool, Rng $rng, int $k): array
    {
        if ($pool === []) { return []; }
        return array_map([$this, 'scrubSeed'], $rng->sample($pool, $k));
    }

    /** Убрать из семени доменные токены, чужие бренд-URL и плейсхолдеры бренда */
    private function scrubSeed(string $s): string
    {
        $s = preg_replace('/\{[^}]*бренд[^}]*\}/ui', 'бренд', $s) ?? $s;
        $s = preg_replace('#\b[\w\-]+\.(?:net|com|ru|org|win|info|io|xyz|cc|bet|casino)\b#ui', '[домен]', $s) ?? $s;
        $s = preg_replace('/\bhttps?:\/\/\S+/i', '[ссылка]', $s) ?? $s;
        return trim($s);
    }

    private function loadFactPool(string $type): array
    {
        $path = $this->factDir . '/' . $type . '.txt';
        $raw = @file_get_contents($path);
        if ($raw === false) { return []; }
        $lines = preg_split('/\r?\n/', trim($raw)) ?: [];
        return array_values(array_filter(array_map('trim', $lines), static fn($l) => $l !== '' && mb_strlen($l) > 15));
    }

    /** Общий кросс-пул тем (для инъекции в любой тип) */
    private function crossTopics(): array
    {
        $out = [];
        foreach ($this->pools['topics'] as $list) {
            foreach ($list as $t) { $out[] = $t; }
        }
        return array_values(array_unique($out));
    }
}
