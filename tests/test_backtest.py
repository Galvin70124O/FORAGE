"""Backtest simulator on toy cases with hand-computed results."""

import pandas as pd
import pytest

from backtest import daily_policy, recorded_policy, run_backtest, simulate, summarise, weekly_policy


def test_expired_stock_is_wasted_and_unmet_days_are_stockouts():
    # shelf life 2: bought day 0 -> edible days 0 and 1, thrown away at the start of day 2.
    # demand 1/day: eat 1, eat 1, (1 left) wasted on day 2, days 2 and 3 have nothing.
    out = simulate([1, 1, 1, 1], 2, recorded_policy([3, 0, 0, 0]))
    assert (out.purchased, out.eaten, out.wasted, out.stockout_days, out.unmet) == (3, 2, 1, 2, 2)
    assert out.waste_pct == pytest.approx(100 / 3)


def test_food_is_eaten_oldest_first():
    # two batches of 2, shelf life 3. Day 0-1 eat the first batch, day 2 eats from the second.
    out = simulate([1, 1, 1], 3, recorded_policy([2, 2, 0]))
    assert out.wasted == 0 and out.leftover == pytest.approx(1)  # second batch still edible on day 3
    # if the newer batch were eaten first, the old one would expire on day 3 instead
    late = simulate([1, 1, 1, 0], 3, recorded_policy([2, 2, 0, 0]))
    assert late.wasted == 0 and late.leftover == pytest.approx(1)


def test_a_perfect_daily_forecast_has_no_waste_and_no_stockouts():
    demand = [1.0, 2.0, 0.5, 1.5]
    out = simulate(demand, 2, daily_policy(demand))
    assert out.wasted == 0 and out.stockout_days == 0 and out.purchased == pytest.approx(sum(demand))


def test_daily_policy_tops_up_to_the_forecast():
    out = simulate([1, 1], 5, daily_policy([3, 3]))  # day 0 buys 3, day 1 has 2 on hand -> buys 1
    assert out.purchased == pytest.approx(4)


def test_weekly_policy_never_buys_more_than_can_be_eaten_before_expiry():
    # 7-day forecast 7 (1/day) but shelf life 3: buys only 3 days' worth on day 0, then nothing until day 7.
    out = simulate([1] * 7, 3, weekly_policy([7.0] * 7, shelf_life=3))
    assert out.purchased == pytest.approx(3) and out.wasted == 0 and out.stockout_days == 4


def test_run_backtest_and_summary():
    frame = pd.DataFrame({"Food": ["Milk"] * 4, "Date": pd.date_range("2026-01-01", periods=4),
                          "Demand": [1, 1, 1, 1], "Bought": [3, 0, 0, 0], "Forecast": [1, 1, 1, 1],
                          "Week_Forecast": [7, 7, 7, 7], "Shelf_Life": [2] * 4, "Unit_Price": [50] * 4})
    results = run_backtest(frame)
    recorded = results.set_index("Policy").loc["Recorded"]
    assert recorded["Wasted"] == 1 and recorded["Wasted_Rupees"] == 50 and recorded["Stockout_Days"] == 2
    daily = results.set_index("Policy").loc["FORAGE daily"]
    assert daily["Wasted"] == 0 and daily["Stockout_Days"] == 0
    summary = summarise(results)
    assert summary.loc["Recorded", "Waste_Pct"] == pytest.approx(100 / 3)
    assert summary.loc["Recorded", "Stockout_Pct"] == pytest.approx(50)
    assert summary.loc["Recorded", "Unmet_Pct"] == pytest.approx(50)  # 2 of 4 units of demand unmet
