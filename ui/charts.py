"""Plotly chart builders shared by every page, drawn with the FORAGE template (ui.theme).

Rules: one y-axis per chart; axis titles carry units; hover on every mark;
ONE accent colour for the series or category that carries the finding and
stone grey for context; values labelled directly where it helps; titles that
state the finding (rendered as text above the chart so they wrap on a phone);
standard heights (ui.theme.HEIGHTS). Number formats are d3 formats (",.2f").
"""

from __future__ import annotations

from html import escape

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui.theme import HEIGHTS, colors, plotly_template

CONFIG = {"displayModeBar": False, "responsive": True, "scrollZoom": False}


def tip(field: str, title: str, fmt: str | None = ".2f") -> dict:
    """Hover entry: quantitative with a number format, or text when fmt is None."""
    return {"field": field, "title": title, "fmt": fmt}


def _tip_spec(entry) -> dict:
    """Accept tip() dicts and Altair-style "Field:N" / "Field" strings."""
    if isinstance(entry, dict):
        return entry
    field, _, kind = str(entry).partition(":")
    return {"field": field, "title": field.replace("_", " "), "fmt": None if kind in ("N", "O", "") else ",.2f"}


def _hover(specs: list[dict], first_index: int = 0) -> str:
    """Hover lines for customdata columns starting at `first_index`."""
    lines = []
    for i, spec in enumerate(specs, start=first_index):
        fmt = f":{spec['fmt']}" if spec.get("fmt") else ""
        lines.append(f"{escape(spec['title'])}: %{{customdata[{i}]{fmt}}}")
    return "<br>".join(lines)


def _heading(title: str | None, subtitle: str | None) -> None:
    if title or subtitle:
        html = (f'<p class="fs-chart-title">{escape(title)}</p>' if title else "") + \
               (f'<p class="fs-chart-sub">{escape(subtitle)}</p>' if subtitle else "")
        st.html(html)


def _show(fig: go.Figure, height: int, title: str | None = None, subtitle: str | None = None) -> None:
    _heading(title, subtitle)
    fig.update_layout(template=plotly_template(), height=height, paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, config=CONFIG, theme=None, width="stretch")


def bar(data: pd.DataFrame, category: str, value: str, *, value_title: str, category_title: str | None = None,
        slot: int = 0, height: int | None = None, value_format: str = ",.2f", sort: str | list = "-x",
        horizontal: bool = True, extra_tooltip: list | None = None, highlight: list | str | None = "top",
        labels: bool | None = None, title: str | None = None, subtitle: str | None = None) -> None:
    """Bar chart in one accent colour for the highlighted bars and grey for the rest.

    highlight: "top" (largest value), "all", None (all accent) or a list of categories.
    Bars carry their value as a direct label when there are at most 15 of them.
    """
    palette = colors()
    data = data.copy()
    data[category] = data[category].astype(str)
    if highlight == "top":
        chosen = [data.loc[data[value].idxmax(), category]] if not data.empty else []
    elif highlight in (None, "all"):
        chosen = list(data[category])
    else:
        chosen = [str(c) for c in highlight]
    if isinstance(sort, str) and sort.lstrip("-") in ("x", "y"):
        order = data.sort_values(value, ascending=not sort.startswith("-"))[category].tolist()
    elif isinstance(sort, str):
        order = sorted(data[category].unique(), reverse=sort == "descending")
    else:
        order = [str(c) for c in sort]
    data = data.set_index(category).loc[[c for c in order if c in set(data[category])]].reset_index()
    bar_colors = [palette["accent"] if c in chosen else palette["context"] for c in data[category]]
    show_labels = labels if labels is not None else len(data) <= 15
    extras = [_tip_spec(e) for e in (extra_tooltip or [])]
    custom = data[[e["field"] for e in extras]].to_numpy() if extras else None
    name = escape(category_title or category.replace("_", " "))
    values = data[value]
    span = (values.max() - min(values.min(), 0)) if len(values) else 1
    pad = (span or 1) * (0.16 if show_labels else 0.04)
    value_range = [min(values.min(), 0) - (pad if values.min() < 0 else 0), max(values.max(), 0) + pad] if len(values) else None
    common = dict(marker=dict(color=bar_colors, line=dict(width=0)), customdata=custom, cliponaxis=False,
                  texttemplate=f"%{{{'x' if horizontal else 'y'}:{value_format}}}" if show_labels else None,
                  textposition="outside", textfont=dict(color=palette["muted"], size=11))
    if horizontal:
        hover = f"<b>%{{y}}</b><br>{escape(value_title)}: %{{x:{value_format}}}"
        fig = go.Figure(go.Bar(x=values, y=data[category], orientation="h", **common,
                               hovertemplate=hover + ("<br>" + _hover(extras) if extras else "") + "<extra></extra>"))
        fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(data[category].tolist())), title=None,
                         showgrid=False, ticksuffix="  ")
        fig.update_xaxes(title=value_title, range=value_range, showgrid=True, gridcolor=palette["grid"], showline=False,
                         tickformat=value_format.replace("+", ""))
        height = height or max(HEIGHTS["small"], 26 * len(data) + 60)
    else:
        hover = f"<b>{name}: %{{x}}</b><br>{escape(value_title)}: %{{y:{value_format}}}"
        fig = go.Figure(go.Bar(x=data[category], y=values, **common,
                               hovertemplate=hover + ("<br>" + _hover(extras) if extras else "") + "<extra></extra>"))
        fig.update_xaxes(type="category", categoryorder="array", categoryarray=data[category].tolist(),
                         title=category_title)
        fig.update_yaxes(title=value_title, range=value_range, tickformat=value_format.replace("+", ""))
        height = height or HEIGHTS["medium"]
    fig.update_layout(showlegend=False, bargap=0.3)
    _show(fig, height, title, subtitle)


def _x_kind(x_type: str) -> str:
    return {"T": "date", "O": "category", "Q": "linear"}.get(x_type, "-")


def line(data: pd.DataFrame, x: str, y: str, *, y_title: str, x_title: str | None = None,
         series: str | None = None, order: list[str] | None = None, slot: int = 0, height: int | None = None,
         y_format: str = ",.2f", x_type: str = "T", dashed: list[str] | None = None,
         zero: bool = True, x_format: str | None = None, highlight: str | None = None,
         title: str | None = None, subtitle: str | None = None, label_last: bool = False) -> None:
    """Line chart. With `series`, `highlight` (default: the first in `order`) is drawn in the accent
    colour and the others in grey; dashed series also differ in stroke, so colour is never the only cue."""
    palette = colors()
    x_hover = f"%{{x|{x_format}}}" if x_format and x_type == "T" else "%{x}"
    fig = go.Figure()
    if series:
        domain = order or sorted(data[series].unique())
        focus = highlight or domain[0]
        for name in domain:
            part = data[data[series] == name].sort_values(x)
            fig.add_trace(go.Scatter(
                x=part[x], y=part[y], name=str(name), mode="lines",
                line=dict(color=palette["accent"] if name == focus else palette["context"], width=2.2 if name == focus else 1.8,
                          dash="dash" if name in (dashed or []) else "solid"),
                hovertemplate=f"{escape(str(name))}: %{{y:{y_format}}}<extra></extra>"))
        fig.update_layout(showlegend=True, hovermode="x unified")
    else:
        part = data.sort_values(x)
        fig.add_trace(go.Scatter(x=part[x], y=part[y], mode="lines+markers", line=dict(color=palette["accent"], width=2.4),
                                 marker=dict(size=5, color=palette["accent"]), fill="tozeroy" if zero else None,
                                 fillcolor=_alpha(palette["accent"], 0.07),
                                 hovertemplate=f"<b>{x_hover}</b><br>{escape(y_title)}: %{{y:{y_format}}}<extra></extra>"))
        fig.update_layout(showlegend=False, hovermode="closest")
        if label_last and not part.empty:
            last = part.iloc[-1]
            fig.add_annotation(x=last[x], y=last[y], text=f"<b>{_fmt(last[y], y_format)}</b>", showarrow=False,
                               xanchor="left", xshift=8, font=dict(color=palette["text"], size=12))
            fig.add_trace(go.Scatter(x=[last[x]], y=[last[y]], mode="markers", hoverinfo="skip",
                                     marker=dict(size=10, color=palette["accent"], line=dict(width=2, color=palette["card"]))))
    fig.update_xaxes(title=x_title, type=_x_kind(x_type), tickformat=x_format if x_type == "T" else None)
    fig.update_yaxes(title=y_title, rangemode="tozero" if zero else "normal", tickformat=y_format.replace("+", ""))
    if label_last and not series:
        fig.update_layout(margin=dict(r=56))
    _show(fig, height or HEIGHTS["medium"], title, subtitle)


def _alpha(hex_color: str, alpha: float) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({r},{g},{b},{alpha})"


def _fmt(value: float, d3: str) -> str:
    """The few d3 number formats used here, in Python (for direct labels)."""
    spec = d3.replace("~", "")
    try:
        return format(value, spec)
    except ValueError:
        return f"{value:,.2f}"


def histogram(data: pd.DataFrame, value: str, *, value_title: str, bins: int = 30, slot: int = 0,
              height: int | None = None, title: str | None = None, subtitle: str | None = None,
              weight: str | None = None, count_title: str = "Records") -> None:
    """Histogram of raw values, or of pre-counted values when `weight` names the count column."""
    palette = colors()
    trace = go.Histogram(x=data[value], y=data[weight] if weight else None, histfunc="sum" if weight else "count",
                         nbinsx=bins, marker=dict(color=palette["accent"], line=dict(width=1, color=palette["bg"])),
                         hovertemplate=f"{escape(value_title)}: %{{x}}<br>{escape(count_title)}: %{{y:,}}<extra></extra>")
    fig = go.Figure(trace)
    fig.update_xaxes(title=value_title)
    fig.update_yaxes(title=count_title)
    fig.update_layout(showlegend=False, bargap=0.04)
    _show(fig, height or HEIGHTS["medium"], title, subtitle)


def scatter(data: pd.DataFrame, x: str, y: str, *, x_title: str, y_title: str, label: str,
            log_x: bool = False, height: int | None = None, tooltip: list | None = None, label_extremes: int = 3,
            title: str | None = None, subtitle: str | None = None) -> None:
    """Scatter with direct labels only on the highest and lowest `label_extremes` points; hover shows the rest."""
    palette = colors()
    specs = [_tip_spec(e) for e in (tooltip or [label, f"{x}:Q", f"{y}:Q"])]
    custom = data[[s["field"] for s in specs]].to_numpy()
    ranked = data[y].rank(method="first")
    labelled = data[(ranked <= label_extremes) | (ranked > len(data) - label_extremes)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=data[x], y=data[y], mode="markers", customdata=custom,
                             marker=dict(size=11, color=palette["accent"], opacity=0.85,
                                         line=dict(width=1, color=palette["card"])),
                             hovertemplate=_hover(specs) + "<extra></extra>"))
    fig.add_trace(go.Scatter(x=labelled[x], y=labelled[y], mode="text", text=labelled[label], textposition="middle right",
                             textfont=dict(color=palette["muted"], size=11), hoverinfo="skip", cliponaxis=False))
    fig.update_xaxes(title=x_title, type="log" if log_x else "linear", showgrid=True, gridcolor=palette["grid"])
    fig.update_yaxes(title=y_title)
    fig.update_layout(showlegend=False, margin=dict(r=72))
    _show(fig, height or HEIGHTS["large"], title, subtitle)


def _mix(start: str, end: str, share: float) -> str:
    a = [int(start[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(end[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * share):02x}" for x, y in zip(a, b))


def diverging_color(r: float) -> str:
    """Neutral at r = 0, herb green towards +1 and tomato towards -1, interpolated from the neutral midpoint."""
    negative, middle, positive = colors()["diverging"]
    return middle if pd.isna(r) else _mix(middle, positive if r >= 0 else negative, min(abs(r), 1.0))


def correlation_heatmap(corr: pd.DataFrame, *, height: int | None = None, title: str | None = None) -> None:
    """Diverging heatmap: green = positive, tomato = negative, neutral at r = 0; every cell is labelled."""
    palette = colors()
    negative, middle, positive = palette["diverging"]
    order = list(corr.columns)
    z = corr.loc[order, order]
    text = [[("" if pd.isna(v) else f"{v:.2f}") for v in row] for row in z.to_numpy()]
    text_colors = [[palette["text_on_strong"] if (pd.notna(v) and abs(v) > 0.6) else palette["text"] for v in row]
                   for row in z.to_numpy()]
    fig = go.Figure(go.Heatmap(
        z=z.to_numpy(), x=order, y=order, zmin=-1, zmax=1, xgap=2, ygap=2,
        colorscale=[[0, negative], [0.5, middle], [1, positive]], showscale=False,
        hovertemplate="%{y} with %{x}<br>r = %{z:.2f}<extra></extra>"))
    for i, row in enumerate(order):
        for j, column in enumerate(order):
            if text[i][j]:
                fig.add_annotation(x=column, y=row, text=text[i][j], showarrow=False,
                                   font=dict(size=11, color=text_colors[i][j]))
    fig.update_xaxes(showgrid=False, showline=False, tickangle=-35)
    fig.update_yaxes(showgrid=False, autorange="reversed")
    _show(fig, height or 380, title)
