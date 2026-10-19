"""Descriptive statistics used by the EDA page and the report.

Every function is pure (DataFrame in, DataFrame/str out) so it can be tested
without Streamlit. Missing values are excluded from each statistic and counted
separately; they are never filled in.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def descriptive_statistics(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Return count, missing, mean, median, mode, std, min, max, Q1, Q3 and IQR.

    The mode is the most frequent recorded value; when several values tie, the
    smallest is reported so the result is deterministic. Std is the sample
    standard deviation (ddof=1), matching pandas and most textbooks.
    """
    rows = []
    for column in columns:
        values = pd.to_numeric(df[column], errors="coerce")
        present = values.dropna()
        modes = present.mode()
        q1, q3 = (present.quantile([0.25, 0.75]).tolist() if not present.empty else (np.nan, np.nan))
        rows.append({
            "Column": column,
            "Count": int(present.size),
            "Missing": int(values.isna().sum()),
            "Mean": present.mean(),
            "Median": present.median(),
            "Mode": modes.min() if not modes.empty else np.nan,
            "Std": present.std(ddof=1),
            "Min": present.min(),
            "Max": present.max(),
            "Q1": q1,
            "Q3": q3,
            "IQR": q3 - q1,
        })
    return pd.DataFrame(rows).set_index("Column")


def frequency_table(series: pd.Series, *, label: str | None = None) -> pd.DataFrame:
    """Count and percentage for each category, most frequent first. Missing values get their own row."""
    counts = series.astype("object").fillna("(missing)").value_counts()
    table = pd.DataFrame({"Count": counts, "Share (%)": counts / counts.sum() * 100})
    table.index.name = label or series.name
    return table


def category_aggregation(df: pd.DataFrame, by: str, value: str) -> pd.DataFrame:
    """Total, mean and record count of `value` per `by` group, largest total first."""
    return (df.groupby(by, observed=True)[value]
            .agg(Total="sum", Mean="mean", Records="count")
            .sort_values("Total", ascending=False))


def correlation_matrix(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Pearson correlation of the given columns, ignoring constant columns.

    A constant column has zero variance, so its correlation is undefined; it is
    dropped instead of being shown as a row of blanks.
    """
    numeric = df[columns].apply(pd.to_numeric, errors="coerce")
    varying = [column for column in columns if numeric[column].nunique(dropna=True) > 1]
    return numeric[varying].corr(method="pearson")


def strongest_correlations(corr: pd.DataFrame, n: int = 3, *, exclude_pairs: set[frozenset] | None = None) -> pd.DataFrame:
    """The `n` off-diagonal pairs with the largest absolute correlation."""
    exclude_pairs = exclude_pairs or set()
    pairs = []
    columns = list(corr.columns)
    for i, first in enumerate(columns):
        for second in columns[i + 1:]:
            if frozenset((first, second)) in exclude_pairs:
                continue
            value = corr.loc[first, second]
            if pd.notna(value):
                pairs.append({"First": first, "Second": second, "r": value})
    table = pd.DataFrame(pairs, columns=["First", "Second", "r"])
    return table.reindex(table["r"].abs().sort_values(ascending=False).index).head(n).reset_index(drop=True)


def describe_strength(r: float) -> str:
    """Conventional verbal label for |r| (Cohen-style cut-offs)."""
    size = abs(r)
    if size >= 0.7:
        strength = "strong"
    elif size >= 0.4:
        strength = "moderate"
    elif size >= 0.2:
        strength = "weak"
    else:
        return "no meaningful"
    return f"{strength} {'positive' if r > 0 else 'negative'}"
