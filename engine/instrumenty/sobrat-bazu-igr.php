<?php
/**
 * База игр для витрины: пара сотен слотов с именем, студией, отдачей, темами
 * и обложкой → engine/data-v5/igry.json + data-v5/oblozhki/<слаг>.webp.
 *
 * Зачем. Состав витрины у доноров один на все восемьдесят наборов, и в
 * двенадцати карточках всегда те же игры. Чтобы набор игр можно было менять
 * при генерации, нужен запас: имена, студии и отдача — как у корпуса, плюс
 * настоящая картинка на каждое имя.
 *
 * Порядок отбора. Сначала имена из корпусного каталога (274 игры, которые
 * доноры и правда называют, — engine/data-v5/katalog-slotov.json), потом
 * остальные игры тех же студий по убыванию веса студии в корпусе. Так база
 * растёт из корпуса, а не из случайного списка сайта.
 *
 * Прогон идёт по двум запросам на игру (страница и картинка) с паузой, и его
 * можно прерывать: уже собранное лежит в igry.json и повторно не качается.
 *
 *   php engine/instrumenty/sobrat-bazu-igr.php [--предел=220] [--пауза=1200]
 *                                              [--проба] [--только-индекс]
 */
require_once __DIR__ . '/set-kataloga.php';

/** Студия корпуса → её слаг в каталоге. Пропущенные в каталоге не заведены. */
const СТУДИИ = [
    'Pragmatic Play'    => 'pragmatic-play',
    "Play'n GO"         => 'play-n-go',
    'NetEnt'            => 'netent',
    'Push Gaming'       => 'push-gaming',
    'Microgaming'       => 'games-global',      // Microgaming теперь Games Global
    'Relax Gaming'      => 'relax-gaming',
    'Hacksaw Gaming'    => 'hacksaw-gaming',
    'Nolimit City'      => 'nolimit-city',
    'Yggdrasil'         => 'yggdrasil-gaming',
    'Big Time Gaming'   => 'big-time-gaming',
    'Novomatic'         => 'novomatic',
    'Blueprint Gaming'  => 'blueprint-gaming',
    'Red Tiger'         => 'red-tiger-gaming',
    'Thunderkick'       => 'thunderkick',
    'Quickspin'         => 'quickspin',
    'Playtech'          => 'playtech',
    'Kalamba Games'     => 'kalamba-games',
    'Bgaming'           => 'bgaming',
    'Spinomenal'        => 'spinomenal',
    'Endorphina'        => 'endorphina',
    'Igrosoft'          => 'igrosoft',
];

$предел = 220; $пауза = 1200000; $проба = false; $толькоИндекс = false; $толькоТемы = false;
foreach (array_slice($argv, 1) as $а) {
    if ($а === '--проба') { $проба = true; continue; }
    if ($а === '--только-индекс') { $толькоИндекс = true; continue; }
    // Освежить темы у уже собранных игр, не перекачивая картинки: первая
    // версия разбора ловила меню сайта и писала всем одни и те же темы.
    if ($а === '--темы') { $толькоТемы = true; continue; }
    if (str_starts_with($а, '--предел=')) { $предел = (int) substr($а, strlen('--предел=')); continue; }
    if (str_starts_with($а, '--пауза=')) { $пауза = ((int) substr($а, strlen('--пауза='))) * 1000; continue; }
}

$корень   = dirname(__DIR__, 2);
$данные   = $корень . '/engine/data-v5';
$обложки  = $данные . '/oblozhki';
$файлБазы = $данные . '/igry.json';
if (!is_dir($обложки)) { mkdir($обложки, 0777, true); }

if (катДоменЗакрыт()) { exit(2); }

// ── 1. Корпусный пул: его имена идут первыми, из него же теги и отдача ──
$корпус = [];
if (is_file("$данные/katalog-slotov.json")) {
    foreach ((json_decode((string) file_get_contents("$данные/katalog-slotov.json"), true)['игры'] ?? []) as $и) {
        $корпус[катКлюч((string) $и['н'])] = $и;
    }
}
printf("корпусных имён: %d | студий: %d | предел: %d\n\n", count($корпус), count(СТУДИИ), $предел);

// ── 2. Индекс каталога: игры со страниц студий ──
$индекс = [];                                  // ключ имени => [имя, путь, студия]
foreach (СТУДИИ as $студия => $слагСтудии) {
    $путь = '/software/' . $слагСтудии;
    if (катЗапрещено($путь)) { printf("· %-18s robots.txt запрещает\n", $слагСтудии); continue; }
    $r = катВзять(КАТ_БАЗА . $путь);
    if ($r['код'] !== 200) { printf("✗ %-18s код %d\n", $слагСтудии, $r['код']); usleep($пауза); continue; }
    $было = count($индекс);
    if (preg_match_all('~<a href="(/software/' . preg_quote($слагСтудии, '~') . '/[a-z0-9-]+)"[^>]*class="game-holder".*?<span class="game-title">(.*?)</span>~su',
                       $r['тело'], $m, PREG_SET_ORDER)) {
        foreach ($m as $с) {
            $имя = trim(html_entity_decode(strip_tags($с[2]), ENT_QUOTES, 'UTF-8'));
            $к = катКлюч($имя);
            if ($имя === '' || isset($индекс[$к])) { continue; }
            $индекс[$к] = ['имя' => $имя, 'путь' => $с[1], 'студия' => $студия];
        }
    }
    printf("· %-18s игр %3d (всего %d)\n", $слагСтудии, count($индекс) - $было, count($индекс));
    usleep($пауза);
}
printf("\nиндекс: %d игр\n", count($индекс));
if ($толькоИндекс) {
    $вКорпусе = count(array_intersect_key($индекс, $корпус));
    printf("из них в корпусном каталоге: %d\n", $вКорпусе);
    exit(0);
}

// ── 3. Очередь: корпусные имена вперёд ──
$очередь = [];
foreach ($корпус as $к => $_) { if (isset($индекс[$к])) { $очередь[$к] = $индекс[$к]; } }
foreach ($индекс as $к => $з) { if (!isset($очередь[$к])) { $очередь[$к] = $з; } }
$очередь = array_slice($очередь, 0, $предел, true);
printf("в очереди: %d (корпусных %d)\n\n", count($очередь), count(array_intersect_key($очередь, $корпус)));

// ── 4. Уже собранное не качаем заново ──
$база = is_file($файлБазы)
    ? (array) (json_decode((string) file_get_contents($файлБазы), true)['игры'] ?? [])
    : [];
$поСлагу = [];
foreach ($база as $и) { $поСлагу[(string) $и['слаг']] = $и; }

/** Имя → слаг файла: латиница, строчные, дефисы. */
function слагИмени(string $имя): string
{
    $с = mb_strtolower(html_entity_decode($имя, ENT_QUOTES, 'UTF-8'));
    $с = (string) preg_replace('~[^a-z0-9]+~', '-', $с);
    return trim($с, '-');
}

$взято = 0; $пропущено = 0; $беды = [];
foreach ($очередь as $к => $з) {
    $слаг = слагИмени($з['имя']);
    if ($слаг === '') { continue; }
    // Столы и лайв в витрину слотов не идут: у доноров там только автоматы.
    // Проверка не по началу имени, а по вхождению: у студий столы названы
    // «NetEnt French Roulette», «NetEnt Blackjack» — префикс их не ловит.
    if (preg_match('~(table game|\blive\b|roulette|blackjack|baccarat|video poker|jacks or better|sic bo|craps|\bkeno\b|\bbingo\b|scratch|dragon tiger|andar|teen patti|casino night)~i', $з['имя'])) { continue; }
    if ($толькоТемы && !isset($поСлагу[$слаг])) { continue; }
    if (!$толькоТемы && isset($поСлагу[$слаг]) && is_file("$обложки/$слаг.webp")) { $пропущено++; continue; }
    if (катЗапрещено($з['путь'])) { $беды[] = $з['имя'] . ': robots.txt'; continue; }

    $стр = катВзять(КАТ_БАЗА . $з['путь']);
    if ($стр['код'] !== 200) { $беды[] = $з['имя'] . ': страница ' . $стр['код']; usleep($пауза); continue; }
    if (!катИмяВЗаголовке($стр['тело'], $з['имя'])) { $беды[] = $з['имя'] . ': h1 не о ней'; usleep($пауза); continue; }

    // Отдача: корпусная в приоритете — её же называют доноры; иначе со страницы.
    $отдача = (string) ($корпус[$к]['rtp'] ?? '');
    if ($отдача === '' && preg_match('~rtp-label.*?details-cont[^>]*>\s*([\d.]+)\s*%~su', $стр['тело'], $m)) {
        $отдача = $m[1];
    }
    // Тема игры лежит в блоке деталей, у ссылки свой класс. Простое
    // href="/themes/..." ловит меню сайта, и у всех игр выходили одни и те же
    // «777, christmas, asian».
    $темы = [];
    if (preg_match_all('~class="tech"[^>]*href="/themes/([a-z0-9-]+)"~', $стр['тело'], $m)) {
        $темы = array_slice(array_values(array_unique($m[1])), 0, 4);
    }

    if ($толькоТемы) {
        $поСлагу[$слаг]['темы'] = $темы;
        $поСлагу[$слаг]['путь'] = $з['путь'];
        $взято++;
        printf("· %-34s темы: %s\n", $з['имя'], $темы ? implode(', ', $темы) : '—');
        ksort($поСлагу);
        file_put_contents($файлБазы, json_encode(
            ['источник' => ['каталог' => КАТ_БАЗА, 'собрано' => date('c')], 'игры' => array_values($поСлагу)],
            JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
        usleep($пауза);
        continue;
    }
    $адрес = катКартинка($стр['тело']);
    if ($адрес === null) { $беды[] = $з['имя'] . ': нет og:image'; usleep($пауза); continue; }
    if ($проба) {
        printf("· %-34s %-16s RTP %-6s %s\n", $з['имя'], $з['студия'], $отдача ?: '—', basename($адрес));
        $взято++; usleep($пауза); continue;
    }
    usleep($пауза);
    $к2 = катВзять($адрес, 45);
    if ($к2['код'] !== 200 || $к2['тело'] === '') { $беды[] = $з['имя'] . ': картинка ' . $к2['код']; usleep($пауза); continue; }
    $беда = катВОбложку($к2['тело'], "$обложки/$слаг.webp");
    if ($беда !== '') { $беды[] = $з['имя'] . ': ' . $беда; usleep($пауза); continue; }

    $поСлагу[$слаг] = ['слаг' => $слаг, 'н' => $з['имя'], 'п' => $з['студия'],
                       'rtp' => $отдача, 'темы' => $темы, 'путь' => $з['путь'],
                       'т' => array_values((array) ($корпус[$к]['т'] ?? [])),
                       'корпус' => isset($корпус[$к])];
    $взято++;
    printf("✓ %-34s %-16s RTP %-6s %d КБ\n", $з['имя'], $з['студия'], $отдача ?: '—',
           (int) (filesize("$обложки/$слаг.webp") / 1024));
    // Запись после каждой игры: прогон можно прервать и продолжить.
    ksort($поСлагу);
    file_put_contents($файлБазы, json_encode(
        ['источник' => ['каталог' => КАТ_БАЗА, 'собрано' => date('c')], 'игры' => array_values($поСлагу)],
        JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));
    usleep($пауза);
}

printf("\nвзято %d, пропущено (уже есть) %d, в базе всего %d\n", $взято, $пропущено, count($поСлагу));
if ($беды) {
    printf("не вышло у %d:\n", count($беды));
    foreach (array_slice($беды, 0, 25) as $б) { echo "  $б\n"; }
}
