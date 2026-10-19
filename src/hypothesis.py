"""Hypothesis tests for the EDA page, each reported with H0/H1, statistic, p, effect size and a conclusion.

Effect sizes:
    Cohen's d  (difference in means / pooled SD)         0.2 small, 0.5 medium, 0.8 large
    eta²       (between-group SS / total SS)              0.01 small, 0.06 medium, 0.14 large
    Cramér's V (sqrt(chi² / (n * (min(rows, cols) - 1)))) 0.1 small, 0.3 medium, 0.5 large

With thousands of rows almost any difference is "significant", so the
conclusion always states the effect size as well as p.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import stats

ALPHA = 0.05


@dataclass
class TestResult:
    name: str
    question: str
    h0: str
    h1: str
    statistic_name: str
    statistic: float
    p_value: float
    effect_name: str
    effect: float
    effect_label: str
    n: int
    conclusion: str = ""
    extra: dict = field(default_factory=dict)


def _label(value: float, cuts: tuple[float, float, float]) -> str:
    size = abs(value)
    if np.isnan(size):
        return "undefined"
    return "large" if size >= cuts[2] else "medium" if size >= cuts[1] else "small" if size >= cuts[0] else "negligible"


def _conclude(result: TestResult, alpha: float = ALPHA) -> TestResult:
    if result.p_value < alpha:
        result.conclusion = (f"Reject H0 at α = {alpha}: p = {format_p(result.p_value)}. The effect is "
                             f"{result.effect_label} ({result.effect_name} = {result.effect:.3f}).")
    else:
        result.conclusion = (f"Do not reject H0 at α = {alpha}: p = {format_p(result.p_value)}; no evidence of a "
                             f"difference ({result.effect_name} = {result.effect:.3f}, {result.effect_label}).")
    return result


def format_p(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    a, b = np.asarray(a, float), np.asarray(b, float)
    pooled = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    return float((a.mean() - b.mean()) / pooled) if pooled > 0 else float("nan")


def welch_t(a, b, *, question: str, h0: str, h1: str) -> TestResult:
    a, b = pd.Series(a).dropna().to_numpy(float), pd.Series(b).dropna().to_numpy(float)
    t, p = stats.ttest_ind(a, b, equal_var=False)
    d = cohens_d(a, b)
    return _conclude(TestResult("Welch's t-test", question, h0, h1, "t", float(t), float(p), "Cohen's d", d,
                                _label(d, (0.2, 0.5, 0.8)), len(a) + len(b),
                                extra={"mean_a": a.mean(), "mean_b": b.mean(), "n_a": len(a), "n_b": len(b)}))


def eta_squared(groups: list[np.ndarray]) -> float:
    values = np.concatenate(groups)
    grand = values.mean()
    between = sum(len(g) * (g.mean() - grand) ** 2 for g in groups)
    total = ((values - grand) ** 2).sum()
    return float(between / total) if total > 0 else float("nan")


def anova(values: pd.Series, groups: pd.Series, *, question: str, h0: str, h1: str) -> tuple[TestResult, TestResult]:
    """One-way ANOVA with eta², plus Kruskal-Wallis as the non-parametric check."""
    frame = pd.DataFrame({"v": values, "g": groups}).dropna()
    arrays = [g["v"].to_numpy(float) for _, g in frame.groupby("g") if len(g) >= 2]
    f, p = stats.f_oneway(*arrays)
    eta = eta_squared(arrays)
    main = _conclude(TestResult("One-way ANOVA", question, h0, h1, "F", float(f), float(p), "η²", eta,
                                _label(eta, (0.01, 0.06, 0.14)), int(sum(map(len, arrays))),
                                extra={"groups": len(arrays)}))
    h, kp = stats.kruskal(*arrays)
    # epsilon² for Kruskal-Wallis: H / (n - 1)
    epsilon = float(h / (main.n - 1))
    check = _conclude(TestResult("Kruskal–Wallis", question, h0.replace("means", "distributions"),
                                 h1.replace("mean", "distribution"), "H", float(h), float(kp), "ε²", epsilon,
                                 _label(epsilon, (0.01, 0.06, 0.14)), main.n, extra={"groups": len(arrays)}))
    return main, check


def cramers_v(table: pd.DataFrame, chi2: float) -> float:
    n = table.to_numpy().sum()
    k = min(table.shape) - 1
    return float(np.sqrt(chi2 / (n * k))) if n > 0 and k > 0 else float("nan")


def chi_square(a: pd.Series, b: pd.Series, *, question: str, h0: str, h1: str) -> TestResult:
    table = pd.crosstab(a, b)
    chi2, p, dof, expected = stats.chi2_contingency(table, correction=False)
    v = cramers_v(table, chi2)
    small = float((expected < 5).mean() * 100)
    return _conclude(TestResult("χ² test of independence", question, h0, h1, "χ²", float(chi2), float(p),
                                "Cramér's V", v, _label(v, (0.1, 0.3, 0.5)), int(table.to_numpy().sum()),
                                extra={"dof": int(dof), "cells_expected_below_5_pct": small, "table": table}))


# --- assembled per source ---------------------------------------------------------
def relative_to_mean(values: pd.Series, keys: pd.Series) -> pd.Series:
    """Each value as % of its own group's mean (unit-free across foods or items)."""
    return values / values.groupby(keys).transform("mean") * 100


def household_tests(df: pd.DataFrame, *, daily: bool = True) -> list[TestResult]:
    """Demo data (daily) or My data (per period: the weekend t-test is skipped)."""
    results = []
    if daily:
        relative = relative_to_mean(df["Quantity_Consumed"], df["Food"])
        weekend = df["Date"].dt.dayofweek >= 5
        results.append(welch_t(
            relative[weekend], relative[~weekend],
            question="Is consumption different at weekends?",
            h0="Mean consumption (as % of each food's average) is the same on weekends and weekdays.",
            h1="Mean consumption differs between weekends and weekdays."))
    results.extend(anova(
        df["Waste_Percentage"], df["Category"],
        question="Does waste % differ between food categories?",
        h0="Mean waste % is the same in every category.",
        h1="At least one category has a different mean waste %."))
    high = df["Waste_Percentage"] > df["Waste_Percentage"].median()
    valid = df["Waste_Percentage"].notna()
    results.append(chi_square(
        df.loc[valid, "Category"], high[valid].map({True: "High waste", False: "Not high"}),
        question="Is being a high-waste record related to the category?",
        h0="Category and high waste (waste % above the median) are independent.",
        h1="High waste is more common in some categories."))
    return results


def m5_tests(df: pd.DataFrame) -> list[TestResult]:
    relative = relative_to_mean(df["Quantity_Sold"].astype(float), df["Product_ID"])
    weekend = df["Date"].dt.dayofweek >= 5
    results = [welch_t(relative[weekend], relative[~weekend],
                       question="Do items sell differently at weekends?",
                       h0="Mean unit sales (as % of each item's average) are the same on weekends and weekdays.",
                       h1="Mean unit sales differ between weekends and weekdays.")]
    results.extend(anova(df["Quantity_Sold"].astype(float), df["Department"].astype(str),
                         question="Do unit sales per item-day differ across departments?",
                         h0="Mean units sold per item-day are the same in every department.",
                         h1="At least one department has a different mean."))
    return results


def instacart_tests(df: pd.DataFrame) -> list[TestResult]:
    return [chi_square(df["Department"].astype(str), df["Reordered"].map({1: "Reordered", 0: "First purchase"}),
                       question="Does the reorder rate depend on the department?",
                       h0="Department and whether a product line is a reorder are independent.",
                       h1="Some departments are reordered more often than others.")]
