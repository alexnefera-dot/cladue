<?php

declare(strict_types=1);

namespace Tests;

/**
 * Запускает tests/fake-api-server.php через встроенный сервер PHP на свободном порту.
 * Для каждого режима (FAKE_MODE: ok, captcha, error, local) поднимается отдельный экземпляр.
 */
final class FakeServer
{
    /** @var array<string, array{process: resource, port: int}> */
    private static array $servers = [];
    private static ?string $failure = null;

    public static function port(string $mode = 'ok'): int
    {
        if (isset(self::$servers[$mode])) {
            return self::$servers[$mode]['port'];
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

        $log = sys_get_temp_dir() . '/yandex-sites-fake-server-' . $mode . '.log';
        $env = array_merge(getenv(), ['FAKE_MODE' => $mode]);
        $process = @proc_open(
            [PHP_BINARY, '-S', '127.0.0.1:' . $port, TESTS_ROOT . '/fake-api-server.php'],
            [0 => ['pipe', 'r'], 1 => ['file', $log, 'a'], 2 => ['file', $log, 'a']],
            $pipes,
            null,
            $env,
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
                if (self::$servers === []) {
                    register_shutdown_function([self::class, 'stop']);
                }
                self::$servers[$mode] = ['process' => $process, 'port' => $port];

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
        foreach (self::$servers as $server) {
            proc_terminate($server['process']);
            proc_close($server['process']);
        }
        self::$servers = [];
    }
}
