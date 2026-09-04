<?php

declare(strict_types=1);

namespace YandexSites\Check;

/**
 * Результат HTTP-проверки сайта.
 */
final class CheckResult
{
    public function __construct(
        public readonly bool $ok,
        public readonly string $reason,
        public readonly ?int $status,
        public readonly string $finalUrl,
        public readonly string $title = '',
        public readonly string $error = '',
    ) {
    }

    /**
     * @return array<string, mixed>
     */
    public function toArray(): array
    {
        return [
            'ok' => $this->ok,
            'reason' => $this->reason,
            'status' => $this->status,
            'final_url' => $this->finalUrl,
            'title' => $this->title,
            'error' => $this->error,
        ];
    }
}
