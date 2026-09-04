<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Check\SiteChecker;
use YandexSites\Model\Site;
use YandexSites\Support\Logger;

/**
 * SiteChecker, направляющий все хосты на фейковый сервер через CURLOPT_RESOLVE.
 */
final class LocalSiteChecker extends SiteChecker
{
    public const HOSTS = ['okna-moskva.ru', 'dead-site.ru', 'redirect-site.ru', 'other-domain.ru', 'phone-site.ru', 'cp1251-site.ru', 'parked-site.ru', 'unresolvable.invalid'];

    public function __construct(array $cfg, Logger $log, private int $port)
    {
        parent::__construct($cfg, $log);
    }

    protected function targetUrl(Site $site, string $scheme): string
    {
        return 'http://' . $site->host . ':' . $this->port . '/';
    }

    protected function curlOptions(string $url): array
    {
        $resolve = [];
        foreach (self::HOSTS as $host) {
            if ($host === 'unresolvable.invalid') {
                continue;
            }
            $resolve[] = $host . ':' . $this->port . ':127.0.0.1';
        }

        return [CURLOPT_RESOLVE => $resolve];
    }
}
