#!/usr/bin/env python3
"""Recommendations for «Що робити» after every measurement, each tied to a number from the run.

    recommend.py <dashboard.config.json> [--write]
    recommend.py --selftest

Reads, all local and free:
  - the run folder (geo.run_dir): the newest finalized month, its *_diagnosis.json (diagnose.py),
    and sections.opportunities of the data JSON when a report already wrote them;
  - the built dashboard page (`page` in the config): its inlined Search Console and rank data, so
    search recommendations appear only when Google is connected.

Prints the actions; with --write puts them into geo.notes_file (default seo_geo.json next to the
config), the file the page shows as «Що робити». Claude may then reword a row, never its numbers.
Run inject_dashboard.py before (fresh search data) and after (show the rows).
"""
from __future__ import annotations

import collections
import json
import pathlib
import re
import sys

EFFORT = {"Low": "тиждень", "Medium": "2–6 тижнів", "High": "квартал"}
PRIO = {"High": "високий", "Medium": "середній", "Low": "низький"}
RANK = {"високий": 0, "середній": 1, "низький": 2}
MAX_AI, MAX_SEARCH = 5, 3


def act(title, what, effort, prio):
    return {"title": title, "what": what, "effort": effort, "prio": prio}


def top(items, n=3):
    return ", ".join(f"{k} {v}" for k, v in items[:n])


# ── AI part: from diagnose.py output ───────────────────────────────────────────
def ai_actions(diag, rival_name):
    """Deterministic rows from the diagnosis: old brand, topics without a page, weak pages, directories, lists."""
    out = []
    P = diag["prompts"]
    measured = sum(p["measured"] for p in P)
    old = diag.get("old_brand_answers") or []
    contest = sorted({s["domain"] for s in diag["sources"] if s["type"] == "CONTEST"})
    if old or contest:
        out.append(act("Прибрати старий бренд з відповідей",
                       f"старий бренд у {len(old)} відповідях із {measured}"
                       + (f"; застарілі дані про вас на: {', '.join(contest[:4])}" if contest else "")
                       + ". Виправити ці сторінки й профілі, тоді повторний замір покаже ефект",
                       "тиждень", "високий"))

    by_topic = collections.defaultdict(list)
    for p in P:
        by_topic[p["topic"]].append(p)

    def topic_row(rows):
        named = sum(r["named"] for r in rows)
        of = sum(r["measured"] for r in rows)
        rivals = collections.Counter()
        for r in rows:
            for d, n in r["rivals"]:
                rivals[rival_name.get(d, d)] += n
        return named, of, rivals.most_common(2)

    missing = [(t, rs) for t, rs in by_topic.items() if any(r["reason"] == "missing_page" for r in rs)]
    for t, rs in sorted(missing, key=lambda x: topic_row(x[1])[0] / max(topic_row(x[1])[1], 1)):
        named, of, rv = topic_row(rs)
        langs = sorted({r["lang"] for r in rs if r["reason"] == "missing_page" and r["lang"]})
        out.append(act(f"Сторінка під тему «{t}»",
                       f"названо {named} з {of}, своєї сторінки на тему нема"
                       + (f" ({', '.join(langs)})" if langs else "")
                       + (f"; замість вас: {top(rv)}" if rv else "")
                       + ". Сторінка-відповідь з іменем бренду в першому абзаці і кейсом із цифрами",
                       "2–6 тижнів", "високий" if named == 0 else "середній"))

    weak = [(t, rs) for t, rs in by_topic.items()
            if t not in dict(missing) and any(r["reason"] == "weak_page" for r in rs)]
    for t, rs in weak:
        named, of, rv = topic_row(rs)
        page = next((r["own_page"] for r in rs if r["own_page"]), None)
        idx = next((r["own_page_index"] for r in rs if r["own_page"]), None)
        out.append(act(f"Дописати сторінку «{t}»",
                       f"названо {named} з {of}, сторінка є"
                       + (f" ({re.sub(r'^https?://[^/]+', '', page) or '/'}"
                          + (", не в індексі Google" if idx == "not_indexed" else "") + ")" if page else "")
                       + (f"; замість вас: {top(rv)}" if rv else "")
                       + ". Ім'я бренду в першому абзаці, пряма відповідь на питання, докази",
                       "2–6 тижнів", "середній"))

    claim = [d for d in diag["domains"] if d["type"] == "CLAIM"]
    if claim:
        out.append(act("Профілі в каталогах, які цитують моделі",
                       "у програних відповідях: " + ", ".join(
                           f"{d['domain']} {d['lost_cells']} відп. ({d['prompts']} питань)" for d in claim[:4])
                       + ". Створити або заповнити профілі, додати відгуки й кейси",
                       "тиждень", "високий" if claim[0]["prompts"] >= 5 else "середній"))

    earn = [d for d in diag["domains"] if d["type"] == "EARN"]
    if earn:
        out.append(act("Потрапити в списки, з яких моделі збирають відповіді",
                       "найчастіші сторонні джерела в програних відповідях: " + ", ".join(
                           f"{d['domain']} {d['lost_cells']}" for d in earn[:4])
                       + ". Запропонувати авторам матеріал чи кейс, гостьовий текст, участь у рейтингу",
                       "квартал", "середній"))
    out.sort(key=lambda a: RANK[a["prio"]])
    return out[:MAX_AI]


def report_actions(data):
    """Rows a report already wrote (sections.opportunities of the data JSON), same grounding rule."""
    rows = ((data.get("sections") or {}).get("opportunities") or {}).get("actions") or []
    out = []
    for a in rows:
        e = (a.get("effort") or "").split(" ")[0]
        what = a.get("why", "")
        if a.get("actions"):
            what += " " + re.sub(r"\s*\d\)\s*", " ", a["actions"]).strip()
        out.append(act(a["title"], what.strip(), EFFORT.get(e, a.get("effort", "")),
                       PRIO.get(a.get("priority"), "середній")))
    return out[:MAX_AI]


# ── search part: from the data inlined in the built page ───────────────────────
def search_actions(seo, brand_rx=None):
    """Only when Search Console / rank data exist. Thresholds keep it to rows a number can defend."""
    out = []
    g = seo.get("gsc") or {}
    brand = re.compile(brand_rx, re.I) if brand_rx else None
    # [query, clicks, impressions, ctr %, position]
    low_ctr = [q for q in g.get("queries") or []
               if q[2] >= 50 and q[4] <= 10 and q[3] < 2 and not (brand and brand.search(q[0]))]
    for q in sorted(low_ctr, key=lambda q: -q[2])[:2]:
        out.append(act(f"Заголовок і опис під запит «{q[0]}»",
                       f"{q[2]} показів за 28 днів, позиція {q[4]}, CTR {q[3]}% ({q[1]} кліків). "
                       "Переписати title і description сторінки з цим запитом, щоб відповідали на питання",
                       "тиждень", "середній"))
    r = seo.get("ranks") or {}
    # [keyword, pos, prev, url, aio, volume, [competitor positions]]
    near = [k for k in r.get("rows") or [] if k[1] and 11 <= k[1] <= 20]
    for k in sorted(near, key=lambda k: (k[1], -(k[5] or 0)))[:MAX_SEARCH - len(out)]:
        better = [f"{d} {p}" for d, p in zip(r.get("competitors") or [], k[6]) if p and p < k[1]]
        out.append(act(f"Довести «{k[0]}» до топ-10",
                       f"позиція {k[1]}" + (f" (було {k[2]})" if k[2] else "")
                       + (f", пошуковий попит {k[5]}/міс" if k[5] else "")
                       + (f"; конкуренти вище: {', '.join(better[:3])}" if better else "")
                       + ". Посилити сторінку " + (k[3] or "під цей запит") + ": внутрішні посилання, повніша відповідь",
                       "2–6 тижнів", "середній"))
    return out[:MAX_SEARCH]


def page_data(page):
    if not page.exists():
        return {}
    m = re.search(r"const SEO = (.*?);\n", page.read_text(encoding="utf-8"), re.S)
    try:
        return json.loads(m.group(1)) if m else {}
    except ValueError:
        return {}


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    cfg_path = pathlib.Path(sys.argv[1]).expanduser().resolve()
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    base = cfg_path.parent
    geo = cfg.get("geo") or {}
    run = (base / geo["run_dir"]).resolve() if geo.get("run_dir") else None
    actions, run_date = [], None
    if run and run.exists():
        dom = cfg["domain"]
        rc = json.loads((run / f"{dom}_config.json").read_text(encoding="utf-8"))
        finals = [p for p in sorted(run.glob(f"{dom}_ai_visibility_*.json"))
                  if re.search(r"_\d{4}-\d{2}\.json$", p.name)]
        if not finals:
            raise SystemExit("no finalized month in the run folder: run avr.py finalize first")
        data = json.loads(finals[-1].read_text(encoding="utf-8"))
        slug = re.search(r"_(\d{4}-\d{2})\.json$", finals[-1].name).group(1)
        arc = run / f"{dom}_config_{slug}.json"
        run_date = (json.loads(arc.read_text()) if arc.exists() and rc.get("period_slug") != slug else rc)["date_generated"]
        actions = report_actions(data)
        if not actions:
            diag = run / f"{dom}_ai_visibility_{slug}_diagnosis.json"
            if not diag.exists():
                raise SystemExit(f"no {diag.name}: run `python3 <skill-dir>/scripts/diagnose.py {dom}_config.json` "
                                 "in the run folder first (free)")
            actions = ai_actions(json.loads(diag.read_text(encoding="utf-8")),
                                 {c["domain"]: c["name"] for c in rc.get("competitors", [])})
    seo = page_data((base / cfg.get("page", "dashboard.html")).resolve())
    actions += search_actions(seo, cfg.get("brand_query_regex"))
    for a in actions:
        print(f"[{a['prio']}] {a['title']} · {a['effort']}\n    {a['what']}")
    if not actions:
        print("no recommendation can be grounded in numbers yet")
    if "--write" in sys.argv:
        notes = (base / geo.get("notes_file", "seo_geo.json")).resolve()
        old = json.loads(notes.read_text(encoding="utf-8")) if notes.exists() else {}
        notes.write_text(json.dumps({
            "forRun": run_date, "generated": True,
            "note": old.get("note") or "Згенеровано recommend.py після заміру; формулювання можна правити, цифри ні.",
            "actions": actions}, ensure_ascii=False, indent=1), encoding="utf-8")
        print("->", notes, "" if geo.get("notes_file") else "(add \"notes_file\": \"seo_geo.json\" to geo in the config)")


def selftest():
    diag = {"old_brand_answers": ["p2__gemini"], "sources": [{"domain": "old.example", "type": "CONTEST"}],
            "prompts": [
                {"topic": "a", "lang": "uk", "reason": "missing_page", "named": 0, "measured": 4,
                 "rivals": [["rival.example", 3]], "own_page": None, "own_page_index": None},
                {"topic": "b", "lang": "uk", "reason": "weak_page", "named": 1, "measured": 4, "rivals": [],
                 "own_page": "https://me.example/b", "own_page_index": "not_indexed"},
                {"topic": "c", "lang": "en", "reason": "won", "named": 4, "measured": 4, "rivals": [],
                 "own_page": "https://me.example/c", "own_page_index": "indexed"}],
            "domains": [{"domain": "clutch.co", "type": "CLAIM", "lost_cells": 9, "prompts": 6},
                        {"domain": "blog.example", "type": "EARN", "lost_cells": 4, "prompts": 2}]}
    a = ai_actions(diag, {"rival.example": "Rival"})
    t = [x["title"] for x in a]
    assert t[0] == "Прибрати старий бренд з відповідей" and "1 відповідях із 12" in a[0]["what"]
    assert "Сторінка під тему «a»" in t and "Rival 3" in a[t.index("Сторінка під тему «a»")]["what"]
    assert "не в індексі Google" in a[t.index("Дописати сторінку «b»")]["what"]
    assert not any("«c»" in x for x in t), "a won topic gets no action"
    assert all(re.search(r"\d", x["what"]) for x in a), "every row carries a number"
    seo = {"gsc": {"queries": [["q1", 3, 400, 0.8, 6.2], ["brand q", 1, 900, 0.1, 2], ["q2", 9, 30, 1, 4]]},
           "ranks": {"competitors": ["r.example"], "rows": [["k1", 14, 18, "me.example/k", False, 90, [8]],
                                                            ["k2", 3, 3, "", False, 10, [1]]]}}
    s = search_actions(seo, "brand")
    assert [x["title"] for x in s] == ["Заголовок і опис під запит «q1»", "Довести «k1» до топ-10"], s
    assert "r.example 8" in s[1]["what"]
    assert search_actions({}) == [], "no Google data, no search rows"
    r = report_actions({"sections": {"opportunities": {"actions": [
        {"title": "T", "why": "0 of 21.", "actions": "1) a.  2) b.", "effort": "Medium (2-6 weeks)", "priority": "High"}]}}})
    assert r[0]["effort"] == "2–6 тижнів" and r[0]["prio"] == "високий" and "a." in r[0]["what"]
    print("selftest ok")


if __name__ == "__main__":
    main()
