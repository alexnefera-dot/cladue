<?php
declare(strict_types=1);

/**
 * Разбор флагов командной строки, общий для всех инструментов движка.
 *
 * Появился после того, как выяснилось: `priyomka-v4.php` и
 * `priyomka-komplekt.php` принимали корпус только латиницей (`--korpus=`),
 * а вызывались с кириллическим `--корпус=`. Неизвестный флаг молча
 * отбрасывался, приёмка сравнивала текст с зашитым по умолчанию корпусом
 * прошлого поколения, и девять комплектов из двадцати ушли в сдачу с
 * пересечением выше порога.
 *
 * Отсюда два правила, которые здесь и заданы:
 *   1. написание флага не имеет значения — «корпус» и «korpus» это одно и то же;
 *   2. неизвестный флаг — это ошибка с выходом, а не молчаливый пропуск.
 */
final class Flagi
{
    /** Синонимы: как бы флаг ни написали, он ложится в первое имя списка. */
    private const SINONIMY = [
        'корпус'  => ['korpus', 'corpus'],
        'профиль' => ['profil', 'profile'],
        'выход'   => ['vyhod', 'out'],
        'маска'   => ['maska', 'mask'],
        'комплект' => ['komplekt', 'set'],
        'каркас'  => ['karkas'],
        'попыток' => ['popytok', 'tries'],
        'текст'   => ['text'],
        'школа'   => ['shkola', 'school'],
        'пары'    => ['pairs'],
    ];

    /**
     * @param list<string> $argv    аргументы как есть, включая имя скрипта
     * @param int          $ot      с какого индекса начинать разбор
     * @param list<string> $znaem   какие ключи инструмент понимает (в любом написании)
     * @param list<string> $flagi   ключи без значения: `--json`, `--пары`
     * @return array{0: array<string,string>, 1: list<string>} опции и позиционные аргументы
     */
    public static function razobrat(array $argv, int $ot, array $znaem, array $flagi = []): array
    {
        $karta = self::karta($znaem, $flagi);
        $opts = [];
        $poz = [];
        foreach (array_slice($argv, $ot) as $a) {
            if (!str_starts_with($a, '--')) { $poz[] = $a; continue; }
            $telo = substr($a, 2);
            $imya = $telo;
            $znach = '';
            $sZnach = false;
            if (str_contains($telo, '=')) {
                [$imya, $znach] = explode('=', $telo, 2);
                $sZnach = true;
            }
            $klyuch = self::normalizovat($imya, $karta);
            if ($klyuch === null) {
                fwrite(STDERR, "неизвестный флаг: --$imya\n");
                fwrite(STDERR, '  понимаю: ' . implode(', ', array_map(
                    static fn($k) => "--$k=…",
                    array_values(array_unique(array_merge($znaem, $flagi)))
                )) . "\n");
                exit(1);
            }
            $opts[$klyuch] = $sZnach ? $znach : '1';
        }
        return [$opts, $poz];
    }

    /** Карта «любое написание → каноническое имя». */
    private static function karta(array $znaem, array $flagi): array
    {
        $karta = [];
        foreach (array_merge($znaem, $flagi) as $k) {
            $karta[mb_strtolower($k)] = $k;
            foreach (self::SINONIMY[$k] ?? [] as $s) { $karta[mb_strtolower($s)] = $k; }
            // Обратная сторона: инструмент объявил латинское имя, а позвали кириллицей.
            foreach (self::SINONIMY as $kanon => $spisok) {
                if (in_array($k, $spisok, true)) {
                    $karta[mb_strtolower($kanon)] = $k;
                    foreach ($spisok as $s) { $karta[mb_strtolower($s)] = $k; }
                }
            }
        }
        return $karta;
    }

    private static function normalizovat(string $imya, array $karta): ?string
    {
        return $karta[mb_strtolower($imya)] ?? null;
    }
}
