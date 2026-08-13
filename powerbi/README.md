# Power BI report

## Building it

The `.pbix` is not committed — a Power BI file is a binary zip, so it produces
useless diffs and bloats the repository on every save. Instead, the report is
fully specified in [`../docs/POWERBI_GUIDE.md`](../docs/POWERBI_GUIDE.md):
data model, every Power Query step, every DAX measure, page-by-page visual
placement, the theme JSON, and a validation table to check your measures
against the pipeline's numbers.

Build order:

1. `python scripts/01_clean_data.py` and `python scripts/02_build_kpis.py`
2. Open Power BI Desktop, load the four CSVs from `data/processed/`
3. Follow `docs/POWERBI_GUIDE.md` sections 2 → 8
4. Validate against section 9 before you share it

## Files to put here once you have built it

```
powerbi/
├── zomato_analytics.pbix     the report (add with git-lfs if you commit it)
├── theme.json               copied from docs/POWERBI_GUIDE.md section 8
└── measures.dax             optional: export via Tabular Editor for diffable measures
```

If you do want the `.pbix` in git, use Git LFS:

```bash
git lfs install
git lfs track "*.pbix"
git add .gitattributes
```

## Interactive alternative

If you do not have Power BI Desktop, open
[`../dashboard/zomato_dashboard.html`](../dashboard/zomato_dashboard.html) — it
implements the same five pages, the same measures and the same slicer behaviour
in a single file that runs in any browser with no install.
