"""Data-source registry, cached loaders and cached model results shared by every page."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from clean_data import RAW_DATA_PATH, clean_records
from dataset_registry import get_dataset
from ui.components import fmt_date

# Model modules (scikit-learn, scipy) are imported inside the functions that need them, so pages
# that only show data start quickly on a cold start.

SOURCES = {
    "demo": "Demo data",
    "personal": "My data",
    "m5": "M5 (Walmart)",
    "instacart": "Instacart",
}
HOUSEHOLD_SOURCES = {"demo", "personal"}
M5_PATH = get_dataset("m5")["path"]
INSTACART_PATH = get_dataset("instacart")["path"]
DEMO_PATH = get_dataset("demo")["path"]
EXTRACT_COMMAND = "python src/real_data_processor.py"


@st.cache_resource(show_spinner=False)
def _artifacts() -> dict | None:
    from artifacts import load
    return load()


def _precomputed(key: str | None):
    """A precomputed demo result (see src/artifacts.py), or None to compute it live."""
    results = _artifacts() if key else None
    return None if results is None else results.get(key)


def current_source() -> str:
    return st.session_state.get("source", "demo")


def set_source(key: str) -> None:
    st.session_state["source"] = key


@st.cache_data(show_spinner="Loading demo data...")
def load_demo() -> pd.DataFrame:
    return pd.read_csv(DEMO_PATH, parse_dates=["Date", "Estimated_Expiry_Date"])


@st.cache_data(show_spinner="Loading the M5 extract...")
def load_m5() -> pd.DataFrame:
    return pd.read_csv(M5_PATH, parse_dates=["Date"], dtype={
        "Product_ID": "category", "Store_ID": "category", "Department": "category",
        "Category": "category", "Quantity_Sold": "int16", "Price": "float32",
        "Weekday": "category", "Month": "int8", "Event_Name": "category", "Event_Type": "category",
    })


@st.cache_data(show_spinner="Loading the Instacart extract...")
def load_instacart() -> pd.DataFrame:
    return pd.read_csv(INSTACART_PATH, dtype={
        "Order_ID": "int32", "User_ID": "int32", "Order_Set": "category",
        "Order_Number": "int16", "Order_Day_Of_Week": "int8", "Order_Hour": "int8",
        "Days_Since_Prior_Order": "float32", "Product_ID": "int32", "Product_Name": "category",
        "Aisle": "category", "Department": "category", "Add_To_Cart_Order": "int16", "Reordered": "int8",
    })


def load(source: str) -> pd.DataFrame | None:
    """The selected source's records, or None when a public extract has not been built."""
    if source == "demo":
        return load_demo()
    if source == "personal":
        from services.personal import personal_frame
        frame = personal_frame()
        return pd.DataFrame() if frame is None else frame
    if source == "m5":
        return load_m5() if M5_PATH.exists() else None
    return load_instacart() if INSTACART_PATH.exists() else None


def quality_report(source: str) -> dict | None:
    path = (M5_PATH if source == "m5" else INSTACART_PATH).parent / "quality_report.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def describe(source: str, df: pd.DataFrame | None) -> str:
    """One line for the data-source label under each page title."""
    if df is None:
        return "available in the local version"
    if source == "demo":
        return f"synthetic household records · {len(df):,} rows · {fmt_date(df['Date'].min())} to {fmt_date(df['Date'].max())}"
    if source == "personal":
        if df.empty:
            return "no completed pantry-check periods yet"
        return (f"your purchases and pantry checks · {len(df):,} food-periods · "
                f"{fmt_date(df['Period_Start'].min())} to {fmt_date(df['Date'].max())}")
    if source == "m5":
        return (f"Walmart retail unit sales, store CA_1, top {df['Product_ID'].nunique()} food items · "
                f"{len(df):,} rows · {fmt_date(df['Date'].min())} to {fmt_date(df['Date'].max())}")
    return (f"online grocery orders from users 1–2,000 · {len(df):,} order lines · "
            f"{df['Order_ID'].nunique():,} orders · no calendar dates")


@st.cache_resource(show_spinner="Evaluating forecasting models on the held-out period...")
def demo_forecast() -> dict:
    if (hit := _precomputed("demo_forecast")) is not None:
        return hit
    from prediction import run_demo_forecast
    return run_demo_forecast(load_demo())


@st.cache_resource(show_spinner="Evaluating M5 forecasting models on the held-out period...")
def m5_forecast():
    from m5_forecasting import forecast_retail_demand
    return forecast_retail_demand(load_m5())


@st.cache_resource(show_spinner="Building the purchase plan...")
def demo_recommendations():
    if (hit := _precomputed("demo_recommendations")) is not None:
        return hit
    from recommendations import generate_recommendations
    return generate_recommendations(load_demo(), best_next_day("demo"))


@st.cache_data
def demo_cleaning_summary() -> dict:
    return clean_records(pd.read_csv(RAW_DATA_PATH))[1]


@st.cache_data
def raw_demo() -> pd.DataFrame:
    return pd.read_csv(RAW_DATA_PATH)


@st.cache_resource(show_spinner="Simulating households over the test period...")
def demo_backtest() -> tuple[pd.DataFrame, pd.DataFrame, float, int]:
    """(summary, per-food results, recorded waste % in the data, days simulated) for the demo data."""
    if (hit := _precomputed("demo_backtest")) is not None:
        return hit
    from backtest import demo_frame, run_backtest, summarise
    from waste import unit_prices

    records, result, week = load_demo(), demo_forecast(), demo_week()
    weekly = week["test"].set_index(["Date", "Food"])[week["best"]]
    frame = demo_frame(records, result["tested"], best_next_day("demo"), week_forecasts=weekly,
                       unit_prices=unit_prices(records))
    results = run_backtest(frame)
    test = records[records["Date"] >= result["cutoff"]]
    reference = (test.groupby("Food")["Quantity_Wasted"].sum() / test.groupby("Food")["Quantity_Purchased"].sum()).mean() * 100
    return summarise(results), results, float(reference), int(frame["Date"].nunique())


@st.cache_data(show_spinner="Running hypothesis tests...")
def source_tests(source: str) -> list:
    """Hypothesis tests for a public or demo source (My data is computed per request)."""
    if (hit := _precomputed(f"source_tests_{source}" if source == "demo" else None)) is not None:
        return hit
    from hypothesis import household_tests, instacart_tests, m5_tests

    if source == "demo":
        return household_tests(load_demo())
    if source == "m5":
        return m5_tests(load_m5())
    return instacart_tests(load_instacart())


MESSY_SAMPLE = DEMO_PATH.parent / "samples" / "messy_food_data.csv"


@st.cache_data(show_spinner="Running the cleaning pipeline...")
def messy_sample_cleaning():
    """(raw messy sample, cleaned rows, per-rule summary, per-row audit log)."""
    messy = pd.read_csv(MESSY_SAMPLE)
    cleaned, summary, audit = clean_records(messy, audit=True)
    return messy, cleaned, summary, audit


# --- rolling-origin selection and 7-day forecasts (C5, C6) -----------------------
FOLDS, FOLD_DAYS = 5, 14


@st.cache_resource(show_spinner="Backtesting next-day models over 5 rolling folds...")
def demo_rolling():
    """(per-fold metrics, mean ± std per model) for next-day demo forecasts; best model first."""
    if (hit := _precomputed("demo_rolling")) is not None:
        return hit
    from horizon import rolling_origin
    from prediction import (CATEGORICAL_FEATURES, DEMO_BASELINES, FEATURE_COLUMNS, NUMERIC_FEATURES, TARGET,
                            build_models, create_forecasting_features)
    return rolling_origin(create_forecasting_features(load_demo()), target=TARGET, features=FEATURE_COLUMNS,
                          baselines=DEMO_BASELINES, folds=FOLDS, test_days=FOLD_DAYS,
                          models_factory=lambda: build_models(NUMERIC_FEATURES, CATEGORICAL_FEATURES))


@st.cache_resource(show_spinner="Backtesting M5 models over 5 rolling folds...")
def m5_rolling():
    from horizon import rolling_origin
    from m5_forecasting import FEATURES, M5_BASELINES, create_m5_features, impute_price, m5_models
    return rolling_origin(create_m5_features(load_m5()), target="Quantity_Sold", features=FEATURES,
                          baselines=M5_BASELINES, folds=FOLDS, test_days=FOLD_DAYS, models_factory=m5_models,
                          prepare=lambda train, test: impute_price(train, test)[:2])


def best_next_day(source: str) -> str:
    """The next-day model with the lowest mean MAE across rolling folds."""
    return (demo_rolling() if source == "demo" else m5_rolling())[1].iloc[0]["Model"]


def _week(df: pd.DataFrame, key: str, target: str, static: list[str], categorical: list[str], cutoff) -> dict:
    from horizon import WEEK_BASELINES, WEEK_NUMERIC, evaluate_week, latest_week_forecast, rolling_origin, week_models, weekly_frame
    frame_all = weekly_frame(df, key, target, static=static, keep_future=True)
    frame = frame_all.dropna(subset=["Target_7"])
    comparison, predictions, test = evaluate_week(frame, cutoff, categorical)
    per_fold, rolling = rolling_origin(frame, target="Target_7", features=WEEK_NUMERIC + categorical,
                                       baselines=WEEK_BASELINES, folds=FOLDS, test_days=FOLD_DAYS, gap=7,
                                       models_factory=lambda: week_models(categorical))
    best = rolling.iloc[0]["Model"]
    test = test.assign(**{name: values for name, values in predictions.items()})
    return {"comparison": comparison, "rolling": rolling, "per_fold": per_fold, "best": best, "test": test,
            "cutoff": cutoff, "latest": latest_week_forecast(frame_all, best, categorical, key),
            "train_rows": int((frame["Date"] + pd.Timedelta(days=7) < cutoff).sum()), "test_rows": len(test)}


@st.cache_resource(show_spinner="Evaluating 7-day forecasts...")
def demo_week() -> dict:
    if (hit := _precomputed("demo_week")) is not None:
        return hit
    from prediction import TARGET
    return _week(load_demo(), "Food", TARGET, ["Category", "Quantity_Unit"], ["Food", "Category"],
                 demo_forecast()["cutoff"])


@st.cache_resource(show_spinner="Evaluating M5 7-day forecasts...")
def m5_week() -> dict:
    return _week(load_m5().assign(Product_ID=lambda d: d["Product_ID"].astype(str)), "Product_ID",
                 "Quantity_Sold", [], [], m5_forecast()[3]["cutoff"])


# --- explanations and the waste-risk classifier (C7, C8) --------------------------
@st.cache_resource(show_spinner="Explaining the forecaster on held-out data...")
def forecaster_explanations(source: str) -> dict:
    """Permutation importance and residuals for the selected next-day model on the final test period."""
    if (hit := _precomputed(f"forecaster_explanations_{source}" if source == "demo" else None)) is not None:
        return hit
    from explain import error_by, importance, residual_frame
    from m5_forecasting import FEATURES as M5_FEATURES
    from prediction import FEATURE_COLUMNS, TARGET

    summary = (demo_rolling() if source == "demo" else m5_rolling())[1]
    models = summary[summary["Type"] == "Model"]
    best = models.iloc[0]["Model"]  # explain the best model even if a baseline was selected overall
    if source == "demo":
        result = demo_forecast()
        model, tested = result["models"][best], result["tested"]
        X, y = result["test_features"][FEATURE_COLUMNS], result["test_features"][TARGET]
        groups, keys = tested[["Food", "Category"]], ("Food", "Category")
        predicted = tested[best]
    else:
        tested, _, _, meta = m5_forecast()
        model = meta["models"][best]
        X, y = tested[M5_FEATURES], tested["Quantity_Sold"]
        groups, keys = tested[["Product_ID", "Department"]].astype(str), ("Product_ID", "Department")
        predicted = tested[best]
    residuals = residual_frame(y.reset_index(drop=True), predicted.reset_index(drop=True), groups.reset_index(drop=True))
    return {"model_name": best, "selected_overall": summary.iloc[0]["Model"],
            "importance": importance(model, X, y, scoring="neg_mean_absolute_error"),
            "residuals": residuals, "by_item": error_by(residuals, keys[0]), "by_group": error_by(residuals, keys[1]),
            "keys": keys}


@st.cache_resource(show_spinner="Training the waste-risk classifiers...")
def demo_classifier() -> dict:
    if (hit := _precomputed("demo_classifier")) is not None:
        return hit
    from explain import importance
    from waste_risk import evaluate
    result = evaluate(load_demo())
    model, features, _ = result["model"]
    result["importance"] = importance(model, result["test"][features], result["test"]["High_Waste"], scoring="roc_auc")
    return result


@st.cache_resource(show_spinner="Training the waste-risk classifiers on your purchases...", max_entries=16, ttl=3600)
def personal_classifier(purchases: pd.DataFrame, checks: pd.DataFrame) -> dict | None:
    """The classifier trained on the user's resolved purchases, or None when there are too few of each class."""
    from pantry import purchase_outcomes
    from waste_risk import add_features, evaluate
    outcomes = purchase_outcomes(purchases, checks).dropna(subset=["Waste_Percentage", "Expiry_Days"])
    labelled = add_features(outcomes) if not outcomes.empty else outcomes
    if len(labelled) < 30 or labelled["High_Waste"].sum() < 5 or (1 - labelled["High_Waste"]).sum() < 5:
        return None
    try:
        result = evaluate(outcomes)
    except ValueError:
        return None
    result.pop("fitted")  # keep only the chosen model
    return result


@st.cache_resource(show_spinner="Finding products bought together (FP-growth)...")
def instacart_rules():
    """(basket matrix shape, association rules) for the top 150 Instacart products."""
    from basket import baskets, find_rules
    matrix = baskets(load_instacart().assign(Product_Name=lambda d: d["Product_Name"].astype(str)), top_n=150)
    return matrix.shape, find_rules(matrix, min_support=0.005, min_lift=1.2)


@st.cache_resource(show_spinner="Scoring the purchase plan for waste risk...")
def demo_plan_with_risk() -> pd.DataFrame:
    """The next-day plan with the classifier's waste risk (%) and a "likely to be wasted" alert."""
    if (hit := _precomputed("demo_plan_with_risk")) is not None:
        return hit
    from waste_risk import planned_rows, score_purchases
    plan = demo_recommendations()[0]
    model_info = demo_classifier()["model"]
    rows = planned_rows(load_demo(), plan["Food"], plan["Recommended_Purchase_Quantity"].clip(lower=0.01),
                        plan["Forecast_Date"].iloc[0])
    scored = plan.assign(Waste_Risk=score_purchases(model_info, rows).to_numpy() * 100)
    likely = (scored["Waste_Risk"] >= model_info[2] * 100) & (scored["Recommended_Purchase_Quantity"] > 0)
    scored["Alerts"] = [
        ("likely to be wasted" if a == "No alert" else f"{a}; likely to be wasted") if flag else a
        for a, flag in zip(scored["Alerts"], likely)]
    return scored


def data_as_of(source: str) -> str:
    """Footer text: the last date covered by the selected source."""
    if source == "demo":
        return f"Data as of {fmt_date(load_demo()['Date'].max())}"
    if source == "m5":
        return f"Data as of {fmt_date(load_m5()['Date'].max())}" if M5_PATH.exists() else "Local version only"
    if source == "instacart":
        return "No calendar dates" if INSTACART_PATH.exists() else "Local version only"
    from services.personal import personal_data
    data = personal_data()
    if not data or (data[0].empty and data[1].empty):
        return "No entries yet"
    return f"Data as of {fmt_date(pd.concat([data[0]['date'], data[1]['date']]).max())}"
