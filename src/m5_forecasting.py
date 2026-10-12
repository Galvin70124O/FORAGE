"""Leakage-safe, chronological M5 retail-demand model evaluation."""
from pathlib import Path

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "real" / "m5" / "m5_food_demand.csv"


def _metrics(actual, predicted):
    return {
        "MAE": float(mean_absolute_error(actual, predicted)),
        "RMSE": float(mean_squared_error(actual, predicted) ** 0.5),
        "R2": float(r2_score(actual, predicted)),
    }


def forecast_retail_demand(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    """Evaluate three models against a later, unseen M5 date period.

    Lag and rolling features are shifted per item/store before splitting.  Price
    imputation uses the training median only, so neither targets nor test-period
    information leak into model fitting.
    """
    required = {"Date", "Product_ID", "Store_ID", "Quantity_Sold", "Month", "Price"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"M5 extract is missing required columns: {sorted(missing)}")
    data = df.sort_values(["Product_ID", "Store_ID", "Date"]).copy()
    group = data.groupby(["Product_ID", "Store_ID"], group_keys=False)["Quantity_Sold"]
    data["Lag_1_Sales"] = group.shift(1)
    data["Lag_7_Sales"] = group.shift(7)
    data["Rolling_7_Sales"] = group.transform(lambda x: x.shift(1).rolling(7, min_periods=7).mean())
    data["Day_Number"] = data["Date"].dt.dayofweek
    data = data.dropna(subset=["Lag_1_Sales", "Lag_7_Sales", "Rolling_7_Sales"]).copy()
    if len(data) < 30:
        raise ValueError("The M5 derived extract has insufficient history for forecasting.")
    dates = sorted(data["Date"].unique())
    cutoff = pd.Timestamp(dates[int(len(dates) * .8)])
    train, test = data[data["Date"] < cutoff].copy(), data[data["Date"] >= cutoff].copy()
    if train.empty or test.empty:
        raise ValueError("The chronological M5 split produced an empty train or test period.")
    features = ["Lag_1_Sales", "Lag_7_Sales", "Rolling_7_Sales", "Day_Number", "Month", "Price"]
    price_median = train["Price"].median()
    price_median = 0.0 if pd.isna(price_median) else price_median
    train.loc[:, "Price"] = train["Price"].fillna(price_median)
    test.loc[:, "Price"] = test["Price"].fillna(price_median)

    predictions = {"Moving Average": test["Rolling_7_Sales"]}
    models = {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(n_estimators=120, min_samples_leaf=2, random_state=42, n_jobs=-1),
    }
    for name, model in models.items():
        model.fit(train[features], train["Quantity_Sold"])
        predictions[name] = pd.Series(model.predict(test[features]), index=test.index).clip(lower=0)

    comparison = pd.DataFrame(
        [{"Model": name, **_metrics(test["Quantity_Sold"], values)} for name, values in predictions.items()]
    ).sort_values("MAE").reset_index(drop=True)
    best_model = comparison.loc[0, "Model"]
    test = test.copy()
    test["Predicted_Sales"] = predictions[best_model]
    metadata = {"cutoff": cutoff, "best_model": best_model, "features": features}
    return test, data, comparison, metadata
