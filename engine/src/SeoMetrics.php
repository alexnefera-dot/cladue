<?php
declare(strict_types=1);

/**
 * SEO / HTML-метрики on-page: метатеги, заголовки, изображения, ссылки,
 * микроразметка, форматирование, соотношение текст/код.
 * Требует DOMDocument (для plain-text большинство полей = дефолт/недоступно).
 */
final class SeoMetrics
{
    private ?DOMDocument $dom;
    private string $rawHtml;
    private DOMXPath $xp;

    public function __construct(?DOMDocument $dom, string $rawHtml)
    {
        $this->dom = $dom;
        $this->rawHtml = $rawHtml;
        $this->xp = $dom ? new DOMXPath($dom) : new DOMXPath(new DOMDocument());
    }

    public function hasDom(): bool { return $this->dom !== null; }

    private function first(string $query): ?DOMNode
    {
        if (!$this->dom) { return null; }
        $r = $this->xp->query($query);
        return $r && $r->length ? $r->item(0) : null;
    }

    private function count(string $query): int
    {
        if (!$this->dom) { return 0; }
        $r = $this->xp->query($query);
        return $r ? $r->length : 0;
    }

    // --- метатеги ---
    public function title(): string
    {
        $n = $this->first('//title');
        return $n ? trim($n->textContent) : '';
    }

    public function metaContent(string $name): string
    {
        $n = $this->first("//meta[translate(@name,'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz')='{$name}']");
        return $n instanceof DOMElement ? trim($n->getAttribute('content')) : '';
    }

    public function description(): string { return $this->metaContent('description'); }

    public function h1Text(): string
    {
        $n = $this->first('//h1');
        return $n ? trim($n->textContent) : '';
    }

    public function headingCount(int $level): int { return $this->count("//h{$level}"); }

    /** текст всех заголовков H1–H3 (для определения интента страницы) */
    public function headingsText(): string
    {
        if (!$this->dom) { return ''; }
        $parts = [];
        foreach ($this->xp->query('//h1|//h2|//h3') ?: [] as $h) {
            $parts[] = trim($h->textContent);
        }
        return implode(' ', $parts);
    }

    /** корректность иерархии заголовков (нет пропуска уровней) */
    public function headingHierarchyOk(): bool
    {
        if (!$this->dom) { return true; }
        $levels = [];
        foreach ($this->xp->query('//h1|//h2|//h3|//h4|//h5|//h6') ?: [] as $h) {
            $levels[] = (int) substr($h->nodeName, 1);
        }
        $prev = 0;
        foreach ($levels as $l) {
            if ($prev && $l > $prev + 1) { return false; }
            $prev = $l;
        }
        return true;
    }

    // --- изображения ---
    public function imgCount(): int { return $this->count('//img'); }

    public function imgAltFilledPercent(): float
    {
        $total = $this->imgCount();
        if (!$total) { return 100.0; }
        $filled = 0;
        foreach ($this->xp->query('//img') ?: [] as $img) {
            if ($img instanceof DOMElement && trim($img->getAttribute('alt')) !== '') { $filled++; }
        }
        return round($filled / $total * 100, 0);
    }

    // --- микроразметка / тех ---
    public function hasSchema(): bool
    {
        return $this->count('//script[@type="application/ld+json"]') > 0
            || $this->count('//*[@itemscope]') > 0;
    }

    public function langAttr(): bool
    {
        $html = $this->first('//html');
        return $html instanceof DOMElement && $html->getAttribute('lang') !== '';
    }

    public function hasViewport(): bool
    {
        return $this->metaContent('viewport') !== ''
            || $this->count('//meta[@name="viewport"]') > 0;
    }

    public function textHtmlRatio(): float
    {
        $html = strlen($this->rawHtml);
        if (!$html) { return 0.0; }
        $text = strlen(strip_tags($this->rawHtml));
        return round($text / $html * 100, 1);
    }

    // --- форматирование ---
    public function listCount(): int { return $this->count('//ul|//ol'); }
    public function strongCount(): int { return $this->count('//strong|//b'); }
    public function emCount(): int { return $this->count('//em|//i'); }
    public function tableCount(): int { return $this->count('//table'); }
    public function videoCount(): int { return $this->count('//video|//iframe'); }

    public function mediaRichness(): int
    {
        return $this->imgCount() + $this->listCount() + $this->tableCount() + $this->videoCount();
    }

    /** переспам выделением ключа: >30% strong содержат ключ */
    public function strongKeywordSpam(string $keyword): bool
    {
        $keyword = mb_strtolower(trim($keyword), 'UTF-8');
        if ($keyword === '' || !$this->dom) { return false; }
        $total = 0; $withKw = 0;
        foreach ($this->xp->query('//strong|//b') ?: [] as $n) {
            $total++;
            if (mb_strpos(mb_strtolower($n->textContent, 'UTF-8'), $keyword, 0, 'UTF-8') !== false) { $withKw++; }
        }
        return $total >= 3 && $withKw / $total > 0.3;
    }

    // --- ссылки ---
    /**
     * @return array{internal:list<array{href:string,anchor:string,nofollow:bool}>,
     *               external:list<array{href:string,anchor:string,nofollow:bool}>}
     */
    public function links(string $domain, string $selfUrl): array
    {
        $internal = []; $external = [];
        if (!$this->dom) { return ['internal' => [], 'external' => []]; }
        foreach ($this->xp->query('//a[@href]') ?: [] as $a) {
            if (!$a instanceof DOMElement) { continue; }
            $href = trim($a->getAttribute('href'));
            if ($href === '' || str_starts_with($href, '#')
                || str_starts_with($href, 'mailto:') || str_starts_with($href, 'tel:')
                || str_starts_with($href, 'javascript:')) { continue; }
            $rel = strtolower($a->getAttribute('rel'));
            $item = [
                'href'     => $href,
                'anchor'   => trim($a->textContent),
                'nofollow' => str_contains($rel, 'nofollow'),
            ];
            if ($this->isInternal($href, $domain)) { $internal[] = $item; }
            else { $external[] = $item; }
        }
        return ['internal' => $internal, 'external' => $external];
    }

    private function isInternal(string $href, string $domain): bool
    {
        if ($href === '') { return false; }
        if (!preg_match('#^https?://#i', $href)) { return true; }        // относительная
        if ($domain === '') { return false; }
        $host = parse_url($href, PHP_URL_HOST) ?: '';
        return $host !== '' && str_contains($host, $domain);
    }
}
