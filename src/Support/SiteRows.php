<?php

declare(strict_types=1);

namespace YandexSites\Support;

use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;
use YandexSites\Visit\PageVisitor;

/**
 * Список сайтов для панели: чтение sites.json в объекты Site и строки таблицы (превью). Общий для
 * фонового задания (bin/run-job.php) и панели (bin/panel.php): панель достаёт прошлый сбор из sites.json,
 * когда в status.json списка нет — после обновления страницы, перезапуска панели или ошибки.
 */
final class SiteRows
{
    /**
     * Сайты из sites.json (host → Site) с прошлыми визитами и признаком «наш».
     *
     * @return array<string, Site>
     */
    public static function load(string $file): array
    {
        $data = is_file($file) ? json_decode((string) file_get_contents($file), true) : null;
        $sites = [];
        foreach (is_array($data) && isset($data['sites']) ? $data['sites'] : [] as $row) {
            $host = (string) ($row['host'] ?? '');
            if ($host === '') {
                continue;
            }
            $site = new Site($host, $host, (string) ($row['domain'] ?? $host));
            $url = (string) ($row['url'] ?? '');
            $query = (string) ($row['best_query'] ?? '');
            $position = isset($row['best_position']) ? (int) $row['best_position'] : 1;
            $site->add(new SearchResult($query, 0, max(1, $position), $url !== '' ? $url : 'https://' . $host . '/', $host, (string) ($row['title'] ?? '')));
            // Восстанавливаем прошлые визиты и признак «наш» — при докачке только части сайтов остальные
            // сохраняют свои результаты, и итоговый sites.json не теряет уже выгруженные страницы.
            if (isset($row['visits']) && is_array($row['visits'])) {
                $site->visits = array_values($row['visits']);
            }
            $site->own = (bool) ($row['own'] ?? false);
            $sites[$host] = $site;
        }

        return $sites;
    }

    /**
     * Строки таблицы результатов: host, домен, число страниц (ok/всего), причина ошибки, признак «наш»,
     * есть ли что докачивать (retryable), число страниц с 404, ссылки на html/скриншот (относительно runDir).
     *
     * @param array<int|string, Site> $sites
     * @return list<array<string, mixed>>
     */
    public static function preview(array $sites, string $runDir = '', int $limit = 1000): array
    {
        $rel = static function (string $abs) use ($runDir): string {
            $prefix = rtrim($runDir, '/\\') . '/';

            return $runDir !== '' && str_starts_with($abs, $prefix) ? substr($abs, strlen($prefix)) : $abs;
        };
        $rows = [];
        foreach (array_slice(array_values($sites), 0, $limit) as $site) {
            $data = $site->toArray();
            $summary = $site->visitSummary();
            $own = (bool) ($data['own'] ?? false);
            // Для показа берём первый успешный визит, а если такого нет (ошибка/наш) — самый первый визит:
            // так остаётся ссылка на скриншот (у «наших» он сохранён) и видна причина ошибки.
            $visit = $site->firstVisit() ?? ($site->visits[0] ?? null);
            // Есть ли у сайта страницы, которые докачка реально может добрать (таймаут/блок/404 с языковым
            // префиксом) — по этому флагу панель считает кнопку «Докачать с ошибками» и не предлагает докачку впустую.
            $retryable = false;
            $notFound = 0; // страниц с 404/410 — для кнопки «Убрать с 404 > N» в панели
            if (!$own) {
                foreach ($site->visits as $v) {
                    $v = (array) $v;
                    if (!$retryable && PageVisitor::isRetryableVisit($v)) {
                        $retryable = true;
                    }
                    $e = mb_strtolower((string) ($v['error'] ?? ''));
                    if (!($v['ok'] ?? false) && (str_contains($e, 'не найдена') || str_contains($e, 'http 404') || str_contains($e, 'http 410'))) {
                        $notFound++;
                    }
                }
            }
            $rows[] = [
                'retryable' => $retryable,
                'pages_404' => $notFound,
                'host' => $data['host'],
                'domain' => $data['domain'],
                'url' => $data['url'],
                'title' => $data['title'],
                'queries_count' => $data['queries_count'],
                'best_position' => $data['best_position'],
                'variants' => $data['variants'],
                'own' => $own,
                'pages_ok' => $own ? null : ($summary['total'] > 0 ? $summary['ok'] : null),
                'pages_total' => $own ? null : ($summary['total'] > 0 ? $summary['total'] : null),
                'page_error' => $own ? 'исключён как наш' : $summary['error'],
                'html' => !$own && $visit !== null && ($visit['html_file'] ?? '') !== '' ? $rel((string) $visit['html_file']) : '',
                'screenshot' => $visit !== null && ($visit['screenshot_file'] ?? '') !== '' ? $rel((string) $visit['screenshot_file']) : '',
            ];
        }

        return $rows;
    }
}
