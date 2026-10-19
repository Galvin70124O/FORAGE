"""I bought…: log a purchase in a few taps, or paste a bill."""

import pandas as pd
import streamlit as st

from pantry import parse_bill
from services.personal import foods as cached_foods
from services.personal import purchases as cached_purchases
from services.personal import queue_toast, require_user, toast_pending
from ui.components import fmt_date, page_header, section, table, number

UNITS = ["kg", "g", "L", "ml", "piece", "dozen", "loaf", "pack", "unit"]

page_header("I bought…", pill="My data", purpose="Log a purchase: pick the food, check the amount and price, save.")
db, uid = require_user()
toast_pending()

buys = cached_purchases(uid)
foods = cached_foods(uid)
known = foods.set_index("name") if not foods.empty else pd.DataFrame()
frequent = buys["food"].value_counts().head(8).index.tolist() if not buys.empty else []


def pick_chip() -> None:
    if st.session_state.get("bought_chip"):
        st.session_state["bought_food"] = st.session_state["bought_chip"]


if frequent:
    st.pills("Buy again", frequent, key="bought_chip", on_change=pick_chip)

# Most recently bought first, then the rest alphabetically: the usual pick is at the top on a phone.
recent = buys.sort_values(["date", "id"], ascending=False)["food"].drop_duplicates().tolist() if not buys.empty else []
options = recent + sorted(set(foods["name"]) - set(recent)) if not foods.empty else []
food = st.selectbox("Food", options, index=None, accept_new_options=True, key="bought_food",
                    placeholder="Type a food, e.g. Milk")
last = buys[buys["food"].str.lower() == str(food).lower()].iloc[-1] if food and not buys.empty and \
    (buys["food"].str.lower() == str(food).lower()).any() else None
is_new = bool(food) and str(food).strip().lower() not in {n.lower() for n in options}
food_unit = known.at[food, "unit"] if food in known.index and pd.notna(known.at[food, "unit"]) else None
default_unit = (last["unit"] if last is not None and last["unit"] in UNITS else food_unit) or "unit"

with st.form("bought", border=False):
    left, right = st.columns(2)
    quantity = left.number_input("Quantity", min_value=0.0, step=0.5, format="%.2f",
                                 value=float(last["quantity"]) if last is not None else 1.0)
    unit = right.selectbox("Unit", UNITS, index=UNITS.index(default_unit) if default_unit in UNITS else len(UNITS) - 1)
    price = left.number_input("Total paid (₹)", min_value=0.0, step=5.0, format="%.2f",
                              value=float(last["total_price"]) if last is not None and pd.notna(last["total_price"]) else 0.0,
                              help="What you paid for this purchase in total, not per unit.")
    day = right.date_input("Date", value=pd.Timestamp.today().date(), format="DD/MM/YYYY")
    category, shelf = None, None
    if is_new:
        st.caption("New food: tell FORAGE how to treat it (you can change this later on My data).")
        left, right = st.columns(2)
        category = left.text_input("Category", placeholder="Dairy")
        shelf = right.number_input("Shelf life (days)", min_value=1, value=7, step=1,
                                   help="Days from purchase until it goes off.")
    saved = st.form_submit_button("Save", type="primary", width="stretch")

if saved:
    if not food or not str(food).strip():
        st.error("Choose or type a food first.")
    elif quantity <= 0:
        st.error("Quantity must be more than 0.")
    else:
        db.add_purchase(uid, day, str(food), quantity, unit, price if price > 0 else None,
                        category=category or None, shelf_life_days=shelf)
        queue_toast(f"Saved: {str(food).strip()} {quantity:g} {unit}" + (f" for ₹{price:,.0f}" if price else ""))
        for key in ("bought_food", "bought_chip"):
            st.session_state.pop(key, None)
        st.rerun()

with st.expander("Paste a bill or grocery order"):
    st.caption("One item per line, ending with the price, e.g. `Milk 2 L 120` or `Eggs x12 84`. "
               "You check the rows before anything is saved.")
    bill = st.text_area("Bill text", height=140, label_visibility="collapsed",
                        placeholder="Milk 2 L 120\nEggs x12 84\nTomato 1kg 40")
    if st.button("Read the bill"):
        if bill.strip():
            rows, skipped = parse_bill(bill)
            st.session_state["bill_rows"], st.session_state["bill_skipped"] = rows, skipped
        else:
            st.error("Paste the bill text first.")
    rows = st.session_state.get("bill_rows")
    if rows is not None:
        if st.session_state.get("bill_skipped"):
            st.caption("Not read: " + "; ".join(st.session_state["bill_skipped"]))
        if rows.empty:
            st.write("No items were recognised.")
        else:
            rows = rows.assign(Save=True)
            edited = st.data_editor(rows, hide_index=True, width="stretch", num_rows="fixed", key="bill_editor",
                                    column_config={"food": "Food", "quantity": number("Quantity"),
                                                   "unit": st.column_config.SelectboxColumn("Unit", options=UNITS),
                                                   "total_price": number("Total ₹"), "Save": st.column_config.CheckboxColumn("Save")})
            chosen = edited[edited["Save"]]
            if st.button(f"Save {len(chosen)} purchases", type="primary", disabled=chosen.empty):
                for row in chosen.itertuples():
                    db.add_purchase(uid, pd.Timestamp.today(), row.food, row.quantity, row.unit,
                                    row.total_price if row.total_price > 0 else None)
                st.session_state.pop("bill_rows", None)
                queue_toast(f"Saved {len(chosen)} purchases from the bill.")
                st.rerun()

if not buys.empty:
    section("Recent purchases", "Edit or delete them on My data")
    recent = buys.sort_values(["date", "id"], ascending=False).head(5)
    table(recent[["date", "food", "quantity", "unit", "total_price"]], {
        "date": st.column_config.DateColumn("Date", format="D MMM"), "food": "Food",
        "quantity": number("Qty", "%g"), "unit": "Unit", "total_price": number("₹", "%.0f")})
    st.caption(f"{len(buys):,} purchases logged since {fmt_date(buys['date'].min())}.")
