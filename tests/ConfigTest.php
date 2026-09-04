<?php

declare(strict_types=1);

namespace Tests;

use YandexSites\Config;
use YandexSites\Filter\DefaultExclusions;
use YandexSites\Live\UserAgents;

final class ConfigTest
{
    public function testDefaultsAndMerge(): void
    {
        $config = new Config(['search' => ['pages' => 3], 'filters' => ['exclude_domains' => ['only.ru']]]);
        Assert::same(3, $config->get('search.pages'));
        Assert::same(50, $config->get('search.groups_on_page'), 'остальные значения раздела сохраняются');
        Assert::same(['only.ru'], $config->get('filters.exclude_domains'), 'списки заменяются целиком');
        Assert::same('host', $config->get('filters.unique_by'));
        Assert::same(null, $config->get('nope.nope'));
        Assert::same('x', $config->get('nope.nope', 'x'));
        Assert::true(count(DefaultExclusions::LIST) > 50);
        Assert::same(DefaultExclusions::LIST, (new Config())->get('filters.exclude_domains'));

        $defaults = new Config();
        Assert::same(UserAgents::YANDEX_BOT, $defaults->get('site_check.user_agent'), 'проверка сайтов — как робот Яндекса');
        Assert::same(UserAgents::YANDEX_BOT, $defaults->get('visit.user_agents')[0], 'первый визит — как робот Яндекса');
        Assert::same(UserAgents::BROWSERS[0], $defaults->get('visit.user_agents')[1]);
        Assert::same(UserAgents::BROWSERS, $defaults->get('live.user_agents'), 'к выдаче — как браузер');
        Assert::true(UserAgents::isBot(UserAgents::YANDEX_BOT));
        Assert::false(UserAgents::isBot(UserAgents::BROWSERS[0]));
    }

    public function testOverrides(): void
    {
        $config = (new Config())->withOverrides(['search.pages' => 2, 'output.dir' => '/tmp/x', 'new.key' => 1]);
        Assert::same(2, $config->get('search.pages'));
        Assert::same('/tmp/x', $config->get('output.dir'));
        Assert::same(1, $config->get('new.key'));
        Assert::same(1, (new Config())->get('search.pages'), 'исходный объект не меняется');
    }

    public function testValidation(): void
    {
        $config = new Config(['api' => ['folder_id' => '', 'api_key' => '', 'iam_token' => '']]);
        $errors = $config->validate();
        Assert::same(2, count($errors));
        Assert::contains('folder_id', $errors[0]);
        Assert::contains('api_key', $errors[1]);
        Assert::same([], $config->validate(false), 'без проверки доступа ошибок нет');

        $config = new Config([
            'api' => ['folder_id' => 'f', 'api_key' => 'k', 'version' => 'soap'],
            'search' => ['groups_on_page' => 500, 'family_mode' => 'x', 'pages' => 0],
            'filters' => ['unique_by' => 'url', 'exclude_domains' => 'a.ru'],
        ]);
        $errors = implode("\n", $config->validate());
        Assert::contains('api.version', $errors);
        Assert::contains('search.groups_on_page', $errors);
        Assert::contains('search.family_mode', $errors);
        Assert::contains('search.pages', $errors);
        Assert::contains('filters.unique_by', $errors);
        Assert::contains('filters.exclude_domains', $errors);

        $badScope = new Config(['api' => ['folder_id' => 'f', 'api_key' => 'k'], 'filters' => ['domain_scope' => 'weird']]);
        Assert::contains('filters.domain_scope', implode("\n", $badScope->validate()));
        Assert::same('all', (new Config())->get('filters.domain_scope'));

        $ok = new Config(['api' => ['folder_id' => 'f', 'iam_token' => 't']]);
        Assert::same([], $ok->validate());
    }

    public function testFromFile(): void
    {
        $dir = sys_get_temp_dir() . '/yandex-sites-test-' . uniqid();
        mkdir($dir);
        file_put_contents($dir . '/config.php', '<?php return ["search" => ["region" => 2]];');
        Assert::same(2, Config::fromFile($dir . '/config.php')->get('search.region'));
        Assert::throws(\RuntimeException::class, static fn () => Config::fromFile($dir . '/missing.php'), 'не найден');
        file_put_contents($dir . '/bad.php', '<?php return "x";');
        Assert::throws(\RuntimeException::class, static fn () => Config::fromFile($dir . '/bad.php'), 'массив');
        Assert::same(213, Config::fromFile(null)->get('search.region'));
        array_map('unlink', glob($dir . '/*') ?: []);
        rmdir($dir);
    }

    public function testDotEnv(): void
    {
        $file = sys_get_temp_dir() . '/yandex-sites-test-' . uniqid() . '.env';
        putenv('YS_TEST_EXISTING=keep');
        file_put_contents($file, "# comment\nYS_TEST_A=hello\nYS_TEST_B=\"quoted value\"\nexport YS_TEST_C='single'\nYS_TEST_EXISTING=override\ninvalid line\n");
        Config::loadDotEnv($file);
        Assert::same('hello', getenv('YS_TEST_A'));
        Assert::same('quoted value', getenv('YS_TEST_B'));
        Assert::same('single', getenv('YS_TEST_C'));
        Assert::same('keep', getenv('YS_TEST_EXISTING'), 'уже заданные переменные не перекрываются');
        Config::loadDotEnv($file . '.missing');
        unlink($file);
    }
}
