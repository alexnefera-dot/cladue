<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Support\Browser;

final class BrowserTest
{
    private ?string $dir = null;

    private function dir(): string
    {
        if ($this->dir === null) {
            $this->dir = sys_get_temp_dir() . '/yandex-sites-browser-' . uniqid();
            mkdir($this->dir);
        }

        return $this->dir;
    }

    public function testCommandPerSystem(): void
    {
        $url = 'http://127.0.0.1:8777/';

        $mac = Browser::command($url, '127.0.0.1', 8777, 'Darwin', '/usr/bin/php');
        Assert::contains("open '$url'", $mac, 'macOS открывает ссылку через open');
        Assert::contains('8777', $mac, 'в ожидании порта стоит нужный порт');
        Assert::contains('/usr/bin/php', $mac, 'ждём тем же php, которым запущена панель');
        Assert::contains('>/dev/null 2>&1 &', $mac, 'фоном и молча — терминал остаётся под логом панели');

        $linux = Browser::command($url, '127.0.0.1', 8777, 'Linux', '/usr/bin/php');
        foreach (['xdg-open', 'x-www-browser', 'sensible-browser', 'gio open'] as $opener) {
            Assert::contains($opener, $linux, 'на linux перебираем открывашки по очереди');
        }

        // В cmd первый аргумент start — заголовок окна: без пустой пары кавычек открывается не браузер.
        $win = Browser::command($url, '127.0.0.1', 8777, 'Windows');
        Assert::contains('start ""', $win, 'на Windows обязательна пустая пара кавычек перед адресом');
        Assert::contains($url, $win);
        Assert::false(str_contains($win, '&& {'), 'в cmd нет подоболочек — ждать порт там нечем');
    }

    public function testWaitsForTheServerBeforeOpening(): void
    {
        // Суть правки: раньше была слепая пауза в секунду, и при уже запущенном браузере адрес
        // уходил в него раньше, чем php -S занимал порт. Теперь открывашка ждёт ответа порта.
        $flag = $this->dir() . '/opened.flag';
        $port = 0;
        $probe = @stream_socket_server('tcp://127.0.0.1:0', $errno, $errstr);
        if ($probe === false) {
            Assert::skip("нет доступа к сокетам: $errstr");
        }
        $name = (string) stream_socket_get_name($probe, false);
        $port = (int) substr($name, (int) strrpos($name, ':') + 1);
        fclose($probe);

        exec(sprintf('(%s && touch %s) >/dev/null 2>&1 &', Browser::waitCommand('127.0.0.1', $port), escapeshellarg($flag)));
        usleep(900000);
        Assert::false(is_file($flag), 'сервера ещё нет — браузер не зовём');

        $server = @proc_open(
            [PHP_BINARY, '-S', '127.0.0.1:' . $port, '-t', $this->dir()],
            [1 => ['file', '/dev/null', 'a'], 2 => ['file', '/dev/null', 'a']],
            $pipes,
        );
        if (!is_resource($server)) {
            Assert::skip('не удалось запустить php -S');
        }
        try {
            for ($i = 0; $i < 40 && !is_file($flag); $i++) {
                usleep(200000);
            }
            Assert::true(is_file($flag), 'порт ответил — открывашка сработала');
        } finally {
            proc_terminate($server);
            proc_close($server);
        }
    }

    public function tearDownClass(): void
    {
        if ($this->dir === null) {
            return;
        }
        foreach (glob($this->dir . '/*') ?: [] as $file) {
            @unlink($file);
        }
        @rmdir($this->dir);
    }
}
