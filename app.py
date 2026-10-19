"""FORAGE Streamlit entry point.

Run from the project root with:
    python -m streamlit run app.py
"""

from pathlib import Path
import sys

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from services.data import SOURCES  # noqa: E402
from services.session import personal_available, render_account  # noqa: E402
from ui.theme import apply_styles  # noqa: E402


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


def render_sidebar(pages: dict[str, list], signed_in: bool) -> None:
    sources = [key for key in SOURCES if key != "personal" or signed_in]
    if st.session_state.get("source") not in sources:
        st.session_state["source"] = "demo"
    with st.sidebar:
        st.markdown('<p class="fg-brand">FORAGE</p><p class="fg-tagline">Household food demand and waste</p>',
                    unsafe_allow_html=True)
        for section, entries in pages.items():
            st.caption(section)
            for page in entries:
                st.page_link(page)
        st.divider()
        st.radio("Insights data source", sources, format_func=SOURCES.get, key="source",
                 help="Every Insights page uses only the selected source. Sources are never combined.")
        st.caption("Demo data is synthetic and for illustration only. M5 and Instacart are public datasets.")
        st.divider()
        render_account()


def main() -> None:
    st.set_page_config(page_title="FORAGE", layout="wide", initial_sidebar_state="expanded")
    apply_styles()
    st.session_state.setdefault("source", "demo")
    signed_in = personal_available()
    pages = build_pages(signed_in)
    navigation = st.navigation(pages, position="hidden")
    render_sidebar(pages, signed_in)
    navigation.run()


main()
