"""FORAGE Streamlit entry point.

Two modes, chosen with a switch at the bottom of the sidebar and remembered for the session:
- Kitchen (default when signed in): Home, I bought…, Pantry check, Shopping list, My data.
- Project insights (default for visitors): the data-science pages and the dataset picker.

Run from the project root with:
    python -m streamlit run app.py
"""

from pathlib import Path
import sys

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
ASSETS = PROJECT_ROOT / "assets"
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import public_data  # noqa: E402
from kitchen import default_mode  # noqa: E402
from services.data import SOURCES, data_as_of  # noqa: E402
from services.session import personal_available, render_account, store, user_id  # noqa: E402
from ui.kitchen import install_help, language_picker, t  # noqa: E402
from ui.theme import VERSION, apply_styles  # noqa: E402


def kitchen_pages() -> list:
    return [
        st.Page("views/home.py", title=t("nav_home"), icon=":material/home:", default=True),
        st.Page("views/bought.py", title=t("nav_bought"), icon=":material/add_shopping_cart:"),
        st.Page("views/pantry.py", title=t("nav_pantry"), icon=":material/kitchen:"),
        st.Page("views/shopping.py", title=t("nav_shopping"), icon=":material/list_alt:"),
        st.Page("views/my_data.py", title=t("nav_my_data"), icon=":material/table_rows:"),
    ]


def insights_pages() -> list:
    return [
        st.Page("views/overview.py", title="Overview", icon=":material/dashboard:", default=True),
        st.Page("views/data_quality.py", title="Data Quality", icon=":material/fact_check:"),
        st.Page("views/eda.py", title="EDA", icon=":material/query_stats:"),
        st.Page("views/waste.py", title="Waste & Expiry", icon=":material/delete_sweep:"),
        st.Page("views/forecasting.py", title="Forecasting", icon=":material/trending_up:"),
        st.Page("views/recommendations.py", title="Recommendations", icon=":material/checklist:"),
    ]


def current_mode(signed_in: bool) -> str:
    """The mode the person chose in this session, else Kitchen when signed in and Project insights otherwise."""
    if not st.session_state.get("app_mode_chosen"):
        st.session_state["app_mode"] = default_mode(signed_in)
    return st.session_state["app_mode"]


def switch_mode(mode: str) -> None:
    st.session_state.update(app_mode=mode, app_mode_chosen=True)


def render_licence(source: str) -> None:
    """Attribution and licence for the selected Insights source."""
    if source == "demo":
        st.caption("Synthetic household records made by FORAGE's own generator (src/generate_data.py). "
                   "For illustration only; prices are illustrative.")
    elif source == "personal":
        st.caption("Your own purchases and pantry checks, private to your account.")
    else:
        info = public_data.LICENCES[source]
        built = public_data.manifest(source)
        st.caption(f"{info['attribution']}  \n{info['licence']}  \n[Dataset page]({info['url']})"
                   + (f"  \nResults built {built['built']}." if built else ""))


def account_block(text: str) -> None:
    """The signed-in user (or sign-in button) and the data note, at the bottom of the sidebar."""
    with st.container(key="fs-account"):
        render_account()
        st.markdown(f'<div class="fg-footer">{text}<br>FORAGE {VERSION} · Fresh Shelf</div>', unsafe_allow_html=True)


def render_kitchen_sidebar(signed_in: bool) -> None:
    with st.sidebar:
        db, uid = (store(), user_id()) if signed_in else (None, None)
        language_picker(db, uid)
        install_help()
        st.button(t("switch_to_insights"), on_click=switch_mode, args=("insights",), width="stretch",
                  icon=":material/insights:", help=t("switch_insights_help"), key="switch_mode")
        account_block(t("section_kitchen"))


def render_insights_sidebar(signed_in: bool) -> None:
    sources = [key for key in SOURCES if key != "personal" or signed_in]
    if st.session_state.get("source") not in sources:
        st.session_state["source"] = "demo"
    with st.sidebar:
        st.radio("Insights data source", sources, format_func=SOURCES.get, key="source",
                 help="Every Insights page uses only the selected source. Sources are never combined.")
        with st.expander("Source & licence"):
            render_licence(st.session_state["source"])
        st.button(t("switch_to_kitchen"), on_click=switch_mode, args=("kitchen",), width="stretch",
                  icon=":material/kitchen:", help=t("switch_kitchen_help"), key="switch_mode")
        account_block(data_as_of(st.session_state["source"]))


def main() -> None:
    # "auto": expanded on desktop, collapsed on phones (the native navigation closes itself after a tap).
    st.set_page_config(page_title="FORAGE", page_icon=str(ASSETS / "forage_icon.svg"), layout="wide",
                       initial_sidebar_state="auto")
    st.logo(str(ASSETS / "forage_wordmark.svg"), icon_image=str(ASSETS / "forage_icon.svg"), size="large")
    st.session_state.setdefault("source", "demo")
    signed_in = personal_available()
    kitchen = current_mode(signed_in) == "kitchen"
    apply_styles(kitchen=kitchen)
    if kitchen:
        navigation = st.navigation({t("section_kitchen"): kitchen_pages()}, position="sidebar")
        render_kitchen_sidebar(signed_in)
    else:
        navigation = st.navigation({t("section_insights"): insights_pages()}, position="sidebar")
        render_insights_sidebar(signed_in)
    if target := st.session_state.pop("goto", None):  # set by a link from an Insights page to a Kitchen page
        st.switch_page(target)
    navigation.run()


main()
