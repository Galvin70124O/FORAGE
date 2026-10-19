"""Rendering of the hypothesis tests on the EDA page."""

import streamlit as st

from hypothesis import ALPHA, format_p
from ui.components import kpi_row

SYNTHETIC_NOTE = ("The demo data is synthetic: its generator adds +15% consumption at weekends for four foods and "
                  "+20% on festival days, so these tests show the method rather than real-world findings.")


def render(results: list, *, source: str) -> None:
    st.caption(f"Significance level α = {ALPHA}. With thousands of observations even tiny differences are "
               "significant, so read the effect size before the p-value. "
               + (SYNTHETIC_NOTE if source == "demo" else ""))
    for result in results:
        st.markdown(f"**{result.question}** · {result.name}")
        st.markdown(f"H0: {result.h0}  \nH1: {result.h1}")
        items = [(result.statistic_name, f"{result.statistic:,.3f}"), ("p-value", format_p(result.p_value)),
                 (result.effect_name, f"{result.effect:.3f}", f"{result.effect_label.capitalize()} effect."),
                 ("n", f"{result.n:,}")]
        if "mean_a" in result.extra:
            items.append(("Means (a / b)", f"{result.extra['mean_a']:.1f} / {result.extra['mean_b']:.1f}",
                          f"n = {result.extra['n_a']:,} and {result.extra['n_b']:,}."))
        kpi_row(items)
        st.markdown(f"Conclusion: {result.conclusion}")
        if result.extra.get("cells_expected_below_5_pct", 0) > 20:
            st.warning("More than 20% of cells have an expected count below 5, so the χ² approximation is unreliable.")
        st.divider()
