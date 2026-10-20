"""Pantry check (Kitchen mode): per food, tap Full / Half / Almost empty / Finished; consumption is derived from it.

"Check everything" walks through the foods one at a time with a progress count.
The level is a share of what was available (left at the last check + bought since);
the remaining quantity is stored in the food's base unit.
"""

import pandas as pd
import streamlit as st

from kitchen import LEVELS, WASTE_LEVELS, amount_text, pantry_amounts
from pantry import TOLERANCE, expected_stock
from services import personal
from services.personal import require_user
from ui.components import empty_state, section
from ui.kitchen import flash, page_title, success, t, tiles

page_title("nav_pantry", "pantry_purpose")
db, uid = require_user()
flash()

buys, checks = personal.purchases(uid), personal.checks(uid)
today = pd.Timestamp.today().normalize()
with st.expander(t("checked_another_day")):
    day = pd.Timestamp(st.date_input(t("date"), value=today.date(), format="DD/MM/YYYY", key="k_check_day"))
stock = expected_stock(buys, checks, day)

if stock.empty:
    empty_state(t("nothing_to_check"), t("nothing_to_check_body"), page="views/bought.py", page_label=t("log_purchase"))
    st.stop()

units = stock.set_index("Food")["Unit"].to_dict()
recent = buys.sort_values(["date", "id"], ascending=False)["food"].drop_duplicates().tolist() if not buys.empty else []
ordered = [f for f in recent if f in units] + sorted(set(units) - set(recent))


def available_for(food: str) -> float:
    """Left at the last check before this date + bought since then (up to this date)."""
    earlier = checks[(checks["food"] == food) & (checks["date"] < day)] if not checks.empty else checks
    base = float(earlier.sort_values("date")["remaining"].iloc[-1]) if not earlier.empty else 0.0
    since = earlier["date"].max() if not earlier.empty else pd.Timestamp.min
    bought = buys[(buys["food"] == food) & (buys["date"] > since) & (buys["date"] <= day)]["quantity"].sum()
    return base + float(bought)


def problem(food: str, left: float, wasted: float) -> str | None:
    if left < 0 or wasted < 0:
        return t("not_negative")
    available = available_for(food)
    if left + wasted > available + TOLERANCE:
        unit = units.get(food) or ""
        return t("too_much", food=food, left=amount_text(left, unit), wasted=amount_text(wasted, unit),
                 available=amount_text(available, unit))
    return None


def save(food: str, left: float, wasted: float) -> bool:
    if message := problem(food, left, wasted):
        st.error(message)
        return False
    db.add_check(uid, day, food, float(left), float(wasted))
    success(t("saved_check", food=food, left=amount_text(left, units.get(food))))
    return True


def card(food: str, key: str) -> bool:
    """One food: the waste question, four big level buttons and an exact-amount fallback. True once saved."""
    unit = units.get(food) or ""
    available = available_for(food)
    st.subheader(food)
    st.caption(t("full_is", amount=amount_text(available, unit)))
    waste = st.segmented_control(t("thrown_q"), list(WASTE_LEVELS), default="nothing", required=True,
                                 format_func=lambda w: t(f"waste_{w}"), key=f"{key}_waste_{food}")
    st.markdown(f"**{t('how_much_left')}**")
    with st.container(horizontal=True, key=f"fg-levels-{key}"):
        for level in LEVELS:
            if st.button(t(f"level_{level}"), key=f"{key}_{level}_{food}", width="stretch"):
                return save(food, *pantry_amounts(available, level, waste or "nothing"))
    with st.expander(t("exact_amount")):
        left_col, right_col = st.columns(2)
        expected = float(stock.set_index("Food").at[food, "Expected"])
        left = left_col.number_input(t("left_now", unit=unit), min_value=0.0, value=expected, step=0.25,
                                     format="%.2f", key=f"{key}_left_{food}")
        wasted = right_col.number_input(t("thrown_away", unit=unit), min_value=0.0, value=0.0, step=0.25,
                                        format="%.2f", key=f"{key}_wasted_{food}")
        if st.button(t("save_check"), type="primary", key=f"{key}_exact_{food}"):
            return save(food, left, wasted)
    return False


queue = st.session_state.get("k_queue")
if queue is not None:
    # Check everything: one food at a time.
    position = st.session_state.get("k_queue_pos", 0)
    if position >= len(queue):
        st.success(t("all_done", n=st.session_state.get("k_queue_done", 0)))
        for name in ("k_queue", "k_queue_pos", "k_queue_done"):
            st.session_state.pop(name, None)
    else:
        st.progress(position / len(queue), text=t("progress", i=position + 1, n=len(queue)))
        food = queue[position]
        if card(food, "queue"):
            st.session_state["k_queue_pos"] = position + 1
            st.session_state["k_queue_done"] = st.session_state.get("k_queue_done", 0) + 1
            st.rerun()
        with st.container(horizontal=True):
            if st.button(t("skip_food")):
                st.session_state["k_queue_pos"] = position + 1
                st.rerun()
            if st.button(t("stop_checking")):
                for name in ("k_queue", "k_queue_pos", "k_queue_done"):
                    st.session_state.pop(name, None)
                st.rerun()
        st.stop()

if st.button(t("check_everything", n=len(ordered)), type="primary", width="stretch", icon=":material/checklist:"):
    st.session_state.update(k_queue=ordered, k_queue_pos=0, k_queue_done=0)
    st.rerun()

section(t("check_one"))
selected = st.session_state.get("k_check_food")
tapped = tiles(ordered[:12], "check", selected=selected)
if tapped:
    st.session_state["k_check_food"] = None if tapped == selected else tapped
    st.rerun()
if len(ordered) > 12:
    other = st.selectbox(t("other_food"), ordered[12:], index=None, key="k_check_other")
    if other:
        selected = other
if selected and selected in units:
    if card(selected, "one"):
        st.session_state["k_check_food"] = None
        st.rerun()

with st.expander(t("how_it_works")):
    st.write(t("how_it_works_body"))
