#!/usr/bin/env python3
"""Why each unbranded prompt was lost, and what to do about it. Costs nothing (no LLM, no paid API).
Vendored from the ai-visibility-report skill; feeds «Чому не назвали» on the page and recommend.py.

    diagnose.py <config.json> [--slug 2026-11] [--no-fetch]
    diagnose.py --selftest

Reads the month's cells + raw answers from the run folder, fetches the site's sitemap pages and
the third-party pages the assistants cited in lost answers (cached in _diagnose_cache.json), and
writes <stem>_diagnosis.json next to the cells.

Optional <domain>_diagnose.json in the run folder:
    {"topics": {"<keyword from config>": "<regex a dedicated page must have in title/h1>"},
     "old_brand_regex": "...", "claim_domains": ["..."]}
_index_status.json ({url: "indexed" | "not_indexed"}), filled from the gsc MCP, is optional too;
without it indexing is reported as not checked, never as fine.
"""
import collections
import json
import os
import re
import sys
import urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Safari/605.1.15"
CLAIM = {"clutch.co", "goodfirms.co", "designrush.com", "themanifest.com", "upwork.com", "g2.com",
         "crunchbase.com", "sortlist.com", "it-rating.ua", "itprofiles.com", "techbehemoths.com"}
BLOCKED = {"linkedin.com", "facebook.com", "instagram.com", "x.com", "reddit.com", "t.me"}
ACTION = {"OWN": "правити власну сторінку", "CLAIM": "створити або заповнити профіль",
          "EARN": "отримати згадку на цій сторінці", "CONTEST": "виправити застарілі дані",
          "RIVAL": "сайт конкурента: відповісти власною сторінкою-порівнянням",
          "HAVE": "вас уже названо: нічого робити не треба"}


def clean_page(page):
    return re.sub(r"[?&]utm_[^&#]*", "", page or "/") or "/"


def source_type(domain, page, cfg, claim):
    """OWN/CLAIM/RIVAL/EARN by address alone. HAVE and CONTEST need the page text, see page_verdict."""
    if domain == cfg["brand_domain"]:
        return "OWN"
    if domain in {c["domain"] for c in cfg.get("competitors", [])}:
        return "RIVAL"
    if domain in claim or (domain == "linkedin.com" and re.match(r"/(in|company)/", page or "")):
        return "CLAIM"
    return "EARN"


def page_verdict(kind, text, brand_rx, old_rx):
    """Refine the type once the page was read. text=None means it could not be read: keep the type."""
    if text is None or kind in ("OWN", "RIVAL"):
        return kind
    if old_rx and re.search(old_rx, text, re.I):
        return "CONTEST"
    return "HAVE" if re.search(brand_rx, text, re.I) else kind


def cell_state(c):
    if c.get("status") != "measured":
        return "not_measured"
    if c["brand_mention"] and c["brand_citation"]:
        return "won"
    if c["brand_mention"]:
        return "named_no_source"
    if c["brand_citation"]:
        return "cited_not_named"
    return "lost_to_tracked" if c["competitor_mentions"] else "lost_open"


def prompt_reason(states, page, old_brand=0):
    """One cause per prompt, the most fixable first. page: dedicated page in the prompt's language or None.
    old_brand: answers that name the old brand instead of the person, so the regex counts them as lost."""
    live = [s for s in states if s != "not_measured"]
    if not live:
        return "not_measured"
    if all(s in ("won", "named_no_source") for s in live):
        return "won"
    if old_brand:
        return "old_brand"
    if any(s in ("won", "named_no_source") for s in live):
        return "partial"       # some models already name you: the gap is per model
    if "cited_not_named" in live:
        return "weak_page"     # the page is read but the name does not reach the answer
    return "weak_page" if page else "missing_page"


def fetch(url, cache):
    if url in cache:
        return cache[url]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=20) as r:
            if "html" not in (r.headers.get("Content-Type") or "") or r.status != 200:
                raise ValueError(r.headers.get("Content-Type"))
            raw = r.read(1_500_000).decode("utf-8", "replace")
        title = " ".join(re.findall(r"<(?:title|h1)[^>]*>(.*?)</(?:title|h1)>", raw, re.I | re.S))
        lang = re.search(r"<html[^>]*\blang=[\"']?([a-z]{2})", raw, re.I)
        body = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", raw, flags=re.I | re.S)
        cache[url] = {"title": re.sub(r"<[^>]+>|\s+", " ", title).strip()[:300],
                      "lang": lang.group(1).lower() if lang else None,
                      "text": re.sub(r"<[^>]+>|\s+", " ", body)[:200_000]}
    except Exception as e:      # a page we could not read stays "not checked", it is never counted as absent
        cache[url] = {"error": str(e)[:120]}
    return cache[url]


def own_pages(cfg, cache):
    r = fetch_raw(f"https://{cfg['brand_domain']}/sitemap.xml")
    pages = []
    for u in re.findall(r"<loc>([^<]+)", r):
        p = fetch(u, cache)
        if not p.get("error"):
            pages.append({"url": u, "title": p["title"], "lang": p["lang"]})
    return pages


def fetch_raw(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def diagnose(cfg, cells, prev, raw_text, pages, read_page, extra, index_status):
    claim = CLAIM | set(extra.get("claim_domains", []))
    old_rx = extra.get("old_brand_regex")
    topics = extra.get("topics", {})
    unknown = set(topics) - {p["keyword"] for p in cfg["prompts"]}
    if unknown:     # a misspelt key would silently turn the whole topic into "missing page"
        raise SystemExit(f"topics not in config keywords: {sorted(unknown)}")
    skip = extra.get("page_exclude")
    pages = [g for g in pages if not (skip and re.search(skip, g["url"]))]
    by_prompt = collections.defaultdict(list)
    for c in cells:
        by_prompt[c["prompt_id"]].append(c)
    prev_named = collections.Counter(c["prompt_id"] for c in prev if c.get("brand_mention"))
    old_unnamed = [k for k, t in raw_text.items() if old_rx and re.search(old_rx, t, re.I)
                   and not re.search(cfg["brand_pattern"], t, re.I)]
    sources = {}
    rows = []
    for p in cfg["prompts"]:
        if p.get("branded"):
            continue
        cs = by_prompt.get(p["id"], [])
        rx = topics.get(p["keyword"])
        same = sorted((g for g in pages if rx and re.search(rx, g["title"], re.I)),
                      key=lambda g: -g["url"].rstrip("/").count("/"))
        page = next((g for g in same if g["lang"] == p.get("lang")), None)
        states = [cell_state(c) for c in cs]
        old_here = [k for k in old_unnamed if k.startswith(p["id"] + "__")]
        reason = prompt_reason(states, page, len(old_here))
        rivals = collections.Counter(d for c in cs for d in c.get("competitor_mentions", []))
        lost = [c for c in cs if c.get("status") == "measured" and not c["brand_mention"]]
        cited = collections.Counter()
        for c in lost:
            for s in {(x["domain"], clean_page(x["page"])) for x in c.get("cited_sources", [])}:
                cited[s] += 1
                e = sources.setdefault(s, {"domain": s[0], "page": s[1], "lost_cells": 0, "prompts": set()})
                e["lost_cells"] += 1
                e["prompts"].add(p["id"])
        rows.append({
            "id": p["id"], "lang": p.get("lang"), "topic": p["keyword"], "text": p["text"],
            "reason": reason, "cells": dict(collections.Counter(states)),
            "named": sum(1 for c in cs if c.get("brand_mention")), "measured": sum(s != "not_measured" for s in states),
            "named_prev": prev_named[p["id"]], "old_brand_cells": len(old_here),
            "named_by": sorted(c["model"].split(" ")[0] for c in cs if c.get("brand_mention")),
            "rivals": rivals.most_common(5),
            "own_page": page["url"] if page else None,
            "own_page_other_lang": [g["url"] for g in same if g["lang"] != p.get("lang")][:2],
            "own_page_index": (index_status.get(page["url"], "not_checked") if page else None),
            "top_sources": [{"domain": d, "page": g, "lost_cells": n} for (d, g), n in cited.most_common(5)],
        })
    out = []
    for e in sources.values():
        kind = source_type(e["domain"], e["page"], cfg, claim)
        text = None if e["domain"] in BLOCKED else read_page(f"https://{e['domain']}{e['page']}")
        final = page_verdict(kind, text, cfg["brand_pattern"], old_rx)
        rivals_there = [c["name"] for c in cfg.get("competitors", []) if text and re.search(c["pattern"], text, re.I)]
        out.append({"domain": e["domain"], "page": e["page"], "lost_cells": e["lost_cells"],
                    "prompts": sorted(e["prompts"], key=lambda x: int(x[1:])), "type": final,
                    "page_read": text is not None, "rivals_on_page": rivals_there,
                    "action": ACTION[final]})
    out.sort(key=lambda s: (-s["lost_cells"], s["domain"]))
    domains = collections.defaultdict(lambda: {"lost_cells": 0, "pages": 0, "types": collections.Counter(), "prompts": set()})
    for s in out:
        d = domains[s["domain"]]
        d["lost_cells"] += s["lost_cells"]
        d["pages"] += 1
        d["types"][s["type"]] += 1
        d["prompts"].update(s["prompts"])
    dom_rows = [{"domain": k, "lost_cells": v["lost_cells"], "pages": v["pages"], "type": v["types"].most_common(1)[0][0],
                 "prompts": len(v["prompts"])} for k, v in domains.items()]
    dom_rows.sort(key=lambda s: (-s["prompts"], -s["lost_cells"], s["domain"]))
    wrong = []
    if old_rx:
        wrong = sorted(k for k, t in raw_text.items() if re.search(old_rx, t, re.I))
    return {
        "period": cfg["period_slug"], "prompts": rows, "sources": out, "domains": dom_rows,
        "old_brand_answers": wrong,
        "summary": {
            "reasons": dict(collections.Counter(r["reason"] for r in rows)),
            "source_types": dict(collections.Counter(s["type"] for s in out)),
            "pages_not_read": sum(not s["page_read"] for s in out), "pages_total": len(out),
            "named": sum(r["named"] for r in rows), "measured": sum(r["measured"] for r in rows),
            "index_checked": bool(index_status),
        },
    }


def selftest():
    cfg = {"brand_domain": "me.com", "brand_pattern": r"ivan petrenko", "period_slug": "2026-11",
           "competitors": [{"name": "R", "domain": "rival.com", "pattern": r"\brival\b"}],
           "prompts": [{"id": "p1", "keyword": "cro", "lang": "uk", "text": "q1"},
                       {"id": "p2", "keyword": "gtm", "lang": "uk", "text": "q2"},
                       {"id": "p3", "keyword": "gtm", "lang": "en", "text": "q3"},
                       {"id": "p4", "keyword": "cro", "lang": "uk", "text": "q4", "branded": True}]}
    def cell(pid, m, cite=False, rivals=(), src=(), status="measured", model="ChatGPT (x)"):
        return {"prompt_id": pid, "model": model, "status": status, "brand_mention": m, "brand_citation": cite,
                "competitor_mentions": list(rivals), "cited_sources": [{"domain": d, "page": g} for d, g in src]}
    cells = [cell("p1", True, True), cell("p1", False, False, model="Claude (y)"),
             cell("p2", False, False, ["rival.com"], [("clutch.co", "/ua"), ("blog.ua", "/top"), ("old.ua", "/a"),
                                                       ("rival.com", "/"), ("linkedin.com", "/in/x"), ("fan.ua", "/b")]),
             cell("p3", False, True), cell("p4", True, True)]
    pages = [{"url": "https://me.com/gtm", "title": "GTM system", "lang": "en"}]
    texts = {"https://blog.ua/top": "top: rival", "https://old.ua/a": "Ivan Petrenko, founder of OldCo",
             "https://fan.ua/b": "ivan petrenko helps", "https://clutch.co/ua": "list"}
    d = diagnose(cfg, cells, [cell("p1", True, True), cell("p1", True, True, model="Claude (y)")], {"p2__x": "OldCo here"},
                 pages, texts.get, {"topics": {"gtm": "gtm"}, "old_brand_regex": "oldco"}, {})
    r = {x["id"]: x for x in d["prompts"]}
    assert set(r) == {"p1", "p2", "p3"}, "branded prompts stay out"
    assert r["p1"]["reason"] == "partial" and r["p1"]["named_prev"] == 2
    assert r["p2"]["own_page_other_lang"] == ["https://me.com/gtm"]
    assert r["p3"]["reason"] == "weak_page" and r["p3"]["own_page_index"] == "not_checked"
    t = {s["domain"]: s for s in d["sources"]}
    assert t["clutch.co"]["type"] == "CLAIM" and t["blog.ua"]["type"] == "EARN" and t["rival.com"]["type"] == "RIVAL"
    assert t["old.ua"]["type"] == "CONTEST" and t["fan.ua"]["type"] == "HAVE"
    assert t["linkedin.com"]["type"] == "CLAIM" and not t["linkedin.com"]["page_read"], "unread stays unread"
    assert d["old_brand_answers"] == ["p2__x"]
    assert r["p2"]["reason"] == "old_brand" and r["p2"]["old_brand_cells"] == 1
    d2 = diagnose(cfg, cells, [], {"p2__x": "OldCo, Ivan Petrenko"}, pages, texts.get, {"topics": {"gtm": "gtm"}, "old_brand_regex": "oldco"}, {})
    assert {x["id"]: x for x in d2["prompts"]}["p2"]["reason"] == "missing_page", "name present: not an old-brand loss"
    assert cell_state(cell("p1", False, status="not_measured")) == "not_measured"
    assert prompt_reason(["not_measured"], None) == "not_measured"
    print("selftest ok")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    cfg_path = os.path.abspath(sys.argv[1])
    run = os.path.dirname(cfg_path)
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    slug = sys.argv[sys.argv.index("--slug") + 1] if "--slug" in sys.argv else cfg["period_slug"]
    no_fetch = "--no-fetch" in sys.argv
    dom = cfg["brand_domain"]
    cfg["period_slug"] = slug
    cells_of = lambda s: os.path.join(run, f"{dom}_ai_visibility_{s}_cells.json")
    cells = json.load(open(cells_of(slug), encoding="utf-8"))
    months = sorted(re.search(r"_(\d{4}-\d{2})_cells", f).group(1) for f in os.listdir(run) if f.endswith("_cells.json"))
    earlier = [m for m in months if m < slug]
    prev = json.load(open(cells_of(earlier[-1]), encoding="utf-8")) if earlier else []
    raw_dir = os.path.join(run, "raw" if slug == json.load(open(cfg_path))["period_slug"] else f"raw_{slug}")
    raw_text = {}
    for f in os.listdir(raw_dir):
        a = json.load(open(os.path.join(raw_dir, f), encoding="utf-8"))
        if a.get("status") == "measured":
            raw_text[f[:-5]] = a["text"]
    load = lambda name: json.load(open(os.path.join(run, name), encoding="utf-8")) if os.path.exists(os.path.join(run, name)) else {}
    extra = load(f"{dom}_diagnose.json")
    index_status = load("_index_status.json")
    cache = load("_diagnose_cache.json")
    pages = [] if no_fetch else own_pages(cfg, cache)

    def read_page(url):
        if no_fetch and url not in cache:
            return None
        return fetch(url, cache).get("text")
    result = diagnose(cfg, cells, prev, raw_text, pages, read_page, extra, index_status)
    result["compared_with"] = earlier[-1] if earlier else None
    json.dump(cache, open(os.path.join(run, "_diagnose_cache.json"), "w", encoding="utf-8"), ensure_ascii=False)
    path = os.path.join(run, f"{dom}_ai_visibility_{slug}_diagnosis.json")
    json.dump(result, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(path)
    print(json.dumps(result["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()
