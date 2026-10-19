"""Design tokens, the registered Altair themes and the small amount of CSS Streamlit's theme cannot express.

Surfaces, text, the accent and fonts live in .streamlit/config.toml. Charts use
one registered Altair theme per mode ("forage_light" / "forage_dark"): one
accent colour for the series that matters, grey for context, hairline grids,
the same font and heights everywhere. Contrast of every text colour against its
surface is at least WCAG AA (4.5:1); chart marks are at least 3:1.
"""

import altair as alt
import streamlit as st

VERSION = "2.0"

PALETTE = {
    "light": {
        "accent": "#2a78d6", "context": "#a3a29d", "second": "#d9662b",
        "series": ["#2a78d6", "#a3a29d", "#d9662b"],
        "text": "#1b1b19", "muted": "#5f5e5a", "grid": "#e8e7e2", "axis": "#c9c8c1",
        "surface": "#fbfbfa", "diverging": ["#d9534f", "#efeeea", "#2a78d6"], "text_on_strong": "#ffffff",
    },
    "dark": {
        "accent": "#5598e7", "context": "#6f6e69", "second": "#e07a45",
        "series": ["#5598e7", "#6f6e69", "#e07a45"],
        "text": "#ecebe7", "muted": "#a3a29d", "grid": "#2a2a27", "axis": "#46453f",
        "surface": "#171716", "diverging": ["#e06c69", "#34342f", "#5598e7"], "text_on_strong": "#ffffff",
    },
}
FONT = "Inter, system-ui, -apple-system, Segoe UI, sans-serif"
HEIGHTS = {"small": 220, "medium": 280, "large": 340}


def _theme(mode: str) -> dict:
    p = PALETTE[mode]
    axis = {"labelColor": p["muted"], "titleColor": p["muted"], "labelFont": FONT, "titleFont": FONT,
            "labelFontSize": 11, "titleFontSize": 11, "titleFontWeight": 500, "gridColor": p["grid"],
            "domainColor": p["axis"], "tickColor": p["axis"], "labelPadding": 6, "titlePadding": 10}
    return {"config": {
        "background": "transparent",
        "font": FONT,
        "view": {"stroke": None},
        "axis": axis,
        "axisX": {"grid": False},
        "axisY": {"domain": False, "ticks": False},
        "legend": {"labelColor": p["muted"], "titleColor": p["muted"], "labelFont": FONT, "labelFontSize": 11,
                   "orient": "top", "direction": "horizontal", "symbolType": "stroke"},
        "title": {"color": p["text"], "font": FONT, "fontSize": 13, "fontWeight": 600, "anchor": "start",
                  "subtitleColor": p["muted"], "subtitleFont": FONT, "subtitleFontSize": 11, "offset": 12},
        "range": {"category": p["series"]},
        "bar": {"color": p["accent"], "cornerRadiusEnd": 3},
        "line": {"color": p["accent"], "strokeWidth": 2},
        "point": {"color": p["accent"]},
        "text": {"color": p["muted"], "font": FONT, "fontSize": 11},
        "header": {"labelColor": p["muted"], "titleColor": p["muted"]},
    }}


for _mode in ("light", "dark"):
    alt.theme.register(f"forage_{_mode}", enable=False)(lambda m=_mode: _theme(m))


def mode() -> str:
    """'dark' or 'light', as reported by the browser for the active Streamlit theme."""
    theme = getattr(st.context, "theme", None)
    return "dark" if theme is not None and getattr(theme, "type", None) == "dark" else "light"


def colors() -> dict:
    return PALETTE[mode()]


def altair_theme() -> str:
    return f"forage_{mode()}"


CSS = """
<style>
/* Layout: ~1200 px content width, 8 px spacing grid. */
.block-container { padding-top: 3.5rem; padding-bottom: 4rem; max-width: 1232px; }
[data-testid="stVerticalBlock"] { gap: 1rem; }
h1 { letter-spacing: -0.015em; margin: 0 !important; padding: 0 !important; }
h2 { letter-spacing: -0.005em; padding-top: 0.5rem !important; }
h3 { padding-bottom: 0 !important; }
hr { margin: 0.5rem 0 !important; }
.fg-purpose { margin: 0.25rem 0 0 0; font-size: 0.97rem; opacity: 0.86; max-width: 48rem; line-height: 1.5; }
.fg-detail { font-size: 0.8rem; opacity: 0.72; margin-top: 0.25rem; }
.fg-pill { display: inline-block; float: right; margin-top: 0.5rem; padding: 0.25rem 0.75rem; border-radius: 999px;
  border: 1px solid var(--fg-border); font-size: 0.78rem; font-weight: 500; white-space: nowrap; }
.fg-pill b { font-weight: 600; }
.fg-brand { font-weight: 700; letter-spacing: 0.16em; font-size: 0.95rem; margin: 0; }
.fg-tagline { font-size: 0.8rem; opacity: 0.72; margin: 0.25rem 0 0.5rem 0; }
.fg-footer { font-size: 0.75rem; opacity: 0.72; line-height: 1.6; }
.fg-formula { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.85rem;
  opacity: 0.9; }
.fg-action { padding: 0.5rem 0; border-bottom: 1px solid var(--fg-border); }
.fg-action:last-child { border-bottom: none; }
.fg-action-title { font-weight: 600; }
.fg-action-why { font-size: 0.85rem; opacity: 0.8; }
.fg-tag { display: inline-block; font-size: 0.7rem; font-weight: 600; letter-spacing: 0.02em; padding: 0.05rem 0.5rem;
  border-radius: 999px; border: 1px solid var(--fg-border); margin-right: 0.5rem; vertical-align: 1px; }
[data-testid="stMetricValue"] { font-size: 1.65rem; font-weight: 600; }
[data-testid="stMetricLabel"] p { font-size: 0.8rem; opacity: 0.8; }
/* Hide only the Deploy button, the footer and Streamlit branding; the main menu (theme switch) stays. */
[data-testid="stAppDeployButton"], .stDeployButton, footer, [data-testid="stDecoration"] { display: none !important; }
@media (max-width: 640px) {
  .block-container { padding-left: 1rem; padding-right: 1rem; padding-top: 4.5rem; }
  .fg-pill { float: none; margin: 0.5rem 0 0 0; }
  [data-testid="stMetricValue"] { font-size: 1.35rem; }
  h1 { font-size: 1.5rem !important; }
}
</style>
"""


def apply_styles() -> None:
    border = "#e1e0d9" if mode() == "light" else "#33332f"
    st.markdown(CSS.replace("<style>", f"<style>:root {{ --fg-border: {border}; }}", 1), unsafe_allow_html=True)
