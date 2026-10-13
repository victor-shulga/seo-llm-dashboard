# Google AI-mode impressions — UI export only (optional section)

Search Console has a report "Performance -> Generative AI features" (in Russian UI «Функции на основе
генеративного ИИ»): impressions in AI Overviews, AI Mode and Discover AI blocks.

Hard facts, verified September 2026:
- **Not in the Search Analytics API** (no `type` value for it, `searchAppearance` returns zero rows) and
  **not in the BigQuery bulk export**. Do not spend time looking.
- Impressions only, **no clicks**. History starts 2026-05-18, no backfill.
- The only way out is the report's EXPORT button (CSV as ZIP, or Google Sheets).

Flow:
1. Owner opens the report, sets the period (3 months), EXPORT -> Download CSV.
2. `python3 scripts/import_gsc_ai.py ~/Downloads/<file>.zip <dashboard-dir>/seo_ai.json`
   (column headers are localized; the script matches by keywords, ru/uk/en).
3. `ai_mode_file` in the dashboard config points at that JSON; re-run inject and deploy.

With only a total typed in (no export), the page shows the two KPI cards and hides the daily chart and the
page/country tables. That is by design: an empty frame read as a broken dashboard.

Ask the owner once whether they will export monthly. If not, keep the section with the total or drop
`ai_mode_file` from the config, and do not offer the export again.
