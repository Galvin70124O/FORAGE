"""Waste-risk classifier: purchase-time features only, recall-first threshold, honest metrics."""

import numpy as np
import pandas as pd
import pytest

from waste_risk import (
    ALL_FEATURES,
    HIGH_WASTE_PCT,
    add_features,
    evaluate,
    metrics,
    recall_first_threshold,
    time_split,
)


def records(days=120, seed=3):
    rng = np.random.default_rng(seed)
    rows = []
    for food, category, shelf, waste_bias in (("Milk", "Dairy", 7, 0.4), ("Rice", "Grains", 90, 0.1),
                                              ("Bread", "Bakery", 5, 0.5), ("Dal", "Pulses", 180, 0.05)):
        for i, day in enumerate(pd.date_range("2025-01-01", periods=days)):
            bought = rng.uniform(1, 3)
            consumed = bought * rng.uniform(0.3, 0.9)
            wasted = (bought - consumed) * min(1, waste_bias + rng.uniform(0, 0.5))
            rows.append({"Date": day, "Food": food, "Category": category, "Expiry_Days": shelf,
                         "Quantity_Purchased": bought, "Quantity_Consumed": consumed, "Quantity_Wasted": wasted,
                         "Waste_Percentage": wasted / bought * 100})
    return pd.DataFrame(rows)


def test_recent_consumption_excludes_the_current_record():
    df = records(20)
    features = add_features(df)
    milk = df[df["Food"] == "Milk"].sort_values("Date").reset_index(drop=True)
    rate = milk["Quantity_Consumed"] / milk["Quantity_Purchased"]
    row = features[(features["Food"] == "Milk")].reset_index(drop=True).iloc[9]  # 11th Milk record
    assert row["Recent_Consumption"] == pytest.approx(rate.iloc[3:10].mean())
    assert "Quantity_Wasted" not in ALL_FEATURES and "Waste_Percentage" not in ALL_FEATURES
    assert features["High_Waste"].equals((features["Waste_Percentage"] > HIGH_WASTE_PCT).astype(int))


def test_split_is_chronological():
    train, test = time_split(add_features(records()))
    assert train["Date"].max() < test["Date"].min()


def test_recall_first_threshold_and_metrics():
    y = np.array([0, 0, 1, 1, 1, 0, 1, 0])
    scores = np.array([0.1, 0.4, 0.35, 0.8, 0.7, 0.6, 0.2, 0.05])
    threshold = recall_first_threshold(y, scores, target=0.75)
    assert threshold == pytest.approx(0.35)  # catches 3 of 4 positives
    result = metrics(y, scores, threshold)
    assert (result["TP"], result["FN"], result["FP"], result["TN"]) == (3, 1, 2, 2)
    assert result["Recall"] == pytest.approx(0.75) and result["Precision"] == pytest.approx(0.6)


def test_evaluate_reports_all_four_variants_and_learns_something():
    result = evaluate(records())
    table = result["comparison"]
    assert len(table) == 4 and set(table["Features"]) == {"All features", "Without quantity purchased"}
    assert table["ROC_AUC"].min() > 0.6  # waste propensity differs by food, so there is signal
    assert result["best"].endswith("All features")
    assert (table["Recall"] >= 0.5).all()  # thresholds favour catching likely waste


def test_planned_rows_use_history_only():
    from waste_risk import planned_rows
    df = records(30)
    rows = planned_rows(df, pd.Series(["Milk", "Rice"]), pd.Series([2.0, 5.0]), "2025-02-01")
    milk = df[df["Food"] == "Milk"].sort_values("Date").tail(7)
    assert rows.loc[0, "Recent_Consumption"] == pytest.approx((milk["Quantity_Consumed"] / milk["Quantity_Purchased"]).mean())
    assert rows.loc[1, "Expiry_Days"] == 90 and rows.loc[0, "Day_of_Week"] == "Saturday"
    assert set(ALL_FEATURES) <= set(rows.columns)
