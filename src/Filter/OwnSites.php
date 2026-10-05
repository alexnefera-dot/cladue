<?php

declare(strict_types=1);

namespace YandexSites\Filter;

use YandexSites\Dorgen\DorgenClient;
use YandexSites\Dorgen\OwnBases;

/**
 * «Свои» сайты — ЕДИНСТВЕННЫЙ источник: список запущенных доменов из системы запусков dorgen.
 *
 * Раньше «наш» угадывался ещё и по меткам в HTML/адресе, по накопленному списку доменов и по
 * ручному own-domains.txt. Эти догадки давали ложные срабатывания — чужой сайт получал пометку
 * «исключён как наш» и выпадал из работы, — поэтому остался один точный источник: список от самой
 * системы, которая эти доры и запускала («наши только с базы апи должны браться, не по оферу,
 * скрину, домену и тп»).
 *
 * Сверка идёт по БАЗЕ — регистрируемому домену хоста (leebet.4916.team → 4916.team). Каждая база
 * несёт все бренды, поэтому множества баз достаточно, и новый поддомен на нашей базе опознаётся
 * сразу, ещё до того как попадёт в очередную выгрузку.
 *
 * Список берётся из `filters.own_bases` (список) и `filters.own_bases_file` (кэш выгрузки,
 * по умолчанию runs/dorgen-bases.json). Файл не коммитится — своя инфраструктура в открытый
 * репозиторий не попадает.
 */
final class OwnSites
{
    /** Почему сайт признан нашим: он запущен в системе запусков. Другой причины больше нет. */
    public const REASON_BASE = 'запущен в системе запусков';

    /** @var array<string, bool> базы (регистрируемые домены) для сверки за один шаг */
    private array $bases = [];

    /**
     * @param iterable<mixed> $bases список баз или карта «база => true» (её отдаёт OwnBases::bases())
     */
    public function __construct(iterable $bases = [])
    {
        foreach ($bases as $key => $value) {
            $base = DorgenClient::baseOf(is_string($key) ? $key : (string) $value);
            if ($base !== '') {
                $this->bases[$base] = true;
            }
        }
    }

    /**
     * Список из конфигурации: `filters.own_bases` + кэш выгрузки `filters.own_bases_file`.
     */
    public static function fromConfig(\YandexSites\Config $config): self
    {
        $bases = array_values((array) $config->get('filters.own_bases', []));
        $file = (string) $config->get('filters.own_bases_file', '');
        if ($file !== '' && is_file($file)) {
            // Тем же загрузчиком, что и страница разбора выдачи: один список «наших» на все экраны.
            $bases = array_merge($bases, array_keys((new OwnBases($file))->bases()));
        }

        return new self($bases);
    }

    /** Нечем определять «наш»: список пуст (выгрузка не настроена или не сделана). */
    public function isEmpty(): bool
    {
        return $this->bases === [];
    }

    /**
     * @return list<string>
     */
    public function bases(): array
    {
        return array_keys($this->bases);
    }

    public function count(): int
    {
        return count($this->bases);
    }

    /**
     * Наш ли хост: его база (регистрируемый домен) есть в списке из системы запусков.
     */
    public function matchesBase(string $host): bool
    {
        if ($this->bases === []) {
            return false;
        }
        $base = DorgenClient::baseOf($host);

        return $base !== '' && isset($this->bases[$base]);
    }

    /**
     * Есть ли наша база в любом из адресов (например, во всей цепочке редиректов).
     *
     * Наш дор уводит через свой же редиректор, и в конечном адресе того уже нет.
     *
     * @param list<string> $urls
     */
    public function matchesBaseInUrls(array $urls): bool
    {
        if ($this->bases === []) {
            return false;
        }
        foreach ($urls as $url) {
            $url = trim((string) $url);
            if ($url === '') {
                continue;
            }
            $host = (string) parse_url(preg_match('~^[a-z0-9+.-]+://~i', $url) === 1 ? $url : 'http://' . $url, PHP_URL_HOST);
            if ($host !== '' && $this->matchesBase($host)) {
                return true;
            }
        }

        return false;
    }
}
