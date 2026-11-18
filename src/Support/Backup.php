<?php

declare(strict_types=1);

namespace YandexSites\Support;

use RuntimeException;
use YandexSites\Dorgen\OwnBases;
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

    /** То же человеческим языком — состояние работы (см. stateMarkdown()); лежит и в архиве, и рядом с ним. */
    public const STATE = 'backup.md';

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
    public static function create(string $projectDir, string $zipFile, bool $withPages = false, bool $withSecrets = true, string $version = '', string $versionDate = ''): array
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
            // Состояние работы — рядом с описанием: числа, по которым видно, что именно перенеслось.
            $state = $tmp . '/' . self::STATE;
            $text = self::stateMarkdown($projectDir, $plan, $version, $versionDate);
            if (@file_put_contents($state, $text) !== false) {
                $files[self::STATE] = $state;
                $plan['state_text'] = $text;
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
                    if (!in_array($entry, [self::MANIFEST, self::STATE], true) && !str_ends_with($entry, '/')) {
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

    /**
     * СОСТОЯНИЕ РАБОТЫ одним markdown-файлом — «а md для клауда?». Код лежит в git вместе с CLAUDE.md
     * и README.md, их новая сессия Claude читает сама; чего она НЕ видит — это данные: сколько доменов
     * в базе, сколько сборов в истории, где остановилась очередь запросов, что лежит на диске. Файл
     * кладётся рядом с архивом и внутрь него, и его можно переслать: внутри только числа и даты,
     * ни ключей, ни прокси, ни адресов сайтов.
     *
     * @param array<string, mixed>|null $plan готовый plan(), если он уже посчитан (чтобы не обходить диск дважды)
     */
    public static function stateMarkdown(string $projectDir, ?array $plan = null, string $version = '', string $versionDate = ''): string
    {
        $dir = rtrim($projectDir, '/\\');
        $runs = $dir . '/runs';
        $plan ??= self::plan($dir);
        $json = static function (string $file): array {
            $data = @json_decode((string) @file_get_contents($file), true);

            return is_array($data) ? $data : [];
        };
        $rows = [];
        $row = static function (string $what, string $value, string $where = '') use (&$rows): void {
            $rows[] = '| ' . $what . ' | ' . $value . ' | ' . $where . ' |';
        };

        $base = is_file($runs . '/domains-base.txt') ? new DomainLedger($runs . '/domains-base.txt') : null;
        $row('База пересечений доменов', $base !== null ? self::word($base->count(), 'домен', 'домена', 'доменов') : 'нет', '`runs/domains-base.txt`');

        $history = CollectHistory::load($runs);
        $last = $history[0] ?? null;
        $row(
            'История сборов',
            $history === [] ? 'нет' : self::word(count($history), 'запись', 'записи', 'записей') . ', последняя ' . self::day((string) ($last['date'] ?? '')) . ' — отобрано ' . self::word((int) ($last['sites'] ?? 0), 'сайт', 'сайта', 'сайтов'),
            '`runs/history.json`',
        );

        $snaps = SerpHistory::snapshots($runs);
        $row(
            'Снимки выдачи (разбор по брендам)',
            $snaps === [] ? 'нет' : self::word(count($snaps), 'снимок', 'снимка', 'снимков') . ', последний ' . self::day((string) ($snaps[0]['at'] ?? '')) . ' — ' . self::word((int) ($snaps[0]['brands'] ?? 0), 'бренд', 'бренда', 'брендов') . ', топ-' . (int) ($snaps[0]['top'] ?? 0),
            '`runs/serp-history.json`',
        );

        $bases = $json($runs . '/' . OwnBases::FILE);
        $row(
            'Наши базы из системы запусков',
            $bases === [] ? 'не выгружались' : self::word(count((array) ($bases['bases'] ?? [])), 'база', 'базы', 'баз') . ', выгружено по ' . ((string) ($bases['date_to'] ?? '—')),
            '`runs/' . OwnBases::FILE . '`',
        );

        $sites = $json($runs . '/current/sites.json');
        $row('Таблица текущего прогона', $sites === [] ? 'пусто' : self::word(count((array) ($sites['sites'] ?? [])), 'сайт', 'сайта', 'сайтов'), '`runs/current/sites.json`');

        $results = $runs . '/current/results.csv';
        $row('Строки выдачи последнего сбора', is_file($results) ? self::size((int) filesize($results)) : 'нет', '`runs/current/results.csv`');

        $queue = $json($runs . '/current/' . QueryQueue::FILE);
        if ($queue !== []) {
            $sum = QueryQueue::summary(['queries' => (array) ($queue['queries'] ?? []), 'done' => (int) ($queue['done'] ?? 0)]);
            $row('Очередь запросов', 'пройдено ' . $sum['done'] . ' из ' . $sum['total'] . ($sum['left'] > 0 ? ' (осталось ' . $sum['left'] . ' — кнопка «Продолжить сбор»)' : ''), '`runs/current/queue.json`');
        }

        $pages = count(Archive::listFiles($runs . '/current/pages'));
        $content = count(Archive::listFiles($runs . '/current/content'));
        $row('Скачанные страницы', $pages > 0 ? self::files($pages) : 'нет', '`runs/current/pages`');
        $row('Очищенные статьи', $content > 0 ? self::files($content) : 'нет', '`runs/current/content`');

        $secrets = array_keys((array) $plan['secrets']);
        $heavy = (array) $plan['pages'];

        return implode("\n", [
            '# Состояние yandex-sites — ' . date('d.m.Y'),
            '',
            'Код проекта лежит в git вместе с `CLAUDE.md` и `README.md` — новая сессия Claude читает их сама,'
                . ' пересказывать их не нужно. Здесь только то, чего в git НЕТ: данные этой машины.'
                . ($version !== '' ? ' Версия кода: **' . $version . '**' . ($versionDate !== '' ? ' от ' . self::day($versionDate) : '') . '.' : ''),
            '',
            '## Что в бекапе',
            '',
            '- ' . self::files((int) $plan['count']) . ', ' . self::size((int) $plan['bytes'])
                . ((bool) $plan['with_pages'] ? ' — со скачанными страницами' : ' — без скачанных страниц и контента'
                    . ((int) $heavy['files'] > 0 ? ' (на диске их ' . self::files((int) $heavy['files']) . ', ' . self::size((int) $heavy['bytes']) . ' — кнопка «Со страницами» или `--all`)' : '')),
            '- ключи и пароли: ' . ($secrets === []
                ? 'в архив не вошли (`--no-secrets`) — на новом ПК их придётся вписать заново'
                : implode(', ', array_map(static fn (string $f): string => '`' . $f . '`', $secrets)) . ' — **внутри архива**, не выкладывайте его в общие папки'),
            '- в ЭТОМ файле ключей, паролей и адресов сайтов нет — его можно переслать как есть',
            '',
            '## Данные на этой машине',
            '',
            '| Что | Сколько | Где |',
            '|---|---|---|',
            implode("\n", $rows),
            '',
            '## Развернуть на другом ПК',
            '',
            '```bash',
            'git clone https://github.com/alexnefera-dot/cladue.git && cd cladue',
            'php bin/setup.php',
            'php bin/backup.php --restore=/путь/к/' . self::fileName((bool) $plan['with_pages'], (bool) $plan['with_secrets']),
            'php bin/panel.php',
            '```',
            '',
            'Файлы, которые уже на месте, не перезаписываются: если такой есть хоть один, не распакуется'
                . ' ничего и команда их назовёт — перезапись по `--force`. Из архива берутся только корневые'
                . ' настройки и `runs/`, пути наружу папки проекта игнорируются.',
            '',
        ]);
    }

    /** Дата из ISO-строки в привычном виде (18.11.2026); пустая строка — прочерк. */
    private static function day(string $iso): string
    {
        $ts = $iso !== '' ? strtotime($iso) : false;

        return $ts === false ? '—' : date('d.m.Y', $ts);
    }

    /** «1 файл» / «3 файла» / «11 файлов» — число со склонением, чтобы вывод не выглядел черновиком. */
    public static function files(int $n): string
    {
        return self::word($n, 'файл', 'файла', 'файлов');
    }

    /** Число с нужной формой слова и пробелами в тысячах: «8 018 доменов», «1 запись», «3 базы». */
    public static function word(int $n, string $one, string $few, string $many): string
    {
        $last = $n % 10;
        $tens = $n % 100;
        if ($tens >= 11 && $tens <= 14) {
            $word = $many;
        } elseif ($last === 1) {
            $word = $one;
        } elseif ($last >= 2 && $last <= 4) {
            $word = $few;
        } else {
            $word = $many;
        }

        return number_format($n, 0, ',', ' ') . ' ' . $word;
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
        if ($rel === '' || $rel === self::MANIFEST || $rel === self::STATE || str_ends_with($rel, '/')) {
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
