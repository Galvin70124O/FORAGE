import numpy as np
import pandas as pd
import pytest

from stats import (
    category_aggregation,
    correlation_matrix,
    describe_strength,
    descriptive_statistics,
    frequency_table,
    strongest_correlations,
)


def test_descriptive_statistics_known_values():
    df = pd.DataFrame({"x": [1.0, 2.0, 2.0, 3.0, np.nan]})
    row = descriptive_statistics(df, ["x"]).loc["x"]
    assert row["Count"] == 4 and row["Missing"] == 1
    assert row["Mean"] == 2.0 and row["Median"] == 2.0 and row["Mode"] == 2.0
    assert row["Std"] == pytest.approx(np.std([1, 2, 2, 3], ddof=1))
    assert (row["Min"], row["Max"]) == (1.0, 3.0)
    assert row["IQR"] == pytest.approx(row["Q3"] - row["Q1"])


def test_zero_is_a_value_not_missing():
    row = descriptive_statistics(pd.DataFrame({"x": [0.0, 0.0, 4.0]}), ["x"]).loc["x"]
    assert row["Missing"] == 0 and row["Mean"] == pytest.approx(4 / 3) and row["Mode"] == 0.0


def test_mode_tie_is_deterministic():
    row = descriptive_statistics(pd.DataFrame({"x": [5, 5, 1, 1, 3]}), ["x"]).loc["x"]
    assert row["Mode"] == 1


def test_frequency_table_counts_missing_and_sums_to_100():
    table = frequency_table(pd.Series(["Dairy", "Dairy", "Fruit", None], name="Category"))
    assert table.loc["Dairy", "Count"] == 2
    assert table.loc["(missing)", "Count"] == 1
    assert table["Share (%)"].sum() == pytest.approx(100)


def test_category_aggregation_uses_requested_column():
    df = pd.DataFrame({"Category": ["A", "A", "B"], "Wasted": [1.0, 3.0, 10.0], "Other": [100, 100, 0]})
    table = category_aggregation(df, "Category", "Wasted")
    assert table.loc["A", "Total"] == 4 and table.loc["A", "Mean"] == 2 and table.index[0] == "B"


def test_correlation_drops_constant_columns_and_is_symmetric():
    df = pd.DataFrame({"a": [1, 2, 3, 4], "b": [2, 4, 6, 8], "c": [4, 3, 2, 1], "k": [7, 7, 7, 7]})
    corr = correlation_matrix(df, ["a", "b", "c", "k"])
    assert "k" not in corr.columns
    assert corr.loc["a", "b"] == pytest.approx(1.0)
    assert corr.loc["a", "c"] == pytest.approx(-1.0)
    assert np.allclose(corr.values, corr.values.T)


def test_strongest_correlations_ranks_by_absolute_value_and_can_exclude():
    corr = pd.DataFrame([[1, 0.3, -0.9], [0.3, 1, 0.5], [-0.9, 0.5, 1]], index=list("abc"), columns=list("abc"))
    top = strongest_correlations(corr, 2)
    assert list(zip(top["First"], top["Second"])) == [("a", "c"), ("b", "c")]
    top = strongest_correlations(corr, 1, exclude_pairs={frozenset("ac")})
    assert (top.loc[0, "First"], top.loc[0, "Second"]) == ("b", "c")


@pytest.mark.parametrize("r,label", [(0.85, "strong positive"), (-0.5, "moderate negative"),
                                     (0.25, "weak positive"), (0.05, "no meaningful")])
def test_describe_strength(r, label):
    assert describe_strength(r) == label
