"""Overview: the dashboard. Four KPIs with month-on-month change, the waste trend, top wasted foods, and actions."""

from html import escape

import pandas as pd
import streamlit as st

from services.data import SOURCES
from ui import charts
from ui.components import chips, empty_state, fmt_date, greeting, kpi_row, methods, section, shelf, table, waste_gauge
from views.common import begin

SHELVES = (("expired", "Expired", "Nothing has gone off. Lovely."),
           ("soon", "Use within 2 days", "Nothing needs using up right now."),
           ("week", "This week", "Nothing else expires this week."))

CAPABILITIES = pd.DataFrame({
    "Analysis": ["Descriptive statistics", "Waste and expiry", "Forecasting", "Recommendations"],
    "Demo data": ["Yes", "Yes", "Next day and 7 days", "Daily and weekly purchase plans"],
    "My data": ["Per pantry-check period", "Yes", "7-day use, after 3 weeks", "Weekly buy list"],
    "M5 (Walmart)": ["Yes", "No, waste is not recorded", "Next day and 7 days", "Rising and falling demand"],
    "Instacart": ["Yes", "No, waste is not recorded", "No, orders have no dates", "Repeat purchases, bought together"],
})


TAG_TONES = {"Use first": "fs-soon", "Expires soon": "fs-soon", "Buy less": "fs-gone", "Reduce stock": "fs-gone",
             "Restock": "fs-fresh", "Regular list": "fs-fresh"}


def action_list(actions: list[dict], empty: str) -> None:
    section("Action list", "The most urgent items and what to do about them")
    if not actions:
        st.write(empty)
        return
    html = "".join(
        f'<div class="fg-action"><div class="fg-action-title"><span class="fg-tag {TAG_TONES.get(a["tag"], "")}">'
        f'{escape(a["tag"])}</span>{escape(a["title"])}</div><div class="fg-action-why">{escape(a["why"])}</div></div>'
        for a in actions)
    st.markdown(html, unsafe_allow_html=True)


def waste_trend(monthly: pd.Series, note: str) -> None:
    if len(monthly) >= 2:
        change = (monthly.iloc[-1] - monthly.iloc[-2]) / monthly.iloc[-2] * 100 if monthly.iloc[-2] else 0
        title = (f"₹{monthly.iloc[-1]:,.0f} wasted in {monthly.index[-1]:%b}, "
                 f"{abs(change):.0f}% {'less' if change < 0 else 'more'} than {monthly.index[-2]:%b}")
    else:
        title = f"₹{monthly.sum():,.0f} wasted so far"
    charts.line(monthly.rename_axis("Month").reset_index(), "Month", "Rupees", x_title=None, y_title="₹ wasted",
                y_format=",.0f", x_format="%b %Y", title=title, subtitle=f"₹ wasted per month · {note}",
                label_last=True, height=300)


def top_wasted(by_food: pd.Series, note: str) -> None:
    top = by_food.head(8)
    if top.empty:
        empty_state("Nothing wasted yet", "No food has been thrown away in the periods so far. Keep it up.")
        return
    share = top.iloc[0] / by_food.sum() * 100 if by_food.sum() else 0
    charts.bar(top.rename_axis("Food").reset_index(), "Food", "Rupees", value_title="₹ wasted",
               value_format=",.0f", title=f"{top.index[0]} is the costliest waste: {share:.0f}% of all ₹ wasted",
               subtitle=f"Top {len(top)} foods by ₹ wasted · {note}")


def shelves_preview(source: str, df: pd.DataFrame, as_of: pd.Timestamp) -> None:
    from services.pantry_view import shelf_items
    groups = shelf_items(source, df, as_of)
    st.html(f'<p class="fs-chart-title">On the shelf</p><p class="fs-chart-sub">As of {fmt_date(as_of)} · '
            "the items needing attention soonest on each shelf</p>")
    for key, title, empty in SHELVES:
        shelf(title, groups[key], empty=empty, limit=2)
    st.page_link("views/waste.py", label="See every shelf", icon=":material/arrow_forward:")


def pantry_dashboard(source: str, df: pd.DataFrame, board: dict, now: pd.Period, as_of: pd.Timestamp) -> None:
    """Demo and My data: four pantry labels, the waste gauge and trend, top wasted foods and the shelves."""
    from services.pantry_view import label_items, pantry_labels
    illustrative = source == "demo"
    note = "Illustrative (synthetic prices)" if illustrative else "From the prices you paid"
    labels = pantry_labels(df, source, now)
    kpi_row(label_items(labels, illustrative=illustrative))
    chips([(name, value + (f" ({delta})" if delta else "")) for name, value, _, delta, _ in board["kpis"][2:]])
    st.caption(f"This month = {labels['month']}" + (", the last month in the demo data" if illustrative else "")
               + f". Each label compares with {labels['previous']}. ₹ values use each food's median price per unit.")
    gauge, trend = st.columns([1, 2], gap="large")
    with gauge:
        if pd.isna(labels["target"]):
            empty_state("No waste target yet", "The target is half of your first month's waste. It appears once a "
                        "month has a pantry check.")
        else:
            waste_gauge(labels["now"]["rate"], labels["target"], previous=labels["before"]["rate"],
                        note=f"Target {labels['target']:.1f}%: half of {labels['first'].to_timestamp():%b %Y}'s "
                             f"{labels['first_rate']:.1f}% (SDG 12.3: halve food waste).")
    with trend:
        waste_trend(board["monthly"], note)
    left, right = st.columns(2, gap="large")
    with left:
        top_wasted(board["by_food"], note)
    with right:
        shelves_preview(source, df, as_of)


source, df = begin("Overview", "Where food is bought, used and wasted, and what to do next. FORAGE is framed by "
                   "UN SDG target 12.3: halve per-capita food waste by 2030.", feature=None, greeting=greeting())
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
        pantry_dashboard(source, df, board, df["Date"].max().to_period("M"), df["Date"].max())
        action_list(board["actions"], "Nothing urgent in the plan. Enjoy your week.")
    elif source == "personal":
        from services.overview import personal_dashboard
        from services.personal import personal_data
        board = personal_dashboard(*personal_data())
        today = pd.Timestamp.today().normalize()
        pantry_dashboard(source, df, board, today.to_period("M"), today)
        action_list(board["actions"], "Nothing is close to expiring or at risk of being wasted. Nice work.")
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
        values = df.values
        kpi_row([("Orders", f"{values['orders']:,}"), ("Reorder rate", f"{values['reorder_rate'] * 100:.1f}%",
                  "Share of order lines the customer had bought before."),
                 ("Items per order", f"{values['items_per_order']:.1f}", "Mean basket size."),
                 ("Products", f"{values['products']:,}")])
        st.caption("Instacart has no calendar dates, so there is no month-on-month change, and no quantities, "
                   "expiry or waste.")
        left, right = st.columns(2, gap="large")
        departments = df.departments.sort_values("Lines", ascending=False)
        with left:
            top = departments.iloc[0]
            charts.bar(departments.head(10), "Department", "Lines", value_title="Order lines", value_format=",.0f",
                       title=f"{top['Department'].capitalize()} fills {top['Lines'] / values['order_lines'] * 100:.0f}% "
                             "of order lines", subtitle="Top 10 departments")
        with right:
            reorder = departments.sort_values("Reorder_Rate", ascending=False)
            charts.bar(reorder.head(10), "Department", "Reorder_Rate", value_title="Reorder rate (%)", value_format=".0f",
                       title=f"{reorder.iloc[0]['Department'].capitalize()} is reordered most "
                             f"({reorder.iloc[0]['Reorder_Rate']:.0f}%)",
                       subtitle="Share of order lines bought before, top 10 departments")
        products = df.products.sort_values(["Reorder_Rate", "Order_Lines"], ascending=False).head(5)
        action_list([{"tag": "Regular list", "title": f"Keep {row.Product_Name} on the regular list",
                      "why": f"Reordered {row.Reorder_Rate:.0f}% of the time across {int(row.Order_Lines):,} order lines."}
                     for row in products.itertuples()], "")

    with st.expander("What each data source supports"):
        st.caption("Sources are never mixed. Pages show a clear notice when the selected source cannot support an "
                   "analysis.")
        table(CAPABILITIES[["Analysis", SOURCES[source]] + [c for c in CAPABILITIES.columns[1:] if c != SOURCES[source]]])
