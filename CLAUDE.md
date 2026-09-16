# CLAUDE.md

This file provides guidance to Claude Code and other AI assistants working in this repository.

---

## Repository Overview

**Repository:** `alexnefera-dot/cladue`

`yandex-sites` — a PHP CLI tool (no third-party PHP packages) that runs a list of search queries
through Yandex search results, collects the sites from the results and selects the "needed" ones
using configurable rules (TLDs, domain allow/deny lists, title/snippet keywords, URL regexes,
minimum number of matching queries). Optional stages: a parallel HTTP check of the selected sites
and "visits" — opening each selected site like a visitor coming from Yandex search (headless
Chromium via Playwright, or curl), saving HTML/screenshots and comparing page variants shown to
different visitors.

Three result sources: the official Yandex Search API (Yandex Cloud), the XMLStock service
(Yandex.XML-compatible), and the live yandex.ru results page fetched through user-supplied proxies.
Output: `sites.csv`, `sites.json`, `domains.txt`, `out/pages/<host>/variant-N.html|png`
(crawl mode: `out/pages/<N>-стр/<host>/<last-url-segment>.html|png`, home → `main`).
Responses are cached on disk per source.

User-facing documentation (README, CLI help, config comments) is in Russian; identifiers are English.

---

## Project Structure

```
cladue/
├── bin/yandex-sites.php        # CLI entry point (works with or without composer autoload)
├── bin/setup.php               # first-time setup: config/.env/proxies from examples, folders, environment checks
├── bin/panel.php               # local web UI: launcher + php -S router (keys, run, progress, schedule)
├── bin/run-job.php             # background job: collect / download / clean stages, writes runs/current/status.json
├── bin/clean-content.php       # content prep: article-body templates from downloaded pages (%domain%/%date%/%brand%)
├── public/panel.html           # single-file web UI (inline CSS/JS, polls the panel API)
├── tools/render-page.js        # Node.js + Playwright renderer used by Visit\PlaywrightDriver (stdin JSON → stdout JSON lines)
├── src/
│   ├── Cli/Application.php     # argument parsing, dependency wiring (sources, cache, checker, visitor), summary output
│   ├── Config.php              # defaults, config.php loading, .env, validation, dot-path access
│   ├── Runner.php              # pipeline: queries → fetch → parse → filters → sites → site check → visits
│   ├── RunResult.php           # selected sites, raw results, stats, errors
│   ├── Aggregator.php          # groups results into Site objects (by host or registrable domain)
│   ├── Search/                 # RawFetcherInterface, ResponseParserInterface, RestApiFetcher (API v2),
│   │                           # XmlApiFetcher (API v1), XmlStockFetcher, XmlResponseParser, CachingFetcher,
│   │                           # AbstractApiFetcher (throttle/retries), ApiException
│   ├── Live/                   # LiveFetcher (live SERP through ProxyPool), Proxy, ProxyPool,
│   │                           # HtmlResponseParser (yandex.ru SERP markup), UserAgents
│   ├── Visit/                  # PageVisitor, DriverInterface, PlaywrightDriver, CurlDriver, VisitJob, Fingerprint,
│   │                           # SiteTemplate (template family of a site by its home-page HTML)
│   ├── Filter/                 # ResultFilter rules, DomainMatcher, TextMatcher, Domains helpers, DefaultExclusions
│   ├── Check/                  # SiteChecker (curl_multi), CheckResult, Html helpers
│   ├── Output/ReportWriter.php # CSV / JSON / domains.txt writers
│   ├── Model/                  # SearchResult, SearchPage (hasMore), Site (check + visits)
│   ├── Http/                   # HttpClient (curl wrapper with proxy/cookie/follow options), HttpResponse, HttpException
│   ├── Runtime.php             # shared pipeline factory (fetcher/cache/proxies/checker/visitor) used by CLI and job
│   ├── Content/                # ContentCleaner (article-body extraction, link normalization, %var% templating),
│   │                           # SiteCleaner (one site → content/N-стр/<host>, shared by panel + run-job), BrandDetector, KnownBrands
│   └── Support/                # Logger (STDERR), QueryList (query file reader), Progress (status JSON writer),
│                               # SiteRows (sites.json → Site objects + panel table rows, shared by run-job and panel),
│                               # Archive (zip of a folder: ZipArchive, else bsdtar — «Скачать архив контента»)
├── tests/                      # custom runner (run.php), Assert, fixtures/ (XML + SERP HTML), fake-api-server.php
├── config.example.php          # documented example configuration (copy to config.php)
├── proxies.example.txt         # proxy list formats
├── queries.example.txt         # example query list
├── .env.example                # YANDEX_FOLDER_ID / YANDEX_API_KEY / XMLSTOCK_USER / XMLSTOCK_KEY
├── composer.json               # PSR-4 autoload only, no dependencies
└── CLAUDE.md
```

Ignored by git: `config.php`, `.env`, `proxies.txt`, `cache/`, `out/`, `runs/`, `queries.txt`, `vendor/`, `node_modules/`.

---

## Development Setup

### Prerequisites

- PHP >= 8.1 with `curl`, `dom`, `json`, `libxml`, `mbstring` (`intl` optional, for IDN domains)
- Composer is optional (`bin/yandex-sites.php` falls back to its own autoloader)
- For browser visits: Node.js 18+, `npm install playwright`, `npx playwright install chromium`
  (`node tools/render-page.js --check` verifies the setup; `playwright-core` installed globally also works)

### Initial Setup

```bash
cp config.example.php config.php
cp .env.example .env      # fill in credentials for the chosen source
```

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `YANDEX_FOLDER_ID`, `YANDEX_API_KEY`, `YANDEX_IAM_TOKEN` | Yandex Search API (source `api`) |
| `XMLSTOCK_USER`, `XMLSTOCK_KEY` | XMLStock (source `xmlstock`) |
| `YANDEX_REST_ENDPOINT`, `YANDEX_XML_ENDPOINT`, `XMLSTOCK_ENDPOINT`, `XMLSTOCK_LIVE_ENDPOINT`, `YANDEX_LIVE_DOMAIN` | endpoint overrides (fake server, gateways) |
| `PLAYWRIGHT_BROWSERS_PATH` | passed through to `render-page.js` |

---

## Common Commands

| Task | Command |
|------|---------|
| First-time setup | `php bin/setup.php --proxy=http://host:port:user:pass` (creates config.php, .env, proxies.txt, folders; checks PHP/Playwright) |
| Update code from GitHub | `php bin/setup.php --update` (downloads the branch archive, overwrites code, keeps config/proxies/cache/out) |
| Web interface | `php bin/panel.php` (opens http://127.0.0.1:8777; keys, run, progress, schedule) |
| Run the tool | `php bin/yandex-sites.php queries.txt` |
| Live SERP through proxies | `php bin/yandex-sites.php --live --proxies=proxies.txt queries.txt` |
| Visits with screenshots | `php bin/yandex-sites.php queries.txt --visit --variants=2` |
| Prepare content templates | `php bin/clean-content.php --brand-ru=… --brand-en=… --zip=out/content.zip` |
| Debug SERP parsing | `php bin/yandex-sites.php --parse-html=cache/live/xx/…html` |
| Show CLI help | `php bin/yandex-sites.php --help` |
| Run all tests | `php tests/run.php` |
| Run tests matching a name | `php tests/run.php Live` |
| Syntax check | `php tests/lint.php` |
| Check Playwright setup | `node tools/render-page.js --check` |
| Fake services for a demo | `FAKE_MODE=local php -S 127.0.0.1:8089 tests/fake-api-server.php` |

---

## Testing

Tests use a small custom runner (`tests/run.php`) and `Tests\Assert`; no PHPUnit. Each
`tests/*Test.php` defines a class `Tests\<FileName>` whose `test*` methods are executed.
`Assert::skip()` marks a test as skipped, `tearDownClass()` runs after each class.

- Unit tests cover the XML and HTML parsers, filters, domain helpers, config, cache, API clients
  (via `Tests\StubHttpClient`, which records request options such as proxy/cookie jar), the
  proxy pool, `LiveFetcher`, `XmlStockFetcher`, runner and report writer.
- `Tests\FakeServer::port($mode)` starts `tests/fake-api-server.php` with PHP's built-in server,
  one instance per mode (`ok`, `captcha`, `error`, `local`; `local` makes SERP result URLs point back
  to the fake server over http so visits can be tested). Fake proxies are just extra server
  instances: curl sends absolute-form requests to them and the built-in server answers directly.
- `IntegrationTest` runs the CLI end to end for every source (API v2, API v1, XMLStock, live with a
  captcha proxy and a good proxy, `--visit` with the curl driver, `--parse-html`).
- `VisitTest` exercises `CurlDriver`, `PageVisitor` (variants, referer, `max_sites`) and
  `PlaywrightDriver` (skipped when Node/Playwright/Chromium are unavailable). Hosts are routed
  to the fake server with `CURLOPT_RESOLVE` / Chromium `--host-resolver-rules`.
- Fixtures: real-format Yandex XML responses and a hand-written yandex.ru SERP page
  (`tests/fixtures/serp.html`, organic results + ad + wizard + clck redirect + pager).

Run `php tests/lint.php && php tests/run.php` before committing.

---

## Code Style & Conventions

- `declare(strict_types=1)` in every file, PSR-12 formatting, PSR-4 namespaces `YandexSites\` (src) and `Tests\` (tests).
- Final classes by default; `HttpClient` and `SiteChecker` are non-final on purpose (extended in tests).
- Constructor property promotion and readonly properties for value objects (`Model/`, `Visit/VisitJob`).
- Comments and user-facing strings in Russian; identifiers in English.
- Configuration is a plain PHP array with dot-path access (`$config->get('search.pages')`);
  lists in config replace defaults entirely, associative sections are merged.
- Errors: `ApiException` carries `retryable`/`fatal` flags; `UsageException` maps to exit code 2;
  everything else is a `RuntimeException`/`InvalidArgumentException` with a Russian message.
- Logging goes to STDERR through `Support\Logger`; the final summary goes to STDOUT.
- Positions are numbered across pages (the parser receives `positionOffset`); `SearchPage::$hasMore`
  drives pagination (`null` = fall back to `groups < groups_on_page`).

### Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| Files/classes | `PascalCase` | `ResultFilter.php` |
| Methods/variables | `camelCase` | `queryCount()` |
| Config keys | `snake_case` | `groups_on_page` |
| CLI options | `kebab-case` | `--check-sites` |

---

## Source Notes

- REST (v2): `POST https://searchapi.api.cloud.yandex.net/v2/web/search`, header
  `Authorization: Api-Key <key>` (or `Bearer <IAM>`), JSON body with `query.searchType`,
  `query.queryText`, `groupSpec`, `folderId`, `responseFormat: FORMAT_XML`; response `{"rawData": "<base64 XML>"}`.
  Field names and enums follow `yandex/cloud/searchapi/v2/*.proto` from `yandex-cloud/cloudapi`.
- Legacy XML (v1): `GET https://yandex.ru/search/xml?folderid=…&apikey=…&query=…&lr=…&groupby=…&page=…`.
- XMLStock: `GET https://xmlstock.com/yandex/xml/?user=…&key=…&query=…&lr=…&groupby=…&page=…[&domain=…&device=…]`,
  Yandex.XML-compatible response parsed by `XmlResponseParser`. `xmlstock.mode` (`xml` default | `live`,
  CLI `--xmlstock-mode`, panel select `#xmmode` → settings `xmlstock_mode`) switches `XmlStockFetcher` to
  XMLStock's live-SERP product: `GET https://xmlstock.com/yandexlive/xml/` (`xmlstock.live_endpoint`,
  env `XMLSTOCK_LIVE_ENDPOINT`) with only `user/key/query/lr/page[/domain/device/extra]` — no
  `groupby`/`sortby`/`maxpassages` — and the same Yandex.XML response, always ≤ 10 results per page
  (`XmlStockFetcher::LIVE_PAGE_SIZE`). `Runner` uses that page size instead of `groups_on_page` for the
  «last page» fallback, `buildOverrides()` turns «топ N» into `ceil(N/10)` pages instead of one page of N,
  and `Runtime::cacheKeyParts()` adds `mode=live` so live and XML responses are cached apart. Fake server
  route `/yandexlive/xml/` (10 per page, capture includes `__path`); covered by
  `XmlStockFetcherTest::testLiveModeUsesLiveEndpointWithoutXmlParams` and
  `PanelTest::testXmlstockLiveModeUsesLiveEndpointAndPaginatesByTen`.
- XML response: `yandexsearch/response/results/grouping/group/doc/{url,domain,title,headline,passages/passage}`;
  `<hlword>` tags are flattened; `response/error@code` — 15 = no results (not an error),
  55 = rate limit (retry), 32/33/42/43/44/48 = fatal.
- Live SERP: `GET {live.domain}/search/?text=…&lr=…&p=…`; `HtmlResponseParser` looks for `.serp-item`
  elements, `a.OrganicTitle-Link` (fallback: first external link, `/clck/` links are unwrapped),
  `.OrganicTextContentSpan`, skips ads (`serp-adv-item`, yabs links, «Реклама» label) and detects
  captcha/empty/unknown pages. Captcha is never solved: the proxy is paused and the next one is used.
- Limits: API 10 rps, 10 000 sync requests/hour, ≤ 250 results per query, query ≤ 400 chars,
  `groups_on_page` 1–100, `docs_in_group` 1–3, `max_passages` 1–5.

---

## Git Workflow

- Branches: `claude/<description>-<session-id>` for AI-created branches, `feature/`, `fix/`, `chore/` otherwise.
- Conventional Commits: `feat(live): …`, `fix(visit): …`, `docs: …`, `test: …`.
- Push with `git push -u origin <branch-name>`; never commit `config.php`, `.env`, `proxies.txt`, `cache/` or `out/`.

---

## AI Assistant Notes

- Keep the tool free of third-party PHP packages; Node.js/Playwright is optional and only for visits.
- Never add captcha solving or other measures that defeat Yandex's protections; the live source
  must keep pausing proxies on captcha and stopping when proxies run out.
- Proxies live in the top-level `proxies` list / `proxy_file` (format `scheme://host:port:user:pass`
  and others parsed by `Live\Proxy::parse()`); `live.proxies`/`live.proxy_file` are legacy aliases merged
  in `Application::buildProxyPool()`. The live source rotates them per request, visits per job.
- Page size is capped at `visit.max_bytes` (default 2 MB) in BOTH drivers: `CurlDriver` stops reading, and
  `tools/render-page.js` truncates `page.content()` before writing (the option is passed through
  `PlaywrightDriver`). `PageVisitor::readHtml()` reads saved pages with the same cap, and
  `Fingerprint::text()` cuts its input at `Fingerprint::MAX_BYTES` (3 MB) — a site with a giant DOM once
  made `preg_replace` allocate ~100 MB and the PHP fatal killed the whole collect job. The entry points
  (`bin/run-job.php`, `bin/yandex-sites.php`, `bin/panel.php`, `bin/clean-content.php`) raise
  `memory_limit` to 1 GB as a safety margin on top of the caps.
- Default User-Agent for visits and site checks is `UserAgents::YANDEX_BOT` (the first visit variant
  shows the page as served to Yandex's crawler); additional variants use `UserAgents::BROWSERS`.
  The live SERP fetch always uses browser agents. `--user-agent` overrides visits/checks only.
  Some sites filter by User-Agent and answer the crawler with 403 / an anti-bot stub, so not even a
  screenshot comes back («хитрый фильтр» — the user's report). A retry therefore changes the AGENT as
  well as the proxy: `visit.retry_user_agents` (default true, `Config::defaults()` + `config.example.php`)
  makes `PageVisitor::retryUserAgent()` pick a browser from `UserAgents::browsersFrom($this->userAgents)`
  — the attempt number selects it, so a second retry tries a different browser, and a list with no browser
  (`--user-agent="…YandexBot…"`) falls back to `UserAgents::BROWSERS`. A single pinned browser agent stays
  untouched (one candidate = the current one). The agent that WORKED is then reused: `crawl()` keeps it per
  site in `$state[$key]['ua']` (set from the home visit) so the remaining pages skip the doomed first
  attempt, and `retryFailed()` reads it back from the site's ok visits (`$state[$key]['ua']`) for
  iteration 0. Because a visit is assembled from the ORIGINAL job, `runWithRetry()` stamps
  `retry_proxy`/`retry_user_agent` onto the result and `assembleVisit()` prefers them — otherwise the
  report named the agent and proxy that had just been refused. Reporting: `PageVisitor::openedAsBrowser()`
  counts ok visits whose UA is not a bot, `SiteRows::preview()` emits `pages_browser`, `/api/site-pages`
  emits `as_browser` per page, and the panel shows a «под браузером» tag on the page row plus «под браузером
  (робота не пустили): N стр. на M сайтах» in the stats line, the job message and the log. Covered by
  `VisitTest::testBlockedBotIsRetriedUnderBrowserUserAgent` / `testRetryUserAgentsCanBeDisabled` against
  the fake-server host `botblock.ru` (403 + Cloudflare stub for YandexBot, normal page for browsers).
- `Visit\OfferWall` catches the OTHER cloaking shape the user reported (with a screenshot): instead of
  its own content a site serves a wall of somebody else's bonuses — «В подборке 6 офферов», brand bubbles
  with «ЗАБРАТЬ БОНУС», a ticker «7K КАЗИНО CASINO — 300 000 ₽ 500 FS», «18+ Азартные игры являются
  развлечением. Проверяйте условия бонуса партнёра перед регистрацией» — and hides the real site from us.
  `looksLike($html)` scores the VISIBLE text (`Fingerprint::text`) like `SiteTemplate` does: strong markers
  (weight 2 — the words a wall uses for SOMEONE ELSE's offers: «в подборке», «оффер», «бонуса партнёра»),
  weak ones (weight 1 — «freebet», «на 1-й депозит», «18+» and the disclaimer «Азартные игры являются
  развлечением», which real casino sites carry too: as a strong marker it turned a short real home page
  into a wall), and REPEATS (`забрать бонус` ≥ 3, `казино casino` ≥ 2 — one CTA is a normal site, five is
  a list of competitors) plus ≥ 3 DIFFERENT `Content\KnownBrands` (cached once per process; a real site's
  home talks about its own brand). Wins at `MIN_SCORE` 4 with ≥ 1 strong marker, and a hard gate rejects
  anything over `MAX_TEXT` (4000 chars of text) — a wall is short, a real home page has SEO text, and a
  false positive (a real site thrown away) costs more than a missed wall. Wiring in `PageVisitor`
  (`visit.detect_offer_walls`, default true): `isRetryable()` treats a wall like an anti-bot stub so the
  page is re-requested through ANOTHER proxy AND another User-Agent (the mechanism above) — that is the
  user's «проверять с разных айпи и юзер агентов»; `assembleVisit()` deletes the HTML, keeps the home
  screenshot (so the wall can be eyeballed), sets `offer_wall` and reports «подборка офферов вместо сайта».
  A wall visit is retryable by `isRetryableVisit()` already (non-ok, not own/stub/duplicate/404), so
  «Докачать» tries fresh identities again. `PageVisitor::isOfferWallSite()` = at least one wall visit and NO
  ok visit → `SiteRows::preview()` emits `offer_wall`, the panel tags the host «подборка офферов», counts
  them in the stats line, groups such pages in the expanded row and offers «Убрать подборки офферов (N)»
  (the same reversible `removeWhere()` → `/api/remove` path), and the collect message/log say «подборок
  офферов вместо сайта: N». Covered by `tests/OfferWallTest.php` (four negative cases — a real site, a
  short home page, an own bonus page with three CTAs, an age gate — guard the false-positive side) and
  `VisitTest::testOfferWallIsRetriedWithAnotherIdentity` / `testOfferWallSiteIsFlaggedWhenNeverReal`
  against the fake-server hosts `offerwall.ru` (wall for YandexBot, real site for a browser) and
  `alwaysoffer.ru` (wall for everyone).
- New search sources implement `Search\RawFetcherInterface` (+ `ResponseParserInterface` if the
  format is not Yandex.XML); new visit drivers implement `Visit\DriverInterface`.
- Every new filter rule needs a reason code in `ResultFilter::reject()`, a config default in
  `Config::defaults()`, an example in `config.example.php` and a test in `tests/ResultFilterTest.php`.
- `Filter\OwnSites` marks our own templates so they are neither collected nor downloaded: markers
  (`filters.own_markers` list + gitignored `filters.own_markers_file`, default `own-markers.txt`)
  are stable substrings of the page/URL (hosting domain, `<head>` verification token, asset path) —
  never the changing codes/styles (QR, CSS). The default marker `/uploads/brands/` (asset path shared
  by all their brand templates) is in `Config::defaults()`; `ResultFilter` rejects domain markers at
  collection (`own_site`); `PageVisitor::assembleVisit()` matches HTML/host at visit time, deletes the
  HTML but keeps the home screenshot, sets `Site::$own`, reports «исключён как наш», and buckets the site
  into `pages/наши/<host>/` (screenshot only, for eyeballing) instead of `N-стр`. Real markers stay in
  the untracked `own-markers.txt`, not committed. Screenshots are captured for the home page only in
  crawl mode; `SiteLinks::canonical()` folds `/index.*` and trailing-slash aliases so a page is not
  fetched twice.
- `Runner` and `PageVisitor` accept an optional `$onProgress` callback; `bin/run-job.php` wires it
  to `Support\Progress`, and `bin/panel.php` (dual launcher/router via `PHP_SAPI==='cli-server'`)
  spawns the job and serves `public/panel.html`. Keep CLI and panel behaviour in sync through `Runtime`.
  `public/panel.html` has three tabs (`.tabsec[data-tab=main|config|stats]`, remembered in
  `localStorage['ys-tab']`): «Главная» (queries, run/stage, progress, log, results table), «Настройки»
  (keys + all filter/visit conditions) and «Статистика» (the collect history, see `Support\CollectHistory`). XMLStock params are panel fields `xmlstock_mode`/`xmlstock_device`/`xmlstock_domain`/`xmlstock_extra`
  (the `#xmlstockBox`, shown only when `source=xmlstock`), mapped in `buildOverrides()` to
  `xmlstock.mode`/`xmlstock.device`/`xmlstock.domain`/`xmlstock.extra_params` (`extra_params` parsed from a
  `key=value&…` string) and covered by `PanelTest::testXmlstockParamsReachRequest` /
  `testXmlstockLiveModeUsesLiveEndpointAndPaginatesByTen`.
- `Content\ContentCleaner` is the third stage (`settings.stage=clean`, `bin/clean-content.php`, and the
  per-site `/api/clean-site` button). It follows the user's manual STRICTLY IN ORDER (half the bugs came
  from reordering steps): **1** article body = the page's CONTENT BLOCK (`extractArticle()`, all DOM):
  `contentRoot()` = `<main>`/`role=main` holding ≥ 40% of the body text, else the whole body, after
  `stripNonArticleIn()` removed the site chrome and everything that is not article text — `<header>` outside
  `main`/`article` (an `article > header` holds the h1 + hero and is kept; a `div.header`/`.logo` outside
  `main`/`article` without an h1 is removed via `HEADER_TOKENS`), `nav`, `aside` outside `main`/`article`/
  `itemtype=Article` (an in-article aside is content), `footer` (a `<footer>` inside
  a `<blockquote>` citation is kept), `role=banner|navigation|complementary|contentinfo|dialog`, media
  (`img`, `svg`, `video`…), interactive (`form`, `input`; `button`/`label` unless inside FAQ, where a
  question-like one (`looksLikeQuestion()`: text ends with «?» or class/id has question/faq/accordion/toggle)
  becomes `<h3>` and the rest is unwrapped), `address`, HTML comments, and blocks whose class/id token is junk
  (`JUNK_TOKENS`, always: contacts, tag-cloud/keywords, social/share, popup/modal/overlay, cookie,
  breadcrumbs, ads, `toast`/`notification`/`floating`, `menu`/`navbar`/`topbar`, `skip`, and the game-catalog
  filter bar `filter`/`filters`/`dropdown`). Widgets INSIDE the content block (`WIDGET_TOKENS`: `hero`,
  `banner`, `cta`/`countdown`/`timer`/`ticker`, `jackpot`, `payout(s)`, `dashboard`, `widget`, `related`,
  `action`, `winners`) are content by default — the user's rule is «режем только шапку, меню и подвал» for
  every template — and are stripped only with `remove_widgets` (the same panel checkbox as slot catalogs).
  START: after the first `h1` only when
  `hasArticleTextBefore()` finds no article text before it (≥ 150 chars or a `<p>`/`<li>` ≥ 40 chars — the
  7–10-page template's `div.promo-text` intro is three 40–65-char paragraphs); when
  there IS text (7–10-page templates put intro paragraphs before a mid-page h1) the block is taken from its
  start and the h1 stays (step 6 turns it into h2) — cutting from the h1 lost those paragraphs. END
  (`cutAtEndMarker()`): «Популярные запросы» always (manual); «О компании»/«О портале»/«Контакты»/«Реквизиты»
  (`END_ABOUT`) only when the remainder looks like company details (`CONTACT_SIGNS`: phone, e-mail, ©, licence
  number, legal address) and is ≤ 600–1500 chars — so an in-article «О портале Бренд» section without
  contacts stays. `removeLinkClouds()` drops a cloud heading
  (`CLOUD_HEADING`: «Похожие/Популярные/Ключевые … запросы/темы», «Теги») together with the link-dense block
  after it, and any block that is ≥ 8 links making ≥ 80% of its text (menus, keyword clouds) — the text AFTER
  a mid-page cloud is kept (the old string cut at «Популярные запросы» threw it away). A page without an h1
  is an article only if the block has ≥ `MIN_ARTICLE_CHARS` (300) of text. FAQ is a SECOND STREAM by node
  identity: `faqNodes()` collects the top-level Q&A blocks (`<details>`, a `faq` class/id, `itemtype=FAQPage`)
  BEFORE any cut, and whatever is not inside the final root (a `section#faq` after `<main>`, a block after
  «Популярных запросов») is appended (`isInside()`), else JSON-LD `FAQPage` is rendered (`faqFromJsonLd()`:
  `<h2>Вопросы и ответы</h2>` + `<h3>`/`<p>`), so brand substitution covers it too. Slot/game CATALOG removal is OFF by
  default (`remove_slots`, also implied by `remove_widgets`; one panel checkbox `#removeslots` → settings
  `remove_widgets` + `remove_slots` → run-job/`/api/clean-site` override; CLI `--remove-widgets`,
  catalogs only `--remove-slots`) — on the 7–10-page template the game cards between story sections are
  content («режем только шапку и подвал»); when on, `removeSlots()` (DOM)
  drops slots/games CATALOGS while keeping the article around them: (1) a grid of game cards (`isCard()`:
  `gamecard`/`slot-card`/`game-tile`… — `CARD_TOKENS`, or card/tile + slot/game) is removed as a grid together
  with its widget shell (`removeCardGrid()`: the short caption and heading right before it — «🎡 Рулетка
  онлайн» + «Крупные ставки» — never a ≥ 120-char block, and the wrapper `div.info-block` once it is left with
  < 120 chars); on the flat 7–10-page markup a story `<h2>` + `<p>` followed by such a widget keeps its text
  (the old section-wide removal ate the story); (2) a heading with слот/игры/автоматы (whole words, so
  «выигрыш» is not «игры»; never inside FAQ, never a question ending with «?») plus its siblings up to the next
  same-or-higher heading, only when `proseCount()` finds < 2 leaf blocks (`p`/`li`/`dd`/`div`/`blockquote`)
  of ≥ 120 chars — FAQ answers in `<div>` count too; a prose section about slots on the slots page stays. **2** `applyReplacements()` over body + FAQ together: domain → `%domain_name%` (the regex
  eats an optional subdomain prefix, so `kush.casinozsd.buzz` → `%domain_name%`, not «kush.%domain_name%»),
  `dd.mm.yyyy` → `%date%`, brand → `%brand_name_ru%`/`%brand_name_en%`; the donor template's unfilled
  `{NAME}` placeholder («Где {NAME} выигрывает чаще») becomes a random male name from `RANDOM_NAMES`
  (a fresh one per occurrence; it is NOT one of our variables). This runs BEFORE unwrapping and
  attribute stripping on purpose: the own domain inside `href` becomes `%domain_name%`, which is how step 8
  tells an internal link from an external one. **3–8** `normalizeMarkup()` (DOM; every XPath is RELATIVE to
  the `ys-root` wrapper — an absolute `//div` unwrapped the wrapper itself and yielded an empty result):
  **3** remove `script`, `style`, `meta`, `link`, `noscript`, `img`, `hr`, `br`, `caption` (+ `figcaption`;
  `br`/`hr` become a newline so «Второй<br>абзац» does not fuse); **4** unwrap containers — block ones (`div`,
  `section`, `article`, `aside`, `footer`, `header`, `main`, `thead`, `tbody`, `tfoot`, `figure`) with a newline
  on each side so neighbouring text does not fuse, inline ones (`span`, `small`, `q`, `abbr`, `time`, `cite`,
  `code`, `kbd`, `samp`, `var`, `sup`, `sub`, `u`, `s`, `mark`, `ins`, `del`, `dfn`) tightly so a word split
  as `Крип<span>то</span>босс` re-joins (badge/chip/pill/label spans — `CHIP_TOKENS` — get a space instead, so
  sibling genre tags do not fuse into «TouchКаскады»; `unwrap()` never doubles a separator); **5** `em`/`i` → plain text, `b` → `strong`; **6** `h1` → `h2`, then
  `h4`/`h5`/`h6` → `h3`; **7** strip every attribute except `href` on `<a>`; **8** links — external (another
  host; `#`, `mailto:`, `tel:`, `javascript:`) are unwrapped to text, internal ones go through `mapLink()` to
  one of `ALLOWED_LINKS` (`/vhod`, `/registracia`, `/`, `/app`, `/slots`, `/zerkalo`; the home is `/`, never
  `/main`); finally `pruneEmpty()` drops empty wrappers (`<p>&nbsp;</p>`, an `<a>` around a removed image;
  table cells are left alone), `pruneOrphanHeadings()` drops a heading followed by nothing or by a higher-level
  heading (the h2 of a removed widget), and `wrapLooseText()` wraps top-level bare text runs into `<p>` (text
  that lived directly in an unwrapped `div`) — consecutive short pure-text cells (≤ 24 chars, no end
  punctuation, no block between them) are joined into ONE `<p>` («00 / Дней / 22 / Часов» → «00 Дней 22
  Часов», a card's provider/activity/RTP one line) and a number-only run with no such neighbours (the step
  counter `span.spot-cta-number` «1» before an h2 — the user's «<p>1</p> в начале страницы» artifact) is
  dropped; blank-line runs are collapsed to one newline. A second
  `applyReplacements()` pass then catches a brand that step 4 glued back
  together from `<span>` pieces (idempotent: the variables contain no brand). The output is bare semantic
  HTML — `p`, `h2`/`h3`, `ul`/`ol`/`li`, `table`/`tr`/`td`/`th`, `strong`, `a[href]`, `blockquote`,
  `details`/`summary` — with no classes or styles (the user's templates wrap it in their own markup).
  Brand matching is case-insensitive and homoglyph-tolerant
  (Latin↔Cyrillic look-alikes, so `STAKE`≡`STAKЕ`; digits may follow the brand, so the promo code «Grizzly30»
  becomes `%brand_name_en%30`, while `mistaken` never matches `stake`; a dot or dash inside the site's OWN
  brand — «Bigs.bet», «Бигс.бет», «Bigs-Bet» — matches too, but not for the known-brand list), and the site's OWN Russian brand also matches its declined
  forms («Криптобосса», «в Вулкане Вегасе» — `RU_ENDINGS`, an explicit case-ending list rather than «any 3
  letters», applied per word; deliberately NOT applied to the known/foreign brand list, where short words would
  false-match — «куш» must not eat «кушать»); a concatenated latin brand label also matches its SPACED
  spelling in the text (`cryptoboss` → «Crypto Boss», `vulkanvegas` → «Vulkan Vegas», `moneyx` → «Money X»)
  via `replaceSpacedBrands()`, which folds Title-Case multi-word runs and only replaces those whose glued
  form equals a brand — so «Good Win» maps to a brand but the phrase «a good win» is left alone.
  `Content\BrandDetector` auto-detects the brand: EN is the label of the canonical/og:url host (so a network
  where the brand sits in the subdomain — `kush.casinozsd.buzz` → `kush`, not the shared registrable domain
  `casinozsd`), falling back to the domain label — a mirror number suffix in the label is dropped
  (`grizzly-0.xki.casino` → `grizzly`, not `grizzly0`); RU is the text token — or an adjacent pair of tokens
  («Вулкан Вегас», «Мани Икс» — a brand is often two words) — whose transliteration matches. Detection pools
  ALL of a site's pages, not just the home (`detect($html, $host, $moreHtml)`), so the brand is still found
  when the home is an age-gate/redirect stub and the brand + canonical live on inner pages; generic theme
  words (`казино`/`онлайн`/`бонус`…, `RU_STOP`; `casino`/`bet`/`win`… as a domain label, `EN_GENERIC`) are
  never returned as a brand. It picks the first EN candidate that has a RU match in the text, so no manual
  input is needed; `Content\KnownBrands` adds a built-in list of casino brands — single- and multi-word,
  incl. the Vulkan family (+ gitignored `brands.txt`) — so foreign brands in the text are templated too
  (word-boundary, homoglyph-tolerant; `applyReplacements()` applies longer names first so «Вулкан Вегас» is
  not left as «%brand% Вегас»). `ContentCleaner::autoOptions()` wires detection + known brands and lets
  non-empty overrides win (extra_brands merge); `bin/panel.php` `cleanHostPages()` passes the site's other
  pages as `$moreHtml`. Panel has no stage dropdown: «Собрать сайты» (next to the queries)
  runs `stage=collect`; «Выгрузить страницы оставшихся» (above the results table) runs `stage=download`
  with `exclude_hosts` = the ✕-removed hosts, so only the sites the user kept are opened (run-job filters
  `loadSites()` by that list and rewrites `sites.json` to the kept set). `runCollect()` clears the removed
  set (fresh list); `runDownload()` keeps it. A re-run of download wipes the previous result first
  (`rrmdir()` on `runs/current/pages` and `content`) so it is a clean redo, not an append. «Докачать с
  ошибками» (`runRetry()`) sends `stage=download` with `retry_hosts` = only the sites that have something
  a retry can actually recover: `previewSites()` emits a per-site `retryable` flag computed with
  `PageVisitor::isRetryableVisit()` (timeout/connection/block/SSL/DNS, or a 404 whose URL carries a language
  prefix; never own/duplicate/plain 404), and `siteNeedsRetry()` uses that flag — so the button count matches
  what `retryFailed()` will do, and the per-site «Докачать этот сайт» button is disabled with a hint when
  `retryable === false`. The job message is honest about the outcome: «Докачано: добрано X из Y стр.» or
  «нечего добирать» (`retryFailed()` returns `{attempted, recovered}`), so a no-op retry no longer looks like
  it never started. The download branch calls `PageVisitor::retryFailed()`, which re-fetches ONLY the failed pages of those sites
  (already-downloaded pages are kept, not re-fetched) over several iterations through DIFFERENT proxies with a
  growing timeout; one candidate per page is the URL without a leading language prefix (`/ru/app → /app` —
  the prefixed form sometimes 404s while the bare one opens, `retryUrlCandidates()`/`stripLocaleFromUrl()`),
  and `isRetryableVisit()` treats such a locale-404 as retryable. `unbucketSite()` pulls the site's folder out
  of its `N-стр` bucket for the re-fetch and `bucketByPageCount()` re-buckets it after; the other sites keep
  their pages and visits (`loadSites()` restores `visits`/`own` from `sites.json` so the merged output is not
  lost). A results row expands (caret on the «Скачано» cell) into that site's
  visits **grouped by cause** (`pageCategory()`: скачано / не достучались / дубликаты / 404 / прочее — so
  duplicates and unreachable pages are separated) — URL + reason + file links — lazy-loaded from
  `/api/site-pages` (reads `sites.json`, `pagesCache` cleared when a job finishes) and carrying a per-site
  «Докачать этот сайт» button. Docкачки run as a **background queue**: `runRetryOne()`/`runRetry()` add hosts
  to `retryQueue`, `pumpRetry()` starts one download batch at a time (`retry_hosts`) when idle and auto-starts
  the next batch on completion, so the user can queue several and keep working; the results table is not
  reset while a job runs (`renderResults` keeps `lastSites` when the status is momentarily empty during a
  run), and queued/active hosts show «в очереди»/«докачивается…» chips. Above the table a stats line
  (`siteKind()`: own / problem = a failed page or no page at all / full = every page OK / unchecked)
  summarises the kept sites right after collect, and two bulk-remove buttons add hosts to `removedHosts`
  (server-side through `/api/remove` → `Support\RemovedSites`; reversible via «вернуть все» = `/api/restore`): «Убрать наши» (`s.own`; works right after collect, since the
  preview screenshots already mark own templates, so they are never even downloaded) and «Убрать с 404 > N»
  (`s.pages_404` from `previewSites()`, N from the `#max404` input, default 4; shown once download data exists). The `both`
  branch stays in `buildOverrides()`/run-job for CLI, just not surfaced. Content cleaning is table-only and
  writes to disk (no download): a per-site «Очистить» button (`/api/clean-site`) and a bulk «Очистить всё»
  button (a background `stage=clean` job started through `/api/start`) run `Content\SiteCleaner::cleanHost()`, which cleans a site's
  pages and lays the cleaned articles into a bucket by count — `runs/current/content/<N>-стр/<host>/` —
  `removeHostContent()` clearing that host from any old bucket first so re-cleaning never leaves duplicates.
  «Очистить всё» is a BACKGROUND job (`stage=clean` in `bin/run-job.php`, launched like collect/download so the
  panel stays responsive and shows «N из M сайтов» progress in the usual `visit` progress shape; 250 sites in
  one synchronous HTTP request used to time out): it takes `only` (the sites still in the table) and
  `exclude_hosts` (+ `removed.json`), first `rmTree()`s the whole `content/` dir (clean re-build, so a site
  removed after a previous «Очистить всё» does not linger), honours the Stop button, and ends by writing the
  sites list back into the status so the table survives. `bin/panel.php` keeps thin wrappers
  (`pagesByHost()`/`cleanHostPages()`/`removeHostContent()`/`rmTree()`) delegating to `Content\SiteCleaner` for
  the per-site `/api/clean-site` button. The `stage=clean` job branch is exactly what «Очистить всё» runs; `bin/clean-content.php` stays a
  separate CLI tool with its own loop. Covered by `tests/ContentCleanerTest.php`
  and `tests/BrandDetectorTest.php`.
- The previous collect must survive a page refresh, a panel restart and `setup.php --update` (the user
  works with one list for days): `Support\SiteRows` (moved out of run-job: `load()` = the old `loadSites()`,
  `preview()` = the old `previewSites()`) lets `/api/state` fall back to `sites.json` when `status.json` has
  no `sites` (a download/retry/clean job in progress after a refresh, an error status, a deleted status) —
  the response marks `sites_from_file`; a collect that selects NOTHING (everything `seen_before`/filtered)
  does not overwrite `sites.json`/`sites.csv`/`domains.txt` (`kept_previous` in the status + message «прошлый
  список сайтов оставлен»), so the table stays workable; `runs` is in `setup.php`'s `KEEP_FILES`. Covered
  by `PanelTest::testLedgerSkipsAlreadyCollectedDomains` and `testPanelRemoveAndRestoreEndpoints`.
- Removing a site from the table (✕, «Убрать наши», «Убрать без превью» = `noPreview()`: not own and no
  page opened — `pages_total > 0 && pages_ok === 0`, or no visit at all with a `page_error`; shown as soon
  as preview data exists, so the user can go to download without them; «Убрать с 404 > N») is a SERVER-SIDE, final and
  cross-stage operation — `Support\RemovedSites` (`runs/current/removed.json`): `/api/remove` drops the site's
  row from `sites.json` and from `status.json` (so the table updates on the next poll) and moves its folders
  (`pages/<bucket>/<host>`, `preview/<host>`, `content/<bucket>/<host>`) into `runs/current/removed/` keeping
  the structure; `/api/restore` brings rows and folders back. `run-job` applies `RemovedSites::filter()` right
  after `loadSites()` AND again before the final `sites.json` write (a site removed while the job ran is not
  resurrected; `sweep()` moves folders the job downloaded meanwhile), `/api/clean-all` excludes them too, and
  the collect stage calls `clear()` (a new collect is a new list). The browser keeps only a mirror of the
  server list (`removedHosts`, refreshed from `state.removed` on every poll) plus `pendingRemoved` for instant
  hiding; the old client-side pruning of that list against the current status was what lost removals on
  transient states (job restart, error status, list truncated at the preview limit — now 1000 rows).
- `Visit\SiteTemplate` classifies a site's TEMPLATE FAMILY from its home-page HTML right after collect (the
  preview visit), not from screenshots: `PAGES7` («7–9 стр.» — header with brand, «+7 (495)…»,
  «Круглосуточно · 24/7», filter bar «Все игры/Провайдеры», intro text before the h1, «Навигация»/«Быстрые
  ссылки» cloud), `PAGES12` («12–15 стр.» — «Логотип <бренд>», emoji nav, «🏠 Главная» breadcrumb, «Куда
  перейти» cards, live-win toasts, 24/7 chat bubble, welcome popup) or `OTHER` («без категории», a random
  site). `guess($html)` counts marker substrings (class/id names + typical labels) per family: strong markers
  (weight 2, found in ONE family only — `tags-cloud`, `promo-text`, `filters-section`, `company-info`,
  `Круглосуточно` / `bonusPopup`, `winNotifications`, `keywords-block`, `reserved-aux`, `quicklink`,
  `pulse-glow`…) and weak ones (weight 1, generic names like `breadcrumbs`, `site-footer`, `skip-link`,
  `entry-content`); a family wins with score ≥ `MIN_SCORE` (4) AND at least one strong marker, so a
  WordPress site with skip-link + site-footer + breadcrumbs stays `OTHER`. The obfuscated PAGES12 variant
  (random `pg-xxxxx`/`mh-xxxxx` classes) is caught by its stable ids (`reserved-aux`, `jackpots`, `levels`).
  On the 544-site reference archive: 475/475 PAGES7, 32/32 PAGES12, 0 cross-family hits. Wiring:
  `PageVisitor::assembleVisit()` stores `$visit['template']` for every saved page (preview, crawl, retry —
  the HTML is already in memory), `SiteTemplate::ofVisits()` votes across a site's ok visits (a family beats
  `other` on a tie; '' = no page opened), `SiteRows::preview()` emits `template`/`template_label`,
  `SiteTemplate::histogram()`/`histogramText()` feed `template_histogram` in the collect/download status,
  the collect message («По типу вёрстки (по главной): …») and the log («Итого по типу вёрстки»). Panel:
  a «7–9 стр.»/«12–15 стр.» tag next to the host (`siteType()`; «без категории» is not tagged), «по типу
  вёрстки: …» in the stats line, and the category filter «оставить: [x] 7–9 стр. (N) [x] 12–15 стр. (M)
  [x] без категории (K) → Оставить выбранные (убрать D)» (`#tplwrap`, `.tplkeep` checkboxes,
  `#keepTypesBtn`; all checked by default; any combination — all, one or two) which removes the unchecked
  types through the same reversible server-side `removeWhere()` → `/api/remove` path; own sites and sites
  with no opened page have no type and are never touched by it. When the templates change, re-check the
  markers (a scratch script over `pages/*/<host>/main.html` per bucket) and update `MARKERS` + the fake
  server hosts `tpl7.ru`/`tpl12.ru`; covered by `tests/SiteTemplateTest.php`,
  `VisitTest::testVisitDetectsTemplateType` and `PanelTest::testDownloadStageReportsTemplateTypes`.
- Collect stage (`stage=collect`) dedups to unique registrable domains (`unique_by=domain`) and, when
  `preview_shots` is on (panel default), runs a lightweight home-only screenshot visit into
  `runs/current/preview` (no crawl) so the results table previews volume + own sites before the full
  download; wired in `buildOverrides()`.
- `domain_scope` (all/root/subdomain) and `unique_by=domain` implement the "one site per domain,
  skip other subdomains" rule; covered by `tests/ResultFilterTest.php` and `tests/PanelTest.php`.
- `Visit\SiteLinks::fromHeader()` extracts **same-host** links from a page's header/nav **and footer**
  (home page as base; `www` folded, but sibling subdomains like `hype.`/`max.` of the same domain are
  treated as other brands and skipped), dropping sitemap/htmlmap pages and non-page file resources
  (`.xml`, `.pdf`, images…; `SiteLinks::isJunkPage()`). Language-switch loops with a real page behind
  them (`/RU-ru/RU-ru/…/app`) are **collapsed** to one occurrence (`SiteLinks::collapseRepeats`) so the
  real page is fetched once, not skipped; `SiteLinks::canonical()` also strips a leading locale segment
  (`/RU-ru/promo` ≡ `/promo`) so a language prefix does not yield a `promo-2`, and folds a path that is
  *only* a locale (`/ru`, `/ru-ru`, `/en` — `xx-xx` always, bare `xx` from a known-locale list) to the
  root so a localized home is not saved as a duplicate `main`. `PageVisitor` `visit.crawl`
  mode opens the home page, then a
  single probe link, then the rest, and drops only pages whose final URL redirects to a DIFFERENT SITE
  (`SiteLinks::sameSite`, registrable-domain compare). A redirect that stays within the same registrable
  domain is followed and kept: a site collected by its apex (`casinozsd.buzz`) whose home redirects to the
  brand subdomain (`kush.casinozsd.buzz`) is not thrown away as «редирект на другой сайт» — the home is saved,
  and the menu is parsed relative to the redirected URL (`final_url`) so the brand subdomain's links count as
  same-host (`SiteLinks::sameHost` still gates menu-link extraction to one subdomain, so sibling brands
  `hype.`/`max.` are not crawled). The visited-URL set is seeded with the entry URL, the redirected home and
  the site root so a menu link back to `/` never yields a second `main-2`. Any failed load — timeout/network,
  a block status (403/429/5xx) or an anti-bot/Cloudflare page (`PageVisitor::looksLikeBlock()`) — is retried
  through a different proxy (`visit.retries`, default 2; `PageVisitor::runWithRetry()`/`isRetryable()`); block
  pages are deleted and reported as «заблокировано», never saved as content. HTTP 404/410 responses are
  reported as «страница не найдена (HTTP 404)» and deleted, never saved — a network's soft-404 often returns
  a home-like template for missing paths, which must not be mislabeled a «дубликат» of the home page.
  Page files are named short from the URL's last path segment (`/registracia` → `registracia.html`,
  `/catalog/plastikovye/` → `plastikovye.html`, home → `main.html`; `PageVisitor::fileNameFromUrl()` +
  `uniqueName()`). One file per page NAME: a menu link whose last segment yields a name already taken for that
  site (`/vhod.html`, `/vhod?ref=menu`, `/Vhod` next to `/vhod`) is not crawled at all, and `retryFailed()` marks
  such a failed variant «дубликат» instead of re-fetching it — so `vhod-2`/`registracia-2` never appear
  (`uniqueName()` stays only as a last-resort guard). Duplicate/one-pager
  detection: `Fingerprint::text()` + `Fingerprint::similarity()` (Jaccard word-set); if the probe
  page matches home ≥ `visit.similarity` (default 0.9) the site is a one-pager and the rest are
  skipped, and matching inner pages are dropped (`PageVisitor::dedupVisit()`). The comparison texts are
  tracked with their page label/url, so a duplicate names its reference — «дубликат: совпадает с главной
  / с «registracia» на N%» — and carries `duplicate_of` (the reference URL) in the visit. Finished sites are
  bucketed into `pages/<N>-стр/<host>/` by successful-page count (`PageVisitor::bucketByPageCount()`); the move
  is a MERGE (`moveDirMerge()`: file by file when the target folder exists, newer wins, empty source removed) and
  `unbucketSite()` merges EVERY copy of the host folder (`pages/*/<host>` + `pages/<host>`) before a retry — a
  plain `rename()` used to fail silently when the target existed, leaving a site's pages split across two
  buckets while the table said «9/9». `markMissingFiles()` (end of visit/crawl/retry, and right after unbucket in
  `retryFailed()`) turns an ok visit whose html file is gone into a failure «файл страницы отсутствует на диске»
  (retryable), and `SiteRows::preview()` reports `pages_missing` so the panel shows «нет файла на диске: N» and
  «Докачать» re-fetches exactly those pages. After a download the panel's stats line, the job message
  («Выгружено страниц: N; по страницам: 1 стр. — 12, 9 стр. — 5») and the log («Итого по папкам») show the
  page-count breakdown (`SiteRows::pageHistogram()`/`histogramText()`, `page_histogram` in the status).
  `SiteCleaner::cleanHost()` returns `skipped_files` and the clean
  job logs «без статьи: a.html, b.html» per site, so a page lost at cleaning is visible by name.
  Barrier stubs (age-gate 18+, cookie wall, "enable JavaScript") look identical on every URL but hide
  different content, so `PageVisitor::looksLikeStub()` excludes them from dedup (never a duplicate/one-pager,
  never a similarity reference; visit flagged `stub`). The Playwright renderer best-effort dismisses such
  gates before capture (`passGate()` in `tools/render-page.js`): it finds the barrier by role/position
  (`[role=dialog]`, `[aria-modal=true]`, `<dialog open>`, or a large fixed overlay — obfuscated per-site
  class names are ignored), confirms it is an age/cookie barrier via the *overlay's own* text (footer «18+»
  no longer misfires or blocks it), and clicks the consent button (e.g. «Мне есть 18») strictly inside it.
- `Support\CollectHistory` (`runs/history.json`, newest first, `LIMIT` 500) is the «Статистика» tab, and
  it is entirely about ДОРЫ — the user cut the first version down to exactly that: «зоны анализируются
  именно у поддоменов (доров), отсеяно фильтрами меня не волнует, количество запросов тоже — собрано
  доменов, доров (процент и количество от общей массы), зоны доров, повторы ДОРОВ». The base of that
  percentage is the WHOLE SERP MASS, not the selection: their `domain_scope` filter drops root domains
  («не тот тип домена — 13250»), so among the SELECTED sites doors were 94.6% and the number said
  nothing — «надо отталкиваться от общего числа всех видов доменов… всего результатов в выдаче, не тот
  тип домена тоже нам подходит». The record is therefore a FUNNEL where every number follows from the
  previous one («переделай чтоб и на главной и в статистике были понятные данные, без повторов»;
  «1 — результаты выдачи все не уникальное, 2 — уникальных доменов и поддоменов (уже после группировки
  «один сайт на домен»). И потом из этого числа количество доров. А потом уже фильтр отсева»):
  `results` (every SERP row) → `found` (DISTINCT normalized hosts) → `unique_sites` (what that is after
  the Aggregator's grouping — with `unique_by=domain` all doors of one network are ONE site) →
  `found_doors`/`found_roots` + `zones` COUNTED ON THOSE GROUPS → `cut` (what the filters removed, BY
  SITE and per reason, with the doors among them) → SELECTED (`sites`, `doors`, `roots`, `own`), plus
  `repeats`/`repeats_doors`, `base_domains`, `resume`, `stopped` — and deliberately NOT queries.
  The invariant is `unique_sites == sites + cutTotal(cut)`, asserted both in `CollectHistoryTest` and
  end to end in `PanelTest::testCollectWritesHistoryAndStatsEndpoint`: it is the answer to «куда делись
  6460 доменов, если отобрано 602». Counting the mass by HOST made that question unanswerable — 6460
  addresses never turn into 602 sites directly, because the doors of one network collapse first.
  `breakdownRaw()` delegates to `breakdownRows(iterable $rows, $uniqueBy)` (triples
  `[host, position, reason]`), which groups like `Aggregator` (key = registrable domain or host, from
  `stats['unique_by']`, set by `Runner`) and takes each group's representative host from its BEST result
  — the best PASSING one when the group passed, since that is the address that would land in the table.
  A group lands in `cut` only when NONE of its results passed, under the reason of its best result; the
  reasons that fire AFTER grouping (`min_queries`, `min_hits`, `seen_before`, `site_check:*`) are already
  per-site counters in `Runner`, so `record()` copies them from `stats['rejected']` (with `seen_before`
  carrying `repeats_doors` as its door count). `Runner` also keeps a live `$seenKeys` set →
  `stats['unique_sites']`, so the panel's progress funnel shows the same number while the collect runs.
  `CollectHistory::REASONS`/`reasonLabel()`/`cutText()` give the Russian labels for the log and CSV;
  `public/panel.html` has the same map in `CUT_LABELS`/`cutHtml()`. The panel's «Доля доров» and `totals()`
  `doors_percent` divide `found_doors` by `unique_sites`, falling back to `found` for records written
  before 1.16.0 and to the selected pair for records before 1.13.0 (which have no `found`). `isDoor($host)` = the normalized host is
  longer than its registrable domain (`www.` folded first, and `Domains::SECOND_LEVEL` means
  `kush.net.ru` is NOT a door). The host MUST come from `Site::realHost()`, never `Site::$host`: with
  `filters.unique_by = domain` (the panel's «один сайт на домен», on by default) `Aggregator` puts the
  REGISTRABLE DOMAIN in `$host`, so every door read as a root and the user's first real collect showed
  «339 доменов, доров 0». `realHost()` takes the final URL of an ok visit first (a network collected by
  its apex redirects the home to the brand subdomain — that is a door too), then `bestUrl`, then any
  collected URL, then `$host`. `breakdown()` counts doors/roots and builds `zones` FROM DOORS ONLY;
  `percent()` is the share. Door repeats need the hosts, not a counter, so `Runner` pushes every
  `seen_before` host into `RunResult::$seenBefore` (a separate field, NOT `stats` — the status and
  sites.json must not carry a list of thousands) and `record()` counts the doors among them. One record per collect, written in TWO steps
  from `$result->sites` (THIS run's selection — the table may carry earlier batches). `Runner` calls its
  new `$onSelected($sites, $result)` hook as soon as the domains are selected and checked, BEFORE the
  visit stage, and `bin/run-job.php` appends the record there («мне кажется статистику можно наполнять на
  моменте когда домены собрались, не ждать прохода по сайтам с скринами») — the crawl of hundreds of sites
  takes ages and the numbers are already final; the record also survives a force-kill during the visits.
  The record carries an `id`, and the end of the collect stage patches THAT record through
  `CollectHistory::update()` with the final `doors`/`roots` (a visit may reveal an apex redirecting to a
  brand subdomain — also a door), `own`, `base_domains` and `stopped`; `found*`/`zones` come from the raw SERP
  and never change after the visits, so they are not patched; if the patch finds no
  record (an old job, selection never reached), it appends one as before, so there is always exactly one
  row per collect. OWN sites («внеси как-то в скрипт еще и подсчет наших и процент / ты их определяешь
  скринами» — they are NOT read off the screenshot: `Site::$own` is set by `PageVisitor` from the HTML
  markers of `Filter\OwnSites`, the shot is only there to eyeball it) are counted by `breakdown()` as
  `own` and shown as a share of the SELECTED sites (`totals()['own_percent']`), because a SERP row alone
  cannot tell our template from anybody else's — the flag appears on the preview visit, which is why the
  early record says 0 and the end-of-collect patch fixes it. The same numbers go to the log («За этот сбор:
  N доменов, из них доров (поддоменов) M (X%), повторов доров …», «Наши шаблоны среди отобранного …») and
  to the collect message; the panel's own stats line above the results table prints the same percent next
  to «наших N». Panel: `GET /api/history` returns
  `records` + `totals()` (sums, plus `doors_percent`/`own_percent`/`cut_total` and a merged `cut`;
  `base_domains` is the newest record's ledger size,
  not a sum). The tab's main view is the FUNNEL ITSELF — «так статистику и веди как ты описал в цепочке,
  чтоб было наглядно и чтоб и проценты были на разных шагах»: `renderFunnel(record)` draws one `.fnrow`
  per step (label · number · bar · percent) with indented `.sub` rows for doors/roots, for every `cut`
  reason (percent of the mass + «доров N») and for doors/own among the selected, in TWO scales that are
  each labelled by a `.fnsep`: the first block (строки → адреса → сайты) is scaled to `results`, the
  second (everything after) to the mass, because a 602-of-24544 bar is invisible on one scale. Old
  records degrade in place: no `results` → the first block is skipped and the mass row is marked «*»
  «без группировки»; no `cut` → one «разбивки нет · старая запись» row. `#statRun` switches the funnel
  between «За всё время» (`totals()`) and any single collect (default: the newest), and clicking a table
  row selects it (`.selrow`). The old summary-card grid was REMOVED with `statBox()` — it repeated every
  funnel number. `loadStats()` also renders the door-zone chips (of the selected collect, or of all time),
  the base/runs line and the table (the door-repeat cell carries the total repeats in its `title`, the
  «Срезано» cell the per-reason breakdown, the «Сайтов в выдаче» cell the host count before grouping),
  `GET /download?file=history` builds `csv()` on the fly
  (zones and the cut breakdown each folded into one column so new reasons cannot widen the table). The tab reloads on click and
  whenever a job finishes while it is open. The file lives in `runs/` (not `runs/current/`), so it
  survives `setup.php --update`. It does NOT survive `/api/reset-base` any more: the user cleared the base
  and expected the statistics to go with it («я отчистил базу, сбрось и статистику»), so that endpoint
  calls `CollectHistory::clear()` too and reports `history` (records removed); `POST /api/reset-history`
  («очистить статистику» next to «очистить базу и файлы» in the settings tab) clears ONLY the history and
  leaves the ledger and the run files alone. `load()` maps the
  1.10.0 key `subdomains` onto `doors` so an early history still reads. Records written by 1.10.0–1.11.0
  counted doors off `$host` and therefore say 0, and records before 1.15.0 have no `own` key at all:
  `backfillLatest()` (called from `/api/history`) recomputes the NEWEST record from `sites.json` when its
  site count matches the table — doors/roots (and `zones` only for a pre-1.13.0 record, which has no
  `found`: since 1.13.0 the zones belong to the whole SERP mass and must not be overwritten with the
  selected ones) when it says 0 doors, and `own` when the key is missing — then saves it back, the same
  lazy-upgrade pattern as `SiteRows::backfillTemplates()`. A row with no `own` key shows «—», not «0», so
  an old collect does not claim it had no own templates. `backfillFunnel()` (also called from
  `/api/history`, before `backfillLatest()`) recomputes the NEWEST record's `unique_sites`/`found_doors`/
  `found_roots`/`zones`/`cut` from `runs/current/results.csv` — the raw SERP rows with their reasons are
  in that file — but ONLY when the file describes exactly that collect (its row count equals the record's
  `results` AND its distinct-host count equals `found`; a collect done in parts writes one results.csv for
  several records). Reasons that fire after grouping are not in the file: `seen_before` comes from the
  record's own `repeats`, and any unexplained remainder goes into an `other` bucket labelled «прочее
  (старая запись)» so the invariant still holds. Zones are recomputed together with the doors — leaving
  the host-level ones would contradict the new count. Door repeats cannot be recovered that way (the
  rejected hosts are not on disk) and stay as written. Nothing else is backfilled: pre-1.10.0 collects have no records at all
  and the tab says so. Covered by `tests/CollectHistoryTest.php` (incl.
  `testFunnelAddsUpAndNamesWhatWasCut`, `testGroupingFollowsUniqueBySetting`,
  `testBackfillFunnelRecomputesFromResultsCsv`), `RunnerTest::testCountsUniqueHostsSeparatelyFromResults`,
  `PanelTest::testCollectWritesHistoryAndStatsEndpoint` (asserts the invariant on a real collect) and
  `PanelTest::testHistoryCountsOwnSitesForOldRecords` (both backfills on one record).
- The panel's progress cards are a FUNNEL with no repeated number, because «29 904 результата» next to
  «2 043 сайта» read as a contradiction («а почему результатов в выдаче 29к, а доменов 7к — это
  уникальных?»): запросов → `results` (every SERP row; one site counts again in each query that found it)
  → `unique_sites` (the SERP mass GROUPED the way the collect groups it — `Runner` keeps a `$seenKeys`
  set next to `$seenHosts`, so both are live; the raw host count `hosts_total` is now only the card's
  tooltip, because 6460 addresses never turn into 602 sites directly and the two cards read as a
  contradiction) → `sites_selected` (after the filters) → `new_domains`, shown ONLY when it differs from
  `sites_selected` (with `skip_known` on they are always equal — that was one of the duplicate cards).
  Each card carries a `title` explaining the step; «отобрано сайтов» says explicitly that it is the
  filter result and NOT «the site opened» — the user asked «это те что мы смогли зайти без ошибки или
  как?». The live «Отсеяно» line is labelled «(по строкам выдачи)» with a tooltip pointing at the
  per-site recount in the statistics tab, because its row-level and site-level counters cannot be added. The «Статистика» tab uses the same wording and the
  same numbers, so the two screens can be compared line by line.
- `Support\DomainLedger` (runs/domains-base.txt) is a cross-run base of collected registrable
  domains; `Runner` takes an optional ledger + skipKnown to drop already-seen domains (reason
  `seen_before`) and record new ones. A repeat collect with the same queries therefore selects nothing
  (every domain is `seen_before`) AND makes no source requests (responses come from the cache — panel collects
  set `cache.ttl` to 1 hour in `buildOverrides()`, the CLI keeps the 7-day config default), which
  the user read as «he does not even fetch the XML queries»: `bin/run-job.php` records `cache_hits`/
  `cache_misses` in `stats` (from `CachingFetcher`), the panel shows «ответов из кэша выдачи» and, when
  `seen_before` is ≥ 80% of the rejections, says «Ничего нового: N из M доменов уже в базе пересечений…»
  (+ a cache note) instead of blaming the filters; the panel checkbox «Свежая выдача» (`settings.no_cache`
  → `cache.enabled=false`) refetches. Covered by `PanelTest::testLedgerSkipsAlreadyCollectedDomains`. The panel job has two stages (`settings.stage`): `collect`
  (grow the base, no visits), `download` (open the previously collected sites.json, minus
  `settings.exclude_hosts` — the sites removed with ✕; with `settings.retry_hosts` it re-fetches only
  those hosts and keeps the rest), `both`.
  `settings.top` limits the SERP to the first N results (max_position + one page).
- When Yandex changes its SERP markup, update `Live\HtmlResponseParser` and `tests/fixtures/serp.html`
  together; `--parse-html` helps to check a saved page.
- The download stage opens EXACTLY the sites in the panel table: `runDownload()` sends `only` = the hosts
  currently visible (not removed) alongside `exclude_hosts`, and `bin/run-job.php` restricts `loadSites()` to
  that list (a host in `sites.json` but not in `only` is logged as «в таблице нет — не выгружаем» and dropped
  from the rewritten `sites.json`, like an excluded one). The table used to be capped at 1000 rows
  (`previewSites()`/`SiteRows::preview()`), so sites beyond the cap were invisible, untouched by the type
  filter and still downloaded («выкачиваются сайты, которых не видно в таблице»); the cap is now
  `SiteRows::ROW_LIMIT` (5000), every status carries `sites_count` and the panel says «показаны первые N из
  M» when truncated. `renderResults()` rebuilds the `<tbody>` only when its HTML changed (`lastTableHtml`) —
  thousands of rows re-rendered every 1.5 s poll made the panel sluggish. Retries (`retry_hosts`) are
  unchanged. Covered by `PanelTest::testDownloadStageOpensOnlyTableSites`.
- «Скачать архив контента» (`#contentZipBtn`, an `<a>` styled as a button next to «Очистить всё», shown when
  `/api/state` reports `content_files > 0`, label «(N стр., сайтов M)» from `contentStats()`) downloads
  `GET /download?file=content`: `bin/panel.php` builds a FRESH `runs/current/content.zip` with
  `Support\Archive::zipDir()` from `runs/current/content/` at click time (entries `N-стр/<host>/<page>.html`,
  no extra top-level folder, so it unpacks straight into the user's target folder) and streams it as
  `content-YYYY-MM-DD.zip`; 404 with a Russian message when there is no cleaned content, 500 with the
  archiver's message otherwise. `Archive` uses `ZipArchive` when the PHP zip extension is loaded and falls
  back to the system `tar -a -cf x.zip` (bsdtar on Windows 10+/macOS writes zip by extension; GNU tar on Linux
  cannot, which `isZip()` detects → RuntimeException «включите extension=zip»). `bin/clean-content.php --zip`
  keeps its own ZipArchive-only code. Covered by `tests/ArchiveTest.php` and
  `PanelTest::testContentArchiveDownload`.
- `Visit\KeyPages` reports the pages the CONTENT links to — `registracia`, `vhod`, `zerkalo`, `bonus`,
  `app`, `slots` (`PAGES`: label + URL words, matched on the LAST path segment like
  `ContentCleaner::mapLink()`, `bonus` before `app` so «бонусы» is its own page). A missing one is a dead
  link in the cleaned article, and the user counted them by hand («Чего не хватает (541 сайт):
  registracia 213, vhod 115…»), so the panel now shows it: `statuses($visits)` returns `ok` / `failed`
  (a link existed but the page did not load — retryable) / `none` (no link found at all), `missing()`
  lists the not-ok ones, `histogram()`/`histogramText()` aggregate per site. `SiteRows::preview()` emits
  `key_missing` + `key_failed`, the download status carries `key_pages`, and the job message and log say
  «не хватает: регистрация — 213, …». Panel: a «нет: регистрация, зеркало» chip in the «Скачано» cell,
  «не хватает страниц у N сайтов: …» in the stats line, a «нет страницы [любая|…] → Убрать (N)» control
  (`#keywrap`/`#keysel`/`#removeKeyBtn`, `noKeyPage()`) and «Добрать ключевые (N)» (`runKeyRetry()` →
  `queueRetry(hosts, true)`; `retryKeyHosts` marks the batch so `pumpRetry()` sends
  `retry_key_pages: true`, restored if the start is rejected). With that flag `visit.retry_key_pages`
  (default OFF, so an ordinary retry makes no extra requests) `PageVisitor::retryFailed()` adds a slot per
  `none` key page with ONE candidate — the standard path built from the site's own root
  (`KeyPages::url(rootUrl, name)`, scheme/port from an already-opened page, not a hardcoded https://host)
  — appends the visit on success and, on a non-retryable answer (404), drops it without writing a failed
  visit, so the page counter is not spoiled. Covered by `tests/KeyPagesTest.php`,
  `VisitTest::testRetryFetchesKeyPagesByStandardUrl`, `SiteRowsTest` and
  `PanelTest::testDownloadStageOpensCollectedSites`.
- SPEED. Everything used to be strictly serial, which is what the user felt as «очень медленно»:
  (1) **search** — `AbstractApiFetcher::fetch()` one request at a time with `api.delay_ms` between them,
  so 3000 queries = hours of pure latency; (2) **screenshots/crawl** — `tools/render-page.js` grouped jobs
  by proxy and ran the groups ONE AFTER ANOTHER (`for … await runGroup`), so extra proxies bought nothing,
  with `visit.concurrency` 2, a GLOBAL `delay_ms` of 1500 and `wait_ms` 2500 per page on top; (3) **retry**
  (`PageVisitor::retryFailed()`) looped site by site, launching a fresh Chromium per site PER ITERATION.
  Fixes: `HttpClient::requestMany()` (curl_multi, keeps request keys, returns `HttpResponse|HttpException`
  per key) + `Search\BatchFetcherInterface::fetchMany()` implemented by `AbstractApiFetcher` (one throttle
  per batch, retryable failures fall back to the normal single `fetch()`) and `CachingFetcher` (cache hits
  served first, misses batched); `AbstractApiFetcher` subclasses now expose `buildRequest()` +
  `parseResponse()` instead of `fetchOnce()`. `Search\Prefetcher` keeps `Runner`'s per-query loop intact:
  it pulls page 0 for the next `search.concurrency` queries in ONE parallel batch and only requests page
  N+1 for the queries whose page N was full (same rule as the Runner, so no extra source requests); live
  SERP is not a `BatchFetcherInterface`, so it stays serial. `render-page.js` runs proxy groups in parallel
  through a pool of `options.browsers` browsers, skips `networkidle` and blocks images/media/fonts for
  pages without a screenshot (crawl HTML doesn't need them; the markup — and so the own-site marker
  `/uploads/brands/` — is unaffected), shortens the gate waits and gates repeat visits PER HOST
  (`hostGate`, module-level so it spans browsers). `CurlDriver` does the same per proxy AND per host
  (`gateKey()`) instead of one global delay. `retryFailed()` now builds all sites' slots first, then runs
  ONE driver pass per iteration across every site («Докачка, попытка N из M: X стр. на Y сайтах»), then
  finalises and buckets. New defaults: `search.concurrency` 5, `visit.concurrency` 4, `visit.browsers` 2,
  `visit.delay_ms` 400, `visit.wait_ms` 1200; panel fields `searchthreads`/`visitthreads`/`browsers` →
  settings `search_threads`/`visit_threads`/`browsers` → those config keys. Covered by
  `tests/HttpClientTest.php`, `tests/PrefetcherTest.php`,
  `RunnerTest::testFetchesQueriesInParallelBatches` and the existing `VisitTest` suite.
- A 3000-query list is collected IN PARTS, because waiting for the whole list before touching any site is
  what the user actually complained about. `Support\QueryQueue` (`runs/current/queue.json`: `queries` +
  `done`) remembers the position; `Runner` takes a `$shouldStop` callback (checked BETWEEN queries, so a
  query is atomic and `results.csv` has no half-query) and returns `RunResult::$stopped` +
  `$processed` (counts failed queries too, otherwise resume loops on a broken one). `/api/stop` is now
  GRACEFUL — it only writes the `stop` file, the job finishes the current query, still runs the preview
  visits for what it collected and saves `sites.json` + the queue position; `{"force":true}` keeps the old
  kill for a hung job (panel button «Прервать принудительно», shown while `state.stopping`). `/api/state`
  therefore reports `running` = live process and a separate `stopping` flag, and `/api/start` refuses to
  start while the previous job is still saving. Collect stage (`bin/run-job.php`): without `resume` it
  starts a fresh queue from `settings.queries`; with `resume` it takes `QueryQueue::remaining()` after
  `sync()`ing the queue with the current textarea list (the user may have removed duplicates or appended
  queries — processed head is never touched, the tail follows the list), advances `done` by
  `$result->processed`, merges the new sites with the previous `sites.json` by host (`resume` without
  `reset_sites`) or starts the table from scratch (`reset_sites`, which also clears `removed.json`),
  appends to `results.csv` (`ReportWriter::writeRawCsv($rows, $path, append: true)`) so query-dupes still
  covers the whole list, and puts `queue` + `stopped_early` into the status. Panel: «Продолжить сбор (N)»
  next to «Собрать сайты» opens a two-button ask («Оставить» / «Очистить таблицу») wired to
  `resume(reset)`, and «Запросы списка: пройдено N из M» comes from `state.queue`. Because batches are now
  a normal workflow, NEITHER stage wipes whole directories any more: download removes only the folders of
  the sites it downloads plus `exclude_hosts` (`removeSiteFolders()`), and `stage=clean` removes only the
  excluded hosts' content (`cleanHost()` already clears its own host) — a full `rrmdir(pages|content)`
  would destroy the parts the user already downloaded and cleaned.
  A FRESH collect is the one place that still starts from a clean disk (`wipeRunOutput()` in
  `bin/run-job.php`, guarded by `if (!$resume)` next to `RemovedSites::clear()`): it deletes `pages/`,
  `content/`, `preview/`, `removed/` and `content.zip`, and logs «Новый сбор: прежние страницы и контент
  удалены (N файлов)». Without it the previous run's articles stayed in `content/`, the clean stage only
  ever touches its own hosts, and «Скачать архив контента» (which rebuilds the zip from the whole folder at
  click time) handed the user an archive mixing the new sites with the old ones — exactly what they
  reported. The panel asks first: `/api/state` reports `pages_sites` (downloaded site folders) next to
  `content_files`, and `runCollect()` confirms «Новый сбор удалит результаты прошлого: … Скачайте архив
  контента, если он ещё нужен» when either is non-zero (the last `/api/state` body is kept in `lastState`).
  «Продолжить сбор» never wipes. `repeat_hours` is ignored on resume.
  Covered by `tests/QueryQueueTest.php`, `RunnerTest::testStopBetweenQueriesKeepsCollectedPart`,
  `PanelTest::testResumeCollectContinuesQueueAndMergesTable` (asserts both directions: a fresh collect
  removes the old `pages`/`content`/`content.zip`, a resume keeps the previous part),
  `testRedownloadClearsPreviousPages` and `testCleanStageRunsInBackgroundForKeptSitesOnly`.
- `Support\QueryDupes` finds queries whose SERP is the same SET of sites
 (registrable domains, `www` folded,
  positions ignored): `find(rows, queries)` groups queries by the sorted domain set, keeps the first query of
  each group in the ORDER OF THE USER'S LIST (`settings.queries`) and reports `duplicates`, `groups`
  (`kept`/`duplicates`/`sites`), `unique` and `no_results` (queries with no result at all are NOT duplicates,
  only counted). Rows come from `rawRows(RunResult::$raw)` at the end of the collect stage (run-job writes
  `queries-unique.txt` + `query-dupes.txt` next to the results and puts `query_dupes` = `summary()` into the
  status) or from `csvRows(results.csv)` for `GET /api/query-dupes` in `bin/panel.php`, so the panel can
  evaluate the collect the user already has (the request came mid-collect of 3000 queries). The panel
  (`#dupesBox` under the queries textarea) fetches it once per `results_stamp` (mtime-size of `results.csv`
  in `/api/state`, never while a job runs), shows «N запросов-дублей в G группах из T», and «Убрать дубли из
  списка (P)» drops those lines from the textarea (+ `saveLocal()`), P = duplicates still present; the
  `/download` map serves `queries-unique` / `query-dupes`. Exact set equality only — a similarity threshold
  is a possible follow-up. Covered by `tests/QueryDupesTest.php`, `PanelTest::testRunJobProducesResults`
  and `PanelTest::testQueryDupesEndpointAndDownloads`.
- `/api/reset-base` («очистить базу и файлы» in the settings tab) is a FULL reset, not just the domain
  ledger: it empties `runs/domains-base.txt` and `resetRunFiles()` deletes the run's working data —
  `pages/`, `content/`, `preview/`, `removed/` plus `sites.json|csv`, `domains.txt`, `results.csv`,
  `content.zip`, `removed.json`, `queue.json`, the query-dupes files and `status.json`, plus
  `runs/history.json` through `CollectHistory::clear()` (`settings.json` and the query list stay,
  `run.log` is truncated). The user asked for this: the content archive is
  downloaded through the panel, so those folders are technical leftovers. It refuses with 409 while a job
  is alive (it writes into those folders), returns `{files, dirs}` for the panel's «Очищено: удалено
  файлов N», and the confirm dialog spells out what disappears. The browser mirror (`lastSites`,
  `removedHosts`, `queueInfo`, `dupes`) is cleared client-side on success. Covered by
  `PanelTest::testResetBaseWipesRunFiles`.
- `Cli\Application::VERSION` / `VERSION_DATE` are the only version markers
 and the user's way to verify an
  update (they run `setup.php --update`, which downloads the branch zip, so there is no git metadata on their
  machine): BUMP BOTH in every user-facing change. `setup.php --update` prints «версия X от DD.MM.YYYY» (parsed
  by regex from `Application.php`) plus a reminder to restart the panel, `bin/panel.php` prints the same at
  launch, `/api/state` returns `version`/`version_date` and `public/panel.html` shows «версия X от …» in the
  `<h1>` (`#version`; `Cache-Control: no-store` on `/` keeps the HTML fresh); `/api/state` also returns
  `project_dir` (the launcher's `getcwd()`, i.e. the folder to `cd` into), shown under the title (`#projDir`)
  and printed at launch («Папка проекта: …») because the user kept asking for the path. A running panel keeps the OLD
  code until restarted — say so whenever the user reports «не вижу». Data written by an older version is
  upgraded lazily: `/api/state` rebuilds status rows that lack the `template` key (or the `sites.json`
  fallback) through `SiteRows::backfillTemplates()` (guesses the family from each saved page once, ≤ 2 MB) and
  `SiteRows::saveTemplates()` (writes the types into `sites.json`), and persists the rebuilt rows into
  `status.json` when no job runs — so a feature derived from saved pages appears on the existing collect right
  after an update. Covered by `PanelTest::testPanelBackfillsTemplateTypesAndReportsVersion`,
  `SiteRowsTest::testBackfillTemplatesReadsSavedHtmlAndSavesIntoSitesJson` and `SetupTest`.
- Run `php tests/lint.php && php tests/run.php` after changes.
