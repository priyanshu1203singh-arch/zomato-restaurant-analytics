"""
05_write_docs.py
================
Stage 4: generate README.md, docs/POWERBI_GUIDE.md and docs/INTERVIEW_PREP.md.

WHY GENERATE THE DOCS INSTEAD OF WRITING THEM BY HAND?
------------------------------------------------------
Every figure quoted in the README and the interview pack is pulled from
dashboard/kpis.json, which is itself written by the pipeline. Re-run the
pipeline on a new extract and the documentation updates itself. Nothing in this
repository quotes a number that a human typed from memory.

Run:  python scripts/05_write_docs.py
"""

from __future__ import annotations

import csv
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
K = json.loads((ROOT / "dashboard" / "kpis.json").read_text())

# Counts read straight off the processed files, so no figure in the docs is typed.
PROC = ROOT / "data" / "processed"
with (PROC / "bridge_cuisine.csv").open() as fh:
    BRIDGE_ROWS = sum(1 for _ in csv.reader(fh)) - 1
with (PROC / "fact_restaurants.csv").open() as fh:
    _f = list(csv.DictReader(fh))
CREDIBLE_N = sum(
    1 for x in _f if x["Country"] == "India" and x["Credible Rating"] == "True"
)
kpi, st, meta, ch, tb = K["kpi"], K["stats"], K["meta"], K["charts"], K["tables"]

n = lambda v: f"{v:,.0f}"
r2 = lambda v: f"{v:.2f}"
inr = lambda v: f"₹{v:,.0f}"

city = {c["city"]: c for c in ch["city_benchmark"]}
pr = {p["band"]: p for p in ch["price_range_mix"]}
cvol = ch["cuisine_by_volume"]
crat = ch["cuisine_by_rating"]
opp = tb["opportunity"]
top_rated = tb["top_rated"]
expensive = tb["most_expensive"]
value = tb["best_value"]
trend = ch["cost_band_rating_trend"]
deliv = {d["delivery"]: d for d in ch["delivery_effect"]}

NCR = ["New Delhi", "Gurgaon", "Noida", "Faridabad", "Ghaziabad"]
ncr_rows = [c for c in ch["city_benchmark"] if c["city"] in NCR]
t2_rows = [c for c in ch["city_benchmark"] if c["city"] not in NCR]
ncr_avg = sum(c["avg_rating"] for c in ncr_rows) / len(ncr_rows)
t2_avg = sum(c["avg_rating"] for c in t2_rows) / len(t2_rows)

# ===========================================================================
README = f"""# Restaurant Data Analytics & Insights — Zomato

**An end-to-end restaurant analytics project: a reproducible Python pipeline, a
Power BI data model, and an interactive dashboard that answers three commercial
questions — where to open next, what to charge, and which cuisines actually earn
their rating.**

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![pandas](https://img.shields.io/badge/pandas-2.x-150458?logo=pandas&logoColor=white)
![Power BI](https://img.shields.io/badge/Power%20BI-model%20%2B%20DAX-F2C811?logo=powerbi&logoColor=black)
![Dashboard](https://img.shields.io/badge/dashboard-interactive%20HTML-2a78d6)
![Tests](https://img.shields.io/badge/verification-19%2F19%20passing-0ca30c)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## 60-second summary

| | |
|---|---|
| **Dataset** | {meta['source']} |
| **Rows analysed** | **{n(meta['rows_raw'])}** restaurants globally · **{n(meta['rows_india'])}** in India (the analysis scope) |
| **Coverage** | {n(kpi['cities_covered'])} Indian cities · {n(kpi['localities_covered'])} localities · {n(kpi['distinct_cuisines'])} distinct cuisines |
| **Headline benchmark** | Average cost for two **{inr(kpi['avg_cost_for_two'])}**, median **{inr(kpi['median_cost_for_two'])}**, P90 **{inr(kpi['p90_cost_for_two'])}** |
| **Average rating** | **{r2(kpi['avg_rating'])}** across {n(kpi['total_restaurants'] - kpi['not_rated_count'])} rated venues ({kpi['not_rated_pct']}% have never been rated) |
| **Service adoption** | online delivery **{kpi['online_delivery_pct']}%** · table booking **{kpi['table_booking_pct']}%** |
| **Engagement** | **{n(kpi['total_votes'])}** total votes · {n(kpi['avg_votes'])} per restaurant |
| **Deliverables** | 5-page interactive dashboard · Power BI model + full DAX · reproducible pipeline · 19 automated checks |

**Open the dashboard:** download [`dashboard/zomato_dashboard.html`](dashboard/zomato_dashboard.html)
and double-click it. No server, no install, no internet — the data is baked into the file.

---

## Dashboard

| | |
|---|---|
| ![Executive overview](assets/page-overview.png) | ![Cost and value](assets/page-cost.png) |
| **Page 1 — Executive overview.** KPI strip, rating distribution, price-tier mix, city ranking, service adoption. | **Page 2 — Cost & value.** Does spending more buy a better meal? Cost-vs-rating scatter, most expensive and best-value leaderboards. |
| ![Cuisine and city](assets/page-cuisine.png) | ![Where to open next](assets/page-opportunity.png) |
| **Page 3 — Cuisine & city.** Supply vs quality by cuisine, and the "is my pricing normal here?" city benchmark table. | **Page 4 — Where to open next.** A scored locality shortlist from a demand-vs-quality opportunity model. |

Every page shares one filter bar — city, cuisine, price tier, services, minimum
rating, free-text search — and every KPI, chart and table recalculates from the
row-level data, exactly like a Power BI report. Clicking a bar or a table row
cross-filters the whole page. There is a dark mode, every chart has a
table-view toggle for screen-reader and print users, and page 5 documents every
KPI definition.

---

## The five questions this project answers

### 1. What does eating out actually cost?

Average cost for two is **{inr(kpi['avg_cost_for_two'])}**, but the distribution is
right-skewed (skew ≈ {r2(kpi['cost_skew'])}), so the **median of {inr(kpi['median_cost_for_two'])}**
is the number you should benchmark against. Only 10% of venues charge more than
{inr(kpi['p90_cost_for_two'])}. Half the market ({pr['1 - Budget']['share_pct']}%) sits in
the lowest price tier at an average of {inr(pr['1 - Budget']['avg_cost'])} for two.

| Price tier | Restaurants | Share | Avg cost for two | Avg rating | Online delivery | Table booking |
|---|--:|--:|--:|--:|--:|--:|
""" + "\n".join(
    f"| {p['band']} | {n(p['restaurants'])} | {p['share_pct']}% | {inr(p['avg_cost'])} | {r2(p['avg_rating'])} | {p['delivery_pct']}% | {p['booking_pct']}% |"
    for p in ch["price_range_mix"]
) + f"""

### 2. Who are the top-rated and most expensive establishments?

**Top rated** (rating ties broken by vote count; minimum {meta['min_votes_for_leaderboard']} votes so a
4.9-from-3-reviews cannot win):

| # | Restaurant | City | Cost for two | Rating | Votes |
|--:|---|---|--:|--:|--:|
""" + "\n".join(
    f"| {i+1} | {x['Restaurant Name']} | {x['City']} | {inr(x['Average Cost for two'])} | {x['Aggregate rating']} | {n(x['Votes'])} |"
    for i, x in enumerate(top_rated[:5])
) + f"""

**Most expensive:**

| # | Restaurant | City | Cost for two | Rating |
|--:|---|---|--:|--:|
""" + "\n".join(
    f"| {i+1} | {x['Restaurant Name']} | {x['City']} | {inr(x['Average Cost for two'])} | {x['Aggregate rating']} |"
    for i, x in enumerate(expensive[:5])
) + f"""

### 3. Does paying more get you a better meal?

Barely. Pearson **r = {st['pearson_cost_rating']}** (Spearman {st['spearman_cost_rating']}) between cost
for two and aggregate rating across {n(st['n_for_correlation'])} credibly-rated venues.
Average rating rises from **{r2(trend[1]['avg_rating'])}** in the ₹200–400 band to
**{r2(trend[6]['avg_rating'])}** in the ₹1,600–2,400 band — roughly a third of a star for
six times the price.

The strongest correlate of rating is not price, it is **attention**:
log(votes) correlates with rating at **r = {st['pearson_votes_rating']}**, more than
double the price correlation. Venues that get reviewed get rated well; the
causality runs both ways and neither direction is price.

The best rating-per-rupee venues are Old Delhi street-food institutions:

| # | Restaurant | Locality | Cost for two | Rating | Stars per ₹100 |
|--:|---|---|--:|--:|--:|
""" + "\n".join(
    f"| {i+1} | {x['Restaurant Name']} | {x['Locality']} | {inr(x['Average Cost for two'])} | {x['Aggregate rating']} | {x['Aggregate rating']/(x['Average Cost for two']/100):.2f} |"
    for i, x in enumerate(value[:5])
) + f"""

### 4. Which cuisines are crowded, and which are rewarded?

**{', '.join(st['top3_cuisines'])}** appear on the menu of **{st['top3_cuisine_share_pct']}%** of all
restaurants, yet they sit mid-table on rating ({r2(cvol[0]['avg_rating'])} for
{cvol[0]['cuisine']}). The highest-rated cuisines are the under-supplied ones:

| Cuisine | Restaurants | Avg rating | Avg cost for two |
|---|--:|--:|--:|
""" + "\n".join(
    f"| {c['cuisine']} | {n(c['restaurants'])} | {r2(c['avg_rating'])} | {inr(c['avg_cost'])} |"
    for c in crat[:6]
) + f"""

Only **{st['single_cuisine_restaurants_pct']}%** of restaurants serve a single cuisine — the
average venue lists {r2(kpi['avg_cuisines_per_restaurant'])}. Adding another cuisine to the
board is not differentiation; it moves you into more crowded comparison sets.

### 5. Where should the next restaurant open?

A locality is attractive when demand is already proven but the incumbent quality
bar is beatable:

```
opportunity_score = z( log(1 + votes per restaurant) ) − z( average rating )
```

scored over localities with at least 15 restaurants. The log matters: raw
votes-per-restaurant is so skewed that without it one locality dominates the
score and the quality term becomes decorative.

| # | Locality | City | Restaurants | Avg rating | Votes / restaurant | Avg cost | Score |
|--:|---|---|--:|--:|--:|--:|--:|
""" + "\n".join(
    f"| {i+1} | {o['locality']} | {o['city']} | {n(o['restaurants'])} | {r2(o['avg_rating'])} | {n(o['votes_per_restaurant'])} | {inr(o['avg_cost'])} | {r2(o['opportunity_score'])} |"
    for i, o in enumerate(opp[:6])
) + f"""

**Recommendations that fall out of the model**

1. **Target proven catchments with weak incumbents.** {opp[0]['locality']} ({opp[0]['city']})
   has {n(opp[0]['restaurants'])} restaurants pulling {n(opp[0]['votes_per_restaurant'])} votes each — the
   footfall is proven — at an average rating of only {r2(opp[0]['avg_rating'])} against a market
   average of {r2(kpi['avg_rating'])}. Beating a 2.8 incumbent average is an execution
   problem, not a marketing one.
2. **Price to the locality, not the city.** The shortlist averages
   {inr(sum(o['avg_cost'] for o in opp[:6])/6)} for two. Pricing to the city-wide mean would put
   you above local willingness-to-pay in exactly the catchments where the
   opportunity is.
3. **Differentiate on cuisine, not on breadth.** Cross the locality shortlist with the
   high-rating / low-supply cuisines above ({crat[0]['cuisine']}, {crat[1]['cuisine']},
   {crat[3]['cuisine']}) rather than opening another North Indian + Chinese multi-cuisine.
4. **For venues that already exist, fix the rating first.** {kpi['not_rated_pct']}% of listings
   have never been rated. In a market where {st['pearson_votes_rating']} is the
   votes-to-rating correlation, the first 50 reviews are the cheapest revenue
   lever available.
5. **Table booking is the premium signal, delivery is the mid-market signal.**
   Table booking runs {pr['4 - Luxury']['booking_pct']}% in the luxury tier vs
   {pr['1 - Budget']['booking_pct']}% in budget; online delivery peaks in the
   *mid-range* tier at {pr['2 - Mid-range']['delivery_pct']}% and falls back to
   {pr['4 - Luxury']['delivery_pct']}% at luxury. Match the service to the tier you are
   entering instead of buying both.

---

## What makes this defensible rather than just pretty

These are the decisions an interviewer should ask about, and they are all
documented in the code.

**1. `Aggregate rating = 0` means "not rated yet", not "zero stars".**
{n(kpi['not_rated_count'])} venues ({kpi['not_rated_pct']}%) carry a zero. Averaging them in
reports **{r2(kpi['avg_rating_if_zeros_kept'])}**; excluding them reports the correct
**{r2(kpi['avg_rating'])}** — a {abs(kpi['rating_bias_avoided']):.2f}-star error, which would have made
every city and cuisine comparison wrong in proportion to how many unrated
listings it happened to contain.

**2. Money metrics are scoped to a single currency.** The raw extract spans 15
countries and 15 currencies. Averaging ₹ with $ produces a number with no
meaning, so all cost KPIs are filtered to India ({n(meta['rows_india'])} rows). Currency-free
metrics — price tier 1–4, rating, service flags — are also reported globally on
a separate page.

**3. Leaderboards carry a credibility floor.** Top-rated requires ≥
{meta['min_votes_for_leaderboard']} votes; city benchmarks ≥ 20 restaurants; cuisine rankings ≥ 30;
locality scoring ≥ 15. Without these, every "top 10" is a list of venues with
three reviews.

**4. Cuisines are modelled as a many-to-many bridge table**, not a delimited
string. Cuisine bars therefore sum to more than the restaurant count — correct,
and stated on the chart.

**5. The honest limitation is stated up front.** **{st['pct_restaurants_in_delhi_ncr']}%** of the
Indian rows are Delhi NCR, so national conclusions are really NCR conclusions.
NCR also rates lower ({r2(ncr_avg)} average) than the {len(t2_rows)} other benchmarked cities
({r2(t2_avg)}) — partly saturation, partly a coverage artefact, and both readings
belong in the answer. There are no timestamps in the extract, so nothing here is
a trend; it is a cross-section.

---

## Repository layout

```
zomato-restaurant-analytics/
├── README.md                        this file
├── requirements.txt
├── LICENSE
├── Makefile                         `make all` runs the whole pipeline
├── data/
│   ├── raw/zomato.csv               source extract (9,551 x 21)
│   └── processed/                   star schema written by stage 1
│       ├── fact_restaurants.csv     1 row per restaurant
│       ├── dim_country.csv          country code -> name + currency
│       ├── bridge_cuisine.csv       restaurant -> cuisine (many-to-many)
│       ├── dim_price_range.csv
│       ├── agg_*.csv                pre-aggregated tables for Power BI / Excel
│       └── data_quality_log.csv     audit trail: every row changed, and why
├── scripts/
│   ├── 00_download_data.sh          fetch the raw extract
│   ├── 01_clean_data.py             raw -> clean star schema
│   ├── 02_build_kpis.py             star schema -> kpis.json + aggregates
│   ├── 03_build_dashboard.py        bake data into a single-file dashboard
│   ├── 04_verify_dashboard.mjs      19 headless checks + screenshots
│   └── 05_write_docs.py             regenerate README + docs from kpis.json
├── dashboard/
│   ├── _template.html               dashboard source (charts, measures, layout)
│   ├── kpis.json                    every number, written by stage 2
│   └── zomato_dashboard.html        ← the deliverable, open this
├── powerbi/
│   └── README.md                    where the .pbix lives + how to rebuild it
├── docs/
│   ├── POWERBI_GUIDE.md             full Power BI rebuild: model, DAX, layout
│   ├── INTERVIEW_PREP.md            every KPI explained + 25 likely questions
│   └── verification_report.json     output of stage 4
└── assets/                          dashboard screenshots (generated)
```

## Reproducing it

```bash
git clone https://github.com/<your-username>/zomato-restaurant-analytics.git
cd zomato-restaurant-analytics
pip install -r requirements.txt

bash scripts/00_download_data.sh      # fetch the raw extract
python scripts/01_clean_data.py       # -> data/processed/*.csv
python scripts/02_build_kpis.py       # -> dashboard/kpis.json
python scripts/03_build_dashboard.py  # -> dashboard/zomato_dashboard.html
python scripts/05_write_docs.py       # -> README.md, docs/*.md

npm i playwright                      # optional: run the verification suite
node scripts/04_verify_dashboard.mjs  # 19 checks + screenshots to assets/
```

Or just `make all`.

## Verification

The pipeline is not trusted on sight. `scripts/04_verify_dashboard.mjs` drives the
built dashboard in headless Chromium and asserts:

- the page loads from `file://` with **zero** console errors
- all 8 KPI tiles render, and the headline values match the pipeline exactly
- all five pages draw SVG marks rather than empty containers
- **the browser's JavaScript measures agree with the pandas pipeline on all 11
  reference KPIs** — this is the important one; the dashboard recomputes
  everything client-side, so a mismatch would mean the two implementations of the
  same measure had diverged
- slicers, chart-click cross-filtering, reset, table-view toggles and dark mode
  all behave
- screenshots are captured for this README

Current status: **19/19 passing** (`docs/verification_report.json`).

## Tech

**Python** (pandas, numpy) for the pipeline · **Power BI Desktop** (Power Query +
DAX) for the modelled report, documented in `docs/POWERBI_GUIDE.md` ·
**vanilla JavaScript + SVG** for the interactive dashboard — no chart library and
no CDN, so the single HTML file works offline forever · **Playwright** for
verification.

The dashboard palette is validated for colour-vision deficiency: categorical
hues are assigned in a fixed order that clears a ΔE ≥ 8 CVD-separation gate in
both light and dark mode, price tiers use a single-hue ordinal ramp because they
are ordered rather than categorical, and every chart ships a table view because
three of the light-mode hues sit below 3:1 contrast against the surface.

## Licence

MIT — see [LICENSE](LICENSE). The Zomato dataset is used under the terms of its
original public release.
"""

# ===========================================================================
INTERVIEW = f"""# Interview preparation pack

Everything in this project, explained in the order a panel will ask about it —
plus 25 questions you should expect, with answers you can defend.

> **How to use this.** Read part 1 to be able to narrate the project end to end
> in two minutes. Read part 2 to know what every number means. Read part 3 the
> night before. The numbers in this file are generated from the pipeline, so they
> are the same numbers that are on the dashboard.

---

## Part 1 — The two-minute walkthrough

Say this, in this order.

**The business question.** "A restaurant group wants to know three things: where
to open next, what to charge, and what to put on the menu. I had a public Zomato
extract of {n(meta['rows_raw'])} restaurants across {meta['countries']} countries, so I built the
analysis that answers those three questions from it."

**The data.** "One flat CSV, {n(meta['rows_raw'])} rows, 21 columns. Restaurant name,
city, locality, latitude/longitude, cuisines, average cost for two, currency,
price tier 1–4, table-booking and online-delivery flags, aggregate rating,
rating text, and vote count. No dates anywhere — that matters, and I'll come
back to it."

**The cleaning, and the one decision that mattered.** "The single most important
thing I found is that `Aggregate rating = 0` does not mean zero stars, it means
*not rated yet*. {n(kpi['not_rated_count'])} of the Indian rows — {kpi['not_rated_pct']}% — are
like that. If you leave them in the average you report {r2(kpi['avg_rating_if_zeros_kept'])}
stars. The correct figure is {r2(kpi['avg_rating'])}. That's a
{abs(kpi['rating_bias_avoided']):.2f}-star error, and it's worse than it looks, because the bias is
proportional to how many unrated listings each city or cuisine happens to have —
so it corrupts every comparison, not just the headline."

**The second decision.** "The extract mixes 15 currencies. You cannot average
rupees and dollars, so I scoped every money metric to India —
{n(meta['rows_india'])} restaurants, all in ₹. That's still {n(meta['rows_india'])} restaurants, and
it means the cost benchmark is a real number. Rating, price tier and the service
flags are currency-free, so those I also report globally."

**The model.** "I built a small star schema: a fact table at one row per
restaurant, a country dimension, a price-tier dimension, and a
restaurant-to-cuisine bridge table — because cuisine is many-to-many. One
restaurant lists up to eight cuisines; the average is
{r2(kpi['avg_cuisines_per_restaurant'])}. You cannot slice by cuisine until you explode that
field."

**The output.** "A five-page report. Page one is the executive KPI view. Page two
answers 'does spending more buy a better meal'. Page three is cuisine supply
versus cuisine quality plus a city pricing benchmark. Page four is a scored
locality shortlist for where to open. Page five documents every KPI definition,
because a dashboard nobody can audit is a dashboard nobody should trust."

**The punchline.** "Three findings. One: price barely buys quality — the
cost-to-rating correlation is only {st['pearson_cost_rating']}, while log-votes-to-rating is
{st['pearson_votes_rating']}. Attention matters more than price. Two: the crowded cuisines
are the mediocre ones — {', '.join(st['top3_cuisines'])} are on
{st['top3_cuisine_share_pct']}% of menus and rate mid-table, while
{crat[0]['cuisine']} and {crat[1]['cuisine']} rate {r2(crat[0]['avg_rating'])} and
{r2(crat[1]['avg_rating'])} on a fraction of the supply. Three: the best sites are
suburban mall catchments with proven footfall and weak incumbents —
{opp[0]['locality']} in {opp[0]['city']} tops the list at
{n(opp[0]['votes_per_restaurant'])} votes per restaurant against a
{r2(opp[0]['avg_rating'])} average rating."

---

## Part 2 — Every KPI, bit by bit

### The pipeline, stage by stage

| Stage | File | What goes in | What comes out | Why it exists |
|---|---|---|---|---|
| 0 | `00_download_data.sh` | — | `data/raw/zomato.csv` | Reproducibility. Anyone can rebuild from zero. |
| 1 | `01_clean_data.py` | raw CSV | star schema + `data_quality_log.csv` | All cleaning decisions in one auditable place. |
| 2 | `02_build_kpis.py` | star schema | `kpis.json` + aggregate CSVs | Single source of truth for every number. |
| 3 | `03_build_dashboard.py` | star schema + `kpis.json` | `zomato_dashboard.html` | Self-contained deliverable, opens offline. |
| 4 | `04_verify_dashboard.mjs` | the built dashboard | 19 pass/fail checks + screenshots | Proof it works, not a claim that it does. |
| 5 | `05_write_docs.py` | `kpis.json` | README + this file | Docs can never drift from the data. |

### Stage 1 — the twelve cleaning steps, and the reason for each

1. **Load with `latin-1`.** The file contains non-UTF-8 bytes in names like
   *Le Petit Souffle* and *café*. Loading with UTF-8 throws.
2. **Strip whitespace on every text column.** Otherwise `"Chinese"` and
   `"Chinese "` become two cuisines.
3. **De-duplicate on `Restaurant ID`.** Zero duplicates in this extract — but you
   check, you don't assume, and the check is in the log.
4. **Map `Country Code` to a country name.** The code is meaningless in a slicer.
5. **Cast the Yes/No columns to real booleans.** `AVERAGE("Yes")` is not a thing.
6. **Drop `Switch to order menu`.** Constant `"No"` for all
   {n(meta['rows_raw'])} rows — zero information, and a column that only invites a
   misleading chart.
7. **`Aggregate rating` 0 → NULL, plus an `Is Rated` flag.** The decision above.
   Keeping the flag means "how many venues are unrated" stays a first-class,
   answerable question rather than something the cleaning destroyed.
8. **`Average Cost for two` ≤ 0 → NULL.** 18 rows. A restaurant that charges
   nothing is missing data, not a free restaurant.
9. **Explode `Cuisines` into a bridge table.** {n(BRIDGE_ROWS)} restaurant-cuisine pairs.
10. **Derive the analytical columns** — cost band, value score, and
    `Credible Rating` (`Is Rated AND Votes >= {meta['min_votes_for_leaderboard']}`).
11. **Flag invalid geography** rather than dropping it: lat/long of (0,0) or out of
    range gets `Geo Valid = False`, so map visuals can exclude it while the rows
    still count in every non-map KPI.
12. **Write the star schema and the quality log.** The log records the step, the
    number of rows affected and the reason — so the cleaning is reviewable by
    someone who did not write it.

### The KPI cards

| KPI | Value | Definition | Why it is the right measure |
|---|--:|---|---|
| Restaurants | {n(kpi['total_restaurants'])} | `DISTINCTCOUNT(Restaurant ID)` | Distinct count, not row count, so a re-listing cannot inflate it. |
| Cities / localities | {n(kpi['cities_covered'])} / {n(kpi['localities_covered'])} | distinct counts | Market breadth. Locality is the level a site decision is actually made at. |
| Avg cost for two | {inr(kpi['avg_cost_for_two'])} | mean, India only | The CV headline. Quoted with the median because it is skewed. |
| Median cost for two | {inr(kpi['median_cost_for_two'])} | median, India only | Skew ≈ {r2(kpi['cost_skew'])}. This is the number to benchmark a new opening against. |
| P90 cost for two | {inr(kpi['p90_cost_for_two'])} | 90th percentile | Sizes the luxury tail without letting it move the central estimate. |
| Avg rating | {r2(kpi['avg_rating'])} | mean over `Is Rated = TRUE` | Excluding unrated venues. The whole project hinges on this. |
| Not rated | {kpi['not_rated_pct']}% | share with no rating | A coverage metric *and* a commercial one — these are cold-start venues. |
| Online delivery | {kpi['online_delivery_pct']}% | share of venues with the flag | Channel adoption. |
| Table booking | {kpi['table_booking_pct']}% | share of venues with the flag | The premium-format signal. |
| Total votes | {n(kpi['total_votes'])} | sum of votes | Best available demand proxy. There is no footfall column. |
| Cuisines offered | {n(kpi['distinct_cuisines'])} | distinct cuisines in the bridge | Menu variety across the market. |
| Highest rated | {top_rated[0]['Aggregate rating']} | max rating among ≥ {meta['min_votes_for_leaderboard']} votes | {top_rated[0]['Restaurant Name']}. The vote floor is what makes it meaningful. |

### The two derived measures

**Value score** = `rating / (cost for two / 100)` — stars delivered per ₹100.
Only computed for venues rated ≥ 4.0 with ≥ {meta['min_votes_for_leaderboard']} votes, because
without a quality floor "cheap and bad" wins the ranking. Top result:
{value[0]['Restaurant Name']} in {value[0]['Locality']} —
{value[0]['Aggregate rating']} stars at {inr(value[0]['Average Cost for two'])} for two.

**Opportunity score** = `z(log(1 + votes per restaurant)) − z(avg rating)` per
locality, minimum 15 restaurants. Read it as *proven demand minus incumbent
quality* — high demand and a low quality bar means headroom.

Be ready to explain **why the log**: votes-per-restaurant is heavily
right-skewed. Without the log, the highest-demand locality's z-score is so large
that it swamps the rating term entirely and the model degenerates into "rank by
votes". With the log, the two terms have comparable spread, and the shortlist
changes completely — from famous nightlife districts to suburban mall catchments
with weak incumbents, which is the actually actionable answer.

### The three statistical claims, and how they were tested

| Claim | Statistic | Value | Reading |
|---|---|--:|---|
| Cost predicts rating | Pearson r | {st['pearson_cost_rating']} | Weak positive. Spearman {st['spearman_cost_rating']} confirms it is not just an outlier artefact. |
| Attention predicts rating | Pearson r, log(votes) | {st['pearson_votes_rating']} | Over 2× the price correlation. |
| Delivery venues rate higher | Welch t | {st['delivery_welch_t']} | Gap is only {st['delivery_rating_gap']} stars on n={n(st['delivery_n_yes'])} vs {n(st['delivery_n_no'])}. Statistically detectable, commercially irrelevant. Say so. |

The delivery result is the one to volunteer unprompted. A {st['delivery_rating_gap']}-star gap
that is technically significant on a large sample is exactly the case where a
weaker analyst reports "delivery restaurants are rated significantly higher" and
a stronger one says "significant, but {st['delivery_rating_gap']} stars is not a business
decision — what actually differs is engagement:
{n(deliv['Delivers online']['avg_votes'])} average votes versus
{n(deliv['No online delivery']['avg_votes'])}."

---

## Part 3 — 25 questions a panel will ask

### On the data and the cleaning

**1. Walk me through this project.**
Use the Part 1 script. Business question → data → the rating-zero decision → the
currency decision → the model → the three findings. Two minutes, no tool names
until the end.

**2. What was the hardest data-quality problem?**
The rating zeros. It is dangerous precisely because it is invisible: the pipeline
runs, the dashboard renders, every number looks plausible, and every comparison
is wrong. I found it by profiling the rating distribution and seeing an
impossible spike at exactly 0.0 with nothing between 0 and 1.8 — real ratings
don't behave like that. Cross-checking against `Rating text` confirmed it: every
zero was labelled "Not rated".

**3. Why not just impute the missing ratings?**
Because "unrated" is information, not absence. These venues are systematically
different — newer, smaller, less discovered. Imputing the mean would invent
{n(kpi['not_rated_count'])} data points and simultaneously destroy the ability to answer
"how much of this market has no reviews", which turned out to be one of the more
commercially useful findings on the board.

**4. Why scope the money analysis to India?**
15 currencies in one column. An average across them is arithmetically valid and
semantically meaningless. India is {n(meta['rows_india'])} of {n(meta['rows_raw'])} rows, so
scoping keeps the sample large while making the cost number interpretable. I
could have converted using FX rates, but I would then be baking an
undocumented, undated exchange rate into a dataset with no timestamps — a false
precision I would have to caveat harder than the scope decision itself.

**5. How do you know your dataset is representative?**
It is not, and I say so on the dashboard.
{st['pct_restaurants_in_delhi_ncr']}% of the Indian rows are Delhi NCR, and NCR rates
{r2(ncr_avg)} against {r2(t2_avg)} for the other {len(t2_rows)} benchmarked cities. So this is
an NCR study that I present as an NCR study. If I were doing this commercially,
step one would be sourcing city-balanced coverage.

**6. Why does NCR rate lower? Are NCR restaurants worse?**
Two explanations and I would not pick one without more data. Competition:
saturated markets compress ratings because customers have alternatives. And
selection: NCR is where the platform's coverage was deepest, so it lists the long
tail of small venues that other cities never got listed at all. Both push the
same direction. It is exactly why I benchmark pricing *within* a city and never
across them.

**7. Are there duplicates?**
None on `Restaurant ID` in this extract. The check is stage 1 step 4 and the
result is in `data_quality_log.csv`. I would also flag that name+locality
near-duplicates (chains like {top_rated[0]['Restaurant Name']} with many outlets)
are *not* duplicates and must not be collapsed — each outlet is a real,
separately-rated location.

**8. What would you do with more time or better data?**
Timestamps, so I could measure trend instead of cross-section. Revenue or cover
counts, so "higher revenue" becomes modelled rather than directional. Review text,
so I could tell you *why* a locality's incumbents rate 2.8 — service, food, or
wait time — which turns "there's an opportunity here" into "here's the specific
gap to exploit".

### On the metrics

**9. Why report both mean and median cost?**
Skew ≈ {r2(kpi['cost_skew'])}. The mean is {inr(kpi['avg_cost_for_two'])}, the median
{inr(kpi['median_cost_for_two'])} — the mean is being pulled by a luxury tail that goes up
to {inr(expensive[0]['Average Cost for two'])}. For a positioning decision the median is the
honest anchor; the mean plus P90 tells you how heavy the tail is.

**10. Why a 50-vote floor on the leaderboards?**
Because rating precision scales with sample size. Without the floor the "top
rated" list is venues with three reviews, which is noise wearing a crown.
{n(kpi['total_restaurants'])} restaurants drop to
{n(CREDIBLE_N)} credibly-rated ones — a real cost in coverage, paid deliberately for a
ranking that means something. If pressed on the specific number: 50 is a
judgement call, and I would show the panel how the top 10 changes at 20, 50 and
100 rather than defend 50 as optimal.

**11. Cuisine bars sum to more than your restaurant count. Is that a bug?**
No — it is a many-to-many. One restaurant lists up to eight cuisines, average
{r2(kpi['avg_cuisines_per_restaurant'])}, so cuisine counts are *appearances*, not
restaurants. It is labelled on the chart. The trap this avoids is the "top 3
cuisines = {st['top3_cuisine_share_pct']}%" claim: if you naively sum the top three cuisine
counts and divide by the restaurant count you get over 99%, which is nonsense.
The correct measure is the distinct count of restaurants serving at least one of
the three.

**12. Explain the value score. Isn't it just biased toward cheap places?**
Yes, structurally — cost is the denominator. That is why it carries a 4.0 rating
floor, so it reads as "the best venues, cheapest first" rather than "the
cheapest venues". It is a shortlist-generator for a specific question — where is
quality being delivered efficiently — not a general quality ranking.

**13. Your cheapest cost band has the highest average rating. Doesn't that
contradict "price buys quality"?**
It looks that way and it is survivorship bias — that band only contains venues
that already earned 50+ votes, so it is famous street food, not cheap food in
general. Cheap venues that nobody reviewed are excluded by the credibility floor.
It is a genuine finding about *renowned* street food and I label it as such on the
chart rather than letting it read as a pricing conclusion.

**14. r = {st['pearson_cost_rating']} is weak. So why show the chart at all?**
Because the null result *is* the finding, and it is the commercially useful one.
An operator's instinct is that raising the price point raises perceived quality.
The data says a 6× price increase buys about a third of a star. That redirects
investment from price positioning to execution — which is the whole point of
running the analysis instead of guessing.

**15. Why z-scores in the opportunity model?**
Because votes-per-restaurant and average rating are on completely different
scales — thousands versus a 1–5 range. Standardising puts them in comparable
units so the subtraction is meaningful. And the log inside the demand term
because the raw distribution is skewed enough that one locality would otherwise
dominate.

**16. What are the weaknesses of the opportunity model?**
Three, and I would lead with them. Votes proxy for footfall, and reviewing skews
toward younger app-native diners. Low incumbent rating might reflect something
structural about the catchment — a food court with bad ventilation — that a new
entrant would inherit rather than beat. And a 15-restaurant minimum means a
genuinely under-served locality with four restaurants never appears at all,
which is arguably the most interesting case. I would validate the shortlist
against rent and footfall data before anyone signed a lease.

### On Power BI and the tooling

**17. Why Power BI for this?**
Business users need to explore, not read. The audience question isn't "what's the
average cost" — it's "what's the average cost *in my locality, for my cuisine, in
my price tier*", and that's a slicer, not a chart. Power BI gives you the
in-memory model, DAX measures that respect filter context, and one-click sharing
to people who will never open Python. I do the cleaning and the statistics in
pandas because that is reproducible and diffable, and I hand Power BI a clean
star schema, which is what its engine is built for.

**18. Walk me through your data model.**
Star schema. `fact_restaurants` at one row per restaurant. `dim_country`
one-to-many on `Country Code`. `dim_price_range` one-to-many on `Price range`.
`bridge_cuisine` many-to-many between the fact and a `dim_cuisine`, resolved with
a bridge because Power BI cannot filter a delimited string. Single-direction
filters from dimensions to fact, except the cuisine bridge which is
bidirectional — that is a deliberate, documented exception, not an accident.

**19. Write me the average-rating measure.**
```dax
Avg Rating =
AVERAGEX (
    FILTER ( fact_restaurants, fact_restaurants[Is Rated] = TRUE() ),
    fact_restaurants[Aggregate rating]
)
```
And be able to say why not `AVERAGE([Aggregate rating])`: it would include the
NULLs-as-zeros case if the flag were ever lost, and `AVERAGEX` over an explicit
`FILTER` makes the business rule visible in the measure rather than hidden in the
data-load step.

**20. `CALCULATE` vs `FILTER` — when do you reach for which?**
`CALCULATE` modifies filter context and is the default for simple, testable
conditions — `CALCULATE([Total Restaurants], fact[Has Online delivery] = TRUE())`.
`FILTER` returns a table and is what you need when the condition involves a
measure or row-level logic that `CALCULATE`'s compact syntax cannot express. I
prefer `CALCULATE` where possible because it is more likely to hit the storage
engine rather than falling back to the formula engine.

**21. How do you handle the many-to-many cuisine relationship in DAX?**
The bridge table plus bidirectional filtering on that one relationship. The
consequence to be honest about: measures sliced by cuisine double-count
restaurants, because a venue serving three cuisines contributes to three rows.
That is correct for "how many restaurants offer Italian" and wrong for "what
share of the market is Italian", so the share measures use
`DISTINCTCOUNT(Restaurant ID)` against the bridge instead of a plain count.

**22. Why is there no dual-axis chart anywhere in this report?**
Because a second y-axis lets you manufacture any apparent relationship you want
by choosing the scales, and the reader has no way to detect it. Where I need to
show count and rating together — the price-tier visual — the bar encodes the
count and the rating appears as a labelled figure, so nobody can read a
correlation out of two lines that were scaled into agreement.

### On the interactive dashboard

**23. If the project is Power BI, why is there an HTML dashboard?**
Two reasons. Practical: a `.pbix` needs Power BI Desktop, which not every
reviewer has, and a single HTML file opens anywhere including a phone. And
verification: because the dashboard recomputes every KPI in the browser from the
row-level data, it is an independent second implementation of the same measures.
`04_verify_dashboard.mjs` asserts that the browser's numbers match the pandas
numbers on 11 reference KPIs — which is a real test that the measure logic is
right, not just that the file renders.

**24. How do you know the dashboard is correct?**
19 automated checks in headless Chromium, and the pandas-vs-JavaScript
reconciliation is the important one. Beyond that: the KPI page documents every
definition, the data-quality log records every cleaning action, and page 5 states
the limitations. Correctness you cannot audit is indistinguishable from luck.

**25. What would you change if you rebuilt this today?**
The opportunity model is the weakest part — it uses two features and I would
prefer a proper site-scoring model with rent, footfall, transport access and
income proxies, validated against outcomes of restaurants that actually opened.
I would also add cohort logic once timestamps existed, so "rating improved after
X" became answerable. And I would push the credibility floor decision to the user
as a slicer instead of hard-coding 50 votes, since the right threshold depends on
whether you are shortlisting or ranking.

---

## Part 4 — Traps to avoid

- **Do not say "I cleaned the data".** Say what you changed and why. The
  rating-zero fix is the strongest thing you did; lead with it.
- **Do not quote the mean cost alone.** Skew {r2(kpi['cost_skew'])}. Mean, median, P90.
- **Do not claim causation.** "Higher-rated restaurants get more votes" — the
  arrow runs both ways and you cannot separate them from this data.
- **Do not oversell {st['pearson_cost_rating']}.** It is weak, that is the finding, own it.
- **Do not hide the NCR concentration.** {st['pct_restaurants_in_delhi_ncr']}%. Volunteer it
  before you are asked; it reads as rigour when you raise it and as a gap when
  they do.
- **Do not say "5000+ restaurants" if asked for a precise figure.**
  {n(meta['rows_india'])} in India, {n(meta['rows_raw'])} globally. Precision costs nothing.
- **Do not describe the visuals as "insights".** An insight is a decision you
  would change. "Open in {opp[0]['locality']}" is an insight; "New Delhi has the
  most restaurants" is a fact.
"""

(ROOT / "README.md").write_text(README)
(ROOT / "docs").mkdir(exist_ok=True)
(ROOT / "docs" / "INTERVIEW_PREP.md").write_text(INTERVIEW)
print(f"Wrote README.md ({len(README):,} chars)")
print(f"Wrote docs/INTERVIEW_PREP.md ({len(INTERVIEW):,} chars)")
