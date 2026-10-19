"""Recommendations: what to act on next, with the calculation shown for each source."""

import pandas as pd
import streamlit as st

from recommendations import PERSONAL_MIN_RECORDS, personal_recommendations
from services.data import demo_recommendations
from ui import charts
from ui.components import empty_state, fmt_date, formula, kpi_row, number, section, table, text
from views.common import begin

PLAN_COLUMNS = {
    "Food": text("Food", "small"), "Quantity_Unit": text("Unit", "small"),
    "Predicted_Demand": number("Predicted demand", "%.2f", "Next-day forecast, in the food's unit."),
    "Current_Remaining_Quantity": number("In stock", "%.2f"),
    "Historical_Waste_Percentage": number("Waste rate (%)", "%.1f"),
    "Usable_Remaining_Stock": number("Usable stock", "%.2f", "In stock × (1 − waste rate)."),
    "Recommended_Purchase_Quantity": number("Buy", "%.2f"),
    "Days_Until_Expiry": number("Days to expiry", "%d"),
    "Alerts": text("Alerts", "medium"),
}
ALERT_TAGS = {"historical waste is in the highest 25% of foods": "High waste",
              "usable stock is below predicted demand": "Low stock",
              "remaining stock has comparatively short shelf life": "Expires soon"}


def short_alerts(alerts: str) -> str:
    return ", ".join(ALERT_TAGS.get(part.strip(), part.strip()) for part in alerts.split(";")) if alerts != "No alert" else "–"

source, df = begin("Recommendations", "What to act on next, derived from the selected source. "
                   "Each recommendation shows the calculation behind it.")

if df is not None:
    if source == "demo":
        plan, high_waste, short_life = demo_recommendations()
        model = plan["Forecast_Model"].iloc[0]
        buy = plan["Recommended_Purchase_Quantity"] > 0
        kpi_row([("Plan for", fmt_date(plan["Forecast_Date"].iloc[0])),
                 ("Foods to buy", f"{int(buy.sum())}"), ("Already covered", f"{int((~buy).sum())}"),
                 ("Foods with alerts", f"{int(plan['Alerts'].ne('No alert').sum())}")])

        st.markdown(f"Forecast model: **{model}**, selected on the Forecasting page.")
        section("How the quantities are calculated")
        formula("usable stock = in stock × (1 − waste rate)")
        formula("buy = max(0, predicted demand − usable stock)")
        st.caption(f"Predicted demand is the next-day forecast from {model}, the model with the lowest error on the "
                   "Forecasting page, refit on all history. In stock is the remaining quantity on the last recorded "
                   "day. Discounting it by the food's own waste rate assumes stock is wasted at the same rate as "
                   "past purchases. Alerts: High waste = waste rate in the top quarter of "
                   f"foods (≥ {high_waste:.1f}%); Low stock = usable stock below demand; Expires soon = stock expiring "
                   f"within {short_life:.0f} days (the shortest quarter).")

        section("Purchase plan", "Sorted by quantity to buy; quantities are in each food's own unit")
        shown = plan.assign(Alerts=plan["Alerts"].map(short_alerts))
        table(shown[list(PLAN_COLUMNS)], PLAN_COLUMNS, max_rows=None)
        choice = st.selectbox("Explain a recommendation", plan["Food"], key="explain_food")
        st.write(plan.set_index("Food").loc[choice, "Reason"])
        st.download_button("Download plan as CSV", plan.to_csv(index=False).encode("utf-8"),
                           file_name="forage_purchase_plan.csv", mime="text/csv")

    elif source == "personal":
        plan = personal_recommendations(df)
        if plan.empty:
            empty_state("Not enough history for recommendations",
                        f"Suggestions need at least {PERSONAL_MIN_RECORDS} records for a food.",
                        page="views/my_data.py", page_label="Add records on My Data")
        else:
            section("How the quantities are calculated")
            formula("predicted demand = mean consumption of the food's last 7 records")
            formula("buy = max(0, predicted demand − in stock × (1 − waste rate))")
            st.caption("Personal histories are usually too short to train and test a model, so the 7-record average "
                       "is used (it is also the moving-average baseline on the Forecasting page).")
            columns = {k: v for k, v in PLAN_COLUMNS.items() if k in plan.columns}
            table(plan[list(columns)], columns)

    elif source == "m5":
        recent_end = df["Date"].max()
        recent = df[df["Date"] > recent_end - pd.Timedelta(days=28)]
        previous = df[(df["Date"] <= recent_end - pd.Timedelta(days=28)) & (df["Date"] > recent_end - pd.Timedelta(days=56))]
        trend = pd.DataFrame({
            "Recent": recent.groupby("Product_ID", observed=True)["Quantity_Sold"].mean(),
            "Previous": previous.groupby("Product_ID", observed=True)["Quantity_Sold"].mean(),
        }).dropna()
        trend = trend[trend["Previous"] >= 1]
        trend["Change"] = (trend["Recent"] - trend["Previous"]) / trend["Previous"] * 100
        trend = trend.sort_values("Change", ascending=False).reset_index().rename(columns={"index": "Product_ID"})
        rising = trend[trend["Change"] >= 20]
        kpi_row([("Items compared", f"{len(trend)}"), ("Rising 20% or more", f"{len(rising)}"),
                 ("Falling 20% or more", f"{int((trend['Change'] <= -20).sum())}"),
                 ("Window", f"to {fmt_date(recent_end)}")])
        section("How this is calculated")
        formula("change = (mean daily units, last 28 days − previous 28 days) ÷ previous 28 days")
        st.caption("Items selling at least one unit a day in the earlier window are compared. Rising items need more "
                   "shelf stock; falling items are at risk of overstock, which is where retail waste starts. M5 has "
                   "no stock or waste data, so these are demand signals, not purchase quantities.")
        left, right = st.columns([1, 1], gap="large")
        with left:
            section("Largest increases")
            charts.bar(trend.head(10), "Product_ID", "Change", value_title="Change in mean daily units (%)",
                       category_title="Item", value_format="+.0f", height=320)
        with right:
            section("Largest decreases")
            charts.bar(trend.tail(10), "Product_ID", "Change", value_title="Change in mean daily units (%)",
                       category_title="Item", value_format="+.0f", sort="x", slot=1, height=320)
        table(trend, {"Product_ID": "Item", "Recent": number("Last 28 days (units/day)"),
                      "Previous": number("Previous 28 days (units/day)"), "Change": number("Change (%)", "%+.1f")},
              max_rows=10)

    else:
        products = df.groupby(["Product_Name", "Department"], observed=True).agg(
            Order_Lines=("Order_ID", "size"), Customers=("User_ID", "nunique"), Reorder_Rate=("Reordered", "mean"))
        products = products[products["Order_Lines"] >= 50].reset_index()
        products["Reorder_Rate"] *= 100
        products = products.sort_values(["Reorder_Rate", "Order_Lines"], ascending=False)
        kpi_row([("Products with 50+ order lines", f"{len(products):,}"),
                 ("Median reorder rate", f"{products['Reorder_Rate'].median():.1f}%"),
                 ("Reordered 80% of the time or more", f"{int((products['Reorder_Rate'] >= 80).sum())}")])
        section("How this is calculated")
        formula("reorder rate = order lines the customer had bought before ÷ all order lines for the product")
        st.caption("Products bought often and reordered most of the time are dependable repeat purchases: good "
                   "candidates for a regular list, and the least likely to be wasted. Products with fewer than 50 "
                   "order lines are left out because their rates are unstable. Instacart has no quantities, so no "
                   "purchase amounts are suggested.")
        section("Most reliable repeat purchases")
        charts.bar(products.head(12), "Product_Name", "Reorder_Rate", value_title="Reorder rate (%)",
                   category_title="Product", value_format=".1f", height=380)
        table(products.head(50), {"Product_Name": "Product", "Department": "Department",
                                  "Order_Lines": number("Order lines", "%d"), "Customers": number("Customers", "%d"),
                                  "Reorder_Rate": number("Reorder rate (%)", "%.1f")}, max_rows=10)
