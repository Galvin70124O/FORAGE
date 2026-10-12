"""Professional Streamlit dashboard for the Food Demand and Supply project.

Run from the project root with:
    python -m streamlit run app.py
"""

from pathlib import Path
import sys
import tempfile
import json
from html import escape

import altair as alt
import pandas as pd
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from dataset_loader import process_external_csv  # noqa: E402
from personal_data import (  # noqa: E402
    PERSONAL_DATA_PATH,
    add_personal_record,
    append_personal_records,
    load_personal_data,
    personal_quality_report,
    save_personal_data,
)
from prediction import (  # noqa: E402
    build_models,
    chronological_split,
    create_forecasting_features,
    evaluate_predictions,
    load_data,
)
from recommendations import (  # noqa: E402
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    generate_recommendations,
)
from m5_forecasting import forecast_retail_demand  # noqa: E402
from data_profiles import demo_profile, instacart_profile, m5_profile  # noqa: E402
from dataset_registry import get_dataset  # noqa: E402
from auth import get_current_user, login, logout, signup  # noqa: E402


DATA_PATH = get_dataset("demo")["path"]
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
M5_DATA_PATH = get_dataset("m5")["path"]
INSTACART_DATA_PATH = get_dataset("instacart")["path"]
M5_QUALITY_PATH = M5_DATA_PATH.parent / "quality_report.json"
INSTACART_QUALITY_PATH = INSTACART_DATA_PATH.parent / "quality_report.json"
# Semantic chart identifiers, resolved exclusively through the active theme.
PRIMARY_COLOR = "consumption"
ACCENT_COLOR = "lime"
ALERT_COLOR = "waste"
NEUTRAL_COLOR = "neutral"
SUPPORT_COLOR = "teal"

# A single palette is the source of truth for both CSS and charts.  Keeping
# semantic values here prevents a light-mode text colour leaking into a dark UI.
THEMES = {
    "light": {
        "app": "#F1F3EC", "main": "#EEF1E9", "surface": "#FFFFFF", "surface_alt": "#F8F9F5", "sidebar": "#E7EBE2",
        "text": "#172019", "text_secondary": "#465248", "muted": "#657066", "border": "#D3D9CE", "sidebar_border": "#D3D9CE",
        "soft": "#F8F9F5", "hover": "#FFF0A8", "grid": "#DDE2D9",
        "accent": "#F4D03F", "active": "#F4D03F", "active_text": "#172019",
        "accent_deep": "#D9B900", "button": "#D9B900", "button_hover": "#C5A800",
        "green": "#2E7D32", "lime": "#5E9F32", "waste": "#D98B2B", "waste_line": "#E0A51A", "teal": "#2F7F78", "teal_soft": "#DDEDEA",
        "on_green": "#FFFFFF", "low_bg": "#E4F3D5", "low_text": "#286A2E", "waste_bg": "#F8E7DF", "waste_text": "#A34B2D", "upload_border": "#A8C99D",
    },
    "dark": {
        "app": "#0F130F", "main": "#0F130F", "surface": "#171D17", "surface_alt": "#1D241D", "sidebar": "#121812",
        "text": "#F2F5F1", "text_secondary": "#A7B0A7", "muted": "#8F9A8F", "border": "#2B342B", "sidebar_border": "#2B342B",
        "soft": "#1D241D", "hover": "#242D24", "grid": "#2B342B",
        "accent": "#B7E532", "active": "#253226", "active_text": "#F2F5F1",
        "accent_deep": "#B7E532", "button": "#2E7D32", "button_hover": "#43A047",
        "green": "#43A047", "lime": "#B7E532", "waste": "#DFAE2F", "waste_line": "#DFAE2F", "teal": "#3FA7A0", "teal_soft": "#1D322F",
        "on_green": "#F2F5F1", "low_bg": "#203523", "low_text": "#A9DFA7", "waste_bg": "#3A2921", "waste_text": "#F0B39B", "upload_border": "#4D6B4D",
    },
}

st.set_page_config(page_title="Forage | Food Intelligence", page_icon="FORAGE", layout="wide", initial_sidebar_state="expanded")


def current_theme():
    """Return the persisted UI theme; light is the product default."""
    if "dark_mode" not in st.session_state:
        st.session_state.dark_mode = False
    return "dark" if st.session_state.dark_mode else "light"


def apply_styles(theme_name):
    """Apply a small, centralized presentation layer without altering widget content."""
    theme = THEMES[theme_name]
    st.markdown(f"""
    <style>
    [data-testid="stAppViewContainer"] {{
        --forage-app:{theme['app']}; --forage-surface:{theme['surface']};
        --forage-text:{theme['text']}; --forage-text-secondary:{theme['text_secondary']}; --forage-muted:{theme['muted']};
        --forage-border:{theme['border']}; --forage-soft:{theme['soft']};
        --forage-accent:{theme['accent']}; --forage-accent-deep:{theme['accent_deep']};
        background:var(--forage-app); color-scheme:{theme_name};
    }}
    [data-testid="stHeader"] {{ background:{theme['app']}; }}
    [data-testid="stHeader"] [data-testid="stToolbar"] button {{ color:{theme['text']}; }}
    [data-testid="stMain"] {{ background:{theme['main']}; }}
    .block-container {{ max-width:1500px; padding:1.2rem 2rem 2.4rem; }}
    [data-testid="stSidebar"] {{ min-width:16rem; max-width:16rem; background:{theme['sidebar']}; border-right:1px solid {theme['sidebar_border']}; }}
    [data-testid="stSidebar"] > div:first-child {{ padding:1.25rem .8rem; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] {{ gap:0; margin:0; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] label {{ padding:.5rem .68rem; margin:.06rem 0; border:1px solid transparent; border-left:3px solid transparent; border-radius:7px; color:var(--forage-text); font-size:.85rem; cursor:pointer; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] label > div:first-child {{ display:none; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] label p {{ color:inherit !important; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {{ background:{theme['active']}; border-color:{theme['active']}; border-left-color:var(--forage-accent); color:{theme['active_text']}; font-weight:700; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {{ background:{theme['hover']}; color:var(--forage-text); }}
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked):hover {{ background:{theme['active']}; color:{theme['active_text']}; }}
    [data-testid="stSidebar"] hr {{ border-color:var(--forage-border); }}
    .product-mark {{ display:inline-flex; align-items:center; justify-content:center; width:30px; height:30px; border-radius:8px; background:{theme['green']}; color:{theme['on_green']}; font-size:.72rem; font-weight:800; margin-right:.55rem; }}
    .product-name {{ font-size:1.04rem; font-weight:800; letter-spacing:.1em; color:var(--forage-text); }}
    .product-subtitle {{ font-size:.72rem; color:var(--forage-text-secondary); margin:.25rem 0 1.35rem 2.5rem; }}
    .nav-caption {{ font-size:.63rem; font-weight:800; letter-spacing:.14em; color:{theme['text_secondary']}; margin:1rem .65rem .32rem; }}
    .sidebar-status {{ padding:.65rem; border:1px solid var(--forage-border); border-radius:7px; background:var(--forage-soft); color:var(--forage-text-secondary); font-size:.72rem; line-height:1.45; }}
    .status-dot {{ color:{theme['teal']}; margin-right:.25rem; }}
    .page-kicker {{ color:var(--forage-accent-deep); font-size:.68rem; font-weight:800; letter-spacing:.14em; margin-bottom:.4rem; }}
    .page-title {{ color:var(--forage-text); font-size:2rem; font-weight:720; letter-spacing:-.05em; line-height:1.08; margin:0; }}
    .page-subtitle {{ color:var(--forage-text-secondary); font-size:.94rem; line-height:1.48; max-width:45rem; margin:.45rem 0 1.2rem; }}
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"], [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{ color:var(--forage-text) !important; }}
    [data-testid="stSidebar"] [data-testid="stCheckbox"] label, [data-testid="stSidebar"] [data-testid="stCheckbox"] label p {{ color:var(--forage-text) !important; }}
    [data-testid="stMain"] [data-testid="stMarkdownContainer"] {{ color:var(--forage-text); }}
    [data-testid="stMain"] [data-testid="stCaptionContainer"] {{ color:var(--forage-muted); }}
    [data-testid="stMain"] [data-testid="stWidgetLabel"] {{ color:var(--forage-text); }}
    [data-testid="stMain"] h1, [data-testid="stMain"] h2, [data-testid="stMain"] h3 {{ color:var(--forage-text); }}
    [data-testid="stMain"] [data-testid="stAlert"] {{ color:var(--forage-text); border-color:var(--forage-border); }}
    [data-testid="stMain"] [data-testid="stFileUploader"], [data-testid="stMain"] [data-baseweb="select"], [data-testid="stMain"] input {{ color:var(--forage-text); }}
    [data-testid="stMain"] [data-testid="stExpander"] summary {{ color:var(--forage-text); }}
    [data-testid="stMain"] [data-baseweb="tab"] {{ color:var(--forage-text-secondary); }}
    [data-testid="stMain"] [data-baseweb="tab"][aria-selected="true"] {{ color:var(--forage-text); }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{ background:{theme['surface_alt']}; border-color:var(--forage-border); border-radius:11px; box-shadow:0 2px 8px rgba(23,32,25,.035); }}
    .metric-card {{ min-height:96px; padding:1rem 1.05rem .92rem; background:{theme['surface']}; border:1px solid {theme['border']}; border-top:3px solid var(--metric-accent, var(--forage-accent)); border-radius:11px; box-shadow:0 2px 8px rgba(23,32,25,.045); }}
    .metric-label {{ color:{theme['text_secondary']}; font-size:.66rem; font-weight:800; letter-spacing:.1em; line-height:1.2; text-transform:uppercase; }}
    .metric-value {{ color:{theme['text']}; font-size:1.6rem; font-weight:760; letter-spacing:-.045em; line-height:1.25; margin-top:.46rem; }}
    .metric-context {{ color:var(--metric-accent, var(--forage-accent-deep)); font-size:.72rem; font-weight:700; margin-top:.34rem; }}
    .chart-title {{ color:{theme['text']}; font-weight:700; font-size:1.02rem; margin-bottom:.1rem; }}
    .chart-note {{ color:{theme['text_secondary']}; font-size:.79rem; margin-bottom:.65rem; }}
    .source-badge {{ display:inline-flex; align-items:center; gap:.42rem; padding:.35rem .58rem; background:{theme['surface_alt']}; border:1px solid {theme['border']}; border-radius:99px; color:{theme['text_secondary']}; font-size:.7rem; font-weight:760; letter-spacing:.045em; margin:0 0 .9rem; }}
    .source-badge strong {{ color:{theme['text']}; font-weight:800; }}
    .source-dot {{ width:.42rem; height:.42rem; background:{theme['teal']}; border-radius:50%; display:inline-block; }}
    .workflow {{ display:grid; grid-template-columns:repeat(6,minmax(0,1fr)); gap:.42rem; margin:.15rem 0 1.1rem; }}
    .workflow-step {{ padding:.55rem .5rem; background:{theme['surface_alt']}; border:1px solid {theme['border']}; border-radius:7px; color:{theme['text_secondary']}; font-size:.69rem; line-height:1.25; }}
    .workflow-step b {{ display:block; color:{theme['accent_deep']}; font-size:.65rem; margin-bottom:.1rem; }}
    .form-section {{ margin:.45rem 0 .35rem; color:{theme['text_secondary']}; font-size:.68rem; font-weight:800; letter-spacing:.11em; }}
    .signal-card {{ padding:.82rem 0; border-bottom:1px solid {theme['border']}; }}
    .signal-card:last-child {{ border-bottom:0; }}
    .signal-label {{ color:{theme['muted']}; font-size:.65rem; font-weight:800; letter-spacing:.1em; }}
    .signal-name {{ color:{theme['text']}; font-size:1.12rem; font-weight:720; margin-top:.2rem; }}
    .signal-value {{ color:var(--signal-accent, var(--forage-accent-deep)); font-size:.82rem; font-weight:700; margin-top:.12rem; }}
    .rec-card {{ padding:1.15rem 1.2rem; background:{theme['surface']}; border:1px solid {theme['border']}; border-radius:10px; min-height:178px; margin-bottom:.75rem; }}
    .rec-name {{ color:{theme['text']}; font-size:1.1rem; font-weight:700; }} .rec-category {{ color:{theme['muted']}; font-size:.78rem; margin-top:.05rem; }}
    .rec-quantity {{ color:var(--forage-accent-deep); font-size:1.65rem; font-weight:720; margin:.55rem 0 .05rem; }} .rec-label {{ color:{theme['muted']}; font-size:.69rem; font-weight:700; letter-spacing:.08em; }}
    .badge {{ display:inline-block; padding:.18rem .42rem; border-radius:99px; font-size:.66rem; font-weight:750; margin:.15rem .2rem 0 0; }}
    .badge-low {{ background:{theme['low_bg']}; color:{theme['low_text']}; }} .badge-waste {{ background:{theme['waste_bg']}; color:{theme['waste_text']}; }} .badge-covered {{ background:{theme['soft']}; color:{theme['muted']}; }}
    .upload-well {{ padding:1.35rem 1.4rem; background:{theme['surface']}; border:1px dashed {theme['upload_border']}; border-radius:10px; }}
    [data-testid="stButton"] button, [data-testid="stDownloadButton"] button {{ background:{theme['button']}; color:{theme['active_text']}; border:0; border-radius:7px; font-weight:700; }}
    [data-testid="stButton"] button:hover, [data-testid="stDownloadButton"] button:hover {{ background:{theme['button_hover']}; color:{theme['active_text']}; transform:translateY(-1px); }}
    [data-testid="stButton"] button, [data-testid="stDownloadButton"] button, .metric-card, .rec-card {{ transition:background-color .14s ease, border-color .14s ease, transform .14s ease; }}
    .metric-card:hover, .rec-card:hover {{ border-color:{theme['upload_border']}; transform:translateY(-1px); }}
    [data-testid="stDataFrame"] {{ border:1px solid {theme['border']}; border-radius:8px; overflow:hidden; }}
    [data-testid="stMain"] [data-testid="stFileUploader"] section {{ background:{theme['surface_alt']}; border-color:{theme['border']}; }}
    [data-testid="stMain"] [data-baseweb="select"] > div, [data-testid="stMain"] input {{ background:{theme['surface']} !important; border-color:{theme['border']} !important; color:{theme['text']} !important; }}
    [data-testid="stMain"] [data-baseweb="select"] input {{ color:{theme['text']} !important; }}
    [data-testid="stMain"] [data-baseweb="select"] > div:focus-within, [data-testid="stMain"] input:focus, [data-testid="stButton"] button:focus-visible, [data-testid="stDownloadButton"] button:focus-visible {{ outline:2px solid {theme['teal']}; outline-offset:2px; }}
    [data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:focus-visible) {{ outline:2px solid {theme['teal']}; outline-offset:1px; }}
    /* Vega mounts its hover label outside the chart tree; target only that component. */
    #vg-tooltip-element {{ background:{theme['surface']} !important; color:{theme['text']} !important; border:1px solid {theme['border']} !important; box-shadow:0 4px 12px rgba(23,32,25,.12); }}
    #vg-tooltip-element td, #vg-tooltip-element th {{ color:{theme['text_secondary']} !important; }}
    .auth-brand {{ display:flex; align-items:center; justify-content:center; gap:.65rem; margin:2.4rem 0 .65rem; }}
    .auth-mark {{ display:inline-flex; align-items:center; justify-content:center; width:38px; height:38px; border-radius:10px; background:{theme['green']}; color:{theme['on_green']}; font-size:.88rem; font-weight:850; }}
    .auth-name {{ color:{theme['text']}; font-size:1.35rem; font-weight:850; letter-spacing:.12em; }}
    .auth-kicker {{ color:{theme['accent_deep']}; font-size:.68rem; font-weight:800; letter-spacing:.14em; text-align:center; margin-top:1.4rem; }}
    .auth-title {{ color:{theme['text']}; font-size:1.65rem; font-weight:760; letter-spacing:-.04em; text-align:center; margin:.28rem 0 .35rem; }}
    .auth-subtitle {{ color:{theme['text_secondary']}; font-size:.9rem; line-height:1.5; text-align:center; margin:0 0 1.2rem; }}
    .auth-switch {{ color:{theme['muted']}; font-size:.84rem; text-align:center; margin:.85rem 0 .3rem; }}
    [data-testid="stMain"] [data-testid="stForm"] {{ padding-top:.1rem; }}
    @media (max-width:900px) {{ .block-container {{ padding:1.25rem 1rem 2rem; }} .workflow {{ grid-template-columns:repeat(3,minmax(0,1fr)); }} }}
    </style>
    """, unsafe_allow_html=True)


@st.cache_data
def get_cleaned_data():
    return pd.read_csv(DATA_PATH, parse_dates=["Date", "Estimated_Expiry_Date"])


@st.cache_data
def get_m5_data():
    """Load only the one-time M5 extract, never the raw wide M5 files."""
    return pd.read_csv(M5_DATA_PATH, parse_dates=["Date"], dtype={
        "Product_ID": "category", "Store_ID": "category", "Department": "category",
        "Category": "category", "Quantity_Sold": "int16", "Price": "float32",
        "Weekday": "category", "Month": "int8", "Event_Name": "category", "Event_Type": "category",
    })


@st.cache_data
def get_instacart_data():
    """Load only the one-time Instacart relational extract."""
    return pd.read_csv(INSTACART_DATA_PATH, dtype={
        "Order_ID": "int32", "User_ID": "int32", "Order_Set": "category",
        "Order_Number": "int16", "Order_Day_Of_Week": "int8", "Order_Hour": "int8",
        "Days_Since_Prior_Order": "float32", "Product_ID": "int32", "Product_Name": "category",
        "Aisle": "category", "Department": "category", "Add_To_Cart_Order": "int16", "Reordered": "int8",
    })


@st.cache_data(show_spinner="Evaluating the chronological retail-demand test period...")
def get_m5_forecast_results():
    return forecast_retail_demand(get_m5_data())


@st.cache_data(show_spinner="Evaluating forecasting models on the chronological test period...")
def get_forecast_results():
    """Reuse the tested forecasting logic from prediction.py."""
    raw_df = load_data()
    featured_df = create_forecasting_features(raw_df)
    train_df, test_df, cutoff_date = chronological_split(featured_df)
    x_train, x_test = train_df[FEATURE_COLUMNS], test_df[FEATURE_COLUMNS]
    y_train, y_test = train_df["Quantity_Consumed"], test_df["Quantity_Consumed"]

    predictions = {"Moving Average": test_df["Rolling_Mean_7"]}
    for model_name, model in build_models(NUMERIC_FEATURES, CATEGORICAL_FEATURES).items():
        model.fit(x_train, y_train)
        predictions[model_name] = pd.Series(model.predict(x_test), index=x_test.index)

    comparison = pd.DataFrame(
        [{"Model": name, **evaluate_predictions(y_test, values)} for name, values in predictions.items()]
    ).sort_values("MAE").reset_index(drop=True)
    best_model = comparison.loc[0, "Model"]
    chart_data = test_df[["Date", "Food", "Quantity_Unit", "Quantity_Consumed"]].copy()
    chart_data["Predicted_Consumption"] = predictions[best_model]
    return comparison, chart_data, best_model, pd.Timestamp(cutoff_date)


@st.cache_data(show_spinner="Preparing explainable purchase recommendations...")
def get_recommendations():
    return generate_recommendations()[0]


def render_authentication_page():
    """Render the public authentication flow before any dashboard data loads."""
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"

    top_left, top_right = st.columns([8, 1])
    with top_right:
        toggle_label = "Light mode" if current_theme() == "dark" else "Dark mode"
        st.toggle(toggle_label, key="dark_mode", help="Switch between the light and dark FORAGE interface.")

    _, auth_column, _ = st.columns([1, 1.05, 1])
    with auth_column:
        st.markdown(
            "<div class='auth-brand'><span class='auth-mark'>F</span><span class='auth-name'>FORAGE</span></div>",
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            if st.session_state.auth_mode == "login":
                st.markdown("<div class='auth-kicker'>FOOD INTELLIGENCE PLATFORM</div>", unsafe_allow_html=True)
                st.markdown("<div class='auth-title'>Welcome back</div>", unsafe_allow_html=True)
                st.markdown("<div class='auth-subtitle'>Sign in to explore food demand, consumption, and waste insights.</div>", unsafe_allow_html=True)
                with st.form("forage_login_form"):
                    email = st.text_input("Email", key="login_email", placeholder="you@example.com")
                    password = st.text_input("Password", type="password", key="login_password")
                    submitted = st.form_submit_button("Log in", width="stretch")
                if submitted:
                    success, message = login(email, password)
                    if success:
                        st.rerun()
                    st.error(message)
                st.markdown("<div class='auth-switch'>Don't have an account?</div>", unsafe_allow_html=True)
                if st.button("Create account", key="show_signup", width="stretch"):
                    st.session_state.auth_mode = "signup"
                    st.rerun()
            else:
                st.markdown("<div class='auth-kicker'>FOOD INTELLIGENCE PLATFORM</div>", unsafe_allow_html=True)
                st.markdown("<div class='auth-title'>Create your account</div>", unsafe_allow_html=True)
                st.markdown("<div class='auth-subtitle'>Start using FORAGE to make clearer food purchasing decisions.</div>", unsafe_allow_html=True)
                with st.form("forage_signup_form"):
                    name = st.text_input("Name", key="signup_name", placeholder="Your name")
                    email = st.text_input("Email", key="signup_email", placeholder="you@example.com")
                    password = st.text_input("Password", type="password", key="signup_password")
                    confirmation = st.text_input("Confirm password", type="password", key="signup_confirmation")
                    submitted = st.form_submit_button("Create account", width="stretch")
                if submitted:
                    success, message, authenticated = signup(name, email, password, confirmation)
                    if not success:
                        st.error(message)
                    elif authenticated:
                        st.success(message)
                        st.rerun()
                    else:
                        st.session_state.auth_mode = "login"
                        st.session_state.auth_notice = message
                        st.rerun()
                st.markdown("<div class='auth-switch'>Already have an account?</div>", unsafe_allow_html=True)
                if st.button("Log in", key="show_login", width="stretch"):
                    st.session_state.auth_mode = "login"
                    st.rerun()

        notice = st.session_state.pop("auth_notice", None)
        if notice:
            st.success(notice)


def render_authenticated_sidebar_controls():
    """Show account context and provide a local-session logout control."""
    user = st.session_state.get("user")
    email = getattr(user, "email", None) if user is not None else None
    if email:
        st.sidebar.caption(f"Signed in as {email}")
    if st.sidebar.button("Log out", key="logout", width="stretch"):
        logout()
        st.rerun()


def page_header(kicker, title, description):
    st.markdown(f'<div class="page-kicker">{kicker.upper()}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-subtitle">{description}</div>', unsafe_allow_html=True)


def data_source_badge(kind, name):
    """Make the currently displayed dataset unmistakable on analytical pages."""
    st.markdown(
        f'<div class="source-badge"><span class="source-dot"></span>{escape(kind.upper())} <strong>{escape(name)}</strong></div>',
        unsafe_allow_html=True,
    )


def recorded_quantity_note():
    st.caption("Quantities retain their source units (kg, L, dozen, loaf, and pack). Totals are recorded-quantity summaries; compare physical quantities by food and unit.")


def metric_row(items):
    """Render aligned KPI cards from (label, value, optional delta/help) tuples."""
    accent_by_label = {
        "purchased": "teal", "consumed": "green", "wasted": "waste",
        "overall waste": "accent", "food items": "teal",
    }
    theme = THEMES[current_theme()]
    columns = st.columns(len(items))
    for column, item in zip(columns, items):
        label, value, *optional = item
        context = optional[0] if optional else None
        help_text = optional[1] if len(optional) > 1 else None
        context_markup = f'<div class="metric-context">{escape(str(context))}</div>' if context else ""
        title_markup = f' title="{escape(str(help_text))}"' if help_text else ""
        accent = theme[accent_by_label.get(str(label).lower(), "accent")]
        with column:
            st.markdown(
                f'<div class="metric-card" style="--metric-accent:{accent}"{title_markup}>'
                f'<div class="metric-label">{escape(str(label))}</div>'
                f'<div class="metric-value">{escape(str(value))}</div>{context_markup}</div>',
                unsafe_allow_html=True,
            )


def inventory_signal(label, food, quantity, unit):
    """Present the existing inventory extrema with a compact visual hierarchy."""
    theme = THEMES[current_theme()]
    accent = theme["green"] if "consumption" in label.lower() else theme["waste"]
    st.markdown(
        f'<div class="signal-card" style="--signal-accent:{accent}"><div class="signal-label">{escape(label)}</div>'
        f'<div class="signal-name">{escape(str(food))}</div>'
        f'<div class="signal-value">{quantity:.2f} {escape(str(unit))}</div></div>',
        unsafe_allow_html=True,
    )


def quantity_summary(df, quantity_column):
    return df.groupby(["Food", "Quantity_Unit"], as_index=False)[quantity_column].sum().sort_values(quantity_column, ascending=False)


def section_heading(title, note=None):
    st.markdown(f'<div class="chart-title">{title}</div>', unsafe_allow_html=True)
    if note:
        st.markdown(f'<div class="chart-note">{note}</div>', unsafe_allow_html=True)


def configure_chart(chart):
    """Apply the active palette to every Altair chart surface and label."""
    theme = THEMES[current_theme()]
    return chart.configure(
        background=theme["surface_alt"],
        font="Inter, ui-sans-serif, system-ui, sans-serif",
    ).configure_view(
        fill=theme["surface"], stroke=theme["border"], strokeWidth=1, cornerRadius=6,
    ).configure_axis(
        gridColor=theme["grid"], gridOpacity=0.9, gridDash=[2, 3],
        domainColor=theme["text_secondary"], domainOpacity=0.42, tickColor=theme["text_secondary"], tickOpacity=0.35,
        labelColor=theme["text_secondary"], titleColor=theme["text_secondary"], labelFontSize=11,
        labelPadding=7, titleFontSize=11,
    ).configure_legend(
        labelColor=theme["text_secondary"], titleColor=theme["text"], labelFontSize=11,
        symbolSize=90, padding=4,
    ).configure_title(
        color=theme["text"],
    )


def chart_colors():
    """Return the small, semantic chart palette for the selected interface theme."""
    theme = THEMES[current_theme()]
    return {
        "consumption": theme["green"], "trend_waste": theme["accent"],
        "waste": theme["waste"], "waste_line": theme["waste_line"], "lime": theme["lime"],
        "teal": theme["teal"], "neutral": theme["text_secondary"],
    }


def themed_chart_color(color):
    """Resolve a semantic series identifier through the active palette."""
    return chart_colors()[color]


def themed_line_color(color):
    """Use the dedicated amber waste line while preserving other semantics."""
    palette = chart_colors()
    return palette["waste_line"] if color == ALERT_COLOR else palette[color]


def line_chart(data, x, y, color=None, height=330):
    """Render a consistent interactive line chart with lightweight tooltips."""
    chart = alt.Chart(data).mark_line(point=False, strokeWidth=2.4).encode(
        x=alt.X(f"{x}:T", title=None),
        y=alt.Y(f"{y}:Q", title=None),
        color=alt.Color(f"{color}:N", scale=alt.Scale(range=[chart_colors()["consumption"], chart_colors()["trend_waste"]]) if color else alt.Undefined, legend=alt.Legend(title=None) if color else None),
        tooltip=[alt.Tooltip(f"{x}:T", title="Date"), alt.Tooltip(f"{y}:Q", format=".2f"), *( [alt.Tooltip(f"{color}:N")] if color else [])],
    ).properties(height=height)
    chart = configure_chart(chart)
    st.altair_chart(chart, width="stretch")


def bar_chart(data, label_column, value_column, color, height=300, value_format=".2f"):
    """Render an intentional ranked horizontal bar chart."""
    chart = alt.Chart(data).mark_bar(color=themed_chart_color(color), cornerRadiusEnd=4, size=18).encode(
        y=alt.Y(f"{label_column}:N", sort="-x", title=None),
        x=alt.X(f"{value_column}:Q", title=None),
        tooltip=[alt.Tooltip(f"{label_column}:N", title="Item"), alt.Tooltip(f"{value_column}:Q", format=value_format)],
    ).properties(height=height)
    chart = configure_chart(chart)
    st.altair_chart(chart, width="stretch")


def series_line_chart(data, colors, height=300, markers=False):
    """Render Streamlit series with the shared responsive product chart style."""
    chart_data = data.rename_axis("Date").reset_index().melt("Date", var_name="Measure", value_name="Quantity")
    chart = alt.Chart(chart_data).mark_line(
        point=alt.OverlayMarkDef(size=30, filled=True) if markers else False,
        strokeWidth=3.2 if markers else 2.8,
    ).encode(
        x=alt.X("Date:T", title=None), y=alt.Y("Quantity:Q", title=None),
        color=alt.Color("Measure:N", scale=alt.Scale(range=[themed_line_color(color) for color in colors]), legend=alt.Legend(title=None)),
        tooltip=[alt.Tooltip("Date:T", title="Date"), "Measure:N", alt.Tooltip("Quantity:Q", format=".2f")],
    ).properties(height=height)
    st.altair_chart(configure_chart(chart), width="stretch")


def series_bar_chart(data, color, height=300):
    """Render a single analytical series using the shared product chart style."""
    series_name = data.name or "Quantity"
    chart_data = data.rename(series_name).rename_axis("Label").reset_index()
    chart = alt.Chart(chart_data).mark_bar(color=themed_chart_color(color), cornerRadiusEnd=5, size=19).encode(
        y=alt.Y("Label:N", sort="-x", title=None), x=alt.X(f"{series_name}:Q", title=None),
        tooltip=[alt.Tooltip("Label:N", title="Item"), alt.Tooltip(f"{series_name}:Q", format=".2f")],
    ).properties(height=height)
    st.altair_chart(configure_chart(chart), width="stretch")


def render_filters(df):
    """Return consumption records filtered by the visible controls."""
    with st.container(border=True):
        st.markdown("**Explore consumption records**")
        first, second, third = st.columns([1, 1, 1.3])
        with first:
            foods = st.multiselect("Food", sorted(df["Food"].unique()), placeholder="All foods")
        with second:
            categories = st.multiselect("Category", sorted(df["Category"].unique()), placeholder="All categories")
        with third:
            dates = st.date_input("Date range", value=(df["Date"].min().date(), df["Date"].max().date()), min_value=df["Date"].min().date(), max_value=df["Date"].max().date())
    filtered = df.copy()
    if foods:
        filtered = filtered[filtered["Food"].isin(foods)]
    if categories:
        filtered = filtered[filtered["Category"].isin(categories)]
    if len(dates) == 2:
        filtered = filtered[filtered["Date"].between(pd.Timestamp(dates[0]), pd.Timestamp(dates[1]))]
    return filtered


def render_provenance(profile):
    """Show a compact, reusable source contract beside public-data statistics."""
    with st.container(border=True):
        section_heading("Data provenance")
        left, right = st.columns(2)
        left.caption(f"**Source:** {profile['source']}\n\n**Purpose:** {profile['type']}\n\n**Records:** {profile['records']:,} × {profile['columns']} columns\n\n**Coverage:** {profile['date_range']}")
        right.caption(f"**Available:** {profile['available']}\n\n**Not available:** {profile['unavailable']}\n\n**Forecasting:** {profile['forecasting']} · **Waste:** {profile['waste']} · **Inventory:** {profile['inventory']}")


def instacart_summary(df, *, detailed=False):
    profile = instacart_profile(df)
    orders = df["Order_ID"].nunique()
    metric_row([("Total orders", f"{orders:,}"), ("Unique users", f"{df['User_ID'].nunique():,}"), ("Products", f"{df['Product_ID'].nunique():,}"), ("Items ordered", f"{len(df):,}"), ("Reorder rate", f"{df['Reordered'].mean() * 100:.1f}%")])
    st.caption("Source: Instacart Market Basket Analysis — real order/purchase behavior. Product lines are not physical quantities or household consumption.")
    render_provenance(profile)
    top_products = df.groupby("Product_Name", as_index=False).size().rename(columns={"size": "Order_Lines"}).nlargest(12, "Order_Lines")
    departments = df.groupby("Department", as_index=False).size().rename(columns={"size": "Order_Lines"})
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Most ordered products", "Order-line count")
            bar_chart(top_products, "Product_Name", "Order_Lines", PRIMARY_COLOR, 340, ".0f")
    with right:
        with st.container(border=True):
            section_heading("Department popularity", "Order-line count")
            bar_chart(departments, "Department", "Order_Lines", SUPPORT_COLOR, 340, ".0f")
    if detailed:
        left, right = st.columns(2)
        with left:
            with st.container(border=True):
                section_heading("Orders by source weekday", "Distinct orders; source day code 0–6")
                by_day = df.groupby("Order_Day_Of_Week", as_index=False)["Order_ID"].nunique().rename(columns={"Order_ID": "Orders"})
                bar_chart(by_day, "Order_Day_Of_Week", "Orders", ACCENT_COLOR, 300, ".0f")
        with right:
            with st.container(border=True):
                section_heading("Orders by hour", "Distinct orders")
                by_hour = df.groupby("Order_Hour", as_index=False)["Order_ID"].nunique().rename(columns={"Order_ID": "Orders"})
                bar_chart(by_hour, "Order_Hour", "Orders", NEUTRAL_COLOR, 300, ".0f")


def m5_summary(df, *, detailed=False):
    profile = m5_profile(df)
    daily = df.groupby("Date", as_index=False)["Quantity_Sold"].sum()
    metric_row([("Retail unit sales", f"{df['Quantity_Sold'].sum():,.0f}"), ("Products", f"{df['Product_ID'].nunique():,}"), ("Stores", f"{df['Store_ID'].nunique()}"), ("Departments", f"{df['Department'].nunique()}"), ("Average daily demand", f"{daily['Quantity_Sold'].mean():,.1f}")])
    st.caption("Source: M5 Walmart Retail Sales — observed retail unit sales/demand, not household consumption or food waste.")
    render_provenance(profile)
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Retail sales trend", "Total daily unit sales")
            line_chart(daily, "Date", "Quantity_Sold", height=300)
    with right:
        with st.container(border=True):
            section_heading("Top-selling M5 items", "Retail unit sales")
            top = df.groupby("Product_ID", as_index=False)["Quantity_Sold"].sum().nlargest(12, "Quantity_Sold")
            bar_chart(top, "Product_ID", "Quantity_Sold", PRIMARY_COLOR, 300, ".0f")
            st.caption("Labels such as `FOODS_3_090` are original M5 item IDs, not food names.")
    if detailed:
        left, right = st.columns(2)
        with left:
            with st.container(border=True):
                section_heading("Demand by weekday")
                bar_chart(df.groupby("Weekday", as_index=False)["Quantity_Sold"].sum(), "Weekday", "Quantity_Sold", ACCENT_COLOR, 290, ".0f")
        with right:
            with st.container(border=True):
                section_heading("Demand by department")
                bar_chart(df.groupby("Department", as_index=False)["Quantity_Sold"].sum(), "Department", "Quantity_Sold", SUPPORT_COLOR, 290, ".0f")


def public_overview_page():
    page_header("Real public data", "Overview", "Choose a real public source. Metrics remain within that source and never include personal or synthetic records.")
    source = st.radio("Data source", ["Instacart", "M5 Retail Sales"], horizontal=True, key="overview_public_source")
    if source == "Instacart":
        if not INSTACART_DATA_PATH.exists():
            real_data_missing(INSTACART_DATA_PATH, "Overview")
            return
        data_source_badge("Real data", "Instacart Market Basket Analysis")
        instacart_summary(get_instacart_data())
    else:
        if not M5_DATA_PATH.exists():
            real_data_missing(M5_DATA_PATH, "Overview")
            return
        data_source_badge("Real data", "M5 / Walmart retail sales")
        m5_summary(get_m5_data())


def general_insights_page():
    page_header("Real public data", "General Insights", "Exploratory analysis of one selected data source; meanings are never combined.")
    source = st.radio("Data source", ["Instacart", "M5 Retail Sales", "Demo / Synthetic Data"], horizontal=True, key="general_public_source")
    if source == "Instacart":
        if not INSTACART_DATA_PATH.exists():
            real_data_missing(INSTACART_DATA_PATH, "General Insights")
            return
        data_source_badge("Real data", "Instacart Market Basket Analysis")
        instacart_summary(get_instacart_data(), detailed=True)
    elif source == "M5 Retail Sales":
        if not M5_DATA_PATH.exists():
            real_data_missing(M5_DATA_PATH, "General Insights")
            return
        data_source_badge("Real data", "M5 / Walmart retail sales")
        m5_summary(get_m5_data(), detailed=True)
    else:
        data_source_badge("Demo data", "Synthetic development dataset")
        st.warning("DEMO / SYNTHETIC DATA — these figures are simulated and are not used anywhere in normal real-data statistics.")
        demo = get_cleaned_data()
        render_provenance(demo_profile(demo))
        overview_page(demo)


def purchase_behavior_page():
    page_header("Real public data", "Purchase / demand behavior", "Instacart represents order behavior; M5 represents retail demand. Neither source measures household consumption.")
    source = st.radio("Data source", ["Instacart purchase behavior", "M5 retail demand"], horizontal=True, key="behavior_source")
    if source.startswith("Instacart"):
        if not INSTACART_DATA_PATH.exists():
            real_data_missing(INSTACART_DATA_PATH, "Purchase / demand behavior")
            return
        data_source_badge("Real data", "Instacart order behavior")
        df = get_instacart_data()
        basket = df.groupby("Order_ID").size().rename("Items_Per_Order")
        metric_row([("Orders", f"{len(basket):,}"), ("Average basket size", f"{basket.mean():.1f} product lines"), ("Median basket size", f"{basket.median():.0f} product lines"), ("Average days since prior order", f"{df[['Order_ID','Days_Since_Prior_Order']].drop_duplicates()['Days_Since_Prior_Order'].mean():.1f}")])
        st.caption("Proxy only: basket size and interval between orders describe ordering behavior, not food consumption or waste.")
        section_heading("Product purchase behavior")
        top = df.groupby("Product_Name", as_index=False).size().rename(columns={"size": "Order_Lines"}).nlargest(15, "Order_Lines")
        bar_chart(top, "Product_Name", "Order_Lines", PRIMARY_COLOR, 380, ".0f")
    else:
        if not M5_DATA_PATH.exists():
            real_data_missing(M5_DATA_PATH, "Purchase / demand behavior")
            return
        data_source_badge("Real data", "M5 retail demand")
        df = get_m5_data()
        daily = df.groupby("Date")["Quantity_Sold"].sum()
        metric_row([("Retail unit sales", f"{daily.sum():,.0f}"), ("Average daily demand", f"{daily.mean():.1f}"), ("Peak daily demand", f"{daily.max():.0f}"), ("Products", f"{df['Product_ID'].nunique()}")])
        st.caption("M5 provides retail demand only; it does not provide household consumption, measured food waste, household inventory, or expiry dates.")
        series_line_chart(daily, [PRIMARY_COLOR], 330)


def waste_unavailable_page():
    page_header("Real public data", "Waste analysis", "FORAGE reports only measurements supported by the selected source.")
    data_source_badge("Real data", "Instacart and M5 public extracts")
    st.info("Waste analysis requires explicit waste or disposal records. The selected real datasets do not contain household waste measurements, so FORAGE does not estimate or fabricate waste values.")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Instacart availability")
            st.write("Orders, product lines, reorders, departments, aisles, and order timing are available. Household waste, consumption, inventory, expiry, and physical quantities are not available.")
    with right:
        with st.container(border=True):
            section_heading("M5 availability")
            st.write("Retail unit sales, dates/calendar, item/category information, price, event data, and demand forecasting are available. Household consumption, measured food waste, household inventory, and expiry dates are not available.")


def retail_forecasting_page():
    page_header("M5 / Walmart — Real Public Dataset", "Retail Demand Forecast", "Forecast target: retail unit sales. This is a chronological retail-demand evaluation, not a household-consumption forecast.")
    if not M5_DATA_PATH.exists():
        real_data_missing(M5_DATA_PATH, "Retail Demand Forecast")
        return
    data_source_badge("Real data", "M5 / Walmart retail sales")
    tested, _, comparison, metadata = get_m5_forecast_results()
    best = comparison.iloc[0]
    metric_row([("Selected model", metadata["best_model"]), ("MAE", f"{best['MAE']:.2f}"), ("RMSE", f"{best['RMSE']:.2f}"), ("R²", f"{best['R2']:.3f}"), ("Chronological test begins", f"{metadata['cutoff']:%d %b %Y}")])
    st.caption("All models use the same later M5 test period. Lag and rolling inputs use only prior sales; price filling uses the training period only.")
    ranked = comparison.copy()
    ranked.insert(0, "Rank", range(1, len(ranked) + 1))
    st.dataframe(ranked.rename(columns={"R2": "R²"}).round(3), width="stretch", hide_index=True)
    product = st.selectbox("Product for actual vs predicted retail sales", sorted(tested["Product_ID"].unique()), key="retail_forecast_product")
    selected = tested[tested["Product_ID"] == product].groupby("Date")[["Quantity_Sold", "Predicted_Sales"]].sum()
    series_line_chart(selected, [PRIMARY_COLOR, SUPPORT_COLOR], 350)


def real_recommendations_page():
    page_header("Real public data", "Explainable insights", "Public data can support demand and reorder insights, but not household purchase quantities without inventory and physical units.")
    source = st.radio("Data source", ["Instacart reorder behavior", "M5 expected retail demand"], horizontal=True, key="real_recommendation_source")
    if source.startswith("Instacart"):
        if not INSTACART_DATA_PATH.exists():
            real_data_missing(INSTACART_DATA_PATH, "Recommendations")
            return
        data_source_badge("Real data", "Instacart reorder behavior")
        df = get_instacart_data()
        table = df.groupby("Product_Name").agg(Order_Lines=("Order_ID", "size"), Reorders=("Reordered", "sum"), Reorder_Rate=("Reordered", "mean")).sort_values(["Reorders", "Order_Lines"], ascending=False).head(20).reset_index()
        st.caption("These are observed repeat-purchase patterns, not recommendations to buy a quantity.")
        metric_row([("Products with reorders", f"{(table['Reorders'] > 0).sum()} of top 20"), ("Overall reorder rate", f"{df['Reordered'].mean() * 100:.1f}%"), ("Top product", table.iloc[0]['Product_Name'])])
        st.dataframe(table.round({"Reorder_Rate": 3}), width="stretch", hide_index=True)
    else:
        if not M5_DATA_PATH.exists():
            real_data_missing(M5_DATA_PATH, "Recommendations")
            return
        data_source_badge("Real data", "M5 expected retail demand")
        tested, _, comparison, metadata = get_m5_forecast_results()
        best = comparison.iloc[0]
        st.caption("Expected retail demand only. FORAGE does not turn M5 sales into a household grocery purchase recommendation.")
        expected = tested.groupby("Product_ID", as_index=False).agg(Actual_Unit_Sales=("Quantity_Sold", "sum"), Predicted_Unit_Sales=("Predicted_Sales", "sum")).sort_values("Predicted_Unit_Sales", ascending=False).head(20)
        metric_row([("Selected model", metadata["best_model"]), ("Forecast MAE", f"{best['MAE']:.2f}"), ("Forecast RMSE", f"{best['RMSE']:.2f}"), ("Forecast R²", f"{best['R2']:.3f}")])
        st.dataframe(expected.round(2), width="stretch", hide_index=True)


def overview_page(df):
    page_header("Demo / Synthetic Data", "Demo Insights", "Simulated 7,300-row development data. These statistics are never used for normal real-data views or My Stats.")
    total_purchased = df["Quantity_Purchased"].sum()
    total_consumed = df["Quantity_Consumed"].sum()
    total_wasted = df["Quantity_Wasted"].sum()
    waste_percentage = total_wasted / total_purchased * 100
    monthly = df.groupby("Month").agg(Consumption=("Quantity_Consumed", "sum"), Waste=("Quantity_Wasted", "sum"))
    month_delta = monthly["Waste"].iloc[-1] - monthly["Waste"].iloc[-2]
    highest_waste = quantity_summary(df, "Quantity_Wasted").iloc[0]
    highest_consumption = quantity_summary(df, "Quantity_Consumed").iloc[0]

    metric_row([
        ("Purchased", f"{total_purchased:,.2f}", None, "Total recorded purchase quantity"),
        ("Consumed", f"{total_consumed:,.2f}", None, "Total recorded consumption quantity"),
        ("Wasted", f"{total_wasted:,.2f}", f"{month_delta:+.2f} vs previous month"),
        ("Overall waste", f"{waste_percentage:.2f}%", None, "Total waste divided by total purchased quantity"),
        ("Food items", f"{df['Food'].nunique()}", None, "Unique food names in the dataset"),
    ])
    recorded_quantity_note()

    st.caption(f"Coverage: {df['Date'].min():%d %b %Y} – {df['Date'].max():%d %b %Y}  ·  Cleaned dataset active")
    left, right = st.columns([1.65, 1])
    with left:
        with st.container(border=True):
            section_heading("Consumption & waste trend", "Monthly recorded consumption and waste")
            monthly_long = monthly.reset_index().melt("Month", var_name="Measure", value_name="Quantity")
            palette = chart_colors()
            chart = alt.Chart(monthly_long).mark_line(point=alt.OverlayMarkDef(size=34, filled=True), strokeWidth=2.8).encode(
                x=alt.X("Month:O", title=None), y=alt.Y("Quantity:Q", title=None),
                color=alt.Color("Measure:N", scale=alt.Scale(range=[palette["consumption"], palette["trend_waste"]]), legend=alt.Legend(title=None)),
                tooltip=["Month:O", "Measure:N", alt.Tooltip("Quantity:Q", format=".2f")],
            ).properties(height=300)
            st.altair_chart(configure_chart(chart), width="stretch")
    with right:
        with st.container(border=True):
            section_heading("Inventory signals", "Highest item-level totals")
            inventory_signal("Highest consumption", highest_consumption["Food"], highest_consumption["Quantity_Consumed"], highest_consumption["Quantity_Unit"])
            inventory_signal("Highest waste", highest_waste["Food"], highest_waste["Quantity_Wasted"], highest_waste["Quantity_Unit"])
            st.caption("Use the waste workspace to review high-waste alerts and food-level actions.")
    first, second = st.columns(2)
    category_consumption = df.groupby("Category", as_index=False)["Quantity_Consumed"].sum()
    category_waste = df.groupby("Category", as_index=False)["Quantity_Wasted"].sum()
    with first:
        with st.container(border=True):
            section_heading("Consumption by category", "Recorded consumption by food category")
            bar_chart(category_consumption, "Category", "Quantity_Consumed", PRIMARY_COLOR, 255)
    with second:
        with st.container(border=True):
            section_heading("Waste by category", "Recorded waste by food category")
            bar_chart(category_waste, "Category", "Quantity_Wasted", ALERT_COLOR, 255)
    first, second = st.columns(2)
    with first:
        with st.container(border=True):
            section_heading("Most consumed foods", "Top recorded consumption totals")
            bar_chart(quantity_summary(df, "Quantity_Consumed").head(8), "Food", "Quantity_Consumed", PRIMARY_COLOR, 235)
    with second:
        with st.container(border=True):
            section_heading("Most wasted foods", "Top recorded waste totals")
            bar_chart(quantity_summary(df, "Quantity_Wasted").head(8), "Food", "Quantity_Wasted", ALERT_COLOR, 235)


def consumption_page(df):
    page_header("FORAGE Dataset", "Consumption analysis", "General/demo analysis only. Personal records are available in My Stats.")
    filtered = render_filters(df)
    if filtered.empty:
        st.warning("No records match the selected filters. Change a filter to view consumption results.")
        return
    total_consumption = filtered["Quantity_Consumed"].sum()
    average_consumption = filtered["Quantity_Consumed"].mean()
    weekend_average = filtered.loc[filtered["Is_Weekend"] == 1, "Quantity_Consumed"].mean()
    metric_row([("Matching records", f"{len(filtered):,}"), ("Recorded consumption", f"{total_consumption:,.2f}"), ("Average per record", f"{average_consumption:.2f}"), ("Weekend average", f"{weekend_average:.2f}")])
    recorded_quantity_note()

    trend = filtered.groupby("Date")["Quantity_Consumed"].sum()
    food = quantity_summary(filtered, "Quantity_Consumed").set_index("Food")
    category = filtered.groupby("Category")["Quantity_Consumed"].sum().sort_values(ascending=False)
    day_type = filtered.assign(Day_Type=filtered["Is_Weekend"].map({0: "Weekday", 1: "Weekend"})).groupby("Day_Type")["Quantity_Consumed"].mean().reindex(["Weekday", "Weekend"])
    with st.container(border=True):
        st.subheader("Consumption trend")
        st.caption("Daily recorded consumption for the active filters")
        series_line_chart(trend, [PRIMARY_COLOR], height=285)
    first, second = st.columns(2)
    with first:
        with st.container(border=True):
            st.subheader("By food")
            series_bar_chart(food["Quantity_Consumed"], PRIMARY_COLOR, height=345)
    with second:
        with st.container(border=True):
            st.subheader("By category")
            series_bar_chart(category, NEUTRAL_COLOR, height=345)
    with st.container(border=True):
        st.subheader("Weekday versus weekend")
        st.caption("Average recorded consumption per row")
        series_bar_chart(day_type, ACCENT_COLOR, height=225)


def waste_page(df):
    page_header("FORAGE Dataset", "Waste analysis", "General/demo analysis only. Personal records are available in My Stats.")
    total_waste = df["Quantity_Wasted"].sum()
    overall_waste = total_waste / df["Quantity_Purchased"].sum() * 100
    food_waste = df.groupby(["Food", "Quantity_Unit"]).agg(
        Total_Waste=("Quantity_Wasted", "sum"),
        Waste_Percentage=("Quantity_Wasted", lambda values: values.sum() / df.loc[values.index, "Quantity_Purchased"].sum() * 100),
    ).sort_values("Waste_Percentage", ascending=False)
    category_waste = df.groupby("Category").agg(
        Total_Waste=("Quantity_Wasted", "sum"),
        Waste_Percentage=("Quantity_Wasted", lambda values: values.sum() / df.loc[values.index, "Quantity_Purchased"].sum() * 100),
    ).sort_values("Waste_Percentage", ascending=False)
    highest_food, _ = food_waste.index[0]
    metric_row([
        ("Total waste", f"{total_waste:,.2f}"),
        ("Overall waste rate", f"{overall_waste:.2f}%"),
        ("Highest waste-rate food", highest_food, f"{food_waste.iloc[0]['Waste_Percentage']:.2f}%"),
        ("Highest waste category", category_waste.index[0], f"{category_waste.iloc[0]['Waste_Percentage']:.2f}%"),
    ])
    recorded_quantity_note()

    with st.container(border=True):
        st.subheader("Waste trend")
        st.caption("Daily recorded waste")
        series_line_chart(df.groupby("Date")["Quantity_Wasted"].sum(), [ALERT_COLOR], height=275, markers=True)
    first, second = st.columns(2)
    with first:
        with st.container(border=True):
            st.subheader("Waste rate by food")
            food_rate_chart = food_waste.reset_index().set_index("Food")["Waste_Percentage"].head(12)
            series_bar_chart(food_rate_chart, ALERT_COLOR, height=360)
    with second:
        with st.container(border=True):
            st.subheader("Waste rate by category")
            series_bar_chart(category_waste["Waste_Percentage"], ACCENT_COLOR, height=360)
    with st.container(border=True):
        st.subheader("High-waste items")
        st.dataframe(food_waste.head(10).reset_index().round(2), width="stretch", hide_index=True)


def forecasting_page():
    page_header("FORAGE Dataset", "General demand forecast", "General/demo forecast only; personal forecasting is available in My Stats when enough history exists.")
    comparison, chart_data, best_model, cutoff_date = get_forecast_results()
    best_metrics = comparison.iloc[0]
    metric_row([
        ("Selected model", best_model),
        ("MAE", f"{best_metrics['MAE']:.4f}", None, "Average absolute prediction error; lower is better"),
        ("RMSE", f"{best_metrics['RMSE']:.4f}", None, "Penalizes larger prediction errors; lower is better"),
        ("R²", f"{best_metrics['R2']:.4f}", None, "How much variation the model explains; higher is better"),
    ])
    st.caption(f"Chronological test period starts on {cutoff_date:%d %b %Y}; later dates are never used for training.")
    first, second = st.columns([1, 1.25])
    with first:
        with st.container(border=True):
            st.subheader("How to read these metrics")
            st.markdown("- **MAE:** typical prediction error.\n- **RMSE:** gives extra weight to larger errors.\n- **R²:** fit compared with observed consumption.")
    with second:
        with st.container(border=True):
            st.subheader("Model comparison")
            st.dataframe(comparison.rename(columns={"R2": "R²"}).round(4), width="stretch", hide_index=True)
    with st.container(border=True):
        selected_food = st.selectbox("Food for actual versus predicted comparison", sorted(chart_data["Food"].unique()))
        selected = chart_data[chart_data["Food"] == selected_food].set_index("Date")
        st.subheader(f"Actual versus predicted: {selected_food}")
        st.caption(f"Quantity unit: {selected['Quantity_Unit'].iloc[0]}")
        series_line_chart(selected[["Quantity_Consumed", "Predicted_Consumption"]], [PRIMARY_COLOR, SUPPORT_COLOR], height=350)
    recommendations = get_recommendations()
    with st.container(border=True):
        st.subheader("Next-day predicted demand")
        st.info("The next-day forecast uses Is_Festival = 0 because no confirmed future event calendar is supplied.")
        st.dataframe(recommendations[["Food", "Quantity_Unit", "Forecast_Date", "Predicted_Demand"]].round(2), width="stretch", hide_index=True)


def recommendations_page():
    page_header("FORAGE Dataset", "General purchase plan", "General/demo recommendations based on the FORAGE Dataset, not your personal records.")
    recommendations = get_recommendations()
    needs_purchase = recommendations["Recommended_Purchase_Quantity"] > 0
    active_alerts = recommendations["Alerts"].ne("No alert")
    highest_purchase = recommendations.iloc[0]
    metric_row([
        ("Forecast date", f"{recommendations['Forecast_Date'].iloc[0]:%d %b %Y}"),
        ("Items to purchase", f"{needs_purchase.sum()}"),
        ("Already covered", f"{(~needs_purchase).sum()}"),
        ("High-risk alerts", f"{active_alerts.sum()}"),
    ])
    st.caption("Quantities remain food-specific: mixed units are not summed into one misleading total.")
    st.markdown(f"<div class='chart-note'>Highest immediate purchase action: <b>{escape(str(highest_purchase['Food']))}</b> · {highest_purchase['Recommended_Purchase_Quantity']:.2f} {escape(str(highest_purchase['Quantity_Unit']))}</div>", unsafe_allow_html=True)

    section_heading("Recommended actions", "Cards are ordered by recommended purchase quantity")
    card_rows = recommendations.head(12).reset_index(drop=True)
    for start in range(0, len(card_rows), 2):
        columns = st.columns(2)
        for column, (_, row) in zip(columns, card_rows.iloc[start:start + 2].iterrows()):
            labels = []
            if "highest 25%" in row["Alerts"]:
                labels.append("<span class='badge badge-waste'>HIGH WASTE</span>")
            if "below predicted demand" in row["Alerts"]:
                labels.append("<span class='badge badge-low'>LOW STOCK</span>")
            if row["Recommended_Purchase_Quantity"] == 0:
                labels.append("<span class='badge badge-covered'>STOCK COVERED</span>")
            badges = "".join(labels) or "<span class='badge badge-covered'>MONITOR</span>"
            with column:
                st.markdown(
                    f"""<div class='rec-card'>
                    <div class='rec-name'>{escape(str(row['Food']))}</div>
                    <div class='rec-category'>{escape(str(row['Category']))} · {escape(str(row['Quantity_Unit']))}</div>
                    <div class='rec-quantity'>{row['Recommended_Purchase_Quantity']:.2f} {escape(str(row['Quantity_Unit']))}</div>
                    <div class='rec-label'>RECOMMENDED PURCHASE</div>
                    <div style='margin-top:.65rem;font-size:.84rem'>Demand <b>{row['Predicted_Demand']:.2f}</b> · Remaining <b>{row['Current_Remaining_Quantity']:.2f}</b> · Waste <b>{row['Historical_Waste_Percentage']:.1f}%</b></div>
                    <div>{badges}</div></div>""",
                    unsafe_allow_html=True,
                )
                with st.expander(f"Why {row['Food']}?"):
                    st.write(row["Reason"])
                    st.caption(f"Alert status: {row['Alerts']}")
    with st.expander("View the complete purchase plan table"):
        display_columns = ["Food", "Category", "Quantity_Unit", "Predicted_Demand", "Current_Remaining_Quantity", "Historical_Waste_Percentage", "Recommended_Purchase_Quantity", "Alerts"]
        st.dataframe(recommendations[display_columns].round(2), width="stretch", hide_index=True)
    st.download_button("Download recommendations CSV", recommendations.to_csv(index=False).encode("utf-8"), file_name="purchase_recommendations.csv", mime="text/csv")


def personal_forecast_and_recommendations(df):
    """Return personal-only, history-based signals when the records support them."""
    history = df.dropna(subset=["Date", "Food", "Quantity_Consumed"]).copy()
    eligible = history.groupby("Food").filter(lambda group: len(group) >= 7)
    if eligible.empty:
        return pd.DataFrame(), pd.DataFrame()
    forecast = (eligible.sort_values("Date").groupby("Food").tail(7).groupby(["Food", "Quantity_Unit"], as_index=False)
                .agg(Predicted_Next_Use=("Quantity_Consumed", "mean"), Current_Remaining_Quantity=("Remaining_Quantity", "last"),
                     Historical_Waste=("Quantity_Wasted", "sum"), Historical_Purchased=("Quantity_Purchased", "sum")))
    forecast["Predicted_Next_Use"] = forecast["Predicted_Next_Use"].clip(lower=0)
    forecast["Current_Remaining_Quantity"] = forecast["Current_Remaining_Quantity"].fillna(0)
    forecast["Waste_Percentage"] = (forecast["Historical_Waste"] / forecast["Historical_Purchased"].replace(0, pd.NA) * 100).fillna(0)
    forecast["Suggested_Purchase"] = (forecast["Predicted_Next_Use"] - forecast["Current_Remaining_Quantity"] * (1 - forecast["Waste_Percentage"] / 100)).clip(lower=0)
    recommendations = forecast.sort_values("Suggested_Purchase", ascending=False)
    return forecast, recommendations


def personal_insights(df):
    """Generate only claims directly supported by personal records."""
    if len(df) < 2:
        return ["Not enough personal data yet."]
    insights = []
    consumed = df.groupby("Food")["Quantity_Consumed"].sum().dropna()
    wasted = df.groupby("Food")["Quantity_Wasted"].sum().dropna()
    purchased = df["Quantity_Purchased"].sum()
    if not consumed.empty and consumed.max() > 0:
        insights.append(f"{consumed.idxmax()} is your most consumed food.")
    if not wasted.empty and wasted.max() > 0:
        insights.append(f"{wasted.idxmax()} accounts for the highest share of your recorded waste.")
    if purchased > 0:
        insights.append(f"Your recorded food waste is {df['Quantity_Wasted'].sum() / purchased * 100:.1f}%.")
    if df["Date"].nunique() >= 4:
        weekend = df.assign(Weekend=df["Date"].dt.dayofweek >= 5).groupby("Weekend")["Quantity_Wasted"].sum()
        if len(weekend) == 2 and weekend.nunique() > 1:
            insights.append("Your recorded waste is highest on weekends." if weekend.get(True, 0) > weekend.get(False, 0) else "Your recorded waste is highest on weekdays.")
    return insights or ["Not enough personal data yet."]


def my_stats_page():
    personal = load_personal_data()
    page_header("Personal insights", "My Stats", "Only the food records you add or import in this development mode are used here.")
    data_source_badge("Personal data", "My Food History")
    st.caption(f"Personal storage: {PERSONAL_DATA_PATH.name}. General FORAGE Dataset records are never included.")
    if personal.empty:
        with st.container(border=True):
            st.subheader("No personal food data yet.")
            st.caption("Your personal food insights will appear here once you add or import records.")
            if st.button("Add food", key="empty_add_food"):
                st.session_state.active_page = "Add Food"
                st.rerun()
        return

    total_purchased = personal["Quantity_Purchased"].sum()
    total_consumed = personal["Quantity_Consumed"].sum()
    total_wasted = personal["Quantity_Wasted"].sum()
    spending = personal["Price"].sum(min_count=1)
    kpis = [("Total purchased", f"{total_purchased:,.2f}"), ("Total consumed", f"{total_consumed:,.2f}"),
            ("Total wasted", f"{total_wasted:,.2f}"), ("Personal waste", f"{(total_wasted / total_purchased * 100) if total_purchased else 0:.2f}%"),
            ("Food items", f"{personal['Food'].nunique()}")]
    if pd.notna(spending):
        kpis.append(("Total spending", f"{spending:,.2f}"))
    metric_row(kpis)
    recorded_quantity_note()
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Personal consumption over time")
            series_line_chart(personal.groupby("Date")["Quantity_Consumed"].sum(), [PRIMARY_COLOR], 270)
    with right:
        with st.container(border=True):
            section_heading("Personal waste over time")
            series_line_chart(personal.groupby("Date")["Quantity_Wasted"].sum(), [ALERT_COLOR], 270)
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Most consumed foods")
            series_bar_chart(personal.groupby("Food")["Quantity_Consumed"].sum().sort_values(ascending=False).head(10), PRIMARY_COLOR, 280)
    with right:
        with st.container(border=True):
            section_heading("Most wasted foods")
            series_bar_chart(personal.groupby("Food")["Quantity_Wasted"].sum().sort_values(ascending=False).head(10), ALERT_COLOR, 280)
    food_summary = personal.groupby("Food").agg(Purchased=("Quantity_Purchased", "sum"), Waste=("Quantity_Wasted", "sum"))
    food_summary["Waste percentage"] = food_summary["Waste"] / food_summary["Purchased"].replace(0, pd.NA) * 100
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Waste percentage by food")
            series_bar_chart(food_summary["Waste percentage"].dropna().sort_values(ascending=False).head(10), ALERT_COLOR, 280)
    with right:
        with st.container(border=True):
            section_heading("Personal category breakdown")
            series_bar_chart(personal.groupby("Category")["Quantity_Consumed"].sum().sort_values(ascending=False), NEUTRAL_COLOR, 280)
    if personal["Price"].notna().any():
        with st.container(border=True):
            section_heading("Spending by food")
            series_bar_chart(personal.groupby("Food")["Price"].sum().sort_values(ascending=False), SUPPORT_COLOR, 250)
    with st.container(border=True):
        section_heading("Purchased vs consumed vs wasted")
        comparison = personal.groupby("Date")[["Quantity_Purchased", "Quantity_Consumed", "Quantity_Wasted"]].sum()
        series_line_chart(comparison, [SUPPORT_COLOR, PRIMARY_COLOR, ALERT_COLOR], 280)
    with st.container(border=True):
        section_heading("Personal insights")
        for insight in personal_insights(personal):
            st.write(f"• {insight}")
    forecast, recommendations = personal_forecast_and_recommendations(personal)
    with st.container(border=True):
        section_heading("Personal forecasting")
        if forecast.empty:
            st.info("Add more personal history to unlock personal forecasting.")
        else:
            st.caption("Forecasts use each food's own latest seven personal records; no FORAGE Dataset records are used.")
            st.dataframe(forecast[["Food", "Quantity_Unit", "Predicted_Next_Use"]].round(2), width="stretch", hide_index=True)
    with st.container(border=True):
        section_heading("Personal recommendations")
        if recommendations.empty:
            st.info("Add more personal purchase and consumption history to generate personalized recommendations.")
        else:
            st.dataframe(recommendations[["Food", "Quantity_Unit", "Suggested_Purchase", "Waste_Percentage"]].round(2), width="stretch", hide_index=True)
    render_personal_data_manager(personal)


def render_personal_data_manager(personal):
    with st.expander("View, edit, or delete personal records"):
        st.caption("Changes save only to My Data. Delete rows in the table and select Save changes.")
        editable_columns = ["Record_ID", "Date", "Food", "Category", "Quantity_Purchased", "Quantity_Consumed", "Quantity_Wasted", "Price", "Expiry_Days", "Storage_Type", "Remaining_Quantity", "Quantity_Unit"]
        edited = st.data_editor(personal[editable_columns], hide_index=True, num_rows="dynamic", width="stretch", key="personal_data_editor", column_config={"Record_ID": None})
        if st.button("Save changes to My Data", key="save_personal_changes"):
            try:
                save_personal_data(edited)
                st.success("Your personal food data was updated.")
                st.rerun()
            except Exception as error:
                st.error(f"Could not save personal data: {error}")
        report = personal_quality_report(personal)
        st.caption("Personal data quality")
        metric_row([("Records", str(report["rows"])), ("Missing values", str(sum(report["missing_values"].values()))), ("Duplicates", str(report["duplicate_rows"])), ("Invalid dates", str(report["invalid_dates"])), ("Invalid numeric values", str(sum(report["invalid_numeric_values"].values())))])


def dataset_quality_page():
    page_header("Data ingestion", "Dataset quality", "Inspect a real processed extract or an uploaded food-related CSV. Source files are never modified.")
    st.markdown("""<div class="workflow">
    <div class="workflow-step"><b>01</b>Upload</div><div class="workflow-step"><b>02</b>Inspect</div>
    <div class="workflow-step"><b>03</b>Quality check</div><div class="workflow-step"><b>04</b>Schema mapping</div>
    <div class="workflow-step"><b>05</b>Preview</div><div class="workflow-step"><b>06</b>Import to My Data</div></div>""", unsafe_allow_html=True)
    source = st.radio("Quality report source", ["M5 Forecasting extract", "Instacart extract", "Upload generic food CSV"], horizontal=True)
    if source != "Upload generic food CSV":
        report_path = M5_QUALITY_PATH if source.startswith("M5") else INSTACART_QUALITY_PATH
        if not report_path.exists():
            st.warning("The processed-data quality report is unavailable. Run `python src/real_data_processor.py` to rebuild it from the raw public dataset.")
            return
        report = json.loads(report_path.read_text(encoding="utf-8"))
        st.caption("This report is produced during bounded, dataset-specific preprocessing. It describes the processed extract and join checks without loading large raw files into the interface.")
        metric_row([("Rows", f"{report.get('rows', 0):,}"), ("Columns", str(len(report.get("columns", [])))), ("Duplicate relationship keys", str(report.get("duplicate_keys", 0))), ("Invalid dates", str(report.get("invalid_dates", "Not applicable")))])
        left, right = st.columns(2)
        with left:
            section_heading("Detected schema")
            st.dataframe(pd.DataFrame({"Column": report.get("columns", [])}), width="stretch", hide_index=True)
        with right:
            section_heading("Quality and join checks")
            checks = {key: value for key, value in report.items() if key not in {"columns", "missing_values", "selection"}}
            st.json(checks)
        with st.expander("Missing values and extraction selection"):
            st.json({"missing_values": report.get("missing_values", {}), "selection": report.get("selection", {})})
        return

    st.markdown("<div class='upload-well'>", unsafe_allow_html=True)
    section_heading("Import a CSV", "Drag and drop a food-related CSV. The original file is never changed.")
    with st.container():
        uploaded_file = st.file_uploader("Upload external food CSV", type="csv", help="The original file is not changed.")
        st.caption("The existing alias mapping and data-quality pipeline are used. Missing fields are reported; no values are invented.")
    st.markdown("</div>", unsafe_allow_html=True)
    if uploaded_file is None:
        st.info("Upload a CSV to inspect detected columns, mappings, quality checks, and the processed standardized result.")
        return
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temporary_file:
            temporary_file.write(uploaded_file.getvalue())
            temporary_path = temporary_file.name
        result = process_external_csv(temporary_path)
    except Exception as error:
        st.error(f"The uploaded CSV could not be processed: {error}")
        return
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)

    inspection, report, cleaning_summary = result["inspection"], result["quality_report"], result["cleaning_summary"]
    metric_row([("Rows", f"{inspection['shape'][0]:,}"), ("Columns", f"{inspection['shape'][1]}"), ("Duplicate rows", f"{inspection['duplicate_rows']}"), ("Missing values", f"{sum(report['missing_values'].values())}")])
    first, second = st.columns(2)
    with first:
        with st.container(border=True):
            st.subheader("Detected columns and missing values")
            st.dataframe(pd.DataFrame({"Column": inspection["data_types"].keys(), "Data type": inspection["data_types"].values(), "Missing values": inspection["missing_values"].values()}), width="stretch", hide_index=True)
    with second:
        with st.container(border=True):
            st.subheader("Schema mapping")
            mapping = result["column_mapping"]
            if mapping:
                st.dataframe(pd.DataFrame({"FDS column": mapping.keys(), "Uploaded column": mapping.values()}), width="stretch", hide_index=True)
            else:
                st.warning("No supported columns were detected in this file.")
            if report["missing_required_standard_columns"]:
                st.warning("Missing required fields: " + ", ".join(report["missing_required_standard_columns"]))
            if report["unmapped_source_columns"]:
                st.info("Unmapped uploaded columns: " + ", ".join(report["unmapped_source_columns"]))
    with st.container(border=True):
        st.subheader("Quality checks and cleaning actions")
        removed_rows = sum(value for key, value in cleaning_summary.items() if key.startswith("rows_removed")) + cleaning_summary["duplicates_removed"]
        metric_row([("Invalid dates", f"{report['invalid_dates']}"), ("Invalid numeric values", f"{sum(report['invalid_numeric_values'].values())}"), ("Negative values", f"{sum(report['negative_values'].values())}"), ("Rows removed", f"{removed_rows}")])
        outliers = pd.DataFrame.from_dict(report["suspicious_outliers_iqr"], orient="index").rename_axis("Column").reset_index()
        if not outliers.empty:
            st.caption("IQR outliers are flagged for review and are not automatically removed.")
            st.dataframe(outliers, width="stretch", hide_index=True)
        st.caption("Derived columns: " + (", ".join(cleaning_summary["derived_columns"]) or "None"))
        if inspection["useful_unique_values"]:
            with st.expander("Useful unique values"):
                st.json(inspection["useful_unique_values"])
    with st.container(border=True):
        standardized = result["standardised_data"]
        st.subheader("Processed standardized dataset")
        st.caption(f"Showing the first {min(100, len(standardized))} processed rows.")
        st.dataframe(standardized.head(100), width="stretch", hide_index=True)
        st.download_button("Download processed dataset", standardized.to_csv(index=False).encode("utf-8"), file_name="standardized_external_food_data.csv", mime="text/csv")
        if report["missing_required_standard_columns"]:
            st.warning("Import to My Data is unavailable until Food and Date are supplied.")
        elif standardized.empty:
            st.warning("There are no valid records to import.")
        elif st.button("Add processed records to My Data", key="import_to_personal"):
            append_personal_records(standardized)
            st.success(f"Added {len(standardized)} record(s) to your personal food data. The FORAGE Dataset was not changed.")


def data_input_page():
    page_header("Personal data", "Add food", "Add a record to your personal local data. It will not affect General Insights or the FORAGE Dataset.")
    data_source_badge("Personal data", "My Food History")
    with st.container(border=True):
        with st.form("manual_personal_entry", clear_on_submit=True):
            st.markdown('<div class="form-section">FOOD</div>', unsafe_allow_html=True)
            first, second, third = st.columns(3)
            date = first.date_input("Date")
            food = second.text_input("Food", placeholder="e.g., Milk")
            category = third.text_input("Category", placeholder="e.g., Dairy")
            st.markdown('<div class="form-section">QUANTITY</div>', unsafe_allow_html=True)
            first, second, third, fourth = st.columns(4)
            purchased = first.number_input("Quantity purchased", min_value=0.000, format="%.2f")
            consumed = second.number_input("Quantity consumed", min_value=0.000, format="%.2f")
            wasted = third.number_input("Quantity wasted", min_value=0.000, format="%.2f")
            remaining = fourth.number_input("Remaining quantity", min_value=0.000, format="%.2f")
            st.markdown('<div class="form-section">PURCHASE AND STORAGE</div>', unsafe_allow_html=True)
            first, second, third, fourth = st.columns(4)
            price = first.number_input("Price", min_value=0.000, format="%.2f")
            expiry_days = second.number_input("Expiry days", min_value=0, step=1)
            storage = third.selectbox("Storage type", ["Refrigerator", "Pantry", "Freezer", "Room temperature", "Other"])
            unit = fourth.selectbox("Unit", ["kg", "L", "g", "ml", "dozen", "loaf", "pack", "unit"])
            submitted = st.form_submit_button("Add to My Data")
        if submitted:
            if not food.strip() or purchased <= 0:
                st.error("Enter a food name and a quantity purchased greater than zero.")
            elif consumed + wasted + remaining > purchased + 0.011:
                st.error("Consumed, wasted, and remaining quantities cannot exceed quantity purchased.")
            else:
                add_personal_record({"Date": pd.Timestamp(date), "Food": food.strip(), "Category": category.strip() or "Uncategorized", "Quantity_Purchased": purchased, "Quantity_Consumed": consumed, "Quantity_Wasted": wasted, "Remaining_Quantity": remaining, "Price": price, "Expiry_Days": expiry_days, "Storage_Type": storage, "Quantity_Unit": unit, "Estimated_Expiry_Date": pd.Timestamp(date) + pd.Timedelta(days=expiry_days)})
                st.success("Added to your personal food data.")
    st.info("To add several records at once, use Import Dataset. Imports are processed through the shared mapping and data-quality pipeline, then saved only to My Data.")


def real_data_missing(path, label):
    page_header("Real data", label, "This page uses a separate, preprocessed public dataset and never changes My Data or the FORAGE demo dataset.")
    st.info("Run `python src/real_data_processor.py` from the project root to create the local analytical extract.")


def m5_demand_page():
    if not M5_DATA_PATH.exists():
        real_data_missing(M5_DATA_PATH, "M5 Demand")
        return
    df = get_m5_data()
    page_header("M5 Forecasting / Walmart retail sales dataset", "M5 Demand", "Retail unit sales and demand—not household consumption, food waste, or personal inventory.")
    daily = df.groupby("Date", as_index=False)["Quantity_Sold"].sum()
    metric_row([("Total units sold", f"{df['Quantity_Sold'].sum():,.0f}"), ("Products", f"{df['Product_ID'].nunique():,}"), ("Stores", f"{df['Store_ID'].nunique()}"), ("Departments", f"{df['Department'].nunique()}"), ("Average daily demand", f"{daily['Quantity_Sold'].mean():,.1f}")])
    st.caption(f"Coverage: {df['Date'].min():%d %b %Y} – {df['Date'].max():%d %b %Y}. Source: M5 Walmart retail unit-sales data; prices are weekly sell prices where available.")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Retail demand over time", "Total unit sales for the selected M5 food subset")
            line_chart(daily, "Date", "Quantity_Sold", height=280)
    with right:
        with st.container(border=True):
            section_heading("Demand by department")
            bar_chart(df.groupby("Department", as_index=False)["Quantity_Sold"].sum(), "Department", "Quantity_Sold", SUPPORT_COLOR, 280, ".0f")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Top-selling M5 items", "Highest retail unit sales")
            top = df.groupby("Product_ID", as_index=False)["Quantity_Sold"].sum().nlargest(10, "Quantity_Sold")
            bar_chart(top, "Product_ID", "Quantity_Sold", PRIMARY_COLOR, 320, ".0f")
            st.caption("Labels such as `FOODS_3_090` are original M5 item IDs, not food names.")
    with right:
        with st.container(border=True):
            section_heading("Demand by weekday")
            weekday = df.groupby("Weekday", as_index=False)["Quantity_Sold"].sum()
            bar_chart(weekday, "Weekday", "Quantity_Sold", ACCENT_COLOR, 320, ".0f")
    with st.container(border=True):
        section_heading("Retail Demand Forecasting", "Chronological split; lagged and rolling sales features use only earlier observed sales.")
        try:
            tested, _, comparison, metadata = get_m5_forecast_results()
            best = comparison.iloc[0]
            metric_row([("Selected model", metadata["best_model"]), ("MAE", f"{best['MAE']:.2f}"), ("RMSE", f"{best['RMSE']:.2f}"), ("R²", f"{best['R2']:.3f}"), ("Test begins", f"{metadata['cutoff']:%d %b %Y}")])
            st.dataframe(comparison.rename(columns={"R2": "R²"}).round(3), width="stretch", hide_index=True)
            choices = sorted(tested["Product_ID"].unique())
            product = st.selectbox("M5 item ID / store for actual vs predicted retail sales", choices, key="m5_product")
            shown = tested[tested["Product_ID"] == product].groupby("Date")[["Quantity_Sold", "Predicted_Sales"]].sum()
            series_line_chart(shown, [PRIMARY_COLOR, SUPPORT_COLOR], 325)
        except Exception as error:
            st.warning(f"Retail forecast could not be calculated: {error}")


def instacart_insights_page():
    if not INSTACART_DATA_PATH.exists():
        real_data_missing(INSTACART_DATA_PATH, "Instacart Insights")
        return
    df = get_instacart_data()
    page_header("Instacart Market Basket dataset", "Instacart Insights", "Purchase and reorder behavior from the preprocessed public-data subset. The source does not provide calendar dates, quantities, consumption, or waste.")
    order_count = df["Order_ID"].nunique()
    metric_row([("Total orders", f"{order_count:,}"), ("Unique users", f"{df['User_ID'].nunique():,}"), ("Unique products", f"{df['Product_ID'].nunique():,}"), ("Reorder rate", f"{df['Reordered'].mean() * 100:.1f}%"), ("Departments", f"{df['Department'].nunique()}"), ("Aisles", f"{df['Aisle'].nunique()}")])
    st.caption("Derived subset: users with IDs 1–2,000 and their available prior/train order lines. Order day is the source’s day-of-week code (0–6), not a calendar date.")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Top products", "Most frequently purchased product lines")
            top = df.groupby("Product_Name", as_index=False).size().rename(columns={"size": "Purchases"}).nlargest(12, "Purchases")
            bar_chart(top, "Product_Name", "Purchases", PRIMARY_COLOR, 360, ".0f")
    with right:
        with st.container(border=True):
            section_heading("Most reordered products", "Reordered product lines")
            reordered = df[df["Reordered"] == 1].groupby("Product_Name", as_index=False).size().rename(columns={"size": "Reorders"}).nlargest(12, "Reorders")
            bar_chart(reordered, "Product_Name", "Reorders", ALERT_COLOR, 360, ".0f")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Department distribution")
            dept = df.groupby("Department", as_index=False).size().rename(columns={"size": "Purchases"})
            bar_chart(dept, "Department", "Purchases", SUPPORT_COLOR, 360, ".0f")
    with right:
        with st.container(border=True):
            section_heading("Orders by hour", "Distinct orders by source hour-of-day")
            hourly = df.groupby("Order_Hour", as_index=False)["Order_ID"].nunique().rename(columns={"Order_ID": "Orders"})
            bar_chart(hourly, "Order_Hour", "Orders", ACCENT_COLOR, 360, ".0f")
    with st.container(border=True):
        section_heading("Orders by day of week and reorder behavior")
        by_day = df.groupby("Order_Day_Of_Week", as_index=False)["Order_ID"].nunique().rename(columns={"Order_ID": "Orders"})
        bar_chart(by_day, "Order_Day_Of_Week", "Orders", NEUTRAL_COLOR, 230, ".0f")


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
