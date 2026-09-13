<?php

declare(strict_types=1);

namespace YandexSites\Support;

/**
 * Очередь запросов сбора: большой список (3000 ключей) обрабатывается ЧАСТЯМИ. Сбор идёт, пока
 * пользователь не нажмёт «Остановить»; очередь помнит, сколько запросов уже обработано, и кнопка
 * «Продолжить сбор» запускает оставшиеся. Файл — runs/current/queue.json.
 */
final class QueryQueue
{
    public const FILE = 'queue.json';

    /**
     * Новая очередь: весь список, ничего не обработано.
     *
     * @param list<string> $queries
     * @return array{queries: list<string>, done: int}
     */
    public static function start(string $file, array $queries): array
    {
        $queue = ['queries' => array_values($queries), 'done' => 0];
        self::save($file, $queue);

        return $queue;
    }

    /**
     * @return array{queries: list<string>, done: int}
     */
    public static function load(string $file): array
    {
        $data = is_file($file) ? json_decode((string) file_get_contents($file), true) : null;
        $queries = [];
        foreach (is_array($data) ? (array) ($data['queries'] ?? []) : [] as $q) {
            $q = trim((string) $q);
            if ($q !== '') {
                $queries[] = $q;
            }
        }
        $done = is_array($data) ? max(0, (int) ($data['done'] ?? 0)) : 0;

        return ['queries' => $queries, 'done' => min($done, count($queries))];
    }

    /**
     * @param array{queries: list<string>, done: int} $queue
     */
    public static function save(string $file, array $queue): void
    {
        @mkdir(dirname($file), 0777, true);
        $data = [
            'queries' => array_values($queue['queries']),
            'done' => min(max(0, (int) $queue['done']), count($queue['queries'])),
            'updated_at' => date(DATE_ATOM),
        ];
        $tmp = $file . '.tmp';
        file_put_contents($tmp, json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
        @rename($tmp, $file);
    }

    /**
     * Необработанный хвост очереди.
     *
     * @param array{queries: list<string>, done: int} $queue
     * @return list<string>
     */
    public static function remaining(array $queue): array
    {
        return array_values(array_slice($queue['queries'], $queue['done']));
    }

    /**
     * Сводка для панели: сколько всего, обработано и осталось.
     *
     * @param array{queries: list<string>, done: int} $queue
     * @return array{total: int, done: int, left: int}
     */
    public static function summary(array $queue): array
    {
        $total = count($queue['queries']);
        $done = min($queue['done'], $total);

        return ['total' => $total, 'done' => $done, 'left' => $total - $done];
    }

    /**
     * Приводит хвост очереди в соответствие с текущим списком запросов в панели: пользователь мог
     * почистить список от дублей или дописать новые запросы, пока обрабатывалась предыдущая часть.
     * Обработанное начало очереди не трогаем (позиция сохраняется), из остатка убираем то, чего в
     * списке больше нет, а новые запросы дописываем в конец. Пустой список — очередь без изменений.
     *
     * @param array{queries: list<string>, done: int} $queue
     * @param list<string> $current
     * @return array{queries: list<string>, done: int}
     */
    public static function sync(array $queue, array $current): array
    {
        $current = array_values(array_filter(array_map('trim', $current), static fn (string $q): bool => $q !== ''));
        if ($current === []) {
            return $queue;
        }
        $wanted = array_flip($current);
        $processed = array_slice($queue['queries'], 0, $queue['done']);
        $known = array_flip($queue['queries']);
        $rest = [];
        foreach (self::remaining($queue) as $q) {
            if (isset($wanted[$q])) {
                $rest[] = $q;
            }
        }
        foreach ($current as $q) {
            if (!isset($known[$q])) {
                $rest[] = $q; // запрос дописан в панели уже после старта очереди
                $known[$q] = true;
            }
        }

        return ['queries' => array_values(array_merge($processed, $rest)), 'done' => count($processed)];
    }
}
