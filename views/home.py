"""Home (Kitchen mode): what needs attention today, in plain words, from the user's own purchases and checks."""

import pandas as pd
import streamlit as st

from kitchen import round_rupees, shopping_items
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
    weeks_to_go,
)
from services.personal import checks as personal_checks
from services.personal import purchases as personal_purchases
from services.personal import require_user
from ui.components import empty_state, fmt_date, section
from ui.kitchen import flash, message, page_title, t, walkthrough

page_title("nav_home", "home_purpose")
db, uid = require_user()
if walkthrough(db, uid):
    st.stop()
flash()

with st.container(horizontal=True, key="fg-tiles-home"):
    st.page_link("views/bought.py", label=t("nav_bought"), icon=":material/add_shopping_cart:")
    st.page_link("views/pantry.py", label=t("nav_pantry"), icon=":material/kitchen:")
    st.page_link("views/shopping.py", label=t("nav_shopping"), icon=":material/list_alt:")

buys, checks = personal_purchases(uid), personal_checks(uid)
if buys.empty:
    empty_state(t("start_title"), t("start_body"), page="views/bought.py", page_label=t("log_purchase"))
    st.stop()

today = pd.Timestamp.today().normalize()
cover = coverage(buys, checks)
stock = expected_stock(buys, checks, today)
batches = stock_batches(buys, stock)

# Use first: what expires soon, then what will not be finished in time at the usual pace.
section(t("use_first"))
soon = expiring_soon(batches, today, 3)
if soon.empty:
    st.write(t("nothing_expiring"))
else:
    soon = soon.groupby("Food", as_index=False)["Days_Left"].min().sort_values("Days_Left")
    for row in soon.itertuples():
        days = int(max(row.Days_Left, 0))
        key = "use_today" if days == 0 else "use_tomorrow" if days == 1 else "use_in_days"
        message(t(key, food=row.Food, days=days))
if unlocked("buy_list", cover)[0]:
    risk = likely_wasted(batches, today)
    if not risk.empty:
        already = set(soon["Food"]) if not soon.empty else set()
        risk = risk.groupby("Food", as_index=False)["Value"].sum()
        for row in risk[~risk["Food"].isin(already)].itertuples():
            value = round_rupees(row.Value) if pd.notna(row.Value) and row.Value > 0 else 0
            message(t("at_risk", food=row.Food, amount=f"{value:,}") if value else t("at_risk_plain", food=row.Food))

# This week's shopping
section(t("shopping_head"))
shown, reliable, _ = unlocked("buy_list", cover)
if not shown:
    st.write(t("list_after_check"))
    st.page_link("views/pantry.py", label=t("do_pantry_check"), icon=":material/kitchen:")
else:
    items, enough = shopping_items(buy_list(stock, batches, today, 7))
    st.write(t("to_buy_count", n=len(items)) if items else t("to_buy_none"))
    for food in enough[:3]:
        message(t("enough_skip", food=food))
    if items:
        st.page_link("views/shopping.py", label=t("open_list"), icon=":material/list_alt:")
    if not reliable:
        weeks = weeks_to_go("weeks", 3 - cover.get("weeks", 0), cover)
        if weeks > 0:
            st.caption(t("smarter_after", weeks=weeks, s="" if weeks == 1 else "s"))

# This month
section(t("this_month"))
frame = analysis_frame(buys, checks)
month = frame[frame["Date"] >= today.replace(day=1)] if not frame.empty else frame
spent = buys.loc[buys["date"] >= today.replace(day=1), "total_price"].sum()
if unlocked("waste", cover)[0]:
    wasted = float(wasted_value(month).sum(min_count=1)) if not month.empty else 0.0
    wasted = 0.0 if pd.isna(wasted) else wasted
    st.write(t("wasted_month", amount=f"{round_rupees(wasted):,}") if wasted >= 5 else t("no_waste_month"))
st.write(t("spent_month", amount=f"{spent:,.0f}"))

if checks.empty:
    st.caption(t("no_check_yet"))
else:
    last = checks["date"].max()
    days = int((today - last).days)
    st.caption(t("last_check", date=fmt_date(last)))
    if days >= 8:
        st.warning(t("check_due", days=days))
