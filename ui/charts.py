"""Altair chart builders shared by every page.

Rules: one y-axis per chart, axis titles carry units, every mark has a
tooltip, colours come from ui.theme in a fixed order. Streamlit's chart theme
supplies fonts, grid and axis colours for light and dark mode.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

from ui.theme import colors


def _show(chart: alt.Chart, height: int) -> None:
    st.altair_chart(chart.properties(height=height), width="stretch", theme="streamlit")


def bar(data: pd.DataFrame, category: str, value: str, *, value_title: str, category_title: str | None = None,
        slot: int = 0, height: int = 300, value_format: str = ",.2f", sort: str | list = "-x",
        horizontal: bool = True, extra_tooltip: list | None = None) -> None:
    """Single-series bar chart; horizontal bars are sorted largest first."""
    color = colors()["series"][slot]
    tooltip = [alt.Tooltip(f"{category}:N", title=category_title or category),
               alt.Tooltip(f"{value}:Q", title=value_title, format=value_format), *(extra_tooltip or [])]
    if horizontal:
        # The category labels name themselves; a rotated axis title beside them only adds noise.
        encoding = dict(y=alt.Y(f"{category}:N", sort=sort, title=None,
                                axis=alt.Axis(labelLimit=220, labelOverlap=False)),
                        x=alt.X(f"{value}:Q", title=value_title))
        height = max(height, 22 * data[category].nunique() + 50)
        mark = alt.Chart(data).mark_bar(color=color, cornerRadiusEnd=3, height={"band": 0.72})
    else:
        encoding = dict(x=alt.X(f"{category}:O", sort=sort, title=category_title, axis=alt.Axis(labelAngle=0)),
                        y=alt.Y(f"{value}:Q", title=value_title))
        mark = alt.Chart(data).mark_bar(color=color, cornerRadiusEnd=3, width={"band": 0.72})
    _show(mark.encode(**encoding, tooltip=tooltip), height)


def line(data: pd.DataFrame, x: str, y: str, *, y_title: str, x_title: str | None = None,
         series: str | None = None, order: list[str] | None = None, slot: int = 0, height: int = 300,
         y_format: str = ",.2f", x_type: str = "T", dashed: list[str] | None = None,
         zero: bool = True, x_format: str | None = None) -> None:
    """Line chart; with `series`, colours follow `order` so each series keeps its colour on every page."""
    palette = colors()["series"]
    base = alt.Chart(data)
    tooltip = [alt.Tooltip(f"{x}:{x_type}", title=x_title or x, **({"format": x_format} if x_format else {})),
               alt.Tooltip(f"{y}:Q", title=y_title, format=y_format)]
    x_axis = alt.Axis(format=x_format, labelOverlap=True) if x_format else alt.Axis(labelOverlap=True)
    if x_type == "O":
        x_axis = alt.Axis(labelAngle=0, labelOverlap=True)
    encoding = dict(x=alt.X(f"{x}:{x_type}", title=x_title, axis=x_axis),
                    y=alt.Y(f"{y}:Q", title=y_title, scale=alt.Scale(zero=zero, nice=True, padding=8)))
    if series:
        domain = order or sorted(data[series].unique())
        encoding["color"] = alt.Color(f"{series}:N", title=None, scale=alt.Scale(domain=domain, range=palette[:len(domain)]),
                                      legend=alt.Legend(orient="top", direction="horizontal", labelLimit=320))
        if dashed:
            # Same title/orient as the colour legend so Vega-Lite merges them into one legend showing the dash.
            encoding["strokeDash"] = alt.StrokeDash(
                f"{series}:N", title=None, legend=alt.Legend(orient="top", direction="horizontal", labelLimit=320),
                scale=alt.Scale(domain=domain, range=[[5, 3] if s in dashed else [1, 0] for s in domain]))
        tooltip.insert(1, alt.Tooltip(f"{series}:N", title="Series"))
        chart = base.mark_line(strokeWidth=2).encode(**encoding, tooltip=tooltip)
    else:
        chart = base.mark_line(strokeWidth=2, color=palette[slot]).encode(**encoding, tooltip=tooltip)
    hover = alt.selection_point(fields=[x], nearest=True, on="pointerover", empty=False, clear="pointerout")
    points = base.mark_point(size=60, filled=True, opacity=0).encode(
        x=f"{x}:{x_type}", y=f"{y}:Q", tooltip=tooltip).add_params(hover)
    rule = base.mark_rule(color=colors()["muted"], strokeWidth=1).encode(
        x=f"{x}:{x_type}", opacity=alt.condition(hover, alt.value(0.8), alt.value(0)))
    _show(alt.layer(chart, points, rule), height)


def histogram(data: pd.DataFrame, value: str, *, value_title: str, bins: int = 30, slot: int = 0,
              height: int = 260) -> None:
    color = colors()["series"][slot]
    chart = alt.Chart(data).mark_bar(color=color, cornerRadiusEnd=2, binSpacing=1).encode(
        x=alt.X(f"{value}:Q", bin=alt.Bin(maxbins=bins), title=value_title),
        y=alt.Y("count():Q", title="Records"),
        tooltip=[alt.Tooltip(f"{value}:Q", bin=alt.Bin(maxbins=bins), title=value_title),
                 alt.Tooltip("count():Q", title="Records", format=",")],
    )
    _show(chart, height)


def scatter(data: pd.DataFrame, x: str, y: str, *, x_title: str, y_title: str, label: str,
            log_x: bool = False, height: int = 320, tooltip: list | None = None, label_extremes: int = 3) -> None:
    """Scatter with direct labels only on the highest and lowest `label_extremes` points; hover shows the rest."""
    color = colors()["series"][0]
    low, high = data[x].min(), data[x].max()
    scale = (alt.Scale(type="log", domain=[low / 1.3, high * 1.5], nice=False) if log_x
             else alt.Scale(zero=False))
    ranked = data[y].rank(method="first")
    labelled = data[(ranked <= label_extremes) | (ranked > len(data) - label_extremes)]
    points = alt.Chart(data).mark_circle(size=90, color=color, opacity=0.85).encode(
        x=alt.X(f"{x}:Q", title=x_title, scale=scale), y=alt.Y(f"{y}:Q", title=y_title),
        tooltip=tooltip or [label, x, y])
    labels = alt.Chart(labelled).mark_text(align="left", dx=8, fontSize=11, color=colors()["muted"]).encode(
        x=alt.X(f"{x}:Q", scale=scale), y=f"{y}:Q", text=f"{label}:N")
    _show(points + labels, height)


def _mix(start: str, end: str, share: float) -> str:
    a = [int(start[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(end[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * share):02x}" for x, y in zip(a, b))


def diverging_color(r: float) -> str:
    """Neutral at r = 0, blue towards +1 and red towards -1, interpolated from the neutral midpoint."""
    negative, middle, positive = colors()["diverging"]
    return middle if pd.isna(r) else _mix(middle, positive if r >= 0 else negative, min(abs(r), 1.0))


def correlation_heatmap(corr: pd.DataFrame, *, height: int = 360) -> None:
    """Diverging heatmap: blue = positive, red = negative, neutral grey at r = 0."""
    palette = colors()
    long = corr.rename_axis("Row").reset_index().melt("Row", var_name="Column", value_name="r")
    long["Fill"] = long["r"].map(diverging_color)
    order = list(corr.columns)
    base = alt.Chart(long).encode(
        x=alt.X("Column:N", sort=order, title=None,
                axis=alt.Axis(labelAngle=-35, labelLimit=170, labelOverlap=False)),
        y=alt.Y("Row:N", sort=order, title=None, axis=alt.Axis(labelLimit=170, labelOverlap=False)),
    )
    cells = base.mark_rect(stroke=None).encode(
        color=alt.Color("Fill:N", scale=None),
        tooltip=[alt.Tooltip("Row:N", title="Variable"), alt.Tooltip("Column:N", title="With"),
                 alt.Tooltip("r:Q", format=".2f")],
    )
    text = base.mark_text(fontSize=11).encode(
        text=alt.Text("r:Q", format=".2f"),
        color=alt.condition("abs(datum.r) > 0.6", alt.value(palette["text_on_strong"]), alt.value(palette["text"])),
    )
    _show(cells + text, height)


def tip(field: str, title: str, fmt: str | None = ".2f") -> alt.Tooltip:
    """Tooltip entry: quantitative with a number format, or nominal when fmt is None."""
    return alt.Tooltip(f"{field}:N", title=title) if fmt is None else alt.Tooltip(f"{field}:Q", title=title, format=fmt)
