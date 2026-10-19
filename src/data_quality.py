"""Data-quality checks and safe cleaning for mapped external FORAGE datasets."""

import pandas as pd


NUMERIC_COLUMNS = [
    "Quantity_Purchased",
    "Quantity_Consumed",
    "Quantity_Wasted",
    "Remaining_Quantity",
    "Price",
    "Expiry_Days",
    "Is_Festival",
]
QUANTITY_COLUMNS = [
    "Quantity_Purchased",
    "Quantity_Consumed",
    "Quantity_Wasted",
    "Remaining_Quantity",
]


def _invalid_numeric_counts(df):
    counts = {}
    for column in NUMERIC_COLUMNS:
        if column in df:
            converted = pd.to_numeric(df[column], errors="coerce")
            counts[column] = int((df[column].notna() & converted.isna()).sum())
    return counts


def _outlier_summary(df):
    """Find IQR outliers without automatically treating them as invalid."""
    summary = {}
    for column in NUMERIC_COLUMNS:
        if column not in df:
            continue
        values = pd.to_numeric(df[column], errors="coerce").dropna()
        if len(values) < 4:
            summary[column] = {"count": 0, "lower_bound": None, "upper_bound": None}
            continue
        q1, q3 = values.quantile([0.25, 0.75])
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        count = int(((values < lower_bound) | (values > upper_bound)).sum())
        summary[column] = {
            "count": count,
            "lower_bound": round(float(lower_bound), 2),
            "upper_bound": round(float(upper_bound), 2),
        }
    return summary


def column_profile(df):
    """Per-column type, missing count/share and distinct values for a quality table."""
    rows = len(df)
    return pd.DataFrame({
        "Column": df.columns,
        "Type": [str(dtype) for dtype in df.dtypes],
        "Missing": df.isna().sum().to_numpy(),
        "Missing (%)": (df.isna().mean() * 100).to_numpy() if rows else 0.0,
        "Distinct": [df[column].nunique(dropna=True) for column in df.columns],
    })


def iqr_outliers(df, columns):
    """IQR outlier counts for any numeric columns (flagged for review, never removed)."""
    rows = []
    for column in columns:
        values = pd.to_numeric(df[column], errors="coerce").dropna()
        if len(values) < 4:
            continue
        q1, q3 = values.quantile([0.25, 0.75])
        low, high = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        count = int(((values < low) | (values > high)).sum())
        rows.append({"Column": column, "Lower bound": low, "Upper bound": high,
                     "Outliers": count, "Outliers (%)": count / len(values) * 100})
    return pd.DataFrame(rows, columns=["Column", "Lower bound", "Upper bound", "Outliers", "Outliers (%)"])


def build_quality_report(df, missing_standard_columns, unmapped_source_columns):
    """Create a plain-Python report that can be printed or saved as JSON later."""
    invalid_dates = 0
    if "Date" in df:
        converted_dates = pd.to_datetime(df["Date"], errors="coerce")
        invalid_dates = int((df["Date"].notna() & converted_dates.isna()).sum())

    negative_values = {}
    for column in QUANTITY_COLUMNS + ["Price", "Expiry_Days"]:
        if column in df:
            numeric_values = pd.to_numeric(df[column], errors="coerce")
            negative_values[column] = int((numeric_values < 0).sum())

    return {
        "rows": len(df),
        "columns": list(df.columns),
        "data_types": {column: str(dtype) for column, dtype in df.dtypes.items()},
        "missing_values": {column: int(count) for column, count in df.isna().sum().items()},
        "duplicate_rows": int(df.duplicated().sum()),
        "invalid_numeric_values": _invalid_numeric_counts(df),
        "invalid_dates": invalid_dates,
        "negative_values": negative_values,
        "suspicious_outliers_iqr": _outlier_summary(df),
        "missing_required_standard_columns": sorted(missing_standard_columns),
        "unmapped_source_columns": list(unmapped_source_columns),
    }


def clean_and_derive_features(df):
    """Apply safe conversions, remove clearly invalid rows, and add supported features.

    Outliers are retained because unusual purchases can be genuine. The returned
    summary documents every row-removal decision.
    """
    cleaned = df.copy()
    summary = {"duplicates_removed": 0, "rows_removed_missing_food": 0,
               "rows_removed_invalid_date": 0, "rows_removed_invalid_values": 0,
               "derived_columns": []}

    before = len(cleaned)
    cleaned = cleaned.drop_duplicates().copy()
    summary["duplicates_removed"] = before - len(cleaned)

    if "Food" in cleaned:
        cleaned["Food"] = cleaned["Food"].astype("string").str.strip()
        cleaned.loc[cleaned["Food"].isin(["", "nan", "None"]), "Food"] = pd.NA
        before = len(cleaned)
        cleaned = cleaned.dropna(subset=["Food"]).copy()
        summary["rows_removed_missing_food"] = before - len(cleaned)

    if "Date" in cleaned:
        cleaned["Date"] = pd.to_datetime(cleaned["Date"], errors="coerce")
        before = len(cleaned)
        cleaned = cleaned.dropna(subset=["Date"]).copy()
        summary["rows_removed_invalid_date"] = before - len(cleaned)

    if "Estimated_Expiry_Date" in cleaned:
        cleaned["Estimated_Expiry_Date"] = pd.to_datetime(
            cleaned["Estimated_Expiry_Date"], errors="coerce"
        )

    for column in NUMERIC_COLUMNS:
        if column in cleaned:
            cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

    invalid_rows = pd.Series(False, index=cleaned.index)
    for column in QUANTITY_COLUMNS + ["Price", "Expiry_Days"]:
        if column in cleaned:
            invalid_rows |= cleaned[column].lt(0).fillna(False)
    if "Quantity_Purchased" in cleaned:
        invalid_rows |= cleaned["Quantity_Purchased"].le(0).fillna(False)
    if "Is_Festival" in cleaned:
        invalid_rows |= ~cleaned["Is_Festival"].isin([0, 1]) & cleaned["Is_Festival"].notna()
    summary["rows_removed_invalid_values"] = int(invalid_rows.sum())
    cleaned = cleaned.loc[~invalid_rows].copy()

    if "Date" in cleaned:
        cleaned["Day_of_Week"] = cleaned["Date"].dt.day_name()
        cleaned["Month"] = cleaned["Date"].dt.month
        cleaned["Is_Weekend"] = (cleaned["Date"].dt.dayofweek >= 5).astype(int)
        summary["derived_columns"].extend(["Day_of_Week", "Month", "Is_Weekend"])
    if {"Quantity_Purchased", "Quantity_Wasted"}.issubset(cleaned.columns):
        cleaned["Waste_Percentage"] = (
            cleaned["Quantity_Wasted"] / cleaned["Quantity_Purchased"] * 100
        ).round(2)
        summary["derived_columns"].append("Waste_Percentage")
    if {"Quantity_Purchased", "Quantity_Consumed"}.issubset(cleaned.columns):
        cleaned["Consumption_Rate"] = (
            cleaned["Quantity_Consumed"] / cleaned["Quantity_Purchased"]
        ).round(4)
        summary["derived_columns"].append("Consumption_Rate")
    if ("Remaining_Quantity" not in cleaned and
            {"Quantity_Purchased", "Quantity_Consumed", "Quantity_Wasted"}.issubset(cleaned.columns)):
        cleaned["Remaining_Quantity"] = (
            cleaned["Quantity_Purchased"] - cleaned["Quantity_Consumed"] - cleaned["Quantity_Wasted"]
        ).round(2)
        summary["derived_columns"].append("Remaining_Quantity")

    if "Date" in cleaned and "Food" in cleaned:
        cleaned = cleaned.sort_values(["Date", "Food"]).reset_index(drop=True)
    return cleaned, summary


def print_quality_report(report):
    """Print the most useful quality checks in a concise, viva-friendly form."""
    print("\nDATA-QUALITY REPORT")
    print(f"Mapped dataset: {report['rows']} rows x {len(report['columns'])} columns")
    print(f"Duplicate rows: {report['duplicate_rows']}")
    print(f"Invalid dates: {report['invalid_dates']}")
    print(f"Missing required columns: {report['missing_required_standard_columns'] or 'None'}")
    print(f"Unmapped source columns: {report['unmapped_source_columns'] or 'None'}")
    print("Missing values:", report["missing_values"])
    print("Invalid numeric values:", report["invalid_numeric_values"])
    print("Negative values:", report["negative_values"])
    print("IQR outlier counts (flagged, not removed):",
          {name: values["count"] for name, values in report["suspicious_outliers_iqr"].items()})
