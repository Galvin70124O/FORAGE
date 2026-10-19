"""Light/dark palettes and the injected stylesheet."""


import streamlit as st





PRIMARY_COLOR = "consumption"

ACCENT_COLOR = "lime"

ALERT_COLOR = "waste"

NEUTRAL_COLOR = "neutral"

SUPPORT_COLOR = "teal"

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
