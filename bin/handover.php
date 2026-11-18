<?php

declare(strict_types=1);

/**
 * СБОРКА ПАКЕТА ДЛЯ ПЕРЕДАЧИ — «давай соберём без гит и без авторства».
 *
 * Делает из рабочей папки чистый архив с кодом: без `.git` (а значит, без истории коммитов с их
 * авторами и ссылками на сессии чата), без упоминаний Claude и без адреса чужого репозитория.
 * Данные и ключи сюда НЕ попадают вообще — они передаются отдельно бекапом (bin/backup.php),
 * и это сознательно разделено: код можно показать кому угодно, бекап — только исполнителю.
 *
 * Запуск:
 *   php bin/handover.php                      — runs/handover-ГГГГ-ММ-ДД.zip
 *   php bin/handover.php --out=/путь/my.zip   — другой файл
 *   php bin/handover.php --dir=/путь/папка    — ещё и оставить распакованную копию
 *   php bin/handover.php --list               — что войдёт и что будет заменено, без сборки
 *
 * Последний шаг — ПРОВЕРКА: во всех текстовых файлах ищутся «claude», «anthropic» и имя аккаунта.
 * Нашлось хоть одно — сборка падает со списком. Иначе «без авторства» было бы обещанием, а не фактом.
 */

use YandexSites\Cli\Application;
use YandexSites\Support\Archive;
use YandexSites\Support\Backup;

@ini_set('memory_limit', '1024M');

$root = dirname(__DIR__);
if (is_file($root . '/vendor/autoload.php')) {
    require $root . '/vendor/autoload.php';
} else {
    spl_autoload_register(static function (string $class) use ($root): void {
        if (str_starts_with($class, 'YandexSites\\')) {
            $path = $root . '/src/' . str_replace('\\', '/', substr($class, strlen('YandexSites\\'))) . '.php';
            if (is_file($path)) {
                require $path;
            }
        }
    });
}

/** Что входит в пакет: только код и примеры. Папки с данными и файлы с ключами не перечислены вовсе. */
const DIRS = ['bin', 'src', 'public', 'tools', 'tests'];
const FILES = [
    'README.md', 'composer.json', 'package.json', '.gitignore',
    'config.example.php', '.env.example', 'proxies.example.txt', 'queries.example.txt', 'brands.example.txt',
];
/**
 * Не входит в пакет: сам сборщик (он же и есть таблица того, что вычищается — в передаче ему не место)
 * и его тест.
 */
const EXCLUDE = ['bin/handover.php', 'tests/HandoverTest.php'];

/** Папка верхнего уровня внутри архива. */
const PACKAGE_DIR = 'yandex-sites';

/** Документация переезжает под нейтральным именем. */
const RENAME = ['CLAUDE.md' => 'DOCS.md'];
/** Слова, которых в пакете быть не должно (проверка в конце). */
const FORBIDDEN = ['claude', 'клауд', 'anthropic', 'alexnefera'];

/** Замены во ВСЕХ файлах: ссылка на документацию и на репозиторий. */
const GLOBAL_RULES = [
    'CLAUDE.md' => 'DOCS.md',
    'https://github.com/alexnefera-dot/cladue.git' => '<адрес вашего репозитория>',
    'alexnefera-dot/cladue' => 'yandex-sites',
    'alexnefera/yandex-sites' => 'local/yandex-sites',
];

/**
 * Точечные замены: файл => [что ищем => на что меняем]. Если строка не найдена — сборка падает:
 * значит, текст поменяли, а правило осталось старым, и упоминание уехало бы в пакет незамеченным.
 */
const FILE_RULES = [
    'bin/setup.php' => [
        "const UPDATE_BRANCH = 'claude/php-yandex-site-filter-v2q2lx';\nconst UPDATE_URL = 'https://github.com/yandex-sites/archive/refs/heads/' . UPDATE_BRANCH . '.zip';"
            => "// Автообновление в этой сборке не настроено: код приходит архивом. Чтобы включить, впишите\n"
            . "// сюда адрес zip-архива ветки своего репозитория (или зовите php bin/setup.php --update=URL).\nconst UPDATE_BRANCH = '';\nconst UPDATE_URL = '';",
    ],
    'DOCS.md' => [
        "# DOCS.md\n\nThis file provides guidance to Claude Code and other AI assistants working in this repository."
            => "# yandex-sites — справочник по проекту\n\nКак всё устроено и почему сделано именно так: решения, их причины и места, где они закреплены тестами.",
        "**Repository:** `yandex-sites`\n\n" => '',
        '- Branches: `claude/<description>-<session-id>` for AI-created branches, `feature/`, `fix/`, `chore/` otherwise.'
            => '- Branches: `feature/`, `fix/`, `chore/`.',
        '## AI Assistant Notes' => '## Заметки по реализации',
        '«дай бекап перенести на другой пк и клауд»' => '«дай бекап перенести на другой пк и в облако»',
        '«А MD ДЛЯ КЛАУДА?» — `stateMarkdown()` is the answer: the repo\'s own `DOCS.md`/`README.md` travel in'
            => '«А MD, ЧТОБ ПЕРЕДАТЬ?» — `stateMarkdown()` is the answer: the repo\'s own `DOCS.md`/`README.md` travel in',
        "  git and a new session reads them itself, so what a fresh Claude CANNOT see is the DATA — how many"
            => "  the repository and whoever picks the project up reads them, so what is NOT visible is the DATA — how many",
        "  Claude (.md)» button or `php bin/backup.php --state`." => "  проекта (.md)» button or `php bin/backup.php --state`.",
    ],
    'README.md' => [
        "```bash\ngit clone <адрес вашего репозитория>\ncd cladue\nphp bin/setup.php --proxy=http://host:port:user:pass\n```"
            => "```bash\n# распакуйте архив с кодом в папку проекта и зайдите в неё\ncd yandex-sites\nphp bin/setup.php --proxy=http://host:port:user:pass\n```",
        "```bash\ngit clone <адрес вашего репозитория>\ncd cladue\nphp bin/setup.php\nphp bin/backup.php --restore=/путь/к/backup-ГГГГ-ММ-ДД.zip\nphp bin/panel.php\n```"
            => "```bash\n# распакуйте архив с кодом и зайдите в папку проекта\ncd yandex-sites\nphp bin/setup.php\nphp bin/backup.php --restore=/путь/к/backup-ГГГГ-ММ-ДД.zip\nphp bin/panel.php\n```",
        '«Состояние для Claude (.md)» в панели. Он нужен, когда работу продолжает новая сессия Claude: код,'
            . "\n`DOCS.md` и `README.md` она читает из репозитория сама, а данных этой машины не видит — вот они\nчислами."
            => "«Состояние проекта (.md)» в панели. Он нужен тому, кто продолжает работу: код, `DOCS.md` и\n`README.md` лежат рядом, а данных этой машины в них нет — вот они числами.",
    ],
    'public/panel.html' => [
        'title="Короткий markdown: версия, что собрано, сколько в базе доменов и в истории, где остановилась очередь запросов. Ключей и адресов сайтов в нём нет — его можно переслать, в том числе новой сессии Claude: код и DOCS.md она читает из репозитория, а данные — отсюда. Этот же файл лежит внутри бекапа">Состояние для Claude (.md)</a>'
            => 'title="Короткий markdown: версия, что собрано, сколько в базе доменов и в истории, где остановилась очередь запросов. Ключей и адресов сайтов в нём нет — его можно переслать тому, кто продолжает работу. Этот же файл лежит внутри бекапа">Состояние проекта (.md)</a>',
    ],
    'bin/panel.php' => [
        '// «Состояние для Claude»: тот же markdown, что лежит внутри бекапа — что собрано,'
            => '// «Состояние проекта»: тот же markdown, что лежит внутри бекапа — что собрано,',
    ],
    'bin/backup.php' => [
        ' *   php bin/backup.php --state              — состояние работы в markdown (для новой сессии Claude)'
            => ' *   php bin/backup.php --state              — состояние работы в markdown (для того, кто продолжит)',
        "        . \"в том числе новой сессии Claude: код и DOCS.md она берёт из git, а данные — отсюда.\\n\","
            => "        . \"в том числе тому, кто продолжает работу: код и DOCS.md лежат рядом, а данные — отсюда.\\n\",",
    ],
    'src/Support/Backup.php' => [
        "     * СОСТОЯНИЕ РАБОТЫ одним markdown-файлом — «а md для клауда?». Код лежит в git вместе с DOCS.md\n     * и README.md, их новая сессия Claude читает сама; чего она НЕ видит — это данные: сколько доменов"
            => "     * СОСТОЯНИЕ РАБОТЫ одним markdown-файлом. Код лежит рядом вместе с DOCS.md и README.md,\n     * а чего в них НЕТ — это данные: сколько доменов",
        "            'Код проекта лежит в git вместе с `DOCS.md` и `README.md` — новая сессия Claude читает их сама,'\n                . ' пересказывать их не нужно. Здесь только то, чего в git НЕТ: данные этой машины.'"
            => "            'Код проекта лежит рядом вместе с `DOCS.md` и `README.md` — пересказывать их не нужно.'\n                . ' Здесь только то, чего в коде НЕТ: данные этой машины.'",
        "            'git clone <адрес вашего репозитория> && cd cladue',\n            'php bin/setup.php',"
            => "            '# распакуйте архив с кодом и зайдите в папку проекта',\n            'php bin/setup.php',",
    ],
    'tests/PanelTest.php' => [
        '// «Состояние для Claude»: тот же markdown отдельным файлом, без ключей и адресов сайтов.'
            => '// «Состояние проекта»: тот же markdown отдельным файлом, без ключей и адресов сайтов.',
    ],
];

/** Записка для исполнителя: что это за архив, чего в нём нет и с чего начинать. */
function handoverNote(string $version, string $date): string
{
    return <<<MD
    # Передача проекта yandex-sites

    Это полный код инструмента, версия **{$version}** от {$date}. Репозитория git внутри нет —
    это снимок кода, а не клон; заводите свой git, если он нужен.

    ## Чего здесь НЕТ

    - **Данных и ключей.** База собранных доменов, история сборов, снимки выдачи, список наших
      доменов из системы запусков, настройки панели и таблица сайтов приезжают **отдельным архивом**
      (`backup-ГГГГ-ММ-ДД.zip`), вместе с `.env`, `config.php` и `proxies.txt`. Без него инструмент
      запустится, но будет пустым и без доступов.
    - **Автообновления.** `php bin/setup.php --update` в этой сборке не настроен: новые версии
      приходят архивом. Адрес своего репозитория можно вписать в `bin/setup.php` (UPDATE_URL).

    ## С чего начать

    ```bash
    cd yandex-sites
    php bin/setup.php                                   # создаст config.php, .env, папки
    php bin/backup.php --restore=/путь/к/backup-ГГГГ-ММ-ДД.zip   # данные и ключи
    php bin/panel.php                                   # панель на http://127.0.0.1:8777
    ```

    Проверить, что всё на месте: `php tests/lint.php && php tests/run.php` — должно быть 0 провалов.

    ## Где что лежит

    - `README.md` — руководство: источники выдачи, правила отбора, визиты, очистка контента, панель.
    - `DOCS.md` — справочник по реализации: какое решение принято, почему и каким тестом закреплено.
      Читать перед любой правкой: половина решений там неочевидна, но обоснована.
    - `bin/` — точки входа (панель, фоновая задача, бекап, очистка контента, выгрузка наших доменов).
    - `src/` — код, `tests/` — свой маленький прогон тестов (без PHPUnit), `public/` — панель и разбор выдачи.

    Требуется PHP 8.1+ с curl/dom/json/libxml/mbstring; для скриншотов — Node.js 18+ и Playwright
    (`npm install playwright && npx playwright install chromium`).
    MD;
}

$args = [];
foreach (array_slice($argv, 1) as $arg) {
    if (preg_match('~^--([a-z\-]+)(?:=(.*))?$~', $arg, $m) === 1) {
        $args[$m[1]] = $m[2] ?? '1';
    }
}

if (isset($args['help'])) {
    fwrite(STDOUT, "php bin/handover.php [--out=файл.zip] [--dir=папка] [--list]\n");
    exit(0);
}

/** Собирает список файлов пакета: путь в пакете => файл на диске. */
$collect = static function (string $root): array {
    $out = [];
    foreach (FILES as $name) {
        if (is_file($root . '/' . $name)) {
            $out[RENAME[$name] ?? $name] = $root . '/' . $name;
        }
    }
    foreach (array_keys(RENAME) as $name) {
        if (is_file($root . '/' . $name)) {
            $out[RENAME[$name]] = $root . '/' . $name;
        }
    }
    foreach (DIRS as $dir) {
        foreach (Archive::listFiles($root . '/' . $dir) as $rel => $abs) {
            if (in_array($dir . '/' . $rel, EXCLUDE, true)) {
                continue;
            }
            $out[$dir . '/' . $rel] = $abs;
        }
    }
    ksort($out);

    return $out;
};

$files = $collect($root);
if ($files === []) {
    fwrite(STDERR, "Нечего собирать: не найден код проекта\n");
    exit(2);
}

if (isset($args['list'])) {
    fwrite(STDOUT, sprintf("В пакет войдёт %s:\n", Backup::files(count($files))));
    foreach (array_keys(RENAME) as $from) {
        fwrite(STDOUT, '  ' . $from . ' → ' . RENAME[$from] . "\n");
    }
    foreach (FILE_RULES as $file => $rules) {
        fwrite(STDOUT, '  ' . $file . ' — правок: ' . count($rules) . "\n");
    }
    fwrite(STDOUT, '  во всех файлах: ' . implode(', ', array_keys(GLOBAL_RULES)) . "\n");
    fwrite(STDOUT, "Данные и ключи в пакет не входят — они передаются бекапом (php bin/backup.php)\n");
    exit(0);
}

// Готовим копию во временной папке и правим её — рабочая папка не трогается.
$stage = isset($args['dir']) ? rtrim($args['dir'], '/\\') : sys_get_temp_dir() . '/ys-handover-' . bin2hex(random_bytes(4));
if (is_dir($stage) && Archive::listFiles($stage) !== []) {
    fwrite(STDERR, 'Папка не пуста: ' . $stage . "\n");
    exit(2);
}
@mkdir($stage, 0777, true);
$text = static fn (string $path): bool => in_array(strtolower(pathinfo($path, PATHINFO_EXTENSION)), ['php', 'md', 'html', 'js', 'json', 'txt', 'xml', 'csv', ''], true);
$copied = 0;
foreach ($files as $rel => $abs) {
    $target = $stage . '/' . $rel;
    @mkdir(dirname($target), 0777, true);
    if (!@copy($abs, $target)) {
        fwrite(STDERR, 'Не удалось скопировать ' . $rel . "\n");
        exit(2);
    }
    $copied++;
}

// 1. Общие замены по всем текстовым файлам.
$changed = 0;
foreach (Archive::listFiles($stage) as $rel => $abs) {
    if (!$text($abs)) {
        continue;
    }
    $before = (string) file_get_contents($abs);
    $after = strtr($before, GLOBAL_RULES);
    if ($after !== $before) {
        file_put_contents($abs, $after);
        $changed++;
    }
}

// 2. Точечные замены. Не нашлось — значит текст поменяли, а правило устарело: падаем, не молчим.
foreach (FILE_RULES as $rel => $rules) {
    $abs = $stage . '/' . $rel;
    if (!is_file($abs)) {
        fwrite(STDERR, 'Нет файла для правки: ' . $rel . "\n");
        exit(2);
    }
    $body = (string) file_get_contents($abs);
    foreach ($rules as $from => $to) {
        if (!str_contains($body, $from)) {
            fwrite(STDERR, "Правило не сработало в $rel — текст изменился:\n  " . mb_substr($from, 0, 120) . "…\n");
            exit(2);
        }
        $body = str_replace($from, $to, $body);
    }
    file_put_contents($abs, $body);
}

// 3. Куски документации, которые описывают саму сборку: в пакете сборщика нет, значит и его
// описанию там не место (а ещё оно состоит ровно из тех слов, которые мы вычищаем).
foreach (Archive::listFiles($stage) as $rel => $abs) {
    if (!$text($abs)) {
        continue;
    }
    $body = (string) file_get_contents($abs);
    $cut = (string) preg_replace('~<!--\s*handover:start\s*-->.*?<!--\s*handover:end\s*-->\R?~su', '', $body);
    if ($cut !== $body) {
        file_put_contents($abs, $cut);
    }
}

// 4. Записка исполнителю.
file_put_contents($stage . '/HANDOVER.md', handoverNote(Application::VERSION, date('d.m.Y', (int) strtotime(Application::VERSION_DATE))) . "\n");

// 5. ПРОВЕРКА: ни одного запрещённого слова в текстовых файлах.
$hits = [];
foreach (Archive::listFiles($stage) as $rel => $abs) {
    if (!$text($abs)) {
        continue;
    }
    $body = strtolower((string) file_get_contents($abs));
    foreach (FORBIDDEN as $word) {
        $n = substr_count($body, $word);
        if ($n > 0) {
            $hits[] = sprintf('%s — «%s» × %d', $rel, $word, $n);
        }
    }
}
if ($hits !== []) {
    fwrite(STDERR, "В пакете остались упоминания:\n  " . implode("\n  ", $hits) . "\nСборка отменена\n");
    exit(1);
}

$out = isset($args['out']) ? trim($args['out']) : $root . '/runs/handover-' . date('Y-m-d') . '.zip';
// Внутри архива одна папка проекта: распаковка в «Загрузки» не должна рассыпать 160 файлов по папке.
$packed = [];
foreach (Archive::listFiles($stage) as $rel => $abs) {
    $packed[PACKAGE_DIR . '/' . $rel] = $abs;
}
try {
    $n = Archive::zipFiles($packed, $out);
} catch (RuntimeException $e) {
    fwrite(STDERR, $e->getMessage() . "\n");
    exit(2);
}

fwrite(STDOUT, sprintf(
    "Пакет для передачи готов: %s\nВнутри: %s, %s\n",
    $out,
    Backup::files($n),
    Backup::size((int) filesize($out)),
));
fwrite(STDOUT, "Без git (истории коммитов и их авторов нет), без упоминаний ИИ и без адреса репозитория — проверено по всем файлам.\n");
fwrite(STDOUT, "Данных и ключей внутри НЕТ: их передаёт отдельный бекап — php bin/backup.php\n");
if (isset($args['dir'])) {
    fwrite(STDOUT, 'Распакованная копия оставлена в ' . $stage . "\n");
}
exit(0);
