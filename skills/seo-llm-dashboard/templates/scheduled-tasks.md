# Scheduled task prompts

Two recurring jobs keep the dashboard alive. Create them with the Claude scheduled-tasks tool
(`mcp__scheduled-tasks__create_scheduled_task`), fill every `<…>`, then press "Run now" once
yourself so the tool approvals (python, uv, wrangler/netlify) are stored for future runs.
A scheduled task only runs while the Claude app is open; a missed slot runs on next launch.

Placeholders: `<SKILL_DIR>` = where this skill is installed (the folder with SKILL.md);
`<AVR_SKILL_DIR>` = where the ai-visibility-report skill is installed; `<DASHBOARD_DIR>` = the working
folder with `dashboard.config.json`. Job 2 exists only if ai-visibility-report is installed
(`npx skills add victor-shulga/ai-visibility-report`).

Cron is LOCAL time. Keep both after 10:00: before that the Mac is often asleep.

---

## 1. Weekly refresh — Search Console, rank tracking, page rebuild (no DataForSEO spend)

- taskId: `seo-dashboard-weekly-<slug>` · cron: `30 10 * * 1` (Mondays 10:30)

```text
Weekly refresh of the SEO + LLM dashboard for <BRAND> (<DOMAIN>). Talk to <OWNER> in <LANGUAGE>.
This job spends nothing: OpenSEO runs its own rank checks, this only re-reads data and rebuilds the page.

1. cd "<DASHBOARD_DIR>" && python3 "<SKILL_DIR>/scripts/inject_dashboard.py" dashboard.config.json
   If it stops with "Search Console returned no rows" or {"ok":false,"reason":"api_error"} from OpenSEO,
   the Google OAuth token inside OpenSEO has expired: tell <OWNER> to reconnect GSC in the OpenSEO UI
   (GSC Insights -> Disconnect -> Connect) and stop. Do not retry in a loop.
2. Deploy: <DEPLOY_COMMAND>
3. Check the live page: curl -s "<LIVE_URL>?nc=$RANDOM" | grep -c "оновлено <today YYYY-MM-DD>" must be > 0.
4. Report in 3-5 lines: clicks and impressions for 28 days vs the 28 before, keywords in top 10,
   any keyword that moved 3+ positions. A week of data is noise below that; say so.

Never publish anything else, never message anyone, never edit other sections of the page.
```

---

## 2. Monthly AI-visibility re-measure (spends DataForSEO money)

- taskId: `ai-visibility-monthly-<slug>` · cron: `0 11 1 * *` (1st of the month 11:00)
- Needs the ai-visibility-report skill and a finished first run in `<RUN_DIR>`.

```text
Monthly re-measure of AI visibility for <BRAND> (<DOMAIN>). Talk to <OWNER> in <LANGUAGE>.
<OWNER> approved this job on <DATE> with a budget of up to $<BUDGET> per run (first run cost $<FIRST_COST>).
If the estimate is above the budget, stop and write to <OWNER> without running anything.

What is measured: <N_PROMPTS> prompts (<TOPICS> topics x <LANGS> languages, unbranded + branded) x 4 models.
Prompts and competitors are already in the config. Do NOT change them: months would stop being comparable.

Run folder: <RUN_DIR>
Skill: <AVR_SKILL_DIR> (read SKILL.md steps 4-6 and the Known traps table).
CLI: python3 <AVR_SKILL_DIR>/scripts/avr.py <command> <DOMAIN>_config.json, run from the run folder.

1. `avr.py remeasure`. It archives last month (config/prose/prominence/raw under its slug), pins the same
   models and puts last month's score into prose.summary.previous. If it prints "already on YYYY-MM" and
   <DOMAIN>_ai_visibility_YYYY-MM.json exists, the month is done: tell <OWNER> briefly and stop.
   If "already on" but no data JSON, continue from step 2 (collect only fetches missing answers).
2. `avr.py collect` in the background (Bash run_in_background, log to collect.log), wait for the completion
   notice, do not poll with sleep. If every answer of one model failed (model retired at DataForSEO):
   drop that model from llm_model_overrides, delete the llms_covered key from the config, run collect again.
   Other models' answers are kept. Name the model change in the text.
3. `avr.py review > review.txt`, read every answer that names the brand, write prominence.json
   {"p1": {"chat_gpt": "Named first"}, ...} for EVERY such cell. Named first = lead or sole recommendation;
   Shortlist = among several or "yes, but verify"; Passing mention = named, not recommended, and every purely
   descriptive answer. Note what the models get wrong about the brand (old name, wrong role, no proof).
4. `avr.py finalize` once (prose holds only previous), read sections in <DOMAIN>_ai_visibility_<slug>.json,
   then write <DOMAIN>_prose.json per the prose schema of the ai-visibility-report skill (`prose.schema.md` in its references folder) in <REPORT_LANGUAGE>: summary.narrative +
   insight (with the change vs last month), insights for by_llm, by_prompt, citation_landscape, competitors,
   and 3-4 opportunities.actions, each `why` citing a number from this run. Copy the search_volume block
   unchanged from <DOMAIN>_prose_<previous slug>.json. Compute the score per language (the `lang` field of the
   prompts). One answer out of 32 is worth about two points: call a change under one point noise.
   Text rules: numbers only from the JSON, nothing invented<EXTRA_WRITING_RULES>.
5. `avr.py finalize` again. Render the PDF pages with `uv run --with pymupdf`, look at them. A blank or broken
   page = fix and rebuild.
6. Update <NOTES_FILE>: forRun = date_generated from the config, actions = 3-4 rows {"title","what","effort"}
   in <DASHBOARD_LANGUAGE> for this month's findings. Leave the note field alone.
7. Dashboard: cd "<DASHBOARD_DIR>" && python3 "<SKILL_DIR>/scripts/inject_dashboard.py" dashboard.config.json,
   then <DEPLOY_COMMAND>. Check: curl -s "<LIVE_URL>?nc=$RANDOM" | grep -c "<date_generated>" > 0.
8. Summary to <OWNER>, short: score total and per language, change vs last month; which models started or
   stopped naming the brand; 2-3 findings; cost of the run; path to the PDF. Remind that it is a snapshot.

Never: publish the PDF anywhere (it is confidential), message anyone, change prompts, competitors or the
score formula. If something breaks and one or two attempts do not fix it, stop and say at which step and
with which error.
```
