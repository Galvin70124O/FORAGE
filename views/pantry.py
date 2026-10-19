"""Pantry check: confirm what is left and what was thrown away; consumption is derived from it."""

import pandas as pd
import streamlit as st

from pantry import TOLERANCE, expected_stock
from services import personal
from services.personal import queue_toast, require_user, toast_pending
from ui.components import empty_state, fmt_date, formula, number, page_header

page_header("Pantry check", pill="My data", purpose="Look in your fridge and cupboards: say what is left and what "
            "you threw away. Weekly is enough.")
db, uid = require_user()
toast_pending()

buys, checks = personal.purchases(uid), personal.checks(uid)
day = st.date_input("Check date", value=pd.Timestamp.today().date(), format="DD/MM/YYYY")
stock = expected_stock(buys, checks, day)

if stock.empty:
    empty_state("Nothing to check yet", "Log a purchase first; the foods you buy appear here with the amount you "
                "should still have.", page="views/bought.py", page_label="I bought something")
    st.stop()


def available_for(food: str) -> tuple[float, float, float]:
    """(left at the last check before this date, bought since then up to this date, total available)."""
    earlier = checks[(checks["food"] == food) & (checks["date"] < pd.Timestamp(day))] if not checks.empty else checks
    base = float(earlier.sort_values("date")["remaining"].iloc[-1]) if not earlier.empty else 0.0
    since = earlier["date"].max() if not earlier.empty else pd.Timestamp.min
    bought = float(buys[(buys["food"] == food) & (buys["date"] > since) & (buys["date"] <= pd.Timestamp(day))]["quantity"].sum())
    return base, bought, base + bought


def problem(food: str, unit: str, left, wasted) -> str | None:
    """A friendly message if the amounts are impossible, else None."""
    if left is None or wasted is None or pd.isna(left) or pd.isna(wasted) or left < 0 or wasted < 0:
        return f"{food}: enter amounts of 0 or more."
    base, bought, available = available_for(food)
    if left + wasted > available + TOLERANCE:
        return (f"{food}: {left:g} left + {wasted:g} thrown away is more than the {available:g} {unit} that was "
                f"available ({base:g} at the last check + {bought:g} bought since).")
    return None


recent = buys.sort_values(["date", "id"], ascending=False)["food"].drop_duplicates().tolist() if not buys.empty else []
ordered = recent + sorted(set(stock["Food"]) - set(recent))
one_tab, all_tab = st.tabs(["One food", "Whole pantry"])

with one_tab:
    food = st.selectbox("Food", ordered, key="check_food", help="Most recently bought first.")
    info = stock.set_index("Food").loc[food]
    unit = info["Unit"] or ""
    with st.form("one_check", border=False):
        left_col, right_col = st.columns(2)
        left = left_col.number_input(f"Left now ({unit})", min_value=0.0, value=float(info["Expected"]), step=0.25,
                                     format="%.2f", help="Prefilled with what you should still have.")
        wasted = right_col.number_input(f"Thrown away ({unit})", min_value=0.0, value=0.0, step=0.25, format="%.2f")
        if st.form_submit_button("Save check", type="primary", width="stretch"):
            message = problem(food, unit, left, wasted)
            if message:
                st.error(message)
            else:
                db.add_check(uid, day, food, float(left), float(wasted))
                queue_toast(f"Saved: {food}, {left:g} {unit} left, {wasted:g} thrown away.")
                st.rerun()

with all_tab:
    already = set(checks.loc[checks["date"] == pd.Timestamp(day), "food"]) if not checks.empty else set()
    rows = stock.set_index("Food").loc[ordered].reset_index()
    rows["Left now"], rows["Thrown away"], rows["Include"] = rows["Expected"], 0.0, rows["Expected"] > 0
    st.caption("Prefilled with what you should still have (last check + bought since − usual use). Untick foods "
               "you did not check." + (f" {len(already)} food(s) already checked on this date will be updated."
                                       if already else ""))
    edited = st.data_editor(
        rows[["Include", "Food", "Unit", "Expected", "Left now", "Thrown away"]], hide_index=True, width="stretch",
        num_rows="fixed", key=f"pantry_editor_{day}", disabled=["Food", "Unit", "Expected"],
        column_config={"Include": st.column_config.CheckboxColumn("Check", width="small"),
                       "Expected": number("Expected"), "Left now": number("Left now"),
                       "Thrown away": number("Thrown away")})
    chosen = edited[edited["Include"]].rename(columns={"Left now": "Left", "Thrown away": "Wasted"})
    if st.button(f"Save {len(chosen)} checks", type="primary", disabled=chosen.empty, width="stretch"):
        problems = [m for row in chosen.itertuples() if (m := problem(row.Food, row.Unit or "", row.Left, row.Wasted))]
        if problems:
            for message in problems:
                st.error(message)
        else:
            for row in chosen.itertuples():
                db.add_check(uid, day, row.Food, float(row.Left), float(row.Wasted))
            queue_toast(f"Saved {len(chosen)} pantry checks for {fmt_date(day)}.")
            st.rerun()

with st.expander("How FORAGE uses this"):
    formula("consumed = left at last check + bought since - thrown away - left now")
    st.write("You never type how much you ate: it is worked out from your checks. The more regularly you check, "
             "the sharper your waste rate, buy list and forecasts become.")
