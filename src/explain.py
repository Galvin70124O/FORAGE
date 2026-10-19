"""Model explanations on held-out data: permutation importance, residuals and error by group.

Permutation importance shuffles one input column at a time in the TEST rows
and measures how much the score gets worse; it is computed on the raw input
columns (before one-hot encoding), so each bar is a feature a person would
recognise. A feature with importance near 0 is not used by the model.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance


def importance(model, X: pd.DataFrame, y: pd.Series, *, scoring: str, repeats: int = 5,
               seed: int = 42) -> pd.DataFrame:
    """Mean and std drop in `scoring` when each column of X is shuffled (larger = more important)."""
    result = permutation_importance(model, X, y, scoring=scoring, n_repeats=repeats, random_state=seed, n_jobs=1)
    return (pd.DataFrame({"Feature": X.columns, "Importance": result.importances_mean, "Std": result.importances_std})
            .sort_values("Importance", ascending=False).reset_index(drop=True))


def residual_frame(actual: pd.Series, predicted: pd.Series, groups: pd.DataFrame) -> pd.DataFrame:
    frame = groups.copy()
    frame["Actual"], frame["Predicted"] = actual.to_numpy(), predicted.to_numpy()
    frame["Residual"] = frame["Actual"] - frame["Predicted"]
    return frame


def error_by(residuals: pd.DataFrame, key: str) -> pd.DataFrame:
    """MAE per group and MAE relative to the group's mean actual value (unit-free)."""
    grouped = residuals.groupby(key, observed=True)
    table = pd.DataFrame({"MAE": grouped["Residual"].apply(lambda r: r.abs().mean()),
                          "Mean_Actual": grouped["Actual"].mean(), "Bias": grouped["Residual"].mean(),
                          "Rows": grouped.size()})
    table["Relative_MAE"] = table["MAE"] / table["Mean_Actual"].where(table["Mean_Actual"] > 0) * 100
    return table.sort_values("Relative_MAE", ascending=False).reset_index()


def reading(residuals: pd.DataFrame, by_group: pd.DataFrame, key: str, unit: str) -> str:
    """One line on where the model fails: the worst group and any systematic bias."""
    worst = by_group.iloc[0]
    best = by_group.iloc[-1]
    bias = residuals["Residual"].mean()
    spread = residuals["Residual"].abs().mean()
    tendency = ("no systematic bias" if abs(bias) < 0.1 * spread else
                f"a tendency to {'under' if bias > 0 else 'over'}-predict (mean residual {bias:+.3f} {unit})")
    big = residuals["Residual"].abs() > 2 * residuals["Residual"].abs().std()
    peaks = "larger misses on high-demand days" if residuals.loc[big, "Actual"].mean() > residuals["Actual"].mean() else \
        "larger misses spread across the range"
    return (f"The model struggles most with {worst[key]} (typical error {worst['Relative_MAE']:.0f}% of its average) "
            f"and least with {best[key]} ({best['Relative_MAE']:.0f}%); residuals show {tendency} and {peaks}.")


def sample(frame: pd.DataFrame, n: int = 1500, seed: int = 42) -> pd.DataFrame:
    """A fixed random sample for scatter plots (keeps charts light)."""
    return frame.sample(n=min(n, len(frame)), random_state=seed) if len(frame) > n else frame


def top_feature_sentence(table: pd.DataFrame, metric: str) -> str:
    top = table.iloc[0]
    useless = table[table["Importance"] <= np.maximum(table["Std"], 1e-9)]["Feature"].tolist()
    text = (f"Shuffling {top['Feature']} hurts the model most ({metric} worsens by {top['Importance']:.3f}), so "
            "it relies on it most.")
    if useless:
        text += " " + ", ".join(useless) + (" adds" if len(useless) == 1 else " add") + " almost nothing."
    return text
