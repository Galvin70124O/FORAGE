"""7-day direct forecasting and rolling-origin backtesting, with leakage tests for every fold."""

import pandas as pd
import pytest

from horizon import (
    WEEK_BASELINES,
    WEEK_NUMERIC,
    fold_cutoffs,
    latest_week_forecast,
    purged_split,
    rolling_origin,
    week_models,
    weekly_frame,
)
from prediction import (
    CATEGORICAL_FEATURES,
    DEMO_BASELINES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    TARGET,
    build_models,
    create_forecasting_features,
)


def ramp(days=90, foods=("Milk", "Rice")):
    """Consumption on day i is i (+100 for the second food): easy to check sums by hand."""
    dates = pd.date_range("2026-01-01", periods=days)
    return pd.DataFrame([{"Date": d, "Food": f, "Category": "X", "Quantity_Consumed": float(i + 100 * k)}
                         for k, f in enumerate(foods) for i, d in enumerate(dates)])


def test_weekly_features_use_only_the_past_and_target_is_the_next_seven_days():
    frame = weekly_frame(ramp(), "Food", "Quantity_Consumed", static=["Category"])
    row = frame[(frame["Food"] == "Milk") & (frame["Date"] == pd.Timestamp("2026-02-10"))].iloc[0]
    i = 40  # 10 Feb is day index 40
    assert row["Last_7"] == sum(range(i - 6, i + 1))
    assert row["Prev_7"] == sum(range(i - 13, i - 6))
    assert row["Avg_4w"] == sum(range(i - 27, i + 1)) / 4
    assert row["Target_7"] == sum(range(i + 1, i + 8))
    assert frame.groupby("Food")["Date"].min().eq(pd.Timestamp("2026-01-28")).all()  # needs 28 days of history


def test_target_never_overlaps_the_features():
    base = ramp()
    origin = pd.Timestamp("2026-02-10")
    changed = base.copy()
    changed.loc[changed["Date"] > origin, "Quantity_Consumed"] += 1000  # everything after the origin
    a = weekly_frame(base, "Food", "Quantity_Consumed").set_index(["Food", "Date"]).loc[("Milk", origin)]
    b = weekly_frame(changed, "Food", "Quantity_Consumed").set_index(["Food", "Date"]).loc[("Milk", origin)]
    assert (a[WEEK_NUMERIC] == b[WEEK_NUMERIC]).all()   # features unchanged
    assert b["Target_7"] == a["Target_7"] + 7000         # the target moves with the future


def test_purged_split_keeps_training_targets_before_the_cutoff():
    frame = weekly_frame(ramp(), "Food", "Quantity_Consumed")
    cutoff = pd.Timestamp("2026-03-01")
    train, test = purged_split(frame, cutoff)
    assert (train["Date"] + pd.Timedelta(days=7)).max() < cutoff <= test["Date"].min()


def test_fold_cutoffs_are_consecutive_windows_ending_at_the_last_date():
    cutoffs = fold_cutoffs(pd.Series(pd.date_range("2026-01-01", "2026-03-31")), 5, 14)
    assert len(cutoffs) == 5 and cutoffs[-1] == pd.Timestamp("2026-03-18")
    assert all((b - a).days == 14 for a, b in zip(cutoffs, cutoffs[1:]))


@pytest.mark.parametrize("gap", [0, 7])
def test_no_leakage_in_any_rolling_fold(gap):
    """For every fold: training dates (+ target gap) end before the cutoff, and changing every value
    from the cutoff onward leaves that fold's training rows unchanged."""
    base = weekly_frame(ramp(), "Food", "Quantity_Consumed", static=["Category"])
    for cutoff in fold_cutoffs(base["Date"], 5, 7):
        train, test = purged_split(base, cutoff, gap=gap, test_days=7)
        assert (train["Date"] + pd.Timedelta(days=gap)).max() < cutoff <= test["Date"].min()
        raw = ramp()
        raw.loc[raw["Date"] >= cutoff, "Quantity_Consumed"] *= 50
        perturbed_train, _ = purged_split(weekly_frame(raw, "Food", "Quantity_Consumed", static=["Category"]),
                                          cutoff, gap=7, test_days=7)
        clean_train, _ = purged_split(base, cutoff, gap=7, test_days=7)
        pd.testing.assert_frame_equal(clean_train.reset_index(drop=True), perturbed_train.reset_index(drop=True))


def test_one_step_rolling_folds_have_no_leakage(daily_series):
    featured = create_forecasting_features(daily_series)
    for cutoff in fold_cutoffs(featured["Date"], 5, 5):
        train, test = purged_split(featured, cutoff, gap=0, test_days=5)
        assert train["Date"].max() < cutoff <= test["Date"].min()
        perturbed = daily_series.copy()
        perturbed.loc[perturbed["Date"] >= cutoff, TARGET] *= 100
        again, _ = purged_split(create_forecasting_features(perturbed), cutoff, gap=0, test_days=5)
        pd.testing.assert_frame_equal(train.reset_index(drop=True), again.reset_index(drop=True))


def test_rolling_origin_reports_mean_and_std_and_ranks_by_mean_mae(daily_series):
    featured = create_forecasting_features(daily_series)
    per_fold, summary = rolling_origin(
        featured, target=TARGET, features=FEATURE_COLUMNS, baselines=DEMO_BASELINES, folds=5, test_days=5,
        models_factory=lambda: build_models(NUMERIC_FEATURES, CATEGORICAL_FEATURES))
    assert per_fold["Fold"].nunique() == 5 and set(summary["Folds"]) == {5}
    assert summary["MAE_mean"].is_monotonic_increasing
    milk = per_fold[per_fold["Model"] == "Linear Regression"]["MAE"]
    assert summary.set_index("Model").loc["Linear Regression", "MAE_mean"] == pytest.approx(milk.mean())
    assert summary.set_index("Model").loc["Linear Regression", "MAE_std"] == pytest.approx(milk.std())


def test_weekly_models_beat_nothing_by_construction_and_latest_forecast_uses_the_last_origin():
    frame = weekly_frame(ramp(), "Food", "Quantity_Consumed", static=["Category"], keep_future=True)
    assert frame["Target_7"].isna().sum() == 2 * 7  # the last 7 origins of each food have no full target
    forecast = latest_week_forecast(frame, "Last-week total", [], "Food")
    assert forecast["Milk"] == sum(range(83, 90))  # last origin is day 89
    model_forecast = latest_week_forecast(frame, "Linear Regression", [], "Food")
    assert model_forecast["Milk"] == pytest.approx(sum(range(90, 97)), rel=0.02)  # a ramp is linear
    assert set(WEEK_BASELINES) == {"Last-week total", "4-week average"}
    assert set(week_models(["Category"])) == {"Linear Regression", "Random Forest"}
