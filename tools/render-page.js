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
        await page.waitForLoadState('load', { timeout: Math.min(timeout, 8000) }).catch(() => {});
        await page.waitForLoadState('networkidle', { timeout: Math.min(timeout, 6000) }).catch(() => {});
        await page.waitForTimeout(600);
    }
    return clicked;
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
    try {
        const response = await page.goto(job.url, {
            referer: job.referer || undefined,
            waitUntil: 'domcontentloaded',
            timeout,
        });
        await page.waitForLoadState('load', { timeout: Math.min(timeout, 15000) }).catch(() => {});
        await page.waitForLoadState('networkidle', { timeout: Math.min(timeout, 10000) }).catch(() => {});
        if (options.wait_ms > 0) {
            await page.waitForTimeout(options.wait_ms);
        }
        if (options.pass_gate !== false) {
            await passGate(page, timeout);
        }
        const html = await page.content();
        fs.mkdirSync(path.dirname(job.htmlFile), { recursive: true });
        fs.writeFileSync(job.htmlFile, html, 'utf8');
        if (job.screenshotFile) {
            await page.screenshot({ path: job.screenshotFile, fullPage: Boolean(options.full_page) }).catch(() => {});
        }
        return {
            id: job.id,
            ok: true,
            status: response ? response.status() : null,
            finalUrl: page.url(),
            title: await page.title().catch(() => ''),
        };
    } catch (e) {
        return { id: job.id, ok: false, error: String(e.message || e).split('\n')[0] };
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
    for (const [proxyUrl, groupJobs] of groups) {
        await runGroup(pw, proxyUrl || null, groupJobs, options);
    }
}

main().catch((e) => {
    process.stderr.write(String(e && e.stack ? e.stack : e) + '\n');
    process.exit(1);
});
