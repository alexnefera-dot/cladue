<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Support\QueryQueue;

final class QueryQueueTest
{
    public function testQueueKeepsPositionAndReportsRemaining(): void
    {
        $file = sys_get_temp_dir() . '/yandex-sites-queue-' . uniqid() . '/queue.json';
        $queue = QueryQueue::start($file, ['q1', 'q2', 'q3', 'q4']);
        Assert::same(['total' => 4, 'done' => 0, 'left' => 4], QueryQueue::summary($queue));
        Assert::same(['q1', 'q2', 'q3', 'q4'], QueryQueue::remaining($queue));

        // Сбор остановлен после второго запроса: продолжаем с третьего.
        $queue['done'] = 2;
        QueryQueue::save($file, $queue);
        $loaded = QueryQueue::load($file);
        Assert::same(['q1', 'q2', 'q3', 'q4'], $loaded['queries']);
        Assert::same(2, $loaded['done']);
        Assert::same(['q3', 'q4'], QueryQueue::remaining($loaded));
        Assert::same(['total' => 4, 'done' => 2, 'left' => 2], QueryQueue::summary($loaded));

        // Битый/отсутствующий файл — пустая очередь, а не ошибка; done не больше числа запросов.
        Assert::same(['queries' => [], 'done' => 0], QueryQueue::load($file . '.нет'));
        file_put_contents($file, '{"queries":["a","b"],"done":99}');
        Assert::same(['queries' => ['a', 'b'], 'done' => 2], QueryQueue::load($file));
    }

    public function testSyncFollowsEditedQueryListWithoutLosingPosition(): void
    {
        // Пока обрабатывалась первая часть, список в панели правили: убрали дубль из остатка и дописали
        // новый запрос. Пройденное начало не трогаем, остаток приводим к текущему списку.
        $queue = ['queries' => ['q1', 'q2', 'q3', 'q4'], 'done' => 2];
        $synced = QueryQueue::sync($queue, ['q1', 'q2', 'q4', 'q5']);
        Assert::same(['q1', 'q2', 'q4', 'q5'], $synced['queries'], 'q3 убран из остатка, q5 дописан');
        Assert::same(2, $synced['done'], 'позиция сохранена');
        Assert::same(['q4', 'q5'], QueryQueue::remaining($synced));

        // Пройденные запросы, убранные из списка, остаются в очереди (их уже обработали).
        $synced = QueryQueue::sync($queue, ['q3', 'q4']);
        Assert::same(['q1', 'q2', 'q3', 'q4'], $synced['queries']);
        Assert::same(['q3', 'q4'], QueryQueue::remaining($synced));

        // Пустой список ничего не меняет; пустые строки игнорируются.
        Assert::same($queue, QueryQueue::sync($queue, []));
        Assert::same($queue, QueryQueue::sync($queue, ['  ', '']));
    }
}
