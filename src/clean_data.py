from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw_food_data.csv"
CLEANED_DATA_PATH = PROJECT_ROOT / "data" / "cleaned_food_data.csv"

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


def clean_food_data(raw_data_path=RAW_DATA_PATH, cleaned_data_path=CLEANED_DATA_PATH):
    """Clean and validate food purchase records for FDS analysis."""
    df = pd.read_csv(raw_data_path)
    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(f"Raw data is missing columns: {sorted(missing_columns)}")

    original_rows = len(df)
    df = df.drop_duplicates().copy()
    duplicate_rows_removed = original_rows - len(df)

    # Standardize text values and retain incomplete optional text as Unknown.
    for column in TEXT_COLUMNS:
        df[column] = df[column].fillna("Unknown").astype(str).str.strip()
        df.loc[df[column] == "", column] = "Unknown"

    # Convert dates and numeric fields. Invalid values become missing and are removed below.
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Estimated_Expiry_Date"] = pd.to_datetime(
        df["Estimated_Expiry_Date"], errors="coerce"
    )
    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    # A record without a date or a valid purchase quantity/cost cannot support analysis.
    required_values = [
        "Date",
        "Quantity_Purchased",
        "Quantity_Consumed",
        "Quantity_Wasted",
        "Quantity_Remaining",
        "Price",
        "Expiry_Days",
        "Estimated_Expiry_Date",
        "Is_Festival",
    ]
    df = df.dropna(subset=required_values).copy()

    # Keep only physically and financially valid purchase records.
    quantity_is_valid = (
        (df["Quantity_Purchased"] > 0)
        & (df["Quantity_Consumed"] >= 0)
        & (df["Quantity_Wasted"] >= 0)
        & (df["Quantity_Remaining"] >= 0)
        & (df["Quantity_Remaining"] <= df["Quantity_Purchased"])
    )
    price_and_expiry_are_valid = (
        (df["Price"] >= 0)
        & (df["Expiry_Days"] >= 0)
        & (df["Estimated_Expiry_Date"] >= df["Date"])
        & (df["Is_Festival"].isin([0, 1]))
    )

    # Allow a small difference because the raw quantities are rounded to two decimals.
    balance_difference = (
        df["Quantity_Purchased"]
        - df["Quantity_Consumed"]
        - df["Quantity_Wasted"]
        - df["Quantity_Remaining"]
    )
    balance_is_valid = balance_difference.abs() <= 0.011

    expected_expiry_date = df["Date"] + pd.to_timedelta(df["Expiry_Days"], unit="D")
    expiry_is_valid = df["Estimated_Expiry_Date"] == expected_expiry_date

    df = df[quantity_is_valid & price_and_expiry_are_valid & balance_is_valid & expiry_is_valid].copy()
    invalid_rows_removed = original_rows - duplicate_rows_removed - len(df)

    # Use one clear name for the remaining batch quantity in the analysis dataset.
    df = df.rename(columns={"Quantity_Remaining": "Remaining_Quantity"})
    df["Expiry_Days"] = df["Expiry_Days"].astype(int)
    df["Is_Festival"] = df["Is_Festival"].astype(int)

    # Features used in exploratory analysis, waste analysis, and seasonality analysis.
    df["Day_of_Week"] = df["Date"].dt.day_name()
    df["Month"] = df["Date"].dt.month
    df["Is_Weekend"] = (df["Date"].dt.dayofweek >= 5).astype(int)
    df["Waste_Percentage"] = (
        df["Quantity_Wasted"] / df["Quantity_Purchased"] * 100
    ).round(2)
    df["Consumption_Rate"] = (
        df["Quantity_Consumed"] / df["Quantity_Purchased"]
    ).round(4)

    df = df.sort_values(["Date", "Food"]).reset_index(drop=True)
    df.to_csv(cleaned_data_path, index=False, date_format="%Y-%m-%d")

    print("Cleaning complete!")
    print(f"Rows read: {original_rows}")
    print(f"Duplicate rows removed: {duplicate_rows_removed}")
    print(f"Invalid rows removed: {invalid_rows_removed}")
    print(f"Cleaned rows: {len(df)}")
    print(f"Cleaned columns: {len(df.columns)}")

    return df


if __name__ == "__main__":
    clean_food_data()
