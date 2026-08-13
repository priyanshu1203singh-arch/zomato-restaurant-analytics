# Interview preparation pack

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
extract of 9,551 restaurants across 15 countries, so I built the
analysis that answers those three questions from it."

**The data.** "One flat CSV, 9,551 rows, 21 columns. Restaurant name,
city, locality, latitude/longitude, cuisines, average cost for two, currency,
price tier 1–4, table-booking and online-delivery flags, aggregate rating,
rating text, and vote count. No dates anywhere — that matters, and I'll come
back to it."

**The cleaning, and the one decision that mattered.** "The single most important
thing I found is that `Aggregate rating = 0` does not mean zero stars, it means
*not rated yet*. 2,139 of the Indian rows — 24.7% — are
like that. If you leave them in the average you report 2.52
stars. The correct figure is 3.35. That's a
0.83-star error, and it's worse than it looks, because the bias is
proportional to how many unrated listings each city or cuisine happens to have —
so it corrupts every comparison, not just the headline."

**The second decision.** "The extract mixes 15 currencies. You cannot average
rupees and dollars, so I scoped every money metric to India —
8,652 restaurants, all in ₹. That's still 8,652 restaurants, and
it means the cost benchmark is a real number. Rating, price tier and the service
flags are currency-free, so those I also report globally."

**The model.** "I built a small star schema: a fact table at one row per
restaurant, a country dimension, a price-tier dimension, and a
restaurant-to-cuisine bridge table — because cuisine is many-to-many. One
restaurant lists up to eight cuisines; the average is
2.06. You cannot slice by cuisine until you explode that
field."

**The output.** "A five-page report. Page one is the executive KPI view. Page two
answers 'does spending more buy a better meal'. Page three is cuisine supply
versus cuisine quality plus a city pricing benchmark. Page four is a scored
locality shortlist for where to open. Page five documents every KPI definition,
because a dashboard nobody can audit is a dashboard nobody should trust."

**The punchline.** "Three findings. One: price barely buys quality — the
cost-to-rating correlation is only 0.205, while log-votes-to-rating is
0.463. Attention matters more than price. Two: the crowded cuisines
are the mediocre ones — North Indian, Chinese, Fast Food are on
70.6% of menus and rate mid-table, while
Mediterranean and European rate 3.98 and
3.91 on a fraction of the supply. Three: the best sites are
suburban mall catchments with proven footfall and weak incumbents —
V3S Mall, Laxmi Nagar in New Delhi tops the list at
87 votes per restaurant against a
2.82 average rating."

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
   9,551 rows — zero information, and a column that only invites a
   misleading chart.
7. **`Aggregate rating` 0 → NULL, plus an `Is Rated` flag.** The decision above.
   Keeping the flag means "how many venues are unrated" stays a first-class,
   answerable question rather than something the cleaning destroyed.
8. **`Average Cost for two` ≤ 0 → NULL.** 18 rows. A restaurant that charges
   nothing is missing data, not a free restaurant.
9. **Explode `Cuisines` into a bridge table.** 19,714 restaurant-cuisine pairs.
10. **Derive the analytical columns** — cost band, value score, and
    `Credible Rating` (`Is Rated AND Votes >= 50`).
11. **Flag invalid geography** rather than dropping it: lat/long of (0,0) or out of
    range gets `Geo Valid = False`, so map visuals can exclude it while the rows
    still count in every non-map KPI.
12. **Write the star schema and the quality log.** The log records the step, the
    number of rows affected and the reason — so the cleaning is reviewable by
    someone who did not write it.

### The KPI cards

| KPI | Value | Definition | Why it is the right measure |
|---|--:|---|---|
| Restaurants | 8,652 | `DISTINCTCOUNT(Restaurant ID)` | Distinct count, not row count, so a re-listing cannot inflate it. |
| Cities / localities | 43 / 784 | distinct counts | Market breadth. Locality is the level a site decision is actually made at. |
| Avg cost for two | ₹624 | mean, India only | The CV headline. Quoted with the median because it is skewed. |
| Median cost for two | ₹450 | median, India only | Skew ≈ 3.59. This is the number to benchmark a new opening against. |
| P90 cost for two | ₹1,300 | 90th percentile | Sizes the luxury tail without letting it move the central estimate. |
| Avg rating | 3.35 | mean over `Is Rated = TRUE` | Excluding unrated venues. The whole project hinges on this. |
| Not rated | 24.7% | share with no rating | A coverage metric *and* a commercial one — these are cold-start venues. |
| Online delivery | 28.0% | share of venues with the flag | Channel adoption. |
| Table booking | 12.8% | share of venues with the flag | The premium-format signal. |
| Total votes | 1,187,163 | sum of votes | Best available demand proxy. There is no footfall column. |
| Cuisines offered | 90 | distinct cuisines in the bridge | Menu variety across the market. |
| Highest rated | 4.9 | max rating among ≥ 50 votes | Barbeque Nation. The vote floor is what makes it meaningful. |

### The two derived measures

**Value score** = `rating / (cost for two / 100)` — stars delivered per ₹100.
Only computed for venues rated ≥ 4.0 with ≥ 50 votes, because
without a quality floor "cheap and bad" wins the ranking. Top result:
Jung Bahadur Kachori Wala in Chandni Chowk —
4.1 stars at ₹50 for two.

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
| Cost predicts rating | Pearson r | 0.205 | Weak positive. Spearman 0.228 confirms it is not just an outlier artefact. |
| Attention predicts rating | Pearson r, log(votes) | 0.463 | Over 2× the price correlation. |
| Delivery venues rate higher | Welch t | 2.37 | Gap is only 0.03 stars on n=2,327 vs 4,186. Statistically detectable, commercially irrelevant. Say so. |

The delivery result is the one to volunteer unprompted. A 0.03-star gap
that is technically significant on a large sample is exactly the case where a
weaker analyst reports "delivery restaurants are rated significantly higher" and
a stronger one says "significant, but 0.03 stars is not a business
decision — what actually differs is engagement:
209 average votes versus
109."

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
2,139 data points and simultaneously destroy the ability to answer
"how much of this market has no reviews", which turned out to be one of the more
commercially useful findings on the board.

**4. Why scope the money analysis to India?**
15 currencies in one column. An average across them is arithmetically valid and
semantically meaningless. India is 8,652 of 9,551 rows, so
scoping keeps the sample large while making the cost number interpretable. I
could have converted using FX rates, but I would then be baking an
undocumented, undated exchange rate into a dataset with no timestamps — a false
precision I would have to caveat harder than the scope decision itself.

**5. How do you know your dataset is representative?**
It is not, and I say so on the dashboard.
91.9% of the Indian rows are Delhi NCR, and NCR rates
3.20 against 3.93 for the other 33 benchmarked cities. So this is
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
near-duplicates (chains like Barbeque Nation with many outlets)
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
Skew ≈ 3.59. The mean is ₹624, the median
₹450 — the mean is being pulled by a luxury tail that goes up
to ₹8,000. For a positioning decision the median is the
honest anchor; the mean plus P90 tells you how heavy the tail is.

**10. Why a 50-vote floor on the leaderboards?**
Because rating precision scales with sample size. Without the floor the "top
rated" list is venues with three reviews, which is noise wearing a crown.
8,652 restaurants drop to
3,250 credibly-rated ones — a real cost in coverage, paid deliberately for a
ranking that means something. If pressed on the specific number: 50 is a
judgement call, and I would show the panel how the top 10 changes at 20, 50 and
100 rather than defend 50 as optimal.

**11. Cuisine bars sum to more than your restaurant count. Is that a bug?**
No — it is a many-to-many. One restaurant lists up to eight cuisines, average
2.06, so cuisine counts are *appearances*, not
restaurants. It is labelled on the chart. The trap this avoids is the "top 3
cuisines = 70.6%" claim: if you naively sum the top three cuisine
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

**14. r = 0.205 is weak. So why show the chart at all?**
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
- **Do not quote the mean cost alone.** Skew 3.59. Mean, median, P90.
- **Do not claim causation.** "Higher-rated restaurants get more votes" — the
  arrow runs both ways and you cannot separate them from this data.
- **Do not oversell 0.205.** It is weak, that is the finding, own it.
- **Do not hide the NCR concentration.** 91.9%. Volunteer it
  before you are asked; it reads as rigour when you raise it and as a gap when
  they do.
- **Do not say "5000+ restaurants" if asked for a precise figure.**
  8,652 in India, 9,551 globally. Precision costs nothing.
- **Do not describe the visuals as "insights".** An insight is a decision you
  would change. "Open in V3S Mall, Laxmi Nagar" is an insight; "New Delhi has the
  most restaurants" is a fact.
