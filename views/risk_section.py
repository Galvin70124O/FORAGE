"""Rendering of the waste-risk classifier and its explanation (Waste & Expiry page)."""

import pandas as pd
import streamlit as st

from explain import top_feature_sentence
from ui import charts
from ui.components import kpi_row, number, section, table
from waste_risk import HIGH_WASTE_PCT, TARGET_RECALL

DEMO_NOTE = ("How the demo data was generated matters here: waste is a random 20–70% share of whatever was bought "
             "but not eaten. That randomness caps how well any model can do, and makes food identity (category, "
             "shelf life) and recent eating habits most of what is predictable. Removing purchased quantity costs "
             "very little, as the comparison shows. On real household data the model has to be re-checked.")


def render(result: dict, *, source: str) -> None:

    chosen = result["comparison"][result["comparison"]["Features"] == "All features"].iloc[0]
    section("Which purchases are likely to be wasted?",
            f"High waste = more than {HIGH_WASTE_PCT:.0f}% of a purchase thrown away "
            f"({result['positive_rate'] * 100:.1f}% of {'records' if source == 'demo' else 'your resolved purchases'})")
    kpi_row([("Selected model", chosen["Model"]), ("ROC-AUC", f"{chosen['ROC_AUC']:.3f}",
              "Chance that a random high-waste purchase scores above a random normal one (0.5 = guessing)."),
             ("Recall", f"{chosen['Recall']:.2f}", "Share of high-waste purchases caught."),
             ("Precision", f"{chosen['Precision']:.2f}", "Share of alerts that really were high waste."),
             ("F1", f"{chosen['F1']:.2f}")])
    st.caption(f"Trained on {result['train_rows']:,} records before {result['cutoff']:%d %b %Y}, tested on "
               f"{result['test_rows']:,} later ones. Features known at purchase time only: shelf life, category, "
               "quantity bought, the food's recent consumption rate and day of week. Class weights balance the "
               f"rarer high-waste class. The alert threshold ({chosen['Threshold']:.2f}) is the highest that still "
               f"catches {TARGET_RECALL:.0%} of high-waste records on a validation slice of the training period: "
               "missing waste costs more than a false alarm.")
    comparison = result["comparison"][["Model", "Features", "ROC_AUC", "Precision", "Recall", "F1", "Threshold"]]
    section("With and without purchased quantity", "Test-period scores of all four variants")
    table(comparison, {"ROC_AUC": number("ROC-AUC", "%.3f"), "Precision": number("Precision", "%.3f"),
                       "Recall": number("Recall", "%.3f"), "F1": number("F1", "%.3f"),
                       "Threshold": number("Threshold", "%.2f")}, max_rows=None)
    with_qty = result["comparison"][result["comparison"]["Features"] == "All features"]["ROC_AUC"].max()
    without = result["comparison"][result["comparison"]["Features"] != "All features"]["ROC_AUC"].max()
    st.markdown(f"Dropping purchased quantity changes the best ROC-AUC from {with_qty:.3f} to {without:.3f}: "
                f"that one feature accounts for {max(with_qty - without, 0):.3f} of the score.")
    if source == "demo":
        st.caption(DEMO_NOTE)
    left, right = st.columns(2, gap="large")
    with left:
        section("Confusion matrix", f"{chosen['Model']}, test period")
        matrix = pd.DataFrame({"": ["Actually high waste", "Actually not"],
                               "Alerted": [chosen["TP"], chosen["FP"]], "Not alerted": [chosen["FN"], chosen["TN"]]})
        table(matrix, {"Alerted": number("Alert raised", "%d"), "Not alerted": number("No alert", "%d")})
    with right:
        if "importance" in result:
            section("What drives the prediction", "Permutation importance on the test period (drop in ROC-AUC)")
            charts.bar(result["importance"], "Feature", "Importance", value_title="Drop in ROC-AUC when shuffled",
                       value_format=".3f", height=220)
            st.caption(top_feature_sentence(result["importance"], "ROC-AUC"))
