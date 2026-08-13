# Deploying to Streamlit Community Cloud

Free, public, and live in about three minutes. The end result is a URL like
`https://<your-app-name>.streamlit.app` that you can put straight on your CV.

---

## Prerequisites

- The repo pushed to GitHub (see [`../PUSH_TO_GITHUB.md`](../PUSH_TO_GITHUB.md)).
  The repository must be **public** on the free tier.
- A Streamlit Community Cloud account — sign in with the same GitHub account at
  <https://share.streamlit.io>.

## Deploy

1. Go to <https://share.streamlit.io> and click **Create app** → **Deploy a
   public app from GitHub**.
2. Fill in:

   | Field | Value |
   |---|---|
   | Repository | `<your-username>/zomato-restaurant-analytics` |
   | Branch | `main` |
   | Main file path | `streamlit_app.py` |
   | App URL | e.g. `zomato-restaurant-analytics` |

3. Under **Advanced settings**, set the Python version to **3.11** (3.9 will
   reject the `str | None` type hints in `app/measures.py`).
4. Click **Deploy**. The first build takes 2–4 minutes while it installs pandas,
   numpy, streamlit and plotly from `requirements.txt`.

That is the whole process. There is nothing to configure, no secrets, and no
database — the app reads CSVs that are committed to the repo.

## Run it locally first

Always confirm locally before deploying; a local failure is much faster to
diagnose than a cloud build log.

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
# opens http://localhost:8501
```

## How the app finds its data

`app/measures.py` looks for `data/processed/fact_restaurants.csv`. Those files
are committed, so on Streamlit Cloud they are simply there after the clone.

If they are ever missing — someone cleaned the directory, or you added the
processed CSVs to `.gitignore` — `_ensure_processed()` shells out to
`scripts/01_clean_data.py` and `scripts/02_build_kpis.py` to rebuild them from
`data/raw/zomato.csv`. That adds a few seconds to the first cold start and then
never runs again. It exists so the app cannot fail with a `FileNotFoundError` on
a fresh clone.

## Performance notes

Streamlit re-runs the entire script top to bottom on **every** widget
interaction. Three things keep that fast here:

- **`@st.cache_data` on `get_data()`.** Without it, 8,652 rows plus a
  19,714-row bridge would be re-read from disk on every checkbox click. With it,
  the CSVs are read once per session and the cache is shared across sessions on
  the same container.
- **Filtering is a single boolean-mask pass** over an in-memory DataFrame, so a
  slicer change costs milliseconds, not a query.
- **The measure layer is pure functions** in `app/measures.py`. Nothing mutates
  the cached frame, which matters because `st.cache_data` hands every session a
  reference to the *same* object — an in-place `df.drop()` in one session would
  corrupt every other session's data.

The free tier gives roughly 1 GB of RAM per app. This dataset is about 4 MB in
memory, so there is a lot of headroom; if you swap in a much larger extract,
convert the CSVs to Parquet and load only the columns the app uses.

## Things that commonly break a first deploy

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError: streamlit` | `requirements.txt` not at the repo root, or the wrong branch selected | The file must be at the root; confirm the branch in app settings |
| `TypeError: unsupported operand type(s) for \|` | Python 3.9 selected | Set Python 3.11 in Advanced settings |
| `FileNotFoundError: fact_restaurants.csv` | `data/` excluded by `.gitignore` | The shipped `.gitignore` explicitly keeps the CSVs — check yours matches |
| `ModuleNotFoundError: app` | `app/__init__.py` missing | It is committed; confirm it survived your push |
| App boots then sleeps | Free-tier apps sleep after ~7 days idle | Anyone visiting the URL wakes it in ~30 seconds. Mention this if you send the link to a recruiter — or open it yourself the morning of the interview |
| Blank page, spinner forever | Browser blocking WebSockets | Try a different network; corporate proxies sometimes block them |

## Keeping it updated

Streamlit Cloud watches the branch. Push to `main` and the app redeploys
automatically — no action needed.

## Verifying a deployed app

The browser test suite takes a URL, so you can point it at the live app rather
than a local server:

```bash
APP_URL=https://<your-app-name>.streamlit.app node tests/test_streamlit_app.mjs
```

That runs all 18 UI checks against production: KPI values, every tab rendering,
and the city slicer actually recomputing the metrics.

## What to say about this in an interview

If asked why the project ships three front-ends for the same analysis:

> The Power BI model is the one a business team would actually use — it is the
> tool they already have and the guide specifies the whole report. The
> single-file HTML dashboard exists because a `.pbix` needs Power BI Desktop and
> a reviewer might not have it; that version opens anywhere with no install. The
> Streamlit app exists because it is a live URL — nothing to download at all —
> and because it runs the same Python that produced the analysis, so there is no
> re-implementation risk in the measures.
>
> The useful side effect is verification. The measures now exist in three
> independent implementations, and the test suites assert they agree: 11 KPIs
> reconciled between pandas and the dashboard's JavaScript, and 38 checks
> reconciling `app/measures.py` against the pipeline's `kpis.json`. Two
> implementations agreeing is real evidence the measure logic is right. One
> implementation rendering without errors is not.
