---
name: seo-llm-dashboard
description: >-
  One skill, one page: how a site is found in Google and named by ChatGPT, Gemini, Claude and
  Perplexity. Measures AI visibility itself through DataForSEO (prompts, live answers, scoring,
  recommendations tied to numbers; about 4 USD per 108 answers, shown first and spent only after a yes), then
  builds a single-file HTML dashboard: AI Visibility Score per language and model vs competitors,
  cited sources, every prompt with each model's answer, plus Search Console clicks and queries,
  rank tracking vs competitors and Google AI-mode when Google is connected (self-hosted OpenSEO on
  Cloudflare). Google is optional: without it the page is AI-only. Guides setup step by step.
  Use when the user says
  "set up the SEO LLM dashboard", "AI visibility dashboard", "search and AI visibility dashboard",
  "налаштуй SEO і LLM дашборд", "дашборд видимості в AI", "як нас бачать нейромережі",
  or wants a brand tracked in Google and AI assistants on one page. NOT a PDF report for a client
  (ai-visibility-report), NOT a site audit.
---

# SEO + LLM visibility dashboard

One page, two layers, because they have split apart:
- **link layer**: Google clicks, impressions, positions by keyword against competitors;
- **answer layer**: whether AI Overviews and the chat assistants name the brand and cite its site.

What the finished page shows (all sections hide themselves when their source is missing):

| Section | Source | Refresh |
|---|---|---|
| KPI row: clicks, impressions, top-10 keywords, AI Visibility Score | all below | weekly |
| Search by week, top queries, top pages, branded-query share | Search Console via OpenSEO | weekly |
| Positions by keyword vs competitors + AI Overview presence | OpenSEO rank tracking (DataForSEO) | weekly |
| Google AI-mode impressions | Search Console UI export (no API exists) | when exported |
| AI Visibility Score: total + per language, vs competitors, per model, cited sources, every prompt × answer, what to do | `scripts/avr.py` run (DataForSEO live LLM answers) | monthly |

```
DataForSEO ──► OpenSEO worker (Cloudflare, Access) ──MCP──► Claude / inject_dashboard.py ──► dashboard.html ──► Pages/Netlify
   │                 └─ Google OAuth ─► Search Console                    ▲
   └──────────► scripts/avr.py run (cells JSON, raw answers) ──────────────┘
Google Cloud service account ─► gsc MCP (direct GSC: URL inspection, index coverage, any filter)
```

Talk to the user in their language. Code, configs and this file stay English.
The page UI ships in Ukrainian and is not translated or edited by hand (see Hard rules).

## Hard rules

- **The design is fixed.** The page is ALWAYS built by `scripts/inject_dashboard.py` from
  `templates/dashboard.html`. Never write, edit, translate or "improve" its HTML/CSS/JS. Your part is only:
  (a) fill `dashboard.config.json` and the run config, (b) run collection after the user's yes, (c) write
  recommendation wording into the actions JSON via `recommend.py`, (d) run the build. Brand colours only
  through `colors` in the config, keys `accent`, `accent_deep`, `accent_soft`, `ink`, `positive`,
  `positive_soft`. The build ends with a self-check; if it fails, give the user its message and fix the
  cause, never hand-patch the page.
- **Secrets never pass through the chat.** Keys, client secrets, service tokens: give the user a command
  that reads from the clipboard or prompts (`pbpaste > file`, `wrangler secret put`), never ask them to paste
  a key to you, never print one, never write one into a repo or a project `.mcp.json`. MCP servers with a
  header secret go to `--scope user`.
- **Money only with a yes.** DataForSEO spend (`avr.py collect` and `volume`, extra rank trackers) is shown with
  the estimate first. Monthly jobs get an explicit budget in their prompt.
- **Client work uses the client's brand colours** in `colors`, never the agency's.
- **Confidential.** The page lists competitors and weak spots: put Access/password in front of it for
  clients. The AI-visibility PDF is never published anywhere.
- **Never invent numbers.** A source that fails shows "no data + why", or its section stays hidden.
- Prefer reusing what exists: one OpenSEO instance and one DataForSEO account can serve every site of the
  same owner (new OpenSEO project per site).

To show what the page looks like, send `templates/demo/dashboard.html` (fictional data). Never link the
owner's own live report as an example: it sits next to their other reports.

## The setup path (what the user sees: `SETUP.uk.md`)

`SETUP.uk.md` is the human guide, five steps in plain Ukrainian. Walk the user through the same steps in
their language, one at a time, and say which ones they can skip:

| Step | Gives | Required? | Reference |
|---|---|---|---|
| 1. DataForSEO | live AI answers (and rank checks for step 3) | yes | `references/01-dataforseo.md` |
| 2. Search Console via OpenSEO | clicks, impressions, queries, pages | no (AI-only start) | `references/02-openseo.md` A-D, `05-gsc-ai-mode.md` |
| 3. Rank tracking vs competitors | Google positions per keyword | no, needs step 2 | `references/02-openseo.md` E |
| 4. First measurement + page | the dashboard HTML | yes | `references/04-ai-visibility.md`, `06-build-and-deploy.md` |
| 5. Monthly refresh | the trend, the change vs last month | recommended | `templates/scheduled-tasks.md` |

**AI-only start (steps 1, 4, 5).** Copy `templates/dashboard.html`, `templates/favicon.svg` and
`templates/dashboard.config.ai-only.example.json` (as `dashboard.config.json`) into one folder; set
`domain`, `brand_name`, `geo.run_dir`. No `openseo` and no `ai_mode_file`: the search, rank and AI-mode
sections hide themselves. Adding Google later = add the `openseo` block and re-run inject.

## Step 0: intake in ONE message

Ask only what is missing:
1. Domain, brand name and its spellings (Latin + Cyrillic, with/without space); any retired brand name.
2. Market: country, and every language buyers ask in. Who the buyer is, in a few words.
3. 4 topics buyers ask about; for the Google part also 8-15 search keywords to track.
4. 3-5 competitors with domains (propose from who the models and the live SERP name if the user has none).
5. AI-only or with Google? Where the page lives (local file, Cloudflare Pages, Netlify); brand colours.
6. What already exists: DataForSEO account? OpenSEO instance? GSC property verified, whose Google account?

## Step 1: DataForSEO (`references/01-dataforseo.md`)

Account, $50 minimum top-up, API login + password from API Access, stored by the user's own command
outside any repo. Then `python3 <skill-dir>/scripts/avr.py check` (free) must print `DataForSEO OK`.
On first use, if `check` fails, this step is where you start; never ask for the key in the chat.

## Step 2 (optional): Search Console through OpenSEO (`references/02-openseo.md` A-D)

New owner: deploy (A), custom domain + Access (B), service token + patch + user-scope MCP (C), Google OAuth
published to production (D). Existing instance: only a new project + GSC connect. Done when
`mcp__open-seo__get_search_console_performance` returns rows for the property (new MCP servers appear only
in a new session: tell the user to restart Claude after `claude mcp add`).
Direct Search Console MCP (`references/03-gsc-service-account.md`) is optional, for diagnosis only.
Google AI-mode impressions (`references/05-gsc-ai-mode.md`): ask once whether the owner will export monthly.

## Step 3 (optional): rank tracking (`references/02-openseo.md` E)

Own tracker + one tracker per competitor with the same keywords. First check comes on schedule.

## Step 4: first AI measurement and the page (`references/04-ai-visibility.md`, `06-build-and-deploy.md`)

Decide market and languages first. Run config with `lang` on every prompt, `avr.py estimate` → show the
sum → wait for yes → `avr.py collect` → `review` → `prominence.json` → `finalize`. Copy the template,
fill `dashboard.config.json`, then recommendations (free): `diagnose.py` → `inject_dashboard.py --draft` →
`recommend.py <config> --write` → `inject_dashboard.py` again (`references/04-ai-visibility.md` §6).
Every «Що робити» row carries a number from the run; never write rows by hand from general advice. Preview via `templates/serve_preview.py`, check console +
screenshot, publish where the user wants, protect access for clients.

## Step 5: monthly refresh (`templates/scheduled-tasks.md`)

Weekly Google refresh (no spend, only with step 2) and monthly AI re-measure (budgeted). Create them with
the Claude scheduled-tasks tool, then "Run now" each once so tool approvals are stored. They run only
while the Claude app is open. Any other scheduler (cron, CI) can run the same commands instead.

## Definition of done

- [ ] `inject_dashboard.py` prints a line for every configured source and ends with «перевірка сторінки: ок»
- [ ] page opens with no console errors; the AI block (score, languages, models, rivals, sources, prompts × answers) visible, plus KPI row, weekly chart, queries/pages and ranks when Google is connected
- [ ] brand colours applied; favicon recoloured; no leftover names of another brand anywhere on the page
- [ ] live URL returns the new build (curl check), access protected if it is a client
- [ ] «Що робити» rows come from `recommend.py` for the latest run (`forRun` = run date), «Чому не назвали» filled by `diagnose.py`
- [ ] monthly task exists (weekly too with Google), each run once manually
- [ ] the user got: URL, what each section means in one line each, costs per month, what to do if GSC
      stops (reconnect in OpenSEO)

## Requirements & integrations

| Integration | Used for | Required? | Auth/setup |
|---|---|---|---|
| DataForSEO | live LLM answers, AI keyword volume, rank checks | yes | API login + password (or the Base64 key): `~/.config/dataforseo/key` or env vars; OpenSEO worker secret `DATAFORSEO_API_KEY` with step 2 |
| Cloudflare (Workers, D1, KV, R2, Zero Trust) | hosting OpenSEO, Access in front of it | Google part only | `wrangler login`; Access app + email policy + service-token policy |
| OpenSEO (self-hosted) | GSC data + rank tracking via MCP | Google part only | user-scope MCP `open-seo` with CF-Access-Client-Id/Secret headers; service-token patch applied |
| Google Cloud OAuth client | OpenSEO ↔ Search Console | Google part only | Search Console API on; Web client; app published to production; secrets in worker |
| Google Search Console | the site's search data | Google part only | property verified; connecting Google account (or service account) added as user |
| Google Cloud service account | direct `gsc` MCP | recommended | JSON key in `~/.config/gsc-mcp/`, added as user in Search Console |
| ai-visibility-report skill | a client PDF from the same run folder | optional | `npx skills add victor-shulga/ai-visibility-report` |
| Cloudflare Pages or Netlify | hosting the page | optional (the HTML also opens from disk) | `wrangler pages deploy` / `netlify deploy --site <UUID>` |
| python3 + curl, Chrome | scripts (standard library), render checks | yes | local; `uv` only for `gsc_mcp_server.py` |
| Claude scheduled tasks | weekly + monthly refresh | recommended | scheduled-tasks tool, app must be open |

## Files

| File | Role |
|---|---|
| `scripts/avr.py` | AI measurement CLI: check, estimate, collect, volume, review, finalize, remeasure |
| `scripts/dfs.py`, `scripts/aggregate.py` | DataForSEO transport and answer parsing; the numbers of a run |
| `scripts/diagnose.py` | why each prompt was lost, which sources to go after (free) |
| `scripts/recommend.py` | «Що робити» rows from the diagnosis and the search data, each tied to a number |
| `scripts/check_dashboard.py` | the self-check every build runs (also a CLI with `--selftest`) |
| `scripts/inject_dashboard.py` | config-driven: pulls OpenSEO (MCP over HTTP), AI-mode JSON, the run folder; rewrites the page in place |
| `scripts/gsc_mcp_server.py` | direct Search Console MCP (service account) and CLI |
| `scripts/import_gsc_ai.py` | Search Console AI-mode export (ZIP/CSV, localized headers) -> JSON |
| `templates/dashboard.html` | the page (single file, data inlined as `const SEO = …;`) |
| `templates/dashboard.config.example.json` | every config field |
| `templates/dashboard.config.ai-only.example.json` | the AI-only page: no OpenSEO, no Search Console |
| `templates/ai_run.config.example.json` | the AI measurement run config |
| `SETUP.uk.md` | the five setup steps for the user, plain Ukrainian |
| `templates/seo_geo.example.json` | the «Що робити» file format (`recommend.py --write` fills it) |
| `templates/scheduled-tasks.md` | weekly + monthly task prompts with placeholders |
| `templates/serve_preview.py`, `templates/favicon.svg` | local preview, tab icon |
| `templates/demo/` | the page with fictional data (Example Agency, example.com): show it before any setup; rebuild with `inject_dashboard.py templates/demo/dashboard.config.json` |
| `patches/openseo-service-token-mcp.patch` | lets an Access service token reach OpenSEO `/mcp` |
| `references/01…06`, `references/gotchas.md` | step guides and every trap hit so far |

The traps that cost the most time are collected in `references/gotchas.md`. Read it before Step 2.
