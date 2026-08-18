<?php
declare(strict_types=1);

/**
 * Текстовые метрики: объём, тошнота, водность, Ципф, читабельность, типографика.
 * Работает по чистому тексту (без HTML).
 */
final class TextMetrics
{
    private const VOWELS = 'аеёиоуыэюяАЕЁИОУЫЭЮЯ';

    public string $text;
    /** @var string[] */
    public array $words = [];
    /** @var string[] основы слов (для морфологического сопоставления ключей) */
    public array $stems = [];
    /** @var array<string,int> */
    public array $freq = [];
    /** @var string[] */
    public array $sentences = [];
    /** @var string[] */
    public array $paragraphs = [];

    public function __construct(string $text)
    {
        $this->text = $text;
        $this->tokenize();
    }

    private function tokenize(): void
    {
        // слова: кириллица/латиница/цифры/дефис
        preg_match_all('/[\p{L}\p{Nd}][\p{L}\p{Nd}\-]*/u', mb_strtolower($this->text, 'UTF-8'), $m);
        $this->words = $m[0];
        foreach ($this->words as $w) {
            $this->freq[$w] = ($this->freq[$w] ?? 0) + 1;
            $this->stems[] = Morphology::stem($w);
        }
        arsort($this->freq);

        // предложения
        $parts = preg_split('/(?<=[.!?…])\s+/u', trim($this->text)) ?: [];
        $this->sentences = array_values(array_filter($parts, fn($s) => trim($s) !== ''));

        // абзацы
        $paras = preg_split('/\n{2,}|\n/u', trim($this->text)) ?: [];
        $this->paragraphs = array_values(array_filter($paras, fn($s) => trim($s) !== ''));
    }

    public function wordCount(): int { return count($this->words); }

    public function charsNoSpaces(): int
    {
        return mb_strlen(preg_replace('/\s+/u', '', $this->text) ?? '', 'UTF-8');
    }

    public function uniqueRatio(): float
    {
        $n = $this->wordCount();
        return $n ? round(count($this->freq) / $n * 100, 1) : 0.0;
    }

    public function avgSentenceLen(): float
    {
        $s = count($this->sentences);
        return $s ? round($this->wordCount() / $s, 1) : 0.0;
    }

    public function longParagraphs(int $limit = 100): int
    {
        $c = 0;
        foreach ($this->paragraphs as $p) {
            preg_match_all('/[\p{L}\p{Nd}]+/u', $p, $mm);
            if (count($mm[0]) > $limit) { $c++; }
        }
        return $c;
    }

    /** значимые (не стоп-) слова и их частоты */
    private function contentFreq(): array
    {
        $out = [];
        foreach ($this->freq as $w => $c) {
            $w = (string) $w;
            if (mb_strlen($w, 'UTF-8') < 3) { continue; }
            if (StopWords::is($w)) { continue; }
            $out[$w] = $c;
        }
        return $out;
    }

    /** классическая тошнота = sqrt(частота самого частого значимого слова) */
    public function nauseaClassic(): float
    {
        $cf = $this->contentFreq();
        $max = $cf ? max($cf) : 0;
        return round(sqrt($max), 2);
    }

    /** академическая тошнота = сумма повторов значимых слов / все слова * 100 */
    public function nauseaAcademic(): float
    {
        $n = $this->wordCount();
        if (!$n) { return 0.0; }
        $repeated = 0;
        foreach ($this->contentFreq() as $c) {
            if ($c > 1) { $repeated += $c; }
        }
        return round($repeated / $n * 100, 1);
    }

    /** водность = стоп-слова / все слова * 100 */
    public function water(): float
    {
        $n = $this->wordCount();
        if (!$n) { return 0.0; }
        $stop = 0;
        foreach ($this->words as $w) {
            if (StopWords::is($w)) { $stop++; }
        }
        return round($stop / $n * 100, 1);
    }

    public function stopwordCount(): int
    {
        $c = 0;
        foreach ($this->words as $w) { if (StopWords::is($w)) { $c++; } }
        return $c;
    }

    private const FILLERS = [
        'в связи с тем что','на сегодняшний день','в первую очередь','как правило',
        'в том числе','в целом','в конечном итоге','стоит отметить','следует отметить',
        'не секрет что','ни для кого не секрет','в наше время','играет важную роль',
    ];
    public function fillerPhrases(): int
    {
        $t = mb_strtolower($this->text, 'UTF-8');
        $c = 0;
        foreach (self::FILLERS as $f) { $c += substr_count($t, $f); }
        return $c;
    }

    /** соответствие закону Ципфа, % (по значимым словам) */
    public function zipfScore(): float
    {
        $cf = array_values($this->contentFreq());
        $n = min(count($cf), 20);
        if ($n < 3) { return 0.0; }
        $top = $cf[0];
        $errSum = 0.0;
        for ($r = 1; $r <= $n; $r++) {
            $expected = $top / $r;
            $actual = $cf[$r - 1];
            $errSum += abs($actual - $expected) / max($expected, 1);
        }
        $score = 100 - ($errSum / $n) * 100;
        return round(max(0, min(100, $score)), 0);
    }

    private function syllables(string $word): int
    {
        return max(1, preg_match_all('/[' . self::VOWELS . ']/u', $word));
    }

    private function totalSyllables(): int
    {
        $s = 0;
        foreach ($this->words as $w) { $s += $this->syllables($w); }
        return $s;
    }

    private function complexWords(): int
    {
        $c = 0;
        foreach ($this->words as $w) { if ($this->syllables($w) > 4) { $c++; } }
        return $c;
    }

    /** Индекс Флеша, адаптированный под русский (Оборнева) */
    public function fleschReadingEase(): float
    {
        $w = $this->wordCount(); $s = count($this->sentences);
        if (!$w || !$s) { return 0.0; }
        $asl = $w / $s;                       // средняя длина предложения
        $asw = $this->totalSyllables() / $w;  // слогов на слово
        return round(206.835 - 1.3 * $asl - 60.1 * $asw, 1);
    }

    /** Флеш-Кинкейд (класс), русские коэффициенты */
    public function fleschKincaidGrade(): float
    {
        $w = $this->wordCount(); $s = count($this->sentences);
        if (!$w || !$s) { return 0.0; }
        $asl = $w / $s;
        $asw = $this->totalSyllables() / $w;
        return round(max(0, 0.5 * $asl + 8.4 * $asw - 15.59), 1);
    }

    /** Индекс туманности Ганнинга */
    public function gunningFog(): float
    {
        $w = $this->wordCount(); $s = count($this->sentences);
        if (!$w || !$s) { return 0.0; }
        return round(0.4 * ($w / $s + 100 * $this->complexWords() / $w), 1);
    }

    public function readabilityAvg(): float
    {
        // сводим к шкале Флеша (чем выше — тем легче)
        return $this->fleschReadingEase();
    }

    /** ТОП частотных значимых слов для графика */
    public function topWords(int $limit = 10): array
    {
        $out = [];
        foreach ($this->contentFreq() as $w => $c) {
            $out[] = [$w, $c];
            if (count($out) >= $limit) { break; }
        }
        return $out;
    }

    // --- типографика ---
    public function doubleSpaces(): int
    {
        preg_match_all('/ {2,}/', $this->text, $m);
        return count($m[0]);
    }

    public function badQuotes(): int
    {
        return substr_count($this->text, '"');
    }

    public function capsAbuse(): int
    {
        preg_match_all('/\b[\p{Lu}]{4,}\b/u', $this->text, $m);
        return count($m[0]);
    }

    /** число вхождений ключа по основам слов (морфология) */
    public function keywordStemCount(string $keyword): int
    {
        $need = Morphology::stemPhrase($keyword);
        if (!$need) { return 0; }
        $nlen = count($need);
        $tlen = count($this->stems);
        $count = 0;
        for ($i = 0; $i + $nlen <= $tlen; $i++) {
            if (array_slice($this->stems, $i, $nlen) === $need) { $count++; }
        }
        return $count;
    }

    /** плотность ключа, % (доля слов текста, занятых вхождениями ключа) */
    public function keywordDensity(string $keyword): float
    {
        $need = Morphology::stemPhrase($keyword);
        $n = $this->wordCount();
        if (!$need || !$n) { return 0.0; }
        return round($this->keywordStemCount($keyword) * count($need) / $n * 100, 2);
    }

    public function keywordExactCount(string $keyword): int
    {
        return $this->keywordStemCount($keyword);
    }

    public function keywordInFirstParagraph(string $keyword): bool
    {
        if (trim($keyword) === '' || !$this->paragraphs) { return false; }
        $stems = Morphology::stemPhrase($this->paragraphs[0]);
        return Morphology::allWordsInText($keyword, $stems);
    }
}
