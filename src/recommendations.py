"""Explainable purchase recommendations based on FORAGE demand forecasts.

Run from the project root with:
    python src/recommendations.py

This is a separate recommendation layer: it first predicts next-day demand with
whichever forecaster won the chronological evaluation in prediction.py (lowest
test MAE), then compares that demand with the latest recorded stock and each
food's own historical waste rate.
"""

from pathlib import Path

import pandas as pd

from prediction import (
    CATEGORICAL_FEATURES,
    DEMO_BASELINES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    TARGET,
    build_models,
    create_forecasting_features,
    load_data,
    run_demo_forecast,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "recommendations"


def build_next_day_features(raw_df, future_is_festival=0):
    """Build one historical-only forecast row for the next day of every food.

    Future festival information is set to 0 unless a confirmed event calendar
    supplies it. This avoids assuming an event that is not in the data.
    """
    forecast_date = raw_df["Date"].max() + pd.Timedelta(days=1)
    rows = []
    for food, history in raw_df.groupby("Food", sort=True):
        history = history.sort_values("Date")
        latest = history.iloc[-1]
        last_seven = history[TARGET].tail(7)
        rows.append({
            "Food": food,
            "Category": latest["Category"],
            "Lag_1_Consumption": latest[TARGET],
            "Lag_7_Consumption": history[TARGET].iloc[-7],
            "Rolling_Mean_7": last_seven.mean(),
            "Day_of_Week": forecast_date.day_name(),
            "Month": forecast_date.month,
            "Is_Weekend": int(forecast_date.dayofweek >= 5),
            "Is_Festival": future_is_festival,
        })
    return pd.DataFrame(rows), forecast_date


def calculate_historical_statistics(raw_df):
    """Calculate food-specific consumption, waste, and stock statistics."""
    statistics = raw_df.groupby("Food").agg(
        Historical_Average_Consumption=(TARGET, "mean"),
        Historical_Waste=("Quantity_Wasted", "sum"),
        Historical_Purchased=("Quantity_Purchased", "sum"),
    )
    statistics["Historical_Waste_Percentage"] = (
        statistics["Historical_Waste"] / statistics["Historical_Purchased"] * 100
    )
    return statistics


def latest_inventory(raw_df, forecast_date):
    """Return the latest available remaining quantity and expiry data per food."""
    latest_date = raw_df["Date"].max()
    inventory = raw_df.loc[raw_df["Date"] == latest_date, [
        "Food", "Quantity_Unit", "Remaining_Quantity", "Estimated_Expiry_Date", "Expiry_Days",
    ]].copy()
    inventory["Estimated_Expiry_Date"] = pd.to_datetime(
        inventory["Estimated_Expiry_Date"], errors="coerce"
    )
    inventory["Days_Until_Expiry"] = (
        inventory["Estimated_Expiry_Date"] - forecast_date
    ).dt.days
    return inventory.set_index("Food")


def create_alerts(recommendations, high_waste_threshold, short_life_threshold):
    """Create data-driven alerts without arbitrary fixed percentage rules."""
    alerts = []
    for _, row in recommendations.iterrows():
        food_alerts = []
        if row["Historical_Waste_Percentage"] >= high_waste_threshold:
            food_alerts.append("historical waste is in the highest 25% of foods")
        if row["Usable_Remaining_Stock"] < row["Predicted_Demand"]:
            food_alerts.append("usable stock is below predicted demand")
        if (row["Current_Remaining_Quantity"] > 0 and
                pd.notna(row["Days_Until_Expiry"]) and
                row["Days_Until_Expiry"] <= short_life_threshold):
            food_alerts.append("remaining stock has comparatively short shelf life")
        alerts.append("; ".join(food_alerts) if food_alerts else "No alert")
    return alerts


def create_reasons(recommendations):
    """Create a plain-language explanation for every purchase quantity."""
    reasons = []
    for _, row in recommendations.iterrows():
        reasons.append(
            f"Predicted next-day demand is {row['Predicted_Demand']:.2f}. "
            f"Latest remaining stock is {row['Current_Remaining_Quantity']:.2f}; "
            f"using its historical waste rate of {row['Historical_Waste_Percentage']:.2f}%, "
            f"estimated usable stock is {row['Usable_Remaining_Stock']:.2f}. "
            f"Purchase recommendation is the non-negative gap between demand and usable stock."
        )
    return reasons


def predict_next_day(raw_df, model_name):
    """Next-day demand per food from the named forecaster.

    A baseline needs no fitting; a model is refit on all history (its test-set
    score was already measured in run_demo_forecast).
    """
    future_features, forecast_date = build_next_day_features(raw_df)
    if model_name in DEMO_BASELINES:
        predicted = future_features[DEMO_BASELINES[model_name]]
    else:
        training_df = create_forecasting_features(raw_df)
        model = build_models(NUMERIC_FEATURES, CATEGORICAL_FEATURES)[model_name]
        model.fit(training_df[FEATURE_COLUMNS], training_df[TARGET])
        predicted = model.predict(future_features[FEATURE_COLUMNS])
    future_features["Predicted_Demand"] = predicted
    return future_features, forecast_date


def generate_recommendations(raw_df=None, model_name=None):
    """Forecast demand with the evaluated best model and calculate purchase quantities."""
    raw_df = load_data() if raw_df is None else raw_df
    if model_name is None:
        model_name = run_demo_forecast(raw_df)["best_model"]
    future_features, forecast_date = predict_next_day(raw_df, model_name)
    # Negative demand is physically impossible, so zero is the sensible lower bound.
    future_features["Predicted_Demand"] = future_features["Predicted_Demand"].clip(lower=0)

    statistics = calculate_historical_statistics(raw_df)
    inventory = latest_inventory(raw_df, forecast_date)
    recommendations = future_features.set_index("Food").join(statistics).join(inventory)
    recommendations["Current_Remaining_Quantity"] = recommendations[
        "Remaining_Quantity"
    ].fillna(0)

    # A food's usable stock is its current stock adjusted by its observed loss
    # rate. This is food-specific, calculated from the data, and not a fixed rule.
    recommendations["Usable_Remaining_Stock"] = (
        recommendations["Current_Remaining_Quantity"]
        * (1 - recommendations["Historical_Waste_Percentage"] / 100)
    ).clip(lower=0)
    recommendations["Recommended_Purchase_Quantity"] = (
        recommendations["Predicted_Demand"] - recommendations["Usable_Remaining_Stock"]
    ).clip(lower=0)

    high_waste_threshold = recommendations["Historical_Waste_Percentage"].quantile(0.75)
    short_life_threshold = recommendations["Days_Until_Expiry"].quantile(0.25)
    recommendations["Alerts"] = create_alerts(
        recommendations, high_waste_threshold, short_life_threshold
    )
    recommendations["Reason"] = create_reasons(recommendations)
    recommendations["Forecast_Date"] = forecast_date
    recommendations["Forecast_Model"] = model_name

    output_columns = [
        "Forecast_Date", "Forecast_Model", "Category", "Quantity_Unit", "Predicted_Demand", "Historical_Average_Consumption",
        "Current_Remaining_Quantity", "Historical_Waste_Percentage",
        "Usable_Remaining_Stock", "Recommended_Purchase_Quantity",
        "Days_Until_Expiry", "Alerts", "Reason",
    ]
    return recommendations[output_columns].reset_index().sort_values(
        "Recommended_Purchase_Quantity", ascending=False
    ), high_waste_threshold, short_life_threshold


def main():
    """Print and save explainable next-day purchase recommendations."""
    recommendations, high_waste_threshold, short_life_threshold = generate_recommendations()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / "purchase_recommendations.csv"
    recommendations.to_csv(output_path, index=False, date_format="%Y-%m-%d")

    print("FORAGE EXPLAINABLE PURCHASE RECOMMENDATIONS")
    print(f"Forecast date: {recommendations['Forecast_Date'].iloc[0]:%Y-%m-%d}")
    print(f"High-waste alert threshold (75th percentile): {high_waste_threshold:.2f}%")
    print(f"Short shelf-life alert threshold (25th percentile): {short_life_threshold:.0f} days")
    print("\nRECOMMENDATIONS")
    print(recommendations.round({
        "Predicted_Demand": 2,
        "Historical_Average_Consumption": 2,
        "Current_Remaining_Quantity": 2,
        "Historical_Waste_Percentage": 2,
        "Usable_Remaining_Stock": 2,
        "Recommended_Purchase_Quantity": 2,
    }).to_string(index=False))
    print(f"\nSaved recommendations to: {output_path}")


if __name__ == "__main__":
    main()
