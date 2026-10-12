<?php
/**
 * Общее для сборщиков из каталога slotsmate.com: запрос, robots.txt и
 * приведение картинки к обложке 640×480.
 *
 * Отдельный файл, потому что сборщиков два: двенадцать имён витрины
 * (sobrat-oblozhki.php) и база на пару сотен игр (sobrat-bazu-igr.php).
 */

const КАТ_БАЗА = 'https://www.slotsmate.com';

/**
 * GET через curl. Браузерные заголовки и HTTP/1.1 не маскировка, а
 * необходимость: на голый запрос сервер отвечает «400 Bad Request».
 */
function катВзять(string $url, int $таймаут = 30): array
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
function катЗапрещено(string $путь): bool
{
    static $правила = null;
    if ($правила === null) {
        $r = катВзять(КАТ_БАЗА . '/robots.txt', 15);
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

/** Домен закрыт политикой сети? Печатает причину и возвращает true. */
function катДоменЗакрыт(): bool
{
    $r = катВзять(КАТ_БАЗА . '/robots.txt', 15);
    if ($r['код'] !== 0) { return false; }
    fwrite(STDERR, sprintf("домен недоступен: %s\n", $r['ошибка'] ?: 'нет ответа'));
    if (str_contains($r['ошибка'], 'CONNECT') || str_contains($r['ошибка'], '403')) {
        fwrite(STDERR, "это отказ политики сети окружения, а не сайта: откройте домен в настройках\n"
                     . "окружения (Network access → Allowed domains) и повторите\n");
    }
    return true;
}

/** Адрес из атрибута в абсолютный. */
function катАбсолютный(string $url): string
{
    $u = html_entity_decode($url, ENT_QUOTES, 'UTF-8');
    if (str_starts_with($u, 'http')) { return $u; }
    if (str_starts_with($u, '//')) { return 'https:' . $u; }
    return КАТ_БАЗА . '/' . ltrim($u, '/');
}

/** og:image со страницы игры (у каталога это скриншот 1200×630). */
function катКартинка(string $html): ?string
{
    foreach (['~<meta[^>]+property="og:image"[^>]+content="([^"]+)"~i',
              '~<meta[^>]+content="([^"]+)"[^>]+property="og:image"~i'] as $шаблон) {
        if (preg_match($шаблон, $html, $m)) { return катАбсолютный($m[1]); }
    }
    return null;
}

/** Имя в сравнимый вид: только буквы и цифры в нижнем регистре. */
function катКлюч(string $с): string
{
    return (string) preg_replace('~[^a-z0-9]+~', '', mb_strtolower(html_entity_decode($с, ENT_QUOTES, 'UTF-8')));
}

/** Та ли это игра: имя должно стоять в h1 страницы. */
function катИмяВЗаголовке(string $html, string $имя): bool
{
    if (!preg_match('~<h1[^>]*>(.*?)</h1>~su', $html, $m)) { return false; }
    return str_contains(катКлюч(strip_tags($m[1])), катКлюч($имя));
}

/** Байты → обложка 640×480: кадр по центру в 4:3, без растягивания. */
function катВОбложку(string $байты, string $файл): string
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
