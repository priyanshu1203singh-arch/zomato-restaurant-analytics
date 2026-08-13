"""
app/measures.py
===============
The measure layer, shared by the Streamlit app and the test suite.

This is the third implementation of the same measures — pandas (pipeline),
JavaScript (HTML dashboard), and now this. Keeping them in one importable module
rather than inline in the Streamlit script is what lets
`tests/test_streamlit_measures.py` assert that the app agrees with
`dashboard/kpis.json` without launching a browser.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"

# Thresholds. Identical to scripts/02_build_kpis.py by design — if you change
# one you must change both, and the tests will tell you if you forgot.
MIN_VOTES = 50
MIN_CITY_N = 20
MIN_CUISINE_N = 30
MIN_LOCALITY_N = 15

NCR = ["New Delhi", "Gurgaon", "Noida", "Faridabad", "Ghaziabad"]

PRICE_ORDER = ["1 - Budget", "2 - Mid-range", "3 - Premium", "4 - Luxury"]


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _ensure_processed() -> None:
    """Streamlit Cloud clones the repo but runs no build step, so if the
    processed files are missing we regenerate them from the raw extract."""
    if (PROC / "fact_restaurants.csv").exists():
        return
    for script in ("01_clean_data.py", "02_build_kpis.py"):
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script)],
            check=True,
            capture_output=True,
        )


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (india_fact, cuisine_bridge_for_india)."""
    _ensure_processed()
    fact = pd.read_csv(PROC / "fact_restaurants.csv")
    bridge = pd.read_csv(PROC / "bridge_cuisine.csv")

    india = fact[fact["Country"] == "India"].copy()
    bridge = bridge[bridge["Restaurant ID"].isin(set(india["Restaurant ID"]))].copy()

    # Explicit dtypes so a re-read never silently changes a measure.
    for c in ["Is Rated", "Credible Rating", "Has Table booking",
              "Has Online delivery", "Geo Valid"]:
        india[c] = india[c].astype(bool)
    india["Price Range Label"] = pd.Categorical(
        india["Price Range Label"], categories=PRICE_ORDER, ordered=True
    )
    return india, bridge


# ---------------------------------------------------------------------------
# Filtering — the Streamlit equivalent of Power BI's filter context
# ---------------------------------------------------------------------------
def apply_filters(
    df: pd.DataFrame,
    bridge: pd.DataFrame,
    *,
    cities: list[str] | None = None,
    cuisines: list[str] | None = None,
    price_tiers: list[int] | None = None,
    delivery_only: bool = False,
    booking_only: bool = False,
    rated_only: bool = False,
    credible_only: bool = False,
    min_rating: float = 0.0,
    search: str = "",
) -> pd.DataFrame:
    out = df
    if cities:
        out = out[out["City"].isin(cities)]
    if cuisines:
        ids = set(bridge.loc[bridge["Cuisine"].isin(cuisines), "Restaurant ID"])
        out = out[out["Restaurant ID"].isin(ids)]
    if price_tiers:
        out = out[out["Price range"].isin(price_tiers)]
    if delivery_only:
        out = out[out["Has Online delivery"]]
    if booking_only:
        out = out[out["Has Table booking"]]
    if rated_only:
        out = out[out["Is Rated"]]
    if credible_only:
        out = out[out["Credible Rating"]]
    if min_rating > 0:
        out = out[out["Aggregate rating"].ge(min_rating).fillna(False)]
    if search.strip():
        q = search.strip().lower()
        mask = (
            out["Restaurant Name"].str.lower().str.contains(q, na=False)
            | out["Locality"].str.lower().str.contains(q, na=False)
        )
        out = out[mask]
    return out


# ---------------------------------------------------------------------------
# Measures
# ---------------------------------------------------------------------------
def kpis(df: pd.DataFrame, bridge: pd.DataFrame) -> dict:
    """Every KPI card, computed from whatever rows survived the filters."""
    rated = df[df["Is Rated"]]
    cost = df["Average Cost for two"].dropna()
    b = bridge[bridge["Restaurant ID"].isin(set(df["Restaurant ID"]))]
    top = (
        df[df["Credible Rating"]]
        .sort_values(["Aggregate rating", "Votes"], ascending=[False, False])
        .head(1)
    )
    priciest = df.dropna(subset=["Average Cost for two"]).nlargest(
        1, "Average Cost for two"
    )
    n = len(df)
    return {
        "restaurants": int(df["Restaurant ID"].nunique()),
        "cities": int(df["City"].nunique()),
        "localities": int(df["Locality"].nunique()),
        "avg_cost": float(cost.mean()) if len(cost) else None,
        "median_cost": float(cost.median()) if len(cost) else None,
        "p90_cost": float(cost.quantile(0.90)) if len(cost) else None,
        "max_cost": float(cost.max()) if len(cost) else None,
        "avg_rating": float(rated["Aggregate rating"].mean()) if len(rated) else None,
        "rated_n": int(len(rated)),
        "not_rated_pct": 100 * (n - len(rated)) / n if n else None,
        "delivery_pct": 100 * float(df["Has Online delivery"].mean()) if n else None,
        "booking_pct": 100 * float(df["Has Table booking"].mean()) if n else None,
        "total_votes": int(df["Votes"].sum()),
        "avg_votes": float(df["Votes"].mean()) if n else None,
        "cuisines": int(b["Cuisine"].nunique()),
        "avg_cuisines": float(df["Cuisine Count"].mean()) if n else None,
        "credible_n": int(df["Credible Rating"].sum()),
        "top_name": top["Restaurant Name"].iloc[0] if len(top) else None,
        "top_rating": float(top["Aggregate rating"].iloc[0]) if len(top) else None,
        "priciest_name": priciest["Restaurant Name"].iloc[0] if len(priciest) else None,
    }


def rating_histogram(df: pd.DataFrame) -> pd.DataFrame:
    bins = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.01]
    labels = ["1.0–1.5", "1.5–2.0", "2.0–2.5", "2.5–3.0",
              "3.0–3.5", "3.5–4.0", "4.0–4.5", "4.5–5.0"]
    rated = df[df["Is Rated"]]
    cut = pd.cut(rated["Aggregate rating"], bins=bins, labels=labels, right=False)
    return (
        cut.value_counts().reindex(labels).rename_axis("Rating band")
        .reset_index(name="Restaurants")
    )


def price_tier_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = (
        df.groupby("Price Range Label", observed=False)
        .agg(
            Restaurants=("Restaurant ID", "nunique"),
            **{"Avg rating": ("Aggregate rating", "mean")},
            **{"Avg cost": ("Average Cost for two", "mean")},
            **{"Online delivery %": ("Has Online delivery", "mean")},
            **{"Table booking %": ("Has Table booking", "mean")},
            **{"Avg votes": ("Votes", "mean")},
        )
        .reset_index()
    )
    g["Online delivery %"] *= 100
    g["Table booking %"] *= 100
    total = len(df)
    g["Share %"] = 100 * g["Restaurants"] / total if total else 0
    return g


def city_benchmark(df: pd.DataFrame, min_n: int = MIN_CITY_N) -> pd.DataFrame:
    g = (
        df.groupby("City")
        .agg(
            Restaurants=("Restaurant ID", "nunique"),
            **{"Avg cost": ("Average Cost for two", "mean")},
            **{"Median cost": ("Average Cost for two", "median")},
            **{"Avg rating": ("Aggregate rating", "mean")},
            **{"Online delivery %": ("Has Online delivery", "mean")},
            **{"Table booking %": ("Has Table booking", "mean")},
            **{"Total votes": ("Votes", "sum")},
        )
        .reset_index()
    )
    g["Online delivery %"] *= 100
    g["Table booking %"] *= 100
    return g[g["Restaurants"] >= min_n].sort_values("Restaurants", ascending=False)


def cuisine_summary(df: pd.DataFrame, bridge: pd.DataFrame) -> pd.DataFrame:
    b = bridge[bridge["Restaurant ID"].isin(set(df["Restaurant ID"]))]
    j = b.merge(
        df[["Restaurant ID", "Aggregate rating", "Average Cost for two", "Votes"]],
        on="Restaurant ID",
        how="left",
    )
    g = (
        j.groupby("Cuisine")
        .agg(
            Restaurants=("Restaurant ID", "nunique"),
            **{"Avg rating": ("Aggregate rating", "mean")},
            **{"Avg cost": ("Average Cost for two", "mean")},
            **{"Total votes": ("Votes", "sum")},
        )
        .reset_index()
    )
    return g.sort_values("Restaurants", ascending=False)


def cost_band_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Average rating by cost band, restricted to credibly-rated venues."""
    bins = [0, 200, 400, 600, 800, 1200, 1600, 2400, np.inf]
    labels = ["<200", "200–400", "400–600", "600–800",
              "800–1200", "1200–1600", "1600–2400", "2400+"]
    d = df[df["Credible Rating"]].dropna(
        subset=["Average Cost for two", "Aggregate rating"]
    ).copy()
    d["Cost band"] = pd.cut(
        d["Average Cost for two"], bins=bins, labels=labels, right=False
    )
    return (
        d.groupby("Cost band", observed=False)
        .agg(**{"Avg rating": ("Aggregate rating", "mean"),
                "Restaurants": ("Restaurant ID", "nunique")})
        .reset_index()
    )


def opportunity(df: pd.DataFrame, min_n: int = MIN_LOCALITY_N) -> pd.DataFrame:
    """z(log demand) - z(avg rating) per locality.

    The log is load-bearing: votes-per-restaurant is heavily right-skewed, and
    without it one locality's demand z-score swamps the quality term and the
    model degenerates into "rank by votes".
    """
    g = (
        df.groupby(["City", "Locality"])
        .agg(
            Restaurants=("Restaurant ID", "nunique"),
            **{"Avg rating": ("Aggregate rating", "mean")},
            **{"Avg cost": ("Average Cost for two", "mean")},
            **{"Total votes": ("Votes", "sum")},
        )
        .reset_index()
    )
    g = g[(g["Restaurants"] >= min_n) & g["Avg rating"].notna()].copy()
    if len(g) < 3:
        return g.assign(**{"Votes per restaurant": np.nan, "Opportunity score": np.nan})

    g["Votes per restaurant"] = g["Total votes"] / g["Restaurants"]

    def z(s: pd.Series) -> pd.Series:
        sd = s.std(ddof=0)
        return (s - s.mean()) / (sd if sd else 1)

    g["Opportunity score"] = z(np.log1p(g["Votes per restaurant"])) - z(g["Avg rating"])
    return g.sort_values("Opportunity score", ascending=False)


def correlations(df: pd.DataFrame) -> dict:
    d = df[df["Credible Rating"]].dropna(
        subset=["Average Cost for two", "Aggregate rating"]
    )
    if len(d) < 3:
        return {"pearson": None, "spearman": None, "votes": None, "n": len(d)}
    return {
        "pearson": float(d["Average Cost for two"].corr(d["Aggregate rating"])),
        "spearman": float(
            d["Average Cost for two"].corr(d["Aggregate rating"], method="spearman")
        ),
        "votes": float(np.log1p(d["Votes"]).corr(d["Aggregate rating"])),
        "n": int(len(d)),
    }


def value_leaderboard(df: pd.DataFrame, n: int = 15) -> pd.DataFrame:
    """Stars per Rs.100. The 4.0 rating floor stops cheap-and-bad winning."""
    d = df[
        df["Credible Rating"]
        & df["Aggregate rating"].ge(4.0)
        & df["Average Cost for two"].gt(0)
    ].copy()
    d["Stars per ₹100"] = d["Aggregate rating"] / (d["Average Cost for two"] / 100)
    return d.nlargest(n, "Stars per ₹100")
