<?php

declare(strict_types=1);

namespace YandexSites\Http;

/**
 * Сетевая ошибка (curl): таймаут, DNS, обрыв соединения и т. п.
 */
final class HttpException extends \RuntimeException
{
}
