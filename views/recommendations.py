"""Recommendations: what to act on next, with the calculation shown for each source."""

import pandas as pd
import streamlit as st

from recommendations import weekly_plan
from services.data import (
    demo_backtest,
    demo_plan_with_risk,
    demo_recommendations,
    demo_week,
    forecaster_explanations,
    load_demo,
)
from ui import charts
from ui.components import (
    count,
    demand_card,
    demand_cards,
    fmt_date,
    formula,
    kpi_row,
    methods,
    number,
    percent_bar,
    quantity,
    section,
    table,
    text,
)
from views import backtest_section
from views.common import STAMP_NOTE, begin, demo_demand_cards

PLAN_COLUMNS = {
    "Food": text("Food", "small"), "Recommended_Purchase_Quantity": number("Buy", "%.2f"),
    "Quantity_Unit": text("Unit", "small"),
    "Predicted_Demand": number("Predicted demand", "%.2f", "Next-day forecast, in the food's unit."),
    "Historical_Waste_Percentage": percent_bar("Waste rate"),
    "Usable_Remaining_Stock": number("Usable stock", "%.2f", "In stock × (1 − waste rate)."),
    "Waste_Risk": st.column_config.ProgressColumn("Waste risk", format="%.0f%%", min_value=0, max_value=100,
                                                  help="Classifier probability that this purchase ends up high waste."),
    "Alerts": text("Alerts", "medium"),
}
ALERT_TAGS = {"historical waste is in the highest 25% of foods": "High waste",
              "usable stock is below predicted demand": "Low stock",
              "remaining stock has comparatively short shelf life": "Expires soon",
              "likely to be wasted": "Likely wasted"}


def short_alerts(alerts: str) -> str:
    return ", ".join(ALERT_TAGS.get(part.strip(), part.strip()) for part in alerts.split(";")) if alerts != "No alert" else "–"

source, df = begin("Recommendations", "What to act on next, derived from the selected source. "
                   "Each recommendation shows the calculation behind it.")
methods(['Buy = forecast demand − stock that will still be good. The backtest replays the test period day by day with the same demand, eating oldest food first and binning food past its shelf life.',
         'Association rules: support = how common the items are together, confidence = how often the second follows the first, lift > 1 = bought together more often than chance.'])

if df is not None:
    if source == "demo":
        plan_tab, backtest_tab = st.tabs(["Purchase plan", "Backtest: does it work?"])
        with plan_tab:
            _, high_waste, short_life = demo_recommendations()
            plan = demo_plan_with_risk()
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
                       "past purchases. Waste risk is the classifier on Waste & Expiry; Likely wasted = above its alert threshold. Alerts: High waste = waste rate in the top quarter of "
                       f"foods (≥ {high_waste:.1f}%); Low stock = usable stock below demand; Expires soon = stock expiring "
                       f"within {short_life:.0f} days (the shortest quarter).")

            section("Food by food", "Predicted demand for each food, highest first, with what to buy")
            demo_demand_cards()
            st.caption(STAMP_NOTE)

            section("Purchase plan", "Sorted by quantity to buy; quantities are in each food's own unit")
            shown = plan.assign(Alerts=plan["Alerts"].map(short_alerts))
            table(shown[list(PLAN_COLUMNS)], PLAN_COLUMNS, max_rows=None)
            choice = st.selectbox("Explain a recommendation", plan["Food"], key="explain_food")
            st.write(plan.set_index("Food").loc[choice, "Reason"])
            st.download_button("Download plan as CSV", plan.to_csv(index=False).encode("utf-8"),
                               file_name="forage_purchase_plan.csv", mime="text/csv")

            week = demo_week()
            records = load_demo()
            weekly = weekly_plan(plan, week["latest"], records.groupby("Food")["Expiry_Days"].median())
            weekly["Shop_Again_In_Days"] = weekly["Shop_Again_In_Days"].map(
                lambda d: f"in {d:.0f} days" if pd.notna(d) else "")
            weekly = weekly[["Food", "Buy_Now"] + [c for c in weekly.columns if c not in ("Food", "Buy_Now")]]
            section("Weekly plan: one shop for the next 7 days",
                    f"From the 7-day forecast ({week['best']}, chosen on the Forecasting page)")
            formula("buy now = max(0, 7-day forecast × days it keeps (up to 7) ÷ 7 − usable stock)")
            table(weekly, {"Quantity_Unit": "Unit", "Week_Forecast": number("7-day forecast"),
                           "Usable_Remaining_Stock": number("Usable stock"), "Covers_Days": number("Covers (days)", "%d"),
                           "Buy_Now": number("Buy now"), "Shop_Again_In_Days": "Shop again"},
                  max_rows=None)
            st.caption("Foods that keep fewer than 7 days are bought for as long as they last, with a reminder to "
                       "shop again; this is the weekly policy simulated in the Backtest tab.")

        with backtest_tab:
            summary, _, reference, days = demo_backtest()
            section("Would a household following FORAGE waste less?",
                    f"Simulated over the {days}-day forecast test period, one food at a time")
            backtest_section.render(summary, days, reference=reference, illustrative=True)

    elif source == "personal":
        plan_tab, backtest_tab = st.tabs(["Buy list", "Backtest: does it work?"])
        with plan_tab:
            from pantry import buy_list, expected_stock, stock_batches
            from services.personal import gate, personal_data
            buys, checks = personal_data()
            today = pd.Timestamp.today().normalize()
            stock = expected_stock(buys, checks, today)
            plan = buy_list(stock, stock_batches(buys, stock), today, 7)
            shown, reliable, note = gate("buy_list")
            section("How the quantities are calculated")
            formula("need = your usual daily use (last 4 pantry-check periods) × 7 days")
            formula("buy = max(0, need − stock that will still be good during the week)")
            (st.caption if reliable else st.warning)(note)
            table(plan[["Food", "Buy", "Unit", "Need", "Usable_Stock"]].round({"Buy": 2, "Need": 2, "Usable_Stock": 2}),
                  {"Need": quantity("Need (7 days)"), "Usable_Stock": quantity("Good stock"), "Buy": quantity("Buy")},
                  max_rows=15)

        with backtest_tab:
            from backtest import personal_frame, run_backtest, summarise
            shown, reliable, note = gate("backtest")
            frame = personal_frame(buys, checks) if shown else pd.DataFrame()
            if frame.empty:
                st.write(note)
            else:
                if not reliable:
                    st.warning(note)
                st.caption("Daily use is each period's derived consumption spread evenly over its days, "
                           "because pantry checks do not record which day food was eaten.")
                backtest_section.render(summarise(run_backtest(frame)), int(frame["Date"].nunique()))

    elif source == "m5":
        counts, trend = df.values["trend_counts"], df.trends.sort_values("Change", ascending=False)
        kpi_row([("Items compared", f"{counts['compared']}"), ("Rising 20% or more", f"{counts['rising']}"),
                 ("Falling 20% or more", f"{counts['falling']}"),
                 ("Window", f"to {fmt_date(pd.Timestamp(counts['window_end']))}")])
        section("How this is calculated")
        formula("change = (mean daily units, last 28 days − previous 28 days) ÷ previous 28 days")
        st.caption("Items selling at least one unit a day in the earlier window are compared. Rising items need more "
                   "shelf stock; falling items are at risk of overstock, which is where retail waste starts. M5 has "
                   "no stock or waste data, so these are demand signals, not purchase quantities.")
        if df.offline:
            st.caption("Computed offline on the full dataset; online the page shows the 5 largest increases and "
                       "the 5 largest decreases.")
        shown = 10 if not df.offline else 5
        explained = forecaster_explanations("m5").get("by_item")
        error = (explained.set_index("Product_ID")["Relative_MAE"]
                 if explained is not None and "Product_ID" in explained else pd.Series(dtype=float))

        def trend_cards(rows: pd.DataFrame) -> None:
            demand_cards([demand_card(
                row.Product_ID, f"{row.Recent:.1f}", "units/day",
                stamp="more" if row.Change >= 20 else "less" if row.Change <= -20 else "same",
                what=f"last 28 days · was {row.Previous:.1f} ({row.Change:+.0f}%)",
                relative_error=error.get(row.Product_ID),
                note="Rising: keep more on the shelf." if row.Change >= 20 else
                     "Falling: order less to avoid overstock." if row.Change <= -20 else "Steady demand.")
                for row in rows.itertuples()])

        section("Largest increases", "Restock: demand is up 20% or more")
        trend_cards(trend.head(shown))
        section("Largest decreases", "Order less: demand is down 20% or more")
        trend_cards(trend.tail(shown).sort_values("Change"))
        st.caption("Stamps: Buy more for a rise of 20% or more, Buy less for a fall of 20% or more. Confidence, where "
                   "shown, comes from the forecasting model's typical error for that item.")
        table(trend, {"Product_ID": "Item", "Recent": number("Last 28 days (units/day)"),
                      "Previous": number("Previous 28 days (units/day)"), "Change": number("Change (%)", "%+.1f")},
              max_rows=10)

    else:
        repeat_tab, together_tab = st.tabs(["Repeat purchases", "Bought together"])
        with together_tab:
            from basket import DEFINITIONS, bought_together, strongest_rules
            from services.data import instacart_rules
            (orders, products), rules = instacart_rules()
            section("Products bought together", f"Association rules (FP-growth) on {orders:,} orders that contain at "
                    f"least two of the {products} most-ordered products; minimum support 0.5%, lift above 1.2")
            for name, meaning in DEFINITIONS.items():
                st.markdown(f"**{name}:** {meaning}")
            top = strongest_rules(rules, 10)
            table(top[["If", "Then", "Support", "Confidence", "Lift"]], {
                "If": text("If the basket has", "medium"), "Then": text("it often also has", "medium"),
                "Support": number("Support", "%.3f"), "Confidence": number("Confidence", "%.2f"),
                "Lift": number("Lift", "%.2f")}, max_rows=None)
            st.caption(f"{len(rules):,} rules found; each pair is shown once, in its stronger direction.")
            choices = sorted({next(iter(a)) for a in rules["Antecedents"] if len(a) == 1})
            product = st.selectbox("Frequently bought together with", choices,
                                   index=choices.index("Banana") if "Banana" in choices else 0, key="together_product")
            matches = bought_together(rules, product)
            if matches.empty:
                st.write("No rule passes the thresholds for this product.")
            else:
                table(matches, {"Then": text("Also in the basket", "large"), "Support": number("Support", "%.3f"),
                                "Confidence": number("Confidence", "%.2f"), "Lift": number("Lift", "%.2f")})
        with repeat_tab:
            products = df.products.sort_values(["Reorder_Rate", "Order_Lines"], ascending=False)
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
                                      "Order_Lines": count("Order lines"), "Customers": count("Customers"),
                                      "Reorder_Rate": number("Reorder rate (%)", "%.1f")}, max_rows=10)
