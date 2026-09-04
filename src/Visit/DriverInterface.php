<?php

declare(strict_types=1);

namespace YandexSites\Visit;

/**
 * Способ открыть страницу и сохранить её HTML: headless-браузер (Playwright) или curl.
 */
interface DriverInterface
{
    public function name(): string;

    /**
     * @param list<VisitJob> $jobs
     * @param array<string, mixed> $options timeout, wait_ms, concurrency, delay_ms, verify_ssl, resolve, full_page, max_bytes, browser_path
     * @param callable(VisitJob, array<string, mixed>): void|null $onResult вызывается по мере готовности
     * @return array<string, array{ok: bool, error: string, status: int|null, final_url: string, title: string}> по id задания
     */
    public function visit(array $jobs, array $options, ?callable $onResult = null): array;
}
