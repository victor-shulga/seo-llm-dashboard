# Build, preview, deploy

## Folder layout (one per site)

```
<dashboard-dir>/
  dashboard.html            <- copy of templates/dashboard.html, rewritten in place by inject
  dashboard.config.json     <- from templates/dashboard.config.example.json
  favicon.svg               <- templates/favicon.svg, recolour to the brand
  seo_geo.json              <- "what to do" rows (templates/seo_geo.example.json)
  seo_ai.json               <- optional, from import_gsc_ai.py
```

Keep it inside a working folder the user chooses (not /tmp). If other report pages exist on the same host, set
`tabs` in the config so the pages link to each other, and set `"page"` to the real filename (e.g. `seo.html`).

## Config

Fill every field of `dashboard.config.example.json`:
- `domain` = bare domain, used to strip origins in the pages table and to find the own rank tracker.
- `brand_query_regex` = what counts as a branded search query (name spellings, Latin and Cyrillic).
  `old_brand_regex` = a retired brand still bringing clicks, or null.
- `colors` = the owner's/client's brand. For a client ALWAYS the client's palette, never the agency's.
  `accent` drives bars and donuts, `ink` the text, `positive` good-news numbers (use a green or the
  brand's positive colour; never the same as accent).
- `geo.audience` = the buyer in 3-5 words, shown under the section title. `geo.country_note` = one sentence
  on how the country was set per model, or null.
- UI language of the template is Ukrainian. For another language translate the static labels in
  `dashboard.html` once and keep that copy as the client's template.

## Inject

```bash
python3 <skill>/scripts/inject_dashboard.py <dashboard-dir>/dashboard.config.json
```
Prints one line per source. Sections without data hide themselves: no rank tracker -> no ranks section,
no ai_mode_file -> no AI-mode section, no finalized run -> no AI Visibility Score.

## Preview and verify (before every deploy)

macOS privacy (TCC) blocks a launcher-started python from serving files in protected folders (Desktop,
Documents), so serve a copy:
`python3 <skill>/templates/serve_preview.py <dashboard-dir> 4661` (or a `.claude/launch.json` entry that runs it).
Then in the browser pane: console must have no errors; every section title present; numbers match the
inject printout; screenshot the page. Resync the copy after every inject.
Mobile: the template carries `<meta name="viewport">` and a `<style id="mobile-guard">` block (grid tracks
`minmax(0,1fr)`, tables scroll inside their panel, one column on phones); keep both in every copy. Check the
preview at 360 and 390 px wide: no horizontal page scroll.

## Deploy

The page is one static file plus a favicon. Pick by owner:
- **Cloudflare Pages** (own domain in Cloudflare): `npx --yes wrangler pages deploy <dashboard-dir> --project-name=<project> --commit-dirty=true`.
  First time: `wrangler pages project create <project>`, then attach a custom domain (`report.<domain>`) in
  the dashboard. Pretty URLs: `/seo` serves `seo.html`.
- **Netlify** (client deliverables): `npx --yes netlify-cli deploy --prod --dir <dashboard-dir> --site <SITE_ID>`.
  `--site` takes the UUID, never the name (a name can resolve to a parent-linked site and overwrite it).
  New site = `sites:create` first.

Verify live: `curl -s "<url>?nc=$RANDOM" | grep -c "<a date or number from this build>"` > 0.
Cloudflare caches assets immutably: bump `favicon.svg?v=N` when it changes.

**Privacy.** The page has competitor names and the owner's weak spots. It is unlisted, not private. For a
client, put Cloudflare Access (email allow-list) in front of the Pages domain or use Netlify password
protection. Never publish the AI-visibility PDF.
