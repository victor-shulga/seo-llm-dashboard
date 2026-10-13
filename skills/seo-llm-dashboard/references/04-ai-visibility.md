# AI Visibility Score — the ai-visibility-report run behind the donuts

The block is fed by a run of the **ai-visibility-report** skill. It is optional: if it is installed
(`npx skills add victor-shulga/ai-visibility-report`), read its SKILL.md before the first run; without it
the AI Visibility Score block stays hidden. This file only covers what the dashboard needs on top of it.

## Decide the market before writing a single prompt

The score is only meaningful for the buyers the owner actually sells to. The skill defaults to
US/English; that default was wrong for a Ukrainian-market owner and the first run had to be thrown away.
Ask: who asks the model, in which country, in which language(s)?

Multilingual market (e.g. Ukrainian founders asking in uk/ru/en): one config, the same topics in every
language, and a `lang` field on every prompt. The dashboard computes the score per language from it.

## Prompt set that worked

- 4 topics a buyer asks about (category, strategy, channel, team-building).
- Per language per topic: 1 Comparative ("who are the best…") + 1 Recommendation ("recommend…").
- 1 Branded prompt per language ("What do you know about <brand> as <category>? Is it worth working with?").
  Branded answers never enter the score; they show whether the models recognise the name and what they get
  wrong about it (old company name, wrong role, no proof). Those errors are usually the best finding.
- 3 languages -> 27 prompts x 4 models = 108 answers, ~$4.3.
- Geo in the text ("…for a Ukrainian IT agency…"), because two of four models take no country parameter.

```json
{"id": "p1", "keyword": "fractional CRO for IT agencies", "type": "Comparative", "branded": false, "lang": "uk", "text": "…"}
```

## Config fields that matter for the dashboard

- `brand_pattern`: every spelling and grammatical case, including Cyrillic
  (`(ivan|іван|иван)\w*\s+(petrenko|петренк)|ivanpetrenko` for a person brand "Ivan Petrenko"). A model that says only
  "he" is not a mention; that is correct.
- Competitors: 5 names + domains + regex. A generic word used as a name (e.g. "ScaleUp") needs a
  case-sensitive group: `(?-i:\bScaleUp\b)`. After collect, check each competitor match in context.
- `country_iso` may be a per-model dict: `{"chat_gpt": "UA", "perplexity": "UA", "claude": null, "gemini": null}`.
- Keep one run folder per brand+market: `ai-visibility/runs/<domain>-<market>/`. The dashboard config's
  `geo.run_dir` points there.

## How the dashboard reads the run

`inject_dashboard.py` takes the newest **finalized** month (cells file + data JSON present) and recomputes
from the cells: total score, per-language score, per-model counts, competitors with the SAME formula
(0.6 x share of unbranded answers naming them + 0.4 x share citing their domain), top cited domains,
and the change against the previous finalized month. The PDF's competitor table is share of voice, a
different scale; do not copy its numbers onto the page.

"What to do" rows come from `geo.notes_file` (template: `templates/seo_geo.example.json`), written by hand
per run, in the dashboard language, each citing a number from the run. `forRun` = the run's
`date_generated`; the script warns when they drift apart.

## Monthly

`avr.py remeasure <config>` rolls the folder to the current month (archives last month, pins models,
seeds `previous`). The monthly scheduled task in `templates/scheduled-tasks.md` runs the whole cycle.
One answer out of 32 moves a language score by ~2 points: treat changes under 1 point as noise.
