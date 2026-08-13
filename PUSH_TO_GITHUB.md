# Pushing this to GitHub

The repository is already initialised with one commit. Three steps.

## 1. Create the empty repo on GitHub

Go to <https://github.com/new> and create a repository named
**`zomato-restaurant-analytics`**. Leave "Add a README", ".gitignore" and
"license" **unchecked** — this repo already has all three, and pre-adding them
causes a merge conflict on your first push.

## 2. Push

```bash
cd zomato-restaurant-analytics

# HTTPS (simplest — GitHub will prompt for a Personal Access Token as the password)
git remote add origin https://github.com/<your-username>/zomato-restaurant-analytics.git
git branch -M main
git push -u origin main
```

If you use SSH instead:

```bash
git remote add origin git@github.com:<your-username>/zomato-restaurant-analytics.git
git push -u origin main
```

If the commit author is wrong (it is set to `Priyanshu Singh
<priyanshu1203singh@gmail.com>`), fix it before pushing:

```bash
git config user.name  "Your Name"
git config user.email "you@example.com"
git commit --amend --reset-author --no-edit
```

## 3. Polish the repo page

These take two minutes each and are the first thing a reviewer sees.

**Description** (the field at the top right of the repo page):

> End-to-end restaurant analytics on 8,652 Zomato listings — pandas pipeline,
> Power BI model with full DAX, and a self-contained interactive dashboard.
> Answers where to open next, what to charge, and which cuisines earn their rating.

**Topics:** `data-analytics` `powerbi` `dax` `pandas` `python` `dashboard`
`data-visualization` `business-intelligence` `etl` `zomato`

**Publish the dashboard with GitHub Pages** so you can send a live link instead
of a download:

1. Settings → Pages → Source: **Deploy from a branch** → Branch: `main`,
   folder: `/ (root)` → Save
2. Wait ~1 minute, then your dashboard is live at
   `https://<your-username>.github.io/zomato-restaurant-analytics/dashboard/zomato_dashboard.html`
3. Add that link to the top of the README and to your CV

**Pin the repository** on your GitHub profile (profile → Customize your pins).

## What to put on your CV

> **Restaurant Data Analytics & Insights** — github.com/<your-username>/zomato-restaurant-analytics
> - Built an end-to-end analytics pipeline over **8,652 restaurants** (9,551 globally,
>   15 countries), delivering a 5-page Power BI-style dashboard with cross-filtering
>   slicers and 14 KPIs.
> - Found and corrected a rating-encoding fault where "not rated" was stored as 0,
>   which had biased the market average rating by **0.83 stars**; scoped all cost
>   metrics to a single currency to make the ₹624 mean / ₹450 median cost-for-two
>   benchmark valid.
> - Quantified that price barely predicts quality (**r = 0.21**) while review volume
>   does (**r = 0.46**), and built a demand-vs-quality opportunity model that
>   shortlisted 12 localities for new openings.
> - Shipped 88 automated checks, including a pandas-to-JavaScript reconciliation
>   that proves the dashboard's measures match the pipeline's.

Adjust the wording to match how you actually talk about it — the numbers are all
verifiable from `dashboard/kpis.json`.
