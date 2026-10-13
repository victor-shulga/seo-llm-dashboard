# seo-llm-dashboard

A **Claude Code skill** that sets up one live page showing how a site is found in two places at
once: Google search, and the answers of ChatGPT, Gemini, Claude and Perplexity.

The two have split apart. A site can hold position 3 in Google while no chat assistant ever names
the brand. This skill walks Claude through the whole build: the data accounts, a self-hosted
OpenSEO instance on Cloudflare that holds Search Console and rank tracking behind one MCP, an
optional direct Search Console MCP, an optional AI-visibility baseline, the single-file dashboard,
deploy, and a weekly refresh. Each section of the page hides itself when its source is missing,
so it never shows invented numbers.

## What you get

→ a KPI row: clicks, impressions, keywords in the top 10, AI Visibility Score
→ Search Console by week, top queries and pages, branded-query share
→ positions per keyword against your competitors, with AI Overview presence
→ Google AI-mode impressions, from the Search Console export (Google offers no API for it)
→ AI Visibility Score per language and per model, against the same competitors, with cited
sources and "what to do" rows (needs the optional ai-visibility-report skill)
→ a demo page with fictional data in `templates/demo/dashboard.html`, to see the result first
→ step guides for every integration, plus a table of traps that fail silently

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
  - DataForSEO key: env `DATAFORSEO_API_KEY`, or the file `~/.config/dataforseo/key` (chmod 600).
  - OpenSEO MCP: registered in Claude Code user scope (`claude mcp add ... --scope user`) with the
    Cloudflare Access service-token headers. `scripts/inject_dashboard.py` reads the URL and headers
    from that registration in `~/.claude.json`.
  - Search Console service account: JSON key at `~/.config/gsc-mcp/service-account.json`, or any path
    in env `GSC_CREDENTIALS`. Default property in env `GSC_DEFAULT_SITE`.

### Recommended

1. **AI Visibility Score block:** `npx skills add victor-shulga/ai-visibility-report`. Without it the
   page works and that block stays hidden.
2. **Direct Search Console MCP** (`scripts/gsc_mcp_server.py`): URL inspection, index coverage and every
   Search Analytics filter that OpenSEO does not expose.

## Requirements & integrations

| Integration | Used for | Required? | Auth / setup |
|---|---|---|---|
| Claude Code | running the skill, MCP clients, scheduled refresh | yes | claude.com/claude-code |
| python3 | `inject_dashboard.py`, `import_gsc_ai.py`, `serve_preview.py` (standard library only) | yes | preinstalled on macOS / most Linux |
| DataForSEO | rank checks, live LLM answers, AI keyword volume (pay as you go) | yes | Base64 API key: OpenSEO worker secret `DATAFORSEO_API_KEY` + env or `~/.config/dataforseo/key` |
| OpenSEO (self-hosted, MIT) | Search Console data and rank tracking over MCP | yes | deploy to your Cloudflare account; MCP in user scope with Access service-token headers; apply `patches/openseo-service-token-mcp.patch` |
| Cloudflare (Workers, D1, KV, R2, Zero Trust) | hosting OpenSEO, Access in front of it | yes | `wrangler login`; Access app with an email policy and a service-token policy |
| Google Cloud OAuth client | OpenSEO ↔ Search Console | yes | Search Console API enabled; web client; app published to production; secrets as worker secrets |
| Google Search Console | the site's search data | yes | verified property; the connecting Google account added as a user |
| Google Cloud service account | direct `gsc` MCP | recommended | JSON key in `~/.config/gsc-mcp/` or env `GSC_CREDENTIALS`; added as a user in Search Console |
| `uv` | runs `gsc_mcp_server.py` (PEP 723 script) | recommended | docs.astral.sh/uv |
| ai-visibility-report skill | AI Visibility Score block, monthly re-measure | optional | `npx skills add victor-shulga/ai-visibility-report`; same DataForSEO key |
| Cloudflare Pages or Netlify | hosting the page | yes (one of them) | `wrangler pages deploy` or `netlify deploy --site <site UUID>` |
| Claude scheduled tasks | weekly refresh, monthly AI re-measure | optional | prompts in `templates/scheduled-tasks.md`; the Claude app must be open |

Part of the GTM-system methodology by [Victor Shulga](https://victorshulga.com) (Fractional CRO).
Every skill in the stack: [CATALOG.md](https://github.com/victor-shulga/max/blob/main/CATALOG.md).

## License

MIT © Victor Shulga
