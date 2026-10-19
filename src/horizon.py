"""7-day-ahead forecasting with the direct strategy, and rolling-origin backtesting.

7-day forecast: at the end of day t (the forecast origin) predict the total
demand of days t+1 .. t+7 for each food or item. Every feature is computed
from days <= t only:
    Last_7     total of days t-6 .. t        (also the "last-week total" baseline)
    Prev_7     total of days t-13 .. t-7
    Avg_4w     total of days t-27 .. t / 4   (also the "4-week average" baseline)
    Weekday    day of week of the origin; Month of day t+1
A training origin is only used if its whole target window ends before the
test cutoff (t + 7 < cutoff), so no test-period demand reaches training.

Rolling origin: the last `folds` x `test_days` days are split into
consecutive test windows; each fold trains on everything before its window
(an expanding window, minus a gap for the 7-day target) and is scored on the
window. Models are ranked by mean MAE across folds.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from prediction import FOREST, evaluate_models

HORIZON = 7
WEEK_NUMERIC = ["Last_7", "Prev_7", "Avg_4w", "Weekday", "Month"]
WEEK_BASELINES = {"Last-week total": "Last_7", "4-week average": "Avg_4w"}


def weekly_frame(df: pd.DataFrame, key: str, target: str, *, date: str = "Date", static: list[str] = (),
                 horizon: int = HORIZON, keep_future: bool = False) -> pd.DataFrame:
    """One row per key per origin day with origin-time features and the next-`horizon`-day total.

    Origins in the last `horizon` days have no complete target; they are kept
    (with Target_7 = NaN) only when `keep_future` is set, for live forecasts.
    """
    rows = []
    for name, series in df.sort_values(date).groupby(key, observed=True):
        values = series.set_index(date)[target].astype(float)
        values = values.asfreq("D", fill_value=0.0) if len(values) > 1 else values
        frame = pd.DataFrame({date: values.index, key: name})
        frame["Last_7"] = values.rolling(7, min_periods=7).sum().to_numpy()
        frame["Prev_7"] = values.shift(7).rolling(7, min_periods=7).sum().to_numpy()
        frame["Avg_4w"] = (values.rolling(28, min_periods=28).sum() / 4).to_numpy()
        frame["Target_7"] = values[::-1].rolling(horizon, min_periods=horizon).sum()[::-1].shift(-1).to_numpy()
        for column in static:
            frame[column] = series[column].iloc[0]
        rows.append(frame)
    out = pd.concat(rows, ignore_index=True)
    out["Weekday"] = out[date].dt.dayofweek
    out["Month"] = (out[date] + pd.Timedelta(days=1)).dt.month
    required = ["Last_7", "Prev_7", "Avg_4w"] + ([] if keep_future else ["Target_7"])
    return out.dropna(subset=required).reset_index(drop=True)


def week_models(categorical: list[str]) -> dict:
    numeric = WEEK_NUMERIC
    linear = ColumnTransformer([("num", StandardScaler(), numeric),
                                *([("cat", OneHotEncoder(handle_unknown="ignore"), categorical)] if categorical else [])])
    forest = ColumnTransformer([("num", "passthrough", numeric),
                                *([("cat", OneHotEncoder(handle_unknown="ignore"), categorical)] if categorical else [])])
    return {
        "Linear Regression": Pipeline([("prep", linear), ("model", LinearRegression())]),
        "Random Forest": Pipeline([("prep", forest), ("model", RandomForestRegressor(**FOREST))]),
    }


def purged_split(frame: pd.DataFrame, cutoff, *, date: str = "Date", gap: int = HORIZON,
                 test_days: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train on origins whose target window ends before `cutoff`; test on origins from `cutoff`."""
    cutoff = pd.Timestamp(cutoff)
    train = frame[frame[date] + pd.Timedelta(days=gap) < cutoff]
    test = frame[frame[date] >= cutoff]
    if test_days is not None:
        test = test[test[date] < cutoff + pd.Timedelta(days=test_days)]
    return train.copy(), test.copy()


def fold_cutoffs(dates: pd.Series, folds: int, test_days: int) -> list[pd.Timestamp]:
    """Start dates of `folds` consecutive test windows of `test_days` ending at the last date."""
    last = pd.Timestamp(dates.max())
    return [last - pd.Timedelta(days=(folds - k) * test_days - 1) for k in range(folds)]


def rolling_origin(frame: pd.DataFrame, *, target: str, features: list[str], models_factory, baselines: dict,
                   folds: int = 5, test_days: int = 14, gap: int = 0, date: str = "Date",
                   clip_at_zero: bool = True, prepare=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Expanding-window evaluation. Returns (per-fold metrics, mean ± std per model, best first).

    `prepare(train, test)` runs inside each fold (e.g. imputation fitted on that fold's training rows).
    """
    rows = []
    for number, cutoff in enumerate(fold_cutoffs(frame[date], folds, test_days), start=1):
        train, test = purged_split(frame, cutoff, date=date, gap=gap, test_days=test_days)
        if train.empty or test.empty:
            continue
        if prepare is not None:
            train, test = prepare(train, test)
        comparison, _ = evaluate_models(train, test, target, features, models_factory(), baselines,
                                        clip_at_zero=clip_at_zero)
        comparison.insert(0, "Fold", number)
        comparison["Cutoff"] = cutoff
        comparison["Train_Rows"], comparison["Test_Rows"] = len(train), len(test)
        rows.append(comparison)
    per_fold = pd.concat(rows, ignore_index=True)
    summary = per_fold.groupby(["Model", "Type"]).agg(
        MAE_mean=("MAE", "mean"), MAE_std=("MAE", "std"), RMSE_mean=("RMSE", "mean"), RMSE_std=("RMSE", "std"),
        R2_mean=("R2", "mean"), R2_std=("R2", "std"), Folds=("Fold", "nunique")).reset_index()
    return per_fold, summary.sort_values(["MAE_mean", "RMSE_mean"]).reset_index(drop=True)


def evaluate_week(frame: pd.DataFrame, cutoff, categorical: list[str]) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Single purged split for the 7-day forecast: (comparison, test predictions, test rows)."""
    train, test = purged_split(frame, cutoff)
    features = WEEK_NUMERIC + categorical
    comparison, predictions = evaluate_models(train, test, "Target_7", features, week_models(categorical),
                                              WEEK_BASELINES, clip_at_zero=True)
    return comparison, predictions, test


def latest_week_forecast(frame_all: pd.DataFrame, model_name: str, categorical: list[str], key: str) -> pd.Series:
    """7-day forecast from the last origin of each key, using `model_name` refit on all complete targets."""
    features = WEEK_NUMERIC + categorical
    last = frame_all.sort_values("Date").groupby(key, observed=True).tail(1)
    if model_name in WEEK_BASELINES:
        return last.set_index(key)[WEEK_BASELINES[model_name]]
    model = week_models(categorical)[model_name]
    train = frame_all.dropna(subset=["Target_7"])
    model.fit(train[features], train["Target_7"])
    return pd.Series(np.clip(model.predict(last[features]), 0, None), index=last[key])
