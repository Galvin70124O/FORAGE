"""Page prelude shared by the analysis pages: title, purpose line, source label, missing-data states."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services.data import (
    EXTRACT_COMMAND,
    SOURCES,
    current_source,
    describe,
    load,
    offline,
    set_source,
)
from ui.components import empty_state, page_header

OFFLINE_NOTE = {
    "m5": ("Computed offline on the full dataset: the page shows published aggregates (department totals, the 10 "
           "best sellers, model results), with no prices or per-item daily rows."),
    "instacart": ("Computed offline on the full dataset: the page shows published aggregates only (no customer IDs "
                  "or individual orders)."),
}

UNIT_NOTE = ("Quantities are in each food's recorded unit (kg, L, dozen, loaf or pack), so totals are only "
             "compared within a food; rates and percentages are unit-free.")


PERIOD_NOTE = ("My data is recorded per pantry-check period, not per day, so day-level analyses (next-day "
               "forecasts, weekend vs weekday tests) cannot run on it. That is a sample-size limit of weekly "
               "checks, not an error.")


def begin(title: str, purpose: str, *, feature: str | None = "waste",
          greeting: str | None = None) -> tuple[str, pd.DataFrame | None]:
    """Render the page header and return (source key, data). Data is None when nothing can be shown.

    For My data, `feature` names the pantry.UNLOCK rule that must be met before
    the page shows anything (None = always shown, e.g. Data Quality); a
    reliability note with sample sizes is shown when it is met but still thin.
    """
    source = current_source()
    df = load(source)
    page_header(title, purpose, pill=SOURCES[source], detail=describe(source, df), greeting=greeting)
    if df is None:
        empty_state(f"{SOURCES[source]} results have not been built",
                    f"Download the dataset into dataset/, run `{EXTRACT_COMMAND}`, then "
                    "`python scripts/build_public_artifacts.py`. The demo data and your own data work everywhere.")
        switch_buttons(["demo"], f"missing_{source}")
        return source, None
    if offline(source):
        st.caption(OFFLINE_NOTE[source])
    if source == "personal":
        from services.personal import gate
        if feature:
            shown, reliable, note = gate(feature)
            if not shown:
                empty_state("Not enough of your data yet",
                            f"{note} Keep logging purchases and do a pantry check every week or so; this page "
                            "unlocks on its own.", page="views/pantry.py", page_label="Do a pantry check")
                return source, None
            if not reliable:
                st.warning(note)
            else:
                st.caption(note)
        if df.empty and feature:
            empty_state("No completed periods yet",
                        "A period ends at a pantry check after a purchase. Log what you buy, then check your pantry.",
                        page="views/pantry.py", page_label="Do a pantry check")
            return source, None
    return source, df


def switch_buttons(options: list[str], key: str) -> None:
    """Buttons that switch the global data source to one that supports the current page."""
    with st.container(horizontal=True):
        for option in options:
            st.button(f"Use {SOURCES[option]}", key=f"{key}_{option}", on_click=set_source, args=(option,))


def not_available(source: str, what: str, reason: str, *, alternatives: list[str], key: str) -> None:
    empty_state(f"{what} is not available for {SOURCES[source]}", reason)
    switch_buttons(alternatives, key)


STAMP_BAND = 10  # % either side of usual use that still counts as "Buy same"
STAMP_NOTE = ("Stamp: predicted demand against the food's usual daily use. Buy more / Buy less when demand is more "
              "than 10% above / below usual, otherwise Buy same. The last line is the stock-adjusted amount to buy "
              "(predicted demand − usable stock). Confidence comes from the model's typical error for that food "
              "(High under 25% of its average, Medium under 50%).")


def demand_stamp(predicted: float, usual: float, band: float = STAMP_BAND) -> str:
    """"more", "less" or "same": the forecast against usual use, with a ±band % dead zone."""
    if not usual or pd.isna(usual):
        return "same"
    change = (predicted - usual) / usual * 100
    return "more" if change > band else "less" if change < -band else "same"


def demo_demand_cards(limit: int | None = None) -> None:
    """Demand cards for the demo next-day plan, highest predicted demand first."""
    from services.data import demo_plan_with_risk, forecaster_explanations
    from ui.components import demand_card, demand_cards, fmt_qty
    plan = demo_plan_with_risk().sort_values("Predicted_Demand", ascending=False)
    error = forecaster_explanations("demo")["by_item"].set_index("Food")["Relative_MAE"]
    cards = []
    for row in plan.head(limit).itertuples() if limit else plan.itertuples():
        note = (f"Buy {fmt_qty(row.Recommended_Purchase_Quantity, row.Quantity_Unit)} · usable stock "
                f"{fmt_qty(row.Usable_Remaining_Stock)}")
        if "likely to be wasted" in row.Alerts:
            note += f" · waste risk {row.Waste_Risk:.0f}%, buy carefully"
        cards.append(demand_card(row.Food, fmt_qty(row.Predicted_Demand), row.Quantity_Unit,
                                 stamp=demand_stamp(row.Predicted_Demand, row.Historical_Average_Consumption),
                                 what=f"predicted for {pd.Timestamp(row.Forecast_Date):%a %d %b} · usual "
                                      f"{fmt_qty(row.Historical_Average_Consumption)}",
                                 relative_error=error.get(row.Food), note=note))
    demand_cards(cards)
