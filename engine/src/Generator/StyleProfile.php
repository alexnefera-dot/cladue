<?php
declare(strict_types=1);

require_once __DIR__ . '/Rng.php';

/**
 * Стиль-профиль ГЕНЕРАЦИИ (одной связки из 7 страниц) = «шаблон» сайта.
 *
 * Сэмплируется ОДИН РАЗ на генерацию (seed от бренда/домена) и применяется
 * КО ВСЕМ 7 страницам одинаково. Это фиксирует голос/тон/манеру: обращение,
 * первое лицо, где в коридоре сидит плотность цифр/прилагательных, стиль
 * именования бренда, уровень тематических украшений, эмодзи, персона.
 *
 * Структура и объём при этом остаются РАЗНЫМИ у каждой страницы — «плавают».
 * Так набор выглядит как работа одного автора по одному шаблону.
 */
final class StyleProfile
{
    public function __construct(
        public bool $firstPerson,
        public bool $vy,
        public string $addressMode,
        public float $numbersBias,   // позиция в коридоре [0..1], одинаково на всех страницах
        public float $adjBias,
        public float $sizeBias,      // общий «размах» сайта (компактный ↔ развёрнутый)
        public float $flourish,      // 0..1 — доля тематических украшений в заголовках
        public string $naming,       // 'en-heavy' | 'balanced'
        public bool $emojiSite,      // использует ли сайт эмодзи в теле (актуально для main)
        public string $persona,      // имя для повествования от первого лица
    ) {}

    private const PERSONAS = [
        'Алексей Никифоров', 'Игорь Савельев', 'Дмитрий Орлов', 'Максим Крылов',
        'Сергей Данилов', 'Андрей Соколов', 'Павел Ткач', 'Роман Гущин',
    ];

    /** Сэмпл стиль-профиля один раз на генерацию. */
    public static function sample(Rng $rng): self
    {
        // Доминантный режим обращения сайта (одна манера на всю связку).
        // По корпусу: ~half сайтов «личный опыт», часть на «вы», часть нейтральные.
        $roll = $rng->float();
        if ($roll < 0.45) {
            $firstPerson = true;  $vy = $rng->chance(0.7); $mode = 'личный опыт (первое лицо)';
        } elseif ($roll < 0.75) {
            $firstPerson = false; $vy = true;              $mode = 'обращение на «вы»';
        } else {
            $firstPerson = false; $vy = $rng->chance(0.3); $mode = 'нейтрально-описательный';
        }

        return new self(
            firstPerson: $firstPerson,
            vy: $vy,
            addressMode: $mode,
            numbersBias: $rng->range(0.2, 0.7),   // где сайт держит плотность цифр
            adjBias:     $rng->range(0.3, 0.7),
            sizeBias:    $rng->range(0.3, 0.7),
            flourish:    $rng->range(0.0, 0.35),  // редко-умеренно тематические украшения
            naming:      $rng->chance(0.6) ? 'en-heavy' : 'balanced',
            emojiSite:   $rng->chance(0.7),        // большинство main-страниц с эмодзи в теле
            persona:     self::PERSONAS[$rng->int(0, count(self::PERSONAS) - 1)],
        );
    }

    public function toArray(): array
    {
        return [
            'first_person' => $this->firstPerson,
            'vy'           => $this->vy,
            'address_mode' => $this->addressMode,
            'numbers_bias' => round($this->numbersBias, 2),
            'adj_bias'     => round($this->adjBias, 2),
            'size_bias'    => round($this->sizeBias, 2),
            'flourish'     => round($this->flourish, 2),
            'naming'       => $this->naming,
            'emoji_site'   => $this->emojiSite,
            'persona'      => $this->persona,
        ];
    }
}
