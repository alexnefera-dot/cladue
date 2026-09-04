<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Live\Proxy;
use YandexSites\Live\ProxyPool;

final class ProxyPoolTest
{
    public function testParsesProxyFormats(): void
    {
        $p = Proxy::parse('203.0.113.10:8080');
        Assert::same('http://203.0.113.10:8080', $p->url);
        Assert::same('http://203.0.113.10:8080', $p->label);
        Assert::false($p->isDirect());

        $p = Proxy::parse('203.0.113.11:8080:login:pass word');
        Assert::same('http://login:pass%20word@203.0.113.11:8080', $p->url);
        Assert::same('http://203.0.113.11:8080', $p->label, 'логин и пароль не попадают в подпись');

        Assert::same('http://user:p%40ss@host.example:3128', Proxy::parse('user:p@ss@host.example:3128')->url);
        Assert::same('socks5://u:p@203.0.113.12:1080', Proxy::parse('socks5://u:p@203.0.113.12:1080')->url);
        Assert::same('https://proxy.example:443', Proxy::parse('HTTPS://Proxy.Example:443/')->url);
        Assert::same('socks5h://[::1]:1080', Proxy::parse('socks5h://[::1]:1080')->url);

        $direct = Proxy::parse('direct');
        Assert::true($direct->isDirect());
        Assert::null($direct->url);
        Assert::same('direct', $direct->label);

        foreach (['ftp://h:1', 'host', 'host:99999', 'a:b:c', ''] as $bad) {
            Assert::throws(\InvalidArgumentException::class, static fn () => Proxy::parse($bad));
        }
    }

    public function testRotationAndLeases(): void
    {
        $pool = ProxyPool::fromLines(['# комментарий', '', 'a.ru:1', 'a.ru:1', 'b.ru:2']);
        Assert::same(2, $pool->count(), 'дубли убираются');
        Assert::same(['http://a.ru:1', 'http://b.ru:2', 'http://a.ru:1'], [$pool->next()?->label, $pool->next()?->label, $pool->next()?->label]);

        $sticky = ProxyPool::fromLines(['a.ru:1', 'b.ru:2'], 2);
        $labels = [];
        for ($i = 0; $i < 5; $i++) {
            $labels[] = $sticky->next()?->label;
        }
        Assert::same(['http://a.ru:1', 'http://a.ru:1', 'http://b.ru:2', 'http://b.ru:2', 'http://a.ru:1'], $labels);

        Assert::null((new ProxyPool([]))->next());
        Assert::true((new ProxyPool([]))->isEmpty());
    }

    public function testCooldownAndDisabling(): void
    {
        $pool = ProxyPool::fromLines(['a.ru:1', 'b.ru:2'], 1, 2);
        [$a, $b] = $pool->all();

        $pool->fail($a, 'captcha', 60);
        Assert::same(1, $a->captchas);
        Assert::false($a->isAvailable(time()));
        Assert::same('http://b.ru:2', $pool->next()?->label);
        Assert::same('http://b.ru:2', $pool->next()?->label, 'a на паузе — снова b');
        Assert::same(0, $pool->secondsUntilAvailable());

        $stats = $pool->stats();
        Assert::same(1, $stats[0]['captchas']);
        Assert::true($stats[0]['cooldown'] > 0 && $stats[0]['cooldown'] <= 60);
        Assert::false($stats[0]['disabled']);

        $pool->fail($b, 'error', 30);
        Assert::null($pool->next());
        $wait = $pool->secondsUntilAvailable();
        Assert::true($wait !== null && $wait > 0 && $wait <= 30, 'ближайший — b через 30 с');

        $pool->fail($a, 'error', 10);
        Assert::true($a->disabled, 'после max_failures подряд прокси отключается');
        Assert::same(1, $pool->activeCount());
        $pool->fail($b, 'error', 10);
        Assert::null($pool->secondsUntilAvailable(), 'все отключены');

        $pool->success($b);
        Assert::same(0, $b->failures);
        Assert::same(2, $b->totalFailures);
    }

    public function testFromFile(): void
    {
        $file = sys_get_temp_dir() . '/yandex-sites-proxies-' . uniqid() . '.txt';
        file_put_contents($file, "# список\n10.0.0.1:3128\ndirect\n");
        $pool = ProxyPool::fromFile($file);
        Assert::same(2, $pool->count());
        Assert::true($pool->all()[1]->isDirect());
        unlink($file);
        Assert::throws(\RuntimeException::class, static fn () => ProxyPool::fromFile($file), 'не найден');
    }
}
