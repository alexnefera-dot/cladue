<?php
declare(strict_types=1);

/**
 * Тонкий боевой реалайзер: берёт ОДИН промпт (из PromptBuilder) и делает ОДИН
 * вызов Claude API → сохраняет готовую HTML-страницу. Без агентской обвязки,
 * без tool-use — чистый Messages API. Стоимость ≈ вход(промпт) + выход(страница).
 *
 *   php realize.php --prompt=path/to/prompt-main.md --out=path/to/main.html \
 *       [--model=claude-opus-4-8] [--max-tokens=16000] [--effort=medium] [--register=expert]
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
$model      = $opts['model'] ?? 'claude-opus-4-8';
$maxTokens  = (int)($opts['max-tokens'] ?? 16000);
$effort     = $opts['effort'] ?? 'medium';         // low|medium|high|xhigh|max
$register   = $opts['register'] ?? '';             // подсказка регистра (опц.)
$mode       = $opts['mode'] ?? 'realize';          // realize | fix | fix-v5

if ($promptFile === '' || !is_file($promptFile)) { fwrite(STDERR, "нет --prompt файла\n"); exit(1); }
if ($outFile === '') { fwrite(STDERR, "нет --out файла\n"); exit(1); }
$prompt = (string) file_get_contents($promptFile);

// ── системный промпт (роль + инварианты) ───────────────────────────────────
$regLine = $register !== '' ? "\nРегистр этой связки: {$register} — держи его на всей странице." : '';
if ($mode === 'fix-v5') {
    // Корректирующий проход v5. Отдельный от v4-шного: там на выходе целая
    // страница с JSON-LD и таблицами, здесь — только проза разделов, а
    // виджеты в вызов вообще не попадают и трогать их нечем.
    $system =
"Ты — корректирующий проход реалайзера v5. На входе БРИФ (что вылетело за цель корпуса) и ПРОЗА разделов страницы. Примени только правки из брифа, точечно.
Правила:
- Верни ТОЛЬКО исправленную прозу тем же набором тегов: <h2>, <h3>, <p>, <ul>/<li>, <strong>, <a href=\"…\">. Ни JSON-LD, ни таблиц, ни markdown, ни пояснений.
- Заголовки H2 оставь дословно: это закрытый список фабрики. H3 править можно.
- Число абзацев, пунктов списков и ссылочных адресов не меняй, если бриф прямо не просит об этом: структуру уже приняли.
- Числа из прозы не выдумывай и не заменяй: полосы RTP 92–99 %, бонус «до N%» 15–1000, вейджер до x90. Имя площадки — только %brand_name_ru%.
- Жанр прежний: на «ты», короткие фразы, рядом с обещанием — риск, без «эксклюзивный/лучший/уникальный» и без восклицательных знаков.{$regLine}";
} elseif ($mode === 'fix') {
    // корректирующий проход verify-loop: правим ТОЛЬКО перечисленное в брифе
    $system =
"Ты — корректирующий проход авто-реалайзера казино-контента. На входе БРИФ (что вылетело за цель) и ТЕКУЩИЙ HTML. Примени ТОЛЬКО правки из брифа, точечно.
Правила:
- Верни ТОЛЬКО исправленный HTML-фрагмент тела (как в оригинале: <p>/<h2>/<h3>/<ul>/<table>/<blockquote> + финальный JSON-LD). Без markdown и пояснений.
- Сохрани всё, что уже в норме: объём, структуру, таблицы, %brand_%-переменные, JSON-LD, дата-штамп, существующие ссылки без self-link.
- «ЦИФРЫ убери N» → перепиши N чисел ИЗ ПРОЗЫ словами; числа в таблицах/фактуре не трогай. «КЛАСТЕР ниже» → добавь абзац/пункты по теме СЛОВАМИ (без новых цифр). «КЛАСТЕР выше» → проредь ключи синонимами. «СУЩНОСТИ убери N» → убери N названий игр/провайдеров из прозы. «ТОШНОТА» → снизь повтор частых слов. H3/ВЫДЕЛЕНИЯ/FAQ/ОБЪЁМ — как сказано.
- Регистр не меняй.{$regLine}";
} else {
    $system =
"Ты — авто-реалайзер SEO-контента для казино под Яндекс. На входе — готовый ПРОМПТ с жёсткими целями; на выходе — ОДНА готовая HTML-страница.
Правила:
- Верни ТОЛЬКО HTML-фрагмент тела: <p>,<h2>,<h3>,<ul>/<li>,<table>,<blockquote> и финальный <script type=\"application/ld+json\">. Без <html>/<head>/<body>, без markdown-обёрток, без пояснений до или после.
- Бренд/домен/дата — строго переменные %brand_name_ru%, %brand_name_en%, %domain_name%, %date%. Не выдумывай имя бренда. Каждая страница начинается с «%brand_name_ru%. …».
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
$payload = json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);

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

// ── HTTP (raw curl; прокси и CA среды) с ретраями ──────────────────────────
// Транзиентные сбои (таймаут/обрыв curl, 429/500/502/503/504/529 перегруз)
// повторяем с экспоненциальным backoff — иначе один сбой убивает страницу.
$maxAttempts = (int)($opts['retries'] ?? 4);
$resp = false; $code = 0; $err = '';
for ($attempt = 1; $attempt <= $maxAttempts; $attempt++) {
    $ch = curl_init('https://api.anthropic.com/v1/messages');
    curl_setopt_array($ch, [
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $payload,
        CURLOPT_HTTPHEADER => $headers,
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_TIMEOUT => 900,
        CURLOPT_CONNECTTIMEOUT => 30,
    ]);
    if ($proxy = (getenv('HTTPS_PROXY') ?: getenv('https_proxy'))) { curl_setopt($ch, CURLOPT_PROXY, $proxy); }
    if (is_file('/root/.ccr/ca-bundle.crt')) { curl_setopt($ch, CURLOPT_CAINFO, '/root/.ccr/ca-bundle.crt'); }
    $resp = curl_exec($ch);
    $code = (int) curl_getinfo($ch, CURLINFO_HTTP_CODE);
    $err  = $resp === false ? curl_error($ch) : '';
    curl_close($ch);
    $retryable = ($resp === false) || in_array($code, [429, 500, 502, 503, 504, 529], true);
    if (!$retryable) break;
    if ($attempt < $maxAttempts) {
        $wait = (int) pow(2, $attempt); // 2,4,8,16с
        fwrite(STDERR, "  попытка $attempt: " . ($resp===false ? "curl $err" : "HTTP $code") . " — повтор через {$wait}с\n");
        sleep($wait);
    }
}
if ($resp === false) { fwrite(STDERR, "curl не удался после $maxAttempts попыток: $err\n"); exit(3); }

$data = json_decode((string)$resp, true);
if ($code !== 200 || !is_array($data)) {
    fwrite(STDERR, "HTTP $code (после ретраев): " . substr((string)$resp, 0, 500) . "\n"); exit(4);
}
if (($data['stop_reason'] ?? '') === 'refusal') { fwrite(STDERR, "отказ модели (refusal)\n"); exit(5); }

// ── собираем текст (thinking-блоки пустые/пропускаем) ──────────────────────
$html = '';
foreach (($data['content'] ?? []) as $block) {
    if (($block['type'] ?? '') === 'text') { $html .= $block['text']; }
}
$html = trim($html);
if ($html === '') { fwrite(STDERR, "пустой ответ (stop_reason=" . ($data['stop_reason'] ?? '?') . ")\n"); exit(6); }

file_put_contents($outFile, $html . "\n");
$u = $data['usage'] ?? [];
$words = count(preg_split('~\s+~u', trim(strip_tags(preg_replace('~<script.*?</script>~su',' ',$html))), -1, PREG_SPLIT_NO_EMPTY));
fwrite(STDERR, sprintf("→ %s | ~%d слов | in %d / out %d ток. | stop=%s\n",
    $outFile, $words, (int)($u['input_tokens'] ?? 0), (int)($u['output_tokens'] ?? 0), $data['stop_reason'] ?? '?'));
