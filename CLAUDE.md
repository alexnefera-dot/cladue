# CLAUDE.md

This file provides guidance to Claude Code and other AI assistants working in this repository.

---

## Repository Overview

**Repository:** `alexnefera-dot/cladue`

`yandex-sites` — a dependency-free PHP CLI tool that runs a list of search queries through the
official Yandex Search API (Yandex Cloud), collects the sites from the results and selects the
"needed" ones using configurable rules (TLDs, domain allow/deny lists, title/snippet keywords,
URL regexes, minimum number of matching queries) with an optional parallel HTTP check of the
selected sites. Output: `sites.csv`, `sites.json`, `domains.txt`. API responses are cached on disk.

User-facing documentation (README, CLI help, config comments) is in Russian; identifiers are English.

---

## Project Structure

```
cladue/
├── bin/yandex-sites.php        # CLI entry point (works with or without composer autoload)
├── src/
│   ├── Cli/Application.php     # argument parsing, dependency wiring, summary output
│   ├── Config.php              # defaults, config.php loading, .env, validation, dot-path access
│   ├── Runner.php              # pipeline: queries → API → filters → sites → site check
│   ├── RunResult.php           # selected sites, raw results, stats, errors
│   ├── Aggregator.php          # groups results into Site objects (by host or registrable domain)
│   ├── Search/                 # API clients (RestApiFetcher = v2, XmlApiFetcher = v1), XML parser,
│   │                           # CachingFetcher decorator, ApiException, AbstractApiFetcher (retries)
│   ├── Filter/                 # ResultFilter rules, DomainMatcher, TextMatcher, Domains helpers,
│   │                           # DefaultExclusions (aggregators/marketplaces/social networks)
│   ├── Check/                  # SiteChecker (curl_multi), CheckResult, Html helpers
│   ├── Output/ReportWriter.php # CSV / JSON / domains.txt writers
│   ├── Model/                  # SearchResult, SearchPage, Site
│   ├── Http/                   # HttpClient (curl wrapper), HttpResponse, HttpException
│   └── Support/                # Logger (STDERR), QueryList (query file reader)
├── tests/                      # custom runner (run.php), Assert, fixtures/, fake-api-server.php
├── config.example.php          # documented example configuration (copy to config.php)
├── queries.example.txt         # example query list
├── .env.example                # YANDEX_FOLDER_ID / YANDEX_API_KEY
├── composer.json               # PSR-4 autoload only, no dependencies
└── CLAUDE.md
```

Ignored by git: `config.php`, `.env`, `cache/`, `out/`, `queries.txt`, `vendor/`.

---

## Development Setup

### Prerequisites

- PHP >= 8.1 with `curl`, `dom`, `json`, `libxml`, `mbstring` (`intl` optional, for IDN domains)
- Composer is optional (no third-party packages; `bin/yandex-sites.php` falls back to its own autoloader)

### Initial Setup

```bash
cp config.example.php config.php
cp .env.example .env      # fill in YANDEX_FOLDER_ID and YANDEX_API_KEY
```

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `YANDEX_FOLDER_ID` | Yandex Cloud folder ID |
| `YANDEX_API_KEY` | API key of a service account with role `search-api.webSearch.user` |
| `YANDEX_IAM_TOKEN` | alternative to the API key (12-hour IAM token) |
| `YANDEX_REST_ENDPOINT`, `YANDEX_XML_ENDPOINT` | override API endpoints (used for the fake server / proxies) |

---

## Common Commands

| Task | Command |
|------|---------|
| Run the tool | `php bin/yandex-sites.php queries.txt` |
| Show CLI help | `php bin/yandex-sites.php --help` |
| Run all tests | `php tests/run.php` |
| Run tests matching a name | `php tests/run.php Parser` |
| Syntax check | `php tests/lint.php` |
| Demo without API key | `php -S 127.0.0.1:8089 tests/fake-api-server.php` then run with `YANDEX_REST_ENDPOINT=http://127.0.0.1:8089/v2/web/search` |

---

## Testing

Tests use a small custom runner (`tests/run.php`) and `Tests\Assert`; no PHPUnit. Each
`tests/*Test.php` defines a class `Tests\<FileName>` whose `test*` methods are executed.
`Assert::skip()` marks a test as skipped, `tearDownClass()` runs after each class.

- Unit tests cover the XML parser, filters, domain helpers, config, cache, API clients
  (via `Tests\StubHttpClient`), runner and report writer.
- `IntegrationTest` starts `tests/fake-api-server.php` with PHP's built-in server on a free
  port (`Tests\FakeServer`) and runs the CLI end to end, the legacy XML API and the site checker
  (`Tests\LocalSiteChecker` routes hosts to the fake server with `CURLOPT_RESOLVE`).
- Fixtures with real-format Yandex XML responses live in `tests/fixtures/`.

Run `php tests/lint.php && php tests/run.php` before committing.

---

## Code Style & Conventions

- `declare(strict_types=1)` in every file, PSR-12 formatting, PSR-4 namespaces `YandexSites\` (src) and `Tests\` (tests).
- Final classes by default; `HttpClient` and `SiteChecker` are non-final on purpose (extended in tests).
- Constructor property promotion and readonly properties for value objects (`Model/`).
- Comments and user-facing strings in Russian; identifiers in English.
- Configuration is a plain PHP array with dot-path access (`$config->get('search.pages')`);
  lists in config replace defaults entirely, associative sections are merged.
- Errors: `ApiException` carries `retryable`/`fatal` flags; `UsageException` maps to exit code 2;
  everything else is a `RuntimeException`/`InvalidArgumentException` with a Russian message.
- Logging goes to STDERR through `Support\Logger`; the final summary goes to STDOUT.

### Naming Conventions

| Entity | Convention | Example |
|--------|-----------|---------|
| Files/classes | `PascalCase` | `ResultFilter.php` |
| Methods/variables | `camelCase` | `queryCount()` |
| Config keys | `snake_case` | `groups_on_page` |
| CLI options | `kebab-case` | `--check-sites` |

---

## Yandex Search API Notes

- REST (v2): `POST https://searchapi.api.cloud.yandex.net/v2/web/search`, header
  `Authorization: Api-Key <key>` (or `Bearer <IAM>`), JSON body with `query.searchType`,
  `query.queryText`, `groupSpec`, `folderId`, `responseFormat: FORMAT_XML`; response `{"rawData": "<base64 XML>"}`.
  Field names and enums follow `yandex/cloud/searchapi/v2/*.proto` from `yandex-cloud/cloudapi`.
- Legacy XML (v1): `GET https://yandex.ru/search/xml?folderid=…&apikey=…&query=…&lr=…&groupby=attr=d.mode=deep.groups-on-page=N.docs-in-group=M&page=…`.
- XML response: `yandexsearch/response/results/grouping/group/doc/{url,domain,title,headline,passages/passage}`;
  `<hlword>` tags inside text are flattened; `response/error@code` — 15 = no results (not an error),
  55 = rate limit (retry), 32/33/42/43/44/48 = fatal.
- Limits: 10 rps, 10 000 sync requests/hour, ≤ 250 results per query, query ≤ 400 chars,
  `groups_on_page` 1–100, `docs_in_group` 1–3, `max_passages` 1–5.

---

## Git Workflow

- Branches: `claude/<description>-<session-id>` for AI-created branches, `feature/`, `fix/`, `chore/` otherwise.
- Conventional Commits: `feat(filter): …`, `fix(api): …`, `docs: …`, `test: …`.
- Push with `git push -u origin <branch-name>`; never commit `config.php`, `.env`, `cache/` or `out/`.

---

## AI Assistant Notes

- Keep the tool dependency-free; do not add composer packages without discussion.
- Do not scrape yandex.ru HTML or add captcha bypassing — the official API is the supported source.
- New search sources implement `Search\XmlFetcherInterface` and return Yandex-format XML.
- Every new filter rule needs a reason code in `ResultFilter::reject()`, a config default in
  `Config::defaults()`, an example in `config.example.php` and a test in `tests/ResultFilterTest.php`.
- Run `php tests/lint.php && php tests/run.php` after changes.
