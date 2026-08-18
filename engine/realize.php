<?php
declare(strict_types=1);

/**
 * Тонкий боевой реалайзер: берёт ОДИН промпт (из PromptBuilder) и делает ОДИН
 * вызов Claude API → сохраняет готовую HTML-страницу. Без агентской обвязки,
 * без tool-use — чистый Messages API. Стоимость ≈ вход(промпт) + выход(страница).
 *
 *   php realize.php --prompt=path/to/prompt-main.md --out=path/to/main.html \
 *       [--model=claude-opus-5] [--max-tokens=16000] [--effort=medium] [--register=expert] \
 *       [--профиль=engine/data-v5/profil-v5.json] [--без-потока]
 *
 * Инварианты системного промпта раньше были зашиты в код и описывали поколение
 * v2: финальный JSON-LD и зачин «%brand_name_ru%. …». Корпус v5 не делает ни
 * того, ни другого — микроданные Question/Answer вместо JSON-LD, opener_name
 * ноль, кириллица на внутренних ноль. С --профиль= эти строки собираются из
 * профиля, поэтому смена поколения больше не требует правки кода.
 *
 * Авторизация: ANTHROPIC_API_KEY (x-api-key) или ANTHROPIC_AUTH_TOKEN (Bearer+oauth).
 * Прокси/TLS среды подхватываются автоматически (HTTPS_PROXY, /root/.ccr/ca-bundle.crt).
 */

$opts = [];
foreach (array_slice($argv, 1) as $a) {
    if (preg_match('/^--([^=]+)=(.*)$/s', $a, $m)) { $opts[$m[1]] = $m[2]; }
    elseif (preg_match('/^--(.+)$/', $a, $m)) { $opts[$m[1]] = true; }
}
$promptFile = $opts['prompt'] ?? '';
$outFile    = $opts['out'] ?? '';
$model      = $opts['model'] ?? 'claude-opus-5';
$maxTokens  = (int)($opts['max-tokens'] ?? 16000);
$effort     = $opts['effort'] ?? 'medium';         // low|medium|high|xhigh|max
$register   = $opts['register'] ?? '';             // подсказка регистра (опц.)
$mode       = $opts['mode'] ?? 'realize';          // realize | fix
$profilFile = $opts['профиль'] ?? '';
$SUHOJ      = isset($opts['сухой']);      // собрать запрос и показать, не вызывая модель
// Ответ читается потоком. На длинной генерации без потока по соединению
// минутами не идёт ни байта, и TLS рвётся: «SSL routines::unexpected eof while
// reading». Поток гонит события всё время работы модели и держит канал живым.
$STREAM     = !isset($opts['без-потока']);

if ($promptFile === '' || !is_file($promptFile)) { fwrite(STDERR, "нет --prompt файла\n"); exit(1); }
if ($outFile === '') { fwrite(STDERR, "нет --out файла\n"); exit(1); }
$prompt = (string) file_get_contents($promptFile);

// ── системный промпт (роль + инварианты) ───────────────────────────────────
$regLine = $register !== '' ? "\nРегистр этой связки: {$register} — держи его на всей странице." : '';

/**
 * Инварианты поколения. Без профиля остаются прежние строки: старые прогоны
 * должны воспроизводиться дословно.
 */
$prof = null;
if ($profilFile !== '') {
    $prof = json_decode((string) file_get_contents($profilFile), true);
    if (!$prof) { fwrite(STDERR, "не читается профиль: $profilFile\n"); exit(1); }
}
if ($prof) {
    $zapret = [];
    foreach ($prof['запреты'] ?? [] as $pole => $txt) { $zapret[] = '  — ' . $txt; }
    $inv = "- Разметка FAQ: " . ($prof['FAQ']['разметка'] ?? 'микроданные Question/Answer')
        . ". JSON-LD не ставь.\n"
        . "- Зачин НЕ начинается с имени площадки: opener_name у доноров ноль.\n"
        . "- Финал: " . ($prof['структура']['финал']['задание'] ?? 'FAQ последним H2') . "\n"
        . "- Обращение: " . ($prof['регистр']['адресация'] ?? 'вы') . "\n"
        . "- Запреты (ноль у доноров):\n" . implode("\n", $zapret);
} else {
    $inv = "- Каждая страница начинается с «%brand_name_ru%. …».\n"
        . "- Финальный <script type=\"application/ld+json\"> обязателен.";
}
if ($mode === 'fix') {
    // корректирующий проход verify-loop: правим ТОЛЬКО перечисленное в брифе
    $system =
"Ты — корректирующий проход авто-реалайзера казино-контента. На входе БРИФ (что вылетело за цель) и ТЕКУЩИЙ HTML. Примени ТОЛЬКО правки из брифа, точечно.
Правила:
- Верни ТОЛЬКО исправленный HTML-фрагмент тела (как в оригинале: <p>/<h2>/<h3>/<ul>/<table>/<blockquote> + финальный JSON-LD). Без markdown и пояснений.
- Сохрани всё, что уже в норме: объём, структуру, таблицы, %brand_%-переменные, разметку FAQ, дата-штамп, существующие ссылки без self-link.
- «ЦИФРЫ убери N» → перепиши N чисел ИЗ ПРОЗЫ словами; числа в таблицах/фактуре не трогай. «КЛАСТЕР ниже» → добавь абзац/пункты по теме СЛОВАМИ (без новых цифр). «КЛАСТЕР выше» → проредь ключи синонимами. «СУЩНОСТИ убери N» → убери N названий игр/провайдеров из прозы. «ТОШНОТА» → снизь повтор частых слов. H3/ВЫДЕЛЕНИЯ/FAQ/ОБЪЁМ — как сказано.
- Регистр не меняй.{$regLine}";
} else {
    $system =
"Ты — авто-реалайзер SEO-контента для казино под Яндекс. На входе — готовый ПРОМПТ с жёсткими целями; на выходе — ОДНА готовая HTML-страница.
Правила:
- Верни ТОЛЬКО HTML-фрагмент тела: <p>,<h2>,<h3>,<ul>/<li>,<table>,<blockquote>, блоки FAQ. Без <html>/<head>/<body>, без markdown-обёрток, без пояснений до или после.
- Бренд/домен/дата — строго переменные %brand_name_ru%, %brand_name_en%, %domain_name%, %date%. Имя площадки не выдумывай.
{$inv}
- Соблюдай цели промпта: объём (±10%, НЕ занижай), H2/H3, списки, таблицы, цитаты, <strong>, вставки бренда ру/англ, эмодзи, перелинковку (кол-во и анкоры, без self-ссылок).
- Цифры бери только из блока ФАКТУРА и таблиц — не выдумывай лишних чисел. Семантические кластеры добивай ТЕМАТИЧЕСКИМИ СЛОВАМИ, не цифрами. Сущности — не больше указанного. FAQ при цели ≤1 не делай.
- Принцип: воспроизвести корпус, не превзойти.{$regLine}";
}

// ── тело запроса ───────────────────────────────────────────────────────────
$body = [
    'model'       => $model,
    'max_tokens'  => $maxTokens,
    'system'      => $system,
    'thinking'    => ['type' => 'adaptive'],
    'output_config' => ['effort' => $effort],
    'messages'    => [[ 'role' => 'user', 'content' => $prompt ]],
];
if ($STREAM) { $body['stream'] = true; }
$payload = json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);

// Сухой прогон: показать, что именно уйдёт в модель. Нужен, чтобы проверять
// инварианты системного промпта без расхода токенов и без ключа.
if ($SUHOJ) {
    fwrite(STDERR, "── системный промпт ──\n" . $system . "\n\n"
        . sprintf("── запрос ── модель %s, max_tokens %d, effort %s, поток %s, промпт %d знаков\n",
            $model, $maxTokens, $effort, $STREAM ? 'да' : 'нет', mb_strlen($prompt)));
    exit(0);
}

// ── авторизация ────────────────────────────────────────────────────────────
// Приоритет: env ANTHROPIC_API_KEY → env ANTHROPIC_AUTH_TOKEN → файл-ключ.
// Файл-ключ (фолбэк, если в окружении переменной нет): путь из ANTHROPIC_KEY_FILE
// либо дефолт engine/.anthropic-key. Файл в .gitignore — в репозиторий не попадает.
$headers = ['content-type: application/json', 'anthropic-version: 2023-06-01'];
$apiKey = getenv('ANTHROPIC_API_KEY') ?: '';
$authTok = getenv('ANTHROPIC_AUTH_TOKEN') ?: '';
if ($apiKey === '' && $authTok === '') {
    $keyFile = getenv('ANTHROPIC_KEY_FILE') ?: (__DIR__ . '/.anthropic-key');
    if (is_file($keyFile)) {
        $fileKey = trim((string) file_get_contents($keyFile));
        if ($fileKey !== '') {
            // sk-ant-… → x-api-key; иначе трактуем как OAuth-токен
            if (strncmp($fileKey, 'sk-ant-', 7) === 0) { $apiKey = $fileKey; }
            else { $authTok = $fileKey; }
        }
    }
}
if ($apiKey !== '') { $headers[] = 'x-api-key: ' . $apiKey; }
elseif ($authTok !== '') { $headers[] = 'authorization: Bearer ' . $authTok; $headers[] = 'anthropic-beta: oauth-2025-04-20'; }
else { fwrite(STDERR, "нет ключа: задай ANTHROPIC_API_KEY/ANTHROPIC_AUTH_TOKEN в окружении\nлибо положи ключ в файл engine/.anthropic-key (одной строкой; он в .gitignore)\n"); exit(2); }

/**
 * Разбор потока событий (SSE). Текст приходит кусками в content_block_delta,
 * причина остановки и расход — в message_delta.
 *
 * Состояние держим снаружи: curl отдаёт данные произвольными порциями, и
 * строка события запросто рвётся посередине между двумя вызовами.
 */
function sobratSSE(string $chunk, array &$st): void
{
    $st['хвост'] .= $chunk;
    while (($n = strpos($st['хвост'], "\n")) !== false) {
        $line = rtrim(substr($st['хвост'], 0, $n), "\r");
        $st['хвост'] = substr($st['хвост'], $n + 1);
        if (strncmp($line, 'data:', 5) !== 0) { continue; }
        $j = json_decode(trim(substr($line, 5)), true);
        if (!is_array($j)) { continue; }
        switch ($j['type'] ?? '') {
            case 'content_block_delta':
                // Текст берём только из text_delta: thinking_delta — это
                // рассуждение, в страницу оно попадать не должно.
                if (($j['delta']['type'] ?? '') === 'text_delta') { $st['текст'] .= $j['delta']['text'] ?? ''; }
                break;
            case 'message_start':
                $st['вход'] = (int) ($j['message']['usage']['input_tokens'] ?? 0);
                break;
            case 'message_delta':
                $st['стоп'] = $j['delta']['stop_reason'] ?? $st['стоп'];
                $st['выход'] = (int) ($j['usage']['output_tokens'] ?? $st['выход']);
                break;
            case 'error':
                $st['ошибка'] = ($j['error']['type'] ?? '?') . ': ' . ($j['error']['message'] ?? '');
                break;
        }
    }
}

// ── HTTP (raw curl; прокси и CA среды) с ретраями ──────────────────────────
// Транзиентные сбои (таймаут/обрыв curl, 429/500/502/503/504/529 перегруз)
// повторяем с экспоненциальным backoff — иначе один сбой убивает страницу.
$maxAttempts = (int)($opts['retries'] ?? 4);
$resp = false; $code = 0; $err = ''; $st = [];
for ($attempt = 1; $attempt <= $maxAttempts; $attempt++) {
    $st = ['хвост' => '', 'текст' => '', 'стоп' => '', 'вход' => 0, 'выход' => 0, 'ошибка' => ''];
    $syroj = '';
    $ch = curl_init('https://api.anthropic.com/v1/messages');
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $payload,
        CURLOPT_HTTPHEADER => $headers,
        CURLOPT_TIMEOUT => 1800,
        CURLOPT_CONNECTTIMEOUT => 30,
        // HTTP/2 поверх некоторых сборок curl на macOS роняет длинные ответы
        // тем же «unexpected eof». На 1.1 длинная генерация доходит целиком.
        CURLOPT_HTTP_VERSION => CURL_HTTP_VERSION_1_1,
    ]);
    if ($STREAM) {
        curl_setopt($ch, CURLOPT_WRITEFUNCTION, function ($ch, $chunk) use (&$st, &$syroj) {
            $syroj .= $chunk;                 // на случай, если это не поток, а JSON-ошибка
            sobratSSE($chunk, $st);
            return strlen($chunk);
        });
    } else {
        curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    }
    if ($proxy = (getenv('HTTPS_PROXY') ?: getenv('https_proxy'))) { curl_setopt($ch, CURLOPT_PROXY, $proxy); }
    if (is_file('/root/.ccr/ca-bundle.crt')) { curl_setopt($ch, CURLOPT_CAINFO, '/root/.ccr/ca-bundle.crt'); }
    $vyzov = curl_exec($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err  = curl_error($ch);
    // curl_close() с PHP 8.5 объявлен устаревшим и ничего не делает: дескриптор
    // освобождается сам, когда переменная выходит из области видимости.
    unset($ch);

    if ($STREAM) {
        $resp = $syroj;
        // Успех — когда текст дошёл и поток закрылся штатно.
        $ok = $err === '' && $code === 200 && $st['текст'] !== '' && $st['ошибка'] === '';
    } else {
        $resp = $vyzov;
        $ok = $vyzov !== false && $code === 200;
    }
    if ($ok) { break; }

    $retryable = ($err !== '') || in_array($code, [429, 500, 502, 503, 504, 529], true);
    if (!$retryable) { break; }
    if ($attempt < $maxAttempts) {
        $wait = (int) pow(2, $attempt); // 2,4,8,16с
        $chto = $err !== '' ? "curl $err" : "HTTP $code";
        fwrite(STDERR, "  попытка $attempt: $chto — повтор через {$wait}с\n");
        sleep($wait);
    }
}

if ($STREAM) {
    if ($st['ошибка'] !== '') { fwrite(STDERR, "ошибка API: {$st['ошибка']}\n"); exit(4); }
    if ($st['текст'] === '') {
        $chto = $err !== '' ? "curl $err" : "HTTP $code";
        fwrite(STDERR, "поток пуст после $maxAttempts попыток ($chto): " . substr((string) $resp, 0, 400) . "\n");
        exit(3);
    }
    if ($st['стоп'] === 'refusal') { fwrite(STDERR, "отказ модели (refusal)\n"); exit(5); }
    $html = trim($st['текст']);
    $data = ['stop_reason' => $st['стоп'], 'usage' => ['input_tokens' => $st['вход'], 'output_tokens' => $st['выход']]];
} else {
    if ($resp === false) { fwrite(STDERR, "curl не удался после $maxAttempts попыток: $err\n"); exit(3); }
    $data = json_decode((string) $resp, true);
    if ($code !== 200 || !is_array($data)) {
        fwrite(STDERR, "HTTP $code (после ретраев): " . substr((string) $resp, 0, 500) . "\n"); exit(4);
    }
    if (($data['stop_reason'] ?? '') === 'refusal') { fwrite(STDERR, "отказ модели (refusal)\n"); exit(5); }
    $html = '';
    foreach (($data['content'] ?? []) as $block) {
        if (($block['type'] ?? '') === 'text') { $html .= $block['text']; }
    }
    $html = trim($html);
}
if ($html === '') { fwrite(STDERR, "пустой ответ (stop_reason=" . ($data['stop_reason'] ?? '?') . ")\n"); exit(6); }

file_put_contents($outFile, $html . "\n");
$u = $data['usage'] ?? [];
$words = count(preg_split('~\s+~u', trim(strip_tags(preg_replace('~<script.*?</script>~su',' ',$html))), -1, PREG_SPLIT_NO_EMPTY));
fwrite(STDERR, sprintf("→ %s | ~%d слов | in %d / out %d ток. | stop=%s\n",
    $outFile, $words, (int)($u['input_tokens'] ?? 0), (int)($u['output_tokens'] ?? 0), $data['stop_reason'] ?? '?'));
