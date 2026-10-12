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

const БАЗА = 'https://www.slotsmate.com';

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

/**
 * GET через curl. Заголовки браузерные и HTTP/1.1 не для маскировки, а по
 * необходимости: на голый запрос сервер каталога отвечает «400 Bad Request».
 */
function взять(string $url, int $таймаут = 30): array
{
    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_MAXREDIRS => 5,
        CURLOPT_TIMEOUT => $таймаут,
        CURLOPT_CONNECTTIMEOUT => 15,
        CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
        CURLOPT_ENCODING => '',
        CURLOPT_USERAGENT => 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36',
        CURLOPT_HTTPHEADER => [
            'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language: en-US,en;q=0.9',
        ],
    ]);
    $тело = curl_exec($ch);
    $итог = ['код' => (int) curl_getinfo($ch, CURLINFO_RESPONSE_CODE),
             'тело' => $тело === false ? '' : (string) $тело,
             'url' => (string) curl_getinfo($ch, CURLINFO_EFFECTIVE_URL),
             'ошибка' => curl_error($ch)];
    curl_close($ch);
    return $итог;
}

/** Запрещает ли robots.txt путь (группа «*», строки Disallow). */
function запрещено(string $путь): bool
{
    static $правила = null;
    if ($правила === null) {
        $r = взять(БАЗА . '/robots.txt', 15);
        $правила = []; $наша = false;
        foreach (explode("\n", $r['тело']) as $л) {
            $л = trim((string) preg_replace('~#.*$~', '', $л));
            if ($л === '') { continue; }
            if (preg_match('~^User-agent:\s*(.+)$~i', $л, $m)) { $наша = trim($m[1]) === '*'; continue; }
            if ($наша && preg_match('~^Disallow:\s*(.*)$~i', $л, $m) && trim($m[1]) !== '') { $правила[] = trim($m[1]); }
        }
    }
    foreach ($правила as $п) { if (str_starts_with($путь, $п)) { return true; } }
    return false;
}

/** Та ли это игра: имя должно стоять в h1 страницы. */
function имяВЗаголовке(string $html, string $имя): bool
{
    $норма = static fn (string $с): string => (string) preg_replace('~[^a-z0-9]+~', '', mb_strtolower($с));
    if (!preg_match('~<h1[^>]*>(.*?)</h1>~su', $html, $m)) { return false; }
    return str_contains($норма(strip_tags($m[1])), $норма($имя));
}

function картинкаСоСтраницы(string $html): ?string
{
    foreach (['~<meta[^>]+property="og:image"[^>]+content="([^"]+)"~i',
              '~<meta[^>]+content="([^"]+)"[^>]+property="og:image"~i'] as $шаблон) {
        if (preg_match($шаблон, $html, $m)) {
            $u = html_entity_decode($m[1], ENT_QUOTES, 'UTF-8');
            return str_starts_with($u, 'http') ? $u : (str_starts_with($u, '//') ? 'https:' . $u : БАЗА . '/' . ltrim($u, '/'));
        }
    }
    return null;
}

/** Байты → обложка 640×480: кадр по центру в 4:3, без растягивания. */
function вОбложку(string $байты, string $файл): string
{
    $src = @imagecreatefromstring($байты);
    if (!$src) { return 'не читается как картинка'; }
    $sw = imagesx($src); $sh = imagesy($src);
    if ($sw < 240 || $sh < 180) { imagedestroy($src); return sprintf('мелкая: %d×%d', $sw, $sh); }
    $W = 640; $H = 480;
    $cw = $sw; $ch = (int) round($sw * $H / $W);
    if ($ch > $sh) { $ch = $sh; $cw = (int) round($sh * $W / $H); }
    $im = imagecreatetruecolor($W, $H);
    imagecopyresampled($im, $src, 0, 0, (int) (($sw - $cw) / 2), (int) (($sh - $ch) / 2), $W, $H, $cw, $ch);
    imagedestroy($src);
    $ок = imagewebp($im, $файл, 82);
    imagedestroy($im);
    return $ок ? '' : 'не сохраняется';
}

if (!$проба && !is_dir($выход) && !mkdir($выход, 0777, true)) {
    fwrite(STDERR, "не создаётся $выход\n"); exit(1);
}
printf("каталог: %s | игр: %d | %s\n\n", БАЗА, count($игры), $проба ? 'проба' : 'выход: ' . $выход);
// Первый запрос показывает, открыт ли домен: политика сети рубит CONNECT с 403.
$проверка = взять(БАЗА . '/robots.txt', 15);
if ($проверка['код'] === 0) {
    fwrite(STDERR, sprintf("домен недоступен: %s\n", $проверка['ошибка'] ?: 'нет ответа'));
    if (str_contains($проверка['ошибка'], 'CONNECT') || str_contains($проверка['ошибка'], '403')) {
        fwrite(STDERR, "это отказ политики сети окружения, а не сайта: откройте домен в настройках\n"
                     . "окружения (Network access → Allowed domains) и повторите\n");
    }
    exit(2);
}

$взято = 0;
foreach ($игры as $слаг => [$имя, $путь]) {
    if (запрещено($путь)) { printf("· %-22s robots.txt запрещает %s\n", $слаг, $путь); continue; }
    $стр = взять(БАЗА . $путь);
    if ($стр['код'] !== 200) {
        printf("✗ %-22s страница: код %d %s\n", $слаг, $стр['код'], $стр['ошибка']);
        sleep(2); continue;
    }
    if (!имяВЗаголовке($стр['тело'], $имя)) {
        preg_match('~<h1[^>]*>(.*?)</h1>~su', $стр['тело'], $m);
        printf("✗ %-22s не та игра: h1 «%s»\n", $слаг, trim(strip_tags($m[1] ?? '—')));
        sleep(2); continue;
    }
    $адрес = картинкаСоСтраницы($стр['тело']);
    if ($адрес === null) { printf("✗ %-22s нет og:image на %s\n", $слаг, $стр['url']); sleep(2); continue; }
    if ($проба) { printf("· %-22s %s\n", $слаг, $адрес); sleep(2); continue; }
    $к = взять($адрес, 45);
    if ($к['код'] !== 200 || $к['тело'] === '') {
        printf("✗ %-22s картинка не скачалась: код %d %s\n", $слаг, $к['код'], $к['ошибка']);
        sleep(2); continue;
    }
    $беда = вОбложку($к['тело'], "$выход/$слаг.webp");
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
