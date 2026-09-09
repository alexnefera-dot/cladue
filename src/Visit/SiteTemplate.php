<?php

declare(strict_types=1);

namespace YandexSites\Visit;

use YandexSites\Model\Site;

/**
 * Тип вёрстки сайта — по HTML главной страницы, сразу после сбора (по превью), без скриншотов.
 *
 * Сайты сети приходят двумя семействами шаблонов, и их можно различить по устойчивым признакам
 * разметки (имена классов/id и типовые надписи), которые не пересекаются между семействами:
 *  - «7–9 страниц»: шапка с брендом, телефон «+7 (495)…» и «Круглосуточно · 24/7», панель фильтров
 *    «Все игры / Провайдеры», вступительный текст перед h1, облако «Навигация»/«Быстрые ссылки»;
 *  - «12–15 страниц»: «Логотип <бренд>», меню с эмодзи, хлебные крошки «🏠 Главная», карточки
 *    «Куда перейти», всплывающие «выигрыши», чат 24/7 и приветственный попап; у части сайтов имена
 *    классов обфусцированы (pg-xxxxx / mh-xxxxx), но id секций (reserved-aux, jackpots, levels…) те же.
 * Всё остальное — «без категории» (рандомный сайт). Признак засчитывается по подстроке в HTML;
 * «сильные» признаки (встречаются только у своего семейства) весят 2, «слабые» (типовые имена вроде
 * breadcrumbs/site-footer, которые бывают и у обычных сайтов) — 1; семейство побеждает при сумме
 * ≥ MIN_SCORE и только если найден хотя бы один сильный признак — так WordPress-сайт с
 * skip-link + site-footer + breadcrumbs не становится «12–15-страничным».
 */
final class SiteTemplate
{
    /** Семейство «7–9 страниц» (папки 7-стр…10-стр после выгрузки). */
    public const PAGES7 = 'pages7';

    /** Семейство «12–15 страниц». */
    public const PAGES12 = 'pages12';

    /** Не распознан — рандомный сайт без категории. */
    public const OTHER = 'other';

    public const TYPES = [self::PAGES7, self::PAGES12, self::OTHER];

    /** Подписи для таблицы и статистики. */
    public const LABELS = [
        self::PAGES7 => '7–9 стр.',
        self::PAGES12 => '12–15 стр.',
        self::OTHER => 'без категории',
    ];

    /** Минимальная сумма весов найденных признаков, чтобы отнести сайт к семейству. */
    public const MIN_SCORE = 4;

    /**
     * Признаки семейств: подстрока HTML => вес (2 — только у этого семейства, 1 — типовое имя).
     *
     * @var array<string, array<string, int>>
     */
    private const MARKERS = [
        self::PAGES7 => [
            'tags-cloud' => 2,
            'promo-text' => 2,
            'filters-section' => 2,
            'company-info' => 2,
            'final-cta' => 2,
            'reviews-form' => 2,
            'Круглосуточно' => 2,
            'entry-content' => 1,
            'main-nav' => 1,
            '+7 (495)' => 1,
        ],
        self::PAGES12 => [
            'bonusPopup' => 2,
            'winNotifications' => 2,
            'keywords-block' => 2,
            'keyword-pill' => 2,
            'value-pillars' => 2,
            'layout-block' => 2,
            'mobileNav' => 2,
            'recent-payouts' => 2,
            'supportWidget' => 2,
            'reserved-aux' => 2,
            'yandex-index-blocks' => 2,
            'quicklink' => 2,
            'pulse-glow' => 2,
            'glass-card' => 2,
            'id="jackpots"' => 1,
            'id="neighbors"' => 1,
            'id="levels"' => 1,
            'content-wrapper' => 1,
            'faq-section' => 1,
            'site-footer' => 1,
            'skip-link' => 1,
            'breadcrumbs' => 1,
        ],
    ];

    /** Тип вёрстки страницы: PAGES7 / PAGES12 / OTHER. Пустой HTML — OTHER. */
    public static function guess(string $html): string
    {
        if ($html === '') {
            return self::OTHER;
        }
        $best = self::OTHER;
        $bestScore = 0;
        foreach (self::scores($html) as $type => $s) {
            if ($s['score'] >= self::MIN_SCORE && $s['strong'] > 0 && $s['score'] > $bestScore) {
                $best = $type;
                $bestScore = $s['score'];
            }
        }

        return $best;
    }

    /**
     * Сумма весов и число сильных признаков по каждому семейству — для отладки и тестов.
     *
     * @return array<string, array{score: int, strong: int, hits: list<string>}>
     */
    public static function scores(string $html): array
    {
        $out = [];
        foreach (self::MARKERS as $type => $markers) {
            $score = 0;
            $strong = 0;
            $hits = [];
            foreach ($markers as $marker => $weight) {
                if (str_contains($html, $marker)) {
                    $score += $weight;
                    $strong += $weight >= 2 ? 1 : 0;
                    $hits[] = $marker;
                }
            }
            $out[$type] = ['score' => $score, 'strong' => $strong, 'hits' => $hits];
        }

        return $out;
    }

    /** Подпись типа для человека; неизвестный тип — «без категории». */
    public static function label(string $type): string
    {
        return self::LABELS[$type] ?? self::LABELS[self::OTHER];
    }

    /**
     * Тип сайта по его визитам: голосование успешно открытых страниц (главная и внутренние страницы
     * одного шаблона несут одни и те же признаки). '' — ни одна страница не открыта, типа нет.
     *
     * @param list<array<string, mixed>> $visits
     */
    public static function ofVisits(array $visits): string
    {
        $votes = [];
        foreach ($visits as $visit) {
            $visit = (array) $visit;
            $type = (string) ($visit['template'] ?? '');
            if ($type === '' || !($visit['ok'] ?? false)) {
                continue;
            }
            $votes[$type] = ($votes[$type] ?? 0) + 1;
        }
        if ($votes === []) {
            return '';
        }
        // Семейство с большинством голосов; «без категории» уступает семейству при равенстве
        // (страница-заглушка без признаков не должна перевешивать распознанную главную).
        $best = '';
        $bestVotes = 0;
        foreach ($votes as $type => $n) {
            if ($n > $bestVotes || ($n === $bestVotes && $best === self::OTHER)) {
                $best = $type;
                $bestVotes = $n;
            }
        }

        return $best;
    }

    /**
     * Сколько сайтов какого типа: ['pages7' => 12, 'pages12' => 3, 'other' => 5] (в порядке TYPES,
     * нули опущены). Наши шаблоны и сайты без единой открытой страницы не считаются.
     *
     * @param array<int|string, Site> $sites
     * @return array<string, int>
     */
    public static function histogram(array $sites): array
    {
        $hist = [];
        foreach ($sites as $site) {
            if ($site->own) {
                continue;
            }
            $type = self::ofVisits($site->visits);
            if ($type !== '') {
                $hist[$type] = ($hist[$type] ?? 0) + 1;
            }
        }
        $ordered = [];
        foreach (self::TYPES as $type) {
            if (isset($hist[$type])) {
                $ordered[$type] = $hist[$type];
            }
        }

        return $ordered;
    }

    /** Гистограмма текстом: «7–9 стр. — 12, 12–15 стр. — 3, без категории — 5»; '' — если считать нечего. */
    public static function histogramText(array $hist): string
    {
        $parts = [];
        foreach ($hist as $type => $count) {
            $parts[] = self::label((string) $type) . ' — ' . $count;
        }

        return implode(', ', $parts);
    }
}
