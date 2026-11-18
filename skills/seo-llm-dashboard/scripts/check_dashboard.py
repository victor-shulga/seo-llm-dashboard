#!/usr/bin/env python3
"""Self-check of a built dashboard. inject_dashboard.py runs it after every build; also a CLI:

    check_dashboard.py <dashboard.html> [dashboard.config.json]
    check_dashboard.py --selftest

Exit 1 with plain-language reasons when the page is not what the template + data should give.
The fix is never a hand edit of the HTML: rebuild from templates/dashboard.html with the script.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

# every block the page script fills; a missing id = the HTML was edited or is not the template
IDS = ["kpis", "chart", "queries", "pages", "ranks", "aiSec", "geoSec", "geoLangs", "geoModels",
       "geoRivals", "geoSources", "geoActions", "geoDiag", "geoAns", "geoTrend", "mobile-guard"]
BEIGE = ["#F7F5F1", "#E8E6E1", "#EFEDE8", "#D9D6D0", "#6C6A64", "#B9B6AE", "#C9C6BF", "#ECEAE4",
         "#B9B4AA"]   # retired warm-grey interface colours: the design system uses #E4EAF0/#D5DDE6/#55606E/#3D3D3A
FONTS = ("fonts.googleapis.com", "fonts.gstatic.com")


def problems(html: str, cfg: dict | None = None) -> list[str]:
    out = []
    m = re.search(r"const SEO = (.*?);\n", html, re.S)
    if not m:
        return ["у сторінці немає рядка `const SEO = …;`: це не шаблон дашборда. Скопіюйте templates/dashboard.html і зберіть заново"]
    try:
        seo = json.loads(m.group(1))
    except ValueError as e:
        return [f"дані сторінки не читаються як JSON ({e}): зберіть заново скриптом, не правте HTML"]
    code = html[:m.start()] + html[m.end():]            # markup + script, without the data

    for i in IDS:
        if f'id="{i}"' not in code:
            out.append(f"на сторінці бракує блоку #{i}: HTML правили вручну. Скопіюйте свіжий templates/dashboard.html і зберіть заново")
    if re.search(r"\{\{\s*[\w.-]+\s*\}\}|<[A-Z_]{3,}>|YYYY-MM", code):
        out.append("на сторінці лишилися заглушки ({{…}}, <PLACEHOLDER> або YYYY-MM)")
    ext = [u for u in re.findall(r'(?:src|href)\s*=\s*["\'](https?://[^"\']+)', code)
           + re.findall(r"@import\s+url\(['\"]?(https?://[^)'\"]+)", code)
           if not u.startswith(tuple("https://" + f for f in FONTS))]
    if ext:
        out.append(f"сторінка тягне зовнішні файли ({', '.join(sorted(set(ext))[:3])}): вона має бути самодостатньою")
    if re.search(r"\bfetch\(|XMLHttpRequest", code):
        out.append("у сторінці є мережеві запити (fetch): дані мають бути вшиті в файл")
    if "wk.slice(5)" in code or re.search(r"<title>\$\{wk\}", code):
        out.append("графік підписує тижні номерами ISO: у шаблоні має бути дата понеділка (wkDate)")
    beige = [c for c in BEIGE if c.lower() in code.lower()]
    if beige:
        out.append(f"у дизайні заборонені бежеві кольори {', '.join(beige)}: візьміть свіжий шаблон")

    cfg = cfg or {}
    geo_on = bool((cfg.get("geo") or {}).get("run_dir")) or cfg.get("demo_data")
    g = seo.get("geo")
    if geo_on and not g:
        out.append("AI-блоку немає: у теці прогону нема фіналізованого місяця (avr.py finalize)")
    if g:
        for k, what in (("total", "бал AI-видимості"), ("byModel", "моделі"), ("rivals", "конкуренти"),
                        ("sources", "джерела"), ("byPrompt", "питання й відповіді моделей"),
                        ("actions", "рекомендації «Що робити»")):
            if not g.get(k):
                out.append(f"AI-блок без розділу «{what}»"
                           + (": запустіть diagnose.py і recommend.py --write, потім зберіть знову" if k == "actions" else ""))
        if g.get("byPrompt") and not any(m_.get("text") for p in g["byPrompt"] for m_ in p["models"]):
            out.append("у таблиці питань немає жодного тексту відповіді: тека raw/ прогону порожня або не та")
        if g.get("actions") and not all(re.search(r"\d", a.get("what", "")) for a in g["actions"]):
            out.append("є рекомендація без жодної цифри із заміру: перепишіть її через recommend.py")
    if cfg.get("openseo") and not seo.get("gsc"):
        out.append("Search Console підключено в конфігу, але даних немає: перевірте OpenSEO (крок 2)")
    if not cfg.get("openseo") and not cfg.get("demo_data") and (seo.get("gsc") or seo.get("ranks")):
        out.append("на сторінці дані Google, хоча OpenSEO в конфігу немає")
    return out


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    page = pathlib.Path(sys.argv[1])
    cfg = json.loads(pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")) if len(sys.argv) > 2 else None
    bad = problems(page.read_text(encoding="utf-8"), cfg)
    report(bad, page)
    sys.exit(1 if bad else 0)


def report(bad, page):
    if bad:
        print(f"ПЕРЕВІРКА НЕ ПРОЙДЕНА ({page}):")
        for b in bad:
            print("  ✗", b)
        print("Не правте HTML вручну: виправте причину і зберіть сторінку скриптом ще раз.")
    else:
        print(f"перевірка сторінки: ок ({page.name})")


def selftest():
    tpl = (pathlib.Path(__file__).resolve().parent.parent / "templates/dashboard.html").read_text(encoding="utf-8")
    ok_geo = {"total": {"score": 1}, "byModel": [1], "rivals": [1], "sources": [1],
              "byPrompt": [{"models": [{"text": "a"}]}], "actions": [{"what": "0 з 4"}]}
    page = re.sub(r"(const SEO = )(.*?)(;\n)", lambda m: m.group(1) + json.dumps({"geo": ok_geo}, ensure_ascii=False) + m.group(3), tpl, 1, re.S)
    cfg = {"geo": {"run_dir": "x"}}
    assert problems(page, cfg) == [], problems(page, cfg)
    assert any("Що робити" in p for p in problems(page.replace('"actions": [{"what": "0 з 4"}]', '"actions": []'), cfg))
    assert any("#geoModels" in p for p in problems(page.replace('id="geoModels"', 'id="x"'), cfg))
    assert any("бежеві" in p for p in problems(page.replace("</style>", ".x{color:#C9C6BF}</style>", 1), cfg))
    assert any("зовнішні" in p for p in problems(page.replace("<header>", '<script src="https://cdn.example/x.js"></script><header>', 1), cfg))
    assert any("ISO" in p for p in problems(page.replace("${wkDate(wk)}</text>", "${wk.slice(5)}</text>"), cfg))
    assert any("Search Console" in p for p in problems(page, {**cfg, "openseo": {"project_id": "p"}}))
    print("selftest ok")


if __name__ == "__main__":
    main()
