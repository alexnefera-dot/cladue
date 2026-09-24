#!/usr/bin/env node
/*
 * Открывает страницы в headless Chromium (Playwright) и сохраняет HTML после
 * выполнения JavaScript и скриншот. Вызывается из PHP (src/Visit/PlaywrightDriver.php).
 *
 * Вход (stdin, JSON): {"options": {...}, "jobs": [{"id", "url", "referer", "userAgent", "proxy", "htmlFile", "screenshotFile"}]}
 * Выход (stdout): по одной JSON-строке на задание: {"id", "ok", "status", "finalUrl", "title"} или {"id", "ok": false, "error"}.
 * Проверка окружения: node tools/render-page.js --check
 *
 * Требуется: npm install playwright && npx playwright install chromium
 */

'use strict';

const fs = require('fs');
const path = require('path');

function packageVersion(dir) {
    try {
        return require(path.join(dir, 'package.json')).version || 'unknown';
    } catch (e) {
        return 'unknown';
    }
}

function loadPlaywright() {
    const names = ['playwright', 'playwright-core'];
    const roots = [null];
    try {
        roots.push(require('child_process').execSync('npm root -g', { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim());
    } catch (e) {
        // npm недоступен — ищем только в обычных путях
    }
    for (const root of roots) {
        for (const name of names) {
            const id = root ? path.join(root, name) : name;
            try {
                const module = require(id);
                return { module, name, version: packageVersion(path.dirname(require.resolve(id + '/package.json'))) };
            } catch (e) {
                // ищем дальше
            }
        }
    }
    throw new Error('Не найден модуль playwright. Установите: npm install playwright && npx playwright install chromium');
}

function readStdin() {
    return new Promise((resolve, reject) => {
        let data = '';
        process.stdin.setEncoding('utf8');
        process.stdin.on('data', (chunk) => { data += chunk; });
        process.stdin.on('end', () => resolve(data));
        process.stdin.on('error', reject);
    });
}

function parseProxy(url) {
    if (!url) {
        return undefined;
    }
    const parsed = new URL(url);
    const proxy = { server: `${parsed.protocol}//${parsed.hostname}:${parsed.port}` };
    if (parsed.username) {
        proxy.username = decodeURIComponent(parsed.username);
        proxy.password = decodeURIComponent(parsed.password || '');
    }
    return proxy;
}

function emit(result) {
    process.stdout.write(JSON.stringify(result) + '\n');
}

async function check() {
    try {
        const { module: pw, name, version } = loadPlaywright();
        const executable = process.env.YS_BROWSER_PATH || pw.chromium.executablePath();
        const exists = executable ? fs.existsSync(executable) : false;
        emit({
            ok: exists,
            module: name,
            version,
            executablePath: executable,
            error: exists ? '' : 'Chromium не найден. Выполните: npx playwright install chromium (или задайте visit.browser_path)',
        });
        process.exit(exists ? 0 : 1);
    } catch (e) {
        emit({ ok: false, error: String(e.message || e) });
        process.exit(1);
    }
}

// Тексты кнопок подтверждения возраста / согласия с cookie и признаки такого барьера.
const GATE_CONFIRM = '^(да\\b|да,|мне уже|мне есть|мне исполнилось|подтвержда|подтверди|я совершеннолет|соглас|принима|принять|продолжить|войти на сайт|вход на сайт|enter\\b|yes\\b|i am|18\\+?|21\\+?|accept|agree|continue)';
const GATE_DECLINE = '(мне нет|мне ещё нет|мне еще нет|нет,|younger|no,|exit|leave site|decline|reject|выход|назад)';
const GATE_CONTEXT = '(вам\\s*(уже|есть)|подтвердите\\s*возраст|проверка\\s*возраст|совершеннолет|18\\s*лет|21\\s*(год|года|лет)|age.?verif|adult\\s*content|достигли\\s*ли|cookie|куки|обработку\\s*файлов)';

// Заглушки-барьеры (проверка возраста 18+, cookie-стена) показывают один и тот же экран на всех
// страницах. Чтобы дальше сравнивать реальный контент, а не заглушку, лучшими усилиями нажимаем
// кнопку подтверждения. Срабатывает только при явных признаках барьера — на обычных страницах нет.
async function passGate(page, timeout) {
    let clicked = null;
    try {
        clicked = await page.evaluate((patterns) => {
            const confirmRe = new RegExp(patterns.confirm, 'i');
            const declineRe = new RegExp(patterns.decline, 'i');
            const contextRe = new RegExp(patterns.context, 'i');
            const isVisible = (el) => {
                const s = getComputedStyle(el);
                if (s.visibility === 'hidden' || s.display === 'none' || parseFloat(s.opacity || '1') < 0.1) {
                    return false;
                }
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.height > 0;
            };
            // Кандидаты в барьер: явные модалки (role=dialog / aria-modal / <dialog open>) и крупные
            // фиксированные оверлеи поверх страницы. Классы у таких заглушек обфусцированы и меняются
            // от сайта к сайту, поэтому опираемся на роль/позицию, а не на имена классов.
            const candidates = [];
            document.querySelectorAll('[role="dialog"],[aria-modal="true"],dialog[open]').forEach((el) => {
                if (isVisible(el)) {
                    candidates.push(el);
                }
            });
            Array.from(document.querySelectorAll('body *')).forEach((el) => {
                const s = getComputedStyle(el);
                if ((s.position === 'fixed' || s.position === 'absolute') && isVisible(el)) {
                    const r = el.getBoundingClientRect();
                    if (r.width >= window.innerWidth * 0.6 && r.height >= window.innerHeight * 0.5 && (parseInt(s.zIndex, 10) || 0) >= 30) {
                        candidates.push(el);
                    }
                }
            });
            // Это возрастной/cookie-барьер, только если признаки есть в тексте самого оверлея
            // (а не где-то в футере страницы — там «18+» бывает и без заглушки).
            const barrier = candidates.find((el) => contextRe.test((el.innerText || '').slice(0, 3000)));
            if (!barrier) {
                return null;
            }
            // Жмём кнопку согласия строго внутри барьера, не трогая кнопки на остальной странице.
            const controls = Array.from(barrier.querySelectorAll('button, a, input[type=button], input[type=submit], [role=button], [onclick]'));
            for (const el of controls) {
                const text = ((el.innerText || el.value || el.getAttribute('aria-label') || '')).trim();
                if (!text || text.length > 40 || declineRe.test(text) || !confirmRe.test(text)) {
                    continue;
                }
                if (!isVisible(el)) {
                    continue;
                }
                el.click();
                return text;
            }
            return null;
        }, { confirm: GATE_CONFIRM, decline: GATE_DECLINE, context: GATE_CONTEXT });
    } catch (e) {
        return null;
    }
    if (clicked) {
        await page.waitForLoadState('load', { timeout: Math.min(timeout, 5000) }).catch(() => {});
        await page.waitForLoadState('networkidle', { timeout: Math.min(timeout, 3000) }).catch(() => {});
        await page.waitForTimeout(400);
    }
    return clicked;
}

// Пауза между заходами НА ОДИН САЙТ: разные сайты открываются параллельно (в том числе разными
// браузерами), но один сайт не заваливается запросами. Слот резервируется до ожидания, поэтому
// параллельные воркеры встают в очередь, а не стартуют одновременно.
const hostLastStart = new Map();
async function hostGate(url, delay) {
    if (!(delay > 0)) {
        return;
    }
    let host;
    try {
        host = new URL(url).host;
    } catch (e) {
        return;
    }
    const now = Date.now();
    const start = Math.max(now, (hostLastStart.get(host) || 0) + delay);
    hostLastStart.set(host, start);
    if (start > now) {
        await new Promise((resolve) => setTimeout(resolve, start - now));
    }
}

async function visitJob(browser, job, options) {
    const context = await browser.newContext({
        userAgent: job.userAgent || undefined,
        locale: 'ru-RU',
        viewport: { width: 1366, height: 768 },
        ignoreHTTPSErrors: options.verify_ssl === false,
        extraHTTPHeaders: { 'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7' },
    });
    const page = await context.newPage();
    const timeout = Math.max(1000, (options.timeout || 30) * 1000);
    const needsPicture = Boolean(job.screenshotFile);
    // Страницам без снимка картинки, шрифты и видео не нужны — это основной объём трафика и времени
    // при обходе сайта. HTML, стили и скрипты грузим как обычно, чтобы страница собралась.
    if (!needsPicture && options.block_assets !== false) {
        await context.route('**/*', (route) => {
            const type = route.request().resourceType();
            return type === 'image' || type === 'media' || type === 'font' ? route.abort() : route.continue();
        }).catch(() => {});
    }
    // Цепочка редиректов: наш дор уводит через свой редиректор, а тот — дальше на чужую рефку,
    // поэтому в конечном адресе редиректора уже нет. Ловим и серверные хопы (redirectedFrom), и
    // клиентские переходы (framenavigated — meta refresh, JS).
    const navigated = [];
    page.on('framenavigated', (frame) => {
        if (frame === page.mainFrame()) {
            navigated.push(frame.url());
        }
    });
    try {
        const response = await page.goto(job.url, {
            referer: job.referer || undefined,
            waitUntil: 'domcontentloaded',
            timeout,
        });
        await page.waitForLoadState('load', { timeout: Math.min(timeout, 8000) }).catch(() => {});
        // networkidle нужен, чтобы страница успела отрисоваться для снимка; для HTML хватает load.
        if (needsPicture) {
            await page.waitForLoadState('networkidle', { timeout: Math.min(timeout, 4000) }).catch(() => {});
        }
        const wait = needsPicture ? options.wait_ms : Math.min(options.wait_ms || 0, 500);
        if (wait > 0) {
            await page.waitForTimeout(wait);
        }
        if (options.pass_gate !== false) {
            await passGate(page, timeout);
        }
        let html = await page.content();
        // Ограничение размера, как у curl-драйвера (max_bytes): страница с гигантским DOM (бесконечная
        // подгрузка, base64-картинки) иначе даёт файл на десятки МБ и валит PHP по памяти на отпечатке.
        const maxBytes = Math.max(65536, Number(options.max_bytes) || 2 * 1024 * 1024);
        if (Buffer.byteLength(html, 'utf8') > maxBytes) {
            html = Buffer.from(html, 'utf8').subarray(0, maxBytes).toString('utf8');
        }
        fs.mkdirSync(path.dirname(job.htmlFile), { recursive: true });
        fs.writeFileSync(job.htmlFile, html, 'utf8');
        if (job.screenshotFile) {
            await page.screenshot({ path: job.screenshotFile, fullPage: Boolean(options.full_page) }).catch(() => {});
        }
        const hops = [];
        try {
            let req = response ? response.request() : null;
            while (req) {
                hops.unshift(req.url());
                req = req.redirectedFrom();
            }
        } catch (e) { /* цепочка недоступна — не беда, останутся переходы фрейма */ }
        const redirects = [...new Set([...hops, ...navigated].filter(Boolean))];
        return {
            id: job.id,
            ok: true,
            status: response ? response.status() : null,
            finalUrl: page.url(),
            title: await page.title().catch(() => ''),
            redirects,
        };
    } catch (e) {
        // Даже если страница не открылась (таймаут, обрыв), переходы главного фрейма уже случились:
        // наш дор мог успеть увести на свой редиректор. Отдаём их, иначе сайт не опознать как наш.
        let finalUrl = '';
        try { finalUrl = page.url(); } catch (e2) { /* страница закрыта */ }
        return {
            id: job.id,
            ok: false,
            error: String(e.message || e).split('\n')[0],
            finalUrl: finalUrl && finalUrl !== 'about:blank' ? finalUrl : '',
            redirects: [...new Set(navigated.filter((u) => Boolean(u) && u !== 'about:blank'))],
        };
    } finally {
        await context.close().catch(() => {});
    }
}

async function runGroup(pw, proxyUrl, jobs, options) {
    const args = [];
    if (Array.isArray(options.resolve) && options.resolve.length > 0) {
        const rules = options.resolve
            .map((rule) => String(rule).split(':'))
            .filter((parts) => parts.length >= 3)
            .map((parts) => `MAP ${parts[0]}:${parts[1]} ${parts.slice(2).join(':')}`);
        if (rules.length > 0) {
            args.push('--host-resolver-rules=' + rules.join(', '));
        }
    }
    const launchOptions = { headless: true, args };
    if (options.browser_path) {
        launchOptions.executablePath = options.browser_path;
    }
    const proxy = parseProxy(proxyUrl);
    if (proxy) {
        launchOptions.proxy = proxy;
    }

    let browser;
    try {
        browser = await pw.chromium.launch(launchOptions);
    } catch (e) {
        for (const job of jobs) {
            emit({ id: job.id, ok: false, error: 'Не удалось запустить Chromium: ' + String(e.message || e).split('\n')[0] });
        }
        return;
    }

    const concurrency = Math.max(1, options.concurrency || 1);
    const delay = Math.max(0, options.delay_ms || 0);
    let index = 0;
    let lastStart = 0;

    async function worker() {
        while (index < jobs.length) {
            const job = jobs[index++];
            const sinceLast = Date.now() - lastStart;
            if (lastStart > 0 && sinceLast < delay) {
                await new Promise((resolve) => setTimeout(resolve, delay - sinceLast));
            }
            lastStart = Date.now();
            await hostGate(job.url, delay);
            emit(await visitJob(browser, job, options));
        }
    }

    await Promise.all(Array.from({ length: Math.min(concurrency, jobs.length) }, () => worker()));
    await browser.close().catch(() => {});
}

async function main() {
    if (process.argv.includes('--check')) {
        await check();
        return;
    }

    const input = JSON.parse(await readStdin() || '{}');
    const options = input.options || {};
    const jobs = Array.isArray(input.jobs) ? input.jobs : [];
    if (jobs.length === 0) {
        return;
    }

    let pw;
    try {
        pw = loadPlaywright().module;
    } catch (e) {
        for (const job of jobs) {
            emit({ id: job.id, ok: false, error: String(e.message || e) });
        }
        process.exit(1);
    }

    const groups = new Map();
    for (const job of jobs) {
        const key = job.proxy || '';
        if (!groups.has(key)) {
            groups.set(key, []);
        }
        groups.get(key).push(job);
    }
    // Группы (по одной на прокси) открываются ПАРАЛЛЕЛЬНО, каждая своим браузером: раньше они шли одна
    // за другой, и десяток прокси не ускорял ничего. Сколько браузеров разом — options.browsers.
    const list = [...groups.entries()];
    const maxBrowsers = Math.max(1, Math.min(Number(options.browsers) || 1, list.length));
    let groupIndex = 0;
    async function groupWorker() {
        while (groupIndex < list.length) {
            const [proxyUrl, groupJobs] = list[groupIndex++];
            await runGroup(pw, proxyUrl || null, groupJobs, options);
        }
    }
    await Promise.all(Array.from({ length: maxBrowsers }, () => groupWorker()));
}

main().catch((e) => {
    process.stderr.write(String(e && e.stack ? e.stack : e) + '\n');
    process.exit(1);
});
