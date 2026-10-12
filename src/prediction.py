"""Time-aware consumption forecasting for the Food Demand and Supply project.

Run from the project root with:
    python src/prediction.py

The target is Quantity_Consumed for each food on a future date.  The script
compares a seven-day moving-average baseline with Linear Regression and Random
Forest Regression.  It reads the cleaned data but never changes it.
"""

from pathlib import Path

import matplotlib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

# Save charts to files so the script also works in a terminal without a GUI.
matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "cleaned_food_data.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "predictions"
TARGET = "Quantity_Consumed"


def load_data():
    """Load the project-standard cleaned dataset without modifying it."""
    required_columns = {"Date", "Food", "Category", TARGET, "Is_Festival"}
    df = pd.read_csv(DATA_PATH, parse_dates=["Date"])
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise ValueError(f"Cleaned dataset is missing: {sorted(missing_columns)}")
    return df.sort_values(["Food", "Date"]).reset_index(drop=True)


def create_forecasting_features(df):
    """Create only features that would be known when forecasting each row.

    Lag and rolling features are shifted by one day for each food, so the model
    never sees the consumption value it is trying to predict. Calendar fields
    are known in advance; Food and Category are stable item descriptors.
    """
    features = df.copy()
    grouped_consumption = features.groupby("Food", group_keys=False)[TARGET]
    features["Lag_1_Consumption"] = grouped_consumption.shift(1)
    features["Lag_7_Consumption"] = grouped_consumption.shift(7)
    features["Rolling_Mean_7"] = grouped_consumption.transform(
        lambda values: values.shift(1).rolling(window=7, min_periods=7).mean()
    )

    # Recreate calendar fields from Date instead of relying on target-related data.
    features["Day_of_Week"] = features["Date"].dt.day_name()
    features["Month"] = features["Date"].dt.month
    features["Is_Weekend"] = (features["Date"].dt.dayofweek >= 5).astype(int)

    # The first seven dates for every food have insufficient history for a
    # seven-day prediction. Dropping them prevents incomplete historical data.
    return features.dropna(subset=["Lag_1_Consumption", "Lag_7_Consumption", "Rolling_Mean_7"])


def chronological_split(df, test_fraction=0.20):
    """Split by date: train only on earlier dates and test on later dates."""
    dates = sorted(df["Date"].unique())
    split_index = int(len(dates) * (1 - test_fraction))
    cutoff_date = dates[split_index]
    train_df = df[df["Date"] < cutoff_date].copy()
    test_df = df[df["Date"] >= cutoff_date].copy()
    return train_df, test_df, cutoff_date


def evaluate_predictions(actual, predicted):
    """Return the three metrics requested for model comparison."""
    return {
        "MAE": mean_absolute_error(actual, predicted),
        "RMSE": mean_squared_error(actual, predicted) ** 0.5,
        "R2": r2_score(actual, predicted),
    }


def build_models(numeric_features, categorical_features):
    """Build beginner-friendly preprocessing pipelines for the two ML models."""
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


def plot_best_model(test_df, predictions, best_model_name):
    """Plot test-period actual versus predicted consumption for one food item."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plot_food = (
        test_df.groupby("Food")[TARGET].sum().sort_values(ascending=False).index[0]
    )
    plot_data = test_df.loc[test_df["Food"] == plot_food, ["Date", TARGET]].copy()
    plot_data["Predicted_Consumption"] = predictions.loc[plot_data.index]
    plot_data = plot_data.sort_values("Date")

    plt.figure(figsize=(11, 5))
    plt.plot(plot_data["Date"], plot_data[TARGET], label="Actual", marker="o", markersize=3)
    plt.plot(
        plot_data["Date"], plot_data["Predicted_Consumption"],
        label="Predicted", marker="o", markersize=3,
    )
    plt.title(f"{best_model_name}: Actual vs Predicted Consumption for {plot_food}")
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
    """Train, evaluate, compare, and plot the three forecasting approaches."""
    raw_df = load_data()
    df = create_forecasting_features(raw_df)
    train_df, test_df, cutoff_date = chronological_split(df)

    numeric_features = [
        "Lag_1_Consumption", "Lag_7_Consumption", "Rolling_Mean_7",
        "Month", "Is_Weekend", "Is_Festival",
    ]
    categorical_features = ["Day_of_Week", "Food", "Category"]
    feature_columns = numeric_features + categorical_features

    x_train, y_train = train_df[feature_columns], train_df[TARGET]
    x_test, y_test = test_df[feature_columns], test_df[TARGET]

    # Baseline: a historical seven-day mean, already shifted before prediction.
    all_predictions = {"Moving Average": test_df["Rolling_Mean_7"]}
    models = build_models(numeric_features, categorical_features)
    for model_name, model in models.items():
        model.fit(x_train, y_train)
        all_predictions[model_name] = pd.Series(model.predict(x_test), index=x_test.index)

    comparison_rows = []
    for model_name, predictions in all_predictions.items():
        comparison_rows.append({"Model": model_name, **evaluate_predictions(y_test, predictions)})
    comparison = pd.DataFrame(comparison_rows).set_index("Model").sort_values("MAE")
    best_model_name = comparison.index[0]
    best_predictions = all_predictions[best_model_name]
    plot_path, plot_food = plot_best_model(test_df, best_predictions, best_model_name)

    print("FDS CONSUMPTION FORECASTING")
    print(f"Rows after lag creation: {len(df):,}")
    print(
        f"Chronological split: train through {(cutoff_date - pd.Timedelta(days=1)):%Y-%m-%d}; "
        f"test from {cutoff_date:%Y-%m-%d}"
    )
    print(f"Training rows: {len(train_df):,} | Test rows: {len(test_df):,}")
    print("\nMODEL COMPARISON (lower MAE/RMSE and higher R2 are better)")
    print(comparison.round(4).to_string())
    print(f"\nBest model: {best_model_name} (lowest test MAE: {comparison.iloc[0]['MAE']:.4f})")
    print(f"Actual-vs-predicted plot for {plot_food}: {plot_path}")


if __name__ == "__main__":
    main()
