<?php

declare(strict_types=1);

namespace YandexSites\Cli;

/**
 * Ошибка в аргументах командной строки или конфигурации (код выхода 2).
 */
final class UsageException extends \RuntimeException
{
}
