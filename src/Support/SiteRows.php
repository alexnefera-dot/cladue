<?php

declare(strict_types=1);

namespace YandexSites\Support;

use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;
use YandexSites\Visit\PageVisitor;
use YandexSites\Visit\SiteTemplate;

/**
 * Список сайтов для панели: чтение sites.json в объекты Site и строки таблицы (превью). Общий для
 * фонового задания (bin/run-job.php) и панели (bin/panel.php): панель достаёт прошлый сбор из sites.json,
 * когда в status.json списка нет — после обновления страницы, перезапуска панели или ошибки.
 */
final class SiteRows
{
    /**
     * Сколько сайтов попадает в таблицу панели (status.json / ответ /api/state). Раньше было 1000: сайты сверх
     * лимита в таблице не показывались, но выгрузка брала их из sites.json — «качаются сайты, которых не видно».
     * Теперь выгрузка идёт строго по списку из таблицы (only), а лимит — лишь защита от гигантского статуса.
     */
    public const ROW_LIMIT = 5000;

    /** Сколько байт сохранённой страницы читать при досчёте типа вёрстки (страницы и так обрезаны visit.max_bytes). */
    private const MAX_HTML_BYTES = 2 * 1024 * 1024;
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
     * Сколько сайтов с каким числом успешно открытых страниц: [1 => 12, 7 => 40, 9 => 5, 'own' => 3].
     * Наши шаблоны считаются отдельно (ключ 'own'), сайты без единого визита не считаются.
     *
     * @param array<int|string, Site> $sites
     * @return array<int|string, int>
     */
    public static function pageHistogram(array $sites): array
    {
        $hist = [];
        $own = 0;
        foreach ($sites as $site) {
            if ($site->own) {
                $own++;
                continue;
            }
            $s = $site->visitSummary();
            if ($s['total'] > 0) {
                $hist[$s['ok']] = ($hist[$s['ok']] ?? 0) + 1;
            }
        }
        ksort($hist);
        if ($own > 0) {
            $hist['own'] = $own;
        }

        return $hist;
    }

    /** Гистограмма текстом: «1 стр. — 12, 7 стр. — 40, наши — 3»; '' — если считать нечего. */
    public static function histogramText(array $hist): string
    {
        $parts = [];
        foreach ($hist as $n => $count) {
            $parts[] = $n === 'own' ? 'наши — ' . $count : sprintf('%d стр. — %d', (int) $n, $count);
        }

        return implode(', ', $parts);
    }

    /**
     * Строки таблицы результатов: host, домен, число страниц (ok/всего), причина ошибки, признак «наш»,
     * есть ли что докачивать (retryable), число страниц с 404, тип вёрстки (template/template_label),
     * ссылки на html/скриншот (относительно runDir).
     *
     * @param array<int|string, Site> $sites
     * @return list<array<string, mixed>>
     */
    public static function preview(array $sites, string $runDir = '', int $limit = self::ROW_LIMIT): array
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
            $visit = null;
            foreach ($site->visits as $candidate) {
                $candidate = (array) $candidate;
                if (($candidate['ok'] ?? false) && is_file((string) ($candidate['html_file'] ?? ''))) {
                    $visit = $candidate; // ссылка «html» — на файл, который реально есть на диске
                    break;
                }
            }
            $visit ??= $site->firstVisit() ?? ($site->visits[0] ?? null);
            // Есть ли у сайта страницы, которые докачка реально может добрать (таймаут/блок/404 с языковым
            // префиксом) — по этому флагу панель считает кнопку «Докачать с ошибками» и не предлагает докачку впустую.
            $retryable = false;
            $notFound = 0; // страниц с 404/410 — для кнопки «Убрать с 404 > N» в панели
            $missing = 0; // успешных визитов, чей файл пропал с диска — таблица честно это показывает, докачка перекачивает
            if (!$own) {
                foreach ($site->visits as $v) {
                    $v = (array) $v;
                    $file = (string) ($v['html_file'] ?? '');
                    if (($v['ok'] ?? false) && $file !== '' && !is_file($file)) {
                        $missing++;
                        $retryable = true;
                    }
                    if (!$retryable && PageVisitor::isRetryableVisit($v)) {
                        $retryable = true;
                    }
                    $e = mb_strtolower((string) ($v['error'] ?? ''));
                    if (!($v['ok'] ?? false) && (str_contains($e, 'не найдена') || str_contains($e, 'http 404') || str_contains($e, 'http 410'))) {
                        $notFound++;
                    }
                }
            }
            // Тип вёрстки по открытым страницам (превью главной после сбора): pages7 / pages12 / other; '' — страниц нет.
            $template = $own ? '' : SiteTemplate::ofVisits($site->visits);
            $rows[] = [
                'retryable' => $retryable,
                'template' => $template,
                'template_label' => $template !== '' ? SiteTemplate::label($template) : '',
                'pages_404' => $notFound,
                'pages_missing' => $missing,
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

    /**
     * Дописывает тип вёрстки визитам прошлого сбора, сделанного версией без этого поля: читает сохранённый
     * HTML страницы и определяет семейство (SiteTemplate). Возвращает число дописанных визитов; чтобы файлы не
     * читались при каждом опросе панели, результат сохраняют в sites.json (saveTemplates()).
     *
     * @param array<int|string, Site> $sites
     */
    public static function backfillTemplates(array $sites): int
    {
        $n = 0;
        foreach ($sites as $site) {
            if ($site->own) {
                continue;
            }
            foreach ($site->visits as &$v) {
                $v = (array) $v;
                if (!($v['ok'] ?? false) || (string) ($v['template'] ?? '') !== '') {
                    continue;
                }
                $file = (string) ($v['html_file'] ?? '');
                if ($file === '' || !is_file($file)) {
                    continue;
                }
                $v['template'] = SiteTemplate::guess((string) file_get_contents($file, false, null, 0, self::MAX_HTML_BYTES));
                $n++;
            }
            unset($v);
        }

        return $n;
    }

    /**
     * Переписывает поле template у визитов в sites.json (остальное содержимое файла сохраняется как есть).
     *
     * @param array<int|string, Site> $sites
     */
    public static function saveTemplates(string $file, array $sites): bool
    {
        $data = is_file($file) ? json_decode((string) file_get_contents($file), true) : null;
        if (!is_array($data) || !is_array($data['sites'] ?? null)) {
            return false;
        }
        $byHost = [];
        foreach ($sites as $site) {
            $byHost[$site->host] = $site;
        }
        foreach ($data['sites'] as &$row) {
            $site = $byHost[(string) ($row['host'] ?? '')] ?? null;
            if ($site === null || !is_array($row['visits'] ?? null)) {
                continue;
            }
            $visits = array_values($row['visits']); // load() тоже нумерует визиты подряд — индексы совпадают
            foreach ($visits as $i => &$visit) {
                $template = (string) ($site->visits[$i]['template'] ?? '');
                if ($template !== '' && is_array($visit)) {
                    $visit['template'] = $template;
                }
            }
            unset($visit);
            $row['visits'] = $visits;
        }
        unset($row);
        $tmp = $file . '.tmp';
        file_put_contents($tmp, json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) . PHP_EOL);

        return @rename($tmp, $file);
    }
}
