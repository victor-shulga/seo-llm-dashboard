#!/usr/bin/env python3
"""AI visibility measurement for the dashboard — one CLI for the whole run.

Vendored from the ai-visibility-report skill (same scripts, same numbers), so this skill measures
on its own. Differences: `finalize` writes the data JSON the dashboard reads and no PDF (the PDF
builder lives in ai-visibility-report and works on the same run folder), plus `check` and `estimate`.

    avr.py check    [config.json]              free call: are the DataForSEO credentials valid, balance
    avr.py estimate <config.json>              answers x price, before any spend (free, local)
    avr.py collect  <config.json>              models (Step 2b) + live answers -> cells + raw/
    avr.py volume   <config.json> [head kws]   AI search volume for topics (+ head terms)
    avr.py review   <config.json>              print every answer that names the brand
    avr.py finalize <config.json>              apply prominence.json, aggregate -> data JSON for the page
    avr.py remeasure <config.json>             roll the run folder to the current month: same prompts,
                                               models pinned, last month's score -> prose.previous

All files live next to the config (the run folder). Costs money only in `collect`
and `volume` (`check` uses DataForSEO's free user_data endpoint); everything else is local. `collect` resumes: re-running skips cells
already measured, so a killed run is continued, not repeated.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dfs  # noqa: E402

LLMS = ("chat_gpt", "gemini", "claude", "perplexity")
LABEL = {"chat_gpt": "ChatGPT", "gemini": "Gemini", "claude": "Claude", "perplexity": "Perplexity"}
TOP = ("pro", "opus", "ultra")
LOW = ("flash", "mini", "nano", "lite", "haiku")
PROMINENCE = ("Named first", "Shortlist", "Passing mention", "Absent")


def load(cfg_path):
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    run = os.path.dirname(os.path.abspath(cfg_path))
    stem = f"{cfg['brand_domain']}_ai_visibility_{cfg['period_slug']}"
    return cfg, run, stem


def save(obj, path):
    json.dump(obj, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# ── Step 2b: deterministic model pick ─────────────────────────────────────────
def pick_model(llm):
    res = dfs.call("GET", f"/ai_optimization/{llm}/llm_responses/models")["tasks"][0]["result"]
    pool = [m for m in res if m.get("web_search_supported")] or res

    def key(m):
        n = m["model_name"].lower()
        tier = 0 if any(t in n for t in TOP) else 2 if any(t in n for t in LOW) else 1
        ver = [int(x) for x in re.findall(r"\d+", re.sub(r"-\d{4}-?\d{2}-?\d{2}$|-\d{8}$", "", n))[:3]]
        ver += [0] * (3 - len(ver))   # unpadded, "gpt-5" sorted above "gpt-5.6"
        return (tier, [-v for v in ver], 0 if m.get("reasoning") else 1, n)
    return sorted(pool, key=key)[0]["model_name"]


def classify(cfg, p, m, a):
    if a["status"] != "measured":
        return {"prompt_id": p["id"], "model": m["label"], "status": "not_measured"}
    text = dfs.visible(a["text"])
    doms = [dfs.domain(u) for u in a["sources"]]
    mention = bool(re.search(cfg["brand_pattern"], text, re.I))
    return {
        "prompt_id": p["id"], "model": m["label"], "status": "measured",
        "brand_mention": mention,
        "brand_citation": cfg["brand_domain"] in doms or cfg["brand_domain"] in text.lower(),
        "prominence": "Shortlist" if mention else "Absent",   # judged in `review`/`finalize`
        "competitor_mentions": [c["domain"] for c in cfg.get("competitors", [])
                                if re.search(c["pattern"], text, re.I)],
        "competitor_citations": [c["domain"] for c in cfg.get("competitors", [])
                                 if c["domain"] in doms],
        "cited_sources": [{"domain": dfs.domain(u), "page": re.sub(r"^https?://[^/]+", "", u) or "/"}
                          for u in a["sources"]],
    }


def collect(cfg_path):
    cfg, run, stem = load(cfg_path)
    raw = os.path.join(run, "raw")
    os.makedirs(raw, exist_ok=True)
    overrides = cfg.get("llm_model_overrides") or {}
    if not cfg.get("llms_covered"):
        cfg["llms_covered"] = []
        for llm in LLMS:
            name = overrides.get(llm) or pick_model(llm)
            cfg["llms_covered"].append({"llm_type": llm, "model_name": name,
                                        "label": f"{LABEL[llm]} ({name})"})
        save(cfg, cfg_path)
    print("models:", ", ".join(m["label"] for m in cfg["llms_covered"]), flush=True)

    cells_path = os.path.join(run, f"{stem}_cells.json")
    cells = json.load(open(cells_path)) if os.path.exists(cells_path) else []
    cells = [c for c in cells if c.get("status") == "measured"]
    done = {(c["prompt_id"], c["model"]) for c in cells}
    jobs = [(p, m) for p in cfg["prompts"] for m in cfg["llms_covered"] if (p["id"], m["label"]) not in done]
    total = len(cfg["prompts"]) * len(cfg["llms_covered"])
    print(f"cells: {len(done)} done, {len(jobs)} to fetch", flush=True)

    def work(p, m):
        # country_iso: "US" for all models, or {"chat_gpt": "UA", "claude": null, ...} per model,
        # because Claude rejects some countries (UA -> 40501) that ChatGPT/Perplexity accept
        country = cfg.get("country_iso", "US")
        if isinstance(country, dict):
            country = country.get(m["llm_type"])
        a = dfs.live_answer(m["llm_type"], m["model_name"], p["text"], country)
        save({"prompt": p, "model": m, **a}, os.path.join(raw, f"{p['id']}__{m['llm_type']}.json"))
        return classify(cfg, p, m, a), a.get("cost", 0)

    spent = 0.0
    with ThreadPoolExecutor(max_workers=6) as ex:
        for f in as_completed([ex.submit(work, p, m) for p, m in jobs]):
            cell, cost = f.result()
            spent += cost
            cells.append(cell)
            save(cells, cells_path)
            mark = "✓" if cell.get("brand_mention") else "·" if cell["status"] == "measured" else "✗"
            print(f"  {mark} {cell['prompt_id']:<4} {cell['model']:<36} ({len(cells)}/{total})", flush=True)
    failed = sum(1 for c in cells if c["status"] != "measured")
    print(f"done · spent ${spent:.3f} · failed {failed}"
          + (" · >20% failed: low-confidence run, re-run collect" if failed > total * 0.2 else ""), flush=True)


def volume(cfg_path, head=None):
    cfg, run, _ = load(cfg_path)
    out = {}
    for name, kws in (("topics", cfg["keywords"]), ("head", head or [])):
        if not kws:
            continue
        r = dfs.call("POST", "/ai_optimization/ai_keyword_data/keywords_search_volume/live",
                     {"keywords": kws, "location_name": cfg["location_name"],
                      "language_code": cfg["language_code"]})
        if r.get("failed"):
            print(f"{name}: unavailable for this locale ({r.get('error')})")
            continue
        res = (r["tasks"][0].get("result") or [{}])[0]
        out[name] = [{"keyword": i["keyword"], "ai_search_volume": i.get("ai_search_volume")}
                     for i in res.get("items") or []]
        print(name, out[name])
    save(out, os.path.join(run, "_search_volume.json"))


def review(cfg_path):
    """Every answer that names the brand, trimmed, so prominence can be judged by reading."""
    cfg, run, _ = load(cfg_path)
    rx = re.compile(cfg["brand_pattern"], re.I)
    for f in sorted(os.listdir(os.path.join(run, "raw"))):
        d = json.load(open(os.path.join(run, "raw", f)))
        if d.get("status") != "measured":
            continue
        text = dfs.visible(d["text"])
        m = rx.search(text)
        if not m:
            continue
        start = max(0, m.start() - 300)
        snippet = re.sub(r"\n{2,}", "\n", text[start:start + 1100]).strip()
        print(f"##### {d['prompt']['id']} · {d['prompt']['type']} · {d['model']['llm_type']}")
        print(f"Q: {d['prompt']['text']}\n{snippet}\n")
    print("Write prominence.json as {prompt_id: {llm_type: one of " + " / ".join(PROMINENCE[:3]) + "}}")


def finalize(cfg_path):
    cfg, run, stem = load(cfg_path)
    cells_path = os.path.join(run, f"{stem}_cells.json")
    cells = json.load(open(cells_path))
    prom_path = os.path.join(run, "prominence.json")
    prom = json.load(open(prom_path)) if os.path.exists(prom_path) else {}
    label_llm = {m["label"]: m["llm_type"] for m in cfg["llms_covered"]}
    for c in cells:
        if c["status"] != "measured":
            continue
        if not c["brand_mention"]:
            c["prominence"] = "Absent"
            continue
        v = (prom.get(c["prompt_id"]) or {}).get(label_llm[c["model"]])
        if v not in PROMINENCE[:3]:
            raise SystemExit(f"prominence.json has no valid value for {c['prompt_id']} / {c['model']} "
                             f"(got {v!r}). Run `review` and fill it in.")
        c["prominence"] = v
    save(cells, cells_path)

    agg_cfg = {k: v for k, v in cfg.items() if k not in ("brand_pattern", "period_slug", "country_iso")}
    agg_cfg["competitors"] = [{"name": c["name"], "domain": c["domain"]} for c in cfg.get("competitors", [])]
    agg_cfg["output_path"] = os.path.join(run, f"{stem}.pdf")   # aggregate.py derives the data JSON name from it
    tmp_cfg = os.path.join(run, "_config_for_aggregate.json")
    save(agg_cfg, tmp_cfg)
    data_json = os.path.join(run, f"{stem}.json")
    prose = os.path.join(run, f"{cfg['brand_domain']}_prose.json")
    try:
        subprocess.run([sys.executable, os.path.join(HERE, "aggregate.py"), tmp_cfg, cells_path, prose,
                        "-o", data_json], check=True)
    finally:
        os.remove(tmp_cfg)
    print(f"finalized {cfg['period_slug']} -> {data_json}\n"
          "next: inject_dashboard.py <dashboard.config.json> (a PDF for a client: the ai-visibility-report "
          "skill, `avr.py finalize` on this same run folder)")


PRICE = 0.04   # USD per answer, observed 0.036-0.042 (Opus/Pro tier dearer than Sonar); collect prints the real sum


def estimate(cfg_path):
    cfg, _, stem = load(cfg_path)
    n_models = len(cfg.get("llms_covered") or []) or len(LLMS)
    cells_path = os.path.join(os.path.dirname(os.path.abspath(cfg_path)), f"{stem}_cells.json")
    done = sum(1 for c in (json.load(open(cells_path)) if os.path.exists(cells_path) else [])
               if c.get("status") == "measured")
    todo = len(cfg["prompts"]) * n_models - done
    print(f"{cfg['brand_name']} · {cfg.get('location_name', '')} · {len(cfg['prompts'])} prompts x {n_models} models"
          f" = {todo} answers to fetch ({done} already measured) · about ${todo * PRICE:.2f}"
          f" (DataForSEO, {PRICE * 100:.0f} cents per answer). Nothing is spent until `collect`.")


def check(_cfg_path=None):
    """Free: GET /v3/appendix/user_data costs nothing and proves the login/password work."""
    r = dfs.call("GET", "/appendix/user_data")
    if r.get("failed"):
        raise SystemExit(f"DataForSEO check failed: {r.get('error')}")
    res = (r["tasks"][0].get("result") or [{}])[0]
    money = res.get("money") or {}
    print(f"DataForSEO OK · login {res.get('login', '?')} · balance ${money.get('balance', '?')}"
          " · this check cost $0")


def remeasure(cfg_path):
    """Monthly re-measure in the same run folder.

    Archives last month's config / prose / prominence under their slug, pins the models that
    were used (so a changed score is the market, not a model swap), sets the new period and
    seeds prose.summary.previous from last month's data JSON. Idempotent: if the config is
    already on the current month it does nothing.
    """
    from datetime import date
    cfg, run, stem = load(cfg_path)
    today = date.today()
    slug = today.strftime("%Y-%m")
    if cfg.get("period_slug") == slug:
        print(f"already on {slug}: nothing to do")
        return
    old = cfg["period_slug"]
    dom = cfg["brand_domain"]
    data_old = os.path.join(run, f"{stem}.json")
    if not os.path.exists(data_old):
        raise SystemExit(f"{data_old} missing: finish {old} (finalize) before rolling over")
    shutil.copy(cfg_path, os.path.join(run, f"{dom}_config_{old}.json"))
    for name in (f"{dom}_prose.json", "prominence.json"):
        src = os.path.join(run, name)
        if os.path.exists(src):
            base, ext = os.path.splitext(name)
            shutil.move(src, os.path.join(run, f"{base}_{old}{ext}"))
    # raw/ uses the same <prompt>__<llm>.json names every month; keep last month's answers
    if os.path.isdir(os.path.join(run, "raw")):
        shutil.move(os.path.join(run, "raw"), os.path.join(run, f"raw_{old}"))
    summ = json.load(open(data_old, encoding="utf-8"))["sections"]["summary"]
    save({"summary": {"previous": {k: summ[k] for k in
          ("mention_share", "citation_share", "ai_visibility_score")}}},
         os.path.join(run, f"{dom}_prose.json"))
    save({}, os.path.join(run, "prominence.json"))
    cfg["llm_model_overrides"] = {m["llm_type"]: m["model_name"] for m in cfg.get("llms_covered", [])}
    cfg.pop("llms_covered", None)
    cfg["period_prev"] = cfg.get("period_current")
    cfg["period_slug"] = slug
    cfg["period_current"] = today.strftime("%B %Y")
    cfg["date_generated"] = today.isoformat()
    save(cfg, cfg_path)
    print(f"rolled {old} -> {slug} · models pinned: {cfg['llm_model_overrides']}"
          f" · previous score {summ['ai_visibility_score']}")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "check":
        check()
        raise SystemExit(0)
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    cmd, cfg_path = sys.argv[1], sys.argv[2]
    if cmd == "check":
        check(cfg_path)
    elif cmd == "estimate":
        estimate(cfg_path)
    elif cmd == "collect":
        collect(cfg_path)
    elif cmd == "volume":
        volume(cfg_path, [k.strip() for k in sys.argv[3].split(",")] if len(sys.argv) > 3 else None)
    elif cmd == "review":
        review(cfg_path)
    elif cmd == "finalize":
        finalize(cfg_path)
    elif cmd == "remeasure":
        remeasure(cfg_path)
    else:
        raise SystemExit(__doc__)
