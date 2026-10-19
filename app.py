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

from auth import get_current_user  # noqa: E402
from ui.theme import apply_styles, current_theme  # noqa: E402
from views.auth import render_authenticated_sidebar_controls, render_authentication_page  # noqa: E402
from views.data_quality import dataset_quality_page  # noqa: E402
from views.personal import data_input_page, my_stats_page  # noqa: E402
from views.public import general_insights_page, instacart_insights_page, m5_demand_page, public_overview_page, purchase_behavior_page, real_recommendations_page, retail_forecasting_page, waste_unavailable_page  # noqa: E402

# Development switch: set to True to restore the existing Supabase
# login/signup/session gate. While False, no Supabase Auth calls are made.
AUTH_ENABLED = False
NAVIGATION_GROUPS = {
    "INSIGHTS": ["Overview", "General Insights", "My Stats", "Consumption", "Waste", "Forecast"],
    "DECISIONS": ["Recommendations"],
    "REAL DATA": ["M5 Demand", "Instacart Insights"],
    "DATA": ["Add Food", "Import Dataset"],
}
PAGE_HANDLERS = {
    "Overview": "Overview",
    "General Insights": "General Insights",
    "My Stats": "My Stats",
    "Consumption": "Consumption Analysis",
    "Waste": "Waste Analysis",
    "Forecast": "Forecasting",
    "Recommendations": "Recommendations",
    "M5 Demand": "M5 Demand",
    "Instacart Insights": "Instacart Insights",
    "Import Dataset": "Dataset Quality",
    "Add Food": "Data Input",
}

st.set_page_config(page_title="Forage | Food Intelligence", page_icon="FORAGE", layout="wide", initial_sidebar_state="expanded")


def set_active_page(widget_key):
    """Keep the grouped sidebar controls behaving as one navigation menu."""
    selected_page = st.session_state.get(widget_key)
    if selected_page is None:
        return
    st.session_state["active_page"] = selected_page
    for group_name in NAVIGATION_GROUPS:
        other_key = f"nav_{group_name.lower()}"
        if other_key != widget_key:
            st.session_state[other_key] = None


def render_sidebar_navigation():
    """Render compact, grouped product navigation without default radio controls."""
    if "active_page" not in st.session_state:
        st.session_state.active_page = "Overview"

    st.sidebar.markdown(
        "<div><span class='product-mark'>F</span><span class='product-name'>FORAGE</span></div>"
        "<div class='product-subtitle'>Food intelligence platform</div>",
        unsafe_allow_html=True,
    )
    for group_name, pages in NAVIGATION_GROUPS.items():
        widget_key = f"nav_{group_name.lower()}"
        active_page = st.session_state.active_page
        selected_index = pages.index(active_page) if active_page in pages else None
        st.sidebar.markdown(f"<div class='nav-caption'>{group_name}</div>", unsafe_allow_html=True)
        st.sidebar.radio(
            group_name,
            pages,
            index=selected_index,
            key=widget_key,
            on_change=set_active_page,
            args=(widget_key,),
            label_visibility="collapsed",
            width="stretch",
        )
    st.sidebar.divider()
    toggle_label = "Light mode" if current_theme() == "dark" else "Dark mode"
    st.sidebar.toggle(toggle_label, key="dark_mode", help="Switch between the light and dark FORAGE interface.")
    return PAGE_HANDLERS[st.session_state.active_page]


def main():
    apply_styles(current_theme())
    if AUTH_ENABLED:
        if get_current_user() is None:
            render_authentication_page()
            st.stop()

    page = render_sidebar_navigation()
    if AUTH_ENABLED:
        st.sidebar.divider()
        render_authenticated_sidebar_controls()
        st.sidebar.divider()
    st.sidebar.markdown("<div class='sidebar-status'><span class='status-dot'>●</span>General Insights uses selected real public data. My Stats uses only My Data. Demo data is explicit only.</div>", unsafe_allow_html=True)
    if page == "Overview":
        public_overview_page()
    elif page == "General Insights":
        general_insights_page()
    elif page == "My Stats":
        my_stats_page()
    elif page == "Consumption Analysis":
        purchase_behavior_page()
    elif page == "Waste Analysis":
        waste_unavailable_page()
    elif page == "Forecasting":
        retail_forecasting_page()
    elif page == "Recommendations":
        real_recommendations_page()
    elif page == "M5 Demand":
        m5_demand_page()
    elif page == "Instacart Insights":
        instacart_insights_page()
    elif page == "Dataset Quality":
        dataset_quality_page()
    else:
        data_input_page()



if __name__ == "__main__":
    main()
