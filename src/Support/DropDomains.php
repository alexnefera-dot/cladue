<?php

declare(strict_types=1);

namespace YandexSites\Support;

use YandexSites\Content\BrandKeys;
use YandexSites\Filter\Domains;
use YandexSites\Model\SearchResult;
use YandexSites\Model\Site;

/**
 * «Дроп-домены» — домены, на поддоменах которых живут сайты МНОГИХ РАЗНЫХ брендов.
 *
 * Запрос пользователя: «вести учёт доменов, которые встречаются более чем в 5 разных брендов (это
 * именно отобранные после фильтрации домены с поддоменами), которые были на разных бренд-ключах
 * (не на одном)». Такой домен — не обычный сайт, а площадка сетки: под каждый бренд поднят свой
 * дор, и по одному домену их видно сразу несколько.
 *
 * Считаем так:
 *  - берём строки выдачи, ПРОШЕДШИЕ фильтры (reason = null) — то есть отобранное;
 *  - оставляем только ДОРЫ: адрес на поддомене (у самого домена поддомена нет — это обычный сайт,
 *    и шесть брендовых запросов к нему значат «портал с обзорами», а не сетку);
 *  - домен должен быть среди ОТОБРАННЫХ сайтов (то, что осталось после всех фильтров и базы);
 *  - бренд берём из запроса (Content\BrandKeys сводит «Вулкан Вегас» / «Vulkan Vegas» к одному ключу);
 *  - домен попадает в список, если РАЗНЫХ брендов у него не меньше MIN_BRANDS.
 */
final class DropDomains
{
    /** «Более 5 брендов» — значит от шести. */
    public const MIN_BRANDS = 6;

    /** Сколько доменов кладём в запись истории (полный список пишется в файл). */
    public const TOP_LIMIT = 30;

    /** Имя файла с полным списком рядом с результатами сбора. */
    public const FILE = 'drop-domains.txt';

    /**
     * Домены с числом брендов от $min и выше, по убыванию числа брендов.
     *
     * @param list<array{result: SearchResult, reason: string|null}> $raw все строки выдачи сбора
     * @param array<int|string, Site> $sites отобранные сайты (ограничиваем ими домены)
     * @return array<string, array{brands: list<string>, hosts: int}> домен => бренды и число доров
     */
    public static function find(array $raw, array $sites, int $min = self::MIN_BRANDS): array
    {
        $allowed = [];
        foreach ($sites as $site) {
            $domain = $site->domain !== '' ? $site->domain : Domains::registrable(Domains::normalize($site->host));
            if ($domain !== '') {
                $allowed[$domain] = true;
            }
        }
        if ($allowed === []) {
            return [];
        }

        /** @var array<string, array{brands: array<string, true>, hosts: array<string, true>}> $found */
        $found = [];
        foreach ($raw as $entry) {
            $item = is_array($entry) ? ($entry['result'] ?? null) : null;
            if (!$item instanceof SearchResult || (is_array($entry) ? ($entry['reason'] ?? null) : null) !== null) {
                continue; // строка не прошла фильтры — в отобранное она не попала
            }
            $host = Domains::normalize($item->host !== '' ? $item->host : Domains::hostFromUrl($item->url));
            if ($host === '') {
                continue;
            }
            $domain = Domains::registrable($host);
            if ($domain === $host || !isset($allowed[$domain])) {
                continue; // не дор (сайт на самом домене) либо домен не в отобранном
            }
            $brand = BrandKeys::of($item->query);
            if ($brand === '') {
                continue; // по этому запросу бренда не видно — считать нечего
            }
            $found[$domain]['brands'][$brand] = true;
            $found[$domain]['hosts'][$host] = true;
        }

        $out = [];
        foreach ($found as $domain => $data) {
            if (count($data['brands']) < $min) {
                continue;
            }
            $brands = array_keys($data['brands']);
            sort($brands);
            $out[$domain] = ['brands' => array_values($brands), 'hosts' => count($data['hosts'])];
        }
        uasort($out, static fn (array $a, array $b): int => count($b['brands']) <=> count($a['brands']));

        return $out;
    }

    /**
     * Короткий список для записи истории: домен + сколько брендов и доров.
     *
     * @param array<string, array{brands: list<string>, hosts: int}> $domains
     * @return list<array{domain: string, brands: int, hosts: int}>
     */
    public static function top(array $domains, int $limit = self::TOP_LIMIT): array
    {
        $out = [];
        foreach ($domains as $domain => $data) {
            $out[] = ['domain' => (string) $domain, 'brands' => count($data['brands']), 'hosts' => (int) $data['hosts']];
            if (count($out) >= $limit) {
                break;
            }
        }

        return $out;
    }

    /**
     * Полный список для файла: по строке на домен с названиями брендов.
     *
     * @param array<string, array{brands: list<string>, hosts: int}> $domains
     */
    public static function text(array $domains): string
    {
        if ($domains === []) {
            return "Доменов с несколькими брендами на поддоменах не найдено.\n";
        }
        $out = sprintf(
            "Домены, которые держат на поддоменах сайты разных брендов (от %d брендов).\n"
            . "Бренд определяется по поисковому запросу; написания «Вулкан Вегас» и «Vulkan Vegas» считаются одним.\n\n",
            self::MIN_BRANDS,
        );
        foreach ($domains as $domain => $data) {
            $labels = array_map(static fn (string $key): string => BrandKeys::label($key), $data['brands']);
            $out .= sprintf(
                "%s — брендов %d, доров %d: %s\n",
                $domain,
                count($data['brands']),
                $data['hosts'],
                implode(', ', $labels),
            );
        }

        return $out;
    }
}
