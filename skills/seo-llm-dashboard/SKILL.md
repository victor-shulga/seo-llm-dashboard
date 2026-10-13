---
name: seo-llm-dashboard
description: >-
  Sets up a live "Search + LLM visibility" dashboard for any site, end to end: DataForSEO account,
  self-hosted OpenSEO on Cloudflare (Search Console OAuth, rank tracking, MCP via an Access service
  token), a direct Search Console MCP on a Google Cloud service account, an ai-visibility-report run
  (AI Visibility Score per language vs competitors), optional Google AI-mode export, the single-file
  dashboard page, deploy to Cloudflare Pages or Netlify, and the weekly + monthly scheduled refresh.
  Use when the user says "set up the SEO LLM dashboard", "search and AI visibility dashboard",
  "connect OpenSEO", "connect Search Console", "connect DataForSEO", "налаштуй SEO і LLM дашборд",
  "дашборд видимості в пошуку і нейромережах", or wants to track a brand in Google and in
  ChatGPT/Gemini/Claude/Perplexity on one page. The AI block needs the optional ai-visibility-report
  skill. NOT a one-off PDF report (that is ai-visibility-report) and NOT a site audit.
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
| AI Visibility Score: total + per language, vs competitors, per model, cited sources, what to do | ai-visibility-report run (DataForSEO live LLM answers) | monthly |

```
DataForSEO ──► OpenSEO worker (Cloudflare, Access) ──MCP──► Claude / inject_dashboard.py ──► dashboard.html ──► Pages/Netlify
   │                 └─ Google OAuth ─► Search Console                    ▲
   └──────────► ai-visibility-report run (cells JSON, PDF) ────────────────┘
Google Cloud service account ─► gsc MCP (direct GSC: URL inspection, index coverage, any filter)
```

Talk to the user in their language. Code, configs and this file stay English.
The page UI ships in Ukrainian; translate the static labels once per non-Ukrainian site (see Step 7).

## Hard rules

- **Secrets never pass through the chat.** Keys, client secrets, service tokens: give the user a command
  that reads from the clipboard or prompts (`pbpaste > file`, `wrangler secret put`), never ask them to paste
  a key to you, never print one, never write one into a repo or a project `.mcp.json`. MCP servers with a
  header secret go to `--scope user`.
- **Money only with a yes.** DataForSEO spend (ai-visibility collect, extra rank trackers) is shown with
  the estimate first. Monthly jobs get an explicit budget in their prompt.
- **Client work uses the client's brand colours** in `colors`, never the agency's.
- **Confidential.** The page lists competitors and weak spots: put Access/password in front of it for
  clients. The AI-visibility PDF is never published anywhere.
- **Never invent numbers.** A source that fails shows "no data + why", or its section stays hidden.
- Prefer reusing what exists: one OpenSEO instance and one DataForSEO account can serve every site of the
  same owner (new OpenSEO project per site).

To show what the page looks like, send `templates/demo/dashboard.html` (fictional data). Never link the
owner's own live report as an example: it sits next to their other reports.

## Step 0: intake in ONE message

Ask only what is missing:
1. Domain, brand name and its spellings (Latin + Cyrillic, with/without space); any retired brand name.
2. Market: country, and every language buyers ask in. Who the buyer is, in a few words.
3. 4 topics buyers ask about; 8-15 search keywords to track in Google.
4. 3-5 competitors with domains (for the rank table and for the AI block; propose from the live SERP and
   from who the models name if the user has none).
5. Where it lives: Cloudflare Pages on the owner's domain, or Netlify; brand colours.
6. What already exists: DataForSEO account? OpenSEO instance? GSC property verified, and whose Google
   account has access? Cloudflare account and a domain in it?

## Step 1: DataForSEO (`references/01-dataforseo.md`)

Account, top-up, Base64 key into the OpenSEO worker secret and `~/.config/dataforseo/key`. Smoke test ($0).

## Step 2: OpenSEO (`references/02-openseo.md`)

New owner: deploy (A), custom domain + Access (B), service token + patch + user-scope MCP (C), Google OAuth
published to production (D). Existing instance: only a new project + GSC connect + trackers (D6-7, E).
Done when `mcp__open-seo__get_search_console_performance` returns rows for the property (new MCP servers
appear only in a new session: tell the user to restart Claude after `claude mcp add`).

## Step 3: direct Search Console MCP (`references/03-gsc-service-account.md`)

Optional for the page, recommended for diagnosis (index coverage, URL inspection). Done when
`--check` lists the property.

## Step 4: rank tracking (`references/02-openseo.md` section E)

Own tracker + one tracker per competitor with the same keywords. First check comes on schedule.

## Step 5 (optional): AI visibility baseline (`references/04-ai-visibility.md`, with the ai-visibility-report skill)

If the ai-visibility-report skill is installed (`npx skills add victor-shulga/ai-visibility-report`), run it
for the baseline. Without it, skip this step: the AI Visibility Score block stays hidden and the rest of the
page works.


Decide market and languages first (the US default was wrong once). `lang` on every prompt, per-model
country dict, confirm cost, collect, prominence, prose, PDF. Then write `seo_geo.json` (3-4 actions, each
with a number from the run).

## Step 6 (optional): AI-mode export (`references/05-gsc-ai-mode.md`)

Ask once whether the owner will export monthly; do not push it again after a no.

## Step 7: build and deploy (`references/06-build-and-deploy.md`)

Copy `templates/dashboard.html`, `favicon.svg`, fill `dashboard.config.json`, run
`scripts/inject_dashboard.py <config>`, preview via `templates/serve_preview.py`, check console + screenshot,
deploy, verify live with curl, protect access for clients.

## Step 8: schedule (`templates/scheduled-tasks.md`)

Weekly refresh (no spend) and monthly AI re-measure (budgeted, only with ai-visibility-report). Create both
with the Claude scheduled-tasks tool, then "Run now" each once so tool approvals are stored. They run only
while the Claude app is open. Any other scheduler (cron, CI) can run the same weekly command instead.

## Definition of done

- [ ] `inject_dashboard.py` prints a line for every configured source, no errors
- [ ] page opens with no console errors; KPI row, weekly chart, queries/pages, ranks (and the AI block, if used) visible
- [ ] brand colours applied; favicon recoloured; no leftover names of another brand anywhere on the page
- [ ] live URL returns the new build (curl check), access protected if it is a client
- [ ] if the AI block is used: `seo_geo.json` actions match the latest run (`forRun` = run date)
- [ ] weekly task exists (monthly too if the AI block is used), each run once manually
- [ ] the user got: URL, what each section means in one line each, costs per month, what to do if GSC
      stops (reconnect in OpenSEO)

## Requirements & integrations

| Integration | Used for | Required? | Auth/setup |
|---|---|---|---|
| DataForSEO | rank checks, LLM answers, AI keyword volume | yes | Base64 API key: worker secret `DATAFORSEO_API_KEY` + `~/.config/dataforseo/key` |
| Cloudflare (Workers, D1, KV, R2, Zero Trust) | hosting OpenSEO, Access in front of it | yes | `wrangler login`; Access app + email policy + service-token policy |
| OpenSEO (self-hosted) | GSC data + rank tracking via MCP | yes | user-scope MCP `open-seo` with CF-Access-Client-Id/Secret headers; service-token patch applied |
| Google Cloud OAuth client | OpenSEO ↔ Search Console | yes | Search Console API on; Web client; app published to production; secrets in worker |
| Google Search Console | the site's search data | yes | property verified; connecting Google account (or service account) added as user |
| Google Cloud service account | direct `gsc` MCP | recommended | JSON key in `~/.config/gsc-mcp/`, added as user in Search Console |
| ai-visibility-report skill | AI Visibility Score | optional (AI block only) | `npx skills add victor-shulga/ai-visibility-report`; same DataForSEO key |
| Cloudflare Pages or Netlify | hosting the page | yes (one of them) | `wrangler pages deploy` / `netlify deploy --site <UUID>` |
| `uv`, python3, Chrome | scripts, PDF, render checks | yes | local |
| Claude scheduled tasks | weekly + monthly refresh | recommended | scheduled-tasks tool, app must be open |

## Files

| File | Role |
|---|---|
| `scripts/inject_dashboard.py` | config-driven: pulls OpenSEO (MCP over HTTP), AI-mode JSON, ai-visibility run; rewrites the page in place |
| `scripts/gsc_mcp_server.py` | direct Search Console MCP (service account) and CLI |
| `scripts/import_gsc_ai.py` | Search Console AI-mode export (ZIP/CSV, localized headers) -> JSON |
| `templates/dashboard.html` | the page (single file, data inlined as `const SEO = …;`) |
| `templates/dashboard.config.example.json` | every config field |
| `templates/seo_geo.example.json` | "what to do" rows |
| `templates/scheduled-tasks.md` | weekly + monthly task prompts with placeholders |
| `templates/serve_preview.py`, `templates/favicon.svg` | local preview, tab icon |
| `templates/demo/` | the page with fictional data (Example Agency, example.com): show it before any setup; rebuild with `inject_dashboard.py templates/demo/dashboard.config.json` |
| `patches/openseo-service-token-mcp.patch` | lets an Access service token reach OpenSEO `/mcp` |
| `references/01…06`, `references/gotchas.md` | step guides and every trap hit so far |

The traps that cost the most time are collected in `references/gotchas.md`. Read it before Step 2.
