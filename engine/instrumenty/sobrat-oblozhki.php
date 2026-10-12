<?php
/**
 * Обложки слотов из каталога-агрегатора (по умолчанию slotcatalog.com).
 *
 * Зачем. Двенадцать файлов в data-v5/oblozhki показывают другие игры: на
 * sweet-bonanza.webp напечатано «BOOK OF OIL», на book-of-dead.webp — «THE
 * MONEY GAME» (разбор в docs/vitrina-slotov.md). Пока имена не подтверждены,
 * карточки витрины идут рисованными.
 *
 * Как устроено. На каждую игру: страница игры в каталоге → og:image →
 * скачивание → кадр 4:3 → 640×480 webp. Соответствие проверяется дважды:
 * заголовок страницы должен содержать имя игры, и картинка кладётся в
 * ОТДЕЛЬНЫЙ каталог, а не поверх рабочих файлов. Переносить — после сверки
 * глазом по листу (svod-oblozhek.php): имя попадает в ОБЛОЖКИ_ПОДТВЕРЖДЕНЫ
 * только после неё.
 *
 * Вежливость: robots.txt проверяется до обхода, между играми пауза, обход —
 * двенадцать страниц за прогон, не каталог целиком.
 *
 *   php engine/instrumenty/sobrat-oblozhki.php [--проба] [--только=слаг,слаг]
 *                                              [--выход=dir] [--база=https://…]
 *
 * --проба: ничего не скачивает, печатает найденные URL страниц и картинок.
 */

const ИГРЫ = [
    'sweet-bonanza'       => 'Sweet Bonanza',
    'gates-of-olympus'    => 'Gates of Olympus',
    'book-of-dead'        => 'Book of Dead',
    'big-bass-bonanza'    => 'Big Bass Bonanza',
    'starburst'           => 'Starburst',
    'sugar-rush'          => 'Sugar Rush',
    'money-train-3'       => 'Money Train 3',
    'the-dog-house'       => 'The Dog House',
    'wanted-dead-or-wild' => 'Wanted Dead or a Wild',
    'starlight-princess'  => 'Starlight Princess',
    'razor-shark'         => 'Razor Shark',
    'fruit-party'         => 'Fruit Party',
];

$проба = false; $только = []; $выход = __DIR__ . '/../../scratchpad/oblozhki-novye'; $база = 'https://slotcatalog.com';
foreach (array_slice($argv, 1) as $а) {
    if ($а === '--проба') { $проба = true; continue; }
    // substr по длине В БАЙТАХ: ключи кириллические, и счёт по символам режет не там.
    if (str_starts_with($а, '--только=')) { $только = array_filter(explode(',', substr($а, strlen('--только=')))); continue; }
    if (str_starts_with($а, '--выход=')) { $выход = rtrim(substr($а, strlen('--выход=')), '/'); continue; }
    if (str_starts_with($а, '--база=')) { $база = rtrim(substr($а, strlen('--база=')), '/'); continue; }
}
$игры = $только ? array_intersect_key(ИГРЫ, array_flip($только)) : ИГРЫ;

/** GET через curl: прокси окружения берётся из среды, CA — системный. */
function взять(string $url, int $таймаут = 30): array
{
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_MAXREDIRS => 5,
        CURLOPT_TIMEOUT => $таймаут,
        CURLOPT_CONNECTTIMEOUT => 15,
        CURLOPT_USERAGENT => 'cladue-oblozhki/1.0 (+сбор двенадцати обложек для витрины)',
        CURLOPT_HTTPHEADER => ['Accept-Language: en,ru;q=0.8'],
    ]);
    $тело = curl_exec($ch);
    $код = (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE);
    $конец = (string) curl_getinfo($ch, CURLINFO_EFFECTIVE_URL);
    $ошибка = curl_error($ch);
    curl_close($ch);
    return ['код' => $код, 'тело' => $тело === false ? '' : (string) $тело, 'url' => $конец, 'ошибка' => $ошибка];
}

/** Запрещает ли robots.txt путь. Разбор простой: группа для «*», строки Disallow. */
function запрещено(string $база, string $путь): bool
{
    static $правила = null;
    if ($правила === null) {
        $r = взять($база . '/robots.txt', 15);
        $правила = [];
        $наша = false;
        foreach (explode("\n", $r['тело']) as $л) {
            $л = trim(preg_replace('~#.*$~', '', $л));
            if ($л === '') { continue; }
            if (preg_match('~^User-agent:\s*(.+)$~i', $л, $m)) { $наша = trim($m[1]) === '*'; continue; }
            if ($наша && preg_match('~^Disallow:\s*(.*)$~i', $л, $m) && trim($m[1]) !== '') { $правила[] = trim($m[1]); }
        }
    }
    foreach ($правила as $п) { if (str_starts_with($путь, $п)) { return true; } }
    return false;
}

/** Страница игры: сначала прямые слаги, потом поиск по каталогу. */
function страницаИгры(string $база, string $имя): array
{
    $варианты = [
        '/en/slots/' . str_replace(' ', '-', $имя),
        '/en/slots/' . strtolower(str_replace(' ', '-', $имя)),
        '/ru/slots/' . str_replace(' ', '-', $имя),
    ];
    foreach ($варианты as $путь) {
        if (запрещено($база, $путь)) { continue; }
        $r = взять($база . $путь);
        if ($r['код'] === 200 && заголовокПодходит($r['тело'], $имя)) { return $r + ['путь' => $путь]; }
    }
    // Поиск: берём первую ссылку на /slots/, в тексте которой стоит имя игры.
    foreach (['/en/search?q=' . rawurlencode($имя), '/en/slots?q=' . rawurlencode($имя)] as $путь) {
        if (запрещено($база, $путь)) { continue; }
        $r = взять($база . $путь);
        if ($r['код'] !== 200) { continue; }
        if (preg_match_all('~href="([^"]*/slots/[^"]+)"~i', $r['тело'], $m)) {
            foreach ($m[1] as $ссылка) {
                $u = str_starts_with($ссылка, 'http') ? $ссылка : $база . $ссылка;
                $g = взять($u);
                if ($g['код'] === 200 && заголовокПодходит($g['тело'], $имя)) { return $g + ['путь' => $u]; }
                usleep(800000);
            }
        }
    }
    return ['код' => 0, 'тело' => '', 'url' => '', 'ошибка' => 'страница игры не найдена', 'путь' => ''];
}

/** Та ли это игра: имя должно стоять в h1 или в title. */
function заголовокПодходит(string $html, string $имя): bool
{
    $норма = static fn (string $с): string => preg_replace('~[^a-z0-9]+~', '', mb_strtolower($с));
    $цель = $норма($имя);
    if (preg_match('~<h1[^>]*>(.*?)</h1>~su', $html, $m) && str_contains($норма(strip_tags($m[1])), $цель)) { return true; }
    if (preg_match('~<title[^>]*>(.*?)</title>~su', $html, $m) && str_contains($норма(strip_tags($m[1])), $цель)) { return true; }
    return false;
}

/** Адрес картинки со страницы игры: og:image, twitter:image, первая крупная. */
function картинкаСоСтраницы(string $html, string $база): ?string
{
    foreach (['~<meta[^>]+property="og:image"[^>]+content="([^"]+)"~i',
              '~<meta[^>]+content="([^"]+)"[^>]+property="og:image"~i',
              '~<meta[^>]+name="twitter:image"[^>]+content="([^"]+)"~i'] as $шаблон) {
        if (preg_match($шаблон, $html, $m)) { return абсолютный($m[1], $база); }
    }
    if (preg_match('~<img[^>]+src="([^"]+)"[^>]*class="[^"]*(?:game|slot|cover|thumb)[^"]*"~i', $html, $m)) {
        return абсолютный($m[1], $база);
    }
    if (preg_match('~<img[^>]+class="[^"]*(?:game|slot|cover|thumb)[^"]*"[^>]+src="([^"]+)"~i', $html, $m)) {
        return абсолютный($m[1], $база);
    }
    return null;
}

function абсолютный(string $url, string $база): string
{
    if (str_starts_with($url, 'http')) { return $url; }
    if (str_starts_with($url, '//')) { return 'https:' . $url; }
    return $база . '/' . ltrim($url, '/');
}

/** Байты → обложка 640×480: кадр по центру в 4:3, без растягивания. */
function вОбложку(string $байты, string $файл): bool
{
    $src = @imagecreatefromstring($байты);
    if (!$src) { return false; }
    $sw = imagesx($src); $sh = imagesy($src);
    if ($sw < 240 || $sh < 180) { imagedestroy($src); return false; }   // мелкая иконка — не обложка
    $W = 640; $H = 480;
    $cw = $sw; $ch = (int) round($sw * $H / $W);
    if ($ch > $sh) { $ch = $sh; $cw = (int) round($sh * $W / $H); }
    $cx = (int) (($sw - $cw) / 2); $cy = (int) (($sh - $ch) / 2);
    $im = imagecreatetruecolor($W, $H);
    imagecopyresampled($im, $src, 0, 0, $cx, $cy, $W, $H, $cw, $ch);
    imagedestroy($src);
    $ок = imagewebp($im, $файл, 82);
    imagedestroy($im);
    return $ок;
}

if (!$проба && !is_dir($выход) && !mkdir($выход, 0777, true)) {
    fwrite(STDERR, "не создаётся $выход\n"); exit(1);
}
printf("каталог: %s | игр: %d | %s\n\n", $база, count($игры), $проба ? 'проба' : 'выход: ' . $выход);
// Первый же запрос показывает, открыт ли домен: политика окружения рубит
// CONNECT с 403, и дальше все двенадцать игр молча «не найдутся».
$проверка = взять($база . '/robots.txt', 15);
if ($проверка['код'] === 0) {
    fwrite(STDERR, sprintf("домен недоступен: %s\n", $проверка['ошибка'] ?: 'нет ответа'));
    if (str_contains($проверка['ошибка'], 'CONNECT') || str_contains($проверка['ошибка'], '403')) {
        fwrite(STDERR, "это отказ политики сети окружения, а не сайта: откройте домен в настройках\n"
                     . "окружения (Network access → Allowed domains) и повторите\n");
    }
    exit(2);
}
$взято = 0;
foreach ($игры as $слаг => $имя) {
    $стр = страницаИгры($база, $имя);
    if ($стр['код'] !== 200) {
        printf("✗ %-22s %s\n", $слаг, $стр['ошибка'] ?: ('код ' . $стр['код']));
        sleep(2); continue;
    }
    $адрес = картинкаСоСтраницы($стр['тело'], $база);
    if ($адрес === null) {
        printf("✗ %-22s страница есть (%s), картинки нет\n", $слаг, $стр['url']);
        sleep(2); continue;
    }
    if ($проба) {
        printf("· %-22s %s\n    %s\n", $слаг, $стр['url'], $адрес);
        sleep(2); continue;
    }
    $к = взять($адрес, 45);
    if ($к['код'] !== 200 || $к['тело'] === '') {
        printf("✗ %-22s картинка не скачалась: код %d %s\n", $слаг, $к['код'], $к['ошибка']);
        sleep(2); continue;
    }
    $файл = $выход . '/' . $слаг . '.webp';
    if (!вОбложку($к['тело'], $файл)) {
        printf("✗ %-22s картинка не читается или мелкая (%d байт)\n", $слаг, strlen($к['тело']));
        sleep(2); continue;
    }
    [$w, $h] = getimagesize($файл);
    printf("✓ %-22s %s → %d×%d, %d КБ\n", $слаг, $адрес, $w, $h, (int) (filesize($файл) / 1024));
    $взято++;
    sleep(2);
}
printf("\nвзято %d из %d\n", $взято, count($игры));
if (!$проба && $взято) {
    printf("дальше: php engine/instrumenty/svod-oblozhek.php лист.png %s — и сверить глазом,\n", $выход);
    printf("что на каждой картинке та игра; только после этого переносить в data-v5/oblozhki\n");
}
