<?php

declare(strict_types=1);

namespace YandexSites\Content;

/**
 * Список известных названий казино-брендов (латиница и кириллица) — чтобы при подготовке контента
 * автоматически заменять ЛЮБЫЕ упоминания посторонних брендов на переменную (латиница →
 * %brand_name_en%, кириллица → %brand_name_ru%), а не только основной бренд сайта.
 *
 * Базовый список ниже можно дополнять/сокращать своим файлом brands.txt (по одному бренду на строку,
 * `#` — комментарий); он не коммитится. Совпадение — по границам слова и с учётом гомоглифов
 * (латиница↔кириллица), так что опечатки вида STAKE/STAKЕ тоже ловятся.
 */
final class KnownBrands
{
    /** @var list<string> распространённые бренды (RU-рынок); подобраны так, чтобы реже задевать обычные слова */
    public const DEFAULTS = [
        'vavada', 'вавада',
        'cryptoboss', 'криптобосс',
        'stake', 'стейк',
        'mostbet', 'мостбет',
        'melbet', 'мелбет',
        '1xbet', '1хбет',
        '1win', '1вин',
        'pinup', 'pin-up', 'пинап', 'пин-ап',
        'izzi', 'иззи',
        'jozz', 'джозз',
        'legzo', 'легзо',
        'riobet', 'риобет',
        'playfortuna', 'play fortuna', 'плейфортуна',
        'gizbo', 'гизбо',
        'sykaaa', 'сукка',
        'brillx', 'бриллкс', 'брилкс',
        'starda', 'старда',
        'joycasino', 'джойказино',
        'azino777', 'azino', 'азино777', 'азино',
        'arkada', 'аркада',
        'kometa', 'комета',
        'dragonmoney', 'dragon money', 'драгонмани', 'драгон мани',
        'catcasino', 'кэтказино',
        'ramenbet', 'раменбет',
        'gama', 'гама',
        'monro', 'монро',
        'booi', 'буи',
        'rox', 'рокс',
        'irwin', 'ирвин',
        'starz', 'старз',
        'volna', 'волна казино',
        'lex casino', 'лекс казино',
        'sol casino', 'сол казино',
    ];

    /**
     * Полный список: базовые бренды + записи из файла (по умолчанию brands.txt в текущем каталоге).
     *
     * @return list<string>
     */
    public static function all(?string $file = 'brands.txt'): array
    {
        $brands = self::DEFAULTS;
        if ($file !== null && $file !== '' && is_file($file)) {
            foreach (file($file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [] as $line) {
                $line = trim($line);
                if ($line !== '' && !str_starts_with($line, '#')) {
                    $brands[] = $line;
                }
            }
        }
        $seen = [];
        $out = [];
        foreach ($brands as $brand) {
            $key = mb_strtolower($brand);
            if (!isset($seen[$key])) {
                $seen[$key] = true;
                $out[] = $brand;
            }
        }

        return $out;
    }
}
