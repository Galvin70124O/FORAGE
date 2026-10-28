"""Fresh Shelf: FORAGE's design tokens, the one stylesheet and the one Plotly template.

Surfaces, text colour and fonts for Streamlit's own widgets live in .streamlit/config.toml.
Everything else is defined here and injected once per run by app.py:

- PALETTE: light and dark tokens. Status colours mean the same in both modes:
  fresh (green), use soon (turmeric), expired / wasted (tomato), neutral (stone).
  Every text colour is at least 4.5:1 against its surface; fills used only as
  marks (turmeric, light stone) are at least 3:1.
- CSS: Streamlit chrome, the pantry-label KPI cards, freshness meters, shelves,
  the waste gauge, demand cards and empty states (see ui/components.py).
- Plotly templates "forage_light" / "forage_dark": transparent background,
  hairline grid, one accent colour, DM Sans; used by every chart in ui/charts.py.
"""

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

VERSION = "3.0"

PALETTE = {
    "light": {
        "bg": "#F6F3EA", "card": "#FFFFFF", "text": "#1F2420", "muted": "#5C625B", "line": "#E4DFD2",
        "line_strong": "#CFC8B6", "brand": "#2E6B4F", "brand_tint": "#E3EFE7", "logo": "#3F8763",
        "fresh": "#2F7D4F", "fresh_text": "#2A6E45", "fresh_tint": "#D5EADC",
        "soon": "#B7791F", "soon_text": "#8A5A12", "soon_tint": "#F5E2BC",
        "gone": "#B84A32", "gone_text": "#9E3D28", "gone_tint": "#F3D3CA",
        "stone": "#77736A", "stone_text": "#6A665D", "stone_tint": "#EFECE4",
        "wood": "#C49A68", "wood_dark": "#8E6A41", "on_brand": "#FFFFFF", "grid": "#ECE8DD", "axis": "#CFC8B6",
        # chart roles
        "accent": "#2E6B4F", "context": "#A7A296", "second": "#B7791F",
        "series": ["#2E6B4F", "#A7A296", "#B7791F"],
        "diverging": ["#B84A32", "#F1EDE2", "#2E6B4F"], "text_on_strong": "#FFFFFF", "surface": "#F6F3EA",
    },
    "dark": {
        "bg": "#161A17", "card": "#1F2420", "text": "#ECE8DD", "muted": "#A9AEA5", "line": "#323A34",
        "line_strong": "#46504A", "brand": "#7CC29E", "brand_tint": "#22382B", "logo": "#3F8763",
        "fresh": "#74C690", "fresh_text": "#86D3A0", "fresh_tint": "#284A35",
        "soon": "#D99A3A", "soon_text": "#E2B160", "soon_tint": "#4A3819",
        "gone": "#EE8A6E", "gone_text": "#F29C83", "gone_tint": "#4C2A21",
        "stone": "#ADA89C", "stone_text": "#ADA89C", "stone_tint": "#2A302B",
        "wood": "#7A5C3C", "wood_dark": "#56402A", "on_brand": "#161A17", "grid": "#2A302B", "axis": "#46504A",
        "accent": "#7CC29E", "context": "#6E6A61", "second": "#D99A3A",
        "series": ["#7CC29E", "#6E6A61", "#D99A3A"],
        "diverging": ["#EE8A6E", "#2A302B", "#7CC29E"], "text_on_strong": "#161A17", "surface": "#161A17",
    },
}
FONT = "DM Sans, system-ui, -apple-system, Segoe UI, sans-serif"
SERIF = "Fraunces, Georgia, 'Times New Roman', serif"
HEIGHTS = {"small": 220, "medium": 280, "large": 340}


def mode() -> str:
    """'dark' or 'light', as reported by the browser for the active Streamlit theme."""
    theme = getattr(st.context, "theme", None)
    return "dark" if theme is not None and getattr(theme, "type", None) == "dark" else "light"


def colors() -> dict:
    return PALETTE[mode()]


# --- Plotly ------------------------------------------------------------------

def _template(name: str) -> go.layout.Template:
    p = PALETTE[name]
    axis = dict(gridcolor=p["grid"], linecolor=p["axis"], tickcolor=p["axis"], zerolinecolor=p["axis"],
                title=dict(font=dict(color=p["muted"], size=12)), tickfont=dict(color=p["muted"], size=11),
                automargin=True, ticks="", showline=False, zeroline=False)
    return go.layout.Template(layout=dict(
        font=dict(family=FONT, color=p["text"], size=12),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        colorway=p["series"],
        xaxis=dict(axis, showgrid=False, showline=True),
        yaxis=dict(axis, showgrid=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title=None,
                    font=dict(color=p["muted"], size=11), bgcolor="rgba(0,0,0,0)"),
        hoverlabel=dict(bgcolor=p["card"], bordercolor=p["line_strong"], font=dict(family=FONT, color=p["text"], size=12)),
        margin=dict(l=8, r=16, t=16, b=8),
        bargap=0.3,
        dragmode=False,
    ))


for _name in PALETTE:
    pio.templates[f"forage_{_name}"] = _template(_name)


def plotly_template() -> str:
    return f"forage_{mode()}"


# --- CSS ---------------------------------------------------------------------

def _variables(p: dict) -> str:
    keys = ["bg", "card", "text", "muted", "line", "line_strong", "brand", "brand_tint", "fresh", "fresh_text",
            "fresh_tint", "soon", "soon_text", "soon_tint", "gone", "gone_text", "gone_tint", "stone", "stone_text",
            "stone_tint", "wood", "wood_dark", "on_brand"]
    return " ".join(f"--fs-{key.replace('_', '-')}: {p[key]};" for key in keys)


CSS = """
/* ---------- Streamlit chrome: no menu, footer or Deploy button; tighter top ---------- */
[data-testid="stMainMenu"], [data-testid="stAppDeployButton"], .stDeployButton, footer,
[data-testid="stDecoration"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2.5rem; padding-bottom: 4rem; max-width: 1232px; }
[data-testid="stVerticalBlock"] { gap: 1rem; }
h1 { letter-spacing: -0.01em; margin: 0 !important; padding: 0 !important; line-height: 1.15 !important; }
h2 { padding-top: 0.5rem !important; }
h3 { padding-bottom: 0 !important; }
hr { margin: 0.5rem 0 !important; border-color: var(--fs-line) !important; }
[data-testid="stCaptionContainer"], .stCaption { color: var(--fs-muted); }

/* ---------- Surfaces: 16 px cards, 1 px warm borders, almost no shadow ---------- */
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stVerticalBlock"][class*="border"] { border-radius: 16px; }
[data-testid="stExpander"] details { border-radius: 16px; border-color: var(--fs-line); background: var(--fs-card); }
[data-testid="stExpander"] summary p { font-weight: 600; }
[data-testid="stAlertContainer"] { border-radius: 12px; }
[data-testid="stDataFrame"], [data-testid="stTable"] { font-variant-numeric: tabular-nums; }
[data-testid="stTabs"] [data-baseweb="tab"] p { font-weight: 600; }
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-primary"] p { color: var(--fs-on-brand) !important; }
[data-testid="stPlotlyChart"] { margin-top: -0.5rem; }

/* ---------- Sidebar: brand, navigation, signed-in user ---------- */
[data-testid="stSidebarHeader"] { padding-bottom: 0.5rem; }
[data-testid="stSidebarNav"] a { border-radius: 10px; min-height: 40px; }
[data-testid="stSidebarNav"] a[aria-current="page"] { background: var(--fs-brand-tint); }
[data-testid="stSidebarNav"] a[aria-current="page"] span { color: var(--fs-brand); font-weight: 600; }
[data-testid="stNavSectionHeader"] span { font-variant: all-small-caps; letter-spacing: 0.1em; font-weight: 600; }
.st-key-fs-account { border-top: 1px solid var(--fs-line); padding-top: 0.75rem; }
.fg-footer { font-size: 0.75rem; color: var(--fs-muted); line-height: 1.6; }

/* ---------- Page header ---------- */
.fs-greeting { font-size: 0.9rem; font-weight: 600; color: var(--fs-brand); margin: 0 0 0.25rem 0;
  font-variant: all-small-caps; letter-spacing: 0.1em; }
.fg-purpose { margin: 0.25rem 0 0 0; font-size: 0.97rem; color: var(--fs-muted); max-width: 48rem; line-height: 1.5; }
.fg-detail { font-size: 0.8rem; color: var(--fs-muted); margin-top: 0.25rem; }
.fg-pill { display: inline-block; float: right; margin-top: 0.5rem; padding: 0.25rem 0.75rem; border-radius: 999px;
  border: 1px solid var(--fs-line-strong); background: var(--fs-card); font-size: 0.78rem; font-weight: 500;
  white-space: nowrap; color: var(--fs-muted); }
.fg-pill b { font-weight: 600; color: var(--fs-text); }
.fg-formula { font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 0.85rem;
  color: var(--fs-muted); }
.fs-chart-title { font-family: Fraunces, Georgia, serif; font-weight: 600; font-size: 1.05rem; line-height: 1.3;
  margin: 0; color: var(--fs-text); }
.fs-chart-sub { font-size: 0.8rem; color: var(--fs-muted); margin: 0.15rem 0 0 0; }

/* ---------- Action list ---------- */
.fg-action { padding: 0.75rem 0; border-bottom: 1px solid var(--fs-line); }
.fg-action:last-child { border-bottom: none; }
.fg-action-title { font-weight: 600; }
.fg-action-why { font-size: 0.85rem; color: var(--fs-muted); }
.fg-tag { display: inline-block; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.06em; padding: 0.05rem 0.5rem;
  border-radius: 6px; border: 1.5px solid currentColor; margin-right: 0.5rem; vertical-align: 1px;
  font-variant: all-small-caps; color: var(--fs-stone-text); }
.fg-tag.fs-gone { color: var(--fs-gone-text); } .fg-tag.fs-soon { color: var(--fs-soon-text); }
.fg-tag.fs-fresh { color: var(--fs-fresh-text); }

/* ---------- 1. Pantry-label KPI cards ---------- */
.fs-labels { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }
.fs-label { position: relative; background: var(--fs-card); border: 1px solid var(--fs-line-strong); border-radius: 16px;
  padding: 14px 18px 14px; box-shadow: inset 0 0 0 4px var(--fs-card), inset 0 0 0 5px var(--fs-line); min-width: 0; }
.fs-label-name { font-variant: all-small-caps; letter-spacing: 0.09em; font-weight: 600; font-size: 0.95rem;
  color: var(--fs-muted); line-height: 1.2; }
.fs-label-value { font-family: Fraunces, Georgia, serif; font-weight: 600; font-size: 1.85rem; line-height: 1.15;
  margin-top: 4px; color: var(--fs-text); font-variant-numeric: tabular-nums lining-nums; overflow-wrap: anywhere; }
.fs-label-value.fs-small { font-size: 1.3rem; }
.fs-label-compare { font-size: 0.82rem; color: var(--fs-muted); margin-top: 6px; font-variant-numeric: tabular-nums; }
.fs-label-compare b { font-weight: 700; }
.fs-good { color: var(--fs-fresh-text); } .fs-bad { color: var(--fs-gone-text); } .fs-flat { color: var(--fs-stone-text); }
.fs-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: -4px; }
.fs-chip { font-size: 0.8rem; color: var(--fs-muted); background: var(--fs-card); border: 1px solid var(--fs-line);
  border-radius: 999px; padding: 2px 10px; font-variant-numeric: tabular-nums; }
.fs-chip b { color: var(--fs-text); font-weight: 600; }

/* ---------- 2. Freshness meter ---------- */
.fs-meter { position: relative; height: 20px; border-radius: 999px; background: var(--fs-stone-tint); overflow: hidden;
  margin-top: 8px; }
.fs-meter-fill { position: absolute; inset: 0 auto 0 0; border-radius: 999px; }
.fs-meter-fill.fs-fresh { background: var(--fs-fresh-tint); box-shadow: inset -3px 0 0 var(--fs-fresh); }
.fs-meter-fill.fs-soon { background: var(--fs-soon-tint); box-shadow: inset -3px 0 0 var(--fs-soon); }
.fs-meter-fill.fs-gone { background: var(--fs-gone-tint); box-shadow: inset -3px 0 0 var(--fs-gone); }
.fs-meter-text { position: relative; font-size: 0.72rem; font-weight: 700; line-height: 20px; padding: 0 9px;
  color: var(--fs-text); white-space: nowrap; font-variant-numeric: tabular-nums; }

/* ---------- 3. Shelves ---------- */
.fs-shelf { margin: 4px 0 8px 0; }
.fs-shelf-head { display: flex; align-items: baseline; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
.fs-shelf-title { font-family: Fraunces, Georgia, serif; font-weight: 600; font-size: 1.1rem; margin: 0; }
.fs-shelf-count { font-size: 0.75rem; font-weight: 700; border-radius: 999px; padding: 1px 9px; background: var(--fs-stone-tint);
  color: var(--fs-stone-text); font-variant-numeric: tabular-nums; }
.fs-shelf-note { font-size: 0.82rem; color: var(--fs-muted); }
.fs-shelf-row { display: grid; grid-template-columns: repeat(auto-fill, minmax(168px, 1fr)); gap: 14px;
  align-items: end; padding: 8px 6px 10px; }
.fs-shelf-empty { font-size: 0.9rem; color: var(--fs-muted); padding: 10px 6px 12px; font-style: italic; }
.fs-plank { position: relative; height: 9px; border-radius: 3px; margin: 0 0 18px 0;
  background: linear-gradient(180deg, var(--fs-wood) 0%, var(--fs-wood) 55%, var(--fs-wood-dark) 100%); }
.fs-plank::before, .fs-plank::after { content: ""; position: absolute; top: 9px; width: 10px; height: 8px;
  background: var(--fs-wood-dark); clip-path: polygon(0 0, 100% 0, 50% 100%); }
.fs-plank::before { left: 7%; } .fs-plank::after { right: 7%; }
.fs-jar { position: relative; background: var(--fs-card); border: 1px solid var(--fs-line-strong); border-radius: 12px;
  padding: 12px 12px 10px; margin-top: 6px; box-shadow: inset 0 0 0 3px var(--fs-card), inset 0 0 0 4px var(--fs-line); }
.fs-jar::before { content: ""; position: absolute; left: 22%; right: 22%; top: -6px; height: 6px; border-radius: 4px 4px 0 0;
  background: var(--fs-stone); }
.fs-jar.fs-fresh::before { background: var(--fs-fresh); } .fs-jar.fs-soon::before { background: var(--fs-soon); }
.fs-jar.fs-gone::before { background: var(--fs-gone); }
.fs-jar-name { font-weight: 600; font-size: 0.95rem; line-height: 1.25; overflow-wrap: anywhere; }
.fs-jar-qty { font-size: 0.8rem; color: var(--fs-muted); font-variant-numeric: tabular-nums; }

/* ---------- 4. Waste-bin gauge ---------- */
.fs-gauge { background: var(--fs-card); border: 1px solid var(--fs-line); border-radius: 16px; padding: 16px 18px;
  text-align: center; height: 100%; }
.fs-gauge svg { width: 100%; max-width: 260px; height: auto; display: block; margin: 4px auto 0; }
.fs-gauge-name { font-variant: all-small-caps; letter-spacing: 0.09em; font-weight: 600; font-size: 0.95rem;
  color: var(--fs-muted); text-align: left; }
.fs-gauge-sentence { font-size: 0.95rem; margin: 6px 0 0 0; line-height: 1.4; }
.fs-gauge-note { font-size: 0.78rem; color: var(--fs-muted); margin-top: 4px; }

/* ---------- 5. Demand cards ---------- */
.fs-demands { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }
.fs-demand { position: relative; background: var(--fs-card); border: 1px solid var(--fs-line-strong); border-radius: 16px;
  padding: 14px 16px; box-shadow: inset 0 0 0 4px var(--fs-card), inset 0 0 0 5px var(--fs-line); min-width: 0; }
.fs-demand-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 8px; }
.fs-demand-name { font-weight: 600; font-size: 1rem; line-height: 1.25; overflow-wrap: anywhere; }
.fs-demand-value { font-family: Fraunces, Georgia, serif; font-weight: 600; font-size: 1.6rem; line-height: 1.1;
  margin-top: 8px; font-variant-numeric: tabular-nums lining-nums; }
.fs-demand-value span { font-family: DM Sans, system-ui, sans-serif; font-size: 0.85rem; font-weight: 500; color: var(--fs-muted); }
.fs-demand-what { font-size: 0.78rem; color: var(--fs-muted); }
.fs-confidence { display: flex; align-items: center; gap: 6px; font-size: 0.8rem; margin-top: 10px; color: var(--fs-muted); }
.fs-dots { display: inline-flex; gap: 3px; }
.fs-dots i { width: 7px; height: 7px; border-radius: 50%; background: var(--fs-stone-tint); border: 1px solid var(--fs-line-strong); }
.fs-dots i.on { background: var(--fs-brand); border-color: var(--fs-brand); }
.fs-demand-note { font-size: 0.8rem; color: var(--fs-muted); margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--fs-line);
  line-height: 1.4; }
.fs-stamp { display: inline-block; flex: none; border: 2px solid currentColor; border-radius: 6px; padding: 1px 8px 2px;
  font-variant: all-small-caps; letter-spacing: 0.1em; font-weight: 700; font-size: 0.9rem; line-height: 1.3;
  transform: rotate(-3deg); box-shadow: inset 0 0 0 2px var(--fs-card), inset 0 0 0 3px currentColor; white-space: nowrap; }
.fs-stamp.fs-more { color: var(--fs-fresh-text); } .fs-stamp.fs-less { color: var(--fs-gone-text); }
.fs-stamp.fs-same { color: var(--fs-stone-text); }

/* ---------- 6. Empty states ---------- */
[class*="st-key-fs-empty"] { text-align: center; align-items: center; border-style: dashed !important; }
.fs-empty svg { width: 56px; height: 56px; display: block; margin: 4px auto 6px; }
.fs-empty-title { font-family: Fraunces, Georgia, serif; font-weight: 600; font-size: 1.15rem; margin: 0; }
.fs-empty-body { color: var(--fs-muted); margin: 4px auto 0; max-width: 34rem; line-height: 1.5; }

/* ---------- Touch targets of at least 44 px ---------- */
.stButton button, .stDownloadButton button, .stFormSubmitButton button, .stLinkButton a { min-height: 44px; }
[data-testid="stPageLink"] a { min-height: 44px; display: flex; align-items: center; }
[data-baseweb="input"], [data-baseweb="select"] > div { min-height: 44px; }
[data-testid="stCheckbox"] label { min-height: 44px; align-items: center; }

/* ---------- Phone width: one column, no sideways scrolling ---------- */
@media (max-width: 640px) {
  .block-container { padding-left: 1rem; padding-right: 1rem; padding-top: 3.5rem; }
  .fg-pill { float: none; margin: 0.5rem 0 0 0; }
  h1 { font-size: 1.6rem !important; }
  .fs-labels, .fs-demands { grid-template-columns: 1fr; }
  .fs-shelf-row { grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }
  .fs-label-value { font-size: 1.6rem; }
  [data-testid="stElementToolbar"] { display: none; }
}
"""

KITCHEN_CSS = """
/* Kitchen mode: readable text and touch targets of at least 44 px. */
.block-container p, .block-container li, .block-container label p { font-size: 1.02rem; }
[class*="st-key-fg-tiles"] button { min-height: 56px; min-width: 104px; font-size: 1.02rem; padding: 0 1rem; }
[class*="st-key-fg-levels"] button { min-height: 64px; min-width: 120px; font-size: 1.05rem; flex: 1 1 40%; }
[class*="st-key-fg-tiles"], [class*="st-key-fg-levels"] { gap: 0.5rem; }
[data-testid="stButtonGroup"] button { min-height: 44px; padding: 0 1rem; font-size: 1rem; }
.fg-message { padding: 0.75rem 1rem; border: 1px solid var(--fs-line); background: var(--fs-card); border-radius: 12px; margin: 0; }
.fg-message b { font-weight: 600; }
.fg-list { margin: 0; padding-left: 1.2rem; }
.fg-list li { padding: 0.2rem 0; }
@media (max-width: 640px) {
  [class*="st-key-fg-tiles"] button { flex: 1 1 calc(33% - 0.5rem); min-width: 96px; }
}
"""


def apply_styles(*, kitchen: bool = False) -> None:
    """Inject the stylesheet (called once per run from app.py), with the tokens of the active mode."""
    css = f":root {{ {_variables(colors())} }}\n{CSS}" + (KITCHEN_CSS if kitchen else "")
    st.html(f"<style>{css}</style>")
