"""Home: what needs attention today, from the signed-in user's own purchases and pantry checks."""

import pandas as pd
import streamlit as st

from pantry import (
    analysis_frame,
    buy_list,
    coverage,
    expected_stock,
    expiring_soon,
    likely_wasted,
    stock_batches,
    unlocked,
    wasted_value,
)
from services.personal import require_user, toast_pending
from ui.components import empty_state, fmt_date, kpi_row, number, page_header, section, table

def classifier_risk(buys, checks, cover):
    """Highest classifier probability of high waste among each food's open purchases, once the model is unlocked."""
    if not unlocked("classifier", cover)[0]:
        return None
    from pantry import purchase_outcomes
    from services.data import personal_classifier
    from waste_risk import score_purchases
    result = personal_classifier(buys, checks)
    if result is None:
        return None
    open_buys = purchase_outcomes(buys, checks)
    open_buys = open_buys[open_buys["Resolved"].isna()].dropna(subset=["Expiry_Days", "Recent_Consumption"])
    if open_buys.empty:
        return None
    open_buys = open_buys.assign(Day_of_Week=open_buys["Date"].dt.day_name())
    return score_purchases(result["model"], open_buys).groupby(open_buys["Food"]).max()


page_header("Home", "What needs your attention today, from your own purchases and pantry checks.")
db, uid = require_user()
toast_pending()

with st.container(horizontal=True):
    st.page_link("views/bought.py", label="I bought…", icon=":material/add_shopping_cart:")
    st.page_link("views/pantry.py", label="Pantry check", icon=":material/kitchen:")

buys, checks = db.purchases(uid), db.checks(uid)
if buys.empty:
    empty_state("Start by logging what you buy",
                "Each time you shop, add it under I bought… (it takes three taps). Then once a week, do a pantry "
                "check. FORAGE works out what you ate and wasted, warns you before food expires and tells you what "
                "to buy.", page="views/bought.py", page_label="Log a purchase")
    st.stop()

today = pd.Timestamp.today().normalize()
cover = coverage(buys, checks)
frame = analysis_frame(buys, checks)
stock = expected_stock(buys, checks, today)
batches = stock_batches(buys, stock)
soon = expiring_soon(batches, today, 3)
risk = likely_wasted(batches, today)
plan = buy_list(stock, batches, today, 7)

month = frame[frame["Date"] >= today.replace(day=1)] if not frame.empty else frame
waste_shown, _, waste_note = unlocked("waste", cover)
month_value = float(wasted_value(month).sum(min_count=1)) if not month.empty else 0.0
waste_rate = (frame["Quantity_Wasted"].sum() / (frame["Opening_Stock"] + frame["Quantity_Purchased"]).sum() * 100
              if waste_shown and not frame.empty else None)
kpi_row([
    ("₹ wasted this month", f"₹{month_value:,.0f}" if waste_shown else "–",
     "Thrown away at pantry checks this month × what you paid per unit."),
    ("Waste rate", f"{waste_rate:.1f}%" if waste_rate is not None else "–", "Thrown away ÷ food available, all periods."),
    ("Expiring in 3 days", f"{len(soon)}"),
    ("Spent this month", f"₹{buys.loc[buys['date'] >= today.replace(day=1), 'total_price'].sum():,.0f}"),
])
st.caption(waste_note)

left, right = st.columns(2, gap="large")
with left:
    section("Expiring soon", "Stock that reaches its shelf life within 3 days")
    if soon.empty:
        st.write("Nothing expires in the next 3 days.")
    else:
        table(soon[["Food", "Quantity", "Unit", "Expiry", "Days_Left"]], {
            "Quantity": number("Amount", "%.2f"), "Expiry": st.column_config.DateColumn("Expires", format="D MMM"),
            "Days_Left": number("Days left", "%d")}, max_rows=6)
with right:
    section("Likely to be wasted", "Will expire before you can eat it at your usual pace")
    shown, reliable, note = unlocked("buy_list", cover)
    if not shown:
        st.write("Appears after your first pantry check, once FORAGE knows how fast you use each food.")
    elif risk.empty:
        st.write("Nothing at risk at your current pace.")
    else:
        risk = risk.groupby(["Food", "Unit"], as_index=False).agg(
            At_Risk=("At_Risk", "sum"), Expiry=("Expiry", "min"), Value=("Value", "sum"))
        model_risk = classifier_risk(buys, checks, cover)
        if model_risk is not None:
            risk["Model_Risk"] = risk["Food"].map(model_risk) * 100
        table(risk[[c for c in ["Food", "At_Risk", "Unit", "Expiry", "Value", "Model_Risk"] if c in risk]], {
            "Model_Risk": st.column_config.ProgressColumn("Model risk", format="%.0f%%", min_value=0, max_value=100),
            "At_Risk": number("At risk", "%.2f"), "Expiry": st.column_config.DateColumn("By", format="D MMM"),
            "Value": number("Worth (₹)", "%.0f")}, max_rows=6)
        st.caption(note)

section("What to buy this week", "Your usual use over 7 days minus stock that will still be good")
shown, reliable, note = unlocked("buy_list", cover)
if not shown:
    st.write("Appears after your first pantry check. " + note)
else:
    to_buy = plan[plan["Buy"] > 0]
    if to_buy.empty:
        st.write("You have enough of everything for the next 7 days.")
    else:
        table(to_buy, {"Need": number("Need (7 days)"), "Usable_Stock": number("Good stock"), "Buy": number("Buy")},
              max_rows=10)
    (st.caption if reliable else st.warning)(note)

if not checks.empty:
    st.caption(f"Last pantry check: {fmt_date(checks['date'].max())}. "
               f"{len(buys):,} purchases and {len(checks):,} checks logged.")
