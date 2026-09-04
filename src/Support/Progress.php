<?php

declare(strict_types=1);

namespace YandexSites\Support;

/**
 * Пишет текущее состояние прогона в JSON-файл, чтобы веб-интерфейс мог показывать прогресс.
 * Записи ограничены по частоте (не чаще ~4 раз в секунду), важные переходы пишутся принудительно.
 */
final class Progress
{
    /** @var array<string, mixed> */
    private array $state;
    private float $lastWrite = 0.0;

    /**
     * @param array<string, mixed> $initial
     */
    public function __construct(private string $file, array $initial = [])
    {
        $this->state = $initial;
        $this->state['updated_at'] = date(DATE_ATOM);
        $dir = dirname($file);
        if (!is_dir($dir)) {
            @mkdir($dir, 0777, true);
        }
        $this->flush(true);
    }

    /**
     * @param array<string, mixed> $patch
     */
    public function update(array $patch, bool $force = false): void
    {
        foreach ($patch as $key => $value) {
            $this->state[$key] = $value;
        }
        $this->state['updated_at'] = date(DATE_ATOM);
        $this->flush($force);
    }

    public function set(string $key, mixed $value, bool $force = false): void
    {
        $this->update([$key => $value], $force);
    }

    /**
     * @return array<string, mixed>
     */
    public function snapshot(): array
    {
        return $this->state;
    }

    private function flush(bool $force): void
    {
        $now = microtime(true);
        if (!$force && $now - $this->lastWrite < 0.25) {
            return;
        }
        $this->lastWrite = $now;
        $json = json_encode($this->state, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        if ($json !== false) {
            @file_put_contents($this->file, $json, LOCK_EX);
        }
    }
}
