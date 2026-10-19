"""Cleaning and validation for the raw demo food records.

Run from the project root with:
    python src/clean_data.py
"""

from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw_food_data.csv"
CLEANED_DATA_PATH = PROJECT_ROOT / "data" / "cleaned_food_data.csv"
BALANCE_TOLERANCE = 0.011  # raw quantities are rounded to two decimals

TEXT_COLUMNS = [
    "Food",
    "Category",
    "Input_Method",
    "Source_Reference",
    "Quantity_Unit",
    "Storage_Type",
]
NUMERIC_COLUMNS = [
    "Quantity_Purchased",
    "Quantity_Consumed",
    "Quantity_Wasted",
    "Quantity_Remaining",
    "Price",
    "Expiry_Days",
    "Is_Festival",
]
REQUIRED_COLUMNS = {
    "Date",
    "Food",
    "Category",
    "Input_Method",
    "Source_Reference",
    "Quantity_Unit",
    "Quantity_Purchased",
    "Quantity_Consumed",
    "Quantity_Wasted",
    "Quantity_Remaining",
    "Price",
    "Expiry_Days",
    "Estimated_Expiry_Date",
    "Storage_Type",
    "Is_Festival",
}


def clean_records(df):
    """Clean and validate raw food purchase records.

    Returns (cleaned, summary). Nothing is imputed: a row missing a required
    value, or failing a validity rule, is removed and counted under the first
    rule it fails. Text fields that are blank become "Unknown" (a label, not an
    invented measurement). Outliers are kept; see data_quality for IQR flags.
    """
    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(f"Raw data is missing columns: {sorted(missing_columns)}")

    summary = {"rows_read": len(df)}
    df = df.drop_duplicates().copy()
    summary["duplicates_removed"] = summary["rows_read"] - len(df)

    for column in TEXT_COLUMNS:
        df[column] = df[column].fillna("Unknown").astype(str).str.strip()
        df.loc[df[column] == "", column] = "Unknown"

    # Invalid dates/numbers become missing here and are removed below.
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Estimated_Expiry_Date"] = pd.to_datetime(df["Estimated_Expiry_Date"], errors="coerce")
    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    required_values = [
        "Date", "Quantity_Purchased", "Quantity_Consumed", "Quantity_Wasted",
        "Quantity_Remaining", "Price", "Expiry_Days", "Estimated_Expiry_Date", "Is_Festival",
    ]
    has_missing = df[required_values].isna().any(axis=1)
    summary["missing_or_unparseable_removed"] = int(has_missing.sum())
    df = df[~has_missing].copy()

    quantity_is_valid = (
        (df["Quantity_Purchased"] > 0)
        & (df["Quantity_Consumed"] >= 0)
        & (df["Quantity_Wasted"] >= 0)
        & (df["Quantity_Remaining"] >= 0)
        & (df["Quantity_Remaining"] <= df["Quantity_Purchased"])
        & (df["Price"] >= 0)
        & (df["Expiry_Days"] >= 0)
        & (df["Is_Festival"].isin([0, 1]))
    )
    summary["invalid_values_removed"] = int((~quantity_is_valid).sum())
    df = df[quantity_is_valid].copy()

    # purchased = consumed + wasted + remaining, allowing for 2-dp rounding.
    balance_difference = (
        df["Quantity_Purchased"] - df["Quantity_Consumed"]
        - df["Quantity_Wasted"] - df["Quantity_Remaining"]
    )
    balance_is_valid = balance_difference.abs() <= BALANCE_TOLERANCE
    summary["unbalanced_removed"] = int((~balance_is_valid).sum())
    df = df[balance_is_valid].copy()

    expected_expiry_date = df["Date"] + pd.to_timedelta(df["Expiry_Days"], unit="D")
    expiry_is_valid = df["Estimated_Expiry_Date"] == expected_expiry_date
    summary["inconsistent_expiry_removed"] = int((~expiry_is_valid).sum())
    df = df[expiry_is_valid].copy()

    df = df.rename(columns={"Quantity_Remaining": "Remaining_Quantity"})
    df["Expiry_Days"] = df["Expiry_Days"].astype(int)
    df["Is_Festival"] = df["Is_Festival"].astype(int)

    df["Day_of_Week"] = df["Date"].dt.day_name()
    df["Month"] = df["Date"].dt.month
    df["Is_Weekend"] = (df["Date"].dt.dayofweek >= 5).astype(int)
    df["Waste_Percentage"] = (df["Quantity_Wasted"] / df["Quantity_Purchased"] * 100).round(2)
    df["Consumption_Rate"] = (df["Quantity_Consumed"] / df["Quantity_Purchased"]).round(4)

    df = df.sort_values(["Date", "Food"]).reset_index(drop=True)
    summary["rows_kept"] = len(df)
    return df, summary


def clean_food_data(raw_data_path=RAW_DATA_PATH, cleaned_data_path=CLEANED_DATA_PATH):
    """Read the raw CSV, clean it and write the cleaned CSV."""
    df, summary = clean_records(pd.read_csv(raw_data_path))
    df.to_csv(cleaned_data_path, index=False, date_format="%Y-%m-%d")
    print("Cleaning complete")
    for key, value in summary.items():
        print(f"{key.replace('_', ' ').capitalize()}: {value}")
    return df


if __name__ == "__main__":
    clean_food_data()
