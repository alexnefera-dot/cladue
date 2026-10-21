<?php

declare(strict_types=1);

namespace YandexSites\Support;

/**
 * Открытие панели в браузере по умолчанию сразу после запуска.
 *
 * Раньше это была одна строка в bin/panel.php: «подожди секунду и зови open». Секунда — слепая
 * пауза, и у кого браузер уже запущен, адрес уходил в него МГНОВЕННО, раньше чем php -S успевал
 * занять порт: вкладка открывалась с «не удалось подключиться» или не открывалась вовсе. Поэтому
 * фоновый процесс сначала ДОЖИДАЕТСЯ порта (тем же php, которым запущена панель, — без curl и nc,
 * чтобы работало на любой машине) и только потом зовёт браузер.
 */
final class Browser
{
    /** Сколько раз проверять порт (по 0.3 с) — около 18 секунд на запуск сервера с запасом. */
    private const TRIES = 60;

    /** Пауза между проверками порта, мкс. */
    private const WAIT_US = 300000;

    /**
     * Команда, которой открывается браузер (фоном, после ожидания порта). '' — система неизвестна.
     * Вынесена отдельно от запуска, чтобы её можно было проверить тестом, ничего не открывая.
     */
    public static function command(string $url, string $host, int $port, string $os, string $php = PHP_BINARY): string
    {
        if ($os === 'Windows') {
            // В cmd ПЕРВЫЙ аргумент start — заголовок окна. Без пустой пары кавычек команда
            // «start http://…» молча открывает консоль с таким заголовком вместо браузера.
            return 'start "" ' . escapeshellarg($url);
        }
        $openers = $os === 'Darwin'
            ? ['open']
            : ['xdg-open', 'x-www-browser', 'sensible-browser', 'gio open'];
        $calls = [];
        foreach ($openers as $opener) {
            $calls[] = $opener . ' ' . escapeshellarg($url);
        }

        return sprintf('(%s && { %s; }) >/dev/null 2>&1 &', self::waitCommand($host, $port, $php), implode(' || ', $calls));
    }

    /**
     * Запускает открытие браузера. Возвращает строку для консоли: что произошло — чтобы молчаливый
     * отказ («а почему не открылось?») был виден сразу, а не выяснялся расспросами.
     */
    public static function open(string $url, string $host, int $port): string
    {
        if (!self::canExec()) {
            return 'Откройте в браузере: ' . $url . ' (открыть сам не могу: функция exec отключена в php.ini)';
        }
        $cmd = self::command($url, $host, $port, PHP_OS_FAMILY);
        if ($cmd === '') {
            return 'Откройте в браузере: ' . $url;
        }
        @exec($cmd);

        return 'Открываю в браузере: ' . $url . ' (если вкладка не появилась — откройте ссылку вручную)';
    }

    /** Доступна ли exec(): её отключают в php.ini на части сборок, и тогда молча ничего не происходит. */
    public static function canExec(): bool
    {
        if (!function_exists('exec')) {
            return false;
        }
        foreach (explode(',', (string) ini_get('disable_functions')) as $fn) {
            if (strtolower(trim($fn)) === 'exec') {
                return false;
            }
        }

        return true;
    }

    /**
     * Ожидание порта: тем же php, которым запущена панель, без внешних утилит (curl/nc есть не везде).
     * Код завершается с 0, как только порт ответил, и с 1, если сервер так и не поднялся.
     */
    public static function waitCommand(string $host, int $port, string $php = PHP_BINARY): string
    {
        $code = sprintf(
            'for($i=0;$i<%d;$i++){$c=@fsockopen(%s,%d,$n,$s,0.3);if($c){fclose($c);exit(0);}usleep(%d);}exit(1);',
            self::TRIES,
            var_export($host, true),
            $port,
            self::WAIT_US,
        );

        return escapeshellarg($php) . ' -r ' . escapeshellarg($code);
    }
}
