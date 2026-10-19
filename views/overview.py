"""Overview: headline figures for the selected source, framed by SDG 12.3."""

import pandas as pd
import streamlit as st

from services.data import SOURCES
from ui import charts
from ui.components import fmt_pct, kpi_row, section, table
from views.common import UNIT_NOTE, begin
from waste import food_waste, overall_waste

CAPABILITIES = pd.DataFrame({
    "Analysis": ["Descriptive statistics", "Waste and expiry", "Forecasting", "Recommendations"],
    "Demo data": ["Yes", "Yes", "Yes, next-day consumption", "Purchase quantities"],
    "My data": ["Yes, per pantry-check period", "Yes", "7-day use, after 3 weeks", "Weekly buy list"],
    "M5 (Walmart)": ["Yes", "No, waste is not recorded", "Yes, next-day unit sales", "Items with rising demand"],
    "Instacart": ["Yes", "No, waste is not recorded", "No, orders have no dates", "Likely repeat purchases"],
})

source, df = begin(
    "Overview",
    "UN SDG target 12.3 aims to halve per-capita food waste at retail and consumer level by 2030. "
    "FORAGE measures where food is bought, used and wasted, and what to buy next.",
    feature=None,
)

if source == "personal" and (df is None or df.empty):
    from ui.components import empty_state
    if df is not None:
        empty_state("No completed periods yet",
                    "Log what you buy, then do a pantry check: each check closes a period, and your waste rate "
                    "and spending appear here.", page="views/bought.py", page_label="I bought something")
elif df is not None:
    if source in ("demo", "personal"):
        headline = overall_waste(df)
        foods = food_waste(df)
        top = foods.iloc[0]
        consumption_rate = (df.groupby("Food")["Quantity_Consumed"].sum()
                            / df.groupby("Food")["Quantity_Purchased"].sum().where(lambda s: s > 0)).mean() * 100
        kpi_row([
            ("Records", f"{len(df):,}"),
            ("Foods tracked", f"{df['Food'].nunique()}"),
            ("Days covered", f"{df['Date'].nunique():,}"),
            ("Waste rate", fmt_pct(headline["rate"]), "Wasted ÷ purchased per food, averaged across foods."),
            ("Consumption rate", fmt_pct(consumption_rate), "Consumed ÷ purchased per food, averaged across foods."),
        ])
        st.caption(f"Highest waste rate: {top['Food']} at {fmt_pct(top['Waste_Rate'])} of what was bought. {UNIT_NOTE}")

        left, right = st.columns([1.4, 1], gap="large")
        with left:
            section("Waste rate by month", "Wasted ÷ purchased, averaged across foods")
            monthly = (df.assign(Month_Start=df["Date"].dt.to_period("M").dt.to_timestamp())
                       .groupby(["Month_Start", "Food"])[["Quantity_Wasted", "Quantity_Purchased"]].sum())
            monthly = (monthly["Quantity_Wasted"] / monthly["Quantity_Purchased"] * 100).groupby("Month_Start").mean()
            charts.line(monthly.rename("Waste rate").reset_index(), "Month_Start", "Waste rate",
                        x_title="Month", y_title="Waste rate (%)", y_format=".1f", slot=1, x_format="%b %Y",
                        height=280)
        with right:
            section("Waste rate by category", "Mean of the food-level rates")
            by_category = foods.groupby("Category", as_index=False)["Waste_Rate"].mean()
            charts.bar(by_category, "Category", "Waste_Rate", value_title="Waste rate (%)", slot=1,
                       value_format=".1f", height=280)

    elif source == "m5":
        daily = df.groupby("Date", as_index=False)["Quantity_Sold"].sum()
        kpi_row([
            ("Records", f"{len(df):,}"),
            ("Items", f"{df['Product_ID'].nunique()}"),
            ("Days covered", f"{df['Date'].nunique()}"),
            ("Units sold", f"{df['Quantity_Sold'].sum():,.0f}"),
            ("Units per day", f"{daily['Quantity_Sold'].mean():,.0f}", "Mean of daily totals across all items."),
        ])
        st.caption("M5 records retail unit sales. It has no household consumption, stock, expiry or waste.")
        left, right = st.columns([1.4, 1], gap="large")
        with left:
            section("Daily unit sales", "All selected items, store CA_1")
            charts.line(daily, "Date", "Quantity_Sold", x_title="Date", y_title="Units sold per day",
                        y_format=",.0f", height=280)
        with right:
            section("Unit sales by department")
            by_department = df.groupby("Department", as_index=False, observed=True)["Quantity_Sold"].sum()
            charts.bar(by_department, "Department", "Quantity_Sold", value_title="Units sold",
                       value_format=",.0f", height=280)

    else:
        orders = df["Order_ID"].nunique()
        kpi_row([
            ("Order lines", f"{len(df):,}"),
            ("Orders", f"{orders:,}"),
            ("Customers", f"{df['User_ID'].nunique():,}"),
            ("Products", f"{df['Product_ID'].nunique():,}"),
            ("Reorder rate", fmt_pct(df["Reordered"].mean() * 100), "Share of order lines the customer had bought before."),
        ])
        st.caption("Instacart records what was ordered and reordered. It has no quantities, consumption, expiry or waste.")
        left, right = st.columns([1.4, 1], gap="large")
        with left:
            section("Order lines by department")
            by_department = df.groupby("Department", as_index=False, observed=True).size()
            charts.bar(by_department, "Department", "size", value_title="Order lines", value_format=",.0f", height=420)
        with right:
            section("Orders by hour of day", "Distinct orders, by the hour the order was placed")
            by_hour = df.groupby("Order_Hour", as_index=False)["Order_ID"].nunique()
            charts.bar(by_hour, "Order_Hour", "Order_ID", value_title="Orders", category_title="Hour of day",
                       value_format=",.0f", horizontal=False, sort="ascending", height=420)

    section("What each source supports",
            "Sources are never mixed. Pages show a clear notice when the selected source cannot support an analysis.")
    table(CAPABILITIES[["Analysis", SOURCES[source]] + [c for c in CAPABILITIES.columns[1:] if c != SOURCES[source]]])
