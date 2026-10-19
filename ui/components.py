"""Layout pieces shared by every page: headers, source label, KPI row, empty states, formatting."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st


def page_header(title: str, purpose: str) -> None:
    st.title(title)
    st.markdown(f'<p class="fg-purpose">{escape(purpose)}</p>', unsafe_allow_html=True)


def source_label(name: str, detail: str) -> None:
    st.markdown(f'<div class="fg-source">Data source: <b>{escape(name)}</b> · {escape(detail)}</div>',
                unsafe_allow_html=True)


def kpi_row(items: list[tuple]) -> None:
    """Plain figures: (label, value) or (label, value, help)."""
    columns = st.columns(len(items))
    for column, item in zip(columns, items):
        label, value, *rest = item
        column.metric(label, value, help=rest[0] if rest else None)


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


def date(label: str):
    return st.column_config.DateColumn(label, format="D MMM YYYY")
