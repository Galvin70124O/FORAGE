"""Hypothesis tests: statistics match scipy, effect sizes match hand calculations, conclusions follow alpha."""

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from hypothesis import (
    anova,
    chi_square,
    cohens_d,
    cramers_v,
    eta_squared,
    household_tests,
    instacart_tests,
    m5_tests,
    welch_t,
)

KW = dict(question="q", h0="H0", h1="H1")


def test_welch_t_matches_scipy_and_cohens_d_by_hand():
    a, b = np.array([5.0, 6, 7, 8]), np.array([1.0, 2, 3, 4])
    result = welch_t(a, b, **KW)
    t, p = stats.ttest_ind(a, b, equal_var=False)
    assert result.statistic == pytest.approx(t) and result.p_value == pytest.approx(p)
    # both SDs = sqrt(5/3); pooled SD = sqrt(5/3); d = 4 / sqrt(5/3)
    assert cohens_d(a, b) == pytest.approx(4 / np.sqrt(5 / 3))
    assert result.effect_label == "large" and result.conclusion.startswith("Reject H0")


def test_no_difference_is_not_rejected():
    rng = np.random.default_rng(0)
    a, b = rng.normal(0, 1, 50), rng.normal(0, 1, 50)
    result = welch_t(a, b, **KW)
    assert result.p_value > 0.05 and result.conclusion.startswith("Do not reject H0")


def test_anova_eta_squared_and_kruskal():
    values = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9], dtype=float)
    groups = pd.Series(list("aaabbbccc"))
    main, check = anova(values, groups, **KW)
    f, p = stats.f_oneway([1, 2, 3], [4, 5, 6], [7, 8, 9])
    assert main.statistic == pytest.approx(f) and main.p_value == pytest.approx(p)
    # group means 2, 5, 8; grand mean 5; between = 3*(9+0+9) = 54; total = 60 -> eta² = 0.9
    assert eta_squared([np.array([1., 2, 3]), np.array([4., 5, 6]), np.array([7., 8, 9])]) == pytest.approx(0.9)
    h, kp = stats.kruskal([1, 2, 3], [4, 5, 6], [7, 8, 9])
    assert check.statistic == pytest.approx(h) and check.p_value == pytest.approx(kp)


def test_chi_square_and_cramers_v_by_hand():
    a = pd.Series(["x"] * 30 + ["y"] * 30)
    b = pd.Series(["yes"] * 25 + ["no"] * 5 + ["yes"] * 5 + ["no"] * 25)
    result = chi_square(a, b, **KW)
    table = pd.crosstab(a, b)
    chi2, p, _, _ = stats.chi2_contingency(table, correction=False)
    assert result.statistic == pytest.approx(chi2) and result.p_value == pytest.approx(p)
    assert cramers_v(table, chi2) == pytest.approx(np.sqrt(chi2 / 60))
    assert result.effect_label == "large"


def test_household_tests_on_demo_shape_and_period_mode():
    rng = np.random.default_rng(1)
    dates = pd.date_range("2025-01-01", periods=56)
    df = pd.DataFrame({"Date": np.tile(dates, 2), "Food": ["Milk"] * 56 + ["Rice"] * 56,
                       "Category": ["Dairy"] * 56 + ["Grains"] * 56,
                       "Quantity_Consumed": rng.uniform(1, 2, 112), "Waste_Percentage": rng.uniform(0, 40, 112)})
    names = [r.name for r in household_tests(df)]
    assert names == ["Welch's t-test", "One-way ANOVA", "Kruskal–Wallis", "χ² test of independence"]
    assert "Welch's t-test" not in [r.name for r in household_tests(df, daily=False)]


def test_public_source_tests():
    m5 = pd.DataFrame({"Date": pd.date_range("2016-01-01", periods=40).repeat(2), "Product_ID": ["A", "B"] * 40,
                       "Department": ["FOODS_1", "FOODS_3"] * 40, "Quantity_Sold": np.arange(80) % 7})
    assert [r.name for r in m5_tests(m5)] == ["Welch's t-test", "One-way ANOVA", "Kruskal–Wallis"]
    insta = pd.DataFrame({"Department": ["dairy"] * 20 + ["snacks"] * 20, "Reordered": [1] * 15 + [0] * 5 + [1] * 5 + [0] * 15})
    assert instacart_tests(insta)[0].effect > 0.4
