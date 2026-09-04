<?php

declare(strict_types=1);

namespace YandexSites;

use YandexSites\Filter\DefaultExclusions;

/**
 * Конфигурация: значения по умолчанию, файл config.php, переменные окружения
 * и переопределения из командной строки.
 */
final class Config
{
    public const SEARCH_TYPES = ['ru', 'tr', 'com', 'kk', 'be', 'uz'];
    public const LOCALIZATIONS = ['ru', 'uk', 'be', 'kk', 'tr', 'en'];
    public const FAMILY_MODES = ['none', 'moderate', 'strict'];
    public const PERIODS = ['all', 'day', '2weeks', 'month'];

    /** @var array<string, mixed> */
    private array $data;

    /**
     * @param array<string, mixed> $data
     */
    public function __construct(array $data = [])
    {
        $this->data = self::merge(self::defaults(), $data);
    }

    /**
     * @return array<string, mixed>
     */
    public static function defaults(): array
    {
        return [
            'api' => [
                'version' => 'rest',
                'folder_id' => (string) (getenv('YANDEX_FOLDER_ID') ?: ''),
                'api_key' => (string) (getenv('YANDEX_API_KEY') ?: ''),
                'iam_token' => (string) (getenv('YANDEX_IAM_TOKEN') ?: ''),
                'rest_endpoint' => (string) (getenv('YANDEX_REST_ENDPOINT') ?: 'https://searchapi.api.cloud.yandex.net/v2/web/search'),
                'xml_endpoint' => (string) (getenv('YANDEX_XML_ENDPOINT') ?: 'https://yandex.ru/search/xml'),
                'timeout' => 30,
                'delay_ms' => 250,
                'retries' => 3,
                'retry_delay_ms' => 1000,
                'user_agent' => 'Mozilla/5.0 (compatible; yandex-sites/1.0)',
            ],
            'search' => [
                'region' => 213,
                'search_type' => 'ru',
                'l10n' => 'ru',
                'pages' => 1,
                'groups_on_page' => 50,
                'docs_in_group' => 1,
                'group_mode' => 'deep',
                'max_passages' => 2,
                'family_mode' => 'moderate',
                'fix_typo' => true,
                'sort' => 'relevance',
                'period' => 'all',
            ],
            'cache' => [
                'enabled' => true,
                'dir' => dirname(__DIR__) . '/cache',
                'ttl' => 7 * 86400,
            ],
            'filters' => [
                'max_position' => null,
                'unique_by' => 'host',
                'strip_www' => true,
                'allowed_tlds' => [],
                'include_domains' => [],
                'exclude_domains' => DefaultExclusions::LIST,
                'url_must_match' => [],
                'url_must_not_match' => [],
                'title_any' => [],
                'title_all' => [],
                'title_none' => [],
                'snippet_any' => [],
                'snippet_none' => [],
                'min_queries' => 1,
                'min_hits' => 1,
            ],
            'site_check' => [
                'enabled' => false,
                'target' => 'root',
                'concurrency' => 5,
                'timeout' => 15,
                'verify_ssl' => true,
                'max_bytes' => 512 * 1024,
                'user_agent' => 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36',
                'require_status' => [200],
                'reject_offsite_redirect' => false,
                'page_must_match' => [],
                'page_must_not_match' => [],
            ],
            'output' => [
                'dir' => 'out',
                'csv' => 'sites.csv',
                'json' => 'sites.json',
                'domains' => 'domains.txt',
                'raw_csv' => 'results.csv',
                'write_raw' => false,
                'csv_delimiter' => ';',
                'csv_bom' => true,
            ],
        ];
    }

    public static function fromFile(?string $path): self
    {
        if ($path === null) {
            return new self();
        }
        if (!is_file($path)) {
            throw new \RuntimeException("Файл конфигурации не найден: $path");
        }
        $data = require $path;
        if (!is_array($data)) {
            throw new \RuntimeException("Файл конфигурации должен возвращать массив: $path");
        }

        return new self($data);
    }

    /**
     * Загружает переменные из .env-файла (KEY=VALUE), не перекрывая уже заданные.
     */
    public static function loadDotEnv(string $path): void
    {
        if (!is_file($path) || !is_readable($path)) {
            return;
        }
        foreach (file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [] as $line) {
            $line = trim($line);
            if ($line === '' || str_starts_with($line, '#') || !str_contains($line, '=')) {
                continue;
            }
            [$key, $value] = explode('=', $line, 2);
            $key = trim($key);
            if (str_starts_with($key, 'export ')) {
                $key = trim(substr($key, 7));
            }
            $value = trim($value);
            if ((str_starts_with($value, '"') && str_ends_with($value, '"')) || (str_starts_with($value, "'") && str_ends_with($value, "'"))) {
                $value = substr($value, 1, -1);
            }
            if ($key === '' || getenv($key) !== false) {
                continue;
            }
            putenv("$key=$value");
            $_ENV[$key] = $value;
        }
    }

    /**
     * Значение по пути вида `api.folder_id`.
     */
    public function get(string $path, mixed $default = null): mixed
    {
        $node = $this->data;
        foreach (explode('.', $path) as $segment) {
            if (!is_array($node) || !array_key_exists($segment, $node)) {
                return $default;
            }
            $node = $node[$segment];
        }

        return $node;
    }

    public function set(string $path, mixed $value): void
    {
        $node = &$this->data;
        $segments = explode('.', $path);
        $last = array_pop($segments);
        foreach ($segments as $segment) {
            if (!isset($node[$segment]) || !is_array($node[$segment])) {
                $node[$segment] = [];
            }
            $node = &$node[$segment];
        }
        $node[$last] = $value;
    }

    /**
     * @param array<string, mixed> $overrides ключи вида `search.pages`
     */
    public function withOverrides(array $overrides): self
    {
        $clone = clone $this;
        foreach ($overrides as $path => $value) {
            $clone->set($path, $value);
        }

        return $clone;
    }

    /**
     * @return array<string, mixed>
     */
    public function all(): array
    {
        return $this->data;
    }

    /**
     * Проверяет конфигурацию и возвращает список ошибок (пустой — всё в порядке).
     *
     * @return list<string>
     */
    public function validate(bool $requireCredentials = true): array
    {
        $errors = [];
        $g = fn (string $path) => $this->get($path);

        if (!in_array($g('api.version'), ['rest', 'xml'], true)) {
            $errors[] = "api.version: допустимы 'rest' (API v2) или 'xml' (API v1), получено: " . var_export($g('api.version'), true);
        }
        if ($requireCredentials) {
            if ((string) $g('api.folder_id') === '') {
                $errors[] = 'api.folder_id: не задан идентификатор каталога Yandex Cloud (переменная YANDEX_FOLDER_ID)';
            }
            if ((string) $g('api.api_key') === '' && (string) $g('api.iam_token') === '') {
                $errors[] = 'api.api_key: не задан API-ключ (переменная YANDEX_API_KEY) или IAM-токен (YANDEX_IAM_TOKEN)';
            }
        }
        foreach (['api.timeout' => [1, 600], 'api.retries' => [0, 20], 'api.delay_ms' => [0, 600000], 'api.retry_delay_ms' => [0, 600000]] as $path => [$min, $max]) {
            $v = $g($path);
            if (!is_numeric($v) || $v < $min || $v > $max) {
                $errors[] = "$path: ожидается число от $min до $max";
            }
        }

        $ranges = [
            'search.pages' => [1, 100],
            'search.groups_on_page' => [1, 100],
            'search.docs_in_group' => [1, 3],
            'search.max_passages' => [1, 5],
        ];
        foreach ($ranges as $path => [$min, $max]) {
            $v = $g($path);
            if (!is_numeric($v) || (int) $v != $v || $v < $min || $v > $max) {
                $errors[] = "$path: ожидается целое число от $min до $max, получено: " . var_export($v, true);
            }
        }
        if ((string) $g('search.region') === '') {
            $errors[] = 'search.region: не задан идентификатор региона (например, 213 — Москва)';
        }
        $enums = [
            'search.search_type' => self::SEARCH_TYPES,
            'search.l10n' => self::LOCALIZATIONS,
            'search.family_mode' => self::FAMILY_MODES,
            'search.period' => self::PERIODS,
            'search.sort' => ['relevance', 'time'],
            'search.group_mode' => ['deep', 'flat'],
            'filters.unique_by' => ['host', 'domain'],
            'site_check.target' => ['root', 'found'],
        ];
        foreach ($enums as $path => $allowed) {
            if (!in_array($g($path), $allowed, true)) {
                $errors[] = "$path: допустимые значения: " . implode(', ', $allowed) . ', получено: ' . var_export($g($path), true);
            }
        }
        foreach (['filters.min_queries', 'filters.min_hits', 'site_check.concurrency', 'site_check.timeout', 'site_check.max_bytes', 'cache.ttl'] as $path) {
            $v = $g($path);
            if (!is_numeric($v) || $v < 0) {
                $errors[] = "$path: ожидается неотрицательное число";
            }
        }
        foreach (['filters.allowed_tlds', 'filters.include_domains', 'filters.exclude_domains', 'filters.url_must_match', 'filters.url_must_not_match', 'filters.title_any', 'filters.title_all', 'filters.title_none', 'filters.snippet_any', 'filters.snippet_none', 'site_check.require_status', 'site_check.page_must_match', 'site_check.page_must_not_match'] as $path) {
            if (!is_array($g($path))) {
                $errors[] = "$path: ожидается массив";
            }
        }
        if ((string) $g('output.dir') === '') {
            $errors[] = 'output.dir: не задан каталог для результатов';
        }

        return $errors;
    }

    /**
     * Рекурсивное слияние: ассоциативные массивы объединяются, списки заменяются целиком.
     *
     * @param array<string, mixed> $base
     * @param array<string, mixed> $override
     * @return array<string, mixed>
     */
    private static function merge(array $base, array $override): array
    {
        foreach ($override as $key => $value) {
            if (is_array($value) && isset($base[$key]) && is_array($base[$key]) && self::isAssoc($base[$key]) && self::isAssoc($value)) {
                $base[$key] = self::merge($base[$key], $value);
            } else {
                $base[$key] = $value;
            }
        }

        return $base;
    }

    /**
     * @param array<mixed> $array
     */
    private static function isAssoc(array $array): bool
    {
        return $array !== [] && array_keys($array) !== range(0, count($array) - 1);
    }
}
