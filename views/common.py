"""Page prelude shared by the analysis pages: title, purpose line, source label, missing-data states."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from services.data import EXTRACT_COMMAND, SOURCES, current_source, describe, load, set_source
from ui.components import empty_state, page_header, source_label

UNIT_NOTE = ("Quantities are in each food's recorded unit (kg, L, dozen, loaf or pack), so totals are only "
             "compared within a food; rates and percentages are unit-free.")


def begin(title: str, purpose: str) -> tuple[str, pd.DataFrame | None]:
    """Render the page header and return (source key, data). Data is None when nothing can be shown."""
    page_header(title, purpose)
    source = current_source()
    df = load(source)
    source_label(SOURCES[source], describe(source, df))
    if df is None:
        empty_state(f"The {SOURCES[source]} extract has not been built",
                    f"Download the raw files into dataset/ and run `{EXTRACT_COMMAND}` from the project root. "
                    "The raw files are never modified.")
        return source, None
    if source == "personal" and df.empty:
        empty_state("No personal records yet",
                    "Add a record or import a CSV on the My Data page. Your records are kept separate from "
                    "the demo and public datasets.", page="views/my_data.py", page_label="Go to My Data")
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
