"""Altair chart builders shared by every page, rendered with the registered FORAGE theme.

Rules: one y-axis per chart; axis titles carry units; tooltips on every mark;
ONE accent colour for the series or category that carries the finding and
grey for context; values labelled directly where it helps; titles that state
the finding when the caller supplies one; standard heights (ui.theme.HEIGHTS).
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from ui.theme import HEIGHTS, altair_theme, colors


def _show(chart, height: int, title: str | None = None, subtitle: str | None = None) -> None:
    if title:
        chart = chart.properties(title=alt.Title(title, subtitle=subtitle or alt.Undefined))
    with alt.theme.enable(altair_theme()):
        st.altair_chart(chart.properties(height=height), width="stretch", theme=None)


def _highlight_scale(categories: list, highlight: list) -> alt.Scale:
    palette = colors()
    return alt.Scale(domain=list(categories),
                     range=[palette["accent"] if c in highlight else palette["context"] for c in categories])


def bar(data: pd.DataFrame, category: str, value: str, *, value_title: str, category_title: str | None = None,
        slot: int = 0, height: int | None = None, value_format: str = ",.2f", sort: str | list = "-x",
        horizontal: bool = True, extra_tooltip: list | None = None, highlight: list | str | None = "top",
        labels: bool | None = None, title: str | None = None, subtitle: str | None = None) -> None:
    """Bar chart in one accent colour for the highlighted bars and grey for the rest.

    highlight: "top" (largest value), "all", None (all accent) or a list of categories.
    Bars carry their value as a direct label when there are at most 15 of them.
    """
    data = data.copy()
    data[category] = data[category].astype(str)
    if highlight == "top":
        chosen = [data.loc[data[value].idxmax(), category]] if not data.empty else []
    elif highlight in (None, "all"):
        chosen = list(data[category])
    else:
        chosen = [str(c) for c in highlight]
    color = alt.Color(f"{category}:N", scale=_highlight_scale(data[category].tolist(), chosen), legend=None)
    tooltip = [alt.Tooltip(f"{category}:N", title=category_title or category.replace("_", " ")),
               alt.Tooltip(f"{value}:Q", title=value_title, format=value_format), *(extra_tooltip or [])]
    show_labels = labels if labels is not None else len(data) <= 15
    # Resolve the sort to an explicit category order: layered marks then share one domain without conflicts.
    if isinstance(sort, str) and sort.lstrip("-") in ("x", "y"):
        sort = data.sort_values(value, ascending=not sort.startswith("-"))[category].tolist()
    elif isinstance(sort, str):
        sort = sorted(data[category].unique(), reverse=sort == "descending")
    base = alt.Chart(data)
    if horizontal:
        # The category labels name themselves; a rotated axis title beside them only adds noise.
        y = alt.Y(f"{category}:N", sort=sort, title=None, axis=alt.Axis(labelLimit=200, labelOverlap=False))
        x = alt.X(f"{value}:Q", title=value_title, scale=alt.Scale(nice=True))
        bars = base.mark_bar(height={"band": 0.7}).encode(y=y, x=x, color=color, tooltip=tooltip)
        text = base.mark_text(align="left", dx=4).encode(y=y, x=x, text=alt.Text(f"{value}:Q", format=value_format))
        height = height or max(HEIGHTS["small"], 24 * data[category].nunique() + 40)
    else:
        x = alt.X(f"{category}:O", sort=sort, title=category_title, axis=alt.Axis(labelAngle=0, labelLimit=120))
        y = alt.Y(f"{value}:Q", title=value_title)
        bars = base.mark_bar(width={"band": 0.7}).encode(x=x, y=y, color=color, tooltip=tooltip)
        text = base.mark_text(baseline="bottom", dy=-3).encode(x=x, y=y, text=alt.Text(f"{value}:Q", format=value_format))
        height = height or HEIGHTS["medium"]
    _show(bars + text if show_labels else bars, height, title, subtitle)


def line(data: pd.DataFrame, x: str, y: str, *, y_title: str, x_title: str | None = None,
         series: str | None = None, order: list[str] | None = None, slot: int = 0, height: int | None = None,
         y_format: str = ",.2f", x_type: str = "T", dashed: list[str] | None = None,
         zero: bool = True, x_format: str | None = None, highlight: str | None = None,
         title: str | None = None, subtitle: str | None = None, label_last: bool = False) -> None:
    """Line chart. With `series`, `highlight` (default: the first in `order`) is drawn in the accent
    colour and the others in grey; dashed series also differ in stroke, so colour is never the only cue."""
    palette = colors()
    base = alt.Chart(data)
    tooltip = [alt.Tooltip(f"{x}:{x_type}", title=x_title or x, **({"format": x_format} if x_format else {})),
               alt.Tooltip(f"{y}:Q", title=y_title, format=y_format)]
    x_axis = alt.Axis(format=x_format, labelOverlap=True) if x_format else alt.Axis(labelOverlap=True)
    if x_type == "O":
        x_axis = alt.Axis(labelAngle=0, labelOverlap=True)
    encoding = dict(x=alt.X(f"{x}:{x_type}", title=x_title, axis=x_axis),
                    y=alt.Y(f"{y}:Q", title=y_title, scale=alt.Scale(zero=zero, nice=True)))
    legend = alt.Legend(orient="top", direction="horizontal", labelLimit=320, title=None)
    if series:
        domain = order or sorted(data[series].unique())
        focus = highlight or domain[0]
        encoding["color"] = alt.Color(f"{series}:N", title=None, legend=legend, scale=alt.Scale(
            domain=domain, range=[palette["accent"] if s == focus else palette["context"] for s in domain]))
        if dashed:
            # Same title/orient as the colour legend so Vega-Lite merges them into one legend showing the dash.
            encoding["strokeDash"] = alt.StrokeDash(f"{series}:N", title=None, legend=legend, scale=alt.Scale(
                domain=domain, range=[[5, 3] if s in dashed else [1, 0] for s in domain]))
        tooltip.insert(1, alt.Tooltip(f"{series}:N", title="Series"))
        chart = base.mark_line().encode(**encoding, tooltip=tooltip)
    else:
        chart = base.mark_line(color=palette["accent"]).encode(**encoding, tooltip=tooltip)
    hover = alt.selection_point(fields=[x], nearest=True, on="pointerover", empty=False, clear="pointerout")
    points = base.mark_point(size=60, filled=True, opacity=0).encode(
        x=f"{x}:{x_type}", y=f"{y}:Q", tooltip=tooltip).add_params(hover)
    rule = base.mark_rule(color=palette["muted"], strokeWidth=1).encode(
        x=f"{x}:{x_type}", opacity=alt.condition(hover, alt.value(0.8), alt.value(0)))
    layers = [chart, points, rule]
    if label_last and not series and not data.empty:
        last = data.sort_values(x).tail(1)
        layers.append(alt.Chart(last).mark_text(align="left", dx=6, fontWeight=600, color=palette["text"]).encode(
            x=f"{x}:{x_type}", y=f"{y}:Q", text=alt.Text(f"{y}:Q", format=y_format)))
        layers.append(alt.Chart(last).mark_point(filled=True, size=50, color=palette["accent"]).encode(
            x=f"{x}:{x_type}", y=f"{y}:Q"))
    _show(alt.layer(*layers), height or HEIGHTS["medium"], title, subtitle)


def histogram(data: pd.DataFrame, value: str, *, value_title: str, bins: int = 30, slot: int = 0,
              height: int | None = None, title: str | None = None, subtitle: str | None = None) -> None:
    chart = alt.Chart(data).mark_bar(color=colors()["accent"], cornerRadiusEnd=2, binSpacing=1).encode(
        x=alt.X(f"{value}:Q", bin=alt.Bin(maxbins=bins), title=value_title),
        y=alt.Y("count():Q", title="Records"),
        tooltip=[alt.Tooltip(f"{value}:Q", bin=alt.Bin(maxbins=bins), title=value_title),
                 alt.Tooltip("count():Q", title="Records", format=",")],
    )
    _show(chart, height or HEIGHTS["medium"], title, subtitle)


def scatter(data: pd.DataFrame, x: str, y: str, *, x_title: str, y_title: str, label: str,
            log_x: bool = False, height: int | None = None, tooltip: list | None = None, label_extremes: int = 3,
            title: str | None = None, subtitle: str | None = None) -> None:
    """Scatter with direct labels only on the highest and lowest `label_extremes` points; hover shows the rest."""
    palette = colors()
    low, high = data[x].min(), data[x].max()
    scale = (alt.Scale(type="log", domain=[low / 1.3, high * 1.5], nice=False) if log_x
             else alt.Scale(zero=False))
    ranked = data[y].rank(method="first")
    labelled = data[(ranked <= label_extremes) | (ranked > len(data) - label_extremes)]
    points = alt.Chart(data).mark_circle(size=80, color=palette["accent"], opacity=0.8).encode(
        x=alt.X(f"{x}:Q", title=x_title, scale=scale), y=alt.Y(f"{y}:Q", title=y_title),
        tooltip=tooltip or [label, x, y])
    labels = alt.Chart(labelled).mark_text(align="left", dx=8).encode(
        x=alt.X(f"{x}:Q", scale=scale), y=f"{y}:Q", text=f"{label}:N")
    _show(points + labels, height or HEIGHTS["large"], title, subtitle)


def _mix(start: str, end: str, share: float) -> str:
    a = [int(start[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(end[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * share):02x}" for x, y in zip(a, b))


def diverging_color(r: float) -> str:
    """Neutral at r = 0, blue towards +1 and red towards -1, interpolated from the neutral midpoint."""
    negative, middle, positive = colors()["diverging"]
    return middle if pd.isna(r) else _mix(middle, positive if r >= 0 else negative, min(abs(r), 1.0))


def correlation_heatmap(corr: pd.DataFrame, *, height: int | None = None, title: str | None = None) -> None:
    """Diverging heatmap: blue = positive, red = negative, neutral grey at r = 0; every cell is labelled."""
    palette = colors()
    long = corr.rename_axis("Row").reset_index().melt("Row", var_name="Column", value_name="r")
    long["Fill"] = long["r"].map(diverging_color)
    order = list(corr.columns)
    base = alt.Chart(long).encode(
        x=alt.X("Column:N", sort=order, title=None,
                axis=alt.Axis(labelAngle=-35, labelLimit=170, labelOverlap=False, orient="bottom")),
        y=alt.Y("Row:N", sort=order, title=None, axis=alt.Axis(labelLimit=170, labelOverlap=False)),
    )
    cells = base.mark_rect(stroke=palette["surface"], strokeWidth=1).encode(
        color=alt.Color("Fill:N", scale=None),
        tooltip=[alt.Tooltip("Row:N", title="Variable"), alt.Tooltip("Column:N", title="With"),
                 alt.Tooltip("r:Q", format=".2f")],
    )
    text = base.mark_text(fontSize=11).encode(
        text=alt.Text("r:Q", format=".2f"),
        color=alt.condition("abs(datum.r) > 0.6", alt.value(palette["text_on_strong"]), alt.value(palette["text"])),
    )
    _show(cells + text, height or 380, title)


def tip(field: str, title: str, fmt: str | None = ".2f") -> alt.Tooltip:
    """Tooltip entry: quantitative with a number format, or nominal when fmt is None."""
    return alt.Tooltip(f"{field}:N", title=title) if fmt is None else alt.Tooltip(f"{field}:Q", title=title, format=fmt)
