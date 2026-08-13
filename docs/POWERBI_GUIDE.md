# Power BI rebuild guide

How to build this report in Power BI Desktop from the files in `data/processed/`.
Follow it top to bottom and you get the same five pages as the HTML dashboard,
with the same numbers.

**Before you start:** run `python scripts/01_clean_data.py` and
`python scripts/02_build_kpis.py`. That produces the four model tables and the
reference KPI values you will check your measures against.

---

## Contents

1. [Load the data](#1-load-the-data)
2. [Power Query transformations](#2-power-query-transformations)
3. [The data model](#3-the-data-model)
4. [Every DAX measure](#4-every-dax-measure)
5. [Calculation groups and helper tables](#5-calculation-groups-and-helper-tables)
6. [Page-by-page build](#6-page-by-page-build)
7. [Slicers, sync and bookmarks](#7-slicers-sync-and-bookmarks)
8. [Formatting and theme](#8-formatting-and-theme)
9. [Validating your model against the pipeline](#9-validating-your-model-against-the-pipeline)
10. [Performance notes](#10-performance-notes)

---

## 1. Load the data

**Home → Get data → Text/CSV**, and load these four files from
`data/processed/`:

| File | Table name in the model | Grain |
|---|---|---|
| `fact_restaurants.csv` | `fact_restaurants` | 1 row per restaurant |
| `dim_country.csv` | `dim_country` | 1 row per country code |
| `bridge_cuisine.csv` | `bridge_cuisine` | 1 row per restaurant-cuisine pair |
| `dim_price_range.csv` | `dim_price_range` | 4 rows |

Set the file encoding to **65001: Unicode (UTF-8)** — the pipeline writes UTF-8
even though the raw source was latin-1.

> **Why load the *processed* files and not the raw CSV?** Because the cleaning
> decisions — the rating-zero fix, the currency scope, the cuisine explode — are
> business logic, and business logic belongs in version-controlled, testable
> code, not in a Power Query step nobody can diff. Power BI's job here is the
> model and the presentation layer.

---

## 2. Power Query transformations

The heavy cleaning already happened in Python, so Power Query only does the
model-shaping Power BI needs.

### 2.1 `fact_restaurants`

In **Transform Data**, apply in this order:

1. **Set data types explicitly.** Do not trust detection.

   | Column | Type |
   |---|---|
   | `Restaurant ID` | Whole Number |
   | `Restaurant Name`, `Country`, `City`, `Locality`, `Address`, `Cuisines`, `Currency`, `Rating text`, `Price Range Label`, `Cost Band (INR)` | Text |
   | `Longitude`, `Latitude`, `Aggregate rating`, `Value Score` | Decimal Number |
   | `Average Cost for two`, `Votes`, `Price range`, `Country Code` | Whole Number |
   | `Is Rated`, `Credible Rating`, `Has Table booking`, `Has Online delivery`, `Is delivering now`, `Geo Valid` | True/False |

   The nullable columns (`Aggregate rating`, `Average Cost for two`,
   `Value Score`, `Cost Band (INR)`) will contain blanks. That is correct and
   intentional — do **not** replace them with 0.

2. **Mark the geography columns.** Select `City` → Column tools → Data category
   → **City**. Same for `Latitude` → **Latitude**, `Longitude` → **Longitude`.
   Without this the map visual guesses, and it guesses badly on Indian localities.

3. **Disable "Column profiling based on top 1000 rows"** (bottom status bar →
   switch to *entire dataset*) so the profiler tells you the truth while you work.

4. **Add a sort column for the cost band** so `< 200` sorts before `1000-2000`
   instead of alphabetically:

   ```m
   = Table.AddColumn(#"Previous Step", "Cost Band Sort", each
       if [#"Cost Band (INR)"] = "< 200"      then 1
       else if [#"Cost Band (INR)"] = "200-500"   then 2
       else if [#"Cost Band (INR)"] = "500-1000"  then 3
       else if [#"Cost Band (INR)"] = "1000-2000" then 4
       else if [#"Cost Band (INR)"] = "2000+"     then 5
       else 99, Int64.Type)
   ```

   Then **Column tools → Sort by column → Cost Band Sort** on
   `Cost Band (INR)`.

5. **Uncheck "Include in report refresh"** for nothing — all four tables should
   refresh.

### 2.2 `dim_cuisine` — create it from the bridge

`bridge_cuisine.csv` has the pairs but no cuisine dimension. Build one:

1. Right-click `bridge_cuisine` → **Reference** → rename to `dim_cuisine`.
2. **Home → Choose Columns** → keep only `Cuisine`.
3. **Home → Remove Rows → Remove Duplicates**.
4. Sort ascending on `Cuisine`.

You now have a 90-row dimension. This is the table your cuisine slicer binds to.

### 2.3 `dim_city` — optional but recommended

Same pattern from `fact_restaurants`: Reference → keep `City`, `Country` →
Remove Duplicates. Gives you a clean city slicer that does not depend on the
fact table's filter context.

---

## 3. The data model

**Model view → Manage relationships.** Build exactly these:

| From | To | Cardinality | Cross-filter | Active |
|---|---|---|---|---|
| `dim_country[Country Code]` | `fact_restaurants[Country Code]` | One to many | Single | Yes |
| `dim_price_range[Price range]` | `fact_restaurants[Price range]` | One to many | Single | Yes |
| `dim_city[City]` | `fact_restaurants[City]` | One to many | Single | Yes |
| `fact_restaurants[Restaurant ID]` | `bridge_cuisine[Restaurant ID]` | One to many | Single | Yes |
| `dim_cuisine[Cuisine]` | `bridge_cuisine[Cuisine]` | One to many | **Both** | Yes |

```
  dim_country ──┐
  dim_city ─────┤
  dim_price_range ──> fact_restaurants ──> bridge_cuisine <──> dim_cuisine
                                                          (bidirectional)
```

### Why the cuisine relationship is bidirectional

A restaurant serves many cuisines and a cuisine is served by many restaurants.
Power BI cannot filter a comma-delimited string, so cuisine is resolved through
a bridge. For a slicer on `dim_cuisine[Cuisine]` to filter `fact_restaurants`,
the filter has to travel *up* the bridge to the fact — and that requires
bidirectional cross-filtering on the `dim_cuisine → bridge_cuisine`
relationship.

**Be able to state the cost of this.** Bidirectional filters can create
ambiguous paths in larger models and they slow the engine down. Here there is
exactly one bidirectional relationship, on a 19,714-row bridge, and no other
path between `dim_cuisine` and the fact — so there is no ambiguity. In a bigger
model the alternative is `CROSSFILTER()` inside the specific measures that need
it, which keeps the model single-direction by default.

**Hide from report view** (right-click → Hide): `bridge_cuisine[Restaurant ID]`,
`fact_restaurants[Country Code]`, `fact_restaurants[Address]`,
`fact_restaurants[Cost Band Sort]`. A field list a user cannot misuse is a
better field list.

---

## 4. Every DAX measure

Create a dedicated measure table so measures do not clutter the fact table:
**Home → Enter data** → one table named `_Measures`, one dummy column, load,
then hide the column.

### 4.1 Base counts

```dax
Total Restaurants =
DISTINCTCOUNT ( fact_restaurants[Restaurant ID] )
```
`DISTINCTCOUNT`, not `COUNTROWS`. Sliced by cuisine, the fact table is reached
through the bridge and a three-cuisine restaurant would otherwise be counted
three times.

```dax
Cities Covered   = DISTINCTCOUNT ( fact_restaurants[City] )
Localities       = DISTINCTCOUNT ( fact_restaurants[Locality] )
Cuisines Offered = DISTINCTCOUNT ( bridge_cuisine[Cuisine] )
```

### 4.2 The rating measures — the important ones

```dax
Rated Restaurants =
CALCULATE ( [Total Restaurants], fact_restaurants[Is Rated] = TRUE() )
```

```dax
Avg Rating =
AVERAGEX (
    FILTER ( fact_restaurants, fact_restaurants[Is Rated] = TRUE() ),
    fact_restaurants[Aggregate rating]
)
```

**Why not `AVERAGE ( fact_restaurants[Aggregate rating] )`?** In this model it
would give the same answer, because the pipeline already turned the zeros into
blanks and `AVERAGE` ignores blanks. It is still the wrong measure to write:
the business rule "unrated venues are excluded" should be *visible in the
measure*, so that a future refresh which loses the null-conversion cannot
silently change every rating on the report. Encoding the rule twice is cheap
insurance.

```dax
Avg Rating (naive, for the docs only) =
AVERAGEX ( fact_restaurants, COALESCE ( fact_restaurants[Aggregate rating], 0 ) )
```
Keep this measure. Put it on the method page next to `Avg Rating` to show the
0.83-star bias you avoided. A measure that demonstrates *why* your other
measure is right is worth its space.

```dax
Not Rated Restaurants =
CALCULATE ( [Total Restaurants], fact_restaurants[Is Rated] = FALSE() )

Not Rated % =
DIVIDE ( [Not Rated Restaurants], [Total Restaurants] )

Credible Ratings =
CALCULATE ( [Total Restaurants], fact_restaurants[Credible Rating] = TRUE() )
```

Always `DIVIDE()`, never `/`. `DIVIDE` returns blank on a zero denominator
instead of an error, which matters the moment a slicer selection is empty.

### 4.3 Cost measures (India scope)

```dax
Avg Cost for Two =
CALCULATE (
    AVERAGE ( fact_restaurants[Average Cost for two] ),
    KEEPFILTERS ( fact_restaurants[Currency] = "Indian Rupees(Rs.)" )
)
```

`KEEPFILTERS` so a currency slicer the user set is respected rather than
overwritten. Scoping on `Currency` rather than `Country` is deliberate: the
metric is only valid within one currency, so the filter should name the actual
constraint.

```dax
Median Cost for Two =
CALCULATE (
    MEDIAN ( fact_restaurants[Average Cost for two] ),
    KEEPFILTERS ( fact_restaurants[Currency] = "Indian Rupees(Rs.)" )
)

P90 Cost for Two =
CALCULATE (
    PERCENTILE.INC ( fact_restaurants[Average Cost for two], 0.90 ),
    KEEPFILTERS ( fact_restaurants[Currency] = "Indian Rupees(Rs.)" )
)

Max Cost for Two =
CALCULATE (
    MAX ( fact_restaurants[Average Cost for two] ),
    KEEPFILTERS ( fact_restaurants[Currency] = "Indian Rupees(Rs.)" )
)
```

```dax
Cost Skew Flag =
VAR M    = [Avg Cost for Two]
VAR Med  = [Median Cost for Two]
RETURN
IF (
    DIVIDE ( M - Med, Med ) > 0.2,
    "Right-skewed — quote the median",
    "Roughly symmetric — the mean is safe"
)
```
Put that in a card next to the cost KPI. It turns a statistical caveat into
something a business reader acts on.

### 4.4 Service adoption

```dax
Online Delivery % =
DIVIDE (
    CALCULATE ( [Total Restaurants], fact_restaurants[Has Online delivery] = TRUE() ),
    [Total Restaurants]
)

Table Booking % =
DIVIDE (
    CALCULATE ( [Total Restaurants], fact_restaurants[Has Table booking] = TRUE() ),
    [Total Restaurants]
)
```

### 4.5 Engagement

```dax
Total Votes = SUM ( fact_restaurants[Votes] )
Avg Votes   = AVERAGE ( fact_restaurants[Votes] )

Votes per Restaurant =
DIVIDE ( [Total Votes], [Total Restaurants] )
```

### 4.6 Leaderboard measures

```dax
Top Rated Restaurant =
VAR Credible =
    FILTER ( fact_restaurants, fact_restaurants[Credible Rating] = TRUE() )
VAR Best = MAXX ( Credible, fact_restaurants[Aggregate rating] )
RETURN
CALCULATE (
    SELECTEDVALUE ( fact_restaurants[Restaurant Name] ),
    TOPN ( 1, Credible, fact_restaurants[Aggregate rating], DESC,
                        fact_restaurants[Votes], DESC )
)

Highest Rating (credible) =
CALCULATE (
    MAX ( fact_restaurants[Aggregate rating] ),
    fact_restaurants[Credible Rating] = TRUE()
)
```

```dax
Value Score =
VAR C = [Avg Cost for Two]
RETURN DIVIDE ( [Avg Rating], DIVIDE ( C, 100 ) )
```
Apply a visual-level filter of `Avg Rating >= 4` and
`Credible Ratings >= 1` on the table that uses it, otherwise cheap-and-bad wins
the ranking.

### 4.7 Rank measures for the leaderboard tables

```dax
Rank by Cost =
IF (
    NOT ISBLANK ( [Avg Cost for Two] ),
    RANKX ( ALLSELECTED ( fact_restaurants[Restaurant Name] ), [Avg Cost for Two], , DESC, DENSE )
)

Rank by Rating =
IF (
    [Credible Ratings] > 0,
    RANKX ( ALLSELECTED ( fact_restaurants[Restaurant Name] ), [Avg Rating], , DESC, DENSE )
)
```

`ALLSELECTED` rather than `ALL`, so the rank recalculates inside whatever the
user's slicers selected — a top-10 that ignores the slicers is a bug.

### 4.8 The opportunity model in DAX

This is the measure to be ready to talk through line by line.

```dax
Locality Demand =
DIVIDE ( SUM ( fact_restaurants[Votes] ), [Total Restaurants] )

Locality Log Demand =
LN ( 1 + [Locality Demand] )
```

```dax
Opportunity Score =
-- Only score localities with enough restaurants to have a stable average.
IF (
    [Total Restaurants] < 15,
    BLANK (),
    VAR LocalityGrid =
        FILTER (
            ALLSELECTED ( fact_restaurants[Locality] ),
            CALCULATE ( [Total Restaurants] ) >= 15
        )
    -- Demand term: z-score of log demand across the comparable localities.
    VAR MeanLogD = AVERAGEX ( LocalityGrid, [Locality Log Demand] )
    VAR SdLogD   = STDEVX.P  ( LocalityGrid, [Locality Log Demand] )
    VAR DemandZ  = DIVIDE ( [Locality Log Demand] - MeanLogD, SdLogD )
    -- Quality term: z-score of incumbent average rating.
    VAR MeanR    = AVERAGEX ( LocalityGrid, [Avg Rating] )
    VAR SdR      = STDEVX.P  ( LocalityGrid, [Avg Rating] )
    VAR QualityZ = DIVIDE ( [Avg Rating] - MeanR, SdR )
    -- Proven demand minus beatable quality = headroom.
    RETURN DemandZ - QualityZ
)
```

Four things to know about it:

- **`ALLSELECTED`, not `ALL`.** The z-scores must be relative to the localities
  currently in scope. Filter to Noida and the score should re-baseline against
  Noida, not against the whole country.
- **`STDEVX.P`, not `.S`.** These localities are the population being compared,
  not a sample drawn from a larger one.
- **`LN(1 + x)`, not `LN(x)`.** A locality can have zero votes and `LN(0)` is an
  error. `LN(1+x)` is defined at zero and behaves the same everywhere else.
- **The `< 15` guard is applied twice** — once to blank out the current locality,
  once inside `LocalityGrid` so the mean and standard deviation are computed over
  the same comparable set the ranking uses. Baselining against localities you
  then refuse to rank would bias every score.

```dax
Opportunity Band =
VAR S = [Opportunity Score]
RETURN
SWITCH (
    TRUE (),
    ISBLANK ( S ),  "Not scored (under 15 restaurants)",
    S >= 0.9,       "Shortlist",
    S >= 0,         "Watch",
                    "Saturated or already strong"
)
```

### 4.9 Dynamic titles and empty states

```dax
Page Title =
VAR C = SELECTEDVALUE ( dim_city[City], "all cities" )
VAR U = SELECTEDVALUE ( dim_cuisine[Cuisine], "all cuisines" )
RETURN "Restaurant analytics — " & C & ", " & U

No Data Message =
IF (
    [Total Restaurants] = 0,
    "No restaurants match the current filters. Try widening the city or price selection.",
    BLANK ()
)
```

Bind `Page Title` to the page's title textbox (**Format → Title → fx →
Field value**) and put `No Data Message` in a card that only shows when the
others are blank. Empty states are the difference between a report that looks
broken and a report that explains itself.

---

## 5. Calculation groups and helper tables

Optional, but it is what separates a modelled report from a pile of visuals. In
**Tabular Editor** (External Tools), add a calculation group `Metric Selector`
with items `Restaurants`, `Avg rating`, `Avg cost`, `Votes`. Then one bar chart
plus one slicer replaces four bar charts, and the user picks the measure.

If you do not have Tabular Editor, the field-parameter feature does the same
job: **Modeling → New parameter → Fields**.

---

## 6. Page-by-page build

Canvas size **1440 × 900** on every page (**Format page → Canvas settings →
Custom**). Leave a 20 px margin and a 12 px gutter between visuals.

### Page 1 — Executive overview

**KPI strip** — 8 cards across the top, 165 × 95 each:

| Card | Measure | Callout |
|---|---|---|
| Restaurants | `Total Restaurants` | subtitle: `Cities Covered` & `Localities` |
| Avg cost for two | `Avg Cost for Two` | subtitle: `Median Cost for Two` |
| Avg rating | `Avg Rating` | subtitle: `Rated Restaurants` |
| Not rated | `Not Rated %` | format as percentage, 1 dp |
| Online delivery | `Online Delivery %` | subtitle: `Table Booking %` |
| Total votes | `Total Votes` | subtitle: `Avg Votes` |
| Cuisines | `Cuisines Offered` | |
| Highest rated | `Highest Rating (credible)` | subtitle: `Top Rated Restaurant` |

Use the **new card visual** (multi-row capable) so the subtitle sits inside the
card rather than needing a second visual.

**Rating distribution** — Clustered column chart.
X: `fact_restaurants[Rating text]`, or better, create a rating-band column:

```dax
Rating Band =
VAR R = fact_restaurants[Aggregate rating]
RETURN
SWITCH (
    TRUE (),
    ISBLANK ( R ), "Not rated",
    R < 1.5, "1.0–1.5", R < 2.0, "1.5–2.0", R < 2.5, "2.0–2.5",
    R < 3.0, "2.5–3.0", R < 3.5, "3.0–3.5", R < 4.0, "3.5–4.0",
    R < 4.5, "4.0–4.5", "4.5–5.0"
)
```
Y: `Total Restaurants`. Filter out `"Not rated"` at visual level. Turn on data
labels; turn off the y-axis (labels make gridlines redundant).

**Price-tier mix** — Clustered bar chart.
Y: `dim_price_range[Price Range Label]`, X: `Total Restaurants`.
Add `Avg Rating` and `Avg Cost for Two` to the **tooltip**, not to a second
axis. If you want them visible, use a table visual beneath rather than a
combo chart — see the dual-axis note in §8.

**Top cities** — Clustered bar chart. Y: `dim_city[City]`, X:
`Total Restaurants`, **Top N filter = 12** on `Total Restaurants`.

**Service adoption** — Table or four gauge-free cards. Avoid the gauge visual;
it spends a lot of pixels on one number.

**Insight text boxes** — three across the bottom. Bind them to measures so they
update with the filters:

```dax
Insight Budget Share =
VAR S =
    DIVIDE (
        CALCULATE ( [Total Restaurants], fact_restaurants[Price range] <= 2 ),
        [Total Restaurants]
    )
RETURN
FORMAT ( S, "0.0%" ) & " of restaurants sit in price tiers 1–2, and the median "
    & "cost for two is " & FORMAT ( [Median Cost for Two], "₹#,##0" )
    & " against a mean of " & FORMAT ( [Avg Cost for Two], "₹#,##0" )
    & ". Quote the median when you benchmark a new opening."
```

### Page 2 — Cost & value

- **Cost band → avg rating**: Line chart. X: `Cost Band (INR)` (sorted by
  `Cost Band Sort`), Y: `Avg Rating`, visual filter `Credible Rating = True`.
  Turn the y-axis "Start at zero" **off** — for a line chart of averages in a
  1–5 range, a zero baseline destroys the signal. (Never do this on a bar
  chart.)
- **Cost vs rating**: Scatter chart. X: `Avg Cost for Two`, Y: `Avg Rating`,
  Size: `Total Votes`, Details: `Restaurant Name`, Legend:
  `dim_price_range[Price Range Label]`. Set the X axis maximum to 4000 so the
  luxury tail does not flatten the cloud, and say so in the subtitle.
  Under **Analytics**, add a **trend line**.
- **Most expensive**: Table. Columns `Rank by Cost`, `Restaurant Name`, `City`,
  `Avg Cost for Two`, `Avg Rating`. Top N = 15 by `Avg Cost for Two`. Conditional
  formatting → data bars on the cost column.
- **Best value**: Table with `Value Score`, filtered `Avg Rating >= 4` and
  `Credible Ratings >= 1`, Top N = 15 by `Value Score`.

### Page 3 — Cuisine & city

- **Cuisine supply**: Bar chart, Y `dim_cuisine[Cuisine]`, X
  `Total Restaurants`, Top N = 14. Put "a restaurant can serve several cuisines,
  so these bars sum above the restaurant count" in the subtitle — it will be
  asked otherwise.
- **Cuisine quality**: Do **not** use a bar chart. These averages sit between
  3.6 and 4.0, and zero-based bars look identical. Use a scatter chart with
  `Avg Rating` on X, `Cuisine` on details, a constant line at the market
  average, and no Y measure — or a table with data bars scaled to a 3.5–4.0
  range. Filter to `Total Restaurants >= 30`.
- **City benchmark**: Matrix. Rows `dim_city[City]`; values `Total Restaurants`,
  `Avg Cost for Two`, `Median Cost for Two`, `Avg Rating`, `Online Delivery %`,
  `Table Booking %`, `Total Votes`. Visual filter `Total Restaurants >= 20`.
  Conditional formatting: background scale on `Avg Rating`, data bars on
  `Total Restaurants`.

### Page 4 — Where to open next

- **Opportunity quadrant**: Scatter chart. X `Avg Rating`, Y
  `Votes per Restaurant`, Size `Total Restaurants`, Details
  `fact_restaurants[Locality]`, Legend `Opportunity Band`. Under **Analytics**
  add an average line on both axes to create the quadrants. Set the Y axis to
  **logarithmic** — votes-per-restaurant spans two orders of magnitude and a
  linear axis crushes everything into the bottom band.
- **Shortlist**: Table. `Locality`, `City`, `Total Restaurants`, `Avg Rating`,
  `Votes per Restaurant`, `Avg Cost for Two`, `Opportunity Score`. Sort
  descending on the score, Top N = 12.
- **Recommendations**: text boxes bound to measures, same pattern as page 1.

### Page 5 — Method & KPI definitions

A page of text boxes plus one small table listing each measure and its
definition. Include `Avg Rating` beside `Avg Rating (naive, for the docs only)`
so the bias fix is visible. This page is what makes the report auditable, and it
is the page an interviewer will linger on.

---

## 7. Slicers, sync and bookmarks

Place these across the top of page 1, then **View → Sync slicers** and tick
every page except page 5:

| Slicer | Field | Style |
|---|---|---|
| City | `dim_city[City]` | Dropdown, single select off |
| Cuisine | `dim_cuisine[Cuisine]` | Dropdown, search on |
| Price tier | `dim_price_range[Price Range Label]` | Tile, multi-select |
| Online delivery | `fact_restaurants[Has Online delivery]` | Tile |
| Table booking | `fact_restaurants[Has Table booking]` | Tile |
| Min rating | `fact_restaurants[Aggregate rating]` | Slider, "Greater than or equal to" |

**Reset button:** with no slicers applied, **View → Bookmarks → Add**, name it
`Reset`, and untick *Data* → tick *Current page* only... actually the reverse:
you want **Data** ticked (so it restores the cleared slicer state) and
**Display** unticked (so it does not fight the page navigation). Then insert a
button, Action → Bookmark → `Reset`.

**Drill-through page:** create a hidden page with `Locality` in the
drill-through field well and a detail table of every restaurant. Right-clicking
a locality on page 4 then jumps to the venue list — the single feature that most
makes a report feel like a tool rather than a poster.

---

## 8. Formatting and theme

Save this as `theme.json` and load it with **View → Themes → Browse for
themes**. The palette is CVD-validated: the categorical order clears a ΔE ≥ 8
colour-vision-deficiency separation gate on adjacent pairs, and the price-tier
ramp is a single hue because price tier is ordered, not categorical.

```json
{
  "name": "Zomato Analytics",
  "dataColors": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                 "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
  "good": "#0ca30c",
  "neutral": "#fab219",
  "bad": "#d03b3b",
  "background": "#fcfcfb",
  "foreground": "#0b0b0b",
  "tableAccent": "#2a78d6",
  "textClasses": {
    "title":    { "fontSize": 14, "fontFace": "Segoe UI Semibold", "color": "#0b0b0b" },
    "label":    { "fontSize": 11, "fontFace": "Segoe UI", "color": "#52514e" },
    "callout":  { "fontSize": 26, "fontFace": "Segoe UI", "color": "#0b0b0b" }
  },
  "visualStyles": {
    "*": {
      "*": {
        "background": [{ "show": true, "color": { "solid": { "color": "#fcfcfb" } } }],
        "border": [{ "show": true, "color": { "solid": { "color": "#e1e0d9" } }, "radius": 8 }],
        "*": [{ "wordWrap": true }]
      }
    }
  }
}
```

Formatting rules worth applying everywhere:

- **Never a dual-axis chart.** Two y-scales let you manufacture any apparent
  relationship by choosing the scales, and the reader cannot detect it. Where
  count and rating must appear together, the bar encodes the count and the
  rating is a label or a tooltip.
- **Bars start at zero, always.** If the range is too narrow for zero-based bars
  to be readable, that is a signal to change the *form* (dot plot, table with
  data bars), not to truncate the axis.
- **Data labels on, gridlines off** wherever the chart has fewer than ~15 marks.
  Labels are more precise than gridlines and use less ink.
- **Format the measures in the model**, not per visual: `Avg Rating` → 2 dp,
  `Avg Cost for Two` → `₹#,##0`, all the `%` measures → percentage 1 dp. Set it
  once in Column tools and every visual inherits it.
- **Sort every categorical axis by a measure**, not alphabetically.

---

## 9. Validating your model against the pipeline

This is the step that turns "the report renders" into "the report is right".
Clear every slicer, put these measures on a page, and compare against
`dashboard/kpis.json`:

| Measure | Expected (India scope, no filters) |
|---|---|
| `Total Restaurants` | 8,652 |
| `Cities Covered` | 43 |
| `Localities` | 784 |
| `Avg Cost for Two` | ₹624 |
| `Median Cost for Two` | ₹450 |
| `P90 Cost for Two` | ₹1,300 |
| `Avg Rating` | 3.35 |
| `Avg Rating (naive)` | 2.52 |
| `Not Rated %` | 24.7% |
| `Online Delivery %` | 28.0% |
| `Table Booking %` | 12.8% |
| `Total Votes` | 1,187,163 |
| `Cuisines Offered` | 90 |
| `Credible Ratings` | 3,250 |

If `Total Restaurants` reads more than 8,652 you have a fan-out through the
cuisine bridge and you are counting rows instead of distinct restaurants. If
`Avg Rating` reads 2.52 you have lost the `Is Rated` filter. If
`Avg Cost for Two` is in the low hundreds you have lost the currency scope and
are averaging in dollars and dirhams.

Add a **filter check**: select one city, and confirm `Total Restaurants` drops to
the value the HTML dashboard shows for the same city. Cross-tool agreement is the
cheapest correctness test available.

---

## 10. Performance notes

At 9,551 rows this model is trivially fast, so performance is a talking point
rather than a problem — but be ready for it.

- **`DISTINCTCOUNT` is the expensive measure here.** On a large model, replacing
  the bridge fan-out with `COUNTROWS(fact)` where a distinct count is not needed
  is the first optimisation.
- **The bidirectional cuisine relationship is the second cost.** The alternative
  is `CROSSFILTER ( dim_cuisine[Cuisine], bridge_cuisine[Cuisine], BOTH )` inside
  only the measures that need it.
- **Iterators over the fact table** (`AVERAGEX(FILTER(...))`) fall to the formula
  engine. Here that is microseconds; at 50 million rows it would matter, and the
  fix is a calculated column materialising the filter.
- **Use Performance Analyzer** (View → Performance Analyzer) and be able to say
  which visual is slowest and why. On this model it will be the scatter with
  ~3,000 details-level marks.
- **Turn off Auto date/time** (Options → Data Load). There are no date columns
  here, so it does nothing but bloat the model — and knowing to check is the
  point.
