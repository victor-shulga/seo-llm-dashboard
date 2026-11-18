# AI visibility measurement — the run behind the AI block

The measurement ships inside this skill: `scripts/avr.py` + `scripts/dfs.py` + `scripts/aggregate.py`,
vendored from the ai-visibility-report skill (same code, same numbers). No second skill is needed.
A client-ready PDF of the same run is the only thing left to ai-visibility-report: install it only
when someone asks for a PDF, and point its `avr.py finalize` at the same run folder.

`<skill-dir>` = the folder with this skill's SKILL.md. All commands are free except `collect` and `volume`.

## 0. Credentials (once)

See `01-dataforseo.md`. Before anything else: `python3 <skill-dir>/scripts/avr.py check` (free).
If it fails, stop and walk the user through Step 1 of `SETUP.uk.md`; never ask for the key in the chat.

## 1. Decide the market before writing a single prompt

The score only means something for the buyers the owner actually sells to. The US/English default was
wrong for a Ukrainian-market owner once and the first run was thrown away. Ask: who asks the model,
in which country, in which language(s)?

## 2. Write the run config

Run folder: one per brand + market, `ai-visibility/runs/<domain>-<market>/` under the user's working
folder (or `$AVR_RUNS_DIR`). Config file name MUST be `<brand_domain>_config.json` (the dashboard looks
it up by that name). Start from `templates/ai_run.config.example.json`.

- `brand_pattern`: case-insensitive regex for every spelling and grammatical case, Latin and Cyrillic
  (`(ivan|іван|иван)\w*\s+(petrenko|петренк)|ivanpetrenko`). A model that says only "he" is not a mention.
- `competitors`: 3-5 × `{name, domain, pattern}`. A generic word used as a name (e.g. "ScaleUp") needs a
  case-sensitive group: `(?-i:\bScaleUp\b)`. After collect, check each competitor match in context.
- `period_slug` (`2026-11`) names the files; `period_current` (`November 2026`) is the label;
  `date_generated` (ISO date) is what the page shows as "measured on".
- `country_iso`: `"US"`, or a per-model dict `{"chat_gpt": "UA", "perplexity": "UA", "claude": null, "gemini": null}`
  (Claude rejects some countries with 40501, Gemini takes none: put the country in the prompt text too).
- `location_name` / `language_code`: used by `volume` only.
- `llm_model_overrides`: `{}` on a first run; `remeasure` pins the models later.
- `white_label`: only matters for a PDF; leave the example values.

**Prompt set that worked** (`prompts`, ids `p1..pN`, each with `branded` and `lang`):
- 4 topics a buyer asks about.
- Per language per topic: 1 Comparative ("who are the best…") + 1 Recommendation ("recommend…").
- 1 Branded prompt per language ("What do you know about <brand> as <category>? Is it worth working with?").
  Branded answers never enter the score; they show whether the models know the name and what they get
  wrong (old company name, wrong role, no proof). Those errors are usually the best finding.
- 3 languages → 27 prompts × 4 models = 108 answers ≈ $4. One language → 9 prompts, 36 answers ≈ $1.5.

## 3. Show the cost, wait for "yes", collect

```bash
python3 <skill-dir>/scripts/avr.py estimate <run>/<domain>_config.json     # free, prints answers and $
python3 <skill-dir>/scripts/avr.py collect  <run>/<domain>_config.json     # SPENDS money
```

Show the `estimate` line to the user and wait for an explicit yes. Run `collect` in the background. It
picks the newest top-tier model per assistant (written back into the config), fans out 6 at a time,
writes `raw/<prompt>__<llm>.json` and the `*_cells.json` checkpoint after every answer, and prints the real
sum at the end. Killed run: run the same command again, measured answers are skipped.

Optional, cents: `avr.py volume <config> "head term 1,head term 2"` → AI search demand
(`_search_volume.json`). Long-tail phrasings come back 0; pass 4-6 short head terms.

## 4. Judge prominence

```bash
python3 <skill-dir>/scripts/avr.py review <config> > <run>/review.txt
```

Read every printed answer and write `<run>/prominence.json`
`{"p4": {"chat_gpt": "Shortlist", "claude": "Passing mention"}, ...}` for EVERY cell that names the brand:
- **Named first**: the lead or sole recommendation.
- **Shortlist**: among several options, or "yes, but verify".
- **Passing mention**: named or described, not recommended; every purely descriptive answer.

## 5. Finalize → the page

```bash
python3 <skill-dir>/scripts/avr.py finalize <config>
```

Writes `<domain>_ai_visibility_<slug>.json`. Only months with this file appear on the page, so a
half-collected run never leaks. Then set `geo.run_dir` in the dashboard config to the run folder.

## 6. Diagnose and recommend (free, after every measurement)

```bash
cd <run> && python3 <skill-dir>/scripts/diagnose.py <domain>_config.json        # «Чому не назвали» + sources
python3 <skill-dir>/scripts/inject_dashboard.py <dashboard-dir>/dashboard.config.json  # fresh page data
python3 <skill-dir>/scripts/recommend.py <dashboard-dir>/dashboard.config.json --write
python3 <skill-dir>/scripts/inject_dashboard.py <dashboard-dir>/dashboard.config.json  # rows on the page
```

`diagnose.py` reads the site's sitemap and the third-party pages the models cited in lost answers (plain
HTTP, cached in `_diagnose_cache.json`, no API spend) and writes `*_diagnosis.json`: per prompt why it was
lost (no page, page without the name, only some models, old brand) and which sources to go after
(profile to claim, list to get into, outdated data to fix). Optional `<domain>_diagnose.json` maps each
topic to a title regex of its dedicated page (`{"topics": {"<keyword>": "<regex>"}, "old_brand_regex": "…"}`);
without it every topic counts as "no page".

`recommend.py` turns that into 3-6 «Що робити» rows, each with a number from the run, effort and
priority, plus 1-3 search rows when Search Console / rank data are on the page (a query with 50+
impressions in the top 10 and CTR under 2%, a keyword at positions 11-20). It writes them to
`geo.notes_file` with `forRun` = the run's `date_generated`. If the data JSON already carries
`sections.opportunities` (a run that also went through ai-visibility-report), those rows are used.
Read the rows; reword one if it reads badly, never change a number, never add a row without one.

## How the dashboard reads the run

`inject_dashboard.py` takes the newest finalized month and recomputes from the cells: total score
(0.6 × share of unbranded answers naming the brand + 0.4 × share citing its domain), per language, per
model, competitors with the SAME formula on the same answers, top cited domains, every prompt with each
model's answer (cut at 2 500 characters), and the change against the previous finalized month.

## Monthly

`avr.py remeasure <config>` rolls the folder to the current month: archives last month's config,
prominence and `raw/` under its slug, pins the models, seeds `previous`. Idempotent. Then steps 3-5 again.
The monthly scheduled task in `templates/scheduled-tasks.md` runs the whole cycle with a budget.
One answer out of 32 moves a language score by ~2 points: treat changes under 1 point as noise.

## Known traps (all hit on real runs)

| Trap | Where it's handled |
|---|---|
| urllib in threads hangs whole runs on macOS | `dfs.py` uses curl subprocesses |
| `gpt-5` sorted above `gpt-5.6` | versions padded in `avr.pick_model` |
| reasoning glued to the answer | only `type == "message"` sections are kept |
| a competitor's name inside a URL slug counted as a mention | `dfs.visible()` strips link targets |
| Gemini sources are `vertexaisearch` redirects | `dfs.resolve()` follows them |
| `uk.example.com` and `www.example.com` as two sites | `dfs.domain()` keeps the registrable domain |
| one model fails every answer (retired at DataForSEO) | drop it from `llm_model_overrides`, delete `llms_covered`, collect again |
| the tracked competitors are not who the models name | count who is actually named per topic and tell the user |
| the brand is still known by an old name | read every branded answer in `review`; set `old_brand_regex` in the dashboard config |
