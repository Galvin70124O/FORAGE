"""Waste & Expiry: how much is wasted, where, and what is about to expire."""

import pandas as pd
import streamlit as st

from ui import charts
from ui.components import fmt_date, fmt_pct, formula, kpi_row, number, section, table
from views.common import UNIT_NOTE, begin, not_available
from waste import (
    SHORT_SHELF_LIFE_DAYS,
    category_waste,
    expiring_stock,
    food_waste,
    overall_waste,
    perishable_waste_by_category,
    rupee_summary,
    waste_vs_shelf_life,
)
from stats import describe_strength
from views import risk_section

def personal_expiring(as_of, days):
    """Expiring stock from the user's purchases, in the same columns as the demo table."""
    from pantry import expected_stock, expiring_soon, stock_batches
    from services.personal import personal_data
    buys, checks = personal_data()
    soon = expiring_soon(stock_batches(buys, expected_stock(buys, checks, as_of)), as_of, days)
    if soon.empty:
        return pd.DataFrame(columns=["Food", "Quantity_Unit", "Remaining", "Batches", "Earliest_Expiry", "Days_Left"])
    return (soon.groupby(["Food", "Unit"], as_index=False)
            .agg(Remaining=("Quantity", "sum"), Batches=("Quantity", "size"), Earliest_Expiry=("Expiry", "min"),
                 Days_Left=("Days_Left", "min"))
            .rename(columns={"Unit": "Quantity_Unit"}).sort_values("Days_Left"))


source, df = begin("Waste & Expiry", "How much food is wasted, which foods and categories waste most, "
                   "and which stock is close to its expiry date.")

if source in ("m5", "instacart") and df is not None:
    reason = ("M5 records retail unit sales. It has no household stock, consumption, waste or expiry dates."
              if source == "m5" else
              "Instacart records orders and reorders. It has no quantities, consumption, waste or expiry dates.")
    not_available(source, "Waste and expiry analysis",
                  reason + " FORAGE does not estimate waste from sales or orders.",
                  alternatives=["demo", "personal"], key="waste_switch")
elif df is not None:
    headline = overall_waste(df)
    foods = food_waste(df)
    categories = category_waste(df)
    top = foods.iloc[0]
    as_of = df["Date"].max() if source == "demo" else pd.Timestamp.today().normalize()
    if source == "personal":
        soon_3, soon_7 = personal_expiring(as_of, 3), personal_expiring(as_of, 7)
    else:
        soon_3, soon_7 = expiring_stock(df, as_of, 3), expiring_stock(df, as_of, 7)

    rupees = rupee_summary(df)
    illustrative = source == "demo"
    rupee_label = "₹ wasted" + (" · illustrative (synthetic prices)" if illustrative else "")
    kpi_row([
        (rupee_label, f"₹{rupees['total']:,.0f}",
         "Wasted quantity × the food's median price per unit (total price ÷ quantity bought)."),
        ("Waste rate", fmt_pct(headline["rate"]), "Mean of the food-level rates (wasted ÷ purchased). "
         f"Pooled across all units: {fmt_pct(headline['pooled_rate'])}."),
        ("Highest-waste food", f"{top['Food']}", f"{fmt_pct(top['Waste_Rate'])} of purchases wasted."),
        ("Highest-waste category", categories.index[0], f"{fmt_pct(categories.iloc[0]['Waste_Rate'])} on average."),
        ("Expiring in 7 days", f"{len(soon_7)} foods", f"Foods with stock that expires by {fmt_date(as_of + pd.Timedelta(days=7))}."),
    ])
    formula("waste rate = wasted ÷ purchased × 100     ₹ wasted = wasted × (price paid ÷ quantity bought)")
    st.caption("Waste is the recorded quantity wasted, never purchased − consumed (that would count stock still "
               "on hand). " + UNIT_NOTE + (" In the demo data, Price is the total paid for each purchase, so the "
               "price per unit is Price ÷ quantity purchased; prices are synthetic, so ₹ figures are illustrative."
               if illustrative else ""))

    st.header("Waste in rupees")
    if rupees["unpriced_foods"]:
        st.caption("No price recorded for: " + ", ".join(rupees["unpriced_foods"]) + " (left out of ₹ figures).")
    left, right = st.columns([1.2, 1], gap="large")
    with left:
        section("₹ wasted per month", "illustrative (synthetic prices)" if illustrative else "From your own prices")
        charts.line(rupees["monthly"].rename_axis("Month").reset_index(), "Month", "Rupees", x_title="Month",
                    y_title="₹ wasted", y_format=",.0f", slot=1, x_format="%b %Y", height=280)
    with right:
        section("₹ wasted by category", "illustrative (synthetic prices)" if illustrative else None)
        charts.bar(rupees["by_category"].rename_axis("Category").reset_index(), "Category", "Rupees",
                   value_title="₹ wasted", slot=1, value_format=",.0f", height=280)
    section("₹ wasted by food", "illustrative (synthetic prices)" if illustrative else None)
    charts.bar(rupees["by_food"].rename_axis("Food").reset_index(), "Food", "Rupees", value_title="₹ wasted",
               slot=1, value_format=",.0f", height=max(240, 22 * len(rupees["by_food"])))

    st.header("Waste by quantity")

    left, right = st.columns([1.2, 1], gap="large")
    with left:
        section("Waste rate by food", "Share of each food's purchases that was wasted")
        charts.bar(foods, "Food", "Waste_Rate", value_title="Waste rate (%)", slot=1, value_format=".1f",
                   height=max(240, 24 * len(foods)),
                   extra_tooltip=["Category:N", "Quantity_Unit:N"] if "Quantity_Unit" in foods else None)
    with right:
        section("Waste rate by category", "Mean of the food-level rates in each category")
        charts.bar(categories.reset_index(), "Category", "Waste_Rate", value_title="Waste rate (%)", slot=1,
                   value_format=".1f", height=max(240, 30 * len(categories)))
        top3 = foods.head(3)
        st.markdown("**Top 3 wasted foods:** " + "; ".join(
            f"{row.Food} {fmt_pct(row.Waste_Rate)}" for row in top3.itertuples()))

    st.header("Expiry")
    as_of_text = (f"As of {fmt_date(as_of)}, the last date in the demo data." if source == "demo"
                  else f"As of today, {fmt_date(as_of)}.")
    st.caption(as_of_text + (" Stock is what should be on hand now (last pantry check + purchases since − usual "
               "use), split into the purchases it most likely came from (newest first)." if source == "personal" else
               " Stock is each purchase's recorded remaining quantity, assumed still on hand until it expires;")
               + " batches already past expiry are excluded.")
    expiry_columns = {"Quantity_Unit": "Unit", "Remaining": number("Remaining", "%.2f"),
                      "Batches": number("Batches", "%d"), "Earliest_Expiry": st.column_config.DateColumn("Earliest expiry", format="D MMM YYYY"),
                      "Days_Left": number("Days left", "%d")}
    left, right = st.columns(2, gap="large")
    for column, frame, days in ((left, soon_3, 3), (right, soon_7, 7)):
        with column:
            section(f"Expiring within {days} days", f"{len(frame)} foods")
            if frame.empty:
                st.write(f"No remaining stock expires within {days} days.")
            else:
                table(frame.drop(columns=["Category"], errors="ignore"), expiry_columns, max_rows=8)

    left, right = st.columns([1.2, 1], gap="large")
    with left:
        section("Waste rate against shelf life", "One point per food; shelf life is the days from purchase to expiry")
        points, r = waste_vs_shelf_life(df)
        if len(points) > 2:
            charts.scatter(points, "Shelf_Life_Days", "Waste_Rate", x_title="Shelf life at purchase (days, log scale)",
                           y_title="Waste rate (%)", label="Food", log_x=True, height=340,
                           tooltip=["Food:N", "Category:N", charts.tip("Shelf_Life_Days", "Shelf life (days)", "d"),
                                    charts.tip("Waste_Rate", "Waste rate (%)", ".1f")])
            if pd.notna(r):
                direction = ("foods that keep longer are wasted more" if r > 0.2 else
                             "foods that spoil sooner are wasted more" if r < -0.2 else "shelf life barely relates to waste")
                st.markdown(f"**Reading:** {describe_strength(r)} correlation across {len(points)} foods "
                            f"(r = {r:.2f}): {direction}.")
                if source == "demo" and r > 0.2:
                    st.caption("In the demo data this follows from how the data was generated: waste is a random share "
                               "of the unused purchase, regardless of expiry. Real household data is expected to "
                               "show the opposite pattern.")
        else:
            st.write("Needs shelf-life information for at least three foods.")
    with right:
        section("Expiry-driven waste by category",
                f"Waste rate of foods with a shelf life of {SHORT_SHELF_LIFE_DAYS} days or less")
        perishable = perishable_waste_by_category(df)
        if perishable.empty:
            st.write(f"No foods with a shelf life of {SHORT_SHELF_LIFE_DAYS} days or less.")
        else:
            charts.bar(perishable.reset_index(), "Category", "Waste_Rate", value_title="Waste rate (%)", slot=1,
                       value_format=".1f", height=max(200, 34 * len(perishable)),
                       extra_tooltip=[charts.tip("Food_List", "Foods", None)])
            st.caption("The data does not record why food was thrown away, so waste on foods that expire within "
                       "a week is treated as expiry-driven.")

    st.header("Waste-risk model")
    if source == "demo":
        from services.data import demo_classifier
        risk_section.render(demo_classifier(), source=source)
    else:
        from services.data import personal_classifier
        from services.personal import gate, personal_data
        shown, reliable, note = gate("classifier")
        result = personal_classifier(*personal_data()) if shown else None
        if result is None:
            st.write("The classifier trains on your own purchases once at least 30 have been fully used up or thrown "
                     "away, with at least 5 high-waste and 5 normal ones. Until then, Home flags stock that will "
                     "expire before you can eat it at your usual pace. " + note)
        else:
            if not reliable:
                st.warning(note)
            risk_section.render(result, source=source)
