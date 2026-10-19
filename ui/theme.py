"""Colour tokens for charts and the small amount of CSS Streamlit's theme cannot express.

Surfaces, text, the accent and the categorical chart colours live in
.streamlit/config.toml. The values here repeat the chart colours so Altair
specs can name a series explicitly (for example, waste is always slot 2).
The three categorical slots were checked with the dataviz palette validator:
all pairs clear the colour-vision-deficiency threshold in both modes.
"""

import streamlit as st

PALETTE = {
    "light": {
        "series": ["#2a78d6", "#eb6834", "#1baf7a"],
        "muted": "#898781",
        "diverging": ["#e34948", "#f0efec", "#2a78d6"],
        "text_on_strong": "#ffffff",
        "text": "#1b1b19",
    },
    "dark": {
        "series": ["#3987e5", "#d95926", "#199e70"],
        "muted": "#898781",
        "diverging": ["#e66767", "#383835", "#3987e5"],
        "text_on_strong": "#ffffff",
        "text": "#ecebe7",
    },
}


def mode() -> str:
    """'dark' or 'light', as reported by the browser for the active Streamlit theme."""
    theme = getattr(st.context, "theme", None)
    return "dark" if theme is not None and getattr(theme, "type", None) == "dark" else "light"


def colors() -> dict:
    return PALETTE[mode()]


CSS = """
<style>
.block-container { padding-top: 2.25rem; padding-bottom: 3rem; max-width: 1240px; }
h1 { letter-spacing: -0.015em; margin-bottom: 0 !important; padding-bottom: 0.15rem !important; }
h2, h3 { letter-spacing: -0.005em; }
.fg-purpose { margin: 0.1rem 0 0.35rem 0; font-size: 0.98rem; opacity: 0.82; max-width: 52rem; }
.fg-source { font-size: 0.82rem; opacity: 0.68; margin-bottom: 1.4rem; }
.fg-source b { font-weight: 600; opacity: 1; }
.fg-brand { font-weight: 700; letter-spacing: 0.14em; font-size: 0.95rem; margin: 0.2rem 0 0 0; }
.fg-tagline { font-size: 0.8rem; opacity: 0.65; margin: 0.1rem 0 1rem 0; }
.fg-formula { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.86rem; }
[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: 600; }
[data-testid="stMetricLabel"] p { font-size: 0.82rem; opacity: 0.75; }
[data-testid="stSidebarNav"] { display: none; }
</style>
"""


def apply_styles() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
