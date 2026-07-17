<?php
declare(strict_types=1);

/**
 * Извлечение контента из входных форматов: HTML, DOCX, plain-text.
 * Возвращает нормализованное представление: сырой HTML (если был),
 * чистый текст, DOMDocument (для HTML) и служебные поля.
 */
final class Parser
{
    public string $rawHtml = '';
    public string $text = '';
    public ?DOMDocument $dom = null;
    public string $sourceType = 'text';

    public static function fromHtml(string $html): self
    {
        $p = new self();
        $p->sourceType = 'html';
        $p->rawHtml = $html;
        $p->dom = self::loadDom($html);
        $p->text = self::domText($p->dom);
        return $p;
    }

    public static function fromText(string $text): self
    {
        $p = new self();
        // если внутри текста есть теги — трактуем как HTML
        if (preg_match('/<\s*(html|body|p|div|h[1-6]|a|img|title)\b/i', $text)) {
            return self::fromHtml($text);
        }
        $p->sourceType = 'text';
        $p->text = self::normalizeText($text);
        return $p;
    }

    /** DOCX = zip-архив; текст лежит в word/document.xml */
    public static function fromDocx(string $path): self
    {
        $p = new self();
        $p->sourceType = 'docx';
        $zip = new ZipArchive();
        if ($zip->open($path) !== true) {
            throw new RuntimeException("Не удалось открыть DOCX: {$path}");
        }
        $xml = $zip->getFromName('word/document.xml') ?: '';
        $zip->close();
        // абзацы w:p -> перенос строки, w:tab -> пробел; затем срезаем разметку
        $xml = preg_replace('/<w:tab[^>]*\/?>/', ' ', $xml);
        $xml = preg_replace('/<\/w:p>/', "\n", $xml);
        $xml = preg_replace('/<w:br[^>]*\/?>/', "\n", $xml);
        $plain = strip_tags($xml);
        $plain = html_entity_decode($plain, ENT_QUOTES | ENT_HTML5, 'UTF-8');
        $p->text = self::normalizeText($plain);
        return $p;
    }

    public static function fromFile(string $path, ?string $name = null): self
    {
        $ext = strtolower(pathinfo($name ?? $path, PATHINFO_EXTENSION));
        return match ($ext) {
            'docx', 'doc' => self::fromDocx($path),
            'html', 'htm' => self::fromHtml((string) file_get_contents($path)),
            default        => self::fromText((string) file_get_contents($path)),
        };
    }

    private static function loadDom(string $html): DOMDocument
    {
        $dom = new DOMDocument();
        $prev = libxml_use_internal_errors(true);
        // корректная обработка UTF-8
        $dom->loadHTML('<?xml encoding="UTF-8">' . $html, LIBXML_NOWARNING | LIBXML_NOERROR);
        libxml_clear_errors();
        libxml_use_internal_errors($prev);
        return $dom;
    }

    private const BLOCK_TAGS = ['p','h1','h2','h3','h4','h5','h6','li','blockquote',
                                'td','th','dd','dt','figcaption','pre','article','section','div'];

    /**
     * Видимый текст по блочным элементам (без мутации DOM). Каждый «листовой»
     * блок — отдельный абзац. Так корректно считаются абзацы/предложения и
     * определяется «первый абзац» для проверки вхождения ключа.
     */
    private static function domText(DOMDocument $dom): string
    {
        $xp = new DOMXPath($dom);
        $context = $dom->getElementsByTagName('body')->item(0) ?? $dom->documentElement;
        if (!$context) { return ''; }

        $cond = implode(' or ', array_map(fn($t) => "self::{$t}", self::BLOCK_TAGS));
        $blocks = $xp->query(".//*[{$cond}]", $context);

        $paras = [];
        foreach ($blocks ?: [] as $el) {
            if (!$el instanceof DOMElement) { continue; }
            // берём только листовые блоки (без вложенных блочных элементов)
            $inner = $xp->query("(.//*[{$cond}])[1]", $el);
            if ($inner && $inner->length) { continue; }
            // пропускаем текст внутри script/style
            $t = trim($el->textContent);
            if ($t !== '') { $paras[] = $t; }
        }

        // запасной вариант: если блоков нет — весь видимый текст
        if (!$paras) {
            $nodes = $xp->query(
                './/text()[not(ancestor::script) and not(ancestor::style) and not(ancestor::noscript)]',
                $context
            );
            foreach ($nodes ?: [] as $n) {
                $t = trim($n->textContent);
                if ($t !== '') { $paras[] = $t; }
            }
        }
        return self::normalizeText(implode("\n\n", $paras));
    }

    public static function normalizeText(string $t): string
    {
        $t = str_replace(["\r\n", "\r"], "\n", $t);
        $t = preg_replace('/[ \t\x{00A0}]+/u', ' ', $t);   // пробелы + nbsp
        $t = preg_replace('/\n{3,}/', "\n\n", $t);
        return trim($t);
    }
}
