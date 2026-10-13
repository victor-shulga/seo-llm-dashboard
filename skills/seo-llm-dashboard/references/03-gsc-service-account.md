# Search Console directly — service account + local `gsc` MCP (recommended, optional for the page)

The dashboard's numbers come through OpenSEO. This second, direct connection is for everything OpenSEO
narrows away: all Search Analytics dimensions and filters, 16 months, URL Inspection, sitemaps, a
sitemap-wide index-coverage sweep. The numbers match OpenSEO's; the proxy just does less.

Server: `scripts/gsc_mcp_server.py` (PEP 723 script, run by `uv`, read-only scope `webmasters.readonly`).
Tools: `sites`, `performance`, `compare`, `inspect_url`, `sitemaps`, `index_coverage`.
Same code works as a CLI: `uv run --script gsc_mcp_server.py --call compare '{"days":28}'`.

## Setup (once per owner)

1. Google Cloud console -> project (a separate one from OpenSEO's OAuth project is cleaner) ->
   enable **Google Search Console API**.
2. IAM & Admin -> Service accounts -> Create (`gsc-mcp`). **No roles.** Done.
3. The service account -> Keys -> Add key -> JSON. Move it into place (user runs it):
   ```bash
   mkdir -p ~/.config/gsc-mcp && mv ~/Downloads/<key-file>.json ~/.config/gsc-mcp/service-account.json && chmod 600 ~/.config/gsc-mcp/service-account.json
   ```
   If the org policy blocks key creation (`iam.disableServiceAccountKeyCreation`), use a personal Google
   Cloud project.
4. **Data access is granted in Search Console, not IAM:** property -> Settings -> Users and permissions ->
   Add user -> the service account's `client_email` -> Full. Repeat per property (a client adds it to theirs).
5. Copy the server somewhere stable (e.g. `~/tools/gsc-mcp/server.py`) and register in user scope:
   ```bash
   claude mcp add gsc --scope user --env GSC_DEFAULT_SITE=sc-domain:<domain> -- uv run --script ~/tools/gsc-mcp/server.py
   ```
6. Check: `uv run --script ~/tools/gsc-mcp/server.py --check` lists the properties it can see.

## Traps

- **403 = the service account was not added to the property** in Search Console. IAM roles do not help.
- Last 2-3 days are incomplete; windows end 3 days back by default. Never read a fresh dip as a drop.
- Rows sum to LESS than the total: Google hides low-volume queries. Quote totals from an unsegmented call.
- `sitemaps.indexed` is always 0 (deprecated field). Use `index_coverage`.
- `inspect_url` flips between sub-states ("Discovered – not indexed" vs "URL is unknown") across calls; the
  fact "not indexed" is reliable, the exact stage is not.
- **The AI-mode / generative-AI report is not in this API and never will be** (see 05-gsc-ai-mode.md).
