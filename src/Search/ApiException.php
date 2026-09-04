<?php

declare(strict_types=1);

namespace YandexSites\Search;

/**
 * Ошибка при обращении к Yandex Search API.
 *
 *  - retryable — запрос имеет смысл повторить (лимит частоты, 5xx, сеть);
 *  - fatal — дальнейшие запросы бессмысленны (авторизация, исчерпан лимит).
 */
final class ApiException extends \RuntimeException
{
    /** Коды ошибок в XML-ответе Яндекса. */
    public const CODES = [
        15 => 'по запросу ничего не найдено',
        32 => 'исчерпан лимит запросов',
        33 => 'запрос с неразрешённого IP-адреса',
        42 => 'недействительный ключ',
        43 => 'ключ не найден или заблокирован',
        44 => 'ошибка проверки ключа',
        48 => 'неизвестный тип поиска',
        55 => 'превышена частота запросов',
        100 => 'неверный параметр запроса',
        101 => 'пустой поисковый запрос',
        102 => 'ошибка в тексте запроса',
    ];

    public function __construct(
        string $message,
        private bool $retryable = false,
        private bool $fatal = false,
        private ?int $yandexCode = null,
        ?\Throwable $previous = null,
    ) {
        parent::__construct($message, $yandexCode ?? 0, $previous);
    }

    public static function fromYandexCode(int $code, string $text): self
    {
        $description = self::CODES[$code] ?? 'неизвестная ошибка';
        $message = sprintf('Яндекс вернул ошибку %d (%s)%s', $code, $description, $text !== '' ? ': ' . $text : '');

        return new self(
            $message,
            retryable: $code === 55,
            fatal: in_array($code, [32, 33, 42, 43, 44, 48], true),
            yandexCode: $code,
        );
    }

    public function isRetryable(): bool
    {
        return $this->retryable;
    }

    public function isFatal(): bool
    {
        return $this->fatal;
    }

    public function getYandexCode(): ?int
    {
        return $this->yandexCode;
    }
}
