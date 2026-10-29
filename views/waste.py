"""Waste & Expiry: how much is wasted, where, and what is about to expire."""

import pandas as pd
import streamlit as st

from stats import describe_strength
from ui import charts
from ui.components import (
    count,
    date,
    fmt_date,
    fmt_pct,
    formula,
    kpi_row,
    methods,
    percent_bar,
    section,
    shelf,
    table,
    text,
)
from ui.components import rupees as rupees_column
from views import risk_section
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
methods(['Waste rate = wasted ÷ purchased per food; expiring stock = purchase date + shelf life for what is still on hand.',
         'The waste-risk model predicts from facts known when food is bought whether more than 30% of a purchase will be thrown away. ROC-AUC 0.5 = guessing, 1 = perfect; recall = share of high-waste purchases it catches.'])

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
    rupee_label = "₹ wasted (illustrative)" if illustrative else "₹ wasted"
    kpi_row([
        (rupee_label, f"₹{rupees['total']:,.0f}",
         "Wasted quantity × the food's median price per unit (total price ÷ quantity bought)."
         + (" Illustrative: the demo prices are synthetic." if illustrative else "")),
        ("Waste rate", fmt_pct(headline["rate"]), "Mean of the food-level rates (wasted ÷ purchased). "
         f"Pooled across all units: {fmt_pct(headline['pooled_rate'])}."),
        ("Worst food", f"{top['Food']}", f"Highest waste rate: {fmt_pct(top['Waste_Rate'])} of purchases wasted."),
        ("Worst category", categories.index[0], f"Highest waste rate: {fmt_pct(categories.iloc[0]['Waste_Rate'])} on average."),
        ("Expiring in 7 days", f"{len(soon_7)} foods", f"Foods with stock that expires by {fmt_date(as_of + pd.Timedelta(days=7))}."),
    ])
    formula("waste rate = wasted ÷ purchased × 100")
    formula("₹ wasted = wasted × (price paid ÷ quantity bought)")
    st.caption("Waste is the recorded quantity wasted, never purchased − consumed (that would count stock still "
               "on hand). " + UNIT_NOTE + (" In the demo data, Price is the total paid for each purchase, so the "
               "price per unit is Price ÷ quantity purchased; prices are synthetic, so ₹ figures are illustrative."
               if illustrative else ""))

    waste_tab, expiry_tab, model_tab = st.tabs(["Waste", "Expiry", "Waste-risk model"])
    with waste_tab:
        note = "Illustrative (synthetic prices)" if illustrative else "From the prices you paid"
        if rupees["unpriced_foods"]:
            st.caption("No price recorded for: " + ", ".join(rupees["unpriced_foods"]) + " (left out of ₹ figures).")
        left, right = st.columns(2, gap="large")
        with left:
            monthly = rupees["monthly"]
            peak = monthly.idxmax()
            charts.line(monthly.rename_axis("Month").reset_index(), "Month", "Rupees", x_title=None,
                        y_title="₹ wasted", y_format=",.0f", x_format="%b %Y", label_last=True,
                        title=f"Waste peaked in {peak:%B} at ₹{monthly.max():,.0f}",
                        subtitle=f"₹ wasted per month · {note}")
        with right:
            by_category = rupees["by_category"]
            total = by_category.sum()
            charts.bar(by_category.rename_axis("Category").reset_index(), "Category", "Rupees",
                       value_title="₹ wasted", value_format=",.0f",
                       title=(f"{by_category.index[0]} cost the most: {by_category.iloc[0] / total * 100:.0f}% of ₹ wasted"
                              if total > 0 else "No ₹ wasted yet"),
                       subtitle=f"₹ wasted by category · {note}")
        left, right = st.columns(2, gap="large")
        with left:
            charts.bar(categories.reset_index(), "Category", "Waste_Rate", value_title="Waste rate (%)",
                       value_format=".1f",
                       title=f"{categories.index[0]} waste the highest share: {categories.iloc[0]['Waste_Rate']:.0f}%",
                       subtitle="Waste rate by category (mean of food-level rates)")
        with right:
            top3 = foods.head(3)
            section("Waste by food", "Top 3: " + "; ".join(f"{row.Food} {fmt_pct(row.Waste_Rate)}"
                                                         for row in top3.itertuples()))
            from services.pantry_view import waste_by_food_rows
            table(waste_by_food_rows(foods, rupees["by_food"]), {
                "Food": text("Food"), "Rupees": rupees_column("₹ wasted", width="small"),
                "Waste_Rate": percent_bar("Waste rate"), "Wasted": text("Wasted", None)}, max_rows=9)

    with expiry_tab:
        as_of_text = (f"As of {fmt_date(as_of)}, the last date in the demo data." if source == "demo"
                      else f"As of today, {fmt_date(as_of)}.")
        st.caption(as_of_text + (" Stock is what should be on hand now (last pantry check + purchases since − usual "
                   "use), split into the purchases it most likely came from (newest first)." if source == "personal" else
                   " Stock is each purchase's recorded remaining quantity, assumed still on hand until it expires.")
                   + " The Expired shelf shows stock that passed its date in the last week; the tables leave it out.")
        expiry_columns = {"Food": text("Food"), "Days_Left": count("Days left"), "Left": text("Left", None),
                          "Earliest_Expiry": date("Expires")}
        from services.pantry_view import SHELVES, expiring_rows, shelf_items
        groups = shelf_items(source, df, as_of)
        for key, title, note, empty in SHELVES:
            shelf(title, groups[key], note=note, empty=empty, limit=10)
        st.caption("Each jar is one food's stock in that window; a food with batches in two windows sits on both. "
                   "The meter is the share of its shelf life left (capped at two weeks).")
        with st.expander("Expiring stock as tables (within 3 and 7 days)"):
            left, right = st.columns(2, gap="large")
            for column, frame, days in ((left, soon_3, 3), (right, soon_7, 7)):
                with column:
                    section(f"Expiring within {days} days", f"{len(frame)} foods")
                    if frame.empty:
                        st.write(f"No remaining stock expires within {days} days.")
                    else:
                        table(expiring_rows(frame), expiry_columns, max_rows=8)

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


    with model_tab:
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
