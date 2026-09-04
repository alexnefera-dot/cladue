<?php

declare(strict_types=1);

namespace YandexSites\Live;

/**
 * Прокси-сервер из списка и его текущее состояние (ошибки, пауза после капчи).
 *
 * Поддерживаемые форматы строк:
 *   host:port, host:port:user:pass, user:pass@host:port,
 *   http://…, https://…, socks4://…, socks4a://…, socks5://…, socks5h://… (логин и пароль через @),
 *   direct — прямое подключение без прокси.
 */
final class Proxy
{
    public const SCHEMES = ['http', 'https', 'socks4', 'socks4a', 'socks5', 'socks5h'];

    /** Ошибок подряд. */
    public int $failures = 0;
    public int $totalFailures = 0;
    public int $requests = 0;
    public int $captchas = 0;
    /** Unix-время, с которого прокси снова можно использовать. */
    public int $availableAt = 0;
    public bool $disabled = false;
    public float $lastRequestAt = 0.0;
    public ?string $userAgent = null;

    private function __construct(
        public readonly ?string $url,
        public readonly string $label,
    ) {
    }

    public static function direct(): self
    {
        return new self(null, 'direct');
    }

    public static function parse(string $line): self
    {
        $line = trim($line);
        if ($line === '') {
            throw new \InvalidArgumentException('пустая строка прокси');
        }
        if (strcasecmp($line, 'direct') === 0) {
            return self::direct();
        }

        $scheme = 'http';
        $rest = $line;
        if (preg_match('~^([a-z0-9]+)://(.*)$~i', $line, $m) === 1) {
            $scheme = strtolower($m[1]);
            $rest = $m[2];
        }
        if (!in_array($scheme, self::SCHEMES, true)) {
            throw new \InvalidArgumentException(sprintf('неподдерживаемый тип прокси «%s» в «%s» (допустимы: %s)', $scheme, $line, implode(', ', self::SCHEMES)));
        }

        $user = null;
        $pass = '';
        $rest = rtrim($rest, '/');
        if (str_contains($rest, '@')) {
            $at = (int) strrpos($rest, '@');
            [$user, $pass] = array_pad(explode(':', substr($rest, 0, $at), 2), 2, '');
            $user = rawurldecode($user);
            $pass = rawurldecode($pass);
            $hostPort = substr($rest, $at + 1);
        } elseif (str_starts_with($rest, '[')) {
            $hostPort = $rest;
        } else {
            $parts = explode(':', $rest);
            if (count($parts) === 4) {
                [$host, $port, $user, $pass] = $parts;
                $hostPort = $host . ':' . $port;
            } elseif (count($parts) === 2) {
                $hostPort = $rest;
            } else {
                throw new \InvalidArgumentException(sprintf('не удалось разобрать прокси «%s»: ожидается host:port, host:port:user:pass, user:pass@host:port или scheme://user:pass@host:port', $line));
            }
        }

        if (preg_match('~^(\[[0-9a-f:.]+\]|[a-z0-9.\-_]+):(\d{1,5})$~i', $hostPort, $m) !== 1 || (int) $m[2] < 1 || (int) $m[2] > 65535) {
            throw new \InvalidArgumentException(sprintf('не удалось разобрать адрес прокси «%s»: ожидается host:port', $line));
        }
        $host = strtolower($m[1]);
        $port = (int) $m[2];

        $auth = $user !== null && $user !== '' ? rawurlencode($user) . ':' . rawurlencode($pass) . '@' : '';

        return new self(sprintf('%s://%s%s:%d', $scheme, $auth, $host, $port), sprintf('%s://%s:%d', $scheme, $host, $port));
    }

    public function isDirect(): bool
    {
        return $this->url === null;
    }

    public function isAvailable(int $now): bool
    {
        return !$this->disabled && $this->availableAt <= $now;
    }
}
