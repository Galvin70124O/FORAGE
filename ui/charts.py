"""Altair chart helpers that share one palette."""


import altair as alt
import streamlit as st



from ui.theme import ALERT_COLOR, THEMES, current_theme


def configure_chart(chart):
    """Apply the active palette to every Altair chart surface and label."""
    theme = THEMES[current_theme()]
    return chart.configure(
        background=theme["surface_alt"],
        font="Inter, ui-sans-serif, system-ui, sans-serif",
    ).configure_view(
        fill=theme["surface"], stroke=theme["border"], strokeWidth=1, cornerRadius=6,
    ).configure_axis(
        gridColor=theme["grid"], gridOpacity=0.9, gridDash=[2, 3],
        domainColor=theme["text_secondary"], domainOpacity=0.42, tickColor=theme["text_secondary"], tickOpacity=0.35,
        labelColor=theme["text_secondary"], titleColor=theme["text_secondary"], labelFontSize=11,
        labelPadding=7, titleFontSize=11,
    ).configure_legend(
        labelColor=theme["text_secondary"], titleColor=theme["text"], labelFontSize=11,
        symbolSize=90, padding=4,
    ).configure_title(
        color=theme["text"],
    )


def chart_colors():
    """Return the small, semantic chart palette for the selected interface theme."""
    theme = THEMES[current_theme()]
    return {
        "consumption": theme["green"], "trend_waste": theme["accent"],
        "waste": theme["waste"], "waste_line": theme["waste_line"], "lime": theme["lime"],
        "teal": theme["teal"], "neutral": theme["text_secondary"],
    }


def themed_chart_color(color):
    """Resolve a semantic series identifier through the active palette."""
    return chart_colors()[color]


def themed_line_color(color):
    """Use the dedicated amber waste line while preserving other semantics."""
    palette = chart_colors()
    return palette["waste_line"] if color == ALERT_COLOR else palette[color]


def line_chart(data, x, y, color=None, height=330):
    """Render a consistent interactive line chart with lightweight tooltips."""
    chart = alt.Chart(data).mark_line(point=False, strokeWidth=2.4).encode(
        x=alt.X(f"{x}:T", title=None),
        y=alt.Y(f"{y}:Q", title=None),
        color=alt.Color(f"{color}:N", scale=alt.Scale(range=[chart_colors()["consumption"], chart_colors()["trend_waste"]]) if color else alt.Undefined, legend=alt.Legend(title=None) if color else None),
        tooltip=[alt.Tooltip(f"{x}:T", title="Date"), alt.Tooltip(f"{y}:Q", format=".2f"), *( [alt.Tooltip(f"{color}:N")] if color else [])],
    ).properties(height=height)
    chart = configure_chart(chart)
    st.altair_chart(chart, width="stretch")


def bar_chart(data, label_column, value_column, color, height=300, value_format=".2f"):
    """Render an intentional ranked horizontal bar chart."""
    chart = alt.Chart(data).mark_bar(color=themed_chart_color(color), cornerRadiusEnd=4, size=18).encode(
        y=alt.Y(f"{label_column}:N", sort="-x", title=None),
        x=alt.X(f"{value_column}:Q", title=None),
        tooltip=[alt.Tooltip(f"{label_column}:N", title="Item"), alt.Tooltip(f"{value_column}:Q", format=value_format)],
    ).properties(height=height)
    chart = configure_chart(chart)
    st.altair_chart(chart, width="stretch")


def series_line_chart(data, colors, height=300, markers=False):
    """Render Streamlit series with the shared responsive product chart style."""
    chart_data = data.rename_axis("Date").reset_index().melt("Date", var_name="Measure", value_name="Quantity")
    chart = alt.Chart(chart_data).mark_line(
        point=alt.OverlayMarkDef(size=30, filled=True) if markers else False,
        strokeWidth=3.2 if markers else 2.8,
    ).encode(
        x=alt.X("Date:T", title=None), y=alt.Y("Quantity:Q", title=None),
        color=alt.Color("Measure:N", scale=alt.Scale(range=[themed_line_color(color) for color in colors]), legend=alt.Legend(title=None)),
        tooltip=[alt.Tooltip("Date:T", title="Date"), "Measure:N", alt.Tooltip("Quantity:Q", format=".2f")],
    ).properties(height=height)
    st.altair_chart(configure_chart(chart), width="stretch")


def series_bar_chart(data, color, height=300):
    """Render a single analytical series using the shared product chart style."""
    series_name = data.name or "Quantity"
    chart_data = data.rename(series_name).rename_axis("Label").reset_index()
    chart = alt.Chart(chart_data).mark_bar(color=themed_chart_color(color), cornerRadiusEnd=5, size=19).encode(
        y=alt.Y("Label:N", sort="-x", title=None), x=alt.X(f"{series_name}:Q", title=None),
        tooltip=[alt.Tooltip("Label:N", title="Item"), alt.Tooltip(f"{series_name}:Q", format=".2f")],
    ).properties(height=height)
    st.altair_chart(configure_chart(chart), width="stretch")
