# seo-llm-dashboard

A **Claude Code skill** that sets up one live page showing how a site is found in two places at
once: Google search, and the answers of ChatGPT, Gemini, Claude and Perplexity.

The two have split apart. A site can hold position 3 in Google while no chat assistant ever names
the brand. One install covers both: the skill measures AI visibility itself through DataForSEO
(prompts, live answers of four models, scoring), reads Search Console and rank tracking from a
self-hosted OpenSEO instance when you connect one, and builds a single-file dashboard. Google is
optional: without it the page is AI-only. Each section hides itself when its source is missing, so
it never shows invented numbers.

## What you get

→ a KPI row: clicks, impressions, keywords in the top 10, AI Visibility Score
→ Search Console by week, top queries and pages, branded-query share
→ positions per keyword against your competitors, with AI Overview presence
→ Google AI-mode impressions, from the Search Console export (Google offers no API for it)
→ AI Visibility Score per language and per model, against the same competitors, with cited
sources and "what to do" rows, measured by the skill itself (`scripts/avr.py`)
→ every prompt of the measurement with each model's own answer: who it named first, which
competitors it recommended, which sites it cited
→ an AI-only mode: just the AI block, no Google setup, only a DataForSEO account (about 4 USD for
108 answers; the skill shows the sum and waits for your yes before spending)
→ a demo page with fictional data in `templates/demo/dashboard.html`, to see the result first
→ a five-step setup guide in Ukrainian (`skills/seo-llm-dashboard/SETUP.uk.md`): DataForSEO, Search
Console, rank tracking, first run, monthly refresh; step guides for every integration and a table of
traps that fail silently

## Install

```bash
npx skills add victor-shulga/seo-llm-dashboard
```

Then in Claude: "set up the SEO LLM dashboard for example.com", "connect OpenSEO",
"налаштуй SEO і LLM дашборд".

### Where things live

- **Working folder.** Pick one folder per site (for example `dashboards/example.com/`). It holds
  `dashboard.html`, `dashboard.config.json`, `favicon.svg`, `seo_geo.json`. Every path inside the
  config is relative to the config file.
- **Secrets stay outside the skill and outside the working folder.** You paste them yourself with
  commands the skill gives you. Claude never asks for a key in the chat.
  - DataForSEO: API login + password from app.dataforseo.com/api-access as env `DATAFORSEO_LOGIN` +
    `DATAFORSEO_PASSWORD`, or the Base64 key in `~/.config/dataforseo/key` (chmod 600). Check for free:
    `python3 <skill-dir>/scripts/avr.py check`.
  - OpenSEO MCP: registered in Claude Code user scope (`claude mcp add ... --scope user`) with the
    Cloudflare Access service-token headers. `scripts/inject_dashboard.py` reads the URL and headers
    from that registration in `~/.claude.json`.
  - Search Console service account: JSON key at `~/.config/gsc-mcp/service-account.json`, or any path
    in env `GSC_CREDENTIALS`. Default property in env `GSC_DEFAULT_SITE`.

### Recommended

1. **A client PDF of the same measurement:** `npx skills add victor-shulga/ai-visibility-report`, then its
   `avr.py finalize` on the same run folder. Not needed for the dashboard.
2. **Direct Search Console MCP** (`scripts/gsc_mcp_server.py`): URL inspection, index coverage and every
   Search Analytics filter that OpenSEO does not expose.

## Requirements & integrations

| Integration | Used for | Required? | Auth / setup |
|---|---|---|---|
| Claude Code | running the skill, MCP clients, scheduled refresh | yes | claude.com/claude-code |
| python3 + curl | `avr.py`, `inject_dashboard.py`, `import_gsc_ai.py`, `serve_preview.py` (standard library only) | yes | preinstalled on macOS / most Linux |
| DataForSEO | live LLM answers, AI keyword volume, rank checks (pay as you go; $1 trial, $50 minimum top-up per dataforseo.com) | yes | API login + password, env or `~/.config/dataforseo/key`; OpenSEO worker secret `DATAFORSEO_API_KEY` for the Google part |
| OpenSEO (self-hosted, MIT) | Search Console data and rank tracking over MCP | Google part only | deploy to your Cloudflare account; MCP in user scope with Access service-token headers; apply `patches/openseo-service-token-mcp.patch` |
| Cloudflare (Workers, D1, KV, R2, Zero Trust) | hosting OpenSEO, Access in front of it | Google part only | `wrangler login`; Access app with an email policy and a service-token policy |
| Google Cloud OAuth client | OpenSEO ↔ Search Console | Google part only | Search Console API enabled; web client; app published to production; secrets as worker secrets |
| Google Search Console | the site's search data | Google part only | verified property; the connecting Google account added as a user |
| Google Cloud service account | direct `gsc` MCP | recommended | JSON key in `~/.config/gsc-mcp/` or env `GSC_CREDENTIALS`; added as a user in Search Console |
| `uv` | runs `gsc_mcp_server.py` (PEP 723 script) | recommended | docs.astral.sh/uv |
| ai-visibility-report skill | a client PDF of the same run | optional | `npx skills add victor-shulga/ai-visibility-report` |
| Cloudflare Pages or Netlify | hosting the page | optional (the HTML opens from disk) | `wrangler pages deploy` or `netlify deploy --site <site UUID>` |
| Claude scheduled tasks | weekly refresh, monthly AI re-measure | optional | prompts in `templates/scheduled-tasks.md`; the Claude app must be open |

Part of the GTM-system methodology by [Victor Shulga](https://victorshulga.com) (Fractional CRO).
Every skill in the stack: [CATALOG.md](https://github.com/victor-shulga/max/blob/main/CATALOG.md).

## License

MIT © Victor Shulga
