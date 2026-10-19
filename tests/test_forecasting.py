import numpy as np
import pandas as pd
import pytest

import recommendations
from m5_forecasting import create_m5_features, forecast_retail_demand, impute_price
from prediction import (
    CATEGORICAL_FEATURES,
    DEMO_BASELINES,
    FEATURE_COLUMNS,
    NAIVE_BASELINE,
    NUMERIC_FEATURES,
    TARGET,
    build_models,
    chronological_split,
    create_forecasting_features,
    evaluate_models,
    evaluate_predictions,
    run_demo_forecast,
    select_best_model,
)


def test_lags_are_shifted_within_each_food(daily_series):
    features = create_forecasting_features(daily_series)
    for food, group in features.groupby("Food"):
        original = daily_series[daily_series["Food"] == food].set_index("Date")[TARGET]
        for _, row in group.head(5).iterrows():
            assert row["Lag_1_Consumption"] == original[row["Date"] - pd.Timedelta(days=1)]
            assert row["Lag_7_Consumption"] == original[row["Date"] - pd.Timedelta(days=7)]
    # The first 7 days of each food lack history and are dropped, so no value crosses foods.
    assert features.groupby("Food")["Date"].min().eq(pd.Timestamp("2025-01-08")).all()


def test_rolling_mean_excludes_the_current_day(daily_series):
    spiked = daily_series.copy()
    spike_date = pd.Timestamp("2025-01-20")
    spiked.loc[(spiked["Food"] == "Milk") & (spiked["Date"] == spike_date), TARGET] = 1000.0
    before = create_forecasting_features(daily_series).set_index(["Food", "Date"])
    after = create_forecasting_features(spiked).set_index(["Food", "Date"])
    assert after.loc[("Milk", spike_date), "Rolling_Mean_7"] == before.loc[("Milk", spike_date), "Rolling_Mean_7"]
    next_day = spike_date + pd.Timedelta(days=1)
    assert after.loc[("Milk", next_day), "Rolling_Mean_7"] > before.loc[("Milk", next_day), "Rolling_Mean_7"]


def test_split_is_chronological(daily_series):
    train, test, cutoff = chronological_split(create_forecasting_features(daily_series))
    assert train["Date"].max() < cutoff <= test["Date"].min()
    assert len(train) + len(test) == len(create_forecasting_features(daily_series))


def test_no_leakage_future_targets_cannot_change_the_trained_model(daily_series):
    """Perturb every target after the cutoff; training data and fitted model must be identical."""
    _, _, cutoff = chronological_split(create_forecasting_features(daily_series))
    perturbed = daily_series.copy()
    perturbed.loc[perturbed["Date"] >= cutoff, TARGET] *= 100

    fitted = []
    for data in (daily_series, perturbed):
        train, _, data_cutoff = chronological_split(create_forecasting_features(data))
        assert data_cutoff == cutoff
        model = build_models(NUMERIC_FEATURES, CATEGORICAL_FEATURES)["Linear Regression"]
        model.fit(train[FEATURE_COLUMNS], train[TARGET])
        fitted.append((train, model.named_steps["model"].coef_.copy()))
    pd.testing.assert_frame_equal(fitted[0][0], fitted[1][0])
    np.testing.assert_array_equal(fitted[0][1], fitted[1][1])


def test_scaler_is_fit_on_training_rows_only(daily_series):
    train, _, _ = chronological_split(create_forecasting_features(daily_series))
    model = build_models(NUMERIC_FEATURES, CATEGORICAL_FEATURES)["Linear Regression"]
    model.fit(train[FEATURE_COLUMNS], train[TARGET])
    scaler = model.named_steps["preprocessor"].named_transformers_["numeric"]
    np.testing.assert_allclose(scaler.mean_, train[NUMERIC_FEATURES].mean().to_numpy())


def test_metrics_are_computed_on_the_held_out_period(daily_series):
    train, test, _ = chronological_split(create_forecasting_features(daily_series))
    models = build_models(NUMERIC_FEATURES, CATEGORICAL_FEATURES)
    comparison, predictions = evaluate_models(train, test, TARGET, FEATURE_COLUMNS, models, DEMO_BASELINES)
    assert set(comparison["Model"]) == {"Linear Regression", "Random Forest", *DEMO_BASELINES}
    for name, values in predictions.items():
        assert values.index.equals(test.index)
        expected = evaluate_predictions(test[TARGET], values)
        row = comparison.set_index("Model").loc[name]
        assert row["MAE"] == pytest.approx(expected["MAE"]) and row["R2"] == pytest.approx(expected["R2"])
    naive = comparison.set_index("Model").loc[NAIVE_BASELINE]
    assert naive["Type"] == "Baseline"
    assert naive["MAE"] == pytest.approx((test[TARGET] - test["Lag_1_Consumption"]).abs().mean())


def test_best_model_is_selected_from_results_not_hard_coded():
    table = pd.DataFrame({"Model": ["Linear Regression", "Random Forest", NAIVE_BASELINE],
                          "Type": ["Model", "Model", "Baseline"],
                          "MAE": [0.5, 0.2, 0.9], "RMSE": [0.6, 0.3, 1.0], "R2": [0.5, 0.8, 0.1]})
    assert select_best_model(table) == "Random Forest"
    table.loc[2, ["MAE", "RMSE"]] = [0.1, 0.1]
    assert select_best_model(table) == NAIVE_BASELINE


def test_recommendations_use_the_evaluated_best_model(monkeypatch):
    raw = recommendations.load_data()
    monkeypatch.setattr(recommendations, "run_demo_forecast", lambda df: {"best_model": "7-day moving average"})
    table, _, _ = recommendations.generate_recommendations(raw)
    assert (table["Forecast_Model"] == "7-day moving average").all()
    milk = raw[raw["Food"] == "Milk"].sort_values("Date")[TARGET].tail(7).mean()
    assert table.set_index("Food").loc["Milk", "Predicted_Demand"] == pytest.approx(milk)


def test_demo_forecast_end_to_end():
    result = run_demo_forecast()
    comparison = result["comparison"]
    assert result["best_model"] == comparison.iloc[0]["Model"]
    assert result["tested"]["Date"].min() == result["cutoff"]
    assert {"Baseline", "Model"} == set(comparison["Type"])


def m5_frame(days=60):
    dates = pd.date_range("2016-01-01", periods=days, freq="D")
    rows = []
    for product in ("FOODS_1_001", "FOODS_3_090"):
        for i, date in enumerate(dates):
            rows.append({"Date": date, "Product_ID": product, "Store_ID": "CA_1", "Quantity_Sold": 5 + i % 7,
                         "Month": date.month, "Price": 2.0 + (i % 3)})
    return pd.DataFrame(rows)


def test_m5_price_imputation_uses_training_median_only():
    data = create_m5_features(m5_frame())
    train, test, _ = chronological_split(data)
    train.loc[train.index[:3], "Price"] = np.nan
    test["Price"] = np.nan
    expected = train["Price"].median()
    train_filled, test_filled, median = impute_price(train, test)
    assert median == pytest.approx(expected)
    assert (test_filled["Price"] == expected).all()
    test_other = test.assign(Price=999.0)
    assert impute_price(train, test_other)[2] == median  # test prices never affect the fill value


def test_m5_forecast_includes_baselines_and_picks_lowest_mae():
    tested, _, comparison, meta = forecast_retail_demand(m5_frame())
    assert "Naive (yesterday's value)" in set(comparison["Model"])
    assert meta["best_model"] == comparison.sort_values("MAE").iloc[0]["Model"]
    assert tested["Date"].min() == meta["cutoff"]
    assert (tested["Predicted_Sales"] >= 0).all()
