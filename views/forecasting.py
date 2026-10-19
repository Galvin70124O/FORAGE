"""Forecasting: models against baselines on a held-out later period, with a plain-English reading."""

import pandas as pd
import streamlit as st

from prediction import TARGET, best_baseline
from services.data import demo_forecast, m5_forecast
from ui import charts
from ui.components import empty_state, fmt_date, kpi_row, section
from views.common import begin, not_available

ONE_STEP = ("These are one-step-ahead forecasts: the prediction for each day uses the actual figure from the day "
            "before (and the week before), so they measure how well a model tracks next-day demand, not how far "
            "ahead it can see.")


def metrics_table(comparison: pd.DataFrame, best: str, unit: str) -> None:
    shown = comparison.rename(columns={"R2": "R²"})[["Model", "Type", "MAE", "RMSE", "R²"]]
    styled = (shown.style
              .format({"MAE": "{:.3f}", "RMSE": "{:.3f}", "R²": "{:.3f}"})
              .apply(lambda row: ["font-weight: 600; background-color: rgba(57, 135, 229, 0.14)"
                                  if row["Model"] == best else "" for _ in row], axis=1))
    st.dataframe(styled, hide_index=True, width="stretch", height="content", column_config={
        "MAE": st.column_config.NumberColumn("MAE", help=f"Mean absolute error, in {unit}. Lower is better."),
        "RMSE": st.column_config.NumberColumn("RMSE", help=f"Root mean squared error, in {unit}. Penalises large misses."),
        "R²": st.column_config.NumberColumn("R²", help="Share of variation explained (1 is perfect, 0 equals predicting the mean)."),
    })
    st.caption(f"Highlighted: the selected model (lowest MAE on the test period). MAE and RMSE are in {unit}.")


def reading(comparison: pd.DataFrame, best: str, unit: str) -> str:
    rows = comparison.set_index("Model")
    best_row = rows.loc[best]
    baselines = rows[rows["Type"] == "Baseline"]
    if best_row["Type"] == "Baseline":
        return (f"No model beat the simplest approach. The {best.lower()} baseline had the lowest error "
                f"({best_row['MAE']:.3f} {unit} on average), so FORAGE uses it.")
    gains = [f"{(base['MAE'] - best_row['MAE']) / base['MAE'] * 100:.0f}% lower than the {name.lower()}"
             for name, base in baselines.iterrows()]
    text = (f"{best}'s next-day predictions are off by {best_row['MAE']:.3f} {unit} on average: "
            + " and ".join(gains) + ".")
    by_rmse = comparison.sort_values("RMSE").iloc[0]["Model"]
    if by_rmse != best:
        text += (f" {by_rmse} has the lower RMSE ({rows.loc[by_rmse, 'RMSE']:.3f} vs {best_row['RMSE']:.3f}) and "
                 f"higher R², so it makes fewer large misses; the two are close, and FORAGE ranks by MAE.")
    return text


def actual_vs_predicted(tested: pd.DataFrame, key: str, actual: str, best: str, label: str, y_title: str,
                        widget_key: str) -> None:
    options = sorted(tested[key].astype(str).unique())
    default = tested.groupby(key, observed=True)[actual].sum().idxmax()
    choice = st.selectbox(label, options, index=options.index(str(default)), key=widget_key)
    shown = tested[tested[key].astype(str) == choice].groupby("Date")[[actual, best]].sum().reset_index()
    long = shown.rename(columns={actual: "Actual", best: f"Predicted ({best})"}).melt(
        "Date", var_name="Series", value_name="Value")
    order = ["Actual", f"Predicted ({best})"]
    charts.line(long, "Date", "Value", x_title="Date", y_title=y_title, series="Series",
                order=order, dashed=[order[1]], height=320)


source, df = begin("Forecasting", "How accurately next-day demand can be predicted, measured on a later "
                   "period the models never saw, and compared with simple baselines.")

if df is not None:
    if source == "instacart":
        not_available(source, "Forecasting",
                      "Instacart orders only have a day-of-week and hour, not calendar dates, so there is no time "
                      "series to forecast.", alternatives=["demo", "m5", "personal"], key="forecast_switch")
    elif source == "personal":
        from pantry import period_forecast_evaluation, periods
        from services.personal import gate, personal_data
        from views.common import PERIOD_NOTE
        shown, reliable, note = gate("forecast")
        predictions, comparison = period_forecast_evaluation(periods(*personal_data()))
        st.info(PERIOD_NOTE)
        if not shown or comparison.empty:
            empty_state("Not enough of your data to evaluate a forecast",
                        f"{note} A forecast is scored on periods it has not seen, so each food needs at least two "
                        "completed pantry-check periods.", page="views/pantry.py", page_label="Do a pantry check")
        else:
            if not reliable:
                st.warning(note)
            section("Period-level forecasts of daily use", f"Scored on {int(comparison['n'].iloc[0])} later periods; "
                    "each prediction uses earlier periods only")
            metrics_table(comparison.drop(columns="n"), comparison.iloc[0]["Model"], "your units per day")
            st.write(f"Your buy list uses the {comparison.iloc[0]['Model'].lower()}, the more accurate of the two on "
                     "your own history so far.")
    else:
        if source == "m5":
            tested, _, comparison, meta = m5_forecast()
            best, cutoff = meta["best_model"], meta["cutoff"]
            train_rows, test_rows = meta["train_rows"], meta["test_rows"]
            unit, actual, key, label = "units sold per item-day", "Quantity_Sold", "Product_ID", "Item"
            y_title = "Units sold per day"
            features = "yesterday's and last week's sales, the 7-day average, weekday, month and price"
        else:
            result = demo_forecast()
            comparison, tested, best, cutoff = (result["comparison"], result["tested"], result["best_model"],
                                                result["cutoff"])
            train_rows, test_rows = result["train_rows"], result["test_rows"]
            unit, actual, key, label = "recorded units (kg, L, dozen, loaf or pack)", TARGET, "Food", "Food"
            y_title = "Quantity consumed (recorded unit)"
            features = "yesterday's and last week's consumption, the 7-day average, weekday, month, weekend, festival flag, food and category"

        best_row = comparison.set_index("Model").loc[best]
        baseline = best_baseline(comparison)
        st.markdown(f"Selected model: **{best}** (lowest error on the test period)")
        kpi_row([
            ("MAE", f"{best_row['MAE']:.3f}", f"Mean absolute error in {unit}."),
            ("RMSE", f"{best_row['RMSE']:.3f}"),
            ("R²", f"{best_row['R2']:.3f}"),
            ("MAE vs best baseline", f"{(best_row['MAE'] - baseline['MAE']) / baseline['MAE'] * 100:+.0f}%"
             if best_row["Type"] == "Model" else "Baseline selected",
             f"Change in MAE compared with the {baseline['Model'].lower()} baseline. Negative means lower error."),
        ])
        st.info(ONE_STEP)

        left, right = st.columns([1.15, 1], gap="large")
        with left:
            section("Model comparison", f"Test period: {fmt_date(cutoff)} to {fmt_date(tested['Date'].max())}")
            metrics_table(comparison, best, unit)
        with right:
            section("What this means")
            st.write(reading(comparison, best, unit))
            st.caption(f"Trained on {train_rows:,} rows before {fmt_date(cutoff)}; tested on {test_rows:,} rows "
                       f"from {fmt_date(cutoff)}. Inputs: {features}. Lag and average inputs only use earlier days.")
            if source != "m5":
                st.caption("R² is pooled across foods with different typical quantities, so part of it reflects "
                           "differences between foods rather than day-to-day accuracy.")

        section("Actual against predicted", "Test period only; the dashed line is the selected model")
        actual_vs_predicted(tested, key, actual, best, label, y_title, f"forecast_item_{source}")
