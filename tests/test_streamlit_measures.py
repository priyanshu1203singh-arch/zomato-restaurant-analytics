"""
tests/test_streamlit_measures.py
================================
Assert that the Streamlit app's measure layer (`app/measures.py`) reproduces the
pipeline's reference KPIs exactly, and that the filter layer behaves.

This is the same idea as the pandas-vs-JavaScript reconciliation in
`scripts/04_verify_dashboard.mjs`: two independent implementations agreeing is a
real test of the measure logic. An app that renders without errors is not.

Run:  python tests/test_streamlit_measures.py
      (or `pytest tests/` if you have pytest)
"""

from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app import measures as M  # noqa: E402

REF = json.loads((ROOT / "dashboard" / "kpis.json").read_text())
KPI, STATS, META = REF["kpi"], REF["stats"], REF["meta"]

india, bridge = M.load_data()
k = M.kpis(india, bridge)
corr = M.correlations(india)

results: list[tuple[str, bool, str]] = []


def check(name: str, actual, expected, tol: float = 0.0) -> None:
    if actual is None or expected is None:
        ok = actual is expected
    elif isinstance(actual, str):
        ok = actual == expected
    else:
        ok = abs(float(actual) - float(expected)) <= tol
    results.append((name, ok, f"app={actual!r} pipeline={expected!r} tol={tol}"))


# ---- 1. The KPI cards -----------------------------------------------------
check("total restaurants", k["restaurants"], KPI["total_restaurants"])
check("cities covered", k["cities"], KPI["cities_covered"])
check("localities covered", k["localities"], KPI["localities_covered"])
check("avg cost for two", round(k["avg_cost"]), KPI["avg_cost_for_two"], 1)
check("median cost for two", k["median_cost"], KPI["median_cost_for_two"], 1)
check("p90 cost for two", k["p90_cost"], KPI["p90_cost_for_two"], 1)
check("avg rating", round(k["avg_rating"], 2), KPI["avg_rating"], 0.011)
check("rated venue count", k["rated_n"],
      KPI["total_restaurants"] - KPI["not_rated_count"])
check("not-rated %", round(k["not_rated_pct"], 1), KPI["not_rated_pct"], 0.11)
check("online delivery %", round(k["delivery_pct"], 1), KPI["online_delivery_pct"], 0.11)
check("table booking %", round(k["booking_pct"], 1), KPI["table_booking_pct"], 0.11)
check("total votes", k["total_votes"], KPI["total_votes"])
check("distinct cuisines", k["cuisines"], KPI["distinct_cuisines"])
check("avg cuisines per restaurant", round(k["avg_cuisines"], 2),
      KPI["avg_cuisines_per_restaurant"], 0.011)
check("top rated restaurant", k["top_name"],
      REF["tables"]["top_rated"][0]["Restaurant Name"])
check("most expensive restaurant", k["priciest_name"],
      REF["tables"]["most_expensive"][0]["Restaurant Name"])

# ---- 2. The statistics ----------------------------------------------------
check("pearson cost~rating", round(corr["pearson"], 3), STATS["pearson_cost_rating"], 0.0011)
check("spearman cost~rating", round(corr["spearman"], 3), STATS["spearman_cost_rating"], 0.0011)
check("pearson log(votes)~rating", round(corr["votes"], 3), STATS["pearson_votes_rating"], 0.0011)
check("correlation sample size", corr["n"], STATS["n_for_correlation"])

# ---- 3. The opportunity model --------------------------------------------
opp = M.opportunity(india)
ref_opp = REF["tables"]["opportunity"]
check("opportunity #1 locality", opp.iloc[0]["Locality"], ref_opp[0]["locality"])
check("opportunity #1 city", opp.iloc[0]["City"], ref_opp[0]["city"])
check("opportunity #1 score", round(opp.iloc[0]["Opportunity score"], 2),
      ref_opp[0]["opportunity_score"], 0.011)
check("opportunity #2 locality", opp.iloc[1]["Locality"], ref_opp[1]["locality"])
results.append((
    "opportunity model respects the 15-restaurant floor",
    bool((opp["Restaurants"] >= M.MIN_LOCALITY_N).all()),
    f"min n = {int(opp['Restaurants'].min())}",
))

# ---- 4. Derived tables ----------------------------------------------------
pt = M.price_tier_summary(india)
results.append((
    "price tiers sum to the restaurant count",
    int(pt["Restaurants"].sum()) == k["restaurants"],
    f"{int(pt['Restaurants'].sum()):,} vs {k['restaurants']:,}",
))
results.append((
    "price tiers are in ascending order",
    list(pt["Price Range Label"].astype(str)) == M.PRICE_ORDER,
    str(list(pt["Price Range Label"].astype(str))),
))

hist = M.rating_histogram(india)
results.append((
    "rating histogram sums to the rated count",
    int(hist["Restaurants"].sum()) == k["rated_n"],
    f"{int(hist['Restaurants'].sum()):,} vs {k['rated_n']:,}",
))

cu = M.cuisine_summary(india, bridge)
results.append((
    "cuisine counts exceed the restaurant count (many-to-many is real)",
    int(cu["Restaurants"].sum()) > k["restaurants"],
    f"{int(cu['Restaurants'].sum()):,} appearances vs {k['restaurants']:,} restaurants",
))

val = M.value_leaderboard(india)
results.append((
    "value leaderboard respects the 4.0 rating floor",
    bool((val["Aggregate rating"] >= 4.0).all()),
    f"min rating {val['Aggregate rating'].min()}",
))

# ---- 5. The filter layer --------------------------------------------------
f_city = M.apply_filters(india, bridge, cities=["Bangalore"])
results.append(("city filter narrows the frame",
                0 < len(f_city) < len(india), f"{len(f_city):,} rows"))
results.append(("city filter returns only that city",
                set(f_city["City"]) == {"Bangalore"}, str(set(f_city["City"]))))

f_lux = M.apply_filters(india, bridge, price_tiers=[4])
check("luxury tier count", len(f_lux),
      [p for p in REF["charts"]["price_range_mix"] if p["band"] == "4 - Luxury"][0]["restaurants"])

f_cui = M.apply_filters(india, bridge, cuisines=["Italian"])
check("Italian cuisine count", len(f_cui),
      [c for c in REF["charts"]["cuisine_by_volume"] if c["cuisine"] == "Italian"][0]["restaurants"])

f_del = M.apply_filters(india, bridge, delivery_only=True)
check("online delivery count", len(f_del),
      round(KPI["online_delivery_pct"] / 100 * KPI["total_restaurants"]), 1)

f_none = M.apply_filters(india, bridge, cities=["Bangalore"], min_rating=4.99,
                         price_tiers=[1])
results.append(("an impossible filter returns empty rather than throwing",
                len(f_none) == 0, f"{len(f_none)} rows"))

f_search = M.apply_filters(india, bridge, search="hauz khas")
results.append(("free-text search matches localities",
                len(f_search) > 0, f"{len(f_search):,} rows"))

# KPIs must still compute on a filtered frame without blowing up.
k_small = M.kpis(f_city, bridge)
results.append(("KPIs compute on a filtered frame",
                k_small["restaurants"] == len(f_city),
                f"{k_small['restaurants']} restaurants, avg rating "
                f"{k_small['avg_rating']:.2f}"))

# ---- report ---------------------------------------------------------------
for name, ok, detail in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name}  — {detail}")

failed = [r for r in results if not r[1]]
print(f"\n{len(results) - len(failed)}/{len(results)} Streamlit measure checks passed")
(ROOT / "docs" / "streamlit_test_report.json").write_text(
    json.dumps([{"check": a, "pass": b, "detail": c} for a, b, c in results], indent=2)
)
sys.exit(1 if failed else 0)
