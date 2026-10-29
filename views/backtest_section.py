"""Shared rendering of the recommendation backtest (used by the Recommendations page)."""

import pandas as pd
import streamlit as st

from ui import charts
from ui.components import kpi_row, number, rupees, table

ASSUMPTIONS = [
    "Every household eats exactly the recorded consumption of each day, so demand is identical.",
    "Food is eaten first-in-first-out, oldest batch first.",
    "A batch can be eaten until its shelf life runs out, then it is thrown away (the only waste).",
    "All households start with an empty pantry; stock left at the end is reported, not counted as waste.",
    "Recorded buys what was actually bought. FORAGE daily tops stock up to the day's forecast. FORAGE weekly "
    "orders every 7 days up to the 7-day forecast, never more than can be eaten before it expires.",
]


def render(summary: pd.DataFrame, days: int, *, reference: float | None = None, illustrative: bool = False) -> None:
    recorded = summary.loc["Recorded"]
    plan = summary.loc["FORAGE weekly"] if "FORAGE weekly" in summary.index else summary.loc["FORAGE daily"]
    saved = recorded["Wasted_Rupees"] - plan["Wasted_Rupees"]
    rupee_note = " (illustrative, synthetic prices)" if illustrative else ""
    kpi_row([
        ("Waste, recorded purchases", f"{recorded['Waste_Pct']:.1f}%"),
        (f"Waste, {plan.name}", f"{plan['Waste_Pct']:.1f}%"),
        ("₹ saved" + (" (illustrative)" if illustrative else ""), f"₹{saved:,.0f}",
         f"Over the {days}-day test period{rupee_note}."),
        ("Stock-out food-days", f"{plan['Stockout_Pct']:.0f}%",
         f"Days on which some demand could not be met; {plan['Unmet_Pct']:.1f}% of all demand went unmet."),
    ])
    st.markdown(
        f"**What this means:** a household following {plan.name} would have wasted {plan['Waste_Pct']:.1f}% of what "
        f"it bought instead of {recorded['Waste_Pct']:.1f}%, saving ₹{saved:,.0f} over {days} days{rupee_note}. The "
        f"cost is running short of something on {plan['Stockout_Pct']:.0f}% of food-days ({plan['Unmet_Pct']:.1f}% "
        "of total demand), so in practice a small safety margin would be added to the forecast.")
    chart_data = summary.reset_index()
    left, right = st.columns(2, gap="large")
    with left:
        charts.bar(chart_data, "Policy", "Waste_Pct", value_title="Waste (% of purchases)", value_format=".1f",
                   sort=list(summary.index), horizontal=False, highlight=[plan.name],
                   title=f"Waste falls from {recorded['Waste_Pct']:.1f}% to {plan['Waste_Pct']:.1f}%",
                   subtitle="Wasted ÷ purchased, mean across foods, by household")
    with right:
        charts.bar(chart_data, "Policy", "Stockout_Pct", value_title="Food-days with a stock-out (%)",
                   value_format=".1f", sort=list(summary.index), horizontal=False, highlight=[plan.name],
                   title=f"At the cost of stock-outs on {plan['Stockout_Pct']:.0f}% of food-days",
                   subtitle="Food-days on which demand was not fully met, by household")
    table(chart_data[["Policy", "Waste_Pct", "Wasted_Rupees", "Stockout_Pct", "Unmet_Pct", "Leftover"]], {
        "Waste_Pct": number("Waste (%)", "%.1f"), "Wasted_Rupees": rupees("₹ wasted"),
        "Stockout_Pct": number("Stock-out food-days (%)", "%.1f"), "Unmet_Pct": number("Demand unmet (%)", "%.1f"),
        "Leftover": number("Stock left at the end", "%.1f")})
    if reference is not None:
        st.caption(f"Reference only: the data itself records {reference:.1f}% waste over the same period. That "
                   "figure comes from how the data was generated, not from expiry, so it is not compared directly.")
    with st.expander("Assumptions"):
        for line in ASSUMPTIONS:
            st.markdown(f"- {line}")
