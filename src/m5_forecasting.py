"""Leakage-safe, chronological M5 retail-demand model evaluation.

One-step-ahead: features for day t use sales up to day t-1. Price gaps are
filled with the training-period median only.
"""
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression

from prediction import chronological_split, evaluate_models, select_best_model

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "real" / "m5" / "m5_food_demand.csv"
TARGET = "Quantity_Sold"
FEATURES = ["Lag_1_Sales", "Lag_7_Sales", "Rolling_7_Sales", "Day_Number", "Month", "Price"]
M5_BASELINES = {"Naive (yesterday's value)": "Lag_1_Sales", "7-day moving average": "Rolling_7_Sales"}


def create_m5_features(df: pd.DataFrame) -> pd.DataFrame:
    """Shifted lag/rolling sales per item and store; rows without a full week of history are dropped."""
    required = {"Date", "Product_ID", "Store_ID", TARGET, "Month", "Price"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"M5 extract is missing required columns: {sorted(missing)}")
    data = df.sort_values(["Product_ID", "Store_ID", "Date"]).copy()
    group = data.groupby(["Product_ID", "Store_ID"], group_keys=False, observed=True)[TARGET]
    data["Lag_1_Sales"] = group.shift(1)
    data["Lag_7_Sales"] = group.shift(7)
    data["Rolling_7_Sales"] = group.transform(lambda x: x.shift(1).rolling(7, min_periods=7).mean())
    data["Day_Number"] = data["Date"].dt.dayofweek
    data["Price"] = data["Price"].astype(float)
    return data.dropna(subset=["Lag_1_Sales", "Lag_7_Sales", "Rolling_7_Sales"]).copy()


def impute_price(train: pd.DataFrame, test: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, float]:
    """Fill missing prices in both periods with the median of the training period only."""
    median = train["Price"].median()
    median = 0.0 if pd.isna(median) else float(median)
    return train.assign(Price=train["Price"].fillna(median)), test.assign(Price=test["Price"].fillna(median)), median


def m5_models() -> dict:
    return {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(n_estimators=120, min_samples_leaf=2, random_state=42, n_jobs=-1),
    }


def forecast_retail_demand(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Evaluate two baselines and two models on a later, unseen M5 period."""
    data = create_m5_features(df)
    if len(data) < 30:
        raise ValueError("The M5 derived extract has insufficient history for forecasting.")
    train, test, cutoff = chronological_split(data)
    train, test, price_median = impute_price(train, test)
    models = m5_models()
    comparison, predictions = evaluate_models(train, test, TARGET, FEATURES, models, M5_BASELINES, clip_at_zero=True)
    best_model = select_best_model(comparison)
    test = test.copy()
    for name, values in predictions.items():
        test[name] = values
    test["Predicted_Sales"] = predictions[best_model]
    metadata = {"cutoff": cutoff, "best_model": best_model, "features": FEATURES,
                "train_rows": len(train), "test_rows": len(test), "price_median": price_median}
    return test, data, comparison, metadata
