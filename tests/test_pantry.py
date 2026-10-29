"""Purchases + pantry checks -> periods, derived consumption, stock, expiry, buy list, bills, imports.

Hand-worked example (Milk, shelf life 5 days):
  bought 1 Mar 2 L for ₹120, 3 Mar 2 L for ₹130
  check 4 Mar: 1.5 left, 0.5 thrown away   check 8 Mar: 0.5 left, 0 thrown away
  period 1 (1-4 Mar, 4 days): 0 + 4 - 0.5 - 1.5 = 2.0 consumed, waste 0.5/4 = 12.5%
  period 2 (5-8 Mar, 4 days): 1.5 + 0 - 0 - 0.5 = 1.0 consumed
  daily rate = (2 + 1) / 8 = 0.375 L/day; price per unit = median(60, 65) = ₹62.5
"""

import pandas as pd
import pytest

from pantry import (
    analysis_frame,
    buy_list,
    consumption_rates,
    coverage,
    expected_stock,
    expiring_soon,
    likely_wasted,
    parse_bill,
    periods,
    read_import,
    stock_batches,
    unit_prices,
    unlocked,
    wasted_value,
)
from stats import sample_note


def purchases(rows):
    return pd.DataFrame([{"id": i, "date": pd.Timestamp(d), "food": f, "category": "Dairy", "quantity": q,
                          "unit": "L", "total_price": p, "shelf_life_days": s}
                         for i, (d, f, q, p, s) in enumerate(rows)])


def checks(rows):
    return pd.DataFrame([{"id": i, "date": pd.Timestamp(d), "food": f, "category": "Dairy", "unit": "L",
                          "remaining": r, "wasted": w, "shelf_life_days": 5}
                         for i, (d, f, r, w) in enumerate(rows)])


BUYS = purchases([("2026-03-01", "Milk", 2, 120, 5), ("2026-03-03", "Milk", 2, 130, 5)])
CHECKS = checks([("2026-03-04", "Milk", 1.5, 0.5), ("2026-03-08", "Milk", 0.5, 0)])


def test_consumption_is_derived_per_period():
    table = periods(BUYS, CHECKS)
    assert table["Consumed"].tolist() == [2.0, 1.0]
    assert table["Days"].tolist() == [4, 4]
    assert table["Opening_Stock"].tolist() == [0.0, 1.5]
    assert table.loc[0, "Waste_Percentage"] == pytest.approx(12.5)
    assert not table["Impossible"].any()


def test_impossible_consumption_is_flagged_not_hidden():
    table = periods(BUYS, checks([("2026-03-04", "Milk", 5.0, 0)]))  # more left than was ever bought
    assert table.loc[0, "Impossible"] and table.loc[0, "Consumed"] == 0


def test_a_first_check_before_any_purchase_is_only_a_baseline():
    table = periods(purchases([("2026-03-05", "Milk", 2, 120, 5)]),
                    checks([("2026-03-01", "Milk", 1.0, 0), ("2026-03-08", "Milk", 0.5, 0.5)]))
    assert len(table) == 1
    assert table.loc[0, "Opening_Stock"] == 1.0 and table.loc[0, "Consumed"] == pytest.approx(2.0)


def test_prices_rates_and_rupee_waste():
    assert unit_prices(BUYS)["Milk"] == pytest.approx(62.5)
    assert consumption_rates(periods(BUYS, CHECKS))["Milk"] == pytest.approx(0.375)
    frame = analysis_frame(BUYS, CHECKS)
    assert wasted_value(frame).tolist() == pytest.approx([31.25, 0.0])


def test_expected_stock_subtracts_estimated_use_since_the_last_check():
    assert expected_stock(BUYS, CHECKS, "2026-03-08").set_index("Food").loc["Milk", "Expected"] == 0.5
    assert expected_stock(BUYS, CHECKS, "2026-03-10").set_index("Food").loc["Milk", "Expected"] == 0.0
    later = pd.concat([BUYS, purchases([("2026-03-09", "Milk", 2, 130, 5)])], ignore_index=True)
    # 0.5 + 2 bought - 0.375 x 2 days = 1.75
    assert expected_stock(later, CHECKS, "2026-03-10").set_index("Food").loc["Milk", "Expected"] == pytest.approx(1.75)


def test_batches_expiry_and_likely_waste():
    stock = expected_stock(BUYS, CHECKS, "2026-03-08")
    batches = stock_batches(BUYS, stock)
    assert len(batches) == 1 and batches.loc[0, "Bought"] == pd.Timestamp("2026-03-03")
    assert batches.loc[0, "Expiry"] == pd.Timestamp("2026-03-08")
    assert expiring_soon(batches, "2026-03-08", 3).loc[0, "Days_Left"] == 0
    risk = likely_wasted(batches, "2026-03-08")  # expires today, nothing can be eaten in time
    assert risk.loc[0, "At_Risk"] == pytest.approx(0.5) and risk.loc[0, "Value"] == pytest.approx(32.5)


def test_likely_waste_eats_oldest_batches_first():
    buys = purchases([("2026-03-01", "Rice", 3, 300, 10), ("2026-03-05", "Rice", 3, 300, 20)])
    stock = pd.DataFrame([{"Food": "Rice", "Unit": "kg", "Expected": 6.0, "Daily_Rate": 0.5,
                           "Shelf_Life_Days": 10}])
    batches = stock_batches(buys, stock)
    # as of 5 Mar: batch 1 expires 11 Mar (6 days -> 3 kg eaten, all of it); batch 2 expires 25 Mar:
    # 20 days total minus 6 used = 14 days -> 7 kg possible, 3 kg held -> no waste
    assert likely_wasted(batches, "2026-03-05").empty
    fast_expiry = stock_batches(purchases([("2026-03-01", "Rice", 3, 300, 2)]),
                                stock.assign(Expected=3.0))
    assert likely_wasted(fast_expiry, "2026-03-01").loc[0, "At_Risk"] == pytest.approx(2.0)


def test_buy_list_only_counts_stock_that_is_still_good():
    stock = expected_stock(BUYS, CHECKS, "2026-03-08")
    plan = buy_list(stock, stock_batches(BUYS, stock), "2026-03-08", 7)
    row = plan.set_index("Food").loc["Milk"]
    assert row["Need"] == pytest.approx(2.62, abs=0.01)
    assert row["Usable_Stock"] == 0 and row["Buy"] == pytest.approx(2.62, abs=0.01)


def test_unlocking_and_sample_notes():
    cover = coverage(BUYS, CHECKS)
    assert cover["periods"] == 2 and cover["purchases"] == 2 and cover["days"] == 8 and cover["weeks"] == 1
    shown, reliable, note = unlocked("waste", cover)
    assert shown and not reliable and "Not reliable yet" in note
    shown, _, note = unlocked("forecast", cover)  # needs 3 weeks, has 1
    assert shown is False and note.startswith("Not enough data yet (need 2 more weeks)")
    assert "not reliable yet" in sample_note(12, 30, "days")
    assert sample_note(40, 30, "days") == "n = 40 days"


def test_parse_bill_reads_common_formats_and_reports_the_rest():
    rows, skipped = parse_bill("Milk 2 L 120\nEggs x12 84\nTomato 1kg - ₹40\nAMUL BUTTER 500g Rs. 245.50\n"
                               "Bread 45\nThank you for shopping\n")
    assert rows.to_dict("records") == [
        {"food": "Milk", "quantity": 2.0, "unit": "L", "total_price": 120.0},
        {"food": "Eggs", "quantity": 12.0, "unit": "piece", "total_price": 84.0},
        {"food": "Tomato", "quantity": 1.0, "unit": "kg", "total_price": 40.0},
        {"food": "Amul Butter", "quantity": 500.0, "unit": "g", "total_price": 245.5},
        {"food": "Bread", "quantity": 1.0, "unit": "unit", "total_price": 45.0},
    ]
    assert skipped == ["Thank you for shopping"]


@pytest.mark.parametrize("line, food, quantity, unit, price", [
    ("Bread 1 45", "Bread", 1.0, "unit", 45.0),        # a bare count is the quantity, not part of the name
    ("Bread 2 90", "Bread", 2.0, "unit", 90.0),
    ("Bread 45", "Bread", 1.0, "unit", 45.0),
    ("Milk 2 L 60", "Milk", 2.0, "L", 60.0),
    ("7up 2 40", "7Up", 2.0, "unit", 40.0),            # a number at the start of a name stays (title-cased)
    ("7up 40", "7Up", 1.0, "unit", 40.0),
    ("Vitamin B12 3 150", "Vitamin B12", 3.0, "unit", 150.0),
    ("Bread 0 45", "Bread 0", 1.0, "unit", 45.0),      # zero is never a quantity
    ("Rice 2.5 120", "Rice", 2.5, "unit", 120.0),
    ("Eggs 12 x 84", "Eggs", 12.0, "piece", 84.0),
])
def test_parse_bill_reads_a_bare_number_before_the_price_as_the_quantity(line, food, quantity, unit, price):
    rows, skipped = parse_bill(line)
    assert rows.to_dict("records") == [{"food": food, "quantity": quantity, "unit": unit, "total_price": price}]
    assert skipped == []


def test_parse_bill_keeps_a_known_food_whose_name_ends_in_a_number():
    assert parse_bill("Club 7 90")[0].iloc[0][["food", "quantity"]].tolist() == ["Club", 7.0]
    rows, _ = parse_bill("Club 7 90\nclub  7 2 180", known=["Club 7"])
    assert rows[["food", "quantity"]].values.tolist() == [["Club 7", 1.0], ["Club 7", 2.0]]
    # a "Bread 1" left by the old parser does not win over Bread
    rows, _ = parse_bill("Bread 1 45", known=["Bread", "Bread 1"])
    assert rows[["food", "quantity"]].values.tolist() == [["Bread", 1.0]]


def test_read_import_recognises_kind_and_removes_invalid_rows():
    raw = pd.DataFrame({"Date": ["2026-03-01", "2026-03-01", "bad", "2026-03-02", "2026-03-03"],
                        "Item": ["milk", "milk", "Milk", " MILK", "Eggs"],
                        "Qty": [2, 2, 1, -1, 12], "Price": [120, 120, 60, 60, 84]})
    kind, rows, report = read_import(raw)
    assert kind == "purchases" and len(rows) == 2
    assert (report["duplicates"], report["missing_date_or_food"], report["invalid_numbers"]) == (1, 1, 1)
    assert set(rows["food"]) == {"Milk", "Eggs"} or set(rows["food"]) == {"milk", "Eggs"}
    kind, rows, _ = read_import(pd.DataFrame({"date": ["2026-03-04"], "food": ["Milk"], "left": [1.5]}))
    assert kind == "checks" and rows.loc[0, "wasted"] == 0
    assert read_import(pd.DataFrame({"a": [1]}))[0] is None


def test_analysis_frame_balances_by_construction():
    from waste import balance_check
    frame = analysis_frame(BUYS, CHECKS)
    assert balance_check(frame)["failing"] == 0
    assert set(frame.columns) >= {"Date", "Food", "Quantity_Consumed", "Waste_Percentage", "Unit_Price"}


def test_period_forecasts_only_use_earlier_periods():
    from pantry import period_forecast_evaluation
    table = periods(BUYS, CHECKS)  # daily rates 0.5 then 0.25
    predictions, comparison = period_forecast_evaluation(table)
    assert len(predictions) == 1
    row = predictions.iloc[0]
    assert row["Actual"] == pytest.approx(0.25) and row["Previous period"] == pytest.approx(0.5)
    assert row["4-period average"] == pytest.approx(0.5)  # only the first period is in the past
    assert set(comparison["Model"]) == {"Previous period", "4-period average"} and comparison["n"].iloc[0] == 1


def test_purchase_outcomes_allocate_use_then_waste_oldest_first():
    from pantry import purchase_outcomes
    out = purchase_outcomes(BUYS, CHECKS).set_index("Date")
    first, second = out.loc[pd.Timestamp("2026-03-01")], out.loc[pd.Timestamp("2026-03-03")]
    # check 4 Mar: 4 available, 2 eaten (all of batch 1), 0.5 thrown away (from batch 2), 1.5 left
    assert first["Quantity_Consumed"] == 2 and first["Quantity_Wasted"] == 0
    assert first["Resolved"] == pd.Timestamp("2026-03-04") and first["Waste_Percentage"] == 0
    # check 8 Mar: 1.0 eaten from batch 2, 0.5 still left -> not resolved, so no label yet
    assert second["Quantity_Wasted"] == 0.5 and second["Quantity_Consumed"] == 1.0
    assert pd.isna(second["Resolved"]) and pd.isna(second["Waste_Percentage"])
    # batch 2 was bought before batch 1 was resolved, so it has no "recent consumption" history
    assert pd.isna(second["Recent_Consumption"])
