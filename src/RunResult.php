<?php

declare(strict_types=1);

namespace YandexSites;

use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;

/**
 * Итог прогона: отобранные сайты, все результаты выдачи и статистика.
 */
final class RunResult
{
    /** @var list<Site> отобранные сайты (отсортированы по релевантности) */
    public array $sites = [];

    /** @var list<array{result: SearchResult, reason: string|null}> */
    public array $raw = [];

    /** @var array<string, mixed> */
    public array $stats = [
        'queries' => 0,
        'queries_done' => 0,
        'requests' => 0,
        'results' => 0,
        'sites_total' => 0,
        'sites_selected' => 0,
        'rejected' => [],
    ];

    /** @var list<string> */
    public array $errors = [];

    /**
     * Хосты, отклонённые как «уже в базе» (reason seen_before). Нужны статистике сборов: по ним
     * считаются ПОВТОРЫ ДОРОВ — сколько из повторившихся доменов сидело на поддоменах. В stats их
     * не кладём: статус и sites.json не должны раздуваться списком на тысячи строк.
     *
     * @var list<string>
     */
    public array $seenBefore = [];

    /** Прогон прерван из-за фатальной ошибки API. */
    public bool $aborted = false;

    /** Сбор остановлен кнопкой «Остановить»: часть запросов не обработана, результаты сохраняются. */
    public bool $stopped = false;

    /**
     * Сколько запросов списка обработано (включая завершившиеся ошибкой) — позиция для продолжения
     * сбора: очередь запросов (Support\QueryQueue) запускает остаток именно с неё.
     */
    public int $processed = 0;

    public function reject(string $reason, int $count = 1): void
    {
        $this->stats['rejected'][$reason] = ($this->stats['rejected'][$reason] ?? 0) + $count;
    }
}
