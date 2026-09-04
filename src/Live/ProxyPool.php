<?php

declare(strict_types=1);

namespace YandexSites\Live;

/**
 * Список прокси: выбор по кругу, несколько запросов подряд через один прокси,
 * пауза после ошибок и капчи, отключение после серии ошибок.
 */
final class ProxyPool
{
    /** @var list<Proxy> */
    private array $proxies = [];
    private int $cursor = -1;
    private ?Proxy $current = null;
    private int $leaseLeft = 0;

    /**
     * @param iterable<Proxy> $proxies
     */
    public function __construct(iterable $proxies = [], private int $requestsPerProxy = 1, private int $maxFailures = 5)
    {
        foreach ($proxies as $proxy) {
            $this->proxies[] = $proxy;
        }
        $this->requestsPerProxy = max(1, $this->requestsPerProxy);
    }

    /**
     * @param iterable<mixed> $lines строки в форматах Proxy::parse(); пустые и комментарии (#) пропускаются
     */
    public static function fromLines(iterable $lines, int $requestsPerProxy = 1, int $maxFailures = 5): self
    {
        $proxies = [];
        $seen = [];
        foreach ($lines as $line) {
            $line = trim((string) $line);
            if ($line === '' || str_starts_with($line, '#')) {
                continue;
            }
            $proxy = Proxy::parse($line);
            $key = $proxy->url ?? 'direct';
            if (isset($seen[$key])) {
                continue;
            }
            $seen[$key] = true;
            $proxies[] = $proxy;
        }

        return new self($proxies, $requestsPerProxy, $maxFailures);
    }

    public static function fromFile(string $path, int $requestsPerProxy = 1, int $maxFailures = 5): self
    {
        if (!is_file($path) || !is_readable($path)) {
            throw new \RuntimeException("Файл со списком прокси не найден или недоступен: $path");
        }

        return self::fromLines(file($path, FILE_IGNORE_NEW_LINES) ?: [], $requestsPerProxy, $maxFailures);
    }

    public function isEmpty(): bool
    {
        return $this->proxies === [];
    }

    public function count(): int
    {
        return count($this->proxies);
    }

    /**
     * @return list<Proxy>
     */
    public function all(): array
    {
        return $this->proxies;
    }

    /**
     * Следующий доступный прокси или null, если все на паузе или отключены (или список пуст).
     */
    public function next(): ?Proxy
    {
        $now = time();
        if ($this->current !== null && $this->leaseLeft > 0 && $this->current->isAvailable($now)) {
            $this->leaseLeft--;

            return $this->current;
        }

        $n = count($this->proxies);
        for ($i = 0; $i < $n; $i++) {
            $this->cursor = ($this->cursor + 1) % $n;
            $proxy = $this->proxies[$this->cursor];
            if ($proxy->isAvailable($now)) {
                $this->current = $proxy;
                $this->leaseLeft = $this->requestsPerProxy - 1;

                return $proxy;
            }
        }
        $this->current = null;
        $this->leaseLeft = 0;

        return null;
    }

    public function success(Proxy $proxy): void
    {
        $proxy->failures = 0;
    }

    /**
     * @param string $reason captcha | error | blocked
     */
    public function fail(Proxy $proxy, string $reason, int $cooldownSeconds): void
    {
        $proxy->failures++;
        $proxy->totalFailures++;
        if ($reason === 'captcha') {
            $proxy->captchas++;
        }
        $proxy->availableAt = time() + max(0, $cooldownSeconds);
        if ($this->maxFailures > 0 && $proxy->failures >= $this->maxFailures) {
            $proxy->disabled = true;
        }
        if ($this->current === $proxy) {
            $this->current = null;
            $this->leaseLeft = 0;
        }
    }

    /**
     * Через сколько секунд освободится ближайший прокси; null — все отключены (или список пуст).
     */
    public function secondsUntilAvailable(): ?int
    {
        $now = time();
        $min = null;
        foreach ($this->proxies as $proxy) {
            if ($proxy->disabled) {
                continue;
            }
            $wait = max(0, $proxy->availableAt - $now);
            if ($min === null || $wait < $min) {
                $min = $wait;
            }
        }

        return $min;
    }

    public function activeCount(): int
    {
        $count = 0;
        foreach ($this->proxies as $proxy) {
            if (!$proxy->disabled) {
                $count++;
            }
        }

        return $count;
    }

    /**
     * @return list<array{proxy: string, requests: int, captchas: int, failures: int, disabled: bool, cooldown: int}>
     */
    public function stats(): array
    {
        $now = time();
        $stats = [];
        foreach ($this->proxies as $proxy) {
            $stats[] = [
                'proxy' => $proxy->label,
                'requests' => $proxy->requests,
                'captchas' => $proxy->captchas,
                'failures' => $proxy->totalFailures,
                'disabled' => $proxy->disabled,
                'cooldown' => $proxy->disabled ? 0 : max(0, $proxy->availableAt - $now),
            ];
        }

        return $stats;
    }
}
