# Indexing Automation — n8n + XMLStock + Google Sheets

Daily, automatic check of the number of indexed pages per brand × site in Yandex
via [XMLStock](https://xmlstock.com/), with results written to a Google Sheet.

* **Trigger:** daily cron (default: 06:00 server time)
* **Queries:** 5 domains × 6 brands = 30 `site:<brand>.<domain>` queries
* **Data source:** XMLStock Yandex XML API (`found` value from the response)
* **Sink:** single-cell updates in Google Sheets (per brand × site)

---

## Files

```
workflows/
  indexing-automation.json   # importable n8n workflow
.env.example                 # required environment variables
```

---

## Google Sheet layout

The workflow targets the sheet layout shown in the task brief:

| Row | Content                                                            |
|-----|--------------------------------------------------------------------|
| 1   | Merged title (e.g. "Мониторинг")                                   |
| 2   | Merged site headers: `Сайт 1`, `Сайт 2`, `Сайт 3`, `Сайт 4`, `Сайт 5` |
| 3   | Repeating sub-headers per site: `Бренд`, `Индексация`, `Топ3`, `Топ5`, `Топ10`, `Топ20`, `Топ50` |
| 4–9 | One row per brand (Aurora, Cryptoboss, Eva, Enomo, Avocado, Bonsai) |

Each site block occupies 6 columns. The workflow writes only the first column of
each block (`Индексация`):

| Site   | Column |
|--------|--------|
| Сайт 1 | B      |
| Сайт 2 | H      |
| Сайт 3 | N      |
| Сайт 4 | T      |
| Сайт 5 | Z      |

Rows are ordered the same way as the `brands` array in the `Build 30 Queries`
node: Aurora → row 4, Cryptoboss → row 5, …, Bonsai → row 9.

If your sheet layout differs, adjust `FIRST_BRAND_ROW` and `INDEXING_COLUMNS` in
the `Build 30 Queries` Code node.

---

## Setup

### 1. Prerequisites

* An n8n instance (self-hosted or n8n Cloud)
* An [XMLStock](https://xmlstock.com/) account with API user + key
* A Google account with access to the target spreadsheet
* Either a Google OAuth2 credential or a Google Service Account with the
  `https://www.googleapis.com/auth/spreadsheets` scope

### 2. Create credentials in n8n

**Google Sheets OAuth2:**

1. In n8n, go to *Credentials → New → Google Sheets OAuth2 API*.
2. Follow the wizard to authorize access to the target spreadsheet.
3. Note the credential name (the workflow expects it to be bound to the
   `Write Cell to Google Sheets` node after import — see step 5).

If you prefer a service account instead, create a Google Service Account
credential in n8n, share the sheet with the service account's email address
(`...@....iam.gserviceaccount.com`), and switch the HTTP node's
`nodeCredentialType` from `googleSheetsOAuth2Api` to `googleApi`.

### 3. Set environment variables

Copy `.env.example` into your n8n environment (self-hosted: in your `.env`
file or docker-compose `environment:` block; n8n Cloud: *Settings →
Variables*):

```bash
XMLSTOCK_USER=12345
XMLSTOCK_KEY=your-xmlstock-api-key
GOOGLE_SHEET_ID=1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789
GOOGLE_SHEET_TAB=Мониторинг
```

Restart n8n so it picks up the new variables.

### 4. Import the workflow

*Workflows → Import from File →* select `workflows/indexing-automation.json`.

### 5. Bind the Google Sheets credential

Open the imported workflow, click the **Write Cell to Google Sheets** node and
pick the credential you created in step 2 from the *Credential* dropdown.
(The import carries a placeholder ID that has to be replaced.)

### 6. Configure domains and brands

Open the **Build 30 Queries** Code node. Update the `domains` and `brands`
arrays:

```js
const domains = [
  'site1.example.com',
  'site2.example.com',
  'site3.example.com',
  'site4.example.com',
  'site5.example.com'
];

const brands = [
  'aurora',
  'cryptoboss',
  'eva',
  'enomo',
  'avocado',
  'bonsai'
];
```

The generated query for every `(brand, domain)` pair is
`site:<brand>.<domain>`. If your real subdomain scheme differs (e.g. you use
different slugs per site), change the `query` expression inside the same node.

### 7. Test and enable

1. Click **Execute Workflow** once to run manually.
2. Check the target spreadsheet — the 30 `Индексация` cells should update.
3. When it works, flip the workflow **Active** toggle.

---

## Flow

```
Daily Schedule (cron)
        │
        ▼
Build 30 Queries (Code)        # 6 brands × 5 domains = 30 items
        │
        ▼
Loop Over Queries ──────────────┐    # SplitInBatches, size = 1
        │ (loop branch)         │
        ▼                       │
XMLStock API (HTTP)             │
        │                       │
        ▼                       │
Parse XML                       │
        │                       │
        ▼                       │
Extract Found Count (Code)      │
        │                       │
        ▼                       │
Throttle 2.5s (Wait)            │
        │                       │
        ▼                       │
Write Cell (Google Sheets API)──┘
```

The `Write Cell` node loops back into `Loop Over Queries`, which pulls the
next batch. When all 30 items are done the loop exits via its "done" output
(currently unconnected).

---

## XMLStock request

The `XMLStock API` node issues a GET to `https://xmlstock.com/yandex/xml/`
with these parameters:

| Param     | Value                                                     |
|-----------|-----------------------------------------------------------|
| `user`    | `{{ $env.XMLSTOCK_USER }}`                                |
| `key`     | `{{ $env.XMLSTOCK_KEY }}`                                 |
| `query`   | `site:<brand>.<domain>`                                   |
| `groupby` | `attr=d.mode=deep.groups-on-page=10.docs-in-group=1`      |
| `numdoc`  | `10`                                                      |

We only care about the `<found>` element in the response. `Extract Found
Count` prefers `priority="phrase"` (the number Yandex shows for `site:`
queries), then falls back to `"all"` and `"strict"`. If XMLStock returns an
error or the response cannot be parsed, the workflow writes `"ERR"` into the
cell and keeps the `error` field in the execution log so you can investigate.

---

## Google Sheets write

A single cell is updated per iteration via the Sheets API:

```
PUT https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{A1_RANGE}
    ?valueInputOption=USER_ENTERED
Body: { "range": "...", "majorDimension": "ROWS", "values": [[<count>]] }
```

`A1_RANGE` looks like `Мониторинг!B4` — sheet tab + cell, computed in the
`Build 30 Queries` node.

---

## Troubleshooting

* **Cell stays empty / `ERR`** — open the execution, expand `Extract Found
  Count`, and check the `error` field for the XMLStock error message (common
  causes: wrong user/key, daily limit exceeded, malformed query).
* **`403` from Google** — the OAuth2 credential does not have access to the
  sheet. Re-authorize, or share the sheet with the service account email.
* **Wrong cells update** — the `FIRST_BRAND_ROW` / `INDEXING_COLUMNS`
  constants do not match your sheet. Adjust them in `Build 30 Queries`.
* **Ban from XMLStock / timeouts** — increase the Throttle from 2.5s to 5s.
* **Extra sub-metrics (Топ3, Топ5, …)** — out of scope for this workflow.
  Extend `INDEXING_COLUMNS` with additional column letters and run separate
  queries (e.g. each brand's keyword list) to fill those columns.

---

## Extending

* **More brands or sites:** just add entries to the `brands` / `domains`
  arrays. The loop and cell math adapt automatically, as long as you also
  extend `INDEXING_COLUMNS` when you add sites.
* **Multiple spreadsheets:** duplicate the workflow, point `GOOGLE_SHEET_ID`
  at a different sheet per project.
* **Different search engine:** change the HTTP URL and query params — the
  parsing step is structured around XMLStock's `<found>` element and would
  need a small adjustment for a different response shape.
