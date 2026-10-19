"""Association rules on a basket small enough to check by hand."""

import pandas as pd
import pytest

from basket import baskets, bought_together, find_rules


def orders():
    # orders: {A,B}, {A,B}, {A,C}, {B,C}, {A,B,C}, {C} (single item: dropped)
    rows = [(1, "A"), (1, "B"), (2, "A"), (2, "B"), (3, "A"), (3, "C"), (4, "B"), (4, "C"),
            (5, "A"), (5, "B"), (5, "C"), (6, "C")]
    return pd.DataFrame(rows, columns=["Order_ID", "Product_Name"])


def test_baskets_drop_single_item_orders_and_keep_top_products():
    matrix = baskets(orders(), top_n=3)
    assert len(matrix) == 5 and set(matrix.columns) == {"A", "B", "C"}
    assert baskets(orders(), top_n=2).shape[1] == 2


def test_support_confidence_and_lift_match_hand_calculation():
    rules = find_rules(baskets(orders()), min_support=0.2, min_lift=0.0)
    a_to_b = rules[(rules["If"] == "A") & (rules["Then"] == "B")].iloc[0]
    # 5 baskets; A in 4, B in 4, A and B together in 3
    assert a_to_b["Support"] == pytest.approx(3 / 5)
    assert a_to_b["Confidence"] == pytest.approx(3 / 4)
    assert a_to_b["Lift"] == pytest.approx((3 / 4) / (4 / 5))
    assert rules["Lift"].is_monotonic_decreasing


def test_lookup_returns_rules_starting_from_the_product():
    rules = find_rules(baskets(orders()), min_support=0.2, min_lift=0.0)
    together = bought_together(rules, "A")
    assert set(together["Then"]) <= {"B", "C", "B + C"} and len(together) >= 1
    assert find_rules(baskets(orders()), min_support=0.9).empty


def test_strongest_rules_keep_each_item_set_once():
    from basket import strongest_rules
    rules = find_rules(baskets(orders()), min_support=0.2, min_lift=0.0)
    top = strongest_rules(rules, 10)
    sets = [a | c for a, c in zip(top["Antecedents"], top["Consequents"])]
    assert len(sets) == len(set(sets))
