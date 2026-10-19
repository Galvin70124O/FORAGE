"""Overview: the dashboard. Four KPIs with month-on-month change, the waste trend, top wasted foods, and actions."""

from html import escape

import pandas as pd
import streamlit as st

from services.data import SOURCES
from ui import charts
from ui.components import empty_state, kpi_row, methods, section, table
from views.common import begin

CAPABILITIES = pd.DataFrame({
    "Analysis": ["Descriptive statistics", "Waste and expiry", "Forecasting", "Recommendations"],
    "Demo data": ["Yes", "Yes", "Next day and 7 days", "Daily and weekly purchase plans"],
    "My data": ["Per pantry-check period", "Yes", "7-day use, after 3 weeks", "Weekly buy list"],
    "M5 (Walmart)": ["Yes", "No, waste is not recorded", "Next day and 7 days", "Rising and falling demand"],
    "Instacart": ["Yes", "No, waste is not recorded", "No, orders have no dates", "Repeat purchases, bought together"],
})


def action_list(actions: list[dict], empty: str) -> None:
    section("Action list", "The most urgent items and what to do about them")
    if not actions:
        st.write(empty)
        return
    html = "".join(
        f'<div class="fg-action"><div class="fg-action-title"><span class="fg-tag">{escape(a["tag"])}</span>'
        f'{escape(a["title"])}</div><div class="fg-action-why">{escape(a["why"])}</div></div>' for a in actions)
    st.markdown(html, unsafe_allow_html=True)


def rupee_charts(monthly: pd.Series, by_food: pd.Series, *, illustrative: bool) -> None:
    note = "Illustrative (synthetic prices)" if illustrative else "From the prices you paid"
    left, right = st.columns(2, gap="large")
    with left:
        if len(monthly) >= 2:
            change = (monthly.iloc[-1] - monthly.iloc[-2]) / monthly.iloc[-2] * 100 if monthly.iloc[-2] else 0
            title = (f"₹{monthly.iloc[-1]:,.0f} wasted in {monthly.index[-1]:%b}, "
                     f"{abs(change):.0f}% {'less' if change < 0 else 'more'} than {monthly.index[-2]:%b}")
        else:
            title = f"₹{monthly.sum():,.0f} wasted so far"
        charts.line(monthly.rename_axis("Month").reset_index(), "Month", "Rupees", x_title=None, y_title="₹ wasted",
                    y_format=",.0f", x_format="%b %Y", title=title, subtitle=f"₹ wasted per month · {note}",
                    label_last=True)
    with right:
        top = by_food.head(8)
        if not top.empty:
            share = top.iloc[0] / by_food.sum() * 100 if by_food.sum() else 0
            charts.bar(top.rename_axis("Food").reset_index(), "Food", "Rupees", value_title="₹ wasted",
                       value_format=",.0f", title=f"{top.index[0]} is the costliest waste: {share:.0f}% of all ₹ wasted",
                       subtitle=f"Top {len(top)} foods by ₹ wasted · {note}")


source, df = begin("Overview", "Where food is bought, used and wasted, and what to do next. FORAGE is framed by "
                   "UN SDG target 12.3: halve per-capita food waste by 2030.", feature=None)
methods(['Each figure compares this month with last month; arrows show the direction and colour is never the only cue.',
         "Waste rate = wasted ÷ purchased for each food, averaged across foods. ₹ wasted = wasted quantity × the food's median price per unit.",
         'Forecast accuracy = 1 − WAPE: one minus the total absolute forecast error divided by total actual demand.'])

if source == "personal" and (df is None or df.empty):
    if df is not None:
        empty_state("No completed periods yet",
                    "Log what you buy, then do a pantry check: each check closes a period, and your waste, spending "
                    "and actions appear here.", page="views/bought.py", page_label="I bought something")
elif df is not None:
    if source == "demo":
        from services.overview import demo_dashboard
        board = demo_dashboard()
        kpi_row(board["kpis"])
        st.caption(f"This month = {board['month']}, the last month in the demo data. Forecast accuracy = 1 − WAPE "
                   "(total absolute error ÷ total actual).")
        rupee_charts(board["monthly"], board["by_food"], illustrative=True)
        action_list(board["actions"], "Nothing urgent in the plan.")
    elif source == "personal":
        from services.overview import personal_dashboard
        from services.personal import personal_data
        board = personal_dashboard(*personal_data())
        kpi_row(board["kpis"])
        st.caption(f"This month = {board['month']}. Changes compare with last month; they appear once both months "
                   "have data.")
        rupee_charts(board["monthly"], board["by_food"], illustrative=False)
        action_list(board["actions"], "Nothing is close to expiring or at risk of being wasted.")
    elif source == "m5":
        from services.overview import m5_dashboard
        board = m5_dashboard()
        kpi_row(board["kpis"])
        st.caption("M5 records retail unit sales only: no household consumption, stock, expiry or waste.")
        left, right = st.columns(2, gap="large")
        with left:
            weekly = board["weekly"]
            charts.line(weekly.rename_axis("Week").reset_index(), "Week", "Units", x_title=None,
                        y_title="Units sold per week", y_format=",.0f", label_last=True,
                        title=f"{weekly.iloc[-2]:,.0f} units in the last full week",
                        subtitle="Weekly unit sales, 100 food items, store CA_1")
        with right:
            top = board["top"].head(8)
            charts.bar(top.rename_axis("Item").reset_index(), "Item", "Units", value_title="Units sold",
                       value_format=",.0f", title=f"{top.index[0]} sells the most",
                       subtitle="Top 8 items by units sold (M5 item IDs)")
        action_list(board["actions"], "No item changed by 20% or more.")
    else:
        orders = df["Order_ID"].nunique()
        basket = df.groupby("Order_ID").size()
        kpi_row([("Orders", f"{orders:,}"), ("Reorder rate", f"{df['Reordered'].mean() * 100:.1f}%",
                  "Share of order lines the customer had bought before."),
                 ("Items per order", f"{basket.mean():.1f}", "Mean basket size."),
                 ("Products", f"{df['Product_ID'].nunique():,}")])
        st.caption("Instacart has no calendar dates, so there is no month-on-month change, and no quantities, "
                   "expiry or waste.")
        left, right = st.columns(2, gap="large")
        departments = df.groupby("Department", observed=True).size().sort_values(ascending=False)
        with left:
            charts.bar(departments.head(10).rename("Lines").rename_axis("Department").reset_index(), "Department",
                       "Lines", value_title="Order lines", value_format=",.0f",
                       title=f"{departments.index[0].capitalize()} fills {departments.iloc[0] / len(df) * 100:.0f}% "
                             "of order lines", subtitle="Top 10 departments")
        with right:
            reorder = df.groupby("Department", observed=True)["Reordered"].mean().mul(100).sort_values(ascending=False)
            charts.bar(reorder.head(10).rename("Rate").rename_axis("Department").reset_index(), "Department", "Rate",
                       value_title="Reorder rate (%)", value_format=".0f",
                       title=f"{reorder.index[0].capitalize()} is reordered most ({reorder.iloc[0]:.0f}%)",
                       subtitle="Share of order lines bought before, top 10 departments")
        products = df.groupby("Product_Name", observed=True).agg(Lines=("Order_ID", "size"), Rate=("Reordered", "mean"))
        products = products[products["Lines"] >= 50].sort_values("Rate", ascending=False).head(5)
        action_list([{"tag": "Regular list", "title": f"Keep {name} on the regular list",
                      "why": f"Reordered {row.Rate * 100:.0f}% of the time across {int(row.Lines):,} order lines."}
                     for name, row in products.iterrows()], "")

    with st.expander("What each data source supports"):
        st.caption("Sources are never mixed. Pages show a clear notice when the selected source cannot support an "
                   "analysis.")
        table(CAPABILITIES[["Analysis", SOURCES[source]] + [c for c in CAPABILITIES.columns[1:] if c != SOURCES[source]]])
