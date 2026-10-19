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
from services.session import render_account  # noqa: E402
from ui.theme import apply_styles  # noqa: E402

PAGES = [
    st.Page("views/overview.py", title="Overview", default=True),
    st.Page("views/data_quality.py", title="Data Quality"),
    st.Page("views/eda.py", title="EDA"),
    st.Page("views/waste.py", title="Waste & Expiry"),
    st.Page("views/forecasting.py", title="Forecasting"),
    st.Page("views/recommendations.py", title="Recommendations"),
    st.Page("views/my_data.py", title="My Data"),
]


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown('<p class="fg-brand">FORAGE</p><p class="fg-tagline">Household food demand and waste</p>',
                    unsafe_allow_html=True)
        for page in PAGES:
            st.page_link(page)
        st.divider()
        st.radio("Data source", list(SOURCES), format_func=SOURCES.get, key="source",
                 help="Every analysis page uses only the selected source. Sources are never combined.")
        st.caption("Demo data is synthetic and for illustration only. M5 and Instacart are public datasets.")
        st.divider()
        render_account()


def main() -> None:
    st.set_page_config(page_title="FORAGE", layout="wide", initial_sidebar_state="expanded")
    apply_styles()
    st.session_state.setdefault("source", "demo")
    navigation = st.navigation(PAGES, position="hidden")
    render_sidebar()
    navigation.run()


main()
