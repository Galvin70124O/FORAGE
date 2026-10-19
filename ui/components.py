"""Small layout components reused across pages."""

from html import escape

import pandas as pd
import streamlit as st



from ui.theme import THEMES, current_theme


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


def section_heading(title, note=None):
    st.markdown(f'<div class="chart-title">{title}</div>', unsafe_allow_html=True)
    if note:
        st.markdown(f'<div class="chart-note">{note}</div>', unsafe_allow_html=True)


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


def real_data_missing(path, label):
    page_header("Real data", label, "This page uses a separate, preprocessed public dataset and never changes My Data or the FORAGE demo dataset.")
    st.info("Run `python src/real_data_processor.py` from the project root to create the local analytical extract.")
