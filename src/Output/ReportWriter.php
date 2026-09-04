<?php

declare(strict_types=1);

namespace YandexSites\Output;

use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;

/**
 * Запись результатов в CSV, JSON и текстовый список доменов.
 */
final class ReportWriter
{
    public function __construct(
        private string $delimiter = ';',
        private bool $bom = true,
    ) {
    }

    /**
     * @param list<Site> $sites
     */
    public function writeCsv(array $sites, string $path): void
    {
        $fh = $this->open($path);
        $this->row($fh, [
            'host', 'host_unicode', 'domain', 'url', 'title', 'best_position', 'best_query',
            'queries_count', 'hits', 'queries', 'check_status', 'check_final_url', 'check_title', 'check_result',
            'page_file', 'page_final_url', 'page_title', 'page_variants', 'pages_ok', 'pages_total', 'page_error',
        ]);
        foreach ($sites as $site) {
            $data = $site->toArray();
            $queries = [];
            foreach ($site->queries as $query => $position) {
                $queries[] = $query . ' (' . $position . ')';
            }
            $check = $site->check;
            $visit = $site->firstVisit();
            $this->row($fh, [
                $data['host'],
                $data['host_unicode'],
                $data['domain'],
                $data['url'],
                $data['title'],
                $data['best_position'],
                $data['best_query'],
                $data['queries_count'],
                $data['hits'],
                implode(' | ', $queries),
                $check['status'] ?? '',
                $check['final_url'] ?? '',
                $check['title'] ?? '',
                $check === [] ? '' : (($check['ok'] ?? false) ? 'ok' : ($check['reason'] ?? '') . ($check['error'] ?? '' ? ': ' . $check['error'] : '')),
                $visit['html_file'] ?? '',
                $visit['final_url'] ?? '',
                $visit['title'] ?? '',
                $site->visits === [] ? '' : sprintf('%d/%d', $site->variantCount(), count($site->visits)),
                $site->visits === [] ? '' : $site->visitSummary()['ok'],
                $site->visits === [] ? '' : $site->visitSummary()['total'],
                $site->visits === [] ? '' : $site->visitSummary()['error'],
            ]);
        }
        fclose($fh);
    }

    /**
     * @param list<Site> $sites
     * @param array<string, mixed> $meta
     */
    public function writeJson(array $sites, string $path, array $meta = []): void
    {
        $payload = [
            'generated_at' => date(DATE_ATOM),
            'meta' => $meta,
            'sites' => array_map(static fn (Site $site): array => $site->toArray(), $sites),
        ];
        $json = json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
        $this->put($path, $json . PHP_EOL);
    }

    /**
     * @param list<Site> $sites
     */
    public function writeDomains(array $sites, string $path): void
    {
        $lines = array_map(static fn (Site $site): string => $site->host, $sites);
        $this->put($path, $lines === [] ? '' : implode(PHP_EOL, $lines) . PHP_EOL);
    }

    /**
     * Все результаты выдачи с пометкой, прошли ли они фильтры.
     *
     * @param list<array{result: SearchResult, reason: string|null}> $rows
     */
    public function writeRawCsv(array $rows, string $path): void
    {
        $fh = $this->open($path);
        $this->row($fh, ['query', 'page', 'position', 'host', 'url', 'title', 'snippet', 'result']);
        foreach ($rows as $row) {
            $r = $row['result'];
            $this->row($fh, [
                $r->query,
                $r->page + 1,
                $r->position,
                $r->host,
                $r->url,
                $r->title,
                mb_substr($r->text(), 0, 500),
                $row['reason'] ?? 'selected',
            ]);
        }
        fclose($fh);
    }

    /**
     * @return resource
     */
    private function open(string $path)
    {
        $this->ensureDir($path);
        $fh = fopen($path, 'w');
        if ($fh === false) {
            throw new \RuntimeException("Не удалось открыть файл для записи: $path");
        }
        if ($this->bom) {
            fwrite($fh, "\xEF\xBB\xBF");
        }

        return $fh;
    }

    /**
     * @param resource $fh
     * @param list<mixed> $fields
     */
    private function row($fh, array $fields): void
    {
        fputcsv($fh, array_map(static fn ($v): string => (string) ($v ?? ''), $fields), $this->delimiter, '"', '');
    }

    private function put(string $path, string $content): void
    {
        $this->ensureDir($path);
        if (file_put_contents($path, $content) === false) {
            throw new \RuntimeException("Не удалось записать файл: $path");
        }
    }

    private function ensureDir(string $path): void
    {
        $dir = dirname($path);
        if (!is_dir($dir) && !@mkdir($dir, 0777, true) && !is_dir($dir)) {
            throw new \RuntimeException("Не удалось создать каталог: $dir");
        }
    }
}
