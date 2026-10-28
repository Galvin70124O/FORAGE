"""Forecasting: next-day and 7-day models against baselines, ranked by rolling-origin backtests."""

import pandas as pd
import streamlit as st

from prediction import TARGET
from services.data import (
    FOLD_DAYS,
    FOLDS,
    demo_forecast,
    demo_rolling,
    demo_week,
    forecaster_explanations,
    m5_forecast,
    m5_rolling,
    m5_week,
)
from ui import charts
from ui.components import (
    empty_state,
    fmt_date,
    kpi_row,
    methods,
    number,
    section,
    table,
)
from views.common import STAMP_NOTE, begin, demo_demand_cards, not_available

ONE_STEP = ("Next-day forecasts are one-step-ahead: the prediction for each day uses the actual figure from the day "
            "before (and the week before), so they measure how well a model tracks tomorrow's demand.")
SEVEN_DAY = ("7-day forecasts are made at the end of a day for the total of the next seven days, using only what is "
             "known that evening (direct strategy). Training forecasts whose 7 days overlap the test period are "
             "left out.")
HIGHLIGHT = "font-weight: 600; background-color: rgba(63, 135, 99, 0.16)"
OFFLINE_ITEMS = "Per-item detail was computed offline on the full dataset; online the page shows aggregates."


def highlight(frame: pd.DataFrame, best: str, formats: dict) -> "pd.io.formats.style.Styler":
    return frame.style.format(formats).apply(
        lambda row: [HIGHLIGHT if row["Model"] == best else "" for _ in row], axis=1)


def metrics_table(comparison: pd.DataFrame, best: str, unit: str) -> None:
    """Single test period: MAE, RMSE, R² per model with the selected one highlighted."""
    shown = comparison.rename(columns={"R2": "R²"})[["Model", "Type", "MAE", "RMSE", "R²"]]
    st.dataframe(highlight(shown, best, {"MAE": "{:.3f}", "RMSE": "{:.3f}", "R²": "{:.3f}"}), hide_index=True,
                 width="stretch", height="content", column_config={
                     "MAE": st.column_config.NumberColumn("MAE", help=f"Mean absolute error, in {unit}."),
                     "RMSE": st.column_config.NumberColumn("RMSE", help=f"Root mean squared error, in {unit}."),
                     "R²": st.column_config.NumberColumn("R²", help="Share of variation explained.")})
    st.caption(f"Highlighted: the selected model. MAE and RMSE are in {unit}.")


def rolling_table(summary: pd.DataFrame, best: str, unit: str) -> None:
    shown = summary[["Model", "Type", "MAE_mean", "MAE_std", "RMSE_mean", "RMSE_std", "R2_mean", "R2_std"]]
    formats = {c: "{:.3f}" for c in shown.columns if c not in ("Model", "Type")}
    st.dataframe(highlight(shown, best, formats), hide_index=True, width="stretch", height="content",
                 column_config={"MAE_mean": st.column_config.NumberColumn("MAE mean", help=f"In {unit}; lower is better."),
                                "MAE_std": "± std", "RMSE_mean": "RMSE mean", "RMSE_std": "± std",
                                "R2_mean": "R² mean", "R2_std": "± std"})
    st.caption(f"Mean and standard deviation over {FOLDS} rolling folds of {FOLD_DAYS} days each. Highlighted: "
               f"the selected model (lowest mean MAE). MAE and RMSE are in {unit}.")


def reading(summary: pd.DataFrame, best: str, unit: str, horizon: str) -> str:
    rows = summary.set_index("Model")
    chosen = rows.loc[best]
    if chosen["Type"] == "Baseline":
        models = rows[rows["Type"] == "Model"]
        runner = models["MAE_mean"].idxmin()
        return (f"No model beat the simplest approach for {horizon}: the {best.lower()} baseline has the lowest mean "
                f"error ({chosen['MAE_mean']:.3f} {unit}), ahead of {runner} ({models.loc[runner, 'MAE_mean']:.3f}). "
                "FORAGE therefore uses the baseline. A model with more information (prices, promotions, events) "
                "would be needed to do better.")
    baselines = rows[rows["Type"] == "Baseline"]
    gains = [f"{(b['MAE_mean'] - chosen['MAE_mean']) / b['MAE_mean'] * 100:.0f}% lower than the {name.lower()}"
             for name, b in baselines.iterrows()]
    text = (f"For {horizon}, {best} is off by {chosen['MAE_mean']:.3f} {unit} on average across folds, "
            + " and ".join(gains) + ".")
    others = rows[(rows["Type"] == "Model") & (rows.index != best)]
    if not others.empty:
        runner = others["MAE_mean"].idxmin()
        gap = others.loc[runner, "MAE_mean"] - chosen["MAE_mean"]
        if gap < max(chosen["MAE_std"], others.loc[runner, "MAE_std"]):
            text += (f" {runner} is within one fold-to-fold standard deviation ({gap:.3f} worse), so the two are "
                     "practically tied; FORAGE picks the lower mean MAE.")
        if rows["RMSE_mean"].idxmin() == runner:
            text += f" {runner} has the lower RMSE, so it makes fewer large misses."
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


def selected_kpis(summary: pd.DataFrame, best: str, unit: str) -> None:
    rows = summary.set_index("Model")
    chosen = rows.loc[best]
    baseline = rows[rows["Type"] == "Baseline"].sort_values("MAE_mean").iloc[0]
    st.markdown(f"Selected model: **{best}** (lowest mean MAE over {FOLDS} rolling folds)")
    kpi_row([
        ("MAE", f"{chosen['MAE_mean']:.3f} ± {chosen['MAE_std']:.3f}", f"Mean ± std across folds, in {unit}."),
        ("RMSE", f"{chosen['RMSE_mean']:.3f} ± {chosen['RMSE_std']:.3f}"),
        ("R²", f"{chosen['R2_mean']:.3f} ± {chosen['R2_std']:.3f}"),
        ("MAE vs best baseline", "Baseline selected" if chosen["Type"] == "Baseline" else
         f"{(chosen['MAE_mean'] - baseline['MAE_mean']) / baseline['MAE_mean'] * 100:+.0f}%",
         f"Compared with the {baseline.name.lower()} baseline. Negative means lower error."),
    ])


source, df = begin("Forecasting", "How accurately demand can be predicted for tomorrow and for the next 7 days, "
                   "scored on periods the models never saw and compared with simple baselines.")
methods(['Models learn from earlier days and are scored on later days they never saw. MAE is the typical error, RMSE punishes big misses, R² is the share of variation explained (1 = perfect).',
         "Rolling origin repeats this with 5 moving cut-offs; the lowest mean MAE wins. Baselines (yesterday's value, averages) show whether a model adds anything at all."])

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
            section("Period-level forecasts of daily use",
                    f"Expanding window: each of {int(comparison['n'].iloc[0])} later periods is scored using only the "
                    "periods before it")
            metrics_table(comparison.drop(columns="n"), comparison.iloc[0]["Model"], "your units per day")
            st.write(f"Your 7-day buy list multiplies the {comparison.iloc[0]['Model'].lower()} by 7; it is the more "
                     "accurate of the two on your own history so far.")
    else:
        if source == "m5":
            tested, _, _, meta = m5_forecast()
            per_fold, summary = m5_rolling()
            week, cutoff = m5_week(), meta["cutoff"]
            unit, actual = "units sold per item-day", "Quantity_Sold"
            # Online only department totals are published; item-level predictions stay offline.
            key, label = ("Product_ID", "Item") if "Product_ID" in tested.columns else ("Department", "Department")
            week_unit, y_title = "units per item-week", "Units sold per day"
            features = "yesterday's and last week's sales, the 7-day average, weekday, month and price"
        else:
            result = demo_forecast()
            tested, cutoff = result["tested"], result["cutoff"]
            per_fold, summary = demo_rolling()
            week = demo_week()
            unit, actual, key, label = "recorded units (kg, L, dozen, loaf or pack)", TARGET, "Food", "Food"
            week_unit, y_title = "recorded units per food-week", "Quantity consumed (recorded unit)"
            features = ("yesterday's and last week's consumption, the 7-day average, weekday, month, weekend, "
                        "festival flag, food and category")
        best = summary.iloc[0]["Model"]

        day_tab, week_tab, folds_tab, explain_tab = st.tabs(["Next day", "Next 7 days", "Rolling backtest", "Explanations"])
        with day_tab:
            if source == "demo":
                section("Tomorrow at a glance", "The 8 foods with the highest predicted demand, from the selected "
                        "model refit on all history (the same forecasts as the purchase plan)")
                demo_demand_cards(limit=8)
                st.caption(STAMP_NOTE + " Every food is on the Recommendations page.")
            selected_kpis(summary, best, unit)
            st.info(ONE_STEP)
            section("Model comparison", f"{FOLDS} rolling folds covering {fmt_date(per_fold['Cutoff'].min())} "
                    f"to {fmt_date(tested['Date'].max())}")
            rolling_table(summary, best, unit)
            st.markdown("**What this means:** " + reading(summary, best, unit, "the next day"))
            st.caption(f"Inputs: {features}. Lag and average inputs only use earlier days."
                       + (" R² is pooled across foods with different typical quantities, so part of it reflects "
                          "differences between foods rather than day-to-day accuracy." if source != "m5" else ""))
            section("Actual against predicted", f"Final test period from {fmt_date(cutoff)}; the dashed line is "
                    "the selected model")
            if key == "Department":
                st.caption("Department totals (sum of item-level actuals and predictions). " + OFFLINE_ITEMS)
            actual_vs_predicted(tested, key, actual, best, label, y_title, f"forecast_item_{source}")

        with week_tab:
            selected_kpis(week["rolling"], week["best"], week_unit)
            st.info(SEVEN_DAY)
            section("Model comparison", "Baselines: the last 7 days' total, and the average week of the last 4")
            rolling_table(week["rolling"], week["best"], week_unit)
            st.markdown("**What this means:** " + reading(week["rolling"], week["best"], week_unit, "the next 7 days"))
            st.caption(f"Final test period from {fmt_date(week['cutoff'])}: {week['train_rows']:,} training and "
                       f"{week['test_rows']:,} test forecasts. Weekly purchase plans and the weekly backtest use "
                       f"{week['best']}.")
            section("Actual against predicted 7-day totals", "Each point is a forecast made on that date for the "
                    "following 7 days")
            if key == "Department":
                st.caption("Department totals. " + OFFLINE_ITEMS)
            actual_vs_predicted(week["test"], key, "Target_7", week["best"], label, "Total over the next 7 days",
                                f"week_item_{source}")

        with folds_tab:
            section("Mean absolute error in each fold", f"Next-day models; each fold trains on all earlier days and is "
                    f"scored on the next {FOLD_DAYS}")
            pivot = per_fold.pivot_table(index=["Fold", "Cutoff"], columns="Model", values="MAE").reset_index()
            table(pivot, {"Fold": number("Fold", "%d"), "Cutoff": st.column_config.DateColumn("Test from", format="D MMM YYYY"),
                          **{m: number(m, "%.3f") for m in summary["Model"]}}, max_rows=None)
            baseline = summary[summary["Type"] == "Baseline"].iloc[0]["Model"]
            lines = per_fold[per_fold["Model"].isin([best, baseline])].assign(
                Fold=lambda d: "Fold " + d["Fold"].astype(str))
            charts.line(lines, "Fold", "MAE", x_title=None, y_title=f"MAE ({unit.split(' (')[0]})", series="Model",
                        order=[best, baseline], dashed=[baseline], x_type="O", zero=False, y_format=".3f", height=260)
            st.caption(f"The selected model ({best}) against the best baseline ({baseline}). Every fold is checked "
                       "for leakage in the test suite: training data ends before the fold's first test day.")

        with explain_tab:
            from explain import reading as error_reading
            from explain import sample, top_feature_sentence
            info = forecaster_explanations(source)
            name, (item_key, group_key) = info["model_name"], info["keys"]
            if info["selected_overall"] != name:
                st.caption(f"The selected forecaster is a baseline ({info['selected_overall']}), which has nothing to "
                           f"explain; this tab explains the best model, {name}.")
            left, right = st.columns(2, gap="large")
            with left:
                section(f"What {name} relies on", "Permutation importance on the final test period (rise in MAE)")
                charts.bar(info["importance"], "Feature", "Importance", value_title="Rise in MAE when shuffled",
                           value_format=".3f", height=260)
                st.caption(top_feature_sentence(info["importance"], "MAE"))
            with right:
                if "residuals" in info:
                    section("Residuals against predictions", "Actual − predicted; points above 0 were under-predicted")
                    charts.scatter(sample(info["residuals"]), "Predicted", "Residual",
                                   x_title=f"Predicted ({unit.split(' (')[0]})", y_title="Residual", label=item_key,
                                   height=260, label_extremes=0,
                                   tooltip=[f"{item_key}:N", charts.tip("Predicted", "Predicted"),
                                            charts.tip("Actual", "Actual"), charts.tip("Residual", "Residual")])
                else:
                    section("Distribution of residuals", "Actual − predicted per item-day; above 0 = under-predicted")
                    charts.histogram(info["residual_distribution"], "Residual", value_title="Residual (units)", bins=40,
                                     weight="Item_days", count_title="Item-days", height=260)
                    st.caption("Computed offline on the full dataset: the item-day residuals are not published.")
            reading_text = (info["reading"] if "reading" in info else
                            error_reading(info["residuals"], info["by_item"], item_key, unit))
            st.markdown("**Where it fails:** " + reading_text)
            left, right = st.columns(2, gap="large")
            with left:
                section(f"Error by {item_key.replace('_', ' ').lower()}", "MAE as % of that item's average demand")
                charts.bar(info["by_item"].head(15), item_key, "Relative_MAE", value_title="Typical error (% of average)",
                           value_format=".1f", height=300)
            with right:
                section(f"Error by {group_key.lower()}", "MAE as % of the group's average demand")
                charts.bar(info["by_group"], group_key, "Relative_MAE", value_title="Typical error (% of average)",
                           value_format=".1f", height=300)
