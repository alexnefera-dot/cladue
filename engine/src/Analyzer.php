<?php
declare(strict_types=1);

require_once __DIR__ . '/StopWords.php';
require_once __DIR__ . '/Morphology.php';
require_once __DIR__ . '/Parser.php';
require_once __DIR__ . '/TextMetrics.php';
require_once __DIR__ . '/SeoMetrics.php';
require_once __DIR__ . '/Similarity.php';
require_once __DIR__ . '/LinkGraph.php';
require_once __DIR__ . '/BrandBase.php';
require_once __DIR__ . '/Intent.php';
require_once __DIR__ . '/Stylistics.php';

/**
 * Оркестратор анализа. На входе — до 7 страниц; на выходе — структура,
 * идентичная демо-данным фронтенда (assets/app.js), поэтому рендер не меняется.
 *
 * Каждый элемент $pages:
 *   [ 'name' => string, 'url' => string, 'html' => ?string, 'text' => ?string,
 *     'keyword' => string, 'lsi' => string[] ]
 */
final class Analyzer
{
    private BrandBase $brands;

    public function __construct(
        private string $domain = '',
        ?BrandBase $brands = null,
        private bool $fullQueries = false   // прикладывать полный список найденных запросов (для сравнения)
    ) {
        $this->brands = $brands ?? new BrandBase();
    }

    /** @param array<int,array<string,mixed>> $pages */
    public function run(array $pages): array
    {
        $parsed = [];
        foreach ($pages as $p) {
            $parser = $this->parseInput($p);
            $parsed[] = ['input' => $p, 'parser' => $parser];
        }

        $out = ['pages' => [], 'link' => [], 'shingle' => []];
        $texts = [];
        $pageKeys = [];
        $pageLinks = [];
        $allAnchors = [];
        $allFound = [];
        $allBrandKeys = [];
        $pageIntents = [];
        $brandNames = array_map(fn($b) => (string) $b['name'], $this->brands->index());

        foreach ($parsed as $i => $pp) {
            /** @var Parser $parser */
            $parser = $pp['parser'];
            $in = $pp['input'];

            $tm = new TextMetrics($parser->text);
            $seo = new SeoMetrics($parser->dom, $parser->rawHtml);

            // определение бренда: ручной выбор -> иначе авто по контенту
            $brandOverride = trim((string) ($in['brand'] ?? ''));
            $brandInfo = $brandOverride !== ''
                ? $this->brands->byName($brandOverride)
                : $this->brands->detect(mb_strtolower($parser->text, 'UTF-8') . ' ' . mb_strtolower($seo->title(), 'UTF-8'));

            // бренд вне базы: заданный ключ есть, но в базе его нет -> ручной ключ
            // (покрытие по базе не считаем, ключевые метрики — по этому ключу)
            $manualKeyword = ($brandOverride !== '' && !$brandInfo) ? $brandOverride : '';
            $semantics = $this->brandSemantics($tm, $seo, $brandInfo, $manualKeyword);

            // страховка от ложного определения: если ни один запрос бренда не найден
            // в тексте (авто-режим), считаем бренд неопределённым
            if ($brandOverride === '' && $brandInfo && $semantics['queries_found'] === 0) {
                $brandInfo = null;
                $semantics = $this->brandSemantics($tm, $seo, null);
            }

            // интент страницы: доминирующая тема по контенту (+ заголовки), с хинтом из имени/URL
            $intentText = $seo->headingsText() . ' ' . $parser->text;
            $intentHint = (string) ($in['name'] ?? '') . ' ' . (string) ($in['url'] ?? '');
            $pageIntent = Intent::dominant($intentText, (array) ($brandInfo['keys'] ?? []), $intentHint);

            $links = $seo->links($this->domain, (string) ($in['url'] ?? ''));
            $pageKeys[] = (string) ($in['url'] ?? $in['name'] ?? ("page-" . ($i + 1)));
            $pageLinks[] = array_map(fn($l) => $l['href'], $links['internal']);
            foreach ($links['internal'] as $l) { $allAnchors[] = mb_strtolower($l['anchor'], 'UTF-8'); }

            $texts[] = $parser->text;

            $brandForStyle = (string) ($brandInfo['name'] ?? $manualKeyword);
            $page = [
                'name'     => (string) ($in['name'] ?? ('Страница ' . ($i + 1))),
                'url'      => (string) ($in['url'] ?? ''),
                'brand'    => $brandInfo['name'] ?? ($manualKeyword !== '' ? $manualKeyword : null),
                'inBase'   => $brandInfo !== null,
                'pageIntent' => $pageIntent,
                'stylistics' => Stylistics::of($tm, $seo, $brandForStyle, $brandNames),
                'keyword'  => $semantics['main_keyword'] === '' ? [] : [$semantics['main_keyword']],
                'metrics'  => $this->pageMetrics($tm, $seo, $semantics, $links),
                'wordFreq' => $tm->topWords(10),
                'missingQueries' => $semantics['missing_top'],
                'foundQueries'   => $semantics['found_top'],
                'orientation'    => $semantics['orientation'],
            ];
            if ($this->fullQueries) {
                $page['foundAll'] = $semantics['found_all'];   // для разрыва запросов в сравнении
            }
            $out['pages'][] = $page;
            $allFound = array_merge($allFound, $semantics['found_all']);
            if ($brandInfo) { $allBrandKeys = array_merge($allBrandKeys, (array) ($brandInfo['keys'] ?? [])); }
            $pageIntents[] = ['theme' => $pageIntent, 'words' => $tm->wordCount()];
        }

        // матрицы уровня проекта
        $out['shingle'] = Similarity::matrix($texts);
        $graph = new LinkGraph($pageKeys, $pageLinks);
        $out['link'] = $graph->matrix;

        // дубли Title между страницами
        $this->markDuplicateTitles($out['pages']);

        // проектные метрики (фронт также умеет считать их из матриц; отдаём готовыми)
        $anchorDiversity = $allAnchors
            ? round(count(array_unique(array_filter($allAnchors))) / max(count($allAnchors), 1) * 100, 0)
            : 0;
        $out['project'] = [
            'orphan_pages'       => $graph->orphanPages(),
            'dead_end_pages'     => $graph->deadEndPages(),
            'avg_internal_links' => $graph->avgOutgoing(),
            'max_link_depth'     => $graph->maxDepth(),
            'anchor_diversity'   => $anchorDiversity,
            'internal_uniqueness'=> $this->minUniqueness($out['shingle']),
            'dup_paragraphs'     => $this->dupParagraphs($texts),
        ];

        // на что ориентирован весь набор:
        //  - если бренд(ы) в базе — профиль по покрытым запросам (взвешен кликами);
        //  - иначе (бренд вне базы) — по интентам страниц, взвешено объёмом текста.
        $out['orientation'] = $allFound
            ? Intent::profile($allFound, array_values(array_unique($allBrandKeys)))
            : $this->orientationFromPages($pageIntents);
        $out['orientationSource'] = $allFound ? 'queries' : 'pages';
        $out['stylistics'] = $this->aggregateStylistics($out['pages']);
        $out['brandsDetected'] = array_values(array_unique(array_filter(
            array_map(fn($p) => $p['brand'], $out['pages'])
        )));

        return $out;
    }

    /**
     * Ориентация набора без базы: распределение по интентам страниц,
     * взвешенное объёмом текста каждой страницы.
     * @param array<int,array{theme:string,words:int}> $pageIntents
     */
    private function orientationFromPages(array $pageIntents): array
    {
        $byTheme = []; $total = 0;
        foreach ($pageIntents as $p) {
            $w = max(1, (int) $p['words']);
            $byTheme[$p['theme']] = ($byTheme[$p['theme']] ?? 0) + $w;
            $total += $w;
        }
        arsort($byTheme);
        $out = [];
        foreach ($byTheme as $theme => $w) {
            $out[$theme] = [
                'clicks' => $w,   // здесь «вес» = слова, не клики
                'share'  => $total ? round($w / $total * 100, 1) : 0.0,
                'label'  => $theme === 'brand' ? 'Брендовые' : ($theme === 'other' ? 'Прочее' : (Intent::THEMES[$theme]['label'] ?? $theme)),
            ];
        }
        return $out;
    }

    /** сводная стилистическая подпись набора (доли и средние по страницам) */
    private function aggregateStylistics(array $pages): array
    {
        $n = max(count($pages), 1);
        $sum = fn($f) => array_sum(array_map($f, $pages));
        $entities = [];
        $foreign = [];
        foreach ($pages as $p) {
            foreach (($p['stylistics']['entities'] ?? []) as $e) { $entities[$e] = ($entities[$e] ?? 0) + 1; }
            foreach (($p['stylistics']['foreign_brands'] ?? []) as $b) { $foreign[$b] = ($foreign[$b] ?? 0) + 1; }
        }
        arsort($entities);
        return [
            'pages'              => count($pages),
            'first_person_share' => round($sum(fn($p) => ($p['stylistics']['first_person'] ?? 0) >= 2 ? 1 : 0) / $n * 100),
            'you_address_share'  => round($sum(fn($p) => ($p['stylistics']['second_person'] ?? 0) >= 2 ? 1 : 0) / $n * 100),
            'faq_share'          => round($sum(fn($p) => !empty($p['stylistics']['faq_present']) ? 1 : 0) / $n * 100),
            'date_fresh_share'   => round($sum(fn($p) => !empty($p['stylistics']['date_freshness']) ? 1 : 0) / $n * 100),
            'avg_numbers_100w'   => round($sum(fn($p) => $p['stylistics']['numbers_per_100w'] ?? 0) / $n, 1),
            'avg_adj_pct'        => round($sum(fn($p) => $p['stylistics']['adj_pct'] ?? 0) / $n, 1),
            'avg_imperatives'    => round($sum(fn($p) => $p['stylistics']['imperatives'] ?? 0) / $n, 1),
            'avg_faq_questions'  => round($sum(fn($p) => $p['stylistics']['faq_questions'] ?? 0) / $n, 1),
            'entities'           => $entities,
            'foreign_brands'     => $foreign,
        ];
    }

    private function parseInput(array $p): Parser
    {
        if (!empty($p['file']) && is_file((string) $p['file'])) {
            return Parser::fromFile((string) $p['file'], (string) ($p['filename'] ?? $p['file']));
        }
        if (!empty($p['html'])) { return Parser::fromHtml((string) $p['html']); }
        return Parser::fromText((string) ($p['text'] ?? ''));
    }

    /**
     * Семантика по базе бренда: покрытие запросов и кликов, топ-запрос,
     * упущенные и найденные запросы. Заменяет ручной ввод ключей/LSI.
     * @return array<string,mixed>
     */
    private function brandSemantics(TextMetrics $tm, SeoMetrics $seo, ?array $brandInfo, string $manualKeyword = ''): array
    {
        $empty = [
            'main_keyword' => '', 'query_coverage' => 0.0, 'clicks_coverage' => 0.0,
            'queries_found' => 0, 'queries_total' => 0, 'main_kw_density' => 0.0,
            'top_in_title' => false, 'top_in_h1' => false, 'top_in_first_para' => false,
            'missing_top' => [], 'found_top' => [], 'found_all' => [], 'orientation' => [],
        ];
        // бренд вне базы: считаем ключевые метрики по заданному ключу, без покрытия
        if (!$brandInfo && $manualKeyword !== '') {
            $firstParaStems = $tm->paragraphs ? array_flip(Morphology::stemPhrase($tm->paragraphs[0])) : [];
            return array_merge($empty, [
                'main_keyword'    => $manualKeyword,
                'main_kw_density' => $tm->keywordDensity($manualKeyword),
                'top_in_title'    => Morphology::allWordsInText($manualKeyword, Morphology::stemPhrase($seo->title())),
                'top_in_h1'       => Morphology::allWordsInText($manualKeyword, Morphology::stemPhrase($seo->h1Text())),
                'top_in_first_para' => Morphology::allStemsInSet(Morphology::stemPhrase($manualKeyword), $firstParaStems),
            ]);
        }
        if (!$brandInfo) { return $empty; }

        $queries = $this->brands->queries((string) ($brandInfo['file'] ?? ''));
        if (!$queries) { return $empty; }

        $stemSet = array_flip($tm->stems);
        $firstParaStems = $tm->paragraphs ? array_flip(Morphology::stemPhrase($tm->paragraphs[0])) : [];

        $brandName = (string) ($brandInfo['name'] ?? '');
        $found = 0; $clicksTotal = 0; $clicksFound = 0;
        $missing = []; $foundList = []; $foundAll = [];
        foreach ($queries as [$q, $clicks]) {
            $clicks = (int) $clicks;
            $clicksTotal += $clicks;
            $need = Morphology::stemPhrase((string) $q);
            if (Morphology::allStemsInSet($need, $stemSet)) {
                $found++; $clicksFound += $clicks;
                $foundAll[] = [$q, $clicks];
                if (count($foundList) < 20) { $foundList[] = ['q' => $q, 'clicks' => $clicks]; }
            } elseif (count($missing) < 20) {
                $missing[] = ['q' => $q, 'clicks' => $clicks];   // упущенные (идут по убыванию кликов)
            }
        }

        $mainKeyword = (string) ($queries[0][0] ?? '');
        $title = $seo->title();
        $h1 = $seo->h1Text();

        return [
            'main_keyword'    => $mainKeyword,
            'query_coverage'  => round($found / max(count($queries), 1) * 100, 1),
            'clicks_coverage' => round($clicksFound / max($clicksTotal, 1) * 100, 1),
            'queries_found'   => $found,
            'queries_total'   => count($queries),
            'main_kw_density' => $tm->keywordDensity($mainKeyword),
            'top_in_title'    => $mainKeyword !== '' && Morphology::allWordsInText($mainKeyword, Morphology::stemPhrase($title)),
            'top_in_h1'       => $mainKeyword !== '' && Morphology::allWordsInText($mainKeyword, Morphology::stemPhrase($h1)),
            'top_in_first_para' => $mainKeyword !== '' && Morphology::allStemsInSet(Morphology::stemPhrase($mainKeyword), $firstParaStems),
            'missing_top'     => $missing,
            'found_top'       => $foundList,
            'found_all'       => $foundAll,
            'orientation'     => Intent::profile($foundAll, (array) ($brandInfo['keys'] ?? [])),
        ];
    }

    /** @param array<string,mixed> $sem семантика из brandSemantics() */
    private function pageMetrics(TextMetrics $tm, SeoMetrics $seo, array $sem, array $links): array
    {
        $title = $seo->title();
        $h1 = $seo->h1Text();
        $mainKeyword = (string) $sem['main_keyword'];

        return [
            // объём
            'words_total'        => $tm->wordCount(),
            'chars_no_spaces'    => $tm->charsNoSpaces(),
            'words_unique_ratio' => $tm->uniqueRatio(),
            'sentences_total'    => count($tm->sentences),
            'sentence_avg_len'   => $tm->avgSentenceLen(),
            'paragraphs_total'   => count($tm->paragraphs),
            'paragraph_long_count' => $tm->longParagraphs(),
            // тошнота
            'nausea_classic'     => $tm->nauseaClassic(),
            'nausea_academic'    => $tm->nauseaAcademic(),
            'keyword_density_max'=> $sem['main_kw_density'],
            // водность
            'water_percent'      => $tm->water(),
            'stopword_count'     => $tm->stopwordCount(),
            'filler_phrases'     => $tm->fillerPhrases(),
            // естественность
            'zipf_score'         => $tm->zipfScore(),
            // читабельность
            'flesch_reading_ease'=> $tm->fleschReadingEase(),
            'flesch_kincaid_grade'=> $tm->fleschKincaidGrade(),
            'gunning_fog'        => $tm->gunningFog(),
            'readability_avg'    => $tm->readabilityAvg(),
            // семантика по базе бренда
            'clicks_coverage'    => $sem['clicks_coverage'],
            'query_coverage'     => $sem['query_coverage'],
            'queries_found'      => $sem['queries_found'],
            'queries_total'      => $sem['queries_total'],
            'top_in_title'       => $sem['top_in_title'],
            'top_in_h1'          => $sem['top_in_h1'],
            'top_in_first_para'  => $sem['top_in_first_para'],
            // заголовки
            'h1_count'           => $seo->headingCount(1),
            'h1_title_diff'      => trim($h1) !== '' && mb_strtolower(trim($h1), 'UTF-8') !== mb_strtolower(trim($title), 'UTF-8'),
            'h2_count'           => $seo->headingCount(2),
            'h3_count'           => $seo->headingCount(3),
            'heading_hierarchy'  => $seo->headingHierarchyOk(),
            // метатеги
            'title_present'      => $title !== '',
            'title_len'          => mb_strlen($title, 'UTF-8'),
            'desc_present'       => $seo->description() !== '',
            'desc_len'           => mb_strlen($seo->description(), 'UTF-8'),
            'title_duplicate'    => false, // проставится позже
            '_title'             => $title, // служебное для дедупа
            // техника
            'text_html_ratio'    => $seo->hasDom() ? $seo->textHtmlRatio() : 100,
            'img_count'          => $seo->imgCount(),
            'img_alt_filled'     => $seo->imgAltFilledPercent(),
            'schema_present'     => $seo->hasSchema(),
            'lang_attr'          => $seo->langAttr(),
            'viewport_meta'      => $seo->hasViewport(),
            // форматирование
            'list_count'         => $seo->listCount(),
            'table_count'        => $seo->tableCount(),
            'quote_count'        => $seo->quoteCount(),
            'strong_count'       => $seo->strongCount(),
            'strong_kw_spam'     => $seo->strongKeywordSpam($mainKeyword),
            'media_richness'     => $seo->mediaRichness(),
            // типографика
            'double_spaces'      => $tm->doubleSpaces(),
            'typo_quotes'        => $tm->badQuotes(),
            'caps_abuse'         => $tm->capsAbuse(),
        ];
    }

    private function markDuplicateTitles(array &$pages): void
    {
        $seen = [];
        foreach ($pages as $p) {
            $t = mb_strtolower(trim((string) ($p['metrics']['_title'] ?? '')), 'UTF-8');
            if ($t !== '') { $seen[$t] = ($seen[$t] ?? 0) + 1; }
        }
        foreach ($pages as &$p) {
            $t = mb_strtolower(trim((string) ($p['metrics']['_title'] ?? '')), 'UTF-8');
            $p['metrics']['title_duplicate'] = $t !== '' && ($seen[$t] ?? 0) > 1;
            unset($p['metrics']['_title']);
        }
    }

    private function minUniqueness(array $shingle): int
    {
        $maxSim = 0;
        foreach ($shingle as $i => $row) {
            foreach ($row as $j => $v) { if ($i !== $j) { $maxSim = max($maxSim, $v); } }
        }
        return 100 - $maxSim;
    }

    private function dupParagraphs(array $texts): int
    {
        $seen = [];
        $dups = 0;
        foreach ($texts as $t) {
            foreach (preg_split('/\n{2,}|\n/u', $t) ?: [] as $para) {
                $norm = preg_replace('/\s+/u', ' ', mb_strtolower(trim($para), 'UTF-8')) ?? '';
                if (mb_strlen($norm, 'UTF-8') < 40) { continue; }
                $h = crc32($norm);
                if (isset($seen[$h])) { $dups++; } else { $seen[$h] = true; }
            }
        }
        return $dups;
    }
}
