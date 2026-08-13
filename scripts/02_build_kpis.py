"""
02_build_kpis.py
================
Stage 2: turn the clean star schema into the exact numbers the dashboard shows.

DESIGN RULE
-----------
Nothing in the dashboard or the README is typed by hand. Every number is written
by this script into `dashboard/kpis.json`, so the HTML dashboard, the Power BI
guide and the README can never drift out of sync with the data.

SCOPE RULE (the one an interviewer will ask about)
--------------------------------------------------
`Average Cost for two` is stored in 15 different currencies. Averaging INR with
USD is meaningless, so every *money* KPI is scoped to India (Indian Rupees,
8,652 restaurants -- still the 5,000+ scale claimed on the CV). Currency-free
metrics (Price range 1-4, rating, delivery flags) are also reported globally on
a separate page.

Run:  python scripts/02_build_kpis.py
"""

from __future__ import annotations

import json
import pathlib

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
DASH = ROOT / "dashboard"
DASH.mkdir(parents=True, exist_ok=True)

MIN_VOTES = 50          # credibility floor for "top rated" leaderboards
MIN_CITY_N = 20         # a city needs 20+ restaurants before we benchmark it
MIN_CUISINE_N = 30      # a cuisine needs 30+ restaurants before we rank it
MIN_LOCALITY_N = 15     # a locality needs 15+ restaurants before we rank it


def r(x, nd=2):
    """Round for JSON, turning NaN into None so JS gets `null` not `NaN`."""
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    return round(float(x), nd)


def main() -> None:
    fact = pd.read_csv(PROC / "fact_restaurants.csv")
    bridge = pd.read_csv(PROC / "bridge_cuisine.csv")

    # ---------------------------------------------------------------- scopes
    india = fact[fact["Country"] == "India"].copy()
    rated_in = india[india["Is Rated"] == True]          # noqa: E712
    credible_in = india[india["Credible Rating"] == True]  # noqa: E712

    out: dict = {"meta": {}, "kpi": {}, "charts": {}, "tables": {}, "stats": {}}

    out["meta"] = {
        "source": "Zomato Restaurants Data (Kaggle, 9,551 restaurants / 15 countries)",
        "rows_raw": int(len(fact)),
        "rows_india": int(len(india)),
        "countries": int(fact["Country"].nunique()),
        "cities_global": int(fact["City"].nunique()),
        "min_votes_for_leaderboard": MIN_VOTES,
        "generated_by": "scripts/02_build_kpis.py",
    }

    # ====================================================================
    # KPI CARDS  (the header strip of the dashboard)
    # ====================================================================
    print("== KPI cards (India scope) ==")
    kpi = out["kpi"]

    # KPI 1 - Total Restaurants. Distinct count, not row count.
    kpi["total_restaurants"] = int(india["Restaurant ID"].nunique())

    # KPI 2 - Cities Covered. Market breadth.
    kpi["cities_covered"] = int(india["City"].nunique())
    kpi["localities_covered"] = int(india["Locality"].nunique())

    # KPI 3 - Avg Cost for Two. The headline benchmark from the CV bullet.
    kpi["avg_cost_for_two"] = r(india["Average Cost for two"].mean(), 0)
    # Median matters because cost is right-skewed (a few luxury outliers).
    kpi["median_cost_for_two"] = r(india["Average Cost for two"].median(), 0)
    kpi["cost_skew"] = r(india["Average Cost for two"].skew())
    kpi["p90_cost_for_two"] = r(india["Average Cost for two"].quantile(0.90), 0)

    # KPI 4 - Avg Rating. RATED RESTAURANTS ONLY (the bias fix).
    kpi["avg_rating"] = r(rated_in["Aggregate rating"].mean())
    kpi["avg_rating_if_zeros_kept"] = r(
        india["Aggregate rating"].fillna(0).mean()
    )  # shown in docs to prove why the fix matters
    kpi["rating_bias_avoided"] = r(
        kpi["avg_rating"] - kpi["avg_rating_if_zeros_kept"]
    )

    # KPI 5 - Not-Rated share. A data-coverage / cold-start metric.
    kpi["not_rated_count"] = int((india["Is Rated"] == False).sum())  # noqa: E712
    kpi["not_rated_pct"] = r(100 * kpi["not_rated_count"] / len(india), 1)

    # KPI 6/7 - Service adoption.
    kpi["online_delivery_pct"] = r(100 * india["Has Online delivery"].mean(), 1)
    kpi["table_booking_pct"] = r(100 * india["Has Table booking"].mean(), 1)

    # KPI 8 - Engagement.
    kpi["total_votes"] = int(india["Votes"].sum())
    kpi["avg_votes"] = r(india["Votes"].mean(), 0)

    # KPI 9 - Menu variety.
    india_ids = set(india["Restaurant ID"])
    bridge_in = bridge[bridge["Restaurant ID"].isin(india_ids)]
    kpi["distinct_cuisines"] = int(bridge_in["Cuisine"].nunique())
    kpi["avg_cuisines_per_restaurant"] = r(india["Cuisine Count"].mean())

    for k, v in kpi.items():
        print(f"   {k:34s} {v}")

    # ====================================================================
    # CHART 1 - Rating distribution (histogram)
    # ====================================================================
    bins = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.01]
    lab = ["1.0-1.5", "1.5-2.0", "2.0-2.5", "2.5-3.0", "3.0-3.5", "3.5-4.0", "4.0-4.5", "4.5-5.0"]
    hist = pd.cut(rated_in["Aggregate rating"], bins=bins, labels=lab, right=False)
    out["charts"]["rating_distribution"] = [
        {"band": b, "restaurants": int(n)} for b, n in hist.value_counts().reindex(lab).items()
    ]

    # ====================================================================
    # CHART 2 - Price-range mix + avg rating per band
    # ====================================================================
    pr = (
        india.groupby("Price Range Label")
        .agg(
            restaurants=("Restaurant ID", "nunique"),
            avg_rating=("Aggregate rating", "mean"),
            avg_cost=("Average Cost for two", "mean"),
            delivery_pct=("Has Online delivery", "mean"),
            booking_pct=("Has Table booking", "mean"),
            avg_votes=("Votes", "mean"),
        )
        .reset_index()
        .sort_values("Price Range Label")
    )
    out["charts"]["price_range_mix"] = [
        {
            "band": row["Price Range Label"],
            "restaurants": int(row["restaurants"]),
            "share_pct": r(100 * row["restaurants"] / len(india), 1),
            "avg_rating": r(row["avg_rating"]),
            "avg_cost": r(row["avg_cost"], 0),
            "delivery_pct": r(100 * row["delivery_pct"], 1),
            "booking_pct": r(100 * row["booking_pct"], 1),
            "avg_votes": r(row["avg_votes"], 0),
        }
        for _, row in pr.iterrows()
    ]

    # ====================================================================
    # CHART 3 - City benchmark (the "where to open" view)
    # ====================================================================
    city = (
        india.groupby("City")
        .agg(
            restaurants=("Restaurant ID", "nunique"),
            avg_cost=("Average Cost for two", "mean"),
            avg_rating=("Aggregate rating", "mean"),
            delivery_pct=("Has Online delivery", "mean"),
            booking_pct=("Has Table booking", "mean"),
            total_votes=("Votes", "sum"),
        )
        .reset_index()
    )
    city["delivery_pct"] = 100 * city["delivery_pct"]
    city["booking_pct"] = 100 * city["booking_pct"]
    city_bench = city[city["restaurants"] >= MIN_CITY_N].sort_values(
        "restaurants", ascending=False
    )
    out["charts"]["city_benchmark"] = [
        {
            "city": row["City"],
            "restaurants": int(row["restaurants"]),
            "avg_cost": r(row["avg_cost"], 0),
            "avg_rating": r(row["avg_rating"]),
            "delivery_pct": r(row["delivery_pct"], 1),
            "booking_pct": r(row["booking_pct"], 1),
            "total_votes": int(row["total_votes"]),
        }
        for _, row in city_bench.iterrows()
    ]
    out["charts"]["city_all"] = [
        {"city": row["City"], "restaurants": int(row["restaurants"])}
        for _, row in city.sort_values("restaurants", ascending=False).head(15).iterrows()
    ]

    # ====================================================================
    # CHART 4 - Cuisine leaderboard
    # ====================================================================
    cu = bridge_in.merge(
        india[["Restaurant ID", "Aggregate rating", "Average Cost for two", "Votes",
               "Has Online delivery", "Is Rated"]],
        on="Restaurant ID",
        how="left",
    )
    cuisine = (
        cu.groupby("Cuisine")
        .agg(
            restaurants=("Restaurant ID", "nunique"),
            avg_rating=("Aggregate rating", "mean"),
            avg_cost=("Average Cost for two", "mean"),
            total_votes=("Votes", "sum"),
            delivery_pct=("Has Online delivery", "mean"),
        )
        .reset_index()
    )
    cuisine["delivery_pct"] = 100 * cuisine["delivery_pct"]
    cuisine_top = cuisine.sort_values("restaurants", ascending=False).head(15)
    out["charts"]["cuisine_by_volume"] = [
        {
            "cuisine": row["Cuisine"],
            "restaurants": int(row["restaurants"]),
            "avg_rating": r(row["avg_rating"]),
            "avg_cost": r(row["avg_cost"], 0),
            "total_votes": int(row["total_votes"]),
            "delivery_pct": r(row["delivery_pct"], 1),
        }
        for _, row in cuisine_top.iterrows()
    ]
    cuisine_rated = cuisine[cuisine["restaurants"] >= MIN_CUISINE_N].sort_values(
        "avg_rating", ascending=False
    )
    out["charts"]["cuisine_by_rating"] = [
        {
            "cuisine": row["Cuisine"],
            "restaurants": int(row["restaurants"]),
            "avg_rating": r(row["avg_rating"]),
            "avg_cost": r(row["avg_cost"], 0),
        }
        for _, row in cuisine_rated.head(12).iterrows()
    ]

    # ====================================================================
    # CHART 5 - Cost vs rating scatter (does paying more buy quality?)
    # ====================================================================
    sc = credible_in.dropna(subset=["Average Cost for two", "Aggregate rating"])
    sc = sc[sc["Average Cost for two"] <= 4000]  # trim the long tail for readability
    out["charts"]["cost_vs_rating"] = [
        {
            "name": row["Restaurant Name"],
            "city": row["City"],
            "cost": int(row["Average Cost for two"]),
            "rating": r(row["Aggregate rating"]),
            "votes": int(row["Votes"]),
            "band": row["Price Range Label"],
        }
        for _, row in sc.sample(n=min(700, len(sc)), random_state=42).iterrows()
    ]

    # Binned trend line - the honest way to show the relationship
    cost_bins = [0, 200, 400, 600, 800, 1200, 1600, 2400, np.inf]
    cost_lab = ["<200", "200-400", "400-600", "600-800", "800-1200", "1200-1600", "1600-2400", "2400+"]
    tmp = credible_in.dropna(subset=["Average Cost for two", "Aggregate rating"]).copy()
    tmp["bin"] = pd.cut(tmp["Average Cost for two"], bins=cost_bins, labels=cost_lab, right=False)
    trend = tmp.groupby("bin", observed=False).agg(
        avg_rating=("Aggregate rating", "mean"), n=("Restaurant ID", "nunique")
    ).reset_index()
    out["charts"]["cost_band_rating_trend"] = [
        {"band": str(row["bin"]), "avg_rating": r(row["avg_rating"]), "restaurants": int(row["n"])}
        for _, row in trend.iterrows()
    ]

    # ====================================================================
    # CHART 6 - Online delivery effect
    # ====================================================================
    grp = india.groupby("Has Online delivery")
    out["charts"]["delivery_effect"] = [
        {
            "delivery": "Delivers online" if bool(k) else "No online delivery",
            "restaurants": int(g["Restaurant ID"].nunique()),
            "avg_rating": r(g["Aggregate rating"].mean()),
            "avg_votes": r(g["Votes"].mean(), 0),
            "avg_cost": r(g["Average Cost for two"].mean(), 0),
        }
        for k, g in grp
    ]

    # ====================================================================
    # CHART 7 - Global page (currency-free metrics only)
    # ====================================================================
    glob = (
        fact.groupby("Country")
        .agg(
            restaurants=("Restaurant ID", "nunique"),
            avg_rating=("Aggregate rating", "mean"),
            avg_price_range=("Price range", "mean"),
            delivery_pct=("Has Online delivery", "mean"),
            booking_pct=("Has Table booking", "mean"),
        )
        .reset_index()
        .sort_values("restaurants", ascending=False)
    )
    out["charts"]["country_overview"] = [
        {
            "country": row["Country"],
            "restaurants": int(row["restaurants"]),
            "avg_rating": r(row["avg_rating"]),
            "avg_price_range": r(row["avg_price_range"]),
            "delivery_pct": r(100 * row["delivery_pct"], 1),
            "booking_pct": r(100 * row["booking_pct"], 1),
        }
        for _, row in glob.iterrows()
    ]

    # ====================================================================
    # TABLES - leaderboards
    # ====================================================================
    def rows(df, cols):
        return [
            {c: (int(v) if isinstance(v, (np.integer,)) else
                 (r(v) if isinstance(v, (float, np.floating)) else v))
             for c, v in row[cols].items()}
            for _, row in df.iterrows()
        ]

    lb_cols = ["Restaurant Name", "City", "Locality", "Cuisines",
               "Average Cost for two", "Aggregate rating", "Votes"]

    out["tables"]["top_rated"] = rows(
        credible_in.sort_values(["Aggregate rating", "Votes"], ascending=[False, False]).head(15),
        lb_cols,
    )
    out["tables"]["most_expensive"] = rows(
        india.sort_values("Average Cost for two", ascending=False).head(15), lb_cols
    )
    out["tables"]["best_value"] = rows(
        credible_in[credible_in["Aggregate rating"] >= 4.0]
        .sort_values("Value Score", ascending=False).head(15),
        lb_cols,
    )
    out["tables"]["most_voted"] = rows(
        india.sort_values("Votes", ascending=False).head(15), lb_cols
    )

    # ====================================================================
    # OPPORTUNITY MODEL - the "where should we open next" answer
    # ====================================================================
    # A locality is attractive when demand is proven (high votes per restaurant)
    # but the incumbent quality bar is beatable (low avg rating).
    loc = (
        india.groupby(["City", "Locality"])
        .agg(
            restaurants=("Restaurant ID", "nunique"),
            avg_rating=("Aggregate rating", "mean"),
            avg_cost=("Average Cost for two", "mean"),
            total_votes=("Votes", "sum"),
        )
        .reset_index()
    )
    loc = loc[loc["restaurants"] >= MIN_LOCALITY_N].copy()
    loc["votes_per_restaurant"] = loc["total_votes"] / loc["restaurants"]

    def z(s):
        return (s - s.mean()) / s.std(ddof=0)

    # Demand strength minus incumbent quality => headroom.
    # votes-per-restaurant is heavily right-skewed (Hauz Khas Village is ~15x the
    # median locality), so we z-score log1p(demand) instead of raw demand.
    # Without the log, one outlier locality dominates the score and the quality
    # term becomes decorative.
    loc["demand_z"] = z(np.log1p(loc["votes_per_restaurant"]))
    loc["quality_z"] = z(loc["avg_rating"])
    loc["opportunity_score"] = (loc["demand_z"] - loc["quality_z"]).round(3)
    loc = loc.sort_values("opportunity_score", ascending=False)
    out["tables"]["opportunity"] = [
        {
            "city": row["City"],
            "locality": row["Locality"],
            "restaurants": int(row["restaurants"]),
            "avg_rating": r(row["avg_rating"]),
            "avg_cost": r(row["avg_cost"], 0),
            "votes_per_restaurant": r(row["votes_per_restaurant"], 0),
            "opportunity_score": r(row["opportunity_score"]),
        }
        for _, row in loc.head(12).iterrows()
    ]
    out["charts"]["opportunity_quadrant"] = [
        {
            "locality": f'{row["Locality"]}',
            "city": row["City"],
            "restaurants": int(row["restaurants"]),
            "avg_rating": r(row["avg_rating"]),
            "votes_per_restaurant": r(row["votes_per_restaurant"], 0),
            "score": r(row["opportunity_score"]),
        }
        for _, row in loc.iterrows()
    ]

    # ====================================================================
    # STATS - defensible claims, computed not asserted
    # ====================================================================
    print("\n== Statistical tests ==")
    st = out["stats"]

    v = credible_in.dropna(subset=["Average Cost for two", "Aggregate rating"])
    st["pearson_cost_rating"] = r(v["Average Cost for two"].corr(v["Aggregate rating"]), 3)
    st["spearman_cost_rating"] = r(
        v["Average Cost for two"].corr(v["Aggregate rating"], method="spearman"), 3
    )
    st["pearson_votes_rating"] = r(
        np.log1p(v["Votes"]).corr(v["Aggregate rating"]), 3
    )
    st["n_for_correlation"] = int(len(v))

    d_yes = rated_in[rated_in["Has Online delivery"] == True]["Aggregate rating"]  # noqa: E712
    d_no = rated_in[rated_in["Has Online delivery"] == False]["Aggregate rating"]  # noqa: E712
    st["delivery_rating_gap"] = r(d_yes.mean() - d_no.mean())
    # Welch t-test without scipy (unequal variance)
    n1, n2 = len(d_yes), len(d_no)
    s1, s2 = d_yes.var(ddof=1), d_no.var(ddof=1)
    tstat = (d_yes.mean() - d_no.mean()) / np.sqrt(s1 / n1 + s2 / n2)
    st["delivery_welch_t"] = r(tstat, 2)
    st["delivery_n_yes"] = int(n1)
    st["delivery_n_no"] = int(n2)

    st["pct_restaurants_in_delhi_ncr"] = r(
        100
        * india[india["City"].isin(
            ["New Delhi", "Gurgaon", "Noida", "Faridabad", "Ghaziabad"]
        )]["Restaurant ID"].nunique()
        / len(india),
        1,
    )
    # NOTE: a restaurant can serve several cuisines, so you cannot sum cuisine
    # counts and divide -- that double-counts. Correct measure = share of
    # restaurants serving AT LEAST ONE of the top 3 cuisines.
    top3 = cuisine.sort_values("restaurants", ascending=False).head(3)["Cuisine"].tolist()
    st["top3_cuisines"] = top3
    st["top3_cuisine_share_pct"] = r(
        100
        * bridge_in[bridge_in["Cuisine"].isin(top3)]["Restaurant ID"].nunique()
        / len(india),
        1,
    )
    st["single_cuisine_restaurants_pct"] = r(
        100 * (india["Cuisine Count"] == 1).mean(), 1
    )
    for k, vv in st.items():
        print(f"   {k:34s} {vv}")

    # ====================================================================
    DASH.joinpath("kpis.json").write_text(json.dumps(out, indent=2))
    print(f"\nWrote {DASH / 'kpis.json'}")

    # Also drop tidy CSVs so Power BI / Excel users can pick them up directly.
    agg = ROOT / "data" / "processed"
    city_bench.to_csv(agg / "agg_city_benchmark.csv", index=False)
    cuisine.sort_values("restaurants", ascending=False).to_csv(
        agg / "agg_cuisine.csv", index=False
    )
    loc.to_csv(agg / "agg_locality_opportunity.csv", index=False)
    pr.to_csv(agg / "agg_price_range.csv", index=False)
    print("Wrote 4 aggregate CSVs to data/processed/")


if __name__ == "__main__":
    main()
