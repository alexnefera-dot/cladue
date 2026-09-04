<?php

declare(strict_types=1);

namespace YandexSites\Filter;

/**
 * «Свои» сайты — шаблоны, которые мы сами размещаем и не хотим собирать/скачивать.
 * Опознаются по устойчивым меткам (домен размещения, токен верификации, путь к ассетам
 * и т.п.) — подстрокам, которые ищем в HTML страницы и в адресе сайта. Метки не зависят
 * от меняющихся кодов/стилей (QR и оформление), поэтому опираемся на них, а не на текст.
 *
 * Метки берутся из `filters.own_markers` (список) и файла `filters.own_markers_file`
 * (по одной на строку, `#` — комментарий). Файл не коммитится (см. .gitignore), чтобы
 * не публиковать свою инфраструктуру в открытом репозитории.
 */
final class OwnSites
{
    /** @var list<string> */
    private array $markers;

    /**
     * @param list<string> $markers
     */
    public function __construct(array $markers)
    {
        $seen = [];
        $clean = [];
        foreach ($markers as $marker) {
            $marker = trim((string) $marker);
            if ($marker === '' || str_starts_with($marker, '#')) {
                continue;
            }
            $key = mb_strtolower($marker);
            if (!isset($seen[$key])) {
                $seen[$key] = true;
                $clean[] = $marker;
            }
        }
        $this->markers = $clean;
    }

    /**
     * Собирает метки из конфигурации: список `filters.own_markers` + файл `filters.own_markers_file`.
     */
    public static function fromConfig(\YandexSites\Config $config): self
    {
        $markers = array_values((array) $config->get('filters.own_markers', []));
        $file = (string) $config->get('filters.own_markers_file', '');
        if ($file !== '' && is_file($file)) {
            foreach (file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [] as $line) {
                $markers[] = $line;
            }
        }

        return new self($markers);
    }

    public function isEmpty(): bool
    {
        return $this->markers === [];
    }

    /**
     * @return list<string>
     */
    public function markers(): array
    {
        return $this->markers;
    }

    /**
     * Совпадает ли метка с содержимым страницы (подстрока без учёта регистра).
     */
    public function matchesHtml(string $html): bool
    {
        foreach ($this->markers as $marker) {
            if (stripos($html, $marker) !== false) {
                return true;
            }
        }

        return false;
    }

    /**
     * Совпадает ли метка-домен с хостом сайта: точное равенство или поддомен (kush.oasc.team ~ oasc.team).
     */
    public function matchesHost(string $host): bool
    {
        $host = mb_strtolower(trim($host));
        if ($host === '') {
            return false;
        }
        foreach ($this->domainMarkers() as $domain) {
            if ($host === $domain || str_ends_with($host, '.' . $domain)) {
                return true;
            }
        }

        return false;
    }

    /**
     * Метки, похожие на домен (для отсева ещё на этапе сбора, где есть только адрес).
     *
     * @return list<string>
     */
    public function domainMarkers(): array
    {
        $domains = [];
        foreach ($this->markers as $marker) {
            $marker = mb_strtolower($marker);
            if (preg_match('~^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9-]+)*\.[a-z]{2,}$~', $marker) === 1) {
                $domains[] = $marker;
            }
        }

        return $domains;
    }
}
