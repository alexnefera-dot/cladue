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
│   ├── Visit/                  # PageVisitor, DriverInterface, PlaywrightDriver, CurlDriver, VisitJob, Fingerprint
│   ├── Filter/                 # ResultFilter rules, DomainMatcher, TextMatcher, Domains helpers, DefaultExclusions
│   ├── Check/                  # SiteChecker (curl_multi), CheckResult, Html helpers
│   ├── Output/ReportWriter.php # CSV / JSON / domains.txt writers
│   ├── Model/                  # SearchResult, SearchPage (hasMore), Site (check + visits)
│   ├── Http/                   # HttpClient (curl wrapper with proxy/cookie/follow options), HttpResponse, HttpException
│   ├── Runtime.php             # shared pipeline factory (fetcher/cache/proxies/checker/visitor) used by CLI and job
│   ├── Content/                # ContentCleaner (article-body extraction, link normalization, %var% templating)
│   └── Support/                # Logger (STDERR), QueryList (query file reader), Progress (status JSON writer)
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
| `YANDEX_REST_ENDPOINT`, `YANDEX_XML_ENDPOINT`, `XMLSTOCK_ENDPOINT`, `YANDEX_LIVE_DOMAIN` | endpoint overrides (fake server, gateways) |
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
  Yandex.XML-compatible response parsed by `XmlResponseParser`.
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
- Default User-Agent for visits and site checks is `UserAgents::YANDEX_BOT` (the first visit variant
  shows the page as served to Yandex's crawler); additional variants use `UserAgents::BROWSERS`.
  The live SERP fetch always uses browser agents. `--user-agent` overrides visits/checks only.
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
- `Content\ContentCleaner` is the third stage (`settings.stage=clean`, `bin/clean-content.php`, and the
  per-site `/api/clean-site` button): from a downloaded page it keeps only the article body (after
  `</h1>`, before «Популярные запросы»; drops the slots section, header/footer/scripts), rewrites every
  `<a href>` to one of six relative paths (`ALLOWED_LINKS`, mapped by keyword), and templates the domain
  → `%domain_name%`, `dd.mm.yyyy` → `%date%`, brand → `%brand_name_ru%`/`%brand_name_en%`. Brand matching
  is case-insensitive and homoglyph-tolerant (Latin↔Cyrillic look-alikes, so `STAKE`≡`STAKЕ`).
  `Content\BrandDetector` auto-detects the brand (EN from the domain label, RU by finding the text token
  whose transliteration matches), so no manual input is needed; `Content\KnownBrands` adds a built-in list
  of casino brands (+ gitignored `brands.txt`) so foreign brands in the text are templated too (word-boundary,
  homoglyph-tolerant match). `ContentCleaner::autoOptions()` wires detection + known brands and lets non-empty
  overrides win (extra_brands merge). Panel: a per-site «Забрать контент» button (`/api/clean-site` →
  `content-<host>.zip`) and a bulk «Забрать весь контент» button (`/api/clean-all` → `content.zip`);
  shared helpers `pagesByHost()`/`cleanHostPages()`/`zipContent()` in `bin/panel.php`. The bulk stage
  (`stage=clean`) reads `runs/current/pages` → `content` + `content.zip`. Covered by
  `tests/ContentCleanerTest.php` and `tests/BrandDetectorTest.php`.
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
  (`/RU-ru/promo` ≡ `/promo`) so a language prefix does not yield a `promo-2`. `PageVisitor` `visit.crawl`
  mode opens the home page, then a
  single probe link, then the rest, and drops pages whose final URL redirects to another host
  (`SiteLinks::sameHost`, www-insensitive). The visited-URL set is seeded with both the entry URL and
  the site root so a menu link back to `/` never yields a second `main-2`. Any failed load — timeout/network,
  a block status (403/429/5xx) or an anti-bot/Cloudflare page (`PageVisitor::looksLikeBlock()`) — is retried
  through a different proxy (`visit.retries`, default 2; `PageVisitor::runWithRetry()`/`isRetryable()`); block
  pages are deleted and reported as «заблокировано», never saved as content.
  Page files are named short from the URL's last path segment (`/registracia` → `registracia.html`,
  `/catalog/plastikovye/` → `plastikovye.html`, home → `main.html`; `PageVisitor::fileNameFromUrl()` +
  `uniqueName()`). Duplicate/one-pager
  detection: `Fingerprint::text()` + `Fingerprint::similarity()` (Jaccard word-set); if the probe
  page matches home ≥ `visit.similarity` (default 0.9) the site is a one-pager and the rest are
  skipped, and matching inner pages are dropped (`PageVisitor::dedupVisit()`). Finished sites are
  bucketed into `pages/<N>-стр/<host>/` by successful-page count (`PageVisitor::bucketByPageCount()`).
  Barrier stubs (age-gate 18+, cookie wall, "enable JavaScript") look identical on every URL but hide
  different content, so `PageVisitor::looksLikeStub()` excludes them from dedup (never a duplicate/one-pager,
  never a similarity reference; visit flagged `stub`). The Playwright renderer best-effort dismisses such
  gates before capture (`passGate()` in `tools/render-page.js`, guarded by an age/cookie context check so
  it never misfires on normal pages).
- `Support\DomainLedger` (runs/domains-base.txt) is a cross-run base of collected registrable
  domains; `Runner` takes an optional ledger + skipKnown to drop already-seen domains (reason
  `seen_before`) and record new ones. The panel job has two stages (`settings.stage`): `collect`
  (grow the base, no visits), `download` (open the previously collected sites.json), `both`.
  `settings.top` limits the SERP to the first N results (max_position + one page).
- When Yandex changes its SERP markup, update `Live\HtmlResponseParser` and `tests/fixtures/serp.html`
  together; `--parse-html` helps to check a saved page.
- Run `php tests/lint.php && php tests/run.php` after changes.
