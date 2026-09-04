<?php

declare(strict_types=1);

namespace Tests;

/**
 * Запускает tests/fake-api-server.php через встроенный сервер PHP на свободном порту.
 */
final class FakeServer
{
    /** @var resource|null */
    private static $process = null;
    private static ?int $port = null;
    private static ?string $failure = null;

    public static function port(): int
    {
        if (self::$port !== null) {
            return self::$port;
        }
        if (self::$failure !== null) {
            Assert::skip(self::$failure);
        }

        $socket = @stream_socket_server('tcp://127.0.0.1:0', $errno, $errstr);
        if ($socket === false) {
            self::$failure = "нет доступа к сокетам: $errstr";
            Assert::skip(self::$failure);
        }
        $name = (string) stream_socket_get_name($socket, false);
        fclose($socket);
        $port = (int) substr($name, (int) strrpos($name, ':') + 1);

        $log = sys_get_temp_dir() . '/yandex-sites-fake-server.log';
        $process = @proc_open(
            [PHP_BINARY, '-S', '127.0.0.1:' . $port, TESTS_ROOT . '/fake-api-server.php'],
            [0 => ['pipe', 'r'], 1 => ['file', $log, 'a'], 2 => ['file', $log, 'a']],
            $pipes,
        );
        if (!is_resource($process)) {
            self::$failure = 'не удалось запустить php -S';
            Assert::skip(self::$failure);
        }
        fclose($pipes[0]);

        for ($i = 0; $i < 50; $i++) {
            $conn = @fsockopen('127.0.0.1', $port, $e, $s, 0.2);
            if ($conn !== false) {
                fclose($conn);
                self::$process = $process;
                self::$port = $port;
                register_shutdown_function([self::class, 'stop']);

                return $port;
            }
            usleep(100000);
        }

        proc_terminate($process);
        proc_close($process);
        self::$failure = 'встроенный сервер PHP не отвечает';
        Assert::skip(self::$failure);
    }

    public static function stop(): void
    {
        if (self::$process !== null) {
            proc_terminate(self::$process);
            proc_close(self::$process);
            self::$process = null;
            self::$port = null;
        }
    }
}
