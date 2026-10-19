import numpy as np
import pandas as pd
import pytest

from dataset_registry import get_dataset
from waste import (
    WasteNotSupported,
    balance_check,
    category_waste,
    expiring_stock,
    food_waste,
    overall_waste,
    perishable_waste_by_category,
    waste_vs_shelf_life,
)


def frame(rows):
    columns = ["Food", "Category", "Quantity_Unit", "Quantity_Purchased", "Quantity_Consumed",
               "Quantity_Wasted", "Remaining_Quantity", "Expiry_Days", "Estimated_Expiry_Date"]
    return pd.DataFrame(rows, columns=columns)


def test_food_waste_rate_is_ratio_of_totals_not_mean_of_row_percentages():
    df = frame([["A", "X", "kg", 10, 9, 1, 0, 5, "2025-01-06"],
                ["A", "X", "kg", 1, 0, 1, 0, 5, "2025-01-06"]])
    rate = food_waste(df).loc[0, "Waste_Rate"]
    assert rate == pytest.approx(2 / 11 * 100)  # not mean(10%, 100%) = 55%


def test_zero_purchase_gives_undefined_rate_not_zero_or_infinity():
    df = frame([["A", "X", "kg", 0, 0, 0, 0, 5, None]])
    assert np.isnan(food_waste(df).loc[0, "Waste_Rate"])


def test_category_and_overall_rates_average_food_rates_across_units():
    df = frame([["Milk", "Dairy", "L", 100, 90, 10, 0, 7, None],     # 10%
                ["Cheese", "Dairy", "kg", 1, 0.5, 0.5, 0, 30, None],  # 50%
                ["Rice", "Grains", "kg", 10, 8, 2, 0, 90, None]])     # 20%
    assert category_waste(df).loc["Dairy", "Waste_Rate"] == pytest.approx(30)
    headline = overall_waste(df)
    assert headline["rate"] == pytest.approx((10 + 50 + 20) / 3)
    assert headline["pooled_rate"] == pytest.approx(12.5 / 111 * 100)


def test_balance_check_flags_records_that_do_not_add_up():
    df = frame([["A", "X", "kg", 2, 1.2, 0.3, 0.5, 7, None],
                ["B", "X", "kg", 2, 1.2, 0.3, 0.9, 7, None]])
    result = balance_check(df)
    assert result == {"checked": 2, "failing": 1, "max_abs_residual": pytest.approx(0.4)}


def test_expiring_stock_window_excludes_expired_and_empty_batches():
    as_of = pd.Timestamp("2025-01-10")
    df = frame([
        ["Milk", "Dairy", "L", 2, 1, 0, 1, 7, "2025-01-10"],     # 0 days left -> in
        ["Bread", "Bakery", "loaf", 1, 0, 0, 1, 5, "2025-01-13"],  # 3 days -> in 3 and 7
        ["Eggs", "Protein", "dozen", 1, 0, 0, 1, 21, "2025-01-16"],  # 6 days -> only in 7
        ["Curd", "Dairy", "kg", 1, 0, 0, 1, 7, "2025-01-09"],     # already expired -> out
        ["Tofu", "Protein", "kg", 1, 1, 0, 0, 7, "2025-01-11"],   # nothing left -> out
    ])
    assert set(expiring_stock(df, as_of, 3)["Food"]) == {"Milk", "Bread"}
    assert set(expiring_stock(df, as_of, 7)["Food"]) == {"Milk", "Bread", "Eggs"}
    assert expiring_stock(df, as_of, 3).loc[0, "Food"] == "Milk"  # soonest first


def test_perishable_waste_only_counts_short_shelf_life_foods():
    df = frame([["Milk", "Dairy", "L", 10, 8, 2, 0, 7, None],
                ["Cheese", "Dairy", "kg", 10, 5, 5, 0, 30, None],
                ["Bread", "Bakery", "loaf", 10, 9, 1, 0, 5, None]])
    table = perishable_waste_by_category(df)
    assert table.loc["Dairy", "Waste_Rate"] == pytest.approx(20)
    assert table.loc["Dairy", "Food_List"] == "Milk"
    assert list(table.index) == ["Dairy", "Bakery"]


def test_waste_vs_shelf_life_correlation_sign():
    df = frame([["A", "X", "kg", 10, 9, 1, 0, 3, None],
                ["B", "X", "kg", 10, 8, 2, 0, 7, None],
                ["C", "X", "kg", 10, 7, 3, 0, 30, None]])
    _, r = waste_vs_shelf_life(df)
    assert r > 0.8


M5_COLUMNS = ["Date", "Product_ID", "Store_ID", "Department", "Category", "Quantity_Sold", "Price",
              "Weekday", "Month", "Event_Name", "Event_Type"]
INSTACART_COLUMNS = ["Order_ID", "User_ID", "Order_Set", "Order_Number", "Order_Day_Of_Week", "Order_Hour",
                     "Days_Since_Prior_Order", "Product_ID", "Product_Name", "Aisle", "Department",
                     "Add_To_Cart_Order", "Reordered"]


@pytest.mark.parametrize("columns", [M5_COLUMNS, INSTACART_COLUMNS])
@pytest.mark.parametrize("func", [food_waste, overall_waste, balance_check, waste_vs_shelf_life,
                                  perishable_waste_by_category])
def test_waste_is_never_computed_for_public_sources(columns, func):
    with pytest.raises(WasteNotSupported):
        func(pd.DataFrame(columns=columns))


@pytest.mark.parametrize("source", ["m5", "instacart"])
def test_registry_prohibits_waste_for_public_sources(source):
    dataset = get_dataset(source)
    assert "waste" in dataset["prohibits"] and "waste" not in dataset["supports"]
