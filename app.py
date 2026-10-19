"""FORAGE Streamlit entry point.

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

from services.data import SOURCES, data_as_of  # noqa: E402
from services.session import personal_available, render_account  # noqa: E402
from ui.theme import VERSION, apply_styles  # noqa: E402


def build_pages(signed_in: bool) -> dict[str, list]:
    """Two sections: the personal daily-use pages and the public Insights pages."""
    return {
        "Your food": [
            st.Page("views/home.py", title="Home", icon=":material/home:", default=signed_in),
            st.Page("views/bought.py", title="I bought…", icon=":material/add_shopping_cart:"),
            st.Page("views/pantry.py", title="Pantry check", icon=":material/kitchen:"),
            st.Page("views/my_data.py", title="My data", icon=":material/table_rows:"),
        ],
        "Insights": [
            st.Page("views/overview.py", title="Overview", icon=":material/dashboard:", default=not signed_in),
            st.Page("views/data_quality.py", title="Data Quality", icon=":material/fact_check:"),
            st.Page("views/eda.py", title="EDA", icon=":material/query_stats:"),
            st.Page("views/waste.py", title="Waste & Expiry", icon=":material/delete_sweep:"),
            st.Page("views/forecasting.py", title="Forecasting", icon=":material/trending_up:"),
            st.Page("views/recommendations.py", title="Recommendations", icon=":material/checklist:"),
        ],
    }


def render_sidebar(signed_in: bool) -> None:
    """Below Streamlit's own page navigation: the Insights source, the account and a footer."""
    sources = [key for key in SOURCES if key != "personal" or signed_in]
    if st.session_state.get("source") not in sources:
        st.session_state["source"] = "demo"
    with st.sidebar:
        st.radio("Insights data source", sources, format_func=SOURCES.get, key="source",
                 help="Every Insights page uses only the selected source. Sources are never combined.")
        st.caption("Demo data is synthetic and for illustration only. M5 and Instacart are public datasets.")
        st.divider()
        render_account()
        st.markdown(f'<div class="fg-footer">Data as of {data_as_of(st.session_state["source"])}<br>'
                    f'FORAGE {VERSION}</div>', unsafe_allow_html=True)


def main() -> None:
    # "auto": expanded on desktop, collapsed on phones (the native navigation closes itself after a tap).
    st.set_page_config(page_title="FORAGE", page_icon=str(ASSETS / "forage_icon.svg"), layout="wide",
                       initial_sidebar_state="auto")
    st.logo(str(ASSETS / "forage_wordmark.svg"), icon_image=str(ASSETS / "forage_icon.svg"), size="large")
    apply_styles()
    st.session_state.setdefault("source", "demo")
    signed_in = personal_available()
    pages = build_pages(signed_in)
    navigation = st.navigation(pages, position="sidebar")
    render_sidebar(signed_in)
    navigation.run()


main()
