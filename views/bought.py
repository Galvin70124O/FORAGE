"""I bought… (Kitchen mode): tap a food, choose an everyday amount, save. Repeat buttons and bill paste included."""

import pandas as pd
import streamlit as st

from kitchen import (
    CATEGORIES,
    UNITS,
    amount_text,
    frequent_foods,
    guess,
    last_purchase,
    last_week,
    preset_for,
    presets,
)
from pantry import parse_bill
from services.personal import foods as cached_foods
from services.personal import purchases as cached_purchases
from services.personal import require_user
from ui.components import fit_height, fmt_date, quantity, rupees, section
from ui.kitchen import flash, page_title, success, t, tiles

page_title("nav_bought", "bought_purpose")
db, uid = require_user()
flash()

buys, foods = cached_purchases(uid), cached_foods(uid)
today = pd.Timestamp.today().normalize()
known_units = dict(zip(foods["name"], foods["unit"])) if not foods.empty else {}


def describe(row) -> str:
    return f"{preset_for(row['unit'], row['quantity']) or amount_text(row['quantity'], row['unit'])}"


def choose(food: str | None) -> None:
    st.session_state["k_food"] = food
    st.session_state.pop("k_search", None)


def picked_from_search() -> None:
    if st.session_state.get("k_search"):
        st.session_state["k_food"] = str(st.session_state["k_search"]).strip()


@st.dialog(t("repeat_week_title"))
def confirm_repeat_week(rows: pd.DataFrame) -> None:
    st.write(t("repeat_week_body", n=len(rows)))
    st.markdown("\n".join(f"- {row['food']}: {describe(row)}" for _, row in rows.iterrows()))
    with st.container(horizontal=True):
        if st.button(t("add_them"), type="primary"):
            for _, row in rows.iterrows():
                db.add_purchase(uid, today, row["food"], float(row["quantity"]), row["unit"],
                                None if pd.isna(row["total_price"]) else float(row["total_price"]))
            success(t("saved_many", n=len(rows)))
            st.rerun()
        if st.button(t("cancel")):
            st.rerun()


# Repeat buttons: the fastest way to log a usual shop.
last = last_purchase(buys)
week = last_week(buys, today)
if last is not None or not week.empty:
    with st.container(horizontal=True, key="fg-tiles-repeat"):
        if last is not None and st.button(t("repeat_last", food=last["food"], amount=describe(last)),
                                          icon=":material/replay:"):
            db.add_purchase(uid, today, last["food"], float(last["quantity"]), last["unit"],
                            None if pd.isna(last["total_price"]) else float(last["total_price"]))
            success(t("saved_purchase", food=last["food"], amount=describe(last), price=""))
            st.rerun()
        if not week.empty and st.button(t("repeat_week", n=len(week)), icon=":material/event_repeat:"):
            confirm_repeat_week(week)

# 1. Which food: big tiles for the usual foods, search for anything else.
food = st.session_state.get("k_food")
usual = frequent_foods(buys)
section(t("your_foods") if not buys.empty else t("starter_foods"))
tapped = tiles(usual, "food", selected=food)
if tapped:
    choose(None if tapped == food else tapped)
    st.rerun()
names = sorted(set(foods["name"]) if not foods.empty else set()) or []
st.selectbox(t("search_food"), [n for n in names if n not in usual], index=None, accept_new_options=True,
             key="k_search", placeholder=t("search_placeholder"), on_change=picked_from_search)

if food:
    previous = buys[buys["food"].str.lower() == food.lower()] if not buys.empty else buys
    previous = previous.sort_values(["date", "id"]).iloc[-1] if not previous.empty else None
    is_new = food.lower() not in {n.lower() for n in names}
    unit_guess, category_guess, shelf_guess = guess(food)
    stored_unit = previous["unit"] if previous is not None and pd.notna(previous["unit"]) else known_units.get(food)
    unit = stored_unit if isinstance(stored_unit, str) and stored_unit else unit_guess

    st.subheader(food)
    # 2. How much: everyday choices in the food's own unit; any other amount is still possible.
    options = presets(unit)
    labels = [label for label, _ in options]
    default = preset_for(unit, previous["quantity"]) if previous is not None else None
    choice = st.pills(t("how_much"), labels, default=default or labels[min(1, len(labels) - 1)],
                      key=f"k_amount_{food}")
    with st.expander(t("other_amount")):
        left, right = st.columns(2)
        custom = left.number_input(t("amount"), min_value=0.0, step=0.25, format="%.2f", value=0.0, key=f"k_custom_{food}")
        custom_unit = right.selectbox(t("unit"), UNITS, index=UNITS.index(unit) if unit in UNITS else len(UNITS) - 1,
                                      key=f"k_custom_unit_{food}")
    last_price = previous["total_price"] if previous is not None and pd.notna(previous["total_price"]) else 0.0
    price = st.number_input(t("price_paid"), min_value=0.0, step=5.0, format="%.0f", help=t("price_help"),
                            value=float(last_price), key=f"k_price_{food}")
    with st.expander(t("another_day")):
        day = st.date_input(t("date"), value=today.date(), format="DD/MM/YYYY", key="k_day")
    category, shelf = None, None
    if is_new:
        st.caption(t("new_food_note"))
        left, right = st.columns(2)
        category = left.selectbox(t("category"), CATEGORIES, index=CATEGORIES.index(category_guess), key=f"k_cat_{food}")
        shelf = right.number_input(t("stays_good"), min_value=1, value=shelf_guess, step=1, key=f"k_shelf_{food}")

    if st.button(t("save"), type="primary", width="stretch", key="k_save"):
        if custom > 0:
            quantity, unit_saved, amount_label = custom, custom_unit, amount_text(custom, custom_unit)
        elif choice:
            quantity, unit_saved, amount_label = dict(options)[choice], unit, choice
        else:
            quantity = 0.0
        if quantity <= 0:
            st.error(t("choose_amount_first"))
        else:
            db.add_purchase(uid, day, food, float(quantity), unit_saved, float(price) if price > 0 else None,
                            category=category, shelf_life_days=int(shelf) if shelf else None)
            success(t("saved_purchase", food=food, amount=amount_label, price=f", ₹{price:,.0f}" if price else ""))
            choose(None)
            st.rerun()

with st.expander(t("paste_bill")):
    st.caption(t("bill_help"))
    bill = st.text_area(t("paste_bill"), height=140, label_visibility="collapsed",
                        placeholder="Milk 2 L 120\nEggs x12 84\nTomato 1kg 40")
    if st.button(t("read_bill")):
        if bill.strip():
            rows, skipped = parse_bill(bill)
            st.session_state["bill_rows"], st.session_state["bill_skipped"] = rows, skipped
        else:
            st.error(t("paste_first"))
    rows = st.session_state.get("bill_rows")
    if rows is not None:
        if st.session_state.get("bill_skipped"):
            st.caption(t("not_read", lines="; ".join(st.session_state["bill_skipped"])))
        if rows.empty:
            st.write(t("nothing_recognised"))
        else:
            edited = st.data_editor(rows.assign(Save=True), hide_index=True, width="stretch", num_rows="fixed",
                                    key="bill_editor", height=fit_height(len(rows), 10), column_config={
                                        "food": "Food", "quantity": quantity("Quantity"),
                                        "unit": st.column_config.SelectboxColumn("Unit", options=UNITS),
                                        "total_price": rupees("₹"), "Save": st.column_config.CheckboxColumn("Save")})
            chosen = edited[edited["Save"]]
            if st.button(t("save_n", n=len(chosen)), type="primary", disabled=chosen.empty):
                for row in chosen.itertuples():
                    db.add_purchase(uid, today, row.food, row.quantity, row.unit,
                                    row.total_price if row.total_price > 0 else None)
                st.session_state.pop("bill_rows", None)
                success(t("saved_many", n=len(chosen)))
                st.rerun()

if not buys.empty:
    section(t("recent"), t("edit_on_my_data"))
    recent = buys.sort_values(["date", "id"], ascending=False).head(5)
    lines = []
    for _, row in recent.iterrows():
        when = (t("today") if row["date"] == today else t("yesterday") if row["date"] == today - pd.Timedelta(days=1)
                else fmt_date(row["date"]))
        price = f", ₹{row['total_price']:,.0f}" if pd.notna(row["total_price"]) else ""
        lines.append(f"- {when}: **{row['food']}**, {describe(row)}{price}")
    st.markdown("\n".join(lines))
