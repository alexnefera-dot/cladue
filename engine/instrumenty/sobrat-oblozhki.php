<?php
/**
 * Обложки слотов из каталога slotsmate.com.
 *
 * Зачем. Двенадцать файлов в data-v5/oblozhki показывали другие игры: на
 * sweet-bonanza.webp было напечатано «BOOK OF OIL», на book-of-dead.webp —
 * «THE MONEY GAME» (разбор в docs/vitrina-slotov.md). Пока имена не
 * подтверждены, карточки витрины идут рисованными.
 *
 * Как устроено. На каждую игру: страница игры → og:image (у каталога это
 * скриншот игры 1200×630) → кадр 4:3 → 640×480 webp. Адреса прописаны руками
 * и проверены: «угадывание» слага ведёт не туда — /pragmatic-play/fruit-party
 * редиректит на игру Amaya с тем же названием, а Book of Dead лежит под
 * «play-n-go-rich-wilde-and-the-book-of-dead».
 *
 * Соответствие проверяется трижды: имя игры должно стоять в h1 страницы,
 * файлы кладутся в ОТДЕЛЬНЫЙ каталог, и лист сверяется глазом
 * (svod-oblozhek.php). Только после этого имя вписывается в
 * ОБЛОЖКИ_ПОДТВЕРЖДЕНЫ и фотообложки включаются сами.
 *
 * Вежливость: robots.txt читается до обхода, между играми пауза, обход —
 * двенадцать страниц за прогон, не каталог.
 *
 *   php engine/instrumenty/sobrat-oblozhki.php [--проба] [--только=слаг,слаг]
 *                                              [--выход=dir]
 */

require_once __DIR__ . '/set-kataloga.php';

/** слаг обложки => [имя игры, путь страницы в каталоге]. */
const ИГРЫ = [
    'sweet-bonanza'       => ['Sweet Bonanza',        '/software/pragmatic-play/sweet-bonanza'],
    'gates-of-olympus'    => ['Gates of Olympus',     '/software/pragmatic-play/gates-of-olympus'],
    'book-of-dead'        => ['Book of Dead',         '/software/play-n-go/play-n-go-rich-wilde-and-the-book-of-dead'],
    'big-bass-bonanza'    => ['Big Bass Bonanza',     '/software/pragmatic-play/big-bass-bonanza'],
    'starburst'           => ['Starburst',            '/software/netent/starburst'],
    'sugar-rush'          => ['Sugar Rush',           '/software/pragmatic-play/sugar-rush'],
    'money-train-3'       => ['Money Train 3',        '/software/relax-gaming/money-train-3'],
    'the-dog-house'       => ['The Dog House',        '/software/pragmatic-play/the-dog-house'],
    'wanted-dead-or-wild' => ['Wanted Dead or a Wild','/software/hacksaw-gaming/wanted-dead-or-a-wild'],
    'starlight-princess'  => ['Starlight Princess',   '/software/pragmatic-play/starlight-princess'],
    'razor-shark'         => ['Razor Shark',          '/software/push-gaming/razor-shark'],
    'fruit-party'         => ['Fruit Party',          '/software/pragmatic-play/pragmatic-play-fruit-party'],
];

$проба = false; $только = []; $выход = __DIR__ . '/../../scratchpad/oblozhki-novye';
foreach (array_slice($argv, 1) as $а) {
    if ($а === '--проба') { $проба = true; continue; }
    // substr по длине В БАЙТАХ: ключи кириллические, счёт по символам режет не там.
    if (str_starts_with($а, '--только=')) { $только = array_filter(explode(',', substr($а, strlen('--только=')))); continue; }
    if (str_starts_with($а, '--выход=')) { $выход = rtrim(substr($а, strlen('--выход=')), '/'); continue; }
}
$игры = $только ? array_intersect_key(ИГРЫ, array_flip($только)) : ИГРЫ;

if (!$проба && !is_dir($выход) && !mkdir($выход, 0777, true)) {
    fwrite(STDERR, "не создаётся $выход\n"); exit(1);
}
printf("каталог: %s | игр: %d | %s\n\n", КАТ_БАЗА, count($игры), $проба ? 'проба' : 'выход: ' . $выход);
if (катДоменЗакрыт()) { exit(2); }

$взято = 0;
foreach ($игры as $слаг => [$имя, $путь]) {
    if (катЗапрещено($путь)) { printf("· %-22s robots.txt запрещает %s\n", $слаг, $путь); continue; }
    $стр = катВзять(КАТ_БАЗА . $путь);
    if ($стр['код'] !== 200) {
        printf("✗ %-22s страница: код %d %s\n", $слаг, $стр['код'], $стр['ошибка']);
        sleep(2); continue;
    }
    if (!катИмяВЗаголовке($стр['тело'], $имя)) {
        preg_match('~<h1[^>]*>(.*?)</h1>~su', $стр['тело'], $m);
        printf("✗ %-22s не та игра: h1 «%s»\n", $слаг, trim(strip_tags($m[1] ?? '—')));
        sleep(2); continue;
    }
    $адрес = катКартинка($стр['тело']);
    if ($адрес === null) { printf("✗ %-22s нет og:image на %s\n", $слаг, $стр['url']); sleep(2); continue; }
    if ($проба) { printf("· %-22s %s\n", $слаг, $адрес); sleep(2); continue; }
    $к = катВзять($адрес, 45);
    if ($к['код'] !== 200 || $к['тело'] === '') {
        printf("✗ %-22s картинка не скачалась: код %d %s\n", $слаг, $к['код'], $к['ошибка']);
        sleep(2); continue;
    }
    $беда = катВОбложку($к['тело'], "$выход/$слаг.webp");
    if ($беда !== '') { printf("✗ %-22s %s\n", $слаг, $беда); sleep(2); continue; }
    [$w, $h] = getimagesize("$выход/$слаг.webp");
    printf("✓ %-22s %s → %d×%d, %d КБ\n", $слаг, basename($адрес), $w, $h, (int) (filesize("$выход/$слаг.webp") / 1024));
    $взято++;
    sleep(2);
}
printf("\nвзято %d из %d\n", $взято, count($игры));
if (!$проба && $взято) {
    printf("дальше: php engine/instrumenty/svod-oblozhek.php лист.png %s — сверить глазом,\n", $выход);
    printf("что на каждой картинке та игра; только после этого переносить в data-v5/oblozhki\n");
}
