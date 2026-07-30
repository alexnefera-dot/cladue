<?php
/**
 * stats.php — панель управления.
 * Вкладки:  Статистика  |  Кампании
 * Вход:     /stats.php — форма с паролем (сессия в куке), без ключа в URL.
 */

require __DIR__ . '/db.php';
$cfg  = require __DIR__ . '/config.php';
$PASS = $cfg['password'];

session_start();

// выход
if (isset($_GET['logout'])) {
    $_SESSION = [];
    session_destroy();
    header('Location: stats.php');
    exit;
}

// вход (POST с паролем)
$loginError = '';
if (($_POST['action'] ?? '') === 'login') {
    if (hash_equals($PASS, (string)($_POST['password'] ?? ''))) {
        session_regenerate_id(true);
        $_SESSION['auth'] = true;
        header('Location: stats.php');
        exit;
    }
    usleep(700000); // тормозим перебор
    $loginError = 'Неверный пароль';
}

// гейт: не авторизован — показываем форму входа и выходим
if (empty($_SESSION['auth'])) {
    http_response_code(($loginError) ? 401 : 200);
    ?><!doctype html><html lang="ru"><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex,nofollow"><title>Вход</title>
    <style>
      body{font:15px/1.5 system-ui,sans-serif;background:#f6f7f9;display:flex;min-height:100vh;
           align-items:center;justify-content:center;margin:0}
      .box{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:28px;width:300px;
           box-shadow:0 1px 3px #0000000d}
      h1{font-size:18px;margin:0 0 16px}
      input{width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #d1d5db;
            border-radius:8px;font:inherit;margin-bottom:12px}
      button{width:100%;padding:10px;border:0;border-radius:8px;background:#4f46e5;color:#fff;
             font:inherit;font-weight:600;cursor:pointer}
      .err{color:#b91c1c;font-size:13px;margin-bottom:10px}
    </style></head><body>
      <form class="box" method="post">
        <h1>Панель</h1>
        <?php if ($loginError): ?><div class="err"><?= htmlspecialchars($loginError) ?></div><?php endif; ?>
        <input type="hidden" name="action" value="login">
        <input type="password" name="password" placeholder="Пароль" autofocus required>
        <button type="submit">Войти</button>
      </form>
    </body></html><?php
    exit;
}

$key = ''; // ключ в URL больше не используется (вход по сессии)

// ---------- выгрузка CSV (до любого вывода) ----------
if (($_GET['export'] ?? '') !== '' && $_SERVER['REQUEST_METHOD'] === 'GET') {
    $exp = $_GET['export'];
    header('Content-Type: text/csv; charset=utf-8');
    header('Content-Disposition: attachment; filename="stats_' . $exp . '_' . date('Ymd_His') . '.csv"');
    $out = fopen('php://output', 'w');
    fwrite($out, "\xEF\xBB\xBF"); // BOM, чтобы Excel понял UTF-8
    if ($exp === 'daily') {
        fputcsv($out, ['date', 'clicks', 'unique', 'bots', 'regs']);
        foreach (daily_stats(30) as $r) fputcsv($out, [$r['d'], $r['humans'], $r['uniques'], $r['bots'], $r['regs']]);
    } elseif ($exp === 'clicks_full') {
        // подробно: каждый клик со всеми полями
        fputcsv($out, ['datetime', 'campaign', 'country', 'ip', 'clickid', 'source', 'is_bot', 'referer', 'user_agent']);
        $st = db()->query('SELECT ts, slug, country, ip, clickid, source, is_bot, referer, ua FROM clicks ORDER BY id');
        while ($r = $st->fetch(PDO::FETCH_ASSOC)) {
            fputcsv($out, [
                date('Y-m-d H:i:s', (int)$r['ts']), $r['slug'], $r['country'], $r['ip'],
                $r['clickid'], $r['source'], (int)$r['is_bot'] ? 'bot' : 'user', $r['referer'], $r['ua'],
            ]);
        }
    } else { // по кампаниям за сутки
        fputcsv($out, ['slug', 'name', 'clicks_humans', 'unique', 'bots', 'reg', 'dep', 'last_click']);
        $st = db()->prepare("SELECT cl.slug, COALESCE(c.name,'') name,
                SUM(CASE WHEN cl.is_bot=0 THEN 1 ELSE 0 END) humans,
                COUNT(DISTINCT CASE WHEN cl.is_bot=0 THEN cl.ip END) uniques,
                SUM(CASE WHEN cl.is_bot=1 THEN 1 ELSE 0 END) bots,
                MAX(cl.ts) last
            FROM clicks cl LEFT JOIN campaigns c ON c.slug=cl.slug
            WHERE cl.ts >= ? GROUP BY cl.slug ORDER BY humans DESC");
        $st->execute([time() - 86400]);
        $convAll = conversions_by_slug(time() - 86400);
        foreach ($st->fetchAll(PDO::FETCH_ASSOC) as $r) {
            $cv = $convAll[$r['slug']] ?? ['reg'=>0,'dep'=>0];
            fputcsv($out, [$r['slug'], $r['name'], $r['humans'], $r['uniques'], $r['bots'], $cv['reg'], $cv['dep'],
                           $r['last'] ? date('Y-m-d H:i', (int)$r['last']) : '']);
        }
    }
    fclose($out);
    exit;
}

$tab = in_array($_REQUEST['tab'] ?? 'stats', ['campaigns', 'settings'], true) ? $_REQUEST['tab'] : 'stats';
$checkResults = null;

// ---------- обработка действий (POST) ----------
if ($_SERVER['REQUEST_METHOD'] === 'POST' && ($_POST['action'] ?? '') === 'check') {
    // проверка ссылок — рендерим результат прямо здесь, без PRG-редиректа
    @set_time_limit(180);
    $checkResults = check_campaign_links();
    $tab = 'campaigns';
} elseif ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $action = $_POST['action'] ?? '';
    $msg = '';
    if ($action === 'add') {
        $err = add_campaign($_POST['slug'] ?? '', $_POST['name'] ?? '', $_POST['offer_url'] ?? '');
        $msg = $err === null ? 'Кампания добавлена' : ('Ошибка: ' . $err);
    } elseif ($action === 'update_offer') {
        $err = update_offer($_POST['id'] ?? 0, $_POST['offer_url'] ?? '');
        $msg = $err === null ? 'Офер обновлён' : ('Ошибка: ' . $err);
    } elseif ($action === 'rename') {
        rename_campaign($_POST['id'] ?? 0, $_POST['name'] ?? '');
        $msg = 'Название обновлено';
    } elseif ($action === 'delete') {
        delete_campaign($_POST['id'] ?? 0);
        $msg = 'Кампания удалена';
    } elseif ($action === 'bulk') {
        list($n, $errs) = bulk_import($_POST['bulk'] ?? '');
        $msg = "Добавлено: {$n}" . ($errs ? ('; ошибок: ' . count($errs) . ' — ' . implode('; ', array_slice($errs, 0, 5))) : '');
    } elseif ($action === 'replace_domain') {
        $res = replace_domain($_POST['old_domain'] ?? '', $_POST['new_domain'] ?? '');
        $msg = isset($res['err'])
            ? ('Ошибка: ' . $res['err'])
            : ('Домен заменён в кампаниях: ' . $res['changed']);
    } elseif ($action === 'update_prefix') {
        $res = update_offer_by_prefix($_POST['prefix'] ?? '', $_POST['offer_url'] ?? '');
        $msg = isset($res['err'])
            ? ('Ошибка: ' . $res['err'])
            : ('Оффер сменён у ' . $res['changed'] . ' из ' . $res['matched'] . ' кампаний по префиксу');
    } elseif ($action === 'clear_history') {
        $res = clear_history();
        $msg = 'История очищена: удалено кликов ' . $res['clicks'] . ', конверсий ' . $res['conversions'] . '. Кампании сохранены.';
        panel_cache_flush();   // данные удалены — кэш агрегатов больше не актуален
        $loc = 'stats.php?tab=settings&msg=' . rawurlencode($msg);
        header('Location: ' . $loc, true, 303);
        exit;
    }
    panel_cache_flush();   // кампании изменились — сбрасываем кэш сводок
    $loc = 'stats.php?tab=campaigns&msg=' . rawurlencode($msg);
    header('Location: ' . $loc, true, 303);
    exit;
}

// ---------- данные для отображения ----------
$pdo    = db();
$now    = time();
$host    = $_SERVER['HTTP_HOST'] ?? 'sitegrator.com';
$refBase = 'https://' . $host . '/go/';

// период: today / yesterday / 7d / 30d
$PERIODS = ['today'=>'Сегодня', 'yesterday'=>'Вчера', '7d'=>'7 дней', '30d'=>'30 дней'];
$periodKey = isset($_GET['period']) && isset($PERIODS[$_GET['period']]) ? $_GET['period'] : 'today';
$todayStart = strtotime('today');
switch ($periodKey) {
    case 'yesterday': $from = $todayStart - 86400; $to = $todayStart; break;
    case '7d':        $from = $now - 7 * 86400;    $to = $now + 1; break;
    case '30d':       $from = $now - 30 * 86400;   $to = $now + 1; break;
    default:          $from = $todayStart;         $to = $now + 1; break;
}
// хелпер: сохранить период в ссылках
$withPeriod = function ($url) use ($periodKey) {
    return $url . (strpos($url, '?') === false ? '?' : '&') . 'period=' . $periodKey;
};

// автоочистка старых кликов (не чаще раза в сутки)
maybe_cleanup($cfg['retention_days'] ?? 0);
heartbeat($cfg['downtime_gap'] ?? 300);

$detailSlug = ($tab === 'stats') ? trim((string)($_GET['slug'] ?? '')) : '';

$today = []; $sumHumans = 0; $sumUniq = 0; $sumUniqRu = 0; $sumBots = 0; $sumReg = 0; $sumRegRu = 0; $sumDep = 0; $sumRegUnlinked = 0;
$detailName = null; $detailDay = ['humans'=>0,'uniques'=>0,'bots'=>0]; $detailRows = [];
$detailConv = ['reg'=>0,'dep'=>0,'other'=>0]; $detailConvRows = [];
$detailPage = 1; $detailPages = 1; $detailTotal = 0;
$campaigns = []; $domains = [];
$daily = []; $recentConv = []; $pbLog = []; $geo = []; $geoCamp = []; $detailGeo = [];
$detailBots = [];
$detailSources = [];
$detailSourceGroups = [];

if ($tab === 'stats' && $detailSlug !== '') {
    // --- ПОДРОБНО по одной кампании ---
    $st = $pdo->prepare('SELECT name FROM campaigns WHERE slug = ?');
    $st->execute([$detailSlug]);
    $detailName = $st->fetchColumn();

    $st = $pdo->prepare("SELECT
            SUM(CASE WHEN is_bot=0 THEN 1 ELSE 0 END) AS humans,
            COUNT(DISTINCT CASE WHEN is_bot=0 THEN ip END) AS uniques,
            COUNT(DISTINCT CASE WHEN is_bot=0 AND country='RU' THEN ip END) AS uniques_ru,
            SUM(CASE WHEN is_bot=1 THEN 1 ELSE 0 END) AS bots
        FROM clicks WHERE slug = ? AND ts >= ? AND ts < ?");
    $st->execute([$detailSlug, $from, $to]);
    $detailDay = $st->fetch(PDO::FETCH_ASSOC) ?: ['humans'=>0,'uniques'=>0,'uniques_ru'=>0,'bots'=>0];

    // разбивка ботов больше не нужна — боты не логируются (log_bots=false)

    // пагинация кликов по 100 (в пределах периода)
    $perPage = 100;
    $detailPage = max(1, (int)($_GET['page'] ?? 1));
    $st = $pdo->prepare('SELECT COUNT(*) FROM clicks WHERE slug = ? AND ts >= ? AND ts < ?');
    $st->execute([$detailSlug, $from, $to]);
    $detailTotal = (int)$st->fetchColumn();
    $detailPages = max(1, (int)ceil($detailTotal / $perPage));
    $detailPage  = min($detailPage, $detailPages);
    $offset = ($detailPage - 1) * $perPage;

    $st = $pdo->prepare("SELECT ts, ip, ua, referer, source, is_bot, clickid, country
                         FROM clicks WHERE slug = ? AND ts >= ? AND ts < ? ORDER BY id DESC LIMIT $perPage OFFSET $offset");
    $st->execute([$detailSlug, $from, $to]);
    $detailRows = $st->fetchAll(PDO::FETCH_ASSOC);

    $cv = conversions_by_slug($from, $to);
    $detailConv = $cv[$detailSlug] ?? ['reg'=>0,'dep'=>0,'other'=>0,'reg_ru'=>0];

    // конверсии (реги/депы) этой кампании за период, с деталями клика
    $st = $pdo->prepare('SELECT cv.ts, cv.status, cv.payout, cv.clickid, cv.ip,
            (SELECT referer FROM clicks WHERE clickid = cv.clickid ORDER BY id DESC LIMIT 1) AS referer,
            (SELECT ua      FROM clicks WHERE clickid = cv.clickid ORDER BY id DESC LIMIT 1) AS ua,
            (SELECT source  FROM clicks WHERE clickid = cv.clickid ORDER BY id DESC LIMIT 1) AS source,
            (SELECT country FROM clicks WHERE clickid = cv.clickid ORDER BY id DESC LIMIT 1) AS country
        FROM conversions cv WHERE cv.slug = ? AND cv.ts >= ? AND cv.ts < ? ORDER BY cv.id DESC LIMIT 200');
    $st->execute([$detailSlug, $from, $to]);
    $detailConvRows = $st->fetchAll(PDO::FETCH_ASSOC);

    // гео по уникам этой кампании за период
    $detailGeo = geo_by_campaign($from, $detailSlug, $to)[$detailSlug] ?? [];
    $detailSources = sources_by_campaign($detailSlug, $from, $to);
    $detailSourceGroups = sources_grouped_by_campaign($detailSlug, $from, $to);

} elseif ($tab === 'stats') {
    // --- СВОДКА за период: все кампании с кликами ---
    // Сводка кэшируется до следующего импорта: клики попадают в базу только
    // кроном, поэтому пересчитывать её на каждую перезагрузку незачем.
    $today = panel_cache("summary_$periodKey", function () use ($pdo, $from, $to) {
        $st = $pdo->prepare("
            SELECT cl.slug, COALESCE(c.name,'') AS name,
                   SUM(CASE WHEN cl.is_bot=0 THEN 1 ELSE 0 END)                       AS humans,
                   COUNT(DISTINCT CASE WHEN cl.is_bot=0 THEN cl.ip END)               AS uniques,
                   COUNT(DISTINCT CASE WHEN cl.is_bot=0 AND cl.country='RU' THEN cl.ip END) AS uniques_ru,
                   SUM(CASE WHEN cl.is_bot=1 THEN 1 ELSE 0 END)                       AS bots,
                   MAX(cl.ts)                                                         AS last_ts
            FROM clicks cl
            LEFT JOIN campaigns c ON c.slug = cl.slug
            WHERE cl.ts >= ? AND cl.ts < ?
            GROUP BY cl.slug
            ORDER BY humans DESC, bots DESC
        ");
        $st->execute([$from, $to]);
        return $st->fetchAll(PDO::FETCH_ASSOC);
    });

    // конверсии за период по кампаниям (с RU-разбивкой) — для таблицы
    $conv = conversions_by_slug($from, $to);
    // ИТОГО конверсий за период — ВСЕ (включая непривязанные) — для счётчиков в шапке
    $convTot = conversions_totals($from, $to);
    $sumHumans = $sumUniq = $sumUniqRu = $sumBots = 0;
    foreach ($today as &$r) {
        $c = $conv[$r['slug']] ?? ['reg'=>0,'dep'=>0,'reg_ru'=>0];
        $r['reg'] = $c['reg']; $r['dep'] = $c['dep'];
        $r['reg_ru'] = $c['reg_ru'] ?? 0;
        $sumHumans += (int)$r['humans']; $sumUniq += (int)$r['uniques']; $sumBots += (int)$r['bots'];
        $sumUniqRu += (int)$r['uniques_ru'];
    }
    unset($r);
    // счётчики шапки берём из ИТОГО (совпадают с графиком и «Последними постбеками»)
    $sumReg   = $convTot['reg'];
    $sumRegRu = $convTot['reg_ru'];
    $sumDep   = $convTot['dep'];
    $sumRegUnlinked = $convTot['reg_unlinked'];

    // Тяжёлые агрегаты — из кэша (обновляются вместе с импортом).
    // recent_conversions не кэшируем: замер показал ~5 мс, смысла нет.
    $daily      = panel_cache('daily30',           fn() => daily_stats(30));
    $recentConv = recent_conversions(50);
    $geo        = panel_cache("geo_$periodKey",     fn() => geo_stats($from, $to));
    $geoCamp    = panel_cache("geocamp_$periodKey", fn() => geo_by_campaign($from, null, $to));

} else {
    // --- вкладка «Кампании»: только справочник кампаний (без счётчиков кликов) ---
    $campaigns = $pdo->query('SELECT id, slug, name, offer_url, updated_at
                              FROM campaigns ORDER BY name, slug')->fetchAll(PDO::FETCH_ASSOC);
    $domains = domain_stats();
}

function h($s)  { return htmlspecialchars((string)$s, ENT_QUOTES, 'UTF-8'); }
function dt($t) { return $t ? date('Y-m-d H:i', (int)$t) : '—'; }
function is_suspicious_ua($ua) {
    $ua = trim((string)$ua);
    if ($ua === '') return true;
    $needles = ['bot','crawl','spider','curl','wget','python','java/','go-http',
                'okhttp','headless','phantom','scrapy','http-client','libwww','axios','node-fetch'];
    $low = strtolower($ua);
    foreach ($needles as $n) if (strpos($low, $n) !== false) return true;
    return false;
}
function tab_url($t, $key = null) { return 'stats.php?tab=' . $t; }

$msg = $_GET['msg'] ?? '';
?>
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Панель — sitegrator.com</title>
<style>
  :root { --line:#e7e7ee; --muted:#6b7280; --accent:#4f46e5; --bot:#e04444; }
  * { box-sizing: border-box; }
  body { font: 15px/1.5 system-ui, -apple-system, sans-serif; margin: 0; color: #1a1a2e; background: #f6f7fb; }
  .wrap { max-width: 1180px; margin: 0 auto; padding: 24px 20px 60px; }
  h1 { font-size: 18px; margin: 28px 0 4px; }
  h1:first-child { margin-top: 0; }
  .muted { color: var(--muted); font-size: 13px; margin-bottom: 16px; }
  .tabs { display: flex; gap: 8px; border-bottom: 2px solid var(--line); margin-bottom: 24px; }
  .tabs a { padding: 10px 18px; text-decoration: none; color: var(--muted); font-weight: 600;
            border-bottom: 2px solid transparent; margin-bottom: -2px; }
  .tabs a.active { color: var(--accent); border-bottom-color: var(--accent); }
  .note { background: #ecfdf5; border: 1px solid #a7f3d0; color: #065f46; padding: 10px 14px;
          border-radius: 8px; margin-bottom: 20px; font-size: 14px; }
  .errbox { background:#fef2f2; border:1px solid #fecaca; color:#991b1b; padding:12px 16px;
            border-radius:8px; margin-bottom:14px; font-size:14px; }
  .warnbox { background:#fffbeb; border:1px solid #fde68a; color:#92400e; padding:12px 16px;
             border-radius:8px; margin-bottom:14px; font-size:14px; }
  .errbox ul, .warnbox ul { margin:8px 0 4px; padding-left:20px; }
  .errbox li, .warnbox li { margin:3px 0; }
  .errbox code, .warnbox code { background:#0000000d; }
  table { border-collapse: collapse; width: 100%; background: #fff; margin-bottom: 28px;
          border: 1px solid var(--line); border-radius: 10px; overflow: hidden; table-layout: auto; }
  th, td { padding: 8px 10px; text-align: left; border-bottom: 1px solid var(--line); vertical-align: middle; }
  th { background: #fafafe; font-weight: 600; font-size: 13px; color: #444; }
  tr:last-child td { border-bottom: none; }
  td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
  code { background: #f0f0f5; padding: 2px 6px; border-radius: 5px; font-size: 13px; }
  .ref { color: var(--muted); font-size: 12px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  tr.bot { background: #fff4f4; }
  tr.bot td:first-child { box-shadow: inset 3px 0 0 var(--bot); }
  table.rowlink tbody tr[data-href] { cursor: pointer; }
  table.rowlink tbody tr[data-href]:hover { background: #f3f4ff; }
  .badge { display: inline-block; font-size: 11px; padding: 1px 7px; border-radius: 10px; background: var(--bot); color: #fff; }
  .tag-ok  { display:inline-block; font-size:11px; padding:1px 7px; border-radius:10px; background:#dcfce7; color:#166534; }
  .tag-ref { display:inline-block; font-size:11px; padding:1px 7px; border-radius:10px; background:#fef3c7; color:#92400e; }
  input[type=text], input[type=url], textarea {
    width: 100%; padding: 7px 10px; border: 1px solid var(--line); border-radius: 7px;
    font: inherit; font-size: 14px; background: #fff; }
  textarea { resize: vertical; min-height: 90px; font-family: ui-monospace, monospace; font-size: 13px; }
  button { font: inherit; font-weight: 600; padding: 7px 14px; border: none; border-radius: 7px;
           background: var(--accent); color: #fff; cursor: pointer; }
  button.ghost { background: #eef0f6; color: #333; }
  button.danger { background: #fff; color: var(--bot); border: 1px solid #f0c4c4; }
  .reflink { display: flex; gap: 6px; align-items: center; }
  .reflink input { font-family: ui-monospace, monospace; font-size: 12px; color: #333; }
  .inline { display: flex; gap: 6px; align-items: center; }
  .card { background:#fff; border:1px solid var(--line); border-radius:10px; padding:18px; margin-bottom:24px; }
  .card h2 { font-size: 15px; margin: 0 0 12px; }
  .grid3 { display: grid; grid-template-columns: 1fr 1fr 2fr auto; gap: 8px; align-items: end; }
  label.f { font-size: 12px; color: var(--muted); display: block; margin-bottom: 3px; }
  @media (max-width: 700px) { .grid3 { grid-template-columns: 1fr; } .ref { max-width: 150px; } }

  /* переключатель периода */
  .period { display:flex; gap:6px; margin:0 0 18px; flex-wrap:wrap; }
  .period a { padding:6px 14px; border:1px solid var(--line); border-radius:20px; text-decoration:none;
              color:var(--muted); font-size:13px; font-weight:600; background:#fff; }
  .period a.on { background:var(--accent); color:#fff; border-color:var(--accent); }
  /* сортируемые заголовки */
  table.sortable th[data-sort] { cursor:pointer; user-select:none; white-space:nowrap; }
  table.sortable th[data-sort]:hover { color:var(--accent); }
  table.sortable th[data-sort]::after { content:'↕'; opacity:.35; font-size:10px; margin-left:4px; }
  table.sortable th.asc::after  { content:'↑'; opacity:.9; }
  table.sortable th.desc::after { content:'↓'; opacity:.9; }
  /* плашка ботов */
  .bots-box { display:flex; flex-wrap:wrap; gap:8px; margin:0 0 24px; }
  .bots-box .chip { background:#fff4f4; border:1px solid #f3cccc; color:#92400e; border-radius:8px;
                    padding:5px 10px; font-size:13px; }
  .bots-box .chip b { color:var(--bot); }
  .bots-box .none { color:var(--muted); font-size:13px; }
  /* тултип графика */
  #chartTip { position:fixed; pointer-events:none; z-index:50; background:#1a1a2e; color:#fff;
              font-size:12px; line-height:1.45; padding:8px 10px; border-radius:8px; opacity:0;
              transition:opacity .08s; white-space:nowrap; box-shadow:0 4px 14px #0003; }
  #chartTip b { font-weight:700; }
  .chart-wrap svg .hot { fill:transparent; cursor:crosshair; }
  .chart-wrap svg .vline { stroke:#0002; stroke-width:1; visibility:hidden; }
</style>
</head>
<body>
<div class="wrap">

  <div class="tabs">
    <a href="<?= h(tab_url('stats', $key)) ?>"     class="<?= $tab==='stats'?'active':'' ?>">Статистика</a>
    <a href="<?= h(tab_url('campaigns', $key)) ?>" class="<?= $tab==='campaigns'?'active':'' ?>">Кампании</a>
    <a href="<?= h(tab_url('settings', $key)) ?>"  class="<?= $tab==='settings'?'active':'' ?>">Настройки</a>
    <a href="stats.php?logout=1" style="margin-left:auto">Выход</a>
  </div>

  <?php if ($msg !== ''): ?><div class="note"><?= h($msg) ?></div><?php endif; ?>

<?php if ($tab === 'stats'):
  $pbase = tab_url('stats', $key) . ($detailSlug !== '' ? '&slug=' . rawurlencode($detailSlug) : '');
?>
  <div class="period">
    <?php foreach ($PERIODS as $pk => $plabel): ?>
      <a href="<?= h($pbase . '&period=' . $pk) ?>" class="<?= $periodKey===$pk?'on':'' ?>"><?= h($plabel) ?></a>
    <?php endforeach; ?>
  </div>
<?php endif; ?>

<?php if ($tab === 'stats' && $detailSlug !== ''): ?>

  <h1>Кампания: <?= h($detailName ?: $detailSlug) ?></h1>
  <div class="muted">
    <code><?= h($detailSlug) ?></code> · рефка <code><?= h($refBase . $detailSlug) ?></code>
    <a href="<?= h($withPeriod(tab_url('stats', $key))) ?>" style="margin-left:8px">← ко всем кампаниям</a>
  </div>

  <div class="bots-box">
    <span class="chip" style="background:#ecfdf5;border-color:#a7f3d0;color:#166534;font-size:14px">Юзеры (уники): <b style="color:#16a34a"><?= (int)$detailDay['uniques'] ?></b></span>
    <span class="chip" style="background:#faf5ff;border-color:#e9d5ff;color:#7e22ce">Реги: <b style="color:#a855f7"><?= (int)$detailConv['reg'] ?></b></span>
    <span class="chip" style="background:#f0fdf4;border-color:#bbf7d0;color:#15803d">Депы: <b style="color:#16a34a"><?= (int)$detailConv['dep'] ?></b></span>
    <span class="chip" style="background:#f6f7f9;border-color:#e2e4ea;color:#666">Клики (всего): <b><?= (int)$detailDay['humans'] ?></b></span>
  </div>
  <div class="bots-box" style="margin-top:-8px">
    <span class="chip" style="background:#eff6ff;border-color:#bfdbfe;color:#1e40af;font-size:14px" title="Только юзеры со страной RU (по CF-IPCountry)">🇷🇺 <b>RU</b>: Уники <b style="color:#1d4ed8"><?= (int)$detailDay['uniques_ru'] ?></b> · Реги <b style="color:#7e22ce"><?= (int)($detailConv['reg_ru'] ?? 0) ?></b></span>
  </div>

  <h2 style="margin:18px 0 8px;font-size:16px">Источники (<?= h($PERIODS[$periodKey]) ?>)</h2>
  <div class="muted">Сгруппировано по корневому домену. Нажми на строку группы (▶), чтобы раскрыть поддомены. Источник берётся из <code>?s=</code> в рефке, а если параметра нет — из HTTP Referer. «(прямые)» — переходы без источника.</div>
  <?php
    $srcTotalU = 0; foreach ($detailSourceGroups as $g) $srcTotalU += (int)$g['uniques'];
  ?>
  <table class="src-group-table">
    <thead><tr>
      <th style="width:32px"></th>
      <th>Источник / домен</th>
      <th class="num">Клики</th>
      <th class="num">Уники</th>
      <th class="num">Реги</th>
      <th class="num">Доля уник.</th>
    </tr></thead>
    <tbody>
      <?php foreach ($detailSourceGroups as $gi => $g):
        $multi = count($g['subs']) > 1 || ($g['subs'][0]['source'] ?? '') !== $g['root'];
      ?>
      <tr class="src-grp<?= $multi ? ' has-subs' : '' ?>"<?= $multi ? ' data-grp="'.$gi.'"' : '' ?>>
        <td class="src-toggle"><?= $multi ? '<span class="tri">▶</span>' : '' ?></td>
        <td>
          <?= $g['root'] === '(прямые)' ? '<span class="muted">(прямые)</span>' : '<b><code>'.h($g['root']).'</code></b>' ?>
          <?php if ($multi): ?><span class="muted" style="font-size:11px"> · <?= count($g['subs']) ?> подд.</span><?php endif; ?>
        </td>
        <td class="num"><?= (int)$g['clicks'] ?></td>
        <td class="num"><b><?= (int)$g['uniques'] ?></b></td>
        <td class="num"><?= (int)$g['regs'] ? '<b style="color:#a855f7">'.(int)$g['regs'].'</b>' : '0' ?></td>
        <td class="num"><?= $srcTotalU ? round($g['uniques'] * 100 / $srcTotalU) . '%' : '—' ?></td>
      </tr>
      <?php if ($multi): foreach ($g['subs'] as $s): ?>
      <tr class="src-sub src-sub-<?= $gi ?>" style="display:none">
        <td></td>
        <td style="padding-left:28px"><span class="muted">└</span> <code style="font-size:12px"><?= h($s['source']) ?></code></td>
        <td class="num" style="color:#888"><?= (int)$s['clicks'] ?></td>
        <td class="num"><?= (int)$s['uniques'] ?></td>
        <td class="num"><?= (int)$s['regs'] ? '<span style="color:#a855f7">'.(int)$s['regs'].'</span>' : '0' ?></td>
        <td class="num" style="color:#aaa"><?= $srcTotalU ? round($s['uniques'] * 100 / $srcTotalU) . '%' : '—' ?></td>
      </tr>
      <?php endforeach; endif; ?>
      <?php endforeach; ?>
      <?php if (!$detailSourceGroups): ?><tr><td colspan="6">За период данных нет.</td></tr><?php endif; ?>
    </tbody>
  </table>
  <style>
    .src-group-table{width:100%;border-collapse:collapse;font-size:14px}
    .src-group-table th{text-align:left;padding:8px 10px;border-bottom:2px solid #e2e4ea;color:#666;font-weight:600;font-size:13px}
    .src-group-table th.num{text-align:right}
    .src-group-table td{padding:7px 10px;border-bottom:1px solid #f0f1f4}
    .src-group-table td.num{text-align:right}
    .src-grp.has-subs{cursor:pointer}
    .src-grp.has-subs:hover{background:#f6f7fb}
    .src-toggle{width:32px;text-align:center;color:#999}
    .src-grp .tri{display:inline-block;transition:transform .15s;font-size:10px}
    .src-grp.open .tri{transform:rotate(90deg)}
    .src-sub{background:#fafbfc}
    .src-sub:hover{background:#f4f6f8}
  </style>
  <script>
  (function(){
    document.querySelectorAll('.src-grp.has-subs').forEach(function(row){
      row.addEventListener('click', function(){
        var gi = row.getAttribute('data-grp');
        var subs = document.querySelectorAll('.src-sub-' + gi);
        var open = row.classList.toggle('open');
        subs.forEach(function(s){ s.style.display = open ? '' : 'none'; });
      });
    });
  })();
  </script>

  <h2 style="margin:18px 0 8px;font-size:16px">Гео (уники, <?= h($PERIODS[$periodKey]) ?>)</h2>
  <?php $geoTotal = 0; foreach ($detailGeo as $g) $geoTotal += $g['uniques']; ?>
  <table class="sortable">
    <thead><tr><th data-sort="text">Страна</th><th class="num" data-sort="num">Уники</th><th class="num" data-sort="num">Клики</th><th class="num" data-sort="num">Доля</th></tr></thead>
    <tbody>
      <?php foreach ($detailGeo as $g): ?>
      <tr>
        <td><?= country_flag($g['country']) ?> <?= h($g['country']) ?></td>
        <td class="num"><?= (int)$g['uniques'] ?></td>
        <td class="num"><?= (int)$g['clicks'] ?></td>
        <td class="num"><?= $geoTotal ? round($g['uniques'] * 100 / $geoTotal) . '%' : '—' ?></td>
      </tr>
      <?php endforeach; ?>
      <?php if (!$detailGeo): ?><tr><td colspan="4">За период данных нет.</td></tr><?php endif; ?>
    </tbody>
  </table>

  <h2 style="margin:18px 0 8px;font-size:16px">Конверсии (реги / депы)</h2>
  <div class="muted">Реферер, User-Agent, источник и страна берутся из клика, к которому привязана конверсия (по clickid).</div>
  <table class="sortable">
    <thead><tr><th data-sort="text">Время</th><th data-sort="text">Статус</th><th class="num" data-sort="num">Сумма</th><th data-sort="text">clickid</th><th data-sort="text">Страна</th><th data-sort="text">Источник</th><th data-sort="text">Реферер</th><th data-sort="text">User-Agent</th><th data-sort="text">IP</th></tr></thead>
    <tbody>
      <?php foreach ($detailConvRows as $r): $isreg = in_array($r['status'],['reg','registration','lead'],true); ?>
      <tr>
        <td><?= dt($r['ts']) ?></td>
        <td><?= $isreg ? '<b style="color:#a855f7">'.h($r['status']).'</b>' : '<b style="color:#16a34a">'.h($r['status']).'</b>' ?></td>
        <td class="num"><?= (float)$r['payout'] ? h($r['payout']) : '—' ?></td>
        <td><code style="font-size:11px"><?= h($r['clickid']) ?></code></td>
        <td><?= ($r['country'] ?? '') !== '' ? country_flag($r['country']).' '.h($r['country']) : '—' ?></td>
        <td><?= h(($r['source'] ?? '') !== '' ? $r['source'] : '—') ?></td>
        <td class="ref" title="<?= h($r['referer'] ?? '') ?>"><?= h(($r['referer'] ?? '') !== '' ? $r['referer'] : '—') ?></td>
        <td class="ref" title="<?= h($r['ua'] ?? '') ?>"><?= h(($r['ua'] ?? '') !== '' ? $r['ua'] : '—') ?></td>
        <td><?= h($r['ip']) ?></td>
      </tr>
      <?php endforeach; ?>
      <?php if (!$detailConvRows): ?><tr><td colspan="9">Конверсий по этой кампании за период нет.</td></tr><?php endif; ?>
    </tbody>
  </table>

  <h2 style="margin:18px 0 8px;font-size:16px">Клики <span class="muted" style="font-weight:400">(всего <?= (int)$detailTotal ?>, стр. <?= $detailPage ?>/<?= $detailPages ?>)</span></h2>
  <table class="sortable">
    <thead><tr><th data-sort="text">Время</th><th data-sort="text">Страна</th><th data-sort="text">IP</th><th data-sort="text">clickid</th><th data-sort="text">User-Agent</th><th data-sort="text">Реферер</th><th data-sort="text">Источник</th></tr></thead>
    <tbody>
      <?php foreach ($detailRows as $r): ?>
      <tr>
        <td><?= dt($r['ts']) ?></td>
        <td><?= ($r['country'] ?? '') !== '' ? country_flag($r['country']).' '.h($r['country']) : '—' ?></td>
        <td><?= h($r['ip']) ?></td>
        <td><code style="font-size:11px"><?= h($r['clickid'] ?? '') ?: '—' ?></code></td>
        <td class="ref" title="<?= h($r['ua']) ?>"><?= h($r['ua'] ?: '—') ?></td>
        <td class="ref" title="<?= h($r['referer']) ?>"><?= h($r['referer'] ?: '—') ?></td>
        <td><?= h(($r['source'] ?? '') !== '' ? $r['source'] : '—') ?></td>
      </tr>
      <?php endforeach; ?>
      <?php if (!$detailRows): ?><tr><td colspan="7">Кликов по этой кампании за период нет.</td></tr><?php endif; ?>
    </tbody>
  </table>
  <?php if ($detailPages > 1):
    $base = tab_url('stats',$key) . '&slug=' . rawurlencode($detailSlug) . '&period=' . $periodKey . '&page=';
  ?>
  <div style="margin:8px 0 24px;display:flex;gap:8px;align-items:center">
    <?php if ($detailPage > 1): ?><a href="<?= h($base . ($detailPage-1)) ?>">← назад</a><?php endif; ?>
    <span class="muted">стр. <?= $detailPage ?> из <?= $detailPages ?></span>
    <?php if ($detailPage < $detailPages): ?><a href="<?= h($base . ($detailPage+1)) ?>">вперёд →</a><?php endif; ?>
  </div>
  <?php endif; ?>

<?php elseif ($tab === 'stats'): ?>

  <h1>Статистика: <?= h($PERIODS[$periodKey]) ?></h1>
  <?php $botsCnt = bots_counter_read(); ?>
  <div class="bots-box">
    <span class="chip" style="background:#ecfdf5;border-color:#a7f3d0;color:#166534;font-size:14px">Юзеры (уники): <b style="color:#16a34a"><?= (int)$sumUniq ?></b></span>
    <span class="chip" style="background:#faf5ff;border-color:#e9d5ff;color:#7e22ce" title="Все регистрации за период. В скобках — не привязанные к кампании (постбек пришёл, но clickid не совпал с кликом).">Реги: <b style="color:#a855f7"><?= (int)$sumReg ?></b><?php if ($sumRegUnlinked > 0): ?> <span style="color:var(--muted)">(не привязано: <?= (int)$sumRegUnlinked ?>)</span><?php endif; ?></span>
    <span class="chip" style="background:#f0fdf4;border-color:#bbf7d0;color:#15803d">Депы: <b style="color:#16a34a"><?= (int)$sumDep ?></b></span>
    <span class="chip" style="background:#f6f7f9;border-color:#e2e4ea;color:#666">Клики (всего): <b><?= (int)$sumHumans ?></b></span>
    <span class="chip" style="background:#fff4f4;border-color:#f3cccc;color:#92400e" title="Ботов отбито (в базу не пишутся). Сегодня / всего с момента установки.">Отбито ботов: <b style="color:var(--bot)"><?= (int)$botsCnt['today'] ?></b> <span style="color:var(--muted)">· всего <?= (int)$botsCnt['total'] ?></span></span>
  </div>
  <div class="bots-box" style="margin-top:-8px">
    <span class="chip" style="background:#eff6ff;border-color:#bfdbfe;color:#1e40af;font-size:14px" title="Только юзеры со страной RU (по CF-IPCountry)">🇷🇺 <b>RU</b>: Уники <b style="color:#1d4ed8"><?= (int)$sumUniqRu ?></b> · Реги <b style="color:#7e22ce"><?= (int)$sumRegRu ?></b></span>
  </div>
  <div class="muted">
    Все кампании с кликами за выбранный период. Клик по строке — подробности кампании. Колонки сортируются — кликни по заголовку.
  </div>

  <?php
    // --- график за 30 дней (inline SVG, без внешних библиотек) ---
    $n = count($daily);
    $todayRow = $n ? $daily[$n-1] : ['humans'=>0,'uniques'=>0,'bots'=>0,'regs'=>0];
    $maxV = 1;
    foreach ($daily as $r) $maxV = max($maxV, $r['uniques'], $r['regs'], $r['uniques_ru'], $r['regs_ru']);
    $W=920; $H=300; $pl=46; $pr=14; $pt=18; $pb=34;
    $plotW = $W-$pl-$pr; $plotH = $H-$pt-$pb;
    $xat = function($i) use($pl,$plotW,$n){ return $pl + ($n<=1?0:$plotW*$i/($n-1)); };
    $yat = function($v) use($pt,$plotH,$maxV){ return $pt + $plotH - ($plotH*$v/$maxV); };
    $series = [
      ['key'=>'uniques',    'color'=>'#16a34a', 'label'=>'Юзеры (уники)'],
      ['key'=>'uniques_ru', 'color'=>'#2563eb', 'label'=>'🇷🇺 Юзеры'],
      ['key'=>'regs',       'color'=>'#a855f7', 'label'=>'Реги'],
      ['key'=>'regs_ru',    'color'=>'#7e22ce', 'label'=>'🇷🇺 Реги'],
    ];
  ?>
  <h1 style="margin-top:8px">График за месяц</h1>
  <div class="muted">Наведи на график — покажет цифры за день. По оси X — дни, по Y — количество.</div>
  <div class="card chart-wrap" style="overflow-x:auto">
    <div style="margin-bottom:8px;font-size:13px">
      <?php foreach ($series as $s): ?>
        <span style="display:inline-block;margin-right:14px"><span style="display:inline-block;width:11px;height:11px;border-radius:2px;background:<?= $s['color'] ?>;vertical-align:middle"></span> <?= h($s['label']) ?></span>
      <?php endforeach; ?>
    </div>
    <?php
      // данные для JS-тултипа
      $chartData = [];
      foreach ($daily as $i => $r) {
        $chartData[] = [
          'd' => date('d.m.Y', strtotime($r['d'])),
          'x' => round($xat($i), 1),
          'h' => (int)$r['humans'], 'u' => (int)$r['uniques'], 'r' => (int)$r['regs'], 'b' => (int)$r['bots'],
          'uru' => (int)$r['uniques_ru'], 'rru' => (int)$r['regs_ru'],
          'yh'  => round($yat($r['humans']),1),     'yu'  => round($yat($r['uniques']),1),
          'yr'  => round($yat($r['regs']),1),       'yb'  => round($yat($r['bots']),1),
          'yuru'=> round($yat($r['uniques_ru']),1), 'yrru'=> round($yat($r['regs_ru']),1),
        ];
      }
      $band = $n > 1 ? $plotW / ($n - 1) : $plotW;
    ?>
    <svg id="chart" viewBox="0 0 <?= $W ?> <?= $H ?>" style="width:100%;min-width:680px;height:auto;font:11px system-ui">
      <?php for ($g=0; $g<=2; $g++): $val=round($maxV*$g/2); $yy=$yat($val); ?>
        <line x1="<?= $pl ?>" y1="<?= $yy ?>" x2="<?= $W-$pr ?>" y2="<?= $yy ?>" stroke="#eee" />
        <text x="<?= $pl-6 ?>" y="<?= $yy+3 ?>" text-anchor="end" fill="#999"><?= $val ?></text>
      <?php endfor; ?>
      <?php foreach ($daily as $i=>$r): if ($i%5===0 || $i===$n-1): $xx=$xat($i); ?>
        <text x="<?= $xx ?>" y="<?= $H-$pb+16 ?>" text-anchor="middle" fill="#999"><?= h(date('d.m', strtotime($r['d']))) ?></text>
      <?php endif; endforeach; ?>
      <line class="vline" id="chartVline" x1="0" y1="<?= $pt ?>" x2="0" y2="<?= $H-$pb ?>"></line>
      <?php foreach ($series as $s):
        $pts=[]; foreach ($daily as $i=>$r) $pts[]=round($xat($i),1).','.round($yat($r[$s['key']]),1);
      ?>
        <polyline fill="none" stroke="<?= $s['color'] ?>" stroke-width="2" points="<?= implode(' ',$pts) ?>" />
      <?php endforeach; ?>
      <!-- подсвеченные точки (скрыты до наведения) -->
      <g id="chartDots" style="visibility:hidden">
        <circle id="dotU" r="3.5" fill="#16a34a"></circle>
        <circle id="dotURu" r="3.5" fill="#2563eb"></circle>
        <circle id="dotR" r="3.5" fill="#a855f7"></circle>
        <circle id="dotRRu" r="3.5" fill="#7e22ce"></circle>
      </g>
      <!-- зоны наведения по дням -->
      <?php foreach ($chartData as $i=>$c): ?>
        <rect class="hot" x="<?= round($c['x'] - $band/2,1) ?>" y="<?= $pt ?>" width="<?= round($band,1) ?>" height="<?= $plotH ?>" data-i="<?= $i ?>"></rect>
      <?php endforeach; ?>
    </svg>
  </div>
  <div id="chartTip"></div>
  <script>
  (function(){
    var data = <?= json_encode($chartData, JSON_UNESCAPED_UNICODE) ?>;
    var svg = document.getElementById('chart'); if(!svg) return;
    var tip = document.getElementById('chartTip');
    var vline = document.getElementById('chartVline');
    var dots = document.getElementById('chartDots');
    var dU=document.getElementById('dotU'), dURu=document.getElementById('dotURu'),
        dR=document.getElementById('dotR'), dRRu=document.getElementById('dotRRu');
    function show(i, evt){
      var c=data[i]; if(!c) return;
      vline.setAttribute('x1',c.x); vline.setAttribute('x2',c.x); vline.style.visibility='visible';
      dU.setAttribute('cx',c.x);   dU.setAttribute('cy',c.yu);
      dURu.setAttribute('cx',c.x); dURu.setAttribute('cy',c.yuru);
      dR.setAttribute('cx',c.x);   dR.setAttribute('cy',c.yr);
      dRRu.setAttribute('cx',c.x); dRRu.setAttribute('cy',c.yrru);
      dots.style.visibility='visible';
      tip.innerHTML='<b>'+c.d+'</b><br>'+
        '<span style="color:#6ee7a8">Юзеры:</span> '+c.u+' <span style="color:#93c5fd">(RU '+c.uru+')</span><br>'+
        '<span style="color:#d6b4ff">Реги:</span> '+c.r+' <span style="color:#c4b5fd">(RU '+c.rru+')</span><br>'+
        '<span style="color:#aaa">Клики:</span> '+c.h;
      tip.style.opacity='1';
      var x=evt.clientX+14, y=evt.clientY+14;
      if(x+180>window.innerWidth) x=evt.clientX-190;
      tip.style.left=x+'px'; tip.style.top=y+'px';
    }
    function hide(){ tip.style.opacity='0'; vline.style.visibility='hidden'; dots.style.visibility='hidden'; }
    Array.prototype.forEach.call(svg.querySelectorAll('.hot'), function(rect){
      rect.addEventListener('mousemove', function(e){ show(+rect.getAttribute('data-i'), e); });
      rect.addEventListener('mouseleave', hide);
    });
  })();
  </script>

  <h1>По кампаниям (<?= h($PERIODS[$periodKey]) ?>)</h1>
  <div class="muted">Клик по строке — подробности кампании. Отдельно вынесены RU-показатели (уники и реги только из России).</div>
  <table class="sortable rowlink">
    <thead><tr>
      <th data-sort="text">Кампания</th><th data-sort="text">Слаг</th>
      <th class="num" data-sort="num" title="Все уники (все страны)">Юзеры</th>
      <th class="num" data-sort="num" title="Только уники из RU">🇷🇺 Юзеры</th>
      <th class="num" data-sort="num" title="Все реги">Реги</th>
      <th class="num" data-sort="num" title="Реги привязанные к RU-клику">🇷🇺 Реги</th>
      <th class="num" data-sort="num">Клики</th>
      <th>Топ гео (юзеры)</th>
      <th data-sort="num">Последний</th>
    </tr></thead>
    <tbody>
      <?php foreach ($today as $r):
        $du = tab_url('stats', $key) . '&slug=' . rawurlencode($r['slug']) . '&period=' . $periodKey;
        $tg = $geoCamp[$r['slug']] ?? [];
      ?>
      <tr data-href="<?= h($du) ?>">
        <td><?= h($r['name'] ?: '—') ?></td>
        <td><code><?= h($r['slug']) ?></code></td>
        <td class="num"><b><?= (int)$r['uniques'] ?></b></td>
        <td class="num"><?= (int)$r['uniques_ru'] ? '<b style="color:#1d4ed8">'.(int)$r['uniques_ru'].'</b>' : '<span style="color:#bbb">0</span>' ?></td>
        <td class="num"><?= (int)($r['reg'] ?? 0) ? '<b style="color:#a855f7">'.(int)$r['reg'].'</b>' : '0' ?></td>
        <td class="num"><?= (int)($r['reg_ru'] ?? 0) ? '<b style="color:#7e22ce">'.(int)$r['reg_ru'].'</b>' : '<span style="color:#bbb">0</span>' ?></td>
        <td class="num" style="color:#888"><?= (int)$r['humans'] ?></td>
        <td style="white-space:nowrap"><?php
          if ($tg) {
            $parts = [];
            foreach (array_slice($tg, 0, 2) as $g) $parts[] = country_flag($g['country']) . ' ' . h($g['country']) . ' ' . $g['uniques'];
            echo implode(' · ', $parts);
            if (count($tg) > 2) echo ' <span class="muted">+' . (count($tg) - 2) . '</span>';
          } else echo '—';
        ?></td>
        <td data-val="<?= (int)$r['last_ts'] ?>"><?= dt($r['last_ts']) ?></td>
      </tr>
      <?php endforeach; ?>
      <?php if (!$today): ?><tr><td colspan="9">За выбранный период юзеров нет.</td></tr><?php endif; ?>
    </tbody>
  </table>

  <h1>Гео (страны, <?= h($PERIODS[$periodKey]) ?>)</h1>
  <div class="muted">Юзеры — уникальные IP (реальные посетители). Страна из заголовка Cloudflare <code>CF-IPCountry</code>.</div>
  <table class="sortable">
    <thead><tr><th data-sort="text">Страна</th><th class="num" data-sort="num">Юзеры</th><th class="num" data-sort="num">Клики</th></tr></thead>
    <tbody>
      <?php foreach ($geo as $g): ?>
      <tr>
        <td><?= country_flag($g['country']) ?> <?= h($g['country']) ?></td>
        <td class="num"><b><?= (int)$g['uniques'] ?></b></td>
        <td class="num" style="color:#888"><?= (int)$g['humans'] ?></td>
      </tr>
      <?php endforeach; ?>
      <?php if (!$geo): ?><tr><td colspan="3">За период данных нет.</td></tr><?php endif; ?>
    </tbody>
  </table>

  <h1>Последние постбеки</h1>
  <div class="muted">Входящие конверсии от партнёрки. «не привязан» — постбек пришёл, но clickid не совпал ни с одним кликом. (Показаны последние 50, не зависят от периода.)</div>
  <table class="sortable">
    <thead><tr><th data-sort="text">Время</th><th data-sort="text">clickid</th><th data-sort="text">Кампания</th><th data-sort="text">Страна</th><th data-sort="text">Источник</th><th data-sort="text">Реферер</th><th data-sort="text">User-Agent</th><th data-sort="text">IP</th></tr></thead>
    <tbody>
      <?php foreach ($recentConv as $r): ?>
      <tr>
        <td><?= dt($r['ts']) ?></td>
        <td><code style="font-size:11px"><?= h($r['clickid']) ?></code></td>
        <td><?= $r['slug'] ? '<code>'.h($r['slug']).'</code>' : '<span style="color:var(--bot)">не привязан</span>' ?></td>
        <td><?= ($r['country'] ?? '') !== '' ? country_flag($r['country']).' '.h($r['country']) : '—' ?></td>
        <td><?= h(($r['source'] ?? '') !== '' ? $r['source'] : '—') ?></td>
        <td class="ref" title="<?= h($r['referer'] ?? '') ?>"><?= h(($r['referer'] ?? '') !== '' ? $r['referer'] : '—') ?></td>
        <td class="ref" title="<?= h($r['ua'] ?? '') ?>"><?= h(($r['ua'] ?? '') !== '' ? $r['ua'] : '—') ?></td>
        <td><?php
          $userIp = $r['ip'] ?? '';
          if ($userIp !== '') {
            echo h($userIp);
          } else {
            echo '<span class="muted" title="IP отправителя постбека (клик не привязан, IP юзера неизвестен)">'.h($r['postback_ip'] ?? '—').'</span>';
          }
        ?></td>
      </tr>
      <?php endforeach; ?>
      <?php if (!$recentConv): ?><tr><td colspan="8">Постбеков ещё не было.</td></tr><?php endif; ?>
    </tbody>
  </table>

<?php elseif ($tab === 'settings'): ?>

  <h1>Настройки</h1>

  <?php
    $hp = panel_cache('health', fn() => service_health());
    $gaps = recent_gaps(100);
    $fmtAgo = function ($ts) use ($hp) {
        if (!$ts) return 'никогда';
        $d = $hp['now'] - $ts;
        if ($d < 60)    return $d . ' сек назад';
        if ($d < 3600)  return floor($d/60) . ' мин назад';
        if ($d < 86400) return floor($d/3600) . ' ч назад';
        return floor($d/86400) . ' дн назад';
    };
    $fmtDur = function ($sec) {
        $sec = (int)$sec;
        $days = floor($sec/86400); $h = floor(($sec%86400)/3600); $m = floor(($sec%3600)/60);
        if ($days > 0) return $days . ' дн ' . $h . ' ч';
        if ($h > 0)    return $h . ' ч ' . $m . ' мин';
        return $m . ' мин';
    };
    $uptime = max(0, $hp['now'] - $hp['first_seen']);
    // суммарная тишина за 30 дней
    $sumGap = 0; $cnt30 = 0; $cut = $hp['now'] - 30*86400;
    foreach ($gaps as $g) if ((int)$g['end_ts'] >= $cut) { $sumGap += (int)$g['seconds']; $cnt30++; }
  ?>
  <div class="card">
    <h2>Состояние трекера</h2>
    <div class="bots-box" style="margin-bottom:6px">
      <span class="chip" style="background:#eef0f6;border-color:#d8dbe6;color:#333">Работает с момента старта: <b><?= h($fmtDur($uptime)) ?></b></span>
      <span class="chip" style="background:#eef0f6;border-color:#d8dbe6;color:#333">Последняя активность: <b><?= h($fmtAgo($hp['hb_last'])) ?></b></span>
      <span class="chip" style="background:#eef0f6;border-color:#d8dbe6;color:#333">Последний клик: <b><?= h($fmtAgo($hp['last_click'])) ?></b></span>
      <span class="chip" style="background:#eef0f6;border-color:#d8dbe6;color:#333">Последний постбек: <b><?= h($fmtAgo($hp['last_postback'])) ?></b></span>
    </div>
    <div class="muted">
      Старт отсчёта: <?= $hp['first_seen'] ? h(date('d.m.Y H:i', $hp['first_seen'])) : '—' ?> ·
      всего кликов в базе: <b><?= (int)$hp['total_clicks'] ?></b> · конверсий: <b><?= (int)$hp['total_conv'] ?></b>.
    </div>
  </div>

  <div class="card">
    <h2>Журнал окон тишины (возможные простои)</h2>
    <div class="muted">
      Записывается задним числом: когда между двумя обращениями к сервису прошло более <?= (int)(($cfg['downtime_gap'] ?? 300)/60) ?> мин,
      сюда попадает «окно тишины». Это <b>либо реальный простой</b> (сервер/хостинг лежал), <b>либо просто не было трафика</b> (например ночью).
      Длинная дыра в час пик — повод проверить; короткая ночью — норма.
      Точный лог недоступности извне может дать только внешний монитор (UptimeRobot).
      <?php if ($cnt30): ?><br>За 30 дней: <b><?= $cnt30 ?></b> окон, суммарно тишины <b><?= h($fmtDur($sumGap)) ?></b>.<?php endif; ?>
    </div>
    <table class="sortable">
      <thead><tr><th data-sort="num">Начало</th><th data-sort="num">Конец</th><th class="num" data-sort="num">Длительность</th></tr></thead>
      <tbody>
        <?php foreach ($gaps as $g): ?>
        <tr>
          <td data-val="<?= (int)$g['start_ts'] ?>"><?= h(date('d.m.Y H:i', (int)$g['start_ts'])) ?></td>
          <td data-val="<?= (int)$g['end_ts'] ?>"><?= h(date('d.m.Y H:i', (int)$g['end_ts'])) ?></td>
          <td class="num" data-val="<?= (int)$g['seconds'] ?>"><?= h($fmtDur((int)$g['seconds'])) ?></td>
        </tr>
        <?php endforeach; ?>
        <?php if (!$gaps): ?><tr><td colspan="3">Окон тишины пока не зафиксировано — сервис не пропадал дольше порога.</td></tr><?php endif; ?>
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>Доступность рефок (по последнему клику)</h2>
    <div class="muted">Пассивный признак: когда по кампании последний раз был клик. Долгое молчание у активной кампании = повод проверить ссылку/домен.</div>
    <?php
      // MAX(ts) по всей таблице — на боевой базе ~1с, поэтому из кэша
      $lastByCamp = panel_cache('lastbycamp', fn() => db()->query(
          "SELECT cl.slug, COALESCE(c.name,'') name, MAX(cl.ts) last
           FROM clicks cl LEFT JOIN campaigns c ON c.slug=cl.slug
           GROUP BY cl.slug ORDER BY last DESC LIMIT 30")->fetchAll(PDO::FETCH_ASSOC));
    ?>
    <table class="sortable">
      <thead><tr><th data-sort="text">Кампания</th><th data-sort="text">Слаг</th><th data-sort="num">Последний клик</th></tr></thead>
      <tbody>
        <?php foreach ($lastByCamp as $r): ?>
        <tr>
          <td><?= h($r['name'] ?: '—') ?></td>
          <td><code><?= h($r['slug']) ?></code></td>
          <td data-val="<?= (int)$r['last'] ?>"><?= h($fmtAgo((int)$r['last'])) ?></td>
        </tr>
        <?php endforeach; ?>
        <?php if (!$lastByCamp): ?><tr><td colspan="3">Кликов ещё не было.</td></tr><?php endif; ?>
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2>Выгрузка статистики (CSV)</h2>
    <div class="muted">Файлы с BOM — Excel открывает в UTF-8.</div>
    <p><a href="stats.php?tab=settings&export=clicks_full"><b>⬇ Подробно по всем кликам</b></a> — каждый клик со всеми полями (время, кампания, страна, IP, clickid, источник, бот/юзер, реферер, UA). Это и есть детальная выгрузка по кампаниям.</p>
    <p><a href="stats.php?tab=settings&export=today">⬇ Сводка по кампаниям за сутки</a> — клики, уник, боты, рег, деп.</p>
    <p><a href="stats.php?tab=settings&export=daily">⬇ По дням за месяц</a> — клики, уник, боты, реги.</p>
  </div>

  <div class="card">
    <h2>Очистка истории</h2>
    <div class="muted">Удаляет <b>всю историю кликов, конверсий и постбеков</b>. Кампании и их оферы <b>остаются на месте</b>. Действие необратимо.</div>
    <form method="post" onsubmit="return confirm('Точно очистить всю историю кликов и конверсий? Кампании сохранятся. Отменить нельзя.')">
      <input type="hidden" name="action" value="clear_history">
      <button type="submit" style="background:#dc2626">Очистить историю кликов и конверсий</button>
    </form>
  </div>

<?php else: ?>

  <h1>Кампании</h1>
  <div class="muted">Рефка стабильна. Чтобы сменить офер — впиши новый URL и нажми «Сохранить». Старая ссылка продолжит работать.</div>

  <form method="post" style="margin-bottom:18px">
    <input type="hidden" name="key" value="<?= h($key) ?>">
    <input type="hidden" name="action" value="check">
    <button type="submit">🔎 Проверить все рефки</button>
    <span class="muted" style="margin-left:10px">Дёргает URL всех оферов и показывает мёртвые (404 и т.п.).</span>
  </form>

  <?php if ($checkResults !== null):
      $err404 = []; $errOther = []; $okCount = 0;
      foreach ($checkResults as $r) {
          if ($r['code'] === 404)                         $err404[]   = $r;
          elseif ($r['err'] !== '' || $r['code'] < 200 || $r['code'] >= 400) $errOther[] = $r;
          else                                            $okCount++;
      }
  ?>
    <?php if ($err404): ?>
    <div class="errbox">
      <b>Ошибка 404 — оффер не найден (<?= count($err404) ?>):</b>
      <ul>
        <?php foreach ($err404 as $r): ?>
          <li><b><?= h($r['name'] ?: $r['slug']) ?></b> <code><?= h($r['slug']) ?></code> — <span class="ref" style="max-width:none"><?= h($r['offer_url']) ?></span></li>
        <?php endforeach; ?>
      </ul>
    </div>
    <?php endif; ?>

    <?php if ($errOther): ?>
    <div class="warnbox">
      <b>Прочие проблемы (<?= count($errOther) ?>) — таймаут, клоака, 4xx/5xx:</b>
      <ul>
        <?php foreach ($errOther as $r): ?>
          <li><b><?= h($r['name'] ?: $r['slug']) ?></b> — <?= $r['err'] !== '' ? h($r['err']) : ('HTTP ' . (int)$r['code']) ?> — <span class="ref" style="max-width:none"><?= h($r['offer_url']) ?></span></li>
        <?php endforeach; ?>
      </ul>
      <div class="muted">Часть казино-оферов прячется за клоакой и отдаёт боту 403/редирект — для живого юзера может открываться нормально. Проверяй такие вручную.</div>
    </div>
    <?php endif; ?>

    <div class="note">Проверено кампаний: <?= count($checkResults) ?>. Живых (2xx/3xx): <?= $okCount ?>. 404: <?= count($err404) ?>. Прочих проблем: <?= count($errOther) ?>.</div>
  <?php endif; ?>

  <table>
    <thead><tr>
      <th>Кампания</th><th>Рефка (стабильна)</th><th>Офер (можно менять)</th>
      <th>Изменён</th><th></th>
    </tr></thead>
    <tbody>
      <?php foreach ($campaigns as $c): $link = $refBase . $c['slug']; ?>
      <tr>
        <td>
          <form method="post" class="inline">
            <input type="hidden" name="key" value="<?= h($key) ?>">
            <input type="hidden" name="action" value="rename">
            <input type="hidden" name="id" value="<?= (int)$c['id'] ?>">
            <input type="text" name="name" value="<?= h($c['name']) ?>" style="max-width:150px">
          </form>
          <code><?= h($c['slug']) ?></code>
        </td>
        <td>
          <div class="reflink">
            <input type="text" readonly value="<?= h($link) ?>" onclick="this.select()">
            <button type="button" class="ghost" onclick="navigator.clipboard&&navigator.clipboard.writeText('<?= h($link) ?>');this.textContent='✓'">копи</button>
          </div>
        </td>
        <td>
          <form method="post" class="inline">
            <input type="hidden" name="key" value="<?= h($key) ?>">
            <input type="hidden" name="action" value="update_offer">
            <input type="hidden" name="id" value="<?= (int)$c['id'] ?>">
            <input type="url" name="offer_url" value="<?= h($c['offer_url']) ?>" required>
            <button type="submit">Сохранить</button>
          </form>
        </td>
        <td class="ref"><?= dt($c['updated_at']) ?></td>
        <td>
          <form method="post" onsubmit="return confirm('Удалить кампанию <?= h($c['slug']) ?>?')">
            <input type="hidden" name="key" value="<?= h($key) ?>">
            <input type="hidden" name="action" value="delete">
            <input type="hidden" name="id" value="<?= (int)$c['id'] ?>">
            <button type="submit" class="danger">&times;</button>
          </form>
        </td>
      </tr>
      <?php endforeach; ?>
      <?php if (!$campaigns): ?><tr><td colspan="5">Кампаний пока нет — добавь ниже.</td></tr><?php endif; ?>
    </tbody>
  </table>

  <div class="card">
    <h2>Добавить кампанию</h2>
    <form method="post">
      <input type="hidden" name="key" value="<?= h($key) ?>">
      <input type="hidden" name="action" value="add">
      <div class="grid3">
        <div><label class="f">Название</label><input type="text" name="name" placeholder="Fenix RU"></div>
        <div><label class="f">Слаг (рефка)</label><input type="text" name="slug" placeholder="fenix_ru" required></div>
        <div><label class="f">URL офера</label><input type="url" name="offer_url" placeholder="https://..." required></div>
        <div><button type="submit">Добавить</button></div>
      </div>
    </form>
  </div>

  <div class="card">
    <h2>Массовый импорт</h2>
    <div class="muted">По одной кампании в строке. Формат: <code>слаг | URL_офера | название</code> (название необязательно). Строки с <code>#</code> игнорируются.</div>
    <form method="post">
      <input type="hidden" name="key" value="<?= h($key) ?>">
      <input type="hidden" name="action" value="bulk">
      <textarea name="bulk" placeholder="fenix_ru | https://fnx-abs.org/aaa | Fenix RU&#10;fenix_de | https://fnx-abs.org/bbb | Fenix DE"></textarea>
      <div style="margin-top:10px"><button type="submit">Импортировать</button></div>
    </form>
  </div>

  <div class="card">
    <h2>Сменить оффер у группы (по префиксу)</h2>
    <div class="muted">Меняет оффер сразу во всех кампаниях, чей слаг начинается с префикса — чтобы не править 150 ссылок по одной. Например префикс <code>1go_engine</code> заденет <code>1go_engine</code>, <code>1go_engine_site001</code> и т.д. Пишется в историю.</div>
    <form method="post" onsubmit="return confirm('Сменить оффер у всех кампаний с префиксом ' + this.prefix.value + '?')">
      <input type="hidden" name="key" value="<?= h($key) ?>">
      <input type="hidden" name="action" value="update_prefix">
      <div class="grid3">
        <div><label class="f">Префикс слага</label><input type="text" name="prefix" placeholder="1go_engine" required></div>
        <div style="grid-column: span 2"><label class="f">Новый URL оффера</label><input type="url" name="offer_url" placeholder="https://..." required></div>
        <div><button type="submit">Сменить у группы</button></div>
      </div>
    </form>
  </div>

  <div class="card">
    <h2>Постбек (приём конверсий)</h2>
    <div class="muted">
      Вставь эти ссылки в кабинете партнёрки (там, где «URL постбэка»). Мы сами прокидываем наш
      <code>clickid</code> в оффер на доменах: <?= h(implode(', ', $cfg['postback_domains'] ?? [])) ?>.
      Партнёрка вернёт его в <code>${clickid}</code> — и конверсия привяжется к кампании.
    </div>
    <?php $pbBase = 'https://' . h($host) . '/postback.php?key=' . rawurlencode($cfg['postback_secret'] ?? ''); ?>
    <table style="margin-bottom:8px">
      <thead><tr><th>Тип</th><th>URL для кабинета партнёрки</th></tr></thead>
      <tbody>
        <tr><td>Регистрация</td><td class="ref" style="max-width:none"><code><?= $pbBase ?>&cnv_id=${clickid}&cnv_status=reg</code></td></tr>
        <tr><td>Депозит</td><td class="ref" style="max-width:none"><code><?= $pbBase ?>&cnv_id=${clickid}&cnv_status=dep</code></td></tr>
      </tbody>
    </table>
    <div class="muted">
      <code>${clickid}</code> — это макрос партнёрки (подставит наш clickid). Если у партнёрки макрос другой
      (<code>{clickid}</code>, <code>{subid}</code>, <code>{externalid}</code>) — ставь его вместо <code>${clickid}</code>.
      Секрет <code>key</code> и список доменов меняются в <code>config.php</code>.
    </div>
  </div>

  <div class="card">
    <h2>Замена домена офера</h2>
    <div class="muted">Если домен забанили — поменяй его во всех кампаниях разом. Меняется <b>только домен</b>, путь и параметры ссылки остаются. Совпадение строгое (<code>cbc-abs.net</code> не заденет <code>cbc-abs.network</code>). Изменения пишутся в историю.</div>
    <form method="post" onsubmit="return confirm('Заменить домен ' + this.old_domain.value + ' → ' + this.new_domain.value + ' во всех кампаниях?')">
      <input type="hidden" name="key" value="<?= h($key) ?>">
      <input type="hidden" name="action" value="replace_domain">
      <div class="grid3">
        <div><label class="f">Старый домен (забанен)</label><input type="text" name="old_domain" list="domains" placeholder="cbc-abs.net" required></div>
        <div><label class="f">Новый домен</label><input type="text" name="new_domain" placeholder="cbc-abs.com" required></div>
        <div></div>
        <div><button type="submit">Заменить</button></div>
      </div>
    </form>
    <datalist id="domains">
      <?php foreach ($domains as $d => $n): ?><option value="<?= h($d) ?>"><?= h($d) . ' (' . $n . ')' ?></option><?php endforeach; ?>
    </datalist>
    <?php if ($domains): ?>
    <div class="muted" style="margin-top:14px">Текущие домены оферов:</div>
    <table style="margin-bottom:0">
      <thead><tr><th>Домен</th><th class="num">Кампаний</th></tr></thead>
      <tbody>
        <?php foreach ($domains as $d => $n): ?>
        <tr><td><code><?= h($d) ?></code></td><td class="num"><?= (int)$n ?></td></tr>
        <?php endforeach; ?>
      </tbody>
    </table>
    <?php endif; ?>
  </div>

<?php endif; ?>

</div>
<script>
/* Сортировка таблиц кликом по заголовку (без перезагрузки) */
(function(){
  function cellVal(td, type){
    if(!td) return type==='num' ? -Infinity : '';
    if(td.dataset.val!==undefined && td.dataset.val!=='') return type==='num' ? parseFloat(td.dataset.val) : td.dataset.val;
    var t=(td.textContent||'').trim();
    if(type==='num'){
      var m=t.replace(/[^\d.,\-]/g,'').replace(',','.');
      var f=parseFloat(m);
      return isNaN(f) ? -Infinity : f;
    }
    return t.toLowerCase();
  }
  document.querySelectorAll('table.sortable').forEach(function(table){
    var ths=table.querySelectorAll('thead th');
    ths.forEach(function(th, idx){
      var type=th.getAttribute('data-sort'); if(!type) return;
      th.addEventListener('click', function(){
        var tbody=table.tBodies[0]; if(!tbody) return;
        var rows=Array.prototype.slice.call(tbody.rows).filter(function(r){return r.cells.length>1 || r.cells.length===ths.length;});
        // не сортируем строку-заглушку "нет данных"
        rows=Array.prototype.slice.call(tbody.rows);
        if(rows.length && rows[0].cells.length < ths.length) return;
        var asc = !(th.classList.contains('asc'));
        ths.forEach(function(o){o.classList.remove('asc','desc');});
        th.classList.add(asc?'asc':'desc');
        rows.sort(function(a,b){
          var va=cellVal(a.cells[idx],type), vb=cellVal(b.cells[idx],type);
          if(va<vb) return asc?-1:1;
          if(va>vb) return asc?1:-1;
          return 0;
        });
        rows.forEach(function(r){tbody.appendChild(r);});
      });
    });
  });
})();
/* Клик по строке таблицы -> переход в кампанию */
(function(){
  document.querySelectorAll('table.rowlink tbody tr[data-href]').forEach(function(tr){
    tr.addEventListener('click', function(e){
      if (e.target.closest('a,button,input')) return;
      window.location = tr.getAttribute('data-href');
    });
  });
})();
</script>
</body>
</html>
