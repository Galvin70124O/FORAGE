"""Shopping list (Kitchen mode): what to buy this week in everyday amounts, with a list to share on WhatsApp."""

import pandas as pd
import streamlit as st

from kitchen import share_text, shopping_items, whatsapp_link
from pantry import buy_list, coverage, expected_stock, stock_batches, unlocked, weeks_to_go
from services.personal import checks as personal_checks
from services.personal import purchases as personal_purchases
from services.personal import require_user
from ui.components import empty_state, section
from ui.kitchen import flash, page_title, t

page_title("nav_shopping", "shop_purpose")
db, uid = require_user()
flash()

buys, checks = personal_purchases(uid), personal_checks(uid)
if buys.empty:
    empty_state(t("start_title"), t("start_body"), page="views/bought.py", page_label=t("log_purchase"))
    st.stop()

today = pd.Timestamp.today().normalize()
cover = coverage(buys, checks)
shown, reliable, _ = unlocked("buy_list", cover)
if not shown:
    st.info(t("list_after_check"))
    st.page_link("views/pantry.py", label=t("do_pantry_check"), icon=":material/kitchen:")
    st.stop()

stock = expected_stock(buys, checks, today)
items, enough = shopping_items(buy_list(stock, stock_batches(buys, stock), today, 7))

section(t("buy_these"))
if not items:
    st.write(t("nothing_to_buy"))
for food, amount in items:
    st.checkbox(f"**{food}**: {amount}", key=f"k_got_{food}")
st.caption(t("list_note"))
if not reliable:
    weeks = weeks_to_go("weeks", 3 - cover.get("weeks", 0), cover)
    if weeks > 0:
        st.caption(t("smarter_after", weeks=weeks, s="" if weeks == 1 else "s"))

if enough:
    section(t("skip_these"))
    st.markdown("\n".join(f"- {t('enough_skip', food=food)}" for food in enough))

if items:
    section(t("share_list"), t("share_help"))
    text = share_text(t("share_title"), items)
    st.code(text, language=None, wrap_lines=True)
    st.link_button(t("send_whatsapp"), whatsapp_link(text), type="primary", width="stretch",
                   icon=":material/send:")
