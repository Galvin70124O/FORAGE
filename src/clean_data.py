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


OUTLIER_COLUMNS = ["Quantity_Purchased", "Quantity_Consumed", "Quantity_Wasted", "Price"]


def clean_records(df, *, audit=False):
    """Clean and validate raw food purchase records.

    Returns (cleaned, summary), or (cleaned, summary, audit_log) with
    audit=True. Nothing is imputed: a row missing a required value, or failing
    a validity rule, is removed and counted under the first rule it fails.
    Food and category names are tidied (spacing, and case variants unified to
    the most common spelling) before duplicates are looked for, so " MILK" and
    "Milk" rows can be recognised as duplicates. Blank text fields become the
    label "Unknown". IQR outliers are flagged in the audit log and kept.
    """
    from data_quality import normalise_names

    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(f"Raw data is missing columns: {sorted(missing_columns)}")

    original = df.reset_index(drop=True)
    df = original.copy()
    log = []

    def record(mask, action, rule, detail=None):
        for index in df.index[mask]:
            log.append({"Row": int(index) + 2, "Food": original.at[index, "Food"], "Action": action, "Rule": rule,
                        "Detail": detail(index) if callable(detail) else detail})

    summary = {"rows_read": len(df)}
    for column in TEXT_COLUMNS:
        df[column] = df[column].fillna("Unknown").astype(str).str.strip()
        df.loc[df[column] == "", column] = "Unknown"
    fixed = pd.Series(False, index=df.index)
    for column in ("Food", "Category"):
        df[column] = normalise_names(df[column])[0].astype(str)
        fixed |= original[column].notna() & (original[column].astype(str) != df[column])
    summary["names_fixed"] = int(fixed.sum())
    record(fixed, "Fixed", "Name case or spacing", lambda i: f"{original.at[i, 'Food']!r} -> {df.at[i, 'Food']!r}")

    duplicated = df.duplicated()
    summary["duplicates_removed"] = int(duplicated.sum())
    first_seen = df.drop_duplicates().reset_index().set_index(list(df.columns))["index"]
    record(duplicated, "Removed", "Exact duplicate",
           lambda i: f"same as row {int(first_seen.loc[tuple(df.loc[i])]) + 2}")
    df = df[~duplicated].copy()

    # Invalid dates/numbers become missing here and are removed below.
    raw_dates = df[["Date", "Estimated_Expiry_Date"]].copy()
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce", format="mixed")
    df["Estimated_Expiry_Date"] = pd.to_datetime(df["Estimated_Expiry_Date"], errors="coerce", format="mixed")
    raw_numbers = df[NUMERIC_COLUMNS].copy()
    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    required_values = [
        "Date", "Quantity_Purchased", "Quantity_Consumed", "Quantity_Wasted",
        "Quantity_Remaining", "Price", "Expiry_Days", "Estimated_Expiry_Date", "Is_Festival",
    ]

    def missing_detail(index):
        parts = []
        for column in required_values:
            if pd.isna(df.at[index, column]):
                raw = raw_dates.at[index, column] if column in raw_dates else raw_numbers.at[index, column]
                parts.append(f"{column} {'missing' if pd.isna(raw) or str(raw).strip() == '' else repr(raw)}")
        return ", ".join(parts)

    has_missing = df[required_values].isna().any(axis=1)
    summary["missing_or_unparseable_removed"] = int(has_missing.sum())
    record(has_missing, "Removed", "Missing or unreadable value", missing_detail)
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
    checks = {"Quantity_Purchased": df["Quantity_Purchased"] > 0, "Quantity_Consumed": df["Quantity_Consumed"] >= 0,
              "Quantity_Wasted": df["Quantity_Wasted"] >= 0, "Quantity_Remaining": df["Quantity_Remaining"] >= 0,
              "Price": df["Price"] >= 0, "Expiry_Days": df["Expiry_Days"] >= 0, "Is_Festival": df["Is_Festival"].isin([0, 1])}
    record(~quantity_is_valid, "Removed", "Impossible value (negative, zero purchase, bad flag)",
           lambda i: ", ".join(f"{c} {df.at[i, c]:g}" for c, ok in checks.items() if not ok.at[i])
           or "remaining is more than purchased")
    df = df[quantity_is_valid].copy()

    before_purchase = df["Estimated_Expiry_Date"] < df["Date"]
    summary["expiry_before_purchase_removed"] = int(before_purchase.sum())
    record(before_purchase, "Removed", "Expiry date before purchase date",
           lambda i: f"bought {df.at[i, 'Date']:%Y-%m-%d}, expiry {df.at[i, 'Estimated_Expiry_Date']:%Y-%m-%d}")
    df = df[~before_purchase].copy()

    # purchased = consumed + wasted + remaining, allowing for 2-dp rounding.
    balance_difference = (
        df["Quantity_Purchased"] - df["Quantity_Consumed"]
        - df["Quantity_Wasted"] - df["Quantity_Remaining"]
    )
    balance_is_valid = balance_difference.abs() <= BALANCE_TOLERANCE
    summary["unbalanced_removed"] = int((~balance_is_valid).sum())
    record(~balance_is_valid, "Removed", "Quantities do not balance",
           lambda i: f"off by {balance_difference.at[i]:+.2f}")
    df = df[balance_is_valid].copy()

    expected_expiry_date = df["Date"] + pd.to_timedelta(df["Expiry_Days"], unit="D")
    expiry_is_valid = df["Estimated_Expiry_Date"] == expected_expiry_date
    summary["inconsistent_expiry_removed"] = int((~expiry_is_valid).sum())
    record(~expiry_is_valid, "Removed", "Expiry date does not match shelf life")
    df = df[expiry_is_valid].copy()

    flagged = pd.Series(False, index=df.index)
    reasons = pd.Series("", index=df.index)
    for column in OUTLIER_COLUMNS:
        q1, q3 = df[column].quantile([0.25, 0.75])
        low, high = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
        outside = (df[column] < low) | (df[column] > high)
        flagged |= outside
        reasons.loc[outside] = (reasons.loc[outside] + f"{column} " + df.loc[outside, column].round(2).astype(str)
                                + f" outside [{low:.2f}, {high:.2f}]; ")
    summary["outliers_flagged"] = int(flagged.sum())
    record(flagged, "Flagged (kept)", "IQR outlier", lambda i: reasons.at[i].strip("; "))

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
    if audit:
        return df, summary, pd.DataFrame(log, columns=["Row", "Food", "Action", "Rule", "Detail"])
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
