"""
streamlit_app.py
================
The Streamlit version of the Zomato restaurant analytics dashboard.

Same five pages, same measures and the same slicer behaviour as
`dashboard/zomato_dashboard.html` — Streamlit's rerun-on-widget-change model is
the natural analogue of Power BI's filter context, so every KPI, chart and table
recomputes from the filtered frame on each interaction.

Deploy:  https://share.streamlit.io -> point at this repo -> main file
         `streamlit_app.py`
Local:   streamlit run streamlit_app.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import measures as M

# ---------------------------------------------------------------------------
# Palette. Same validated colours as the HTML dashboard: the categorical order
# clears a CVD-separation gate, and price tier uses a single-hue ORDINAL ramp
# because tiers are ordered, not categorical.
# ---------------------------------------------------------------------------
S1, S2, S3, S4 = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
ORD = ["#86b6ef", "#3987e5", "#1c5cab", "#0d366b"]
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, SURFACE = "#e1e0d9", "#fcfcfb"

st.set_page_config(
    page_title="Zomato Restaurant Analytics",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
  .block-container {padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1500px;}
  [data-testid="stMetricValue"] {font-size: 1.7rem; font-weight: 650;}
  [data-testid="stMetricLabel"] {font-size: .72rem; text-transform: uppercase;
      letter-spacing: .04em; color: #898781; font-weight: 700;}
  [data-testid="stMetricDelta"] svg {display: none;}
  [data-testid="stMetric"] {background: #fcfcfb; border: 1px solid rgba(11,11,11,.10);
      border-radius: 12px; padding: 12px 14px;}
  h1 {font-size: 1.55rem !important; letter-spacing: -.01em;}
  h2 {font-size: 1.15rem !important; margin-top: 1.4rem;}
  h3 {font-size: .98rem !important;}
  .caption {color:#52514e; font-size:.85rem;}
  .insight {background:#fcfcfb; border:1px solid rgba(11,11,11,.10);
      border-left:3px solid #2a78d6; border-radius:8px; padding:11px 15px; margin-bottom:10px;}
  .insight.warn {border-left-color:#fab219}
  .insight.good {border-left-color:#0ca30c}
  .insight.crit {border-left-color:#d03b3b}
  .insight h4 {margin:0 0 4px; font-size:.92rem; font-weight:650; color:#0b0b0b}
  .insight p {margin:0; font-size:.85rem; color:#52514e; line-height:1.55}
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data (cached — Streamlit reruns the whole script on every widget change, so
# without this the CSVs would be re-read on every click)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading restaurant data…")
def get_data():
    return M.load_data()


india, bridge = get_data()


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def inr(v):
    return "—" if v is None or pd.isna(v) else f"₹{v:,.0f}"


def num(v):
    return "—" if v is None or pd.isna(v) else f"{v:,.0f}"


def f2(v):
    return "—" if v is None or pd.isna(v) else f"{v:.2f}"


def pct(v):
    return "—" if v is None or pd.isna(v) else f"{v:.1f}%"


def insight(title, body, kind=""):
    st.markdown(
        f'<div class="insight {kind}"><h4>{title}</h4><p>{body}</p></div>',
        unsafe_allow_html=True,
    )


def style_fig(fig, height=330, showlegend=False):
    """One place for chart chrome, so every figure reads as the same system."""
    fig.update_layout(
        height=height,
        showlegend=showlegend,
        margin=dict(l=8, r=8, t=10, b=8),
        paper_bgcolor=SURFACE,
        plot_bgcolor=SURFACE,
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif",
                  size=12, color=INK2),
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=GRID,
                        font=dict(color=INK, size=12)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor="#c3c2b7",
                     tickfont=dict(color=MUTED, size=11), title_font=dict(size=11))
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor="#c3c2b7",
                     tickfont=dict(color=MUTED, size=11), title_font=dict(size=11))
    return fig


# ---------------------------------------------------------------------------
# Sidebar — the slicer panel
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### Filters")
    st.caption("Everything on the page recalculates from your selection.")

    city_counts = india["City"].value_counts()
    sel_cities = st.multiselect(
        "City",
        options=list(city_counts.index),
        format_func=lambda c: f"{c} ({city_counts[c]:,})",
        help="Leave empty for all 43 cities.",
    )

    cuisine_counts = bridge["Cuisine"].value_counts()
    sel_cuisines = st.multiselect(
        "Cuisine",
        options=list(cuisine_counts.index),
        format_func=lambda c: f"{c} ({cuisine_counts[c]:,})",
        help="A restaurant can list several cuisines, so this is an 'includes' filter.",
    )

    sel_tiers_labels = st.multiselect(
        "Price tier",
        options=M.PRICE_ORDER,
        help="Zomato's own 1–4 tier. Currency-free, so it is comparable across cities.",
    )
    sel_tiers = [int(t[0]) for t in sel_tiers_labels]

    st.markdown("**Services & quality**")
    c1, c2 = st.columns(2)
    with c1:
        f_delivery = st.checkbox("Online delivery")
        f_rated = st.checkbox("Rated only")
    with c2:
        f_booking = st.checkbox("Table booking")
        f_credible = st.checkbox(
            "50+ votes",
            help="The credibility floor. A 4.9 from 3 reviews is noise; this removes it.",
        )

    min_rating = st.slider("Minimum rating", 0.0, 5.0, 0.0, 0.1)
    search = st.text_input("Search restaurant / locality",
                           placeholder="e.g. Barbeque Nation, Hauz Khas")

    if st.button("Reset filters", width="stretch"):
        st.rerun()

    st.divider()
    st.caption(
        "**Scope.** Money metrics are India-only — the raw extract mixes 15 "
        "currencies, so a global cost average would be meaningless. Ratings "
        "exclude the 24.7% of venues that have never been rated; a Zomato "
        "rating of 0 means *not rated*, not zero stars."
    )

df = M.apply_filters(
    india, bridge,
    cities=sel_cities, cuisines=sel_cuisines, price_tiers=sel_tiers,
    delivery_only=f_delivery, booking_only=f_booking,
    rated_only=f_rated, credible_only=f_credible,
    min_rating=min_rating, search=search,
)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("Zomato Restaurant Analytics & Insights")
st.markdown(
    '<p class="caption">Where to open next, what to charge, and which cuisines '
    "actually earn their rating — built on 8,652 Indian restaurants from the "
    "public Zomato dataset (9,551 globally, 15 countries).</p>",
    unsafe_allow_html=True,
)

if len(df) == 0:
    st.warning(
        "No restaurants match the current filters. Widen the city, cuisine or "
        "price selection in the sidebar."
    )
    st.stop()

active = []
if sel_cities:
    active.append(f"City: {', '.join(sel_cities[:3])}"
                  + (f" +{len(sel_cities)-3}" if len(sel_cities) > 3 else ""))
if sel_cuisines:
    active.append(f"Cuisine: {', '.join(sel_cuisines[:3])}")
if sel_tiers_labels:
    active.append("Tier: " + ", ".join(t.split(" - ")[1] for t in sel_tiers_labels))
for flag, label in [(f_delivery, "Online delivery"), (f_booking, "Table booking"),
                    (f_rated, "Rated only"), (f_credible, "50+ votes")]:
    if flag:
        active.append(label)
if min_rating > 0:
    active.append(f"Rating ≥ {min_rating:.1f}")
if search.strip():
    active.append(f"Search: {search.strip()}")

st.caption(
    f"**{len(df):,}** of {len(india):,} restaurants in scope"
    + ("  ·  " + "  ·  ".join(active) if active else "  ·  no filters applied")
)

k = M.kpis(df, bridge)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "1 · Executive overview",
    "2 · Cost & value",
    "3 · Cuisine & city",
    "4 · Where to open next",
    "5 · Method & KPI definitions",
])

# ===========================================================================
# PAGE 1 — EXECUTIVE OVERVIEW
# ===========================================================================
with tab1:
    cols = st.columns(4)
    tiles = [
        ("Restaurants", num(k["restaurants"]),
         f"{k['cities']} cities · {k['localities']} localities"),
        ("Avg cost for two", inr(k["avg_cost"]),
         f"median {inr(k['median_cost'])} · P90 {inr(k['p90_cost'])}"),
        ("Avg rating", f2(k["avg_rating"]), f"{k['rated_n']:,} rated venues only"),
        ("Not rated", pct(k["not_rated_pct"]), "cold-start venues, zero reviews"),
        ("Online delivery", pct(k["delivery_pct"]),
         f"table booking {pct(k['booking_pct'])}"),
        ("Total votes", num(k["total_votes"]),
         f"{num(k['avg_votes'])} per restaurant"),
        ("Cuisines offered", num(k["cuisines"]),
         f"{f2(k['avg_cuisines'])} per restaurant"),
        ("Highest rated", f"{k['top_rating']:.1f}" if k["top_rating"] else "—",
         k["top_name"] or "none with 50+ votes"),
    ]
    for i, (label, value, delta) in enumerate(tiles):
        cols[i % 4].metric(label, value, delta, delta_color="off")

    st.write("")
    left, right = st.columns([5, 7])

    with left:
        st.subheader("How ratings are distributed")
        st.caption("Rated restaurants only. The market clusters at 3.0–4.0 — "
                   "a 4.5+ rating is genuinely rare.")
        h = M.rating_histogram(df)
        fig = go.Figure(go.Bar(
            x=h["Rating band"], y=h["Restaurants"], marker_color=S1,
            marker_line_width=0, text=h["Restaurants"].map("{:,.0f}".format),
            textposition="outside", textfont=dict(color=INK2, size=11),
            hovertemplate="<b>Rating %{x}</b><br>%{y:,} restaurants<extra></extra>",
        ))
        fig.update_traces(marker=dict(cornerradius=4))
        fig.update_yaxes(title="Restaurants")
        # Horizontal tick labels: plotly rotates them by default when it thinks
        # they are tight, and rotated labels are harder to read than a slightly
        # narrower plot.
        fig.update_xaxes(tickangle=0, title="Aggregate rating band")
        st.plotly_chart(style_fig(fig, 320), width="stretch")

    with right:
        st.subheader("Price tier: how many restaurants, and how well they score")
        st.caption("Bars encode the count. Rating and cost are labelled per tier "
                   "rather than put on a second y-axis — two scales let you "
                   "manufacture any apparent relationship you like.")
        p = M.price_tier_summary(df)
        p = p[p["Restaurants"] > 0]
        fig = go.Figure(go.Bar(
            x=p["Restaurants"], y=p["Price Range Label"].astype(str),
            orientation="h",
            marker_color=[ORD[int(str(t)[0]) - 1] for t in p["Price Range Label"]],
            marker_line_width=0,
            text=[f"{r:,.0f}   ★ {ar:.2f}   {inr(ac)}"
                  for r, ar, ac in zip(p["Restaurants"], p["Avg rating"], p["Avg cost"])],
            textposition="outside", textfont=dict(color=INK2, size=11),
            customdata=np.stack([p["Avg rating"], p["Avg cost"],
                                 p["Online delivery %"], p["Table booking %"],
                                 p["Share %"]], axis=-1),
            hovertemplate=("<b>%{y}</b><br>%{x:,} restaurants (%{customdata[4]:.1f}%)"
                           "<br>Avg rating %{customdata[0]:.2f}"
                           "<br>Avg cost ₹%{customdata[1]:,.0f}"
                           "<br>Online delivery %{customdata[2]:.1f}%"
                           "<br>Table booking %{customdata[3]:.1f}%<extra></extra>"),
        ))
        fig.update_traces(marker=dict(cornerradius=4))
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(title="Restaurants",
                         range=[0, p["Restaurants"].max() * 1.55])
        st.plotly_chart(style_fig(fig, 320), width="stretch")

    left, right = st.columns([7, 5])
    with left:
        st.subheader("Top cities by restaurant count")
        c = M.city_benchmark(df, min_n=1).head(12)
        fig = go.Figure(go.Bar(
            x=c["Restaurants"], y=c["City"], orientation="h",
            marker_color=S1, marker_line_width=0,
            text=c["Restaurants"].map("{:,.0f}".format),
            textposition="outside", textfont=dict(color=INK2, size=11),
            customdata=np.stack([c["Avg rating"], c["Avg cost"]], axis=-1),
            hovertemplate=("<b>%{y}</b><br>%{x:,} restaurants"
                           "<br>Avg rating %{customdata[0]:.2f}"
                           "<br>Avg cost ₹%{customdata[1]:,.0f}<extra></extra>"),
        ))
        fig.update_traces(marker=dict(cornerradius=4))
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(range=[0, c["Restaurants"].max() * 1.18])
        st.plotly_chart(style_fig(fig, 380), width="stretch")

    with right:
        st.subheader("Service adoption")
        st.caption("Share of restaurants offering each service, within the current filter.")
        svc = pd.DataFrame({
            "Service": ["Online delivery", "Table booking",
                        "Has at least one rating", "Credible rating (50+ votes)"],
            "Share": [k["delivery_pct"], k["booking_pct"],
                      100 - k["not_rated_pct"],
                      100 * k["credible_n"] / len(df)],
            "Colour": [S1, S2, S3, S4],
        })
        fig = go.Figure(go.Bar(
            x=svc["Share"], y=svc["Service"], orientation="h",
            marker_color=svc["Colour"], marker_line_width=0,
            text=svc["Share"].map("{:.1f}%".format),
            textposition="outside", textfont=dict(color=INK2, size=11),
            hovertemplate="<b>%{y}</b><br>%{x:.1f}%<extra></extra>",
        ))
        fig.update_traces(marker=dict(cornerradius=4))
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(range=[0, 118], ticksuffix="%", title="Share of restaurants")
        st.plotly_chart(style_fig(fig, 380), width="stretch")

    st.subheader("What the overview page is telling you")
    budget_share = 100 * (df["Price range"] <= 2).mean()
    rated = df[df["Is Rated"]]
    above4 = int((rated["Aggregate rating"] >= 4).sum())
    insight(
        "The market is a budget market",
        f"<b>{budget_share:.1f}%</b> of restaurants sit in price tiers 1–2, and the "
        f"median cost for two is <b>{inr(k['median_cost'])}</b> against a mean of "
        f"<b>{inr(k['avg_cost'])}</b>. The mean sits above the median because a small "
        f"luxury tail (P90 = {inr(k['p90_cost'])}) pulls it up — quote the <b>median</b> "
        "when you benchmark a new opening, not the mean.",
    )
    insight(
        "A quarter of the market has no rating at all",
        f"<b>{pct(k['not_rated_pct'])}</b> of listings have never been rated. Treating "
        "those as “0 stars” would report an average rating of <b>2.52</b> instead of the "
        "correct <b>3.35</b> — a 0.83-star error, and one that scales with how many "
        "unrated listings each city or cuisine happens to have, so it corrupts every "
        "comparison. Commercially these are cold-start venues: the fastest revenue "
        "lever is getting their first 50 reviews.",
        "warn",
    )
    insight(
        "Rating is scarce currency above 4.0",
        f"Only <b>{above4:,}</b> of {len(rated):,} rated venues "
        f"(<b>{100*above4/max(len(rated),1):.1f}%</b>) clear 4.0. A 4.0+ badge is a real "
        "differentiator, not table stakes.",
        "good",
    )

# ===========================================================================
# PAGE 2 — COST & VALUE
# ===========================================================================
with tab2:
    corr = M.correlations(df)
    cols = st.columns(6)
    for col, (label, value, delta) in zip(cols, [
        ("Avg cost for two", inr(k["avg_cost"]), "right-skewed — read the median too"),
        ("Median cost", inr(k["median_cost"]), "half of venues cost less"),
        ("P90 cost", inr(k["p90_cost"]), "only 10% charge more"),
        ("Most expensive", inr(k["max_cost"]), k["priciest_name"] or "—"),
        ("Cost vs rating r", f2(corr["pearson"]),
         f"weak positive · n={corr['n']:,}"),
        ("Credible sample", num(k["credible_n"]), "rated venues with 50+ votes"),
    ]):
        col.metric(label, value, delta, delta_color="off")

    st.write("")
    left, right = st.columns(2)

    with left:
        st.subheader("Does spending more buy a better meal?")
        st.caption("Average rating per cost-for-two band, restricted to venues with "
                   "50+ votes so the rating is trustworthy.")
        t = M.cost_band_trend(df).dropna(subset=["Avg rating"])
        fig = go.Figure(go.Scatter(
            x=t["Cost band"].astype(str), y=t["Avg rating"],
            mode="lines+markers+text", line=dict(color=S1, width=2),
            marker=dict(size=9, color=S1, line=dict(color=SURFACE, width=2)),
            text=t["Avg rating"].map("{:.2f}".format),
            textposition="top center", textfont=dict(color=INK2, size=11),
            customdata=t["Restaurants"],
            hovertemplate=("<b>₹%{x} for two</b><br>Avg rating %{y:.2f}"
                           "<br>%{customdata:,} restaurants<extra></extra>"),
        ))
        fig.update_xaxes(title="Average cost for two (₹)")
        fig.update_yaxes(title="Average rating")
        st.plotly_chart(style_fig(fig, 340), width="stretch")

    with right:
        st.subheader("Cost vs rating — every restaurant")
        st.caption("Shade = price tier (a single-hue ordinal ramp, because tiers are "
                   "ordered). Marker area ∝ votes.")
        s = df[df["Credible Rating"]].dropna(
            subset=["Average Cost for two", "Aggregate rating"])
        s = s[s["Average Cost for two"] <= 4000]
        fig = go.Figure()
        for tier in [1, 2, 3, 4]:
            g = s[s["Price range"] == tier]
            if not len(g):
                continue
            fig.add_trace(go.Scatter(
                x=g["Average Cost for two"], y=g["Aggregate rating"],
                mode="markers", name=M.PRICE_ORDER[tier - 1].split(" - ")[1],
                marker=dict(
                    size=np.clip(4 + np.sqrt(g["Votes"]) / 6, 5, 22),
                    color=ORD[tier - 1], opacity=0.7,
                    line=dict(color=SURFACE, width=1),
                ),
                customdata=np.stack([g["Restaurant Name"], g["City"], g["Votes"]], axis=-1),
                hovertemplate=("<b>%{customdata[0]}</b><br>%{customdata[1]}"
                               "<br>₹%{x:,.0f} for two · ★ %{y:.1f}"
                               "<br>%{customdata[2]:,} votes<extra></extra>"),
            ))
        fig.update_xaxes(title="Average cost for two (₹)", range=[0, 4100])
        fig.update_yaxes(title="Aggregate rating", range=[1.8, 5.05])
        st.plotly_chart(style_fig(fig, 340, showlegend=True), width="stretch")

    left, right = st.columns(2)
    with left:
        st.subheader("Most expensive establishments")
        e = df.dropna(subset=["Average Cost for two"]).nlargest(15, "Average Cost for two")
        st.dataframe(
            e[["Restaurant Name", "City", "Average Cost for two", "Aggregate rating", "Votes"]]
            .rename(columns={"Average Cost for two": "Cost for two",
                             "Aggregate rating": "Rating"}),
            hide_index=True, width="stretch",
            column_config={
                "Cost for two": st.column_config.ProgressColumn(
                    "Cost for two", format="₹%d", min_value=0,
                    max_value=float(e["Average Cost for two"].max())),
                "Rating": st.column_config.NumberColumn(format="%.1f"),
            },
        )
    with right:
        st.subheader("Best value — rating per ₹100 spent")
        st.caption("Rating ÷ (cost for two ÷ 100), restricted to 4.0+ venues with 50+ "
                   "votes. Without the rating floor, cheap-and-bad wins.")
        v = M.value_leaderboard(df)
        if len(v):
            st.dataframe(
                v[["Restaurant Name", "Locality", "Average Cost for two",
                   "Aggregate rating", "Stars per ₹100"]]
                .rename(columns={"Average Cost for two": "Cost",
                                 "Aggregate rating": "★"}),
                hide_index=True, width="stretch",
                column_config={
                    "Cost": st.column_config.NumberColumn(format="₹%d"),
                    "★": st.column_config.NumberColumn(format="%.1f"),
                    "Stars per ₹100": st.column_config.ProgressColumn(
                        "★ per ₹100", format="%.2f", min_value=0,
                        max_value=float(v["Stars per ₹100"].max())),
                },
            )
        else:
            st.info("No venue in this filter clears 4.0 with 50+ votes.")

    st.subheader("What the cost page is telling you")
    cheap = df[df["Credible Rating"] & df["Average Cost for two"].lt(400)]
    lux = df[df["Credible Rating"] & df["Average Cost for two"].ge(1600)]
    insight(
        "Price buys a little quality, not a lot",
        f"Pearson r between cost for two and rating is <b>{f2(corr['pearson'])}</b> "
        f"(Spearman {f2(corr['spearman'])}) across {corr['n']:,} credibly-rated venues. "
        f"The average ₹1,600+ venue rates "
        f"<b>{f2(lux['Aggregate rating'].mean()) if len(lux) else '—'}</b> versus "
        f"<b>{f2(cheap['Aggregate rating'].mean()) if len(cheap) else '—'}</b> under ₹400 "
        "— roughly half a star for 4× the price. The strongest correlate of rating is "
        f"not price but attention: log(votes) correlates at <b>{f2(corr['votes'])}</b>, "
        "more than double. Price is not the quality lever; execution is.",
    )
    insight(
        "Read the &lt;₹200 point with suspicion",
        "The cheapest band looks excellent, but it only contains venues that already "
        "earned 50+ votes. Cheap places nobody reviewed are filtered out, so this point "
        "suffers survivorship bias. It is a genuine finding about <i>famous</i> street "
        "food, not about cheap food in general.",
        "warn",
    )

# ===========================================================================
# PAGE 3 — CUISINE & CITY
# ===========================================================================
with tab3:
    cu = M.cuisine_summary(df, bridge)
    left, right = st.columns(2)

    with left:
        st.subheader("Cuisine supply — most common cuisines")
        st.caption("A restaurant can serve several cuisines, so these bars sum to more "
                   "than the restaurant count. That is correct, not a bug.")
        top = cu.head(14)
        fig = go.Figure(go.Bar(
            x=top["Restaurants"], y=top["Cuisine"], orientation="h",
            marker_color=S1, marker_line_width=0,
            text=top["Restaurants"].map("{:,.0f}".format),
            textposition="outside", textfont=dict(color=INK2, size=11),
            customdata=np.stack([top["Avg rating"], top["Avg cost"]], axis=-1),
            hovertemplate=("<b>%{y}</b><br>%{x:,} restaurants"
                           "<br>Avg rating %{customdata[0]:.2f}"
                           "<br>Avg cost ₹%{customdata[1]:,.0f}<extra></extra>"),
        ))
        fig.update_traces(marker=dict(cornerradius=4))
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(range=[0, top["Restaurants"].max() * 1.18])
        st.plotly_chart(style_fig(fig, 420), width="stretch")

    with right:
        st.subheader("Cuisine quality — highest average rating")
        st.caption("A dot plot on a zoomed axis, not a bar chart. These averages all sit "
                   "between about 3.6 and 4.0, and zero-based bars would look identical — "
                   "so the honest move is to change the chart form, not truncate the axis.")
        q = (cu[cu["Restaurants"] >= M.MIN_CUISINE_N]
             .dropna(subset=["Avg rating"])
             .nlargest(12, "Avg rating"))
        if len(q) >= 3:
            market = df[df["Is Rated"]]["Aggregate rating"].mean()
            fig = go.Figure()
            for _, r in q.iterrows():
                fig.add_trace(go.Scatter(
                    x=[market, r["Avg rating"]], y=[r["Cuisine"]] * 2,
                    mode="lines", line=dict(color=GRID, width=2),
                    hoverinfo="skip", showlegend=False,
                ))
            fig.add_trace(go.Scatter(
                x=q["Avg rating"], y=q["Cuisine"], mode="markers+text",
                marker=dict(size=11, color=S3, line=dict(color=SURFACE, width=2)),
                text=q["Avg rating"].map("{:.2f}".format),
                textposition="middle right", textfont=dict(color=INK2, size=11),
                customdata=np.stack([q["Restaurants"], q["Avg cost"]], axis=-1),
                hovertemplate=("<b>%{y}</b><br>Avg rating %{x:.2f}"
                               "<br>%{customdata[0]:,} restaurants"
                               "<br>Avg cost ₹%{customdata[1]:,.0f}<extra></extra>"),
                showlegend=False,
            ))
            fig.add_vline(x=market, line_dash="dash", line_color="#c3c2b7",
                          annotation_text=f"market avg {market:.2f}",
                          annotation_font=dict(color=MUTED, size=11))
            fig.update_yaxes(autorange="reversed")
            # Headroom on the right so the value label of the top dot is not
            # clipped by the plot edge.
            span = q["Avg rating"].max() - min(market, q["Avg rating"].min())
            fig.update_xaxes(title="Average aggregate rating",
                             range=[min(market, q["Avg rating"].min()) - span * .08,
                                    q["Avg rating"].max() + span * .22])
            st.plotly_chart(style_fig(fig, 420), width="stretch")
        else:
            st.info(f"Fewer than 3 cuisines have {M.MIN_CUISINE_N}+ restaurants in this "
                    "filter. Widen the selection.")

    st.subheader("City benchmark")
    st.caption("The “is my pricing normal here?” table. Cities with 20+ restaurants "
               "in the current filter.")
    cb = M.city_benchmark(df)
    if len(cb):
        st.dataframe(
            cb, hide_index=True, width="stretch",
            column_config={
                "Restaurants": st.column_config.ProgressColumn(
                    "Restaurants", format="%d", min_value=0,
                    max_value=int(cb["Restaurants"].max())),
                "Avg cost": st.column_config.NumberColumn(format="₹%d"),
                "Median cost": st.column_config.NumberColumn(format="₹%d"),
                "Avg rating": st.column_config.NumberColumn(format="%.2f"),
                "Online delivery %": st.column_config.NumberColumn(format="%.1f%%"),
                "Table booking %": st.column_config.NumberColumn(format="%.1f%%"),
                "Total votes": st.column_config.NumberColumn(format="localized"),
            },
        )
    else:
        st.info("No city has 20+ restaurants in this filter.")

    st.subheader("What the cuisine page is telling you")
    if len(cb) >= 2:
        ncr = cb[cb["City"].isin(M.NCR)]
        t2 = cb[~cb["City"].isin(M.NCR)]
        if len(ncr) and len(t2):
            insight(
                "The finding that surprises people: NCR rates lower than everywhere else",
                f"The {len(ncr)} Delhi-NCR cities average "
                f"<b>{f2(ncr['Avg rating'].mean())}</b> stars; the {len(t2)} other "
                f"benchmarked cities average <b>{f2(t2['Avg rating'].mean())}</b>. Two "
                "readings and you should say both out loud: NCR is the saturated market "
                "where competition compresses ratings, <i>and</i> NCR is where Zomato's "
                "coverage was deepest, so it also lists the long tail of small venues "
                "other cities never got listed. Selection effect and competition effect "
                "point the same way — which is exactly why I benchmark pricing "
                "<b>within</b> a city, never across them.",
                "crit",
            )
    top3 = list(cu.head(3)["Cuisine"])
    share = 100 * bridge[bridge["Cuisine"].isin(top3)]["Restaurant ID"].nunique() / len(df)
    single = 100 * (df["Cuisine Count"] == 1).mean()
    insight(
        "Supply is concentrated, quality is not",
        f"<b>{', '.join(top3)}</b> appear on the menu of <b>{share:.1f}%</b> of "
        "restaurants, yet they sit mid-table on rating. The highest-rated cuisines are "
        "the under-supplied ones. Crowded categories are where averages go to die — and "
        "note that you cannot compute that share by summing cuisine counts, because a "
        "venue serving all three would be counted three times.",
    )
    insight(
        "Multi-cuisine menus are the norm, not an edge",
        f"Only <b>{single:.1f}%</b> of restaurants serve a single cuisine; the average "
        f"venue lists <b>{f2(k['avg_cuisines'])}</b>. Adding another cuisine to the board "
        "does not differentiate you — it moves you into more crowded comparison sets.",
        "warn",
    )

# ===========================================================================
# PAGE 4 — WHERE TO OPEN NEXT
# ===========================================================================
with tab4:
    insight(
        "The question this page answers",
        "“If we open one more restaurant, where?” A locality is attractive when demand is "
        "already proven (high votes per restaurant = people go out and review there) but "
        "the incumbent quality bar is low (a beatable average rating). "
        "Score = z(log demand) − z(avg rating), over localities with 15+ restaurants.",
    )

    o = M.opportunity(df)
    if len(o) < 3 or o["Opportunity score"].isna().all():
        st.info(f"Not enough localities with {M.MIN_LOCALITY_N}+ restaurants inside the "
                "current filter to score. Widen the filter.")
    else:
        left, right = st.columns([5, 7])
        top = o.head(12)
        rank = {loc: i + 1 for i, loc in enumerate(top.head(5)["Locality"])}

        with left:
            st.subheader("Opportunity quadrant")
            st.caption("X = incumbent average rating. Y = votes per restaurant (log "
                       "scale — the raw values span two orders of magnitude). "
                       "Top-left = proven demand, weak competition.")
            shortlisted = o["Opportunity score"] > 0.9
            fig = go.Figure()
            for mask, colour, name in [(~shortlisted, ORD[1], "Other localities"),
                                       (shortlisted, S2, "Shortlisted (score > 0.9)")]:
                g = o[mask]
                if not len(g):
                    continue
                fig.add_trace(go.Scatter(
                    x=g["Avg rating"], y=g["Votes per restaurant"],
                    mode="markers", name=name,
                    marker=dict(size=np.clip(6 + np.sqrt(g["Restaurants"]) * 1.6, 7, 26),
                                color=colour, opacity=.78,
                                line=dict(color=SURFACE, width=1.5)),
                    customdata=np.stack([g["Locality"], g["City"], g["Restaurants"],
                                         g["Avg cost"], g["Opportunity score"]], axis=-1),
                    hovertemplate=("<b>%{customdata[0]}, %{customdata[1]}</b>"
                                   "<br>%{customdata[2]:,} restaurants"
                                   "<br>★ %{x:.2f} · %{y:,.0f} votes/restaurant"
                                   "<br>Avg cost ₹%{customdata[3]:,.0f}"
                                   "<br>Score %{customdata[4]:.2f}<extra></extra>"),
                ))
            # Numbered markers for the top 5 — a numeral keyed to the table beside
            # the chart says the same thing as a text label, without the collisions
            # that floating labels cause in a dense scatter.
            # Reversed so rank 1 paints last and stays on top where two
            # near-identical localities overlap.
            t5 = top.head(5).iloc[::-1]
            fig.add_trace(go.Scatter(
                x=t5["Avg rating"], y=t5["Votes per restaurant"],
                mode="markers+text", showlegend=False,
                marker=dict(size=22, color=S2, line=dict(color=SURFACE, width=2)),
                text=[str(rank[l]) for l in t5["Locality"]],
                textfont=dict(color="white", size=11, family="system-ui"),
                textposition="middle center",
                customdata=np.stack([t5["Locality"], t5["City"]], axis=-1),
                hovertemplate="<b>%{customdata[0]}, %{customdata[1]}</b><extra></extra>",
            ))
            fig.add_vline(x=o["Avg rating"].mean(), line_dash="dash",
                          line_color="#c3c2b7")
            fig.add_hline(y=float(np.exp(np.log(o["Votes per restaurant"]
                                                .clip(lower=1)).mean())),
                          line_dash="dash", line_color="#c3c2b7")
            # Explicit decade ticks. Plotly's default log axis labels every
            # minor tick (2, 5, 10, 20, 50 …), which is unreadable at this height.
            fig.update_yaxes(type="log", title="Votes per restaurant (log)",
                             tickmode="array", tickvals=[1, 10, 100, 1000],
                             ticktext=["1", "10", "100", "1,000"])
            fig.update_xaxes(title="Incumbent average rating →")
            st.plotly_chart(style_fig(fig, 430, showlegend=True), width="stretch")

        with right:
            st.subheader("Ranked shortlist")
            st.caption("Highest opportunity score first. Numbered markers on the "
                       "quadrant are the top 5 of this list.")
            show = (top[["Locality", "City", "Restaurants", "Avg rating",
                         "Votes per restaurant", "Opportunity score"]]
                    .rename(columns={"Restaurants": "n"}))
            st.dataframe(
                show, hide_index=True, width="stretch", height=430,
                column_config={
                    "Locality": st.column_config.TextColumn("Locality", width="medium"),
                    "City": st.column_config.TextColumn("City", width="small"),
                    "n": st.column_config.NumberColumn("n", width="small"),
                    "Avg rating": st.column_config.NumberColumn("★", format="%.2f",
                                                               width="small"),
                    "Votes per restaurant": st.column_config.NumberColumn(
                        "Votes/rest", format="%d", width="small"),
                    "Opportunity score": st.column_config.ProgressColumn(
                        "Score", format="%.2f", min_value=0,
                        max_value=float(top["Opportunity score"].max())),
                },
            )

        st.subheader("Recommendations that fall out of the model")
        t1 = top.iloc[0]
        mean_r = o["Avg rating"].mean()
        weak = o[(o["Avg rating"] < mean_r)
                 & (np.log1p(o["Votes per restaurant"])
                    > np.log1p(o["Votes per restaurant"]).mean())]
        insight(
            "1 · Open in a proven catchment with a weak incumbent set",
            f"<b>{t1['Locality']}, {t1['City']}</b> tops the shortlist: "
            f"{t1['Restaurants']:,} restaurants already there earning "
            f"<b>{t1['Votes per restaurant']:,.0f}</b> votes each — the footfall is "
            f"proven — but their average rating is only <b>{t1['Avg rating']:.2f}</b> "
            f"against a market average of <b>{mean_r:.2f}</b>. Beating a 2.8–3.0 "
            "incumbent average is an execution problem, not a marketing one.",
            "good",
        )
        insight(
            "2 · Price to the locality, not to the city",
            f"The shortlisted localities average <b>{inr(top['Avg cost'].mean())}</b> for "
            "two. Anchor the menu there; pricing to the city-wide mean would place you "
            "above local willingness-to-pay in exactly the catchments where the "
            "opportunity is.",
        )
        insight(
            f"3 · {len(weak):,} localities are “busy but mediocre”",
            "These sit above average on demand and below average on rating. For an "
            "operator who already has a site there, the highest-return action is not a "
            "new outlet — it is fixing the rating, because the demand already exists and "
            "the competitive bar is low.",
            "warn",
        )
        insight(
            "Honest limitation",
            "<b>91.9%</b> of the restaurants in this dataset are in Delhi NCR, so this "
            "shortlist is an NCR shortlist. Votes are a proxy for footfall, not footfall "
            "itself, and the extract is a point-in-time snapshot with no dates — so "
            "nothing here is a trend, only a cross-section.",
            "crit",
        )

# ===========================================================================
# PAGE 5 — METHOD
# ===========================================================================
with tab5:
    st.subheader("Scope decisions — ask me about these, they are the real work")
    st.markdown(
        f"""
- **`Aggregate rating = 0` means “not rated”, not “zero stars”.** 2,139 venues (24.7%)
  carry a zero. Keeping them in the average reports **2.52** instead of the correct
  **3.35** — a 0.83-star error. Worse, the bias scales with how many unrated listings
  each city or cuisine happens to have, so it corrupts every *comparison*, not just the
  headline. Every rating measure here divides by rated venues only.
- **Money is India-only.** The raw extract mixes 15 currencies; averaging ₹ with $ is
  arithmetically valid and semantically meaningless. Cost KPIs are scoped to
  `Country = India` (8,652 of 9,551 rows). Currency-free metrics — price tier 1–4,
  rating, service flags — can safely go global.
- **Leaderboards need a credibility floor.** “Top rated” requires ≥ {M.MIN_VOTES} votes;
  city benchmarks ≥ {M.MIN_CITY_N} restaurants; cuisine rankings ≥ {M.MIN_CUISINE_N};
  locality scoring ≥ {M.MIN_LOCALITY_N}. Without them, every “top 10” is a list of venues
  with three reviews.
- **Cuisines are a many-to-many.** One venue lists up to 8 cuisines, so they live in a
  bridge table of 19,714 pairs. Cuisine bars therefore sum to more than the restaurant
  count — correct, and stated on the chart.
"""
    )

    st.subheader("KPI definitions")
    st.dataframe(
        pd.DataFrame([
            ("Restaurants", "Distinct count of Restaurant ID",
             "Distinct, not row count, so a re-listing cannot inflate it."),
            ("Avg / median / P90 cost for two", "mean / median / 90th percentile, India only",
             "Cost is right-skewed (skew ≈ 3.59), so the median is the honest benchmark "
             "and P90 sizes the luxury tail."),
            ("Avg rating", "mean of Aggregate rating over Is Rated = True",
             "The whole project hinges on this exclusion."),
            ("Not rated %", "share of venues with no rating",
             "A coverage metric and a commercial one — these are cold-start venues."),
            ("Online delivery % / Table booking %", "share with the flag set",
             "Channel adoption; the premium-format signal."),
            ("Value score", "rating ÷ (cost for two ÷ 100)",
             "Stars per ₹100. Needs a 4.0 rating floor or cheap-and-bad wins."),
            ("Opportunity score", "z(log(1 + votes per restaurant)) − z(avg rating)",
             "Proven demand minus beatable quality. The log is load-bearing."),
        ], columns=["KPI", "Definition", "Why it is the right measure"]),
        hide_index=True, width="stretch",
    )

    st.subheader("The same measures in DAX (Power BI parity)")
    st.code(
        """Total Restaurants = DISTINCTCOUNT ( fact_restaurants[Restaurant ID] )

Avg Rating =
AVERAGEX (
    FILTER ( fact_restaurants, fact_restaurants[Is Rated] = TRUE() ),
    fact_restaurants[Aggregate rating]
)

Avg Cost for Two =
CALCULATE (
    AVERAGE ( fact_restaurants[Average Cost for two] ),
    KEEPFILTERS ( fact_restaurants[Currency] = "Indian Rupees(Rs.)" )
)

Online Delivery % =
DIVIDE (
    CALCULATE ( [Total Restaurants], fact_restaurants[Has Online delivery] = TRUE() ),
    [Total Restaurants]
)""",
        language="sql",
    )
    st.caption("The full model — Power Query steps, relationships, every measure, "
               "page-by-page visual placement — is in `docs/POWERBI_GUIDE.md`.")

    st.subheader("Known limitations")
    st.markdown(
        """
- Delhi NCR is **91.9%** of the India rows, so national conclusions are really NCR
  conclusions.
- **No timestamps anywhere** in the extract — every number is a cross-section, never a
  trend.
- `Votes` is the only demand proxy available. It measures *reviewing* behaviour, which
  correlates with footfall but skews toward younger, app-native diners.
- No revenue, cover count or cost-of-goods data, so “higher revenue” recommendations are
  directional, not modelled.
"""
    )

    st.subheader("How this app is verified")
    st.markdown(
        """
This Streamlit app is the **third** implementation of the same measures — after the
pandas pipeline and the vanilla-JavaScript HTML dashboard.
`tests/test_streamlit_measures.py` asserts that `app/measures.py` reproduces all 13
reference KPIs in `dashboard/kpis.json` exactly, and that the filter layer behaves
(filters narrow, an impossible filter returns empty rather than throwing). Two
independent implementations agreeing is a real test of the measure logic; one
implementation rendering without errors is not.
"""
    )

st.divider()
st.caption(
    "Zomato Restaurant Analytics · built with pandas + Streamlit + Plotly · "
    "ratings exclude unrated venues · money KPIs are ₹ (India only) · "
    "source: public Zomato dataset, 9,551 restaurants across 15 countries"
)
