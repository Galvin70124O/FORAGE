"""Layout pieces shared by every page: headers, source label, KPI row, empty states, formatting."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st


def page_header(title: str, purpose: str, *, pill: str | None = None, detail: str | None = None) -> None:
    """Title and one-line purpose on the left; the data-source pill on the right; an optional detail line."""
    left, right = st.columns([5, 2], vertical_alignment="bottom")
    with left:
        st.title(title)
        st.markdown(f'<p class="fg-purpose">{escape(purpose)}</p>', unsafe_allow_html=True)
    if pill:
        right.markdown(f'<div style="text-align:right"><span class="fg-pill">Source: <b>{escape(pill)}</b></span></div>',
                       unsafe_allow_html=True)
    if detail:
        st.markdown(f'<div class="fg-detail">{escape(detail)}</div>', unsafe_allow_html=True)


def source_label(name: str, detail: str) -> None:
    """Detail line for pages that render their own header (personal pages)."""
    st.markdown(f'<div class="fg-detail">{escape(name)} · {escape(detail)}</div>', unsafe_allow_html=True)


def kpi_row(items: list[tuple]) -> None:
    """Plain figures: (label, value[, help[, delta[, delta_color]]]).

    `delta` is shown with an arrow as well as colour; use delta_color="inverse" when a fall is good
    (waste), "normal" when a rise is good, "off" for neutral changes.
    """
    columns = st.columns(len(items))
    for column, item in zip(columns, items):
        label, value, *rest = item
        help_text = rest[0] if len(rest) > 0 else None
        delta = rest[1] if len(rest) > 1 else None
        delta_color = rest[2] if len(rest) > 2 else "normal"
        column.metric(label, value, delta=delta, delta_color=delta_color, help=help_text)


def section(title: str, note: str | None = None) -> None:
    st.subheader(title)
    if note:
        st.caption(note)


def empty_state(title: str, body: str, *, page: str | None = None, page_label: str | None = None) -> None:
    with st.container(border=True):
        st.markdown(f"**{title}**")
        st.write(body)
        if page:
            st.page_link(page, label=page_label or "Open")


def formula(text: str) -> None:
    st.markdown(f'<div class="fg-formula">{escape(text)}</div>', unsafe_allow_html=True)


def fmt_num(value: float, decimals: int = 2) -> str:
    return "–" if pd.isna(value) else f"{value:,.{decimals}f}"


def fmt_pct(value: float, decimals: int = 1) -> str:
    return "–" if pd.isna(value) else f"{value:.{decimals}f}%"


def fmt_date(value) -> str:
    if pd.isna(value):
        return "–"
    stamp = pd.Timestamp(value)
    return f"{stamp.day} {stamp:%b %Y}"


ROW_PX = 35


def fit_height(rows: int, max_rows: int | None = None) -> int:
    """Pixel height that shows `rows` rows plus the header with no empty padding rows."""
    shown = min(rows, max_rows) if max_rows else rows
    return ROW_PX * (shown + 1) + 3


def table(df: pd.DataFrame, columns: dict | None = None, *, max_rows: int | None = 12, hide_index: bool = True) -> None:
    """st.dataframe sized to its rows; `columns` maps column -> st.column_config entry or a label."""
    config = {}
    for name, spec in (columns or {}).items():
        config[name] = st.column_config.Column(spec) if isinstance(spec, str) else spec
    height = "content" if max_rows is None or len(df) <= max_rows else fit_height(len(df), max_rows)
    st.dataframe(df, column_config=config, hide_index=hide_index, width="stretch", height=height)


def text(label: str, width: str = "medium"):
    return st.column_config.TextColumn(label, width=width)


def number(label: str, fmt: str = "%.2f", help: str | None = None):
    return st.column_config.NumberColumn(label, format=fmt, help=help)


def rupees(label: str, help: str | None = None):
    return st.column_config.NumberColumn(label, format="₹%.0f", help=help)


def percent_bar(label: str, help: str | None = None, max_value: float = 100):
    """Waste % and similar rates as a progress bar with the number printed (not colour alone)."""
    return st.column_config.ProgressColumn(label, format="%.1f%%", min_value=0, max_value=max_value, help=help)


def date(label: str):
    return st.column_config.DateColumn(label, format="D MMM YYYY")


def methods(lines: list[str]) -> None:
    """A collapsed "Methods" note: what the analysis does and how to read it, in plain words."""
    with st.expander("Methods"):
        for line in lines:
            st.markdown(f"- {line}")
