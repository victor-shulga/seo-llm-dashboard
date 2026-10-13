# OpenSEO self-hosted on Cloudflare — Search Console + rank tracking behind one MCP

OpenSEO (github.com/every-app/open-seo, MIT) is an open-source Ahrefs/Semrush replacement on top of
DataForSEO. Here it does two jobs for the dashboard: it holds the Search Console connection and it runs
weekly rank checks for our domain and competitors. Claude and `inject_dashboard.py` read both through
its MCP endpoint.

**One instance serves many sites.** For a new client, reuse the existing instance: create a new project,
connect that client's GSC property, add trackers. Deploy a new instance only for a new owner.

## A. Deploy (once per owner)

Follow upstream `docs/SELF_HOSTING_CLOUDFLARE_MANUAL.md` (KV x2, D1, R2, IDs into `wrangler.jsonc`,
`pnpm run deploy`). Deltas that upstream does not tell you:

1. Work on a branch (`deploy`), never on `main`: updates are `git fetch upstream && git reset --hard
   upstream/main` on main, then rebase the branch. `origin` is the public repo: do not push resource IDs.
2. Use `corepack pnpm`. If npx/pnpm fail with EACCES because `~/.npm` has root-owned folders, point them at
   a fresh cache: prefix the command with `npm_config_cache="$HOME/.npm-cache-alt"`.
3. **R2 is mandatory.** It is the DataForSEO response cache (6 h backlinks, 7 days LLM prompts) and the code
   calls `env.R2` without guards. Standard storage class only, or the free tier breaks.
4. **Deploy reads `dist/server/wrangler.json`, not `wrangler.jsonc`.** The Vite Cloudflare plugin generates it
   at build time. Any change to `wrangler.jsonc` needs `corepack pnpm run build` BEFORE `wrangler deploy`,
   otherwise it silently does not ship. Check with `npx wrangler versions view <id>`.
5. Never `wrangler deploy --update-config`: it drops `"migrations_dir": "drizzle"`.
6. Secret name is `DATAFORSEO_API_KEY` (see 01-dataforseo.md).

## B. Custom domain + Cloudflare Access (required: Access cannot guard *.workers.dev)

1. In `wrangler.jsonc`: `"routes": [{ "pattern": "seo.<owner-domain>", "custom_domain": true }]`.
   `wrangler deploy` silently skips custom_domain routes; `npx wrangler triggers deploy` applies them.
   After this workers.dev switches off by itself.
2. Zero Trust (free plan) -> Access -> Applications -> Add -> Self-hosted, hostname `seo.<owner-domain>`.
   Policy 1: Allow, Include -> Emails -> the owner's email. Login: Cloudflare one-time PIN is enough.
3. Put `TEAM_DOMAIN` and `POLICY_AUD` into `"vars"` in `wrangler.jsonc` (they are not secrets), build, deploy.
   **TEAM_DOMAIN is the host you get redirected to**, not the "Team name" in the panel:
   `curl -sI https://seo.<owner-domain> | grep -i location` -> `https://<team>.cloudflareaccess.com`.
   The worker compares the JWT issuer with it byte for byte.
4. Without `TEAM_DOMAIN`/`POLICY_AUD` every request fails `AUTH_CONFIG_MISSING` (default AUTH_MODE is
   `cloudflare_access`).
5. Open the site once in a browser and sign in: this creates the single user row the MCP will act as.

## C. MCP access for Claude and scripts (service token)

1. Zero Trust -> Access -> Service Auth -> Service Tokens -> Create (`openseo-mcp`, 1 year). Copy Client ID
   and Client Secret **values only**. The copy icon puts `CF-Access-Client-Secret: <value>` in the clipboard;
   the secret alone is exactly 64 characters.
2. In the OpenSEO application add a second policy: action **Service Auth**, Include -> Service Token ->
   `openseo-mcp`. Then press **Save at the bottom of the application page**. The "Policy saved" toast does not
   attach it. Check: the Applications list shows "<policy> + 1 other policy".
3. **Patch the worker.** Upstream `/mcp` resolves the user from a human JWT (`sub` + `email`); a service token
   carries only `common_name`, so Access lets it through and the worker answers 500. Apply
   `patches/openseo-service-token-mcp.patch` on the deploy branch (`git am < …patch`), build, deploy.
   Keep the patch when updating from upstream.
4. Register the MCP in **user scope** (a header with a secret must never land in a project `.mcp.json`).
   Two-step rule: the user runs it and types the secret, Claude never sees it:
   ```bash
   claude mcp add --transport http open-seo https://seo.<owner-domain>/mcp --scope user \
     --header "CF-Access-Client-Id: <client-id>" --header "CF-Access-Client-Secret: <secret>"
   ```
   New MCP servers load only in a new session. Tools appear as `mcp__open-seo__*`.
5. Scripts reuse the same credentials from `~/.claude.json` (`mcpServers.open-seo.url/headers`), see
   `scripts/inject_dashboard.py`. Always send a `User-Agent` (Cloudflare bot filter answers 403 otherwise).

## D. Google Search Console inside OpenSEO (OAuth)

1. Google Cloud console -> new project -> APIs & Services -> enable **Google Search Console API**.
2. Google Auth Platform -> Branding: app name, support email, authorized domain `<owner-domain>`, home page,
   **privacy policy URL, terms URL** (real pages on the owner's site; the privacy page should include the
   Google API Services "Limited Use" paragraph). **Do not upload a logo**: a logo sends the app to
   verification; without it publishing is instant because `webmasters.readonly` + `userinfo.email` are not
   sensitive scopes.
3. Clients -> Create -> Web application, redirect URI `https://seo.<owner-domain>/api/gsc/oauth/callback`.
4. Worker secrets: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `BETTER_AUTH_SECRET`
   (`openssl rand -base64 32 | npx wrangler secret put BETTER_AUTH_SECRET`). Without BETTER_AUTH_SECRET the
   UI says "Google OAuth client not configured" even with the Google keys set. Never change it later: it
   encrypts the stored tokens.
5. **Audience -> Publish app -> In production.** In "Testing" the refresh token dies after 7 days and every GSC
   call returns `{"ok":false,"reason":"api_error"}` while the UI still says Connected.
6. OpenSEO UI -> GSC Insights -> Connect -> pick the property (`sc-domain:<domain>`). On the "Google hasn't
   verified this app" screen the continue link is the small one; the big blue button means cancel.
7. The Google account that connects must have access to the property. For a client: the client adds that
   Google account in Search Console -> Settings -> Users and permissions (Full).

Diagnose a dead token in D1, not in code:
`npx wrangler d1 execute <db> --remote --json --command "SELECT updated_at, refresh_token_expires_at FROM account WHERE provider_id='google-search-console'"`.
If publishing happened after the token died: Disconnect -> Connect again.

A deaf "Google rejected the Search Console authorization code" usually hides `401 invalid_client`
(secret copied wrong): make a new client secret in Google (it will not show the old one).

## E. Rank tracking for the dashboard

1. `mcp__open-seo__list_projects` -> project id -> `openseo.project_id` in the dashboard config.
2. In the OpenSEO UI (Rank tracking) add a tracker for the own domain with 8-15 category keywords
   (country, language, device, weekly). Its domain must equal `openseo.own_tracker_domain` in the config.
3. **Competitors = separate trackers with the SAME keyword list.** OpenSEO has no native comparison;
   `inject_dashboard.py` merges trackers by keyword text. Pick competitors from the live SERP of those
   keywords, not from the LLM answers (different sets).
4. First check runs on schedule; each check is ~$0.08 per domain.
