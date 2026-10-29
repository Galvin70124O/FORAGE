"""Layout pieces shared by every page: headers, the Fresh Shelf signature pieces, tables and formatting.

Signature pieces (styled in ui/theme.py):
    label_card / kpi_row   pantry-label KPI cards: small-caps name, Fraunces value, comparison line
    freshness_bar          slim meter from fresh to use soon to expired, with the days written on it
    shelf                  a labelled shelf of small jar cards on a wooden plank
    waste_gauge            semicircle gauge of this month's waste % against a target, with one sentence
    demand_card(s)         predicted quantity, confidence and a Buy less / same / more stamp
    empty_state            a kind, short message with an empty jar and the next step
    placeholder_lines      grey loading lines at the final size of the text they stand in for
"""

from __future__ import annotations

import hashlib
import math
import re
from html import escape

import pandas as pd
import streamlit as st


def page_header(title: str, purpose: str, *, pill: str | None = None, detail: str | None = None,
                greeting: str | None = None) -> None:
    """Title and one-line purpose on the left; the data-source pill on the right; an optional detail line."""
    left, right = st.columns([5, 2], vertical_alignment="bottom")
    with left:
        if greeting:
            st.html(f'<p class="fs-greeting">{escape(greeting)}</p>')
        st.title(title, anchor=False)
        st.markdown(f'<p class="fg-purpose">{escape(purpose)}</p>', unsafe_allow_html=True)
    if pill:
        right.markdown(f'<div style="text-align:right"><span class="fg-pill">Source: <b>{escape(pill)}</b></span></div>',
                       unsafe_allow_html=True)
    if detail:
        st.markdown(f'<div class="fg-detail">{escape(detail)}</div>', unsafe_allow_html=True)


def greeting() -> str:
    """"Good morning" / "afternoon" / "evening" in the viewer's time zone, with their first name when signed in."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    try:
        zone = ZoneInfo(st.context.timezone) if st.context.timezone else None
    except Exception:  # noqa: BLE001 - an unknown zone or auth setup must never break the greeting
        zone = None
    hour = datetime.now(zone).hour
    part = "Good morning" if 5 <= hour < 12 else "Good afternoon" if 12 <= hour < 17 else "Good evening"
    try:
        name = st.user.get("given_name") if st.user.is_logged_in else None
    except Exception:  # noqa: BLE001 - an unknown zone or auth setup must never break the greeting
        name = None
    return f"{part}, {name}" if name else part


def source_label(name: str, detail: str) -> None:
    """Detail line for pages that render their own header (personal pages)."""
    st.markdown(f'<div class="fg-detail">{escape(name)} · {escape(detail)}</div>', unsafe_allow_html=True)


def _change(delta: str | None, delta_color: str) -> tuple[str, str]:
    """(arrow, tone class) for a signed change such as "+₹2,233 vs last month" or "-3 vs a month ago"."""
    text = (delta or "").strip()
    number = re.search(r"\d[\d,]*\.?\d*", text)
    if not text or (number and float(number.group().replace(",", "")) == 0):
        return "→", "fs-flat"
    rising, falling = text[0] == "+", text[0] in "-−"
    arrow = "↑" if rising else "↓" if falling else "→"
    if not (rising or falling) or delta_color == "off":
        return arrow, "fs-flat"
    good = rising if delta_color == "normal" else falling
    return arrow, "fs-good" if good else "fs-bad"


def label_card(name: str, value: str, *, compare: str | None = None, help: str | None = None,
               delta_color: str = "normal") -> str:
    """One pantry label: small-caps name, the value in Fraunces and a comparison with last period.

    The comparison carries an arrow and words as well as colour. delta_color: "normal" when a rise is
    good, "inverse" when a fall is good (waste), "off" for neutral changes.
    """
    arrow, tone = _change(compare, delta_color)
    size = " fs-small" if len(str(value)) > 11 else ""
    line = f'<div class="fs-label-compare"><b class="{tone}">{arrow} {escape(compare)}</b></div>' if compare else ""
    title = f' title="{escape(help, quote=True)}"' if help else ""
    return (f'<div class="fs-label" role="group" aria-label="{escape(name, quote=True)}"{title}>'
            f'<div class="fs-label-name">{escape(name)}</div>'
            f'<div class="fs-label-value{size}">{escape(str(value))}</div>{line}</div>')


def kpi_row(items: list[tuple]) -> None:
    """A row of pantry labels from (label, value[, help[, delta[, delta_color]]]); stacks on a phone.

    `delta` is shown with an arrow as well as colour; use delta_color="inverse" when a fall is good
    (waste), "normal" when a rise is good, "off" for neutral changes.
    """
    cards = []
    for item in items:
        label, value, *rest = item
        help_text = rest[0] if len(rest) > 0 else None
        delta = rest[1] if len(rest) > 1 else None
        delta_color = rest[2] if len(rest) > 2 else "normal"
        cards.append(label_card(label, value, compare=delta, help=help_text, delta_color=delta_color))
    st.html(f'<div class="fs-labels">{"".join(cards)}</div>')


def chips(items: list[tuple[str, str]]) -> None:
    """Small secondary figures under a label row: [(name, value), ...]."""
    st.html('<div class="fs-chips">' + "".join(f'<span class="fs-chip">{escape(n)}: <b>{escape(v)}</b></span>'
                                               for n, v in items) + "</div>")


def _svg_html(markup: str) -> None:
    """HTML that contains inline SVG (st.html strips SVG; st.markdown keeps it)."""
    st.markdown(markup, unsafe_allow_html=True)


# --- Freshness: meter and shelves ---------------------------------------------

def freshness_status(days_left: float) -> str:
    """"gone" (expired), "soon" (use within 2 days) or "fresh"."""
    return "gone" if days_left < 0 else "soon" if days_left <= 2 else "fresh"


def days_text(days_left: float) -> str:
    days = math.floor(days_left)
    if days < 0:
        return "Expired yesterday" if days == -1 else f"Expired {-days} days ago"
    return "Use today" if days == 0 else "1 day left" if days == 1 else f"{days} days left"


def freshness_bar(days_left: float, horizon: float = 7) -> str:
    """Slim meter: the filled share is the freshness left (days left ÷ shelf life, capped at two weeks so
    long-life foods still read), coloured by status, with the days written just above it: colour is never
    the only cue and the bar never covers the text."""
    status = freshness_status(days_left)
    scale = min(max(horizon, 1), 14)
    share = 1.0 if days_left < 0 else min(max((days_left + 1) / (scale + 1), 0.22), 1.0)
    text = days_text(days_left)
    return (f'<div class="fs-meter-text fs-{status}">{text}</div><div class="fs-meter" aria-hidden="true">'
            f'<div class="fs-meter-fill fs-{status}" style="width:{share * 100:.0f}%"></div></div>')


def jar(name: str, quantity: str, days_left: float, horizon: float = 7) -> str:
    """A small label card for one item on a shelf."""
    return (f'<div class="fs-jar fs-{freshness_status(days_left)}"><div class="fs-jar-name">{escape(name)}</div>'
            f'<div class="fs-jar-qty">{escape(quantity)}</div>{freshness_bar(days_left, horizon)}</div>')


def shelf(title: str, items: list[dict], *, note: str | None = None, empty: str = "Nothing on this shelf.",
          limit: int | None = None) -> None:
    """One shelf: a heading with a count, a row of jars (name, quantity, days_left[, horizon]) and a plank."""
    shown = items[:limit] if limit else items
    head = (f'<div class="fs-shelf-head"><p class="fs-shelf-title">{escape(title)}</p>'
            f'<span class="fs-shelf-count">{len(items)}</span>'
            + (f'<span class="fs-shelf-note">{escape(note)}</span>' if note else "") + "</div>")
    if shown:
        row = '<div class="fs-shelf-row">' + "".join(
            jar(i["name"], i["quantity"], i["days_left"], i.get("horizon", 7)) for i in shown) + "</div>"
        if len(items) > len(shown):
            row += f'<div class="fs-shelf-note" style="padding:0 6px 8px">and {len(items) - len(shown)} more</div>'
    else:
        row = f'<div class="fs-shelf-empty">{escape(empty)}</div>'
    st.html(f'<div class="fs-shelf">{head}{row}<div class="fs-plank" aria-hidden="true"></div></div>')


# --- Waste-bin gauge -----------------------------------------------------------

def waste_gauge(rate: float, target: float, *, previous: float | None = None, name: str = "Waste this month",
                note: str | None = None) -> None:
    """Semicircle gauge of this month's waste % against `target`, with one plain sentence under it."""
    if pd.isna(rate):
        st.html(f'<div class="fs-gauge"><div class="fs-gauge-name">{escape(name)}</div>'
                '<p class="fs-gauge-sentence">No waste figure for this month yet.</p></div>')
        return
    top = max(10, math.ceil(max(rate * 1.15, target * 2) / 10) * 10)
    status = "fresh" if rate <= target else "soon" if rate <= target * 1.5 else "gone"

    def point(value: float, radius: float) -> tuple[float, float]:
        angle = math.pi * (1 - min(value / top, 1))
        return 110 + radius * math.cos(angle), 112 - radius * math.sin(angle)

    (x1, y1), (x2, y2), (lx, ly) = point(target, 76), point(target, 104), point(target, 116)
    anchor = "end" if target / top < 0.4 else "start" if target / top > 0.6 else "middle"
    arc = "M20 112 A90 90 0 0 1 200 112"
    svg = (f'<svg viewBox="0 0 220 140" role="img" aria-label="Waste {rate:.1f}% against a target of {target:.1f}%">'
           f'<path d="{arc}" pathLength="100" fill="none" style="stroke:var(--fs-stone-tint)" stroke-width="18" '
           'stroke-linecap="round"/>'
           f'<path d="{arc}" pathLength="100" fill="none" style="stroke:var(--fs-{status})" stroke-width="18" '
           f'stroke-linecap="round" stroke-dasharray="{min(rate / top, 1) * 100:.1f} 100"/>'
           f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" style="stroke:var(--fs-text)" '
           'stroke-width="2.5" stroke-linecap="round"/>'
           f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}" style="fill:var(--fs-muted);font-size:10px;'
           f'font-weight:600">target {target:.0f}%</text>'
           '<text x="110" y="100" text-anchor="middle" style="fill:var(--fs-text);font-family:Fraunces,Georgia,serif;'
           f'font-size:32px;font-weight:600">{rate:.1f}%</text>'
           '<text x="110" y="122" text-anchor="middle" style="fill:var(--fs-muted);font-size:11px">of food wasted</text>'
           '<text x="20" y="137" text-anchor="middle" style="fill:var(--fs-muted);font-size:10px">0%</text>'
           f'<text x="200" y="137" text-anchor="middle" style="fill:var(--fs-muted);font-size:10px">{top}%</text></svg>')
    if previous is None or pd.isna(previous) or previous == 0:
        sentence = "You're under the target. Lovely." if rate <= target else f"{rate - target:.1f} points above the target."
    else:
        change = (rate - previous) / previous * 100
        sentence = ("About the same as last month." if abs(change) < 1 else
                    f"You wasted {abs(change):.0f}% {'less' if change < 0 else 'more'} than last month.")
    _svg_html(f'<div class="fs-gauge"><div class="fs-gauge-name">{escape(name)}</div>{svg}'
            f'<p class="fs-gauge-sentence">{escape(sentence)}</p>'
            + (f'<div class="fs-gauge-note">{escape(note)}</div>' if note else "") + "</div>")


# --- Demand cards --------------------------------------------------------------

STAMPS = {"more": "Buy more", "same": "Buy same", "less": "Buy less"}
LEVELS = {"High": 3, "Medium": 2, "Low": 1}


def confidence_level(relative_error: float | None) -> str | None:
    """High / Medium / Low from the model's typical error as a % of the item's average demand."""
    if relative_error is None or pd.isna(relative_error):
        return None
    return "High" if relative_error < 25 else "Medium" if relative_error < 50 else "Low"


def demand_card(name: str, value: str, unit: str, *, stamp: str, what: str = "predicted for tomorrow",
                relative_error: float | None = None, note: str | None = None) -> str:
    """One predicted item: the quantity in Fraunces, a confidence meter and a Buy less / same / more stamp."""
    level = confidence_level(relative_error)
    confidence = ""
    if level:
        dots = "".join(f'<i class="{"on" if i < LEVELS[level] else ""}"></i>' for i in range(3))
        confidence = (f'<div class="fs-confidence"><span class="fs-dots" aria-hidden="true">{dots}</span>'
                      f"{level} confidence (±{relative_error:.0f}%)</div>")
    return (f'<div class="fs-demand"><div class="fs-demand-top"><div class="fs-demand-name">{escape(name)}</div>'
            f'<span class="fs-stamp fs-{stamp}">{STAMPS[stamp]}</span></div>'
            f'<div class="fs-demand-value">{escape(value)} <span>{escape(unit)}</span></div>'
            f'<div class="fs-demand-what">{escape(what)}</div>{confidence}'
            + (f'<div class="fs-demand-note">{escape(note)}</div>' if note else "") + "</div>")


def demand_cards(cards: list[str]) -> None:
    st.html(f'<div class="fs-demands">{"".join(cards)}</div>')


def section(title: str, note: str | None = None) -> None:
    st.subheader(title)
    if note:
        st.caption(note)


def placeholder_lines(widths: list[int], *, caption_width: int | None = None) -> None:
    """Grey placeholder lines while figures are computed: one paragraph per width (% of the column) and an
    optional caption line, in the same elements (so the same height) as the st.write / st.caption lines that
    replace them inside the same st.empty slot."""
    for width in widths:
        st.markdown(_bar(width), unsafe_allow_html=True)
    if caption_width:
        st.caption(_bar(caption_width), unsafe_allow_html=True)


def _bar(width: int) -> str:
    return (f'<span class="fs-skeleton" style="width:{int(width)}%;max-width:{width / 2.5:.0f}rem" '
            'aria-hidden="true"></span>')


KITCHEN_PAGES = {"views/home.py", "views/bought.py", "views/pantry.py", "views/shopping.py", "views/my_data.py"}


def go_to_kitchen(page: str) -> None:
    """Switch to Kitchen mode and open `page` on the next run (app.py performs the switch)."""
    st.session_state.update(app_mode="kitchen", app_mode_chosen=True, goto=page)


EMPTY_JAR = (
    '<svg viewBox="0 0 56 56" aria-hidden="true">'
    '<rect x="17" y="6" width="22" height="7" rx="2.5" style="fill:var(--fs-line-strong)"/>'
    '<path d="M16 16h24a5 5 0 0 1 5 5v22a7 7 0 0 1-7 7H18a7 7 0 0 1-7-7V21a5 5 0 0 1 5-5z" fill="none" '
    'style="stroke:var(--fs-line-strong)" stroke-width="2.5"/>'
    '<rect x="17" y="26" width="22" height="12" rx="2" style="fill:var(--fs-brand-tint)"/>'
    '<path d="M22 32h12" style="stroke:var(--fs-brand)" stroke-width="2" stroke-linecap="round"/></svg>')


def empty_state(title: str, body: str, *, page: str | None = None, page_label: str | None = None) -> None:
    """A short, kind message with an empty jar and, when given, the next step."""
    slug = hashlib.md5(f"{title}{body}".encode()).hexdigest()[:8]
    with st.container(border=True, key=f"fs-empty-{slug}"):
        _svg_html(f'<div class="fs-empty">{EMPTY_JAR}<p class="fs-empty-title">{escape(title)}</p>'
                f'<p class="fs-empty-body">{escape(body)}</p></div>')
        if page and page in KITCHEN_PAGES and st.session_state.get("app_mode") != "kitchen":
            st.button(page_label or "Open", on_click=go_to_kitchen, args=(page,), key=f"goto_{page}")
        elif page:
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


def row_px() -> int:
    """Height of one st.dataframe / st.data_editor row, and of its header row, in px.

    Streamlit draws them 2.1875rem tall and its rem is theme.baseFontSize: 33 px with FORAGE's 15 px base
    (.streamlit/config.toml), 35 px at Streamlit's default of 16.
    """
    try:
        base = float(st.get_option("theme.baseFontSize") or 16)
    except Exception:  # noqa: BLE001 - an unknown option must never break a table
        base = 16.0
    return round(2.1875 * base)


TABLE_BORDER_PX = 2  # 1 px top and bottom


def fit_height(rows: int, max_rows: int | None = None) -> int:
    """Pixel height that shows `rows` whole rows (at most `max_rows`, scrolling for the rest) plus the header:
    never a row cut in half and no empty padding rows. Pass it as `height` to st.dataframe / st.data_editor."""
    shown = max(min(rows, max_rows) if max_rows else rows, 1)
    return row_px() * (shown + 1) + TABLE_BORDER_PX


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
