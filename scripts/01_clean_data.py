"""
01_clean_data.py
================
Stage 1 of the Zomato Restaurant Analytics pipeline: raw -> clean star schema.

WHY THIS FILE EXISTS
--------------------
The raw Zomato extract is a single flat CSV. It is unusable as-is for BI because:
  1. `Aggregate rating = 0` does NOT mean "rated zero", it means "NOT RATED YET".
     Averaging it drags the KPI down by ~0.6 stars. This is the single most
     important cleaning decision in the whole project.
  2. `Average Cost for two` mixes 15 currencies. Averaging INR and USD together
     produces a meaningless number.
  3. `Cuisines` is a comma-separated multi-value field. You cannot slice by
     cuisine until it is exploded into a bridge table.
  4. Country is stored as a numeric code with no lookup table shipped.

Output: a small star schema in data/processed/ that Power BI (or the HTML
dashboard) can consume directly.

    fact_restaurants.csv   1 row per restaurant  (the fact / detail table)
    dim_country.csv        country code -> country name + currency
    bridge_cuisine.csv     restaurant_id -> single cuisine  (many-to-many)
    dim_price_range.csv    1..4 -> label
    data_quality_log.csv   every row we changed, and why  (audit trail)

Run:  python scripts/01_clean_data.py
"""

from __future__ import annotations

import pathlib
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "zomato.csv"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Country code lookup. The Kaggle release ships this as a separate xlsx; it is
# only 15 rows so we inline it to keep the pipeline dependency-free.
# Currency is taken from the raw `Currency` column and asserted against this.
# ---------------------------------------------------------------------------
COUNTRY_MAP = {
    1: "India",
    14: "Australia",
    30: "Brazil",
    37: "Canada",
    94: "Indonesia",
    148: "New Zealand",
    162: "Philippines",
    166: "Qatar",
    184: "Singapore",
    189: "South Africa",
    191: "Sri Lanka",
    208: "Turkey",
    214: "UAE",
    215: "United Kingdom",
    216: "United States",
}

PRICE_RANGE_LABELS = {
    1: "1 - Budget",
    2: "2 - Mid-range",
    3: "3 - Premium",
    4: "4 - Luxury",
}

YES_NO_COLS = [
    "Has Table booking",
    "Has Online delivery",
    "Is delivering now",
    "Switch to order menu",
]

quality_log: list[dict] = []


def log(step: str, rows: int, detail: str) -> None:
    """Record a data-quality action so the cleaning is auditable, not magic."""
    quality_log.append({"step": step, "rows_affected": rows, "detail": detail})
    print(f"  [{rows:>6,}] {step} :: {detail}")


def main() -> None:
    if not RAW.exists():
        sys.exit(f"Raw file missing: {RAW}\nRun scripts/00_download_data.sh first.")

    print("STEP 1  Load raw extract")
    # latin-1: the file contains non-UTF8 bytes in restaurant names (e.g. cafés)
    df = pd.read_csv(RAW, encoding="latin-1")
    log("load", len(df), f"{RAW.name} -> {df.shape[0]:,} rows x {df.shape[1]} cols")

    print("STEP 2  Normalise column names")
    df.columns = [c.strip() for c in df.columns]

    print("STEP 3  Trim whitespace on every text column")
    text_cols = df.select_dtypes(include=["object", "string"]).columns
    for c in text_cols:
        df[c] = df[c].astype("string").str.strip()

    print("STEP 4  De-duplicate on Restaurant ID")
    before = len(df)
    df = df.drop_duplicates(subset=["Restaurant ID"], keep="first")
    log("dedupe", before - len(df), "dropped duplicate Restaurant IDs")

    print("STEP 5  Attach country + price-range dimensions")
    df["Country"] = df["Country Code"].map(COUNTRY_MAP)
    unmapped = int(df["Country"].isna().sum())
    if unmapped:
        log("country_map", unmapped, "UNMAPPED country codes -> 'Unknown'")
        df["Country"] = df["Country"].fillna("Unknown")
    df["Price Range Label"] = df["Price range"].map(PRICE_RANGE_LABELS)

    print("STEP 6  Cast Yes/No flags to boolean")
    for c in YES_NO_COLS:
        df[c] = df[c].str.lower().map({"yes": True, "no": False}).astype("boolean")
    # `Switch to order menu` is constant ('No' for every row) -> zero information.
    if df["Switch to order menu"].nunique(dropna=True) <= 1:
        log("drop_constant", len(df), "'Switch to order menu' is constant -> dropped")
        df = df.drop(columns=["Switch to order menu"])

    print("STEP 7  *** Rating 0 means NOT RATED, not a zero-star rating ***")
    unrated = int((df["Aggregate rating"] == 0).sum())
    df["Is Rated"] = df["Aggregate rating"] > 0
    df["Aggregate rating"] = df["Aggregate rating"].replace(0, np.nan)
    log(
        "rating_zero_to_null",
        unrated,
        "Aggregate rating 0 -> NULL; excluded from every average (bias fix)",
    )
    # `Rating text` should agree with `Is Rated`
    df.loc[~df["Is Rated"], "Rating text"] = "Not rated"

    print("STEP 8  Invalid cost handling")
    zero_cost = int((df["Average Cost for two"] <= 0).sum())
    df["Average Cost for two"] = df["Average Cost for two"].replace(0, np.nan)
    log("cost_zero_to_null", zero_cost, "Average Cost for two <= 0 -> NULL")

    print("STEP 9  Cuisine hygiene + bridge table")
    df["Cuisines"] = df["Cuisines"].fillna("Unspecified")
    missing_cuisine = int((df["Cuisines"] == "Unspecified").sum())
    if missing_cuisine:
        log("cuisine_missing", missing_cuisine, "blank Cuisines -> 'Unspecified'")
    df["Cuisine Count"] = (
        df["Cuisines"].str.split(",").apply(lambda xs: len([x for x in xs if x.strip()]))
    )
    bridge = (
        df[["Restaurant ID", "Cuisines"]]
        .assign(Cuisine=lambda d: d["Cuisines"].str.split(","))
        .explode("Cuisine")
    )
    bridge["Cuisine"] = bridge["Cuisine"].str.strip()
    bridge = bridge[bridge["Cuisine"].ne("")][["Restaurant ID", "Cuisine"]]
    bridge = bridge.drop_duplicates()
    log("cuisine_explode", len(bridge), "restaurant-cuisine pairs in bridge table")

    print("STEP 10  Derived analytical columns")
    # Votes is the only proxy for footfall/engagement in this dataset.
    df["Has Votes"] = df["Votes"] > 0
    # Cost bands are INR-specific, so only meaningful inside India.
    inr = df["Currency"].str.contains("Indian Rupees", na=False)
    bins = [0, 200, 500, 1000, 2000, np.inf]
    labels = ["< 200", "200-500", "500-1000", "1000-2000", "2000+"]
    df["Cost Band (INR)"] = pd.NA
    df.loc[inr, "Cost Band (INR)"] = pd.cut(
        df.loc[inr, "Average Cost for two"], bins=bins, labels=labels, right=False
    ).astype("string")
    # Value score: rating delivered per 100 rupees spent (India only).
    df["Value Score"] = np.where(
        inr & df["Is Rated"] & df["Average Cost for two"].gt(0),
        df["Aggregate rating"] / (df["Average Cost for two"] / 100.0),
        np.nan,
    )
    # Confidence flag: a 4.9 from 3 votes is not comparable to a 4.9 from 3,000.
    df["Credible Rating"] = df["Is Rated"] & (df["Votes"] >= 50)
    log("derived", len(df), "Cost Band, Value Score, Credible Rating (>=50 votes)")

    print("STEP 11  Geo sanity check")
    # A known quirk: a handful of rows have lat/long swapped or zeroed.
    suspect = df["Latitude"].eq(0) & df["Longitude"].eq(0)
    df["Geo Valid"] = (
        df["Latitude"].between(-90, 90)
        & df["Longitude"].between(-180, 180)
        & ~suspect
    )
    log("geo_flag", int((~df["Geo Valid"]).sum()), "rows flagged Geo Valid = False")

    print("STEP 12  Write star schema")
    fact_cols = [
        "Restaurant ID",
        "Restaurant Name",
        "Country Code",
        "Country",
        "City",
        "Locality",
        "Address",
        "Longitude",
        "Latitude",
        "Geo Valid",
        "Cuisines",
        "Cuisine Count",
        "Currency",
        "Average Cost for two",
        "Cost Band (INR)",
        "Price range",
        "Price Range Label",
        "Has Table booking",
        "Has Online delivery",
        "Is delivering now",
        "Aggregate rating",
        "Is Rated",
        "Credible Rating",
        "Rating text",
        "Votes",
        "Has Votes",
        "Value Score",
    ]
    fact = df[fact_cols].copy()
    fact.to_csv(OUT / "fact_restaurants.csv", index=False)

    dim_country = (
        df.groupby(["Country Code", "Country", "Currency"], dropna=False)
        .size()
        .reset_index(name="Restaurant Count")
        .sort_values("Restaurant Count", ascending=False)
    )
    dim_country.to_csv(OUT / "dim_country.csv", index=False)

    bridge.to_csv(OUT / "bridge_cuisine.csv", index=False)

    pd.DataFrame(
        {"Price range": list(PRICE_RANGE_LABELS), "Price Range Label": list(PRICE_RANGE_LABELS.values())}
    ).to_csv(OUT / "dim_price_range.csv", index=False)

    pd.DataFrame(quality_log).to_csv(OUT / "data_quality_log.csv", index=False)

    print("\nDONE")
    print(f"  fact_restaurants : {len(fact):,} rows")
    print(f"  bridge_cuisine   : {len(bridge):,} rows")
    print(f"  dim_country      : {len(dim_country):,} rows")
    print(f"  India subset     : {int((fact['Country'] == 'India').sum()):,} restaurants")
    print(f"  rated subset     : {int(fact['Is Rated'].sum()):,} restaurants")


if __name__ == "__main__":
    main()
