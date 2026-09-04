<?php

declare(strict_types=1);

namespace YandexSites\Support;

/**
 * База всех когда-либо собранных доменов (по регистрируемому домену).
 * Хранится в текстовом файле, по одному домену в строке. Позволяет при повторных
 * сборах пропускать пересечения — домены, которые уже встречались раньше.
 */
final class DomainLedger
{
    /** @var array<string, true> */
    private array $set = [];

    public function __construct(private string $file)
    {
        foreach (is_file($file) ? (file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: []) : [] as $line) {
            $domain = mb_strtolower(trim($line));
            if ($domain !== '' && !str_starts_with($domain, '#')) {
                $this->set[$domain] = true;
            }
        }
    }

    public function has(string $domain): bool
    {
        return isset($this->set[mb_strtolower(trim($domain))]);
    }

    public function count(): int
    {
        return count($this->set);
    }

    /**
     * Добавляет новые домены в базу и в файл. Уже известные пропускает.
     *
     * @param iterable<string> $domains
     * @return int сколько новых добавлено
     */
    public function add(iterable $domains): int
    {
        $new = [];
        foreach ($domains as $domain) {
            $domain = mb_strtolower(trim((string) $domain));
            if ($domain === '' || isset($this->set[$domain])) {
                continue;
            }
            $this->set[$domain] = true;
            $new[] = $domain;
        }
        if ($new !== []) {
            $dir = dirname($this->file);
            if (!is_dir($dir)) {
                @mkdir($dir, 0777, true);
            }
            @file_put_contents($this->file, implode(PHP_EOL, $new) . PHP_EOL, FILE_APPEND | LOCK_EX);
        }

        return count($new);
    }

    public function clear(): void
    {
        $this->set = [];
        @file_put_contents($this->file, '');
    }
}
