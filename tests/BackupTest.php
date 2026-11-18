<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Support\Backup;

final class BackupTest
{
    /** @var list<string> */
    private static array $dirs = [];

    public function testPacksWhatIsNotInGitAndSkipsWhatIsRestorable(): void
    {
        $dir = $this->project();
        $plan = Backup::plan($dir);
        $entries = array_keys($plan['files']);
        sort($entries);
        Assert::same([
            '.env', 'config.php', 'proxies.txt', 'queries.txt',
            'runs/current/results.csv', 'runs/current/settings.json', 'runs/current/sites.json',
            'runs/current/status.json', 'runs/domains-base.txt', 'runs/history.json',
        ], $entries, 'настройки с ключами и состояние прогона — внутри; кэш, out, логи, pid, stop, архивы и скрытые файлы — нет');
        Assert::same(['config.php' => filesize($dir . '/config.php'), '.env' => filesize($dir . '/.env'), 'proxies.txt' => filesize($dir . '/proxies.txt')], $plan['secrets'], 'файлы с ключами названы по именам — о них надо предупредить');
        Assert::same(3, $plan['pages']['files'], 'страницы, статья и превью посчитаны, хотя в архив не пошли');
        Assert::same(3, $plan['skipped']['pages']['files'] ?? 0);
        Assert::same(1, $plan['skipped']['cache']['files'] ?? 0, 'кэш выдачи перекачивается сам');
        Assert::same(1, $plan['skipped']['logs']['files'] ?? 0);
        Assert::same(1, $plan['skipped']['out']['files'] ?? 0);

        // --all: тяжёлые папки прогона тоже внутри, и «не включено» про них больше не пишется.
        $full = Backup::plan($dir, true);
        Assert::true(isset($full['files']['runs/current/pages/9-стр/kush.net.ru/main.html']), 'скачанная страница в полном бекапе');
        Assert::true(isset($full['files']['runs/current/content/9-стр/kush.net.ru/main.html']), 'очищенная статья в полном бекапе');
        Assert::same(0, $full['skipped']['pages']['files'] ?? 0);

        if (!class_exists('ZipArchive')) {
            Assert::skip('нет расширения zip');
        }
        $made = Backup::create($dir, $dir . '/runs/backup.zip', false, true, '9.9.9');
        Assert::true(Backup::size($made['zip_bytes']) !== '', 'объём архива человекочитаемый');
        $zip = new \ZipArchive();
        Assert::true($zip->open($dir . '/runs/backup.zip') === true);
        $inside = [];
        for ($i = 0; $i < $zip->numFiles; $i++) {
            $inside[] = (string) $zip->getNameIndex($i);
        }
        Assert::true(in_array(Backup::MANIFEST, $inside, true), 'внутри есть описание бекапа');
        $manifest = json_decode((string) $zip->getFromName(Backup::MANIFEST), true);
        Assert::same('9.9.9', $manifest['version'] ?? '', 'версия, которой сделан бекап');
        Assert::false($manifest['with_pages'] ?? true, 'в описании честно сказано, что страниц внутри нет');
        Assert::same('XMLSTOCK_KEY=secret123', trim((string) $zip->getFromName('.env')), 'ключи перенеслись как есть — иначе на новом ПК собирать нечем');
        $zip->close();
        // Архив лежит в runs/, но в следующий бекап он сам не попадает.
        Assert::false(isset(Backup::plan($dir)['files']['runs/backup.zip']), 'бекап не кладёт в себя предыдущий бекап');
    }

    public function testNoSecretsCopyCarriesNoKeysAndNoProxyPasswords(): void
    {
        if (!class_exists('ZipArchive')) {
            Assert::skip('нет расширения zip');
        }
        $dir = $this->project();
        $plan = Backup::plan($dir, false, false);
        Assert::false(isset($plan['files']['.env']), 'ключей в копии «для передачи» нет');
        Assert::false(isset($plan['files']['proxies.txt']));
        Assert::same(3, $plan['skipped']['secrets']['files'] ?? 0);
        Assert::same(['runs/current/settings.json', 'runs/current/status.json'], $plan['masked'], 'настройки панели держат список прокси — их чистим');

        Backup::create($dir, $dir . '/runs/share.zip', false, false);
        $zip = new \ZipArchive();
        Assert::true($zip->open($dir . '/runs/share.zip') === true);
        $leaks = [];
        for ($i = 0; $i < $zip->numFiles; $i++) {
            if (str_contains((string) $zip->getFromIndex($i), 'hunter2')) {
                $leaks[] = (string) $zip->getNameIndex($i);
            }
        }
        Assert::same([], $leaks, 'пароля прокси нет ни в одном файле архива');
        $settings = json_decode((string) $zip->getFromName('runs/current/settings.json'), true);
        Assert::same('вулкан', $settings['queries'] ?? '', 'остальные настройки панели сохранены');
        Assert::false(isset($settings['proxies']), 'список прокси вырезан');
        $status = json_decode((string) $zip->getFromName('runs/current/status.json'), true);
        Assert::false(isset($status['settings']['proxies']), 'в статусе прогона копия настроек тоже чистая');
        Assert::same('done', $status['state'] ?? '', 'сам статус не испорчен');
        $zip->close();
    }

    public function testRestoreNeverOverwritesSilently(): void
    {
        if (!class_exists('ZipArchive')) {
            Assert::skip('нет расширения zip');
        }
        $from = $this->project();
        Backup::create($from, $from . '/runs/backup.zip');
        $zipFile = $from . '/runs/backup.zip';

        // Чистая машина: разворачивается всё, ключи — только владельцу.
        $to = $this->emptyDir();
        $done = Backup::restore($zipFile, $to);
        Assert::same(10, count($done['written']), 'развёрнуто всё, что было в архиве');
        Assert::same([], $done['kept']);
        Assert::same('XMLSTOCK_KEY=secret123', trim((string) file_get_contents($to . '/.env')));
        Assert::same('kush.net.ru', trim((string) file_get_contents($to . '/runs/domains-base.txt')), 'база доменов на месте');
        if (DIRECTORY_SEPARATOR === '/') {
            Assert::same('0600', substr(sprintf('%o', (int) fileperms($to . '/.env')), -4), 'ключи читает только владелец');
        }

        // Повтор без --force не трогает НИ ОДНОГО файла: половина восстановленного состояния хуже, чем ничего.
        file_put_contents($to . '/runs/domains-base.txt', "svoy.ru\n");
        $again = Backup::restore($zipFile, $to);
        Assert::same([], $again['written'], 'без --force не записано ничего');
        Assert::same(10, count($again['kept']), 'и сказано, что именно уже на месте');
        Assert::same('svoy.ru', trim((string) file_get_contents($to . '/runs/domains-base.txt')), 'файл этой машины не перезаписан');

        $forced = Backup::restore($zipFile, $to, true);
        Assert::same(10, $forced['overwritten'], '--force перезаписывает, и сколько — видно');
        Assert::same('kush.net.ru', trim((string) file_get_contents($to . '/runs/domains-base.txt')));
    }

    public function testRestoreTakesOnlyItsOwnFilesAndNeverLeavesTheProject(): void
    {
        if (!class_exists('ZipArchive')) {
            Assert::skip('нет расширения zip');
        }
        // Архив приезжает из облака: подменить им код проекта или записать что-то вне папки нельзя.
        $dir = $this->emptyDir();
        $zipFile = $dir . '/evil.zip';
        $zip = new \ZipArchive();
        Assert::true($zip->open($zipFile, \ZipArchive::CREATE | \ZipArchive::OVERWRITE) === true);
        $zip->addFromString('runs/history.json', '{"records":[]}');
        $zip->addFromString('../escaped.txt', 'выше папки проекта');
        $zip->addFromString('runs/../../escaped2.txt', 'обходом через runs');
        $zip->addFromString('/etc/ys-passwd', 'абсолютный путь');
        $zip->addFromString('src/Runner.php', '<?php /* подмена кода */');
        $zip->addFromString('bin/panel.php', '<?php /* подмена панели */');
        $zip->addFromString('composer.json', '{}');
        $zip->addFromString('runs/current/pid', '999999');
        $zip->addFromString('./queries.txt', "вулкан\n");
        $zip->close();

        $to = $this->emptyDir();
        $result = Backup::restore($zipFile, $to);
        Assert::same(['queries.txt', 'runs/history.json'], array_keys($result['written']), 'взяли только настройки и runs/');
        Assert::same(7, count($result['rejected']), 'и назвали всё остальное: код, пути наружу и чужой pid');
        Assert::false(is_file($to . '/src/Runner.php'), 'код проекта бекапом не подменяется');
        Assert::false(is_file($to . '/bin/panel.php'));
        Assert::false(is_file($to . '/composer.json'));
        Assert::false(is_file($to . '/runs/current/pid'), 'чужой pid на новой машине не нужен');
        Assert::false(is_file(dirname($to) . '/escaped.txt'), 'выше папки проекта не записано ничего');
        Assert::false(is_file(dirname($to) . '/escaped2.txt'));
        Assert::false(is_file(dirname(dirname($to)) . '/escaped2.txt'));
        Assert::false(is_file('/etc/ys-passwd'));
    }

    public function testSizeAndCountReadLikeRussian(): void
    {
        Assert::same('900 Б', Backup::size(900));
        Assert::same('1,5 КБ', Backup::size(1536));
        Assert::same('4,2 МБ', Backup::size((int) (4.2 * 1024 ** 2)));
        Assert::same('1,4 ГБ', Backup::size((int) (1.4 * 1024 ** 3)));
        Assert::same('1 файл', Backup::files(1));
        Assert::same('3 файла', Backup::files(3));
        Assert::same('11 файлов', Backup::files(11));
        Assert::same('21 файл', Backup::files(21));
        Assert::same('backup-' . date('Y-m-d') . '.zip', Backup::fileName());
        Assert::contains('full', Backup::fileName(true), 'полный бекап видно по имени файла');
    }

    public static function tearDownClass(): void
    {
        foreach (self::$dirs as $dir) {
            if (!is_dir($dir)) {
                continue;
            }
            $it = new \RecursiveIteratorIterator(new \RecursiveDirectoryIterator($dir, \FilesystemIterator::SKIP_DOTS), \RecursiveIteratorIterator::CHILD_FIRST);
            foreach ($it as $item) {
                $item->isDir() ? @rmdir($item->getPathname()) : @unlink($item->getPathname());
            }
            @rmdir($dir);
        }
        self::$dirs = [];
    }

    /** Пустая папка «проекта» для разворачивания бекапа. */
    private function emptyDir(): string
    {
        $dir = sys_get_temp_dir() . '/yandex-sites-backup-' . uniqid();
        mkdir($dir . '/nested', 0777, true);
        self::$dirs[] = $dir;

        return $dir . '/nested';
    }

    /** Папка проекта «как у пользователя»: настройки с ключами, runs/ с состоянием, кэш и логи. */
    private function project(): string
    {
        $dir = sys_get_temp_dir() . '/yandex-sites-backup-' . uniqid();
        self::$dirs[] = $dir;
        mkdir($dir . '/runs/current/pages/9-стр/kush.net.ru', 0777, true);
        mkdir($dir . '/runs/current/content/9-стр/kush.net.ru', 0777, true);
        mkdir($dir . '/runs/current/preview/kush.net.ru', 0777, true);
        mkdir($dir . '/cache/live/aa', 0777, true);
        mkdir($dir . '/out/pages', 0777, true);
        file_put_contents($dir . '/config.php', "<?php return [];\n");
        file_put_contents($dir . '/.env', "XMLSTOCK_KEY=secret123\n");
        file_put_contents($dir . '/proxies.txt', "203.0.113.7:59100:user:hunter2\n");
        file_put_contents($dir . '/queries.txt', "вулкан казино\n");
        file_put_contents($dir . '/runs/domains-base.txt', "kush.net.ru\n");
        file_put_contents($dir . '/runs/history.json', '{"records":[{"id":"a"}]}');
        file_put_contents($dir . '/runs/current/sites.json', '{"sites":[]}');
        file_put_contents($dir . '/runs/current/results.csv', "host;query\nkush.net.ru;вулкан\n");
        file_put_contents($dir . '/runs/current/settings.json', '{"queries":"вулкан","proxies":"203.0.113.7:59100:user:hunter2"}');
        file_put_contents($dir . '/runs/current/status.json', '{"state":"done","settings":{"queries":"вулкан","proxies":"203.0.113.7:59100:user:hunter2"}}');
        // Всё, чего в бекапе быть не должно.
        file_put_contents($dir . '/runs/current/pid', '12345');
        file_put_contents($dir . '/runs/current/stop', '');
        file_put_contents($dir . '/runs/current/run.log', "строка журнала\n");
        file_put_contents($dir . '/runs/current/content.zip', 'PK');
        file_put_contents($dir . '/runs/dorgen-progress.json', '{"state":"running","pid":777}');
        file_put_contents($dir . '/runs/.DS_Store', 'macOS');
        mkdir($dir . '/runs/.backup-stale', 0777, true);
        file_put_contents($dir . '/runs/.backup-stale/backup.json', '{}'); // хвост от прерванной сборки архива
        file_put_contents($dir . '/runs/current/pages/9-стр/kush.net.ru/main.html', '<html>страница</html>');
        file_put_contents($dir . '/runs/current/content/9-стр/kush.net.ru/main.html', '<p>статья</p>');
        file_put_contents($dir . '/runs/current/preview/kush.net.ru/variant-1.png', 'PNG');
        file_put_contents($dir . '/cache/live/aa/resp.html', 'кэш');
        file_put_contents($dir . '/out/pages/x.html', 'старое');

        return $dir;
    }
}
