"""Pantry check: confirm what is left and what was thrown away; consumption is derived from it."""

import pandas as pd
import streamlit as st

from pantry import TOLERANCE, expected_stock
from services.personal import queue_toast, require_user, toast_pending
from ui.components import empty_state, fmt_date, formula, number, page_header

page_header("Pantry check", "Look in your fridge and cupboards: correct what is left and add anything you threw "
            "away. Weekly is enough.")
db, uid = require_user()
toast_pending()

buys, checks = db.purchases(uid), db.checks(uid)
day = st.date_input("Check date", value=pd.Timestamp.today().date(), format="DD/MM/YYYY")
stock = expected_stock(buys, checks, day)

if stock.empty:
    empty_state("Nothing to check yet", "Log a purchase first; the foods you buy appear here with the amount you "
                "should still have.", page="views/bought.py", page_label="I bought something")
    st.stop()

already = set(checks.loc[checks["date"] == pd.Timestamp(day), "food"]) if not checks.empty else set()
rows = stock.sort_values(["Expected", "Food"], ascending=[False, True]).copy()
rows["Left now"] = rows["Expected"]
rows["Thrown away"] = 0.0
rows["Include"] = rows["Expected"] > 0
st.caption("Prefilled with what you should still have (last check + bought since − estimated use). Untick foods "
           "you did not check." + (f" {len(already)} food(s) already checked on this date will be updated." if already else ""))

edited = st.data_editor(
    rows[["Include", "Food", "Unit", "Expected", "Left now", "Thrown away"]], hide_index=True, width="stretch",
    num_rows="fixed", key=f"pantry_editor_{day}", disabled=["Food", "Unit", "Expected"],
    column_config={"Include": st.column_config.CheckboxColumn("Check", width="small"),
                   "Expected": number("Expected"), "Left now": number("Left now"),
                   "Thrown away": number("Thrown away")})

chosen = edited[edited["Include"]].rename(columns={"Left now": "Left", "Thrown away": "Wasted"})
if st.button(f"Save {len(chosen)} checks", type="primary", disabled=chosen.empty, width="stretch"):
    problems = []
    for row in chosen.itertuples():
        info = stock.set_index("Food").loc[row.Food]
        last_check = checks[(checks["food"] == row.Food) & (checks["date"] < pd.Timestamp(day))] if not checks.empty else checks
        base = float(last_check.sort_values("date")["remaining"].iloc[-1]) if not last_check.empty else 0.0
        since = last_check["date"].max() if not last_check.empty else pd.Timestamp.min
        bought = float(buys[(buys["food"] == row.Food) & (buys["date"] > since) &
                            (buys["date"] <= pd.Timestamp(day))]["quantity"].sum())
        available = base + bought
        left, wasted = row.Left, row.Wasted
        if pd.isna(left) or left < 0 or pd.isna(wasted) or wasted < 0:
            problems.append(f"{row.Food}: enter amounts of 0 or more.")
        elif left + wasted > available + TOLERANCE:
            problems.append(f"{row.Food}: {left:g} left + {wasted:g} thrown away is more than the {available:g} "
                            f"{info['Unit'] or ''} that was available ({base:g} at the last check + {bought:g} bought).")
    if problems:
        for problem in problems:
            st.error(problem)
    else:
        for row in chosen.itertuples():
            db.add_check(uid, day, row.Food, float(row.Left), float(row.Wasted))
        queue_toast(f"Saved {len(chosen)} pantry checks for {fmt_date(day)}.")
        st.rerun()

with st.expander("How FORAGE uses this"):
    formula("consumed = left at last check + bought since - thrown away - left now")
    st.write("You never type how much you ate: it is worked out from your checks. The more regularly you check, "
             "the sharper your waste rate, buy list and forecasts become.")
