"""
03_build_dashboard.py
=====================
Stage 3: bake the clean data into a single self-contained HTML dashboard.

WHY BAKE INSTEAD OF fetch()?
----------------------------
Browsers block `fetch()` on `file://` URLs. A recruiter who downloads one HTML
file and double-clicks it must see a working dashboard with zero setup, so the
row-level data is compressed and injected straight into the file.

COMPRESSION
-----------
8,652 rows x 10 fields as verbose JSON objects would be ~2.5 MB. We
dictionary-encode the repeated strings (city, locality, cuisine) and emit
arrays-of-arrays, which lands around 0.6 MB - small enough to ship in git.

Run:  python scripts/03_build_dashboard.py
"""

from __future__ import annotations

import json
import pathlib

import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
DASH = ROOT / "dashboard"
TEMPLATE = DASH / "_template.html"
OUTPUT = DASH / "zomato_dashboard.html"


def main() -> None:
    fact = pd.read_csv(PROC / "fact_restaurants.csv")
    bridge = pd.read_csv(PROC / "bridge_cuisine.csv")

    india = fact[fact["Country"] == "India"].copy()

    # ---- dictionary encoding -------------------------------------------------
    cities = sorted(india["City"].dropna().unique().tolist())
    city_ix = {c: i for i, c in enumerate(cities)}

    locs = sorted(india["Locality"].dropna().unique().tolist())
    loc_ix = {c: i for i, c in enumerate(locs)}

    b = bridge[bridge["Restaurant ID"].isin(set(india["Restaurant ID"]))]
    cuisines = sorted(b["Cuisine"].dropna().unique().tolist())
    cus_ix = {c: i for i, c in enumerate(cuisines)}
    cus_by_rest: dict[int, list[int]] = {}
    for rid, cname in zip(b["Restaurant ID"], b["Cuisine"]):
        cus_by_rest.setdefault(int(rid), []).append(cus_ix[cname])

    def num(x, nd=None):
        if pd.isna(x):
            return None
        return int(x) if nd is None else round(float(x), nd)

    rows = []
    for _, x in india.iterrows():
        rows.append([
            x["Restaurant Name"],                       # 0 name
            city_ix.get(x["City"], -1),                 # 1 city id
            loc_ix.get(x["Locality"], -1),              # 2 locality id
            num(x["Average Cost for two"]),             # 3 cost (INR, nullable)
            num(x["Aggregate rating"], 1),              # 4 rating (null = unrated)
            int(x["Votes"]),                            # 5 votes
            int(x["Price range"]),                      # 6 price range 1-4
            1 if x["Has Online delivery"] else 0,       # 7 online delivery
            1 if x["Has Table booking"] else 0,         # 8 table booking
            cus_by_rest.get(int(x["Restaurant ID"]), []),  # 9 cuisine ids
        ])

    payload = {
        "cities": cities,
        "localities": locs,
        "cuisines": cuisines,
        "rows": rows,
    }

    # The python-computed KPI reference travels with the file so the dashboard
    # can self-verify its JS maths against the pandas maths (see the footer).
    reference = json.loads((DASH / "kpis.json").read_text())

    tpl = TEMPLATE.read_text()
    html = tpl.replace(
        "/*__DATA__*/",
        "const DATA = " + json.dumps(payload, separators=(",", ":")) + ";\n"
        "const REFERENCE = " + json.dumps(reference["kpi"], separators=(",", ":")) + ";\n"
        "const STATS = " + json.dumps(reference["stats"], separators=(",", ":")) + ";\n"
        "const META = " + json.dumps(reference["meta"], separators=(",", ":")) + ";",
    )
    OUTPUT.write_text(html)
    kb = OUTPUT.stat().st_size / 1024
    print(f"Wrote {OUTPUT}  ({kb:,.0f} KB, {len(rows):,} rows inlined)")
    print(f"  cities={len(cities)} localities={len(locs)} cuisines={len(cuisines)}")


if __name__ == "__main__":
    main()
