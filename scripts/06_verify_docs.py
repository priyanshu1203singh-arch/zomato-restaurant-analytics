"""
06_verify_docs.py
=================
Stage 5: assert that every headline figure quoted in the prose deliverables
matches `dashboard/kpis.json`.

Stage 4 checks that the *dashboard* agrees with the pipeline. This stage checks
that the *documentation* does too — including the Power BI guide, which is
hand-written and therefore the one file that can drift.

Run:  python scripts/06_verify_docs.py
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
K = json.loads((ROOT / "dashboard" / "kpis.json").read_text())
kpi, st, meta = K["kpi"], K["stats"], K["meta"]

README = (ROOT / "README.md").read_text()
PREP = (ROOT / "docs" / "INTERVIEW_PREP.md").read_text()
PBI = (ROOT / "docs" / "POWERBI_GUIDE.md").read_text()

results: list[tuple[str, bool, str]] = []


def expect(label: str, needle: str, *docs_and_names) -> None:
    for doc, name in docs_and_names:
        ok = needle in doc
        results.append((f"{label} in {name}", ok, f"looked for {needle!r}"))


R = (README, "README.md")
P = (PREP, "INTERVIEW_PREP.md")
B = (PBI, "POWERBI_GUIDE.md")

expect("total restaurants (India)", f"{kpi['total_restaurants']:,}", R, P, B)
expect("total restaurants (global)", f"{meta['rows_raw']:,}", R, P, B)
expect("cities covered", str(kpi["cities_covered"]), R, P, B)
expect("localities covered", str(kpi["localities_covered"]), R, P, B)
expect("avg cost for two", f"₹{kpi['avg_cost_for_two']:,.0f}", R, P, B)
expect("median cost for two", f"₹{kpi['median_cost_for_two']:,.0f}", R, P, B)
expect("p90 cost for two", f"₹{kpi['p90_cost_for_two']:,.0f}", R, P, B)
expect("avg rating", f"{kpi['avg_rating']:.2f}", R, P, B)
expect("naive avg rating", f"{kpi['avg_rating_if_zeros_kept']:.2f}", R, P, B)
expect("not-rated pct", f"{kpi['not_rated_pct']}%", R, P, B)
expect("online delivery pct", f"{kpi['online_delivery_pct']}%", R, P, B)
expect("table booking pct", f"{kpi['table_booking_pct']}%", R, P, B)
expect("total votes", f"{kpi['total_votes']:,}", R, P, B)
expect("distinct cuisines", str(kpi["distinct_cuisines"]), R, P, B)
expect("cost/rating correlation", str(st["pearson_cost_rating"]), R, P)
expect("votes/rating correlation", str(st["pearson_votes_rating"]), R, P)
expect("NCR concentration", f"{st['pct_restaurants_in_delhi_ncr']}%", R, P)
expect("top-3 cuisine share", f"{st['top3_cuisine_share_pct']}%", R, P)

# The Power BI guide quotes the bridge row count and the credible-rating count.
bridge_rows = sum(1 for _ in (ROOT / "data" / "processed" / "bridge_cuisine.csv").open()) - 1
expect("bridge row count", f"{bridge_rows:,}", B, P)

# Deliverables must all exist and be non-trivial.
for rel, min_kb in [
    ("dashboard/zomato_dashboard.html", 300),
    ("dashboard/kpis.json", 20),
    ("README.md", 8),
    ("docs/POWERBI_GUIDE.md", 15),
    ("docs/INTERVIEW_PREP.md", 15),
    ("data/processed/fact_restaurants.csv", 1000),
    ("data/processed/bridge_cuisine.csv", 100),
    ("assets/page-overview.png", 100),
    ("assets/page-cost.png", 100),
    ("assets/page-cuisine.png", 100),
    ("assets/page-opportunity.png", 100),
    ("LICENSE", 0.5),
    ("Makefile", 0.1),
    ("requirements.txt", 0.05),
]:
    p = ROOT / rel
    kb = p.stat().st_size / 1024 if p.exists() else 0
    results.append((f"deliverable {rel}", kb >= min_kb, f"{kb:,.0f} KB (min {min_kb})"))

# The CV bullet claims "5000+ restaurants" — assert the data supports it.
results.append((
    "CV claim: 5,000+ restaurants analysed",
    kpi["total_restaurants"] >= 5000,
    f"{kpi['total_restaurants']:,} Indian restaurants in scope",
))
results.append((
    "CV claim: benchmarked avg dining cost for two",
    kpi["avg_cost_for_two"] is not None and kpi["median_cost_for_two"] is not None,
    f"mean ₹{kpi['avg_cost_for_two']:,.0f} / median ₹{kpi['median_cost_for_two']:,.0f}",
))
results.append((
    "CV claim: identified top-rated and most expensive",
    len(K["tables"]["top_rated"]) > 0 and len(K["tables"]["most_expensive"]) > 0,
    f"{K['tables']['top_rated'][0]['Restaurant Name']} / "
    f"{K['tables']['most_expensive'][0]['Restaurant Name']}",
))

for label, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {label}  — {detail}")

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} documentation checks passed")
(ROOT / "docs" / "doc_verification_report.json").write_text(
    json.dumps([{"check": a, "pass": b, "detail": c} for a, b, c in results], indent=2)
)
sys.exit(1 if failed else 0)
