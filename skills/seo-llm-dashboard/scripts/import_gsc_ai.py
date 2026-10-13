#!/usr/bin/env python3
"""Перетворює експорт звіту Search Console «Функції на основі генеративного ШІ» у scripts/seo_ai.json.

Навіщо окремий крок: AI-режим Google НЕ віддається через Search Analytics API — ні окремим
`type`, ні через `searchAppearance` (перевірено: обидва порожні / відхилені). Єдине джерело —
кнопка ЕКСПОРТУВАТИ в самому звіті.

Як користуватись:
  1. Search Console -> Ефективність -> Функції на основі генеративного ШІ -> період 3 місяці;
  2. ЕКСПОРТУВАТИ -> Завантажити CSV (буде ZIP) або Google Таблиці -> CSV;
  3. python3 import_gsc_ai.py ~/Downloads/<файл>.zip [шлях/до/seo_ai.json]
  4. python3 inject_dashboard.py <config> і деплой сторінки

Заголовки в експорті локалізовані під мову інтерфейсу (ru/uk/en), тому колонки шукаються
за ключовими словами, а не за точною назвою.
"""
from __future__ import annotations

import csv
import io
import json
import pathlib
import re
import sys
import zipfile
from datetime import date

OUT = pathlib.Path(sys.argv[2]).expanduser() if len(sys.argv) > 2 else pathlib.Path(__file__).resolve().parent / "seo_ai.json"

# ключове слово в назві файлу всередині ZIP -> ключ у seo_ai.json
SHEETS = {
    "days": ("дат", "дни", "date", "дні"),
    "pages": ("страниц", "page", "сторінк"),
    "countries": ("стран", "countr", "краї"),
    "devices": ("устройств", "device", "пристро"),
}
CLICKS = ("клик", "клік", "click")
IMPS = ("показ", "impression")
CTR = ("ctr",)
POS = ("позиц", "position")


def _num(s):
    if s is None:
        return None
    s = s.strip().replace(" ", "").replace(" ", "").replace(",", ".").rstrip("%")
    if not s:
        return None
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return None


def _col(header, words):
    for i, h in enumerate(header):
        low = h.lower()
        if any(w in low for w in words):
            return i
    return None


def parse_sheet(text):
    """[[ключ, кліки, покази, ctr, позиція], ...] — відсутні метрики лишаються None."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return []
    head = rows[0]
    ic, ii, ict, ip = _col(head, CLICKS), _col(head, IMPS), _col(head, CTR), _col(head, POS)
    out = []
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        pick = lambda i: _num(r[i]) if i is not None and i < len(r) else None
        out.append([r[0].strip(), pick(ic), pick(ii), pick(ict), pick(ip)])
    return out


def load(path: pathlib.Path):
    """ZIP з експорту, тека з CSV або один CSV -> {ключ: [рядки]}."""
    files = {}
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.lower().endswith(".csv"):
                    files[name] = z.read(name).decode("utf-8-sig")
    elif path.is_dir():
        for f in sorted(path.glob("*.csv")):
            files[f.name] = f.read_text(encoding="utf-8-sig")
    else:
        files[path.name] = path.read_text(encoding="utf-8-sig")

    got = {}
    for key, words in SHEETS.items():
        for name, text in files.items():
            low = name.lower()
            if any(w in low for w in words):
                got[key] = parse_sheet(text)
                break
    if not got:
        # один CSV без впізнаваної назви: якщо перша колонка дати — це ряд по днях
        only = parse_sheet(next(iter(files.values())))
        key = "days" if only and re.match(r"\d{4}-\d{2}-\d{2}", only[0][0]) else "pages"
        got[key] = only
    return got


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    src = pathlib.Path(sys.argv[1]).expanduser()
    if not src.exists():
        raise SystemExit(f"немає файлу: {src}")
    got = load(src)

    days = sorted(got.get("days", []), key=lambda r: r[0])
    prev = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}

    def total(idx):
        vals = [r[idx] for r in days if r[idx] is not None]
        return sum(vals) if vals else None

    clicks, imps = total(1), total(2)
    data = {
        "measuredAt": date.today().isoformat(),
        "since": days[0][0] if days else prev.get("since"),
        "until": days[-1][0] if days else prev.get("until"),
        "label": prev.get("label", "3 місяці"),
        "total": {
            "clicks": clicks,
            "imp": imps if imps is not None else prev.get("total", {}).get("imp"),
            "ctr": round(clicks / imps * 100, 1) if clicks and imps else None,
            "pos": None,
        },
        "days": [[r[0], r[1], r[2]] for r in days],
        "pages": [[r[0], r[1], r[2]] for r in got.get("pages", [])],
        "countries": [[r[0], r[1], r[2]] for r in got.get("countries", [])],
        "devices": [[r[0], r[1], r[2]] for r in got.get("devices", [])],
    }
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"AI-режим {data['since']}..{data['until']}: покази {data['total']['imp']} ·"
          f" кліки {data['total']['clicks']} · днів {len(data['days'])} ·"
          f" сторінок {len(data['pages'])} · країн {len(data['countries'])}")
    print("->", OUT)


if __name__ == "__main__":
    main()
