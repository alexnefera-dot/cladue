<?php
declare(strict_types=1);

require_once __DIR__ . '/Rng.php';
require_once __DIR__ . '/StyleProfile.php';

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
    /** реестр страниц корпуса: путь, разрешённые категории сущностей, роли */
    private array $pages = [];

    public function __construct(?string $dataDir = null, ?string $factDir = null)
    {
        $dataDir ??= __DIR__ . '/../../data';
        $this->profile = $this->loadJson($dataDir . '/profile.json');
        $this->pools   = $this->loadJson($dataDir . '/pools/pools.json');
        $this->factDir = $factDir ?? (__DIR__ . '/../../../samples/fact-pool');
        // Реестр страниц корпуса. Пока его нет в профиле, действуют зашитые
        // умолчания корпусов v1/v2 (семь известных типов) — их поведение не
        // меняется. Корпус v3 приносит свой реестр: там страниц бывает одна или
        // двенадцать, и шесть типов, которых движок раньше не видел.
        $this->pages = $this->profile['pages'] ?? [];
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
     * Можно ли этой странице нести элемент (эмодзи, авторский блок).
     *
     * В корпусах v1/v2 оба стояли только на главной, и это было зашито условием
     * `$type === 'main'`. Корпус v3 показал, что правило корпусное, а не общее:
     * в его связке эмодзи есть на всех двенадцати страницах. Поэтому решает
     * реестр корпуса, а при его отсутствии — прежнее умолчание.
     */
    private function pageAllows(string $type, string $what, string $fallbackType): bool
    {
        if ($this->pages === []) { return $type === $fallbackType; }
        return !empty($this->pages[$type][$what]);
    }

    /**
     * @param StyleProfile|null $style стиль-профиль ГЕНЕРАЦИИ (один на все 7 страниц).
     *        Если не передан — сэмплируется из seed бренда/домена (та же связка → тот же стиль).
     * @return array сборочная спека (см. generate.php для формата вывода)
     */
    public function plan(string $type, array $brand, ?StyleProfile $style = null, ?array $donor = null): array
    {
        if (!isset($this->profile['types'][$type])) {
            throw new RuntimeException("Неизвестный тип страницы: $type");
        }
        $P = $this->profile['types'][$type];
        // Донор-режим: цели тянем из конкретного сайта, а не из коридора корпуса.
        $dp = ($donor !== null) ? ($donor['pages'][$type] ?? null) : null;
        $brandRu = $brand['ru']     ?? 'Бренд';
        $brandEn = $brand['en']     ?? 'Brand';
        $domain  = $brand['domain'] ?? 'example.win';
        $date    = $brand['date']   ?? '21 июля 2026';
        $seed    = $brand['seed']   ?? ($domain . ':' . $type);
        $rng     = new Rng($seed);

        // Стиль-профиль генерации: если не задан — детерминированно из бренда/домена
        // (одинаков для всех типов одной связки → единый тон на всех 7 страницах).
        // В донор-режиме стиль берётся из сайта-донора.
        if ($style === null) {
            $style = $donor !== null
                ? StyleProfile::fromDonor($donor['style'] ?? [], new Rng('donor:' . $seed))
                : StyleProfile::sample(new Rng('style:' . $brandRu . ':' . $brandEn . ':' . $domain));
        }

        // 1. Числовые цели. В донор-режиме — из значений сайта (±джиттер),
        //    иначе — из коридоров корпуса.
        // $key: имя поля в донор-профиле; $triple: коридор корпуса как фолбэк.
        $Ti = fn(string $key, array $triple, int $min = 0)
            => $dp !== null && isset($dp[$key])
                ? max($min, (int) round($dp[$key] * $rng->range(0.9, 1.1)))
                : $rng->triInt($triple);
        $Tf = fn(string $key, array $triple, float $bias)
            => $dp !== null && isset($dp[$key])
                ? round((float) $dp[$key] * $rng->range(0.9, 1.1), 1)
                : round($this->biased($rng, $triple, $bias), 1);

        $targets = [
            'words'          => $Ti('words', $P['words']),
            'h2'             => $Ti('h2', $P['h2'], 1),
            'sections_total' => $Ti('sections', $P['sections'], 1),
            'lists'          => $Ti('lists', $P['lists']),
            'tables'         => $Ti('tables', $P['tables']),
            'quotes'         => $Ti('quotes', $P['quotes']),
            'strong'         => $Ti('strong', $P['strong']),
            'faq_count'      => $Ti('faq', $P['faq']),
            'entities'       => $Ti('entities', $P['entities']),
            'imperatives'    => $Ti('imperatives', $P['imperatives']),
            // Обращение/лицо — числом, а не «да/нет»: иначе при сокращении команд
            // реалайзер заодно вымывает «вы», и наоборот (связанные параметры).
            'vy'             => $Ti('vy', $P['vy']),
            'first_person'   => $Ti('first_person', $P['first_person']),
            'numbers_per100' => $Tf('numbers_per100', $P['numbers_per100'], $style->numbersBias),
            'adj_pct'        => $Tf('adj_pct', $P['adj_pct'], $style->adjBias),
            // эмодзи в теле: в донор-режиме — как у донора; иначе только у эмодзи-сайта на main
            'emoji_body'     => $dp !== null
                ? ($style->emojiSite ? $Ti('emoji', $P['emoji_body']) : 0)
                : (($style->emojiSite && $this->pageAllows($type, 'emoji', 'main')) ? $rng->triInt($P['emoji_body']) : 0),
            // бренд ру/англ: в донор-режиме — как у донора (важный параметр оптимизации), иначе из профиля
            'brand_ru'       => $dp['brand_ru'] ?? max(1, (int) round($P['brand_ru'] * $rng->range(0.7, 1.3))),
            'brand_en'       => $dp['brand_en'] ?? max(1, (int) round($P['brand_en'] * $rng->range(0.7, 1.3) * ($style->naming === 'en-heavy' ? 1.15 : 0.85))),
        ];

        // 2. Тон — из стиль-профиля ГЕНЕРАЦИИ (одинаков на всех 7 страницах)
        $tone = [
            'vy'             => $style->vy,
            'first_person'   => $style->firstPerson,
            'address_mode'   => $style->addressMode,
            'persona'        => $style->firstPerson ? $style->persona : '',
            'flourish'       => round($style->flourish, 2),
            'nausea_acad'    => $Tf('nausea_acad', $P['nausea_acad'], 0.5),
            'water'          => $Tf('water', $P['water'], 0.5),
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
        $angles = $this->pools['topic_angles'] ?? [];

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

            // тема-фраза = база (из пула типа/кросс) + часто «угол подачи».
            // База × угол = сотни комбинаций → разные варианты при одном доноре.
            // Дедуп по СОСТАВНОЙ теме (до 5 попыток).
            $topic = null;
            for ($try = 0; $try < 5; $try++) {
                if ($theme === 'ПРОЧЕЕ / креатив') {
                    $base = $rng->chance(0.5) ? $rng->pick($crossTopics) : $rng->pick($topicPool ?: $crossTopics);
                } else {
                    // ядро типа, но иногда подмешиваем кросс-тему — тоже источник разнообразия
                    $base = $rng->chance(0.2) ? $rng->pick($crossTopics) : ($rng->pick($topicPool ?: [$theme]) ?? $theme);
                }
                $cand = $base;
                if ($angles !== [] && $rng->chance(0.6)) {
                    $cand = $base . ': ' . $rng->pick($angles);
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
            'donor'     => $donor['name'] ?? null,
            'data_card' => $this->buildDataCard($rng, $type),
            'data_tables' => $this->buildDataTables($rng, $type),
            'links'     => $this->buildLinks($type, $rng, $brandRu, $brandEn, $donor),
            'register'  => $this->resolveRegister($style->register),
            // жанр и наличие авторского блока сняты вычиткой референсов
            'donor_genre'  => $donor['style']['genre'] ?? null,
            // Авторский блок в референсах стоит ТОЛЬКО на главной (проверено:
            // на сателлитах 0 из 6 у всех доноров с автором).
            'author_block' => !empty($donor['style']['author_block']) && $this->pageAllows($type, 'author_block', 'main'),
            'style'     => $style->toArray(),
            'targets'   => $targets,
            'tone'      => $tone,
            // семантические цели: в донор-режиме — плотности кластеров этого сайта, иначе медиана типа
            'semantics' => $dp['sem'] ?? null ? $this->labelClusters($dp['sem']) : $P['sem_clusters'],
            'invariants'=> $this->pools['style']['invariants'] ?? [],
            'sections'  => $sections,
        ];
    }

    /** Значение по позиции стиль-профиля в коридоре + малый покадровый джиттер */
    private function biased(Rng $rng, array $triple, float $bias): float
    {
        $u = max(0.0, min(1.0, $bias + $rng->range(-0.12, 0.12)));
        return $rng->triU((float) $triple[0], (float) $triple[1], (float) $triple[2], $u);
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

    /**
     * «Спек-карта» — набор ИМЕНОВАННЫХ конкретных данных бренда (год, игроки,
     * RTP, лицензии, крипта, платформы…). Это защита от «ИИ-водянистости»:
     * реальные сайты выкладывают такие данные блоком и рассыпают по тексту.
     */
    private function buildDataCard(Rng $rng, string $type): array
    {
        $id = $this->pools['identity_facts'] ?? [];
        $card = [];
        // числовые именованные факты
        $labels = [
            'founding_year'   => 'Год основания',
            'players_count'   => 'Игроков',
            'games_count'     => 'Игр в каталоге',
            'providers_count' => 'Провайдеров',
            'payout_rate'     => 'Выплаты (RTP)',
            'mirrors_count'   => 'Рабочих зеркал',
        ];
        // Часть фактов «зажигает» отдельную семантическую категорию сущностей
        // (провайдеры, RTP, лицензия, крипта, платежи, джекпот). На сателлитах
        // донор держит МЕНЬШЕ категорий, поэтому фактуру делаем ТЕМАТИЧЕСКОЙ по типу:
        // только релевантные странице категории, иначе счётчик сущностей улетает.
        $allowCat = [
            'main'        => ['providers_count','payout_rate','licenses','crypto','payments','jackpot','currencies','platforms'],
            'slots'       => ['providers_count','payout_rate','licenses','jackpot'],
            'bonus'       => ['licenses'],
            'zerkalo'     => ['licenses'],
            'registracia' => ['licenses'],
            'vhod'        => [],
            'app'         => ['platforms'],
        ];
        // Реестр корпуса главнее зашитой таблицы: у v3 есть типы, которых здесь нет.
        $ok = $this->pages[$type]['entity_cats'] ?? ($allowCat[$type] ?? ['licenses']);
        $catDriverSlot = ['providers_count','payout_rate'];       // зажигают «Провайдеры»/«RTP»
        // ВСЕ именованные пулы гейтим по $ok, иначе currencies/platforms текут
        // на каждую страницу и раздувают счётчик категорий-сущностей на сателлитах.
        $catDriverEnt  = ['licenses','crypto','payments','currencies','platforms'];

        foreach (($id['slots'] ?? []) as $slot) {
            if (in_array($slot, $catDriverSlot, true) && !in_array($slot, $ok, true)) { continue; }
            $v = $this->sampleValue($slot, $rng);
            if ($v !== '') { $card[$labels[$slot] ?? $slot] = $v; }
        }
        // именованные сущности (лицензии, крипта, валюты, платформы, платёжки)
        $entLabels = [
            'licenses'  => 'Лицензия',
            'crypto'    => 'Криптовалюты',
            'currencies'=> 'Валюты',
            'platforms' => 'Платформы',
            'payments'  => 'Платёжные методы',
        ];
        foreach (($id['named_entities'] ?? []) as $poolKey) {
            if (in_array($poolKey, $catDriverEnt, true) && !in_array($poolKey, $ok, true)) { continue; }
            $pool = $this->pools['entities'][$poolKey] ?? [];
            if ($pool === []) { continue; }
            $k = $poolKey === 'licenses' ? 1 : $rng->int(2, 3);
            $card[$entLabels[$poolKey] ?? $poolKey] = implode(', ', $rng->sample($pool, $k));
        }
        // приветственный бонус — конкретика для main/bonus; джекпот только там, где «джекпот» в теме
        if (in_array($type, ['main', 'bonus'], true)) {
            $card['Приветственный бонус'] = $this->sampleValue('welcome_sum', $rng);
        }
        if (in_array('jackpot', $ok, true)) {
            $card['Джекпот'] = $this->sampleValue('jackpot_sum', $rng);
        }
        return $card;
    }

    /**
     * Расширенная фактура — СТРУКТУРНЫЕ блоки-таблицы (турнирная сетка,
     * история джекпотов, лимиты по уровням лояльности). Для main/bonus/slots.
     */
    private function buildDataTables(Rng $rng, string $type): array
    {
        $tables = [];
        $games = $this->pools['entities']['games_slots'] ?? [];

        if (in_array($type, ['main', 'bonus'], true)) {
            // Турнирная сетка (3-4 турнира)
            $names = ['Слот-баттл', 'Live-марафон', 'Сезонный кубок', 'Ночной турнир', 'Уик-энд гонка', 'Джекпот-квест'];
            $rng->shuffle($names);
            $grid = [];
            $fundPool = [50000, 100000, 300000, 500000, 1000000];
            $n = $rng->int(3, 4);
            for ($i = 0; $i < $n; $i++) {
                $fund = $rng->pick($fundPool);
                $top = (int) round($fund * $rng->range(0.35, 0.6)); // топ-приз — доля фонда
                $grid[] = [
                    'Турнир'  => $names[$i],
                    'Вход'    => $rng->pick(['0 ₽', '5 USD', '10 USD', '100 ₽', '500 ₽']),
                    'Фонд'    => number_format($fund, 0, '', ' ') . ' ₽',
                    'Топ-приз'=> number_format($top, 0, '', ' ') . ' ₽',
                ];
            }
            $tables['Турнирная сетка (неделя)'] = $grid;

            // Уровни лояльности: кэшбэк и лимит растут с уровнем
            $cash = [5, 8, 10, 12, 15];
            $lim  = ['50 000 ₽/сут', '100 000 ₽/сут', '300 000 ₽/сут', '500 000 ₽/сут', '1 000 000 ₽/сут'];
            $lv = [];
            for ($i = 1; $i <= 5; $i++) {
                $lv[] = [
                    'Уровень'     => (string) $i,
                    'Кэшбэк'      => $cash[$i - 1] . '%',
                    'Лимит вывода'=> $lim[$i - 1],
                ];
            }
            $tables['Уровни лояльности'] = $lv;
        }

        if (in_array($type, ['main', 'slots'], true) && $games !== []) {
            // История крупных джекпотов
            $hist = [];
            $picks = $rng->sample($games, $rng->int(3, 4));
            foreach ($picks as $g) {
                $hist[] = [
                    'Игра'   => $g,
                    'Выигрыш'=> $this->sampleValue('jackpot_sum', $rng),
                    'Когда'  => $rng->pick(['на прошлой неделе', 'в этом месяце', 'месяц назад', 'в прошлом квартале']),
                ];
            }
            $tables['Крупные джекпоты (история)'] = $hist;
        }

        return $tables;
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

    /**
     * Перелинковка по реальному принципу корпуса:
     * - число ссылок зависит от типа (main — хаб ~41, сателлиты 3–5) или от донора;
     * - цели выбираются взвешенно (app/zerkalo/vhod/registracia/slots часто, bonus редко),
     *   С ПОВТОРАМИ — одна цель может линковаться несколько раз из разных секций;
     * - анкоры в основном чистые ключи, бренд-переменная лишь в ~4%.
     */
    private function buildLinks(string $type, Rng $rng, string $brandRu, string $brandEn, ?array $donor = null): array
    {
        $cfg = $this->pools['interlinking'] ?? [];
        $paths = ['main'=>'/','zerkalo'=>'/zerkalo','vhod'=>'/vhod','registracia'=>'/registracia','bonus'=>'/bonus','slots'=>'/slots','app'=>'/app'];
        // Пути берём из реестра корпуса, если он есть: состав связки v3 другой.
        if ($this->pages !== []) {
            $paths = [];
            foreach ($this->pages as $pt => $cfg) { $paths[$pt] = $cfg['path'] ?? ('/' . $pt); }
        }

        // сколько ссылок ставить: из донора (если есть) иначе медиана типа
        $n = $donor['pages'][$type]['intlinks']
            ?? ($cfg['links_per_type'][$type] ?? 5);
        $n = max(0, (int) round($n * $rng->range(0.9, 1.1)));

        // веса целей (кроме самой страницы)
        $weights = [];
        foreach (($cfg['target_weights'] ?? []) as $t => $w) {
            if ($t !== $type && isset($paths[$t])) { $weights[$t] = $w; }
        }
        if ($weights === []) { return []; }

        $brandRate = (float) ($cfg['brand_anchor_rate'] ?? 0.04);
        $out = [];
        for ($i = 0; $i < $n; $i++) {
            $target = $rng->weighted($weights);            // с повторами
            $anchors = $cfg['anchors'][$target] ?? [$target];
            $tpl = $rng->pick($anchors);
            // бренд лишь в ~4% анкоров; иначе убираем плейсхолдеры
            if ($rng->chance($brandRate)) {
                $anchor = str_replace(['{ru}', '{en}'], [$brandRu, $brandEn], $tpl);
            } else {
                $anchor = trim(preg_replace('/\{(ru|en)\}/', '', $tpl));
                if ($anchor === '') { $anchor = $target; }
            }
            $out[] = ['path' => $paths[$target], 'anchor' => $anchor, 'target' => $target];
        }
        return $out;
    }

    /** Кластерные id доноров → читаемые метки для промпта */
    private function labelClusters(array $sem): array
    {
        $labels = [
            'official'=>'офиц. сайт', 'access'=>'зеркало / доступ', 'registr'=>'регистрация',
            'money'=>'платежи / вывод', 'bonus'=>'бонусы', 'games'=>'слоты / игры',
            'app'=>'приложение', 'betting'=>'ставки / спорт', 'support'=>'поддержка / отзывы',
        ];
        $out = [];
        foreach ($sem as $k => $v) { $out[$labels[$k] ?? $k] = $v; }
        arsort($out);
        return $out;
    }

    /** Определение регистра (гайд + примеры фраз) из пула по id */
    private function resolveRegister(string $id): array
    {
        $regs = $this->pools['style_registers'] ?? [];
        $def = $regs[$id] ?? $regs['neutral'] ?? null;
        if ($def === null) { return ['id' => $id, 'label' => $id, 'guide' => '', 'samples' => []]; }
        return [
            'id'      => $id,
            'label'   => $def['label'] ?? $id,
            'voice'   => $def['voice'] ?? '',
            'guide'   => $def['guide'] ?? '',
            'samples' => $def['samples'] ?? [],
        ];
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
