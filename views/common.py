"""Page prelude shared by the analysis pages: title, purpose line, source label, missing-data states."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services.data import EXTRACT_COMMAND, SOURCES, current_source, describe, load, set_source
from ui.components import empty_state, page_header, source_label

UNIT_NOTE = ("Quantities are in each food's recorded unit (kg, L, dozen, loaf or pack), so totals are only "
             "compared within a food; rates and percentages are unit-free.")


PERIOD_NOTE = ("My data is recorded per pantry-check period, not per day, so day-level analyses (next-day "
               "forecasts, weekend vs weekday tests) cannot run on it. That is a sample-size limit of weekly "
               "checks, not an error.")


def begin(title: str, purpose: str, *, feature: str | None = "waste") -> tuple[str, pd.DataFrame | None]:
    """Render the page header and return (source key, data). Data is None when nothing can be shown.

    For My data, `feature` names the pantry.UNLOCK rule that must be met before
    the page shows anything (None = always shown, e.g. Data Quality); a
    reliability note with sample sizes is shown when it is met but still thin.
    """
    page_header(title, purpose)
    source = current_source()
    df = load(source)
    source_label(SOURCES[source], describe(source, df))
    if df is None:
        empty_state(f"The {SOURCES[source]} extract has not been built",
                    f"Download the raw files into dataset/ and run `{EXTRACT_COMMAND}` from the project root. "
                    "The raw files are never modified.")
        return source, None
    if source == "personal":
        from services.personal import gate
        if feature:
            shown, reliable, note = gate(feature)
            if not shown:
                empty_state("Not enough of your data yet",
                            f"{note} Keep logging purchases and do a pantry check every week or so; this page "
                            "unlocks on its own.", page="views/pantry.py", page_label="Do a pantry check")
                return source, None
            if not reliable:
                st.warning(note)
            else:
                st.caption(note)
        if df.empty and feature:
            empty_state("No completed periods yet",
                        "A period ends at a pantry check after a purchase. Log what you buy, then check your pantry.",
                        page="views/pantry.py", page_label="Do a pantry check")
            return source, None
    return source, df


def switch_buttons(options: list[str], key: str) -> None:
    """Buttons that switch the global data source to one that supports the current page."""
    with st.container(horizontal=True):
        for option in options:
            st.button(f"Use {SOURCES[option]}", key=f"{key}_{option}", on_click=set_source, args=(option,))


def not_available(source: str, what: str, reason: str, *, alternatives: list[str], key: str) -> None:
    empty_state(f"{what} is not available for {SOURCES[source]}", reason)
    switch_buttons(alternatives, key)
