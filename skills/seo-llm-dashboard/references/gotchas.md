# Traps already paid for (read before Step 2)

Every row cost real time on the first build (August-September 2026). Most fail silently.

## OpenSEO / Cloudflare

| Symptom | Cause | Fix |
|---|---|---|
| `wrangler.jsonc` change has no effect | deploy reads `dist/server/wrangler.json`, generated at build | `corepack pnpm run build` then `wrangler deploy`; verify with `wrangler versions view` |
| custom domain not attached | `wrangler deploy` skips `custom_domain` routes | `npx wrangler triggers deploy` |
| every request `AUTH_CONFIG_MISSING` | no `TEAM_DOMAIN`/`POLICY_AUD` vars | add to `vars`, build, deploy |
| JWT rejected although Access lets you in | TEAM_DOMAIN taken from the "Team name" field | use the redirect host from `curl -sI` |
| MCP 500 after Access approved the token | upstream `/mcp` wants a human `sub`/`email` | apply `patches/openseo-service-token-mcp.patch`; sign in via browser once first |
| MCP 401 with the right token | clipboard held `CF-Access-Client-Secret: <value>` | secret alone = 64 chars |
| service-token policy "saved" but not applied | toast ≠ attach | press Save at the bottom of the Access app page; list shows "+ 1 other policy" |
| script gets 403 from the worker | Cloudflare bot filter | send `User-Agent: curl/8.4.0` |
| MCP result unparseable | JSON is in `result.structuredContent`; answer may be SSE | read structuredContent; join `data: ` lines |
| MCP server missing in a subfolder session | project scope is bound to the exact folder | always `--scope user` |
| MCP added but no tools | servers load at session start | restart the Claude session |
| runtime crash on any DataForSEO call | R2 bucket missing (it is the response cache) | create R2 bucket, Standard class |
| `--update-config` broke migrations | it drops `migrations_dir` | never use it; edit `wrangler.jsonc` by hand |

## Google / Search Console

| Symptom | Cause | Fix |
|---|---|---|
| "Google OAuth client not configured" with keys set | `BETTER_AUTH_SECRET` missing | `openssl rand -base64 32 \| npx wrangler secret put BETTER_AUTH_SECRET`; never rotate |
| "Google rejected the authorization code" | usually `401 invalid_client`, secret copied wrong | new client secret in Google Cloud |
| UI "Connected", calls return `api_error` after a week | app in Testing: refresh token lives 7 days | Branding (home, privacy, terms, no logo) -> Publish to production -> Disconnect/Connect |
| "unverified app" screen, big button cancels | Google's warning UI | click the small "continue/advanced" link |
| service account sees nothing / 403 | access is granted in Search Console, not IAM | add `client_email` as a user of the property |
| data starts late | GSC keeps data only since the property was verified | say so on the page; no backfill |
| AI-mode report not found in API/BigQuery | Google exposes it only in the UI | manual export + `import_gsc_ai.py` |
| numbers don't add up | low-volume queries hidden; last 2-3 days incomplete | totals from unsegmented calls; windows end 3 days back |

## AI visibility run

| Symptom | Cause | Fix |
|---|---|---|
| score is about the wrong buyers | skill default market US/English | decide market + languages in Step 0 |
| all Claude cells fail for UA | Claude rejects `web_search_country_iso_code=UA` | per-model `country_iso` dict, country in the prompt text |
| competitor over-counted | generic word as a name | case-sensitive group `(?-i:\bName\b)`; check matches in context |
| a model "mentions" a vendor it never told the user | reasoning glued to the answer | skill keeps only `message` sections (fixed) |
| PDF build crash at score 0 / blank page | reportlab arc 0°; spacer before page break | fixed in the skill's `build_report.py` |
| month over month jumps | one answer of 32 ≈ 2 points | changes < 1 point are noise |
| next month overwrote last month's answers | shared `raw/` names | `avr.py remeasure` moves them to `raw_<slug>/` |

## Page / hosting / Mac

| Symptom | Cause | Fix |
|---|---|---|
| hidden block still visible | `display:grid` beats the `hidden` attribute | template has `[hidden]{display:none!important}` |
| page dies on load | `const top` collides with `window.top` | never name a global `top` |
| python server can't start in Desktop/Documents | macOS TCC blocks getcwd for launcher-started python | serve a /tmp copy (`serve_preview.py`) |
| old favicon/asset after deploy | Cloudflare caches assets immutably | bump `?v=N` |
| Netlify deploy overwrote another site | `--site <name>` resolved to a parent-linked site | always `--site <UUID>` |
| scheduled job silent on the 1st | Claude app closed / Mac asleep | cron after 10:00; job runs on next launch; "Run now" once to store approvals |
| Cyrillic renders in serif in headless screenshots | fonts not loaded in time | `--virtual-time-budget=6000 --run-all-compositor-stages-before-draw` |
