<?php

declare(strict_types=1);

namespace YandexSites\Support;

/**
 * Простой логгер в поток (по умолчанию STDERR) с тремя уровнями подробности.
 */
final class Logger
{
    public const QUIET = 0;
    public const NORMAL = 1;
    public const VERBOSE = 2;

    /** @var resource */
    private $stream;

    /**
     * @param resource|null $stream
     */
    public function __construct(private int $level = self::NORMAL, $stream = null)
    {
        $this->stream = $stream ?? (defined('STDERR') ? STDERR : fopen('php://stderr', 'w'));
    }

    public function level(): int
    {
        return $this->level;
    }

    public function info(string $message): void
    {
        $this->write(self::NORMAL, $message);
    }

    public function debug(string $message): void
    {
        $this->write(self::VERBOSE, $message);
    }

    public function warn(string $message): void
    {
        $this->write(self::QUIET, 'ВНИМАНИЕ: ' . $message);
    }

    public function error(string $message): void
    {
        $this->write(self::QUIET, 'ОШИБКА: ' . $message);
    }

    private function write(int $minLevel, string $message): void
    {
        if ($this->level >= $minLevel) {
            fwrite($this->stream, $message . PHP_EOL);
        }
    }
}
