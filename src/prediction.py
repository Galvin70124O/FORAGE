"""Time-aware consumption forecasting for FORAGE's demo dataset.

Run from the project root with:
    python src/prediction.py

The target is Quantity_Consumed for each food on the next day. These are
one-step-ahead forecasts: the features for day t include the actual
consumption on day t-1. Two baselines (yesterday's value and a 7-day moving
average) are compared with Linear Regression and Random Forest on a later,
unseen period. The best model is whichever has the lowest test MAE.
"""

from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "cleaned_food_data.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "predictions"
TARGET = "Quantity_Consumed"

NUMERIC_FEATURES = [
    "Lag_1_Consumption", "Lag_7_Consumption", "Rolling_Mean_7",
    "Month", "Is_Weekend", "Is_Festival",
]
CATEGORICAL_FEATURES = ["Day_of_Week", "Food", "Category"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES

# Baselines need no fitting: each is a feature column that already holds the
# forecast. Both columns are built only from earlier days.
NAIVE_BASELINE = "Naive (yesterday's value)"
MOVING_AVERAGE_BASELINE = "7-day moving average"
DEMO_BASELINES = {NAIVE_BASELINE: "Lag_1_Consumption", MOVING_AVERAGE_BASELINE: "Rolling_Mean_7"}


def load_data(path=DATA_PATH):
    """Load the project-standard cleaned dataset without modifying it."""
    required_columns = {"Date", "Food", "Category", TARGET, "Is_Festival"}
    df = pd.read_csv(path, parse_dates=["Date"])
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"Cleaned dataset is missing: {sorted(missing_columns)}")
    return df.sort_values(["Food", "Date"]).reset_index(drop=True)


def create_forecasting_features(df):
    """Create only features that would be known when forecasting each row.

    Lag and rolling features are shifted by one day within each food, so a row
    never sees the consumption value it is trying to predict. Calendar fields
    are known in advance; Food and Category are stable item descriptors.
    """
    features = df.sort_values(["Food", "Date"]).copy()
    grouped_consumption = features.groupby("Food", group_keys=False)[TARGET]
    features["Lag_1_Consumption"] = grouped_consumption.shift(1)
    features["Lag_7_Consumption"] = grouped_consumption.shift(7)
    features["Rolling_Mean_7"] = grouped_consumption.transform(
        lambda values: values.shift(1).rolling(window=7, min_periods=7).mean()
    )
    features["Day_of_Week"] = features["Date"].dt.day_name()
    features["Month"] = features["Date"].dt.month
    features["Is_Weekend"] = (features["Date"].dt.dayofweek >= 5).astype(int)

    # The first seven dates of every food lack a full week of history.
    return features.dropna(subset=["Lag_1_Consumption", "Lag_7_Consumption", "Rolling_Mean_7"])


def chronological_split(df, test_fraction=0.20):
    """Split by date: train only on earlier dates and test on later dates."""
    dates = sorted(df["Date"].unique())
    if len(dates) < 2:
        raise ValueError("A chronological split needs at least two distinct dates.")
    split_index = min(max(int(len(dates) * (1 - test_fraction)), 1), len(dates) - 1)
    cutoff_date = pd.Timestamp(dates[split_index])
    train_df = df[df["Date"] < cutoff_date].copy()
    test_df = df[df["Date"] >= cutoff_date].copy()
    return train_df, test_df, cutoff_date


def evaluate_predictions(actual, predicted):
    """MAE, RMSE and R² of one set of held-out predictions (R² is undefined below two points)."""
    return {
        "MAE": float(mean_absolute_error(actual, predicted)),
        "RMSE": float(mean_squared_error(actual, predicted) ** 0.5),
        "R2": float(r2_score(actual, predicted)) if len(actual) >= 2 else float("nan"),
    }


def build_models(numeric_features, categorical_features):
    """Preprocessing + model pipelines; preprocessing is fit on training data only."""
    linear_preprocessor = ColumnTransformer([
        ("numeric", StandardScaler(), numeric_features),
        ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical_features),
    ])
    forest_preprocessor = ColumnTransformer([
        ("numeric", "passthrough", numeric_features),
        ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical_features),
    ])
    return {
        "Linear Regression": Pipeline([
            ("preprocessor", linear_preprocessor),
            ("model", LinearRegression()),
        ]),
        "Random Forest": Pipeline([
            ("preprocessor", forest_preprocessor),
            ("model", RandomForestRegressor(
                n_estimators=200, random_state=42, n_jobs=-1, min_samples_leaf=2
            )),
        ]),
    }


def evaluate_models(train_df, test_df, target, features, models, baselines, *, clip_at_zero=False):
    """Fit every model on the training period and score all candidates on the test period.

    Returns (comparison, predictions). `comparison` has one row per candidate
    with its type (Baseline/Model) and test-set MAE, RMSE and R², ordered best
    first. `predictions` maps each candidate name to its test-set predictions.
    """
    predictions = {name: test_df[column].astype(float) for name, column in baselines.items()}
    for name, model in models.items():
        model.fit(train_df[features], train_df[target])
        predicted = pd.Series(model.predict(test_df[features]), index=test_df.index)
        predictions[name] = predicted.clip(lower=0) if clip_at_zero else predicted
    rows = [{"Model": name, "Type": "Baseline" if name in baselines else "Model",
             **evaluate_predictions(test_df[target], values)} for name, values in predictions.items()]
    comparison = pd.DataFrame(rows).sort_values(["MAE", "RMSE"]).reset_index(drop=True)
    return comparison, predictions


def select_best_model(comparison):
    """Lowest test MAE wins (ties broken by RMSE); never a fixed choice."""
    return comparison.sort_values(["MAE", "RMSE"]).iloc[0]["Model"]


def best_baseline(comparison):
    baselines = comparison[comparison["Type"] == "Baseline"]
    return baselines.sort_values(["MAE", "RMSE"]).iloc[0] if not baselines.empty else None


def run_demo_forecast(raw_df=None):
    """Evaluate all candidates on the demo data. Returns a dict used by the app and the CLI."""
    raw_df = load_data() if raw_df is None else raw_df
    featured = create_forecasting_features(raw_df)
    train_df, test_df, cutoff = chronological_split(featured)
    models = build_models(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
    comparison, predictions = evaluate_models(
        train_df, test_df, TARGET, FEATURE_COLUMNS, models, DEMO_BASELINES)
    best = select_best_model(comparison)
    tested = test_df[["Date", "Food", "Category", "Quantity_Unit", TARGET]].copy() \
        if "Quantity_Unit" in test_df else test_df[["Date", "Food", "Category", TARGET]].copy()
    for name, values in predictions.items():
        tested[name] = values
    return {
        "comparison": comparison, "tested": tested, "best_model": best, "cutoff": cutoff,
        "train_rows": len(train_df), "test_rows": len(test_df),
        "train_start": train_df["Date"].min(), "test_end": test_df["Date"].max(),
        "models": models, "test_features": test_df[FEATURE_COLUMNS + [TARGET]],
    }


def plot_best_model(tested, best_model_name):
    """Save a matplotlib actual-vs-predicted plot for the highest-volume food."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_food = tested.groupby("Food")[TARGET].sum().idxmax()
    plot_data = tested[tested["Food"] == plot_food].sort_values("Date")
    plt.figure(figsize=(11, 5))
    plt.plot(plot_data["Date"], plot_data[TARGET], label="Actual", marker="o", markersize=3)
    plt.plot(plot_data["Date"], plot_data[best_model_name], label="Predicted", marker="o", markersize=3)
    plt.title(f"{best_model_name}: actual vs predicted consumption for {plot_food}")
    plt.xlabel("Date")
    plt.ylabel("Quantity consumed")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    output_path = OUTPUT_DIR / "best_model_actual_vs_predicted.png"
    plt.savefig(output_path, dpi=150)
    plt.close()
    return output_path, plot_food


def main():
    result = run_demo_forecast()
    comparison, cutoff = result["comparison"], result["cutoff"]
    plot_path, plot_food = plot_best_model(result["tested"], result["best_model"])
    print("FORAGE CONSUMPTION FORECASTING (demo data, one-step-ahead)")
    print(f"Chronological split: train before {cutoff:%Y-%m-%d}; test from {cutoff:%Y-%m-%d}")
    print(f"Training rows: {result['train_rows']:,} | Test rows: {result['test_rows']:,}")
    print("\nMODEL COMPARISON (lower MAE/RMSE and higher R2 are better)")
    print(comparison.round(4).to_string(index=False))
    print(f"\nBest model: {result['best_model']} (lowest test MAE)")
    print(f"Actual-vs-predicted plot for {plot_food}: {plot_path}")


if __name__ == "__main__":
    main()
