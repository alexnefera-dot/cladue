<?php

declare(strict_types=1);

namespace YandexSites\Support;

use RuntimeException;
use ZipArchive;

/**
 * Бекап рабочих данных — «перенести на другой ПК и в облако». Код в бекап НЕ идёт: он лежит в git и
 * ставится заново (git clone или setup.php), а вот всё, чего в git нет, живёт только на машине
 * пользователя и теряется вместе с ней. В архив поэтому попадает ровно то, что перечислено в
 * .gitignore и при этом является ДАННЫМИ:
 *   • config.php, .env, proxies.txt, queries.txt, brands.txt, brand-pairs.txt — настройки и ключи;
 *   • вся папка runs/ — база пересечений доменов, история сборов, снимки выдачи, список наших баз
 *     из системы запусков, настройки панели, таблица сайтов и results.csv текущего прогона.
 * НЕ попадает: cache/ (ответы выдачи, перекачиваются и живут 7 дней), out/ (вывод CLI), логи,
 * сами zip-архивы, pid и флаг stop (чужой pid и остановка на новой машине только мешают), а по
 * умолчанию ещё и тяжёлые папки прогона — скачанные страницы, очищенный контент и превью
 * (их объём — гигабайты, они восстанавливаются выгрузкой; нужны — флаг --all).
 *
 * ВНИМАНИЕ про секреты: .env (ключи XMLStock и системы запусков), config.php и proxies.txt (пароли
 * прокси) по умолчанию В АРХИВЕ — иначе на новом ПК собирать нечем. Поэтому create() всегда
 * возвращает их списком, чтобы вызывающий код сказал об этом вслух перед отправкой архива в облако,
 * а $withSecrets = false делает архив, который можно передавать кому угодно.
 */
final class Backup
{
    /** Описание бекапа внутри архива: версия, дата, что включено. */
    public const MANIFEST = 'backup.json';

    /** Файлы в корне проекта, которых нет в git: без них установка — пустая. */
    public const ROOT_FILES = ['config.php', '.env', 'proxies.txt', 'queries.txt', 'brands.txt', 'brand-pairs.txt'];

    /** Ключи и пароли. В архиве они нужны, но называем их отдельно и всегда. */
    public const SECRET_FILES = ['.env', 'config.php', 'proxies.txt'];

    /** Тяжёлые папки прогона (внутри runs/): страницы, статьи, превью, убранные сайты. */
    public const HEAVY_DIRS = ['current/pages', 'current/content', 'current/preview', 'current/removed'];

    /** Служебные файлы, которые на другой машине только мешают: чужой pid, флаг остановки, ход выгрузки. */
    public const SKIP_NAMES = ['pid', 'stop', 'dorgen-progress.json'];

    /**
     * Настройки панели, а в них — список прокси С ПАРОЛЯМИ (та же причина, по которой
     * settingsForReport() вычищает его из sites.json). В архиве «без ключей» эти файлы нужны, но
     * список прокси из них вырезается: ключ `proxies` сверху и внутри `settings`.
     */
    public const MASKED_FILES = ['runs/current/settings.json', 'runs/current/status.json'];

    /**
     * Что попадёт в архив, без его создания: набор файлов, объём и то, что осталось за бортом.
     *
     * @return array{files: array<string, string>, count: int, bytes: int, secrets: array<string, int>,
     *     pages: array{files: int, bytes: int}, with_pages: bool, with_secrets: bool, masked: list<string>,
     *     skipped: array<string, array{files: int, bytes: int}>}
     */
    public static function plan(string $projectDir, bool $withPages = false, bool $withSecrets = true): array
    {
        $dir = rtrim($projectDir, '/\\');
        $files = [];
        $bytes = 0;
        $secrets = [];
        $skipped = [];
        $pages = ['files' => 0, 'bytes' => 0];
        $add = static function (string $entry, string $abs) use (&$files, &$bytes): void {
            $files[$entry] = $abs;
            $bytes += (int) filesize($abs);
        };
        $skip = static function (string $bucket, string $abs) use (&$skipped): void {
            $skipped[$bucket] ??= ['files' => 0, 'bytes' => 0];
            $skipped[$bucket]['files']++;
            $skipped[$bucket]['bytes'] += (int) filesize($abs);
        };

        foreach (self::ROOT_FILES as $name) {
            $abs = $dir . '/' . $name;
            if (!is_file($abs)) {
                continue;
            }
            $secret = in_array($name, self::SECRET_FILES, true);
            if ($secret && !$withSecrets) {
                $skip('secrets', $abs);
                continue;
            }
            $add($name, $abs);
            if ($secret) {
                $secrets[$name] = (int) filesize($abs);
            }
        }

        foreach (Archive::listFiles($dir . '/runs') as $rel => $abs) {
            $heavy = self::isHeavy($rel);
            if ($heavy) {
                $pages['files']++;
                $pages['bytes'] += (int) filesize($abs);
            }
            if (in_array(basename($rel), self::SKIP_NAMES, true)) {
                continue; // pid/stop/прогресс — в бекапе от них только вред
            }
            if (self::isHidden($rel)) {
                continue; // .DS_Store и временные папки самого архиватора
            }
            $ext = strtolower(pathinfo($rel, PATHINFO_EXTENSION));
            if ($ext === 'log') {
                $skip('logs', $abs);
                continue;
            }
            if ($ext === 'zip') {
                continue; // архивы собираются заново, иначе бекап кладёт в себя предыдущий бекап
            }
            if ($heavy && !$withPages) {
                $skip('pages', $abs);
                continue;
            }
            $add('runs/' . $rel, $abs);
        }

        foreach (['cache', 'out'] as $name) {
            foreach (Archive::listFiles($dir . '/' . $name) as $abs) {
                $skip($name, $abs);
            }
        }

        // Без ключей список прокси вырезается на лету при упаковке (см. create()).
        $masked = $withSecrets ? [] : array_values(array_intersect(self::MASKED_FILES, array_keys($files)));

        return ['files' => $files, 'count' => count($files), 'bytes' => $bytes, 'secrets' => $secrets,
            'pages' => $pages, 'with_pages' => $withPages, 'with_secrets' => $withSecrets, 'masked' => $masked,
            'skipped' => $skipped];
    }

    /**
     * Создаёт архив и возвращает plan() плюс `zip`/`zip_bytes`.
     *
     * @throws RuntimeException бекапить нечего или архив создать нечем
     */
    public static function create(string $projectDir, string $zipFile, bool $withPages = false, bool $withSecrets = true, string $version = ''): array
    {
        $plan = self::plan($projectDir, $withPages, $withSecrets);
        if ($plan['files'] === []) {
            throw new RuntimeException('Бекапить нечего: ни настроек, ни папки runs — проект ещё не настроен');
        }
        @mkdir(dirname($zipFile), 0777, true);
        // Манифест и копии без прокси пишем во временную папку: Archive::zipFiles() берёт файлы с диска.
        $tmp = dirname($zipFile) . '/.backup-' . bin2hex(random_bytes(4));
        @mkdir($tmp, 0777, true);
        $manifest = $tmp . '/backup.json';
        $ok = @file_put_contents($manifest, (string) json_encode([
            'version' => $version,
            'created' => date('c'),
            'files' => $plan['count'],
            'bytes' => $plan['bytes'],
            'with_pages' => $withPages,
            'with_secrets' => $withSecrets,
        ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
        try {
            $files = $plan['files'];
            if ($ok !== false) {
                $files[self::MANIFEST] = $manifest;
            }
            foreach ($plan['masked'] as $i => $entry) {
                $copy = self::withoutProxies((string) $files[$entry], $tmp . '/masked-' . $i . '.json');
                if ($copy === null) {
                    unset($files[$entry]); // не разобрали — в архив «без ключей» не кладём вообще
                    continue;
                }
                $files[$entry] = $copy;
            }
            Archive::zipFiles($files, $zipFile);
        } finally {
            self::rmTree($tmp);
        }
        $plan['zip'] = $zipFile;
        $plan['zip_bytes'] = (int) filesize($zipFile);

        return $plan;
    }

    /**
     * Распаковывает бекап в папку проекта. Берёт ТОЛЬКО свои файлы (корневые из ROOT_FILES и всё
     * внутри runs/) — архив приходит из облака, и подменить им код проекта нельзя; пути с «..»,
     * абсолютные и с диском отбрасываются. Без $force не перезаписывает ни одного файла: если
     * что-то уже на месте, не распаковывается НИЧЕГО (половина восстановленного состояния хуже,
     * чем ничего), и список таких файлов возвращается в `kept`.
     *
     * @return array{written: array<string, int>, kept: list<string>, rejected: list<string>, overwritten: int}
     * @throws RuntimeException файла нет, это не zip или читать его нечем
     */
    public static function restore(string $zipFile, string $projectDir, bool $force = false): array
    {
        if (!is_file($zipFile)) {
            throw new RuntimeException('Файл бекапа не найден: ' . $zipFile);
        }
        if (!Archive::isZip($zipFile)) {
            throw new RuntimeException('Это не zip-архив: ' . $zipFile);
        }
        $dir = rtrim($projectDir, '/\\');
        [$entries, $read, $cleanup] = self::open($zipFile);
        try {
            $take = [];
            $rejected = [];
            $kept = [];
            foreach ($entries as $entry) {
                $rel = self::entryTarget($entry);
                if ($rel === null) {
                    if ($entry !== self::MANIFEST && !str_ends_with($entry, '/')) {
                        $rejected[] = $entry;
                    }
                    continue;
                }
                $take[$rel] = $entry;
                if (is_file($dir . '/' . $rel)) {
                    $kept[] = $rel;
                }
            }
            if ($take === []) {
                return ['written' => [], 'kept' => [], 'rejected' => $rejected, 'overwritten' => 0];
            }
            if ($kept !== [] && !$force) {
                sort($kept);

                return ['written' => [], 'kept' => $kept, 'rejected' => $rejected, 'overwritten' => 0];
            }
            $written = [];
            foreach ($take as $rel => $entry) {
                $target = $dir . '/' . $rel;
                @mkdir(dirname($target), 0777, true);
                $bytes = $read($entry, $target);
                if ($bytes === null) {
                    $rejected[] = $entry;
                    continue;
                }
                // Ключи и пароли — только владельцу: бекап приходит из облака, права в архиве не хранятся.
                if (in_array($rel, self::SECRET_FILES, true)) {
                    @chmod($target, 0600);
                }
                $written[$rel] = $bytes;
            }
            ksort($written);
            sort($kept);

            return ['written' => $written, 'kept' => $kept, 'rejected' => $rejected, 'overwritten' => count($kept)];
        } finally {
            $cleanup();
        }
    }

    /**
     * Копия json-файла настроек без списка прокси (ключ `proxies` сверху и внутри `settings`).
     * null — файл не разобрался: в архив «без ключей» он тогда не попадает совсем.
     */
    private static function withoutProxies(string $file, string $target): ?string
    {
        $raw = @file_get_contents($file);
        if ($raw === false) {
            return null;
        }
        $data = json_decode($raw, true);
        if (!is_array($data)) {
            return null;
        }
        unset($data['proxies']);
        if (isset($data['settings']) && is_array($data['settings'])) {
            unset($data['settings']['proxies']);
        }
        $json = json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        if ($json === false || @file_put_contents($target, $json) === false) {
            return null;
        }

        return $target;
    }

    /** Человекочитаемый объём: «812 КБ», «4,2 МБ». */
    public static function size(int $bytes): string
    {
        if ($bytes < 1024) {
            return $bytes . ' Б';
        }
        foreach ([['ГБ', 1024 ** 3], ['МБ', 1024 ** 2], ['КБ', 1024]] as [$unit, $step]) {
            if ($bytes >= $step) {
                $value = $bytes / $step;

                return str_replace('.', ',', (string) round($value, $value < 10 ? 1 : 0)) . ' ' . $unit;
            }
        }

        return $bytes . ' Б';
    }

    /** «1 файл» / «3 файла» / «11 файлов» — число со склонением, чтобы вывод не выглядел черновиком. */
    public static function files(int $n): string
    {
        $last = $n % 10;
        $tens = $n % 100;
        if ($tens >= 11 && $tens <= 14) {
            $word = 'файлов';
        } elseif ($last === 1) {
            $word = 'файл';
        } elseif ($last >= 2 && $last <= 4) {
            $word = 'файла';
        } else {
            $word = 'файлов';
        }

        return $n . ' ' . $word;
    }

    /** Имя файла бекапа по дате: backup-2026-11-18.zip, с пометкой, если страницы внутри. */
    public static function fileName(bool $withPages = false, bool $withSecrets = true): string
    {
        return 'backup' . ($withPages ? '-full' : '') . ($withSecrets ? '' : '-bez-kluchei') . '-' . date('Y-m-d') . '.zip';
    }

    /** Рекурсивно удаляет временную папку, в которую распаковался архив на запасном пути. */
    private static function rmTree(string $dir): void
    {
        if (!is_dir($dir)) {
            return;
        }
        $it = new \RecursiveIteratorIterator(
            new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS),
            \RecursiveIteratorIterator::CHILD_FIRST,
        );
        foreach ($it as $item) {
            $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
        }
        @rmdir($dir);
    }

    /** В пути есть скрытая часть (.DS_Store, временная папка архиватора .backup-…)? */
    private static function isHidden(string $rel): bool
    {
        foreach (explode('/', $rel) as $part) {
            if (str_starts_with($part, '.')) {
                return true;
            }
        }

        return false;
    }

    /** Путь внутри runs/ ведёт в тяжёлую папку прогона (страницы, контент, превью, убранные)? */
    private static function isHeavy(string $rel): bool
    {
        foreach (self::HEAVY_DIRS as $heavy) {
            if (str_starts_with($rel, $heavy . '/')) {
                return true;
            }
        }

        return false;
    }

    /**
     * Путь из архива → путь внутри проекта, либо null, если такой файл восстанавливать нельзя.
     * Пускаем только корневые файлы из ROOT_FILES и содержимое runs/ — код проекта бекапом не трогаем.
     */
    private static function entryTarget(string $entry): ?string
    {
        $rel = str_replace('\\', '/', trim($entry));
        if ($rel === '' || $rel === self::MANIFEST || str_ends_with($rel, '/')) {
            return null;
        }
        if (str_contains($rel, "\0") || str_starts_with($rel, '/') || preg_match('~^[A-Za-z]:~', $rel) === 1) {
            return null;
        }
        // «./runs/…» и двойные слэши — тоже наш путь, а «..» не бывает нашим никогда.
        $parts = array_values(array_filter(explode('/', $rel), static fn (string $p): bool => $p !== '' && $p !== '.'));
        if ($parts === [] || in_array('..', $parts, true) || in_array(end($parts), self::SKIP_NAMES, true)) {
            return null;
        }
        $rel = implode('/', $parts);
        if (in_array($rel, self::ROOT_FILES, true)) {
            return $rel; // .env начинается с точки, поэтому список проверяем ДО правила о скрытых файлах
        }
        if (self::isHidden($rel)) {
            return null;
        }

        return ($parts[0] === 'runs' && count($parts) > 1) ? $rel : null;
    }

    /**
     * Открывает архив на чтение: список путей, читалка одного файла и уборка.
     * Если расширения zip нет (сборки для Windows), распаковываем системным tar во временную папку —
     * bsdtar читает zip, тем же запасным путём Archive пользуется при создании архива.
     *
     * @return array{0: list<string>, 1: callable(string, string): ?int, 2: callable(): void}
     */
    private static function open(string $zipFile): array
    {
        if (class_exists(ZipArchive::class)) {
            $zip = new ZipArchive();
            if ($zip->open($zipFile) !== true) {
                throw new RuntimeException('Не удалось открыть архив: ' . $zipFile);
            }
            $names = [];
            for ($i = 0; $i < $zip->numFiles; $i++) {
                $names[] = (string) $zip->getNameIndex($i);
            }

            return [
                $names,
                // Переписываем потоком: results.csv большого сбора в память целиком не влезет.
                static function (string $entry, string $target) use ($zip): ?int {
                    $in = $zip->getStream($entry);
                    if (!is_resource($in)) {
                        return null;
                    }
                    $out = @fopen($target, 'wb');
                    if (!is_resource($out)) {
                        fclose($in);

                        throw new RuntimeException('Не удалось записать файл: ' . $target);
                    }
                    $bytes = stream_copy_to_stream($in, $out);
                    fclose($in);
                    fclose($out);

                    return $bytes === false ? null : $bytes;
                },
                static function () use ($zip): void {
                    $zip->close();
                },
            ];
        }
        $tmp = sys_get_temp_dir() . '/ys-restore-' . bin2hex(random_bytes(4));
        @mkdir($tmp, 0777, true);
        $cleanup = static function () use ($tmp): void {
            self::rmTree($tmp);
        };
        $code = 1;
        @exec(sprintf('tar -xf %s -C %s 2>&1', escapeshellarg($zipFile), escapeshellarg($tmp)), $out, $code);
        if ($code !== 0) {
            $cleanup();

            throw new RuntimeException('Распаковать архив нечем: в PHP нет расширения zip, а системный tar не справился. Включите extension=zip в php.ini');
        }
        $found = Archive::listFiles($tmp);

        return [
            array_keys($found),
            static function (string $entry, string $target) use ($found): ?int {
                $abs = $found[$entry] ?? null;
                if ($abs === null || !@copy($abs, $target)) {
                    return null;
                }

                return (int) filesize($target);
            },
            $cleanup,
        ];
    }
}
