#!/usr/bin/env python3
"""Fill the SEO + LLM visibility dashboard (dashboard.html) with live data.

    python3 inject_dashboard.py [path/to/dashboard.config.json]

Default config path: dashboard.config.json next to this script. Every path inside the config is
resolved relative to the config file. With "demo_data" in the config the page is built from that
JSON alone (no OpenSEO, no runs): templates/demo/ uses it. The page is rewritten in place and stays a single
self-contained file (all data inlined, no fetch), so it can be dropped on any static host.

Sources:
  OpenSEO (self-hosted, via its MCP over HTTP) -> Search Console + rank tracking
  <geo.run_dir>  (ai-visibility-report run)    -> AI Visibility Score, per language, vs competitors
  <geo.notes_file>                             -> "what to do" rows written by hand per run
  <ai_mode_file> (import_gsc_ai.py output)     -> Google AI-mode impressions (UI export only)

Why MCP and not REST: the OpenSEO worker has no public API, it sits behind Cloudflare Access, and
the Access service token already lives in ~/.claude.json for the MCP client. One secret, one place.

Three silent traps of MCP over HTTP (all handled below):
  - without a User-Agent Cloudflare answers 403 before Access even looks at the token;
  - the useful JSON is in result.structuredContent, content[0].text is prose for a chat;
  - the answer may arrive as SSE frames when Accept includes text/event-stream.
"""
from __future__ import annotations

import html
import json
import pathlib
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import date

HERE = pathlib.Path(__file__).resolve().parent
CFG_PATH = pathlib.Path(sys.argv[1]).expanduser().resolve() if len(sys.argv) > 1 else HERE / "dashboard.config.json"
CFG = json.loads(CFG_PATH.read_text(encoding="utf-8"))
BASE = CFG_PATH.parent


def rel(p):
    return (BASE / p).resolve() if p else None


PAGE = rel(CFG.get("page", "dashboard.html"))
OWN = CFG["domain"]
OSEO = CFG.get("openseo") or {}
AI_FILE = rel(CFG.get("ai_mode_file"))
GEO = CFG.get("geo") or {}
GEO_RUNS = rel(GEO.get("run_dir"))
GEO_NOTES = rel(GEO.get("notes_file"))

_session = {}


# ── OpenSEO over MCP ───────────────────────────────────────────────────────────
def _server():
    name = OSEO.get("mcp_server", "open-seo")
    servers = json.loads((pathlib.Path.home() / ".claude.json").read_text())["mcpServers"]
    if name not in servers:
        raise SystemExit(f"MCP server '{name}' is not registered in ~/.claude.json (user scope)")
    cfg = servers[name]
    headers = dict(cfg.get("headers") or {})
    headers.update({
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "User-Agent": "curl/8.4.0",          # without it Cloudflare's bot filter answers 403
    })
    return cfg["url"], headers


def rpc(method, params=None, notify=False, _n=[0]):
    url, headers = _server()
    body = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        body["params"] = params
    if not notify:
        _n[0] += 1
        body["id"] = _n[0]
    headers.update(_session)
    req = urllib.request.Request(url, json.dumps(body).encode(), headers, method="POST")
    with urllib.request.urlopen(req, timeout=180) as r:
        if r.headers.get("mcp-session-id"):
            _session["mcp-session-id"] = r.headers["mcp-session-id"]
        raw = r.read().decode()
    if not raw.strip():
        return None
    if raw.lstrip().startswith(("event:", "data:")):
        raw = "\n".join(l[6:] for l in raw.splitlines() if l.startswith("data: "))
    return json.loads(raw)


def connect():
    rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "inject_dashboard", "version": "1"}})
    rpc("notifications/initialized", {}, notify=True)


def tool(name, args):
    res = rpc("tools/call", {"name": name, "arguments": args})["result"]
    data = res.get("structuredContent")
    if data is None:
        raise SystemExit(f"{name}: no structuredContent in the answer ({str(res)[:200]})")
    return data


def gsc(dimensions, days_range="last_28_days", limit=1000):
    return tool("get_search_console_performance", {
        "projectId": OSEO["project_id"], "dimensions": dimensions,
        "dateRange": days_range, "rowLimit": limit})


def search_console():
    """Year of days, queries and pages for 28 days against the 28 before."""
    days = {r["keys"][0]: [r["clicks"], r["impressions"], round(r["position"], 1)]
            for r in gsc(["date"], "last_12_months")["rows"]}
    if not days:
        raise SystemExit("Search Console returned no rows: check the GSC connection in OpenSEO")
    dates = sorted(days)
    last28, prev28 = dates[-28:], dates[-56:-28]

    def total(window):
        clicks = sum(days[d][0] for d in window)
        imp = sum(days[d][1] for d in window)
        pos = sum(days[d][2] * days[d][1] for d in window) / imp if imp else 0   # impression-weighted
        return {"clicks": clicks, "imp": imp, "ctr": round(clicks / imp * 100, 1) if imp else 0,
                "pos": round(pos, 1), "days": len(window)}

    def rows(dim, window="last_28_days"):
        return [[r["keys"][0], r["clicks"], r["impressions"],
                 round(r["ctr"] * 100, 1), round(r["position"], 1)]
                for r in gsc([dim], window)["rows"]]

    weeks = defaultdict(lambda: [0, 0])
    for d in dates:
        iso = date.fromisoformat(d).isocalendar()
        key = f"{iso[0]}-W{iso[1]:02d}"
        weeks[key][0] += days[d][0]
        weeks[key][1] += days[d][1]

    return days, {
        "since": dates[0], "until": dates[-1],
        "weeks": {k: v for k, v in sorted(weeks.items())},
        "last28": total(last28), "prev28": total(prev28) if prev28 else None,
        "queries": rows("query"), "pages": rows("page"),
        "queries3m": rows("query", "last_3_months"),
        "countries": [[r["keys"][0], r["clicks"], r["impressions"]]
                      for r in gsc(["country"], "last_3_months", 20)["rows"]],
    }


def rank_tracking():
    """Our positions plus the same keywords for competitors.

    OpenSEO has no native competitor comparison: each competitor is a separate tracked domain
    with the SAME keyword list, merged here by keyword text.
    """
    configs = tool("get_rank_tracker", {"projectId": OSEO["project_id"]}).get("configs") or []
    own = next((c for c in configs if c["domain"] == OSEO.get("own_tracker_domain", OWN)), None)
    if not own:
        return None
    rivals = [c for c in configs if c is not own]

    def snapshot(cfg):
        data = tool("get_rank_tracker", {"projectId": OSEO["project_id"], "trackerId": cfg["id"]})
        out = {}
        for r in data["results"]["rows"]:
            m = r.get(OSEO.get("device", "mobile")) or {}
            out[r["keyword"]] = {
                "pos": m.get("position"), "prev": m.get("previousPosition"),
                "url": (m.get("rankingUrl") or "").replace("https://", "").rstrip("/"),
                "aio": "ai_overview" in (m.get("serpFeatures") or []),
                "volume": r.get("searchVolume"),
            }
        return out

    mine = snapshot(own)
    comp = {c["domain"]: snapshot(c) for c in rivals}
    rows = []
    for kw, v in sorted(mine.items(), key=lambda kv: (kv[1]["pos"] is None, kv[1]["pos"] or 99, kv[0])):
        rows.append([kw, v["pos"], v["prev"], v["url"], v["aio"], v["volume"],
                     [comp[d].get(kw, {}).get("pos") for d in comp]])
    return {
        "checkedAt": (own.get("lastCheckedAt") or "")[:10], "nextAt": (own.get("nextCheckAt") or "")[:10],
        "market": CFG.get("rank_market_label", ""),
        "competitors": list(comp), "rows": rows,
        "aioShare": round(sum(1 for r in rows if r[4]) / len(rows) * 100) if rows else 0,
        "top10": sum(1 for r in rows if r[1] and r[1] <= 10),
    }


# ── Google AI mode (Search Console UI export only) ─────────────────────────────
def ai_mode(days):
    """AI-mode impressions and their share of ordinary search over the same window.

    Google does not expose this report through the Search Analytics API or BigQuery, so it comes
    from a manual export turned into JSON by import_gsc_ai.py. No file = section stays hidden.
    """
    if not AI_FILE or not AI_FILE.exists():
        return None
    ai = json.loads(AI_FILE.read_text(encoding="utf-8"))
    since, until = ai.get("since"), ai.get("until")
    window = [d for d in days if since and until and since <= d <= until]
    ai["web"] = {"clicks": sum(days[d][0] for d in window),
                 "imp": sum(days[d][1] for d in window), "days": len(window)}
    imp, wimp = (ai.get("total") or {}).get("imp"), ai["web"]["imp"]
    ai["share"] = round(imp / (imp + wimp) * 100, 1) if imp and wimp else None
    return ai


# ── AI Visibility Score (ai-visibility-report run) ─────────────────────────────
def geo():
    """Score, per language, vs competitors, computed from the run's cells.

    Same formula as the ai-visibility-report headline: 60% share of unbranded answers that name
    the brand + 40% share that cite its domain. Competitors use the SAME formula on the same
    answers (not share of voice as in the PDF), so their bars sit on the donut's 0-100 scale.
    Only finalized months (data JSON exists) are shown, so a half-collected run never leaks.
    """
    if not GEO_RUNS or not GEO_RUNS.exists():
        return None
    runs = [p for p in sorted(GEO_RUNS.glob("*_ai_visibility_*_cells.json"))
            if p.with_name(p.name.replace("_cells", "")).exists()]
    if not runs:
        return None

    def cfg_for(slug):
        cur = json.loads((GEO_RUNS / f"{OWN}_config.json").read_text(encoding="utf-8"))
        if cur.get("period_slug") == slug:
            return cur
        arc = GEO_RUNS / f"{OWN}_config_{slug}.json"
        return json.loads(arc.read_text(encoding="utf-8")) if arc.exists() else cur

    slug_of = lambda p: re.search(r"_(\d{4}-\d{2})_cells", p.name).group(1)
    cfg = cfg_for(slug_of(runs[-1]))
    cells = json.loads(runs[-1].read_text(encoding="utf-8"))
    prompt = {p["id"]: p for p in cfg["prompts"]}
    ok = [c for c in cells if c.get("status") == "measured"]
    ub = [c for c in ok if not prompt[c["prompt_id"]]["branded"]]
    br = [c for c in ok if prompt[c["prompt_id"]]["branded"]]
    order = ("uk", "ru", "en", "de", "pl", "es", "fr")
    present = {p.get("lang") for p in cfg["prompts"] if p.get("lang")}
    langs = [l for l in order if l in present] + sorted(present - set(order))
    lang_of = lambda c: prompt[c["prompt_id"]].get("lang")

    def score(cs, ment, cite):
        n = len(cs)
        m = sum(1 for c in cs if ment(c)); k = sum(1 for c in cs if cite(c))
        return {"score": round(0.6 * m / n * 100 + 0.4 * k / n * 100, 1) if n else None,
                "hit": m, "cited": k, "of": n}

    me_m, me_c = (lambda c: c.get("brand_mention")), (lambda c: c.get("brand_citation"))
    by_lang = {l: score([c for c in ub if lang_of(c) == l], me_m, me_c) for l in langs}

    # every finalized run scored the same way: the trend chart and the "минулий замір" rows
    def run_scores(path):
        rc = cfg_for(slug_of(path))
        pp = {p["id"]: p for p in rc["prompts"]}
        pub = [c for c in json.loads(path.read_text(encoding="utf-8"))
               if c.get("status") == "measured" and not pp[c["prompt_id"]]["branded"]]
        return {"slug": slug_of(path), "at": rc["date_generated"],
                "samePrompts": set(pp) == set(prompt),   # a changed question set breaks the line
                "total": score(pub, me_m, me_c),
                "byLang": {l: score([c for c in pub if pp[c["prompt_id"]].get("lang") == l], me_m, me_c)
                           for l in langs},
                # same formula on the same answers as the "Бал проти конкурентів" board
                "rivals": {comp["name"]: score(
                    pub,
                    lambda c, d=comp["domain"]: d in (c.get("competitor_mentions") or []),
                    lambda c, d=comp["domain"]: d in (c.get("competitor_citations") or []))["score"]
                    for comp in rc.get("competitors", [])}}

    history = [run_scores(p) for p in runs]
    prev = history[-2] if len(history) >= 2 else None

    def short(label):
        m = re.match(r"(.+?)\s*\((.+)\)", label)
        return (m.group(1), m.group(2)) if m else (label, "")

    models = []
    for m in cfg["llms_covered"]:
        mine = [c for c in ub if c["model"] == m["label"]]
        name, ver = short(m["label"])
        models.append({
            "model": name, "version": ver,
            "lang": {l: [sum(1 for c in mine if lang_of(c) == l and me_m(c)),
                         sum(1 for c in mine if lang_of(c) == l)] for l in langs},
            "branded": [sum(1 for c in br if c["model"] == m["label"] and me_m(c)),
                        sum(1 for c in br if c["model"] == m["label"])],
            "cites": sum(1 for c in ub if c["model"] == m["label"] and me_c(c)),
        })

    rivals = [{"name": "Ви", "me": True, **score(ub, me_m, me_c),
               "lang": {l: by_lang[l]["hit"] for l in langs}}]
    for comp in cfg.get("competitors", []):
        d = comp["domain"]
        cm = lambda c, d=d: d in (c.get("competitor_mentions") or [])
        cc = lambda c, d=d: d in (c.get("competitor_citations") or [])
        rivals.append({"name": comp["name"], "me": False, **score(ub, cm, cc),
                       "lang": {l: sum(1 for c in ub if lang_of(c) == l and cm(c)) for l in langs}})
    rivals.sort(key=lambda r: -(r["score"] or 0))

    doms = defaultdict(int)
    for c in ok:
        for d in {s["domain"] for s in c.get("cited_sources") or []}:
            doms[d[4:] if d.startswith("www.") else d] += 1
    sources = sorted(doms.items(), key=lambda kv: (-kv[1], kv[0]))[:10]

    notes = json.loads(GEO_NOTES.read_text(encoding="utf-8")) if GEO_NOTES and GEO_NOTES.exists() else {}
    return {
        "measuredAt": cfg["date_generated"],
        "prompts": len(cfg["prompts"]), "models": len(cfg["llms_covered"]), "answers": len(ok),
        "failed": len(cells) - len(ok),
        "total": score(ub, me_m, me_c), "byLang": by_lang, "langs": langs, "prev": prev,
        "history": history,
        "branded": {"hit": sum(1 for c in br if me_m(c)), "of": len(br)},
        "rivals": rivals, "byModel": models,
        "sources": [[d, n, d == cfg["brand_domain"]] for d, n in sources],
        "notesFor": notes.get("forRun"),
        "actions": notes.get("actions", []),
    }


# ── page chrome from config ────────────────────────────────────────────────────
def brand_css():
    c = CFG.get("colors") or {}
    names = {"accent": "--coral", "accent_deep": "--coral-deep", "accent_soft": "--coral-soft",
             "ink": "--ink", "positive": "--forest", "positive_soft": "--forest-soft"}
    decl = ";".join(f"{names[k]}:{v}" for k, v in c.items() if k in names and v)
    return f"/*__BRAND__*/:root{{{decl}}}/*__/BRAND__*/" if decl else "/*__BRAND__*//*__/BRAND__*/"


def chrome(src, seo):
    e = html.escape
    title = CFG.get("title", "Пошук і LLM")
    src = re.sub(r"<title>[^<]*</title>", f"<title>{e(title)}</title>", src, count=1)
    src = re.sub(r"<h1>[^<]*</h1>", f"<h1>{e(CFG.get('h1', title))}</h1>", src, count=1)
    g = seo["gsc"]
    src = re.sub(r'<p class="eyebrow">[^<]*</p>',
                 f'<p class="eyebrow">{e(CFG.get("brand_name", OWN))} · {e(OWN)} · дані з {g["since"]}'
                 f' · {g["last28"]["clicks"]} кліків за 28 днів · оновлено {seo["builtAt"]}</p>', src, count=1)
    tabs = CFG.get("tabs") or []
    nav = ('<nav class="tabs" aria-label="Репорти">' + "".join(
        f'<a href="{e(t["href"])}"' + (' aria-current="page"' if t.get("current") else "") + f'>{e(t["label"])}</a>'
        for t in tabs) + "</nav>") if tabs else '<nav class="tabs" aria-label="Репорти" hidden></nav>'
    src = re.sub(r'<nav class="tabs".*?</nav>', nav, src, count=1, flags=re.S)
    parts = ["Джерела: Search Console і rank tracking — self-hosted OpenSEO"]
    if seo.get("ai"):
        parts.append("AI-режим Google — ручний експорт звіту «Функції на основі генеративного ШІ» (API його не віддає)")
    if seo.get("geo"):
        parts.append("AI Visibility Score — прогін ai-visibility-report (DataForSEO, живі відповіді моделей)")
    parts.append(f"оновлено {seo['builtAt']}")
    src = re.sub(r"<footer>.*?</footer>", "<footer>" + " · ".join(e(p) for p in parts) + "</footer>",
                 src, count=1, flags=re.S)
    src = re.sub(r"/\*__BRAND__\*/.*?/\*__/BRAND__\*/", lambda m: brand_css(), src, count=1, flags=re.S)
    return src


def main():
    if not PAGE.exists():
        raise SystemExit(f"no page at {PAGE}: copy templates/dashboard.html there first")
    if CFG.get("demo_data"):
        # demo mode: no OpenSEO, no runs; the whole SEO object comes from a JSON file
        seo = json.loads(rel(CFG["demo_data"]).read_text(encoding="utf-8"))
        seo.setdefault("meta", {}).update({"domain": OWN, "brand": CFG.get("brand_name", OWN)})
        src = PAGE.read_text(encoding="utf-8")
        src = re.sub(r"(const SEO = )(.*?)(;\n)", lambda m: m.group(1) + json.dumps(seo, ensure_ascii=False) + m.group(3),
                     src, count=1, flags=re.S)
        PAGE.write_text(chrome(src, seo), encoding="utf-8")
        print("demo page ->", PAGE)
        return
    connect()
    days, gsc_data = search_console()
    seo = {
        "meta": {
            "domain": OWN, "brand": CFG.get("brand_name", OWN),
            "brandQueryRegex": CFG.get("brand_query_regex"),
            "oldBrandRegex": CFG.get("old_brand_regex"),
            "audience": GEO.get("audience"), "geoCountryNote": GEO.get("country_note"),
        },
        "gsc": gsc_data,
        "ai": ai_mode(days),
        "ranks": rank_tracking() if OSEO.get("rank_tracking", True) else None,
        "geo": geo(),
        "builtAt": date.today().isoformat(),
    }
    src = PAGE.read_text(encoding="utf-8")
    pattern = re.compile(r"(const SEO = )(.*?)(;\n)", re.S)
    if not pattern.search(src):
        raise SystemExit(f"{PAGE} has no `const SEO = ...;` line: is it the dashboard template?")
    src = pattern.sub(lambda m: m.group(1) + json.dumps(seo, ensure_ascii=False) + m.group(3), src, count=1)
    PAGE.write_text(chrome(src, seo), encoding="utf-8")

    g, r, a, gv = seo["gsc"], seo["ranks"], seo["ai"], seo["geo"]
    print(f"GSC {g['since']}..{g['until']}: 28 days {g['last28']['clicks']} clicks /"
          f" {g['last28']['imp']} impressions · CTR {g['last28']['ctr']}% · position {g['last28']['pos']}")
    print(f"ranks: {r['top10']} of {len(r['rows'])} keywords in top 10 · AI Overview on {r['aioShare']}%"
          f" · competitors {len(r['competitors'])}" if r else "ranks: no tracker for the own domain, section hidden")
    print(f"AI mode: {a['total']['imp']} impressions, share {a['share']}%" if a else "AI mode: no file, section hidden")
    if gv:
        t = gv["total"]
        print(f"AI Visibility Score {gv['measuredAt']}: {t['score']}/100 · unbranded {t['hit']} of {t['of']} · "
              + ", ".join(f"{l} {v['score']}" for l, v in gv["byLang"].items())
              + f" · branded {gv['branded']['hit']} of {gv['branded']['of']} · failed {gv['failed']}")
        if gv["notesFor"] != gv["measuredAt"]:
            print(f"  ! actions in the notes file are for run {gv['notesFor']}, numbers are {gv['measuredAt']}: rewrite them")
    else:
        print("AI Visibility Score: no finalized run, section hidden")
    print("->", PAGE)


if __name__ == "__main__":
    main()
