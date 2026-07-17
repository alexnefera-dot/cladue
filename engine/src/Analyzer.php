<?php
declare(strict_types=1);

require_once __DIR__ . '/StopWords.php';
require_once __DIR__ . '/Morphology.php';
require_once __DIR__ . '/Parser.php';
require_once __DIR__ . '/TextMetrics.php';
require_once __DIR__ . '/SeoMetrics.php';
require_once __DIR__ . '/Similarity.php';
require_once __DIR__ . '/LinkGraph.php';

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
    public function __construct(private string $domain = '') {}

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

        foreach ($parsed as $i => $pp) {
            /** @var Parser $parser */
            $parser = $pp['parser'];
            $in = $pp['input'];
            $keyword = (string) ($in['keyword'] ?? '');
            $lsi = (array) ($in['lsi'] ?? []);

            $tm = new TextMetrics($parser->text);
            $seo = new SeoMetrics($parser->dom, $parser->rawHtml);

            $links = $seo->links($this->domain, (string) ($in['url'] ?? ''));
            $pageKeys[] = (string) ($in['url'] ?? $in['name'] ?? ("page-" . ($i + 1)));
            $pageLinks[] = array_map(fn($l) => $l['href'], $links['internal']);
            foreach ($links['internal'] as $l) { $allAnchors[] = mb_strtolower($l['anchor'], 'UTF-8'); }

            $texts[] = $parser->text;

            $out['pages'][] = [
                'name'    => (string) ($in['name'] ?? ('Страница ' . ($i + 1))),
                'url'     => (string) ($in['url'] ?? ''),
                'keyword' => $keyword === '' ? [] : [$keyword],
                'metrics' => $this->pageMetrics($tm, $seo, $keyword, $lsi, $links),
                'wordFreq'=> $tm->topWords(10),
            ];
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

        return $out;
    }

    private function parseInput(array $p): Parser
    {
        if (!empty($p['file']) && is_file((string) $p['file'])) {
            return Parser::fromFile((string) $p['file'], (string) ($p['filename'] ?? $p['file']));
        }
        if (!empty($p['html'])) { return Parser::fromHtml((string) $p['html']); }
        return Parser::fromText((string) ($p['text'] ?? ''));
    }

    /** @return array<string,mixed> */
    private function pageMetrics(TextMetrics $tm, SeoMetrics $seo, string $keyword, array $lsi, array $links): array
    {
        $title = $seo->title();
        $h1 = $seo->h1Text();
        $inTitle = $keyword !== '' && Morphology::allWordsInText($keyword, Morphology::stemPhrase($title));
        $inH1 = $keyword !== '' && Morphology::allWordsInText($keyword, Morphology::stemPhrase($h1));

        $wordN = max($tm->wordCount(), 1);
        $densities = [];
        foreach (array_merge([$keyword], $lsi) as $k) {
            if (trim((string) $k) !== '') { $densities[] = $tm->keywordDensity((string) $k); }
        }
        $kwDensityMax = $densities ? max($densities) : 0.0;
        $kwExact = $tm->keywordExactCount($keyword);
        // доля точных вхождений ключа среди всех вхождений слов ключа (риск переспама)
        $exactRatio = $keyword !== '' && $kwExact > 0
            ? min(100, round($tm->keywordDensity($keyword), 1))
            : 0;

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
            'keyword_density_max'=> $kwDensityMax,
            'kw_exact_ratio'     => min(100, $exactRatio),
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
            // ключи
            'kw_exact'           => $kwExact,
            'kw_first_para'      => $tm->keywordInFirstParagraph($keyword),
            'kw_in_title'        => $inTitle,
            'kw_in_h1'           => $inH1,
            'lsi_coverage'       => $this->lsiCoverage($tm, $lsi),
            // заголовки
            'h1_count'           => $seo->headingCount(1),
            'h1_title_diff'      => trim($h1) !== '' && mb_strtolower(trim($h1), 'UTF-8') !== mb_strtolower(trim($title), 'UTF-8'),
            'h2_count'           => $seo->headingCount(2),
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
            'strong_count'       => $seo->strongCount(),
            'strong_kw_spam'     => $seo->strongKeywordSpam($keyword),
            'media_richness'     => $seo->mediaRichness(),
            // типографика
            'double_spaces'      => $tm->doubleSpaces(),
            'typo_quotes'        => $tm->badQuotes(),
            'caps_abuse'         => $tm->capsAbuse(),
        ];
    }

    private function lsiCoverage(TextMetrics $tm, array $lsi): float
    {
        $lsi = array_filter(array_map('trim', $lsi), fn($s) => $s !== '');
        if (!$lsi) { return 0.0; }
        $hit = 0;
        foreach ($lsi as $w) {
            if (Morphology::phraseInText($w, $tm->stems)) { $hit++; }
        }
        return round($hit / count($lsi) * 100, 0);
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
