<?php

declare(strict_types=1);

namespace YandexSites\Content;

/**
 * Автоопределение названия бренда по странице: английское берём из домена, русское — ищем в тексте
 * то слово, транслитерация которого совпадает с английским (cryptoboss ↔ криптобосс). Так пользователю
 * не нужно вводить бренд руками — достаточно нажать «Забрать контент» у сайта.
 */
final class BrandDetector
{
    /** Кириллица → латиница для сравнения (упрощённая фонетическая). */
    private const CYR2LAT = [
        'а' => 'a', 'б' => 'b', 'в' => 'v', 'г' => 'g', 'д' => 'd', 'е' => 'e', 'ё' => 'e', 'ж' => 'zh',
        'з' => 'z', 'и' => 'i', 'й' => 'i', 'к' => 'k', 'л' => 'l', 'м' => 'm', 'н' => 'n', 'о' => 'o',
        'п' => 'p', 'р' => 'r', 'с' => 's', 'т' => 't', 'у' => 'u', 'ф' => 'f', 'х' => 'h', 'ц' => 'c',
        'ч' => 'ch', 'ш' => 'sh', 'щ' => 'sch', 'ъ' => '', 'ы' => 'i', 'ь' => '', 'э' => 'e', 'ю' => 'yu', 'я' => 'ya',
    ];

    /**
     * Служебные слова тематики (казино), которые НЕ бывают брендом сайта — чтобы по общему домену
     * (casino…, …bet) или тексту не выдать за бренд «казино»/«онлайн»/«бонус».
     *
     * @var list<string>
     */
    private const RU_STOP = [
        'казино', 'онлайн', 'бонус', 'бонусы', 'слот', 'слоты', 'игра', 'игры', 'играть', 'игровые',
        'зеркало', 'официальный', 'официальное', 'сайт', 'вход', 'войти', 'регистрация', 'ставки',
        'ставка', 'спорт', 'деньги', 'автоматы', 'промокод', 'лицензия', 'депозит', 'выигрыш',
        'фриспины', 'кэшбэк', 'приложение', 'скачать',
    ];

    /** Родовые английские метки домена, которые не считаем брендом. */
    private const EN_GENERIC = [
        'casino', 'kazino', 'bet', 'bets', 'win', 'wins', 'game', 'games', 'gaming', 'online',
        'slot', 'slots', 'play', 'club', 'official', 'bonus', 'mirror', 'site', 'the', 'www',
    ];

    /**
     * @param string $html HTML главной страницы (или любой страницы сайта)
     * @param string $host домен сайта (например, cryptoboss.ccy.casino)
     * @param list<string> $moreHtml HTML остальных страниц сайта — чтобы бренд нашёлся, даже если
     *        главная оказалась заглушкой/редиректом (бренд и canonical есть на внутренних страницах)
     * @return array{en: string, ru: string} английский и русский бренд ('' если не найден)
     */
    public function detect(string $html, string $host, array $moreHtml = []): array
    {
        $docs = array_merge([$html], array_values(array_filter($moreHtml, 'is_string')));
        $text = '';
        foreach ($docs as $doc) {
            $text .= ' ' . $this->visibleText($doc);
        }
        $text = mb_substr($text, 0, 2_000_000);

        // Кандидаты в английский бренд: сперва метки поддоменов из canonical/og:url ВСЕХ страниц
        // (kush.casinozsd.buzz → kush), затем метка самого домена. У сеток бренд часто сидит в
        // поддомене, а регистрируемый домен общий/мусорный (casinozsd), поэтому по домену бренд
        // не находится и в тексте ничего не заменяется. Родовые метки (casino, bet…) отбрасываем.
        $candidates = [];
        foreach ($docs as $doc) {
            $canon = $this->canonicalHost($doc);
            if ($canon !== '') {
                $candidates[] = $this->brandFromHost($canon);
            }
        }
        $candidates[] = $this->brandFromHost($host);
        $candidates = array_values(array_unique(array_filter(
            $candidates,
            fn (string $c): bool => mb_strlen($c) >= 3 && !$this->isGenericEn($c),
        )));

        // Берём первого кандидата, для которого в тексте находится русский бренд — значит, это
        // реальное имя сайта, а не случайная метка домена.
        foreach ($candidates as $en) {
            $ru = $this->detectRu($text, $en);
            if ($ru !== '') {
                return ['en' => $en, 'ru' => $ru];
            }
        }

        return ['en' => $candidates[0] ?? $this->brandFromHost($host), 'ru' => ''];
    }

    /** Родовая ли это английская метка (casino, bet, win…) — такие не бренд (цифры отбрасываем). */
    private function isGenericEn(string $label): bool
    {
        $label = preg_replace('~[0-9]+~', '', mb_strtolower($label)) ?? $label;

        return in_array($label, self::EN_GENERIC, true);
    }

    /**
     * Хост из canonical/og:url страницы — часто именно там «бренд.домен», а не общий регистрируемый домен.
     */
    private function canonicalHost(string $html): string
    {
        $url = '';
        if (preg_match('~<link\b[^>]*\brel=["\']canonical["\'][^>]*>~i', $html, $tag)
            && preg_match('~\bhref=["\']([^"\']+)~i', $tag[0], $h)) {
            $url = $h[1];
        } elseif (preg_match('~<meta\b[^>]*\bproperty=["\']og:url["\'][^>]*>~i', $html, $tag)
            && preg_match('~\bcontent=["\']([^"\']+)~i', $tag[0], $c)) {
            $url = $c[1];
        }
        if ($url === '') {
            return '';
        }
        $host = parse_url(trim($url), PHP_URL_HOST);

        return is_string($host) ? mb_strtolower($host) : '';
    }

    /**
     * Английский бренд — первая метка домена (cryptoboss.ccy.casino → cryptoboss), только буквы/цифры.
     */
    public function brandFromHost(string $host): string
    {
        $host = mb_strtolower(trim($host));
        $host = preg_replace('~^www\d*\.~', '', $host) ?? $host;
        $label = explode('.', $host)[0] ?? '';

        return (string) preg_replace('~[^a-z0-9]~', '', $label);
    }

    /**
     * Русский бренд — кириллическое слово (или пара соседних слов: «вулкан вегас», «мани икс»),
     * чья транслитерация ближе всего к английскому бренду. Служебные слова тематики (казино,
     * бонус…) в бренд не берём.
     */
    private function detectRu(string $text, string $en): string
    {
        $target = $this->phonetic($en);
        if (mb_strlen($target) < 3) {
            return '';
        }
        $threshold = max(1, (int) floor(mb_strlen($target) / 4));

        preg_match_all('~[А-Яа-яЁё]{3,}~u', $text, $m);
        $tokens = array_map('mb_strtolower', $m[0]);
        if ($tokens === []) {
            return '';
        }
        $freq = array_count_values($tokens);

        // Кандидаты-фразы: отдельные слова и соседние пары (бренд бывает из двух слов).
        $phrases = [];
        $count = count($tokens);
        for ($i = 0; $i < $count; $i++) {
            $phrases[$tokens[$i]] = [$tokens[$i]];
            if ($i + 1 < $count) {
                $phrases[$tokens[$i] . ' ' . $tokens[$i + 1]] = [$tokens[$i], $tokens[$i + 1]];
            }
        }

        $best = '';
        $bestDistance = PHP_INT_MAX;
        $bestFreq = 0;
        foreach ($phrases as $phrase => $words) {
            // Фразу целиком из служебных слов (казино, бонус, онлайн…) за бренд не считаем.
            if (array_filter($words, fn (string $w): bool => !$this->isStopword($w)) === []) {
                continue;
            }
            $distance = levenshtein($this->phonetic($this->translit(str_replace(' ', '', $phrase))), $target);
            if ($distance > $threshold) {
                continue;
            }
            $f = 0;
            foreach ($words as $w) {
                $f += $freq[$w] ?? 0;
            }
            if ($distance < $bestDistance || ($distance === $bestDistance && $f > $bestFreq)) {
                $best = $phrase;
                $bestDistance = $distance;
                $bestFreq = $f;
            }
        }

        return $best;
    }

    private function isStopword(string $token): bool
    {
        return in_array(mb_strtolower($token), self::RU_STOP, true);
    }

    private function translit(string $cyr): string
    {
        $out = '';
        foreach (preg_split('~~u', mb_strtolower($cyr), -1, PREG_SPLIT_NO_EMPTY) ?: [] as $ch) {
            $out .= self::CYR2LAT[$ch] ?? $ch;
        }

        return $out;
    }

    /**
     * Фонетическая нормализация для сравнения: только латинские буквы, c/q→k, y→i, w→v, без сдвоенных.
     */
    private function phonetic(string $text): string
    {
        $text = mb_strtolower($text);
        $text = (string) preg_replace('~[^a-zа-яё]~u', '', $text);
        $text = strtr($text, ['c' => 'k', 'q' => 'k', 'y' => 'i', 'w' => 'v']);
        $text = (string) preg_replace('~(.)\1+~u', '$1', $text);

        return $text;
    }

    private function visibleText(string $html): string
    {
        $text = preg_replace('~<(script|style|noscript|svg|template)\b[^>]*>.*?</\1>~isu', ' ', $html) ?? $html;
        $text = strip_tags($text);

        return html_entity_decode($text, ENT_QUOTES | ENT_HTML5, 'UTF-8');
    }
}
