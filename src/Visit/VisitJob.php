<?php

declare(strict_types=1);

namespace YandexSites\Visit;

/**
 * Одно посещение страницы сайта: адрес, «личность» посетителя и куда сохранять результат.
 */
final class VisitJob
{
    public function __construct(
        public readonly string $id,
        public readonly string $siteKey,
        public readonly int $variant,
        public readonly string $url,
        public readonly string $referer,
        public readonly string $userAgent,
        public readonly ?string $proxyUrl,
        public readonly string $proxyLabel,
        public readonly string $htmlFile,
        public readonly ?string $screenshotFile,
    ) {
    }
}
