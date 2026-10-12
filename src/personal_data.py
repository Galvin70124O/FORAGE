"""Persistent local storage for unauthenticated FORAGE personal records.

This module deliberately never reads or writes either development dataset.
It is the small storage boundary that can later be replaced by a user-scoped
Supabase repository without changing the personal dashboard.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pandas as pd

from data_quality import build_quality_report, clean_and_derive_features


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PERSONAL_DATA_PATH = PROJECT_ROOT / "data" / "my_food_data.csv"
PERSONAL_COLUMNS = [
    "Record_ID", "Date", "Food", "Category", "Quantity_Purchased",
    "Quantity_Consumed", "Quantity_Wasted", "Price", "Expiry_Days",
    "Storage_Type", "Remaining_Quantity", "Quantity_Unit", "Input_Method",
    "Source_Reference", "Estimated_Expiry_Date", "Is_Festival",
    "Day_of_Week", "Month", "Is_Weekend", "Waste_Percentage", "Consumption_Rate",
]
DEFAULTS = {
    "Category": "Uncategorized", "Quantity_Unit": "unit", "Storage_Type": "Unknown",
    "Input_Method": "Manual entry", "Source_Reference": "Personal data", "Is_Festival": 0,
}


def _empty_data() -> pd.DataFrame:
    return pd.DataFrame(columns=PERSONAL_COLUMNS)


def ensure_personal_store() -> Path:
    """Create the personal CSV with its explicit schema on first use."""
    PERSONAL_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not PERSONAL_DATA_PATH.exists():
        _empty_data().to_csv(PERSONAL_DATA_PATH, index=False)
    return PERSONAL_DATA_PATH


def _normalise(df: pd.DataFrame, *, source: str) -> pd.DataFrame:
    """Use the shared cleaning pipeline, then complete the personal schema."""
    if df.empty:
        return _empty_data()
    working = df.copy()
    for column, value in DEFAULTS.items():
        if column not in working:
            working[column] = value
        else:
            working[column] = working[column].fillna(value)
    if "Record_ID" not in working:
        working["Record_ID"] = [str(uuid4()) for _ in range(len(working))]
    else:
        missing_ids = working["Record_ID"].isna() | working["Record_ID"].astype(str).str.strip().eq("")
        working.loc[missing_ids, "Record_ID"] = [str(uuid4()) for _ in range(int(missing_ids.sum()))]
    if "Input_Method" not in working or working["Input_Method"].isna().all():
        working["Input_Method"] = source
    cleaned, _ = clean_and_derive_features(working)
    if "Estimated_Expiry_Date" not in cleaned and "Date" in cleaned:
        cleaned["Estimated_Expiry_Date"] = cleaned["Date"] + pd.to_timedelta(cleaned["Expiry_Days"].fillna(0), unit="D")
    for column in PERSONAL_COLUMNS:
        if column not in cleaned:
            cleaned[column] = pd.NA
    cleaned["Input_Method"] = cleaned["Input_Method"].fillna(source)
    cleaned["Source_Reference"] = cleaned["Source_Reference"].fillna("Personal data")
    return cleaned[PERSONAL_COLUMNS].sort_values(["Date", "Food", "Record_ID"]).reset_index(drop=True)


def load_personal_data() -> pd.DataFrame:
    ensure_personal_store()
    df = pd.read_csv(PERSONAL_DATA_PATH, parse_dates=["Date", "Estimated_Expiry_Date"])
    if df.empty:
        return _empty_data()
    return _normalise(df, source="Personal data")


def save_personal_data(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = _normalise(df, source="Personal data")
    ensure_personal_store()
    cleaned.to_csv(PERSONAL_DATA_PATH, index=False, date_format="%Y-%m-%d")
    return cleaned


def add_personal_record(record: dict) -> pd.DataFrame:
    record = dict(record)
    record["Record_ID"] = str(uuid4())
    record.setdefault("Input_Method", "Manual entry")
    record.setdefault("Source_Reference", "Personal data")
    existing = load_personal_data()
    return save_personal_data(pd.concat([existing, pd.DataFrame([record])], ignore_index=True))


def append_personal_records(df: pd.DataFrame) -> pd.DataFrame:
    """Append already schema-mapped/cleaned imported records only to My Data."""
    if df.empty:
        return load_personal_data()
    imported = df.copy()
    imported["Record_ID"] = [str(uuid4()) for _ in range(len(imported))]
    if "Input_Method" not in imported:
        imported["Input_Method"] = "CSV import"
    else:
        imported["Input_Method"] = imported["Input_Method"].fillna("CSV import")
    if "Source_Reference" not in imported:
        imported["Source_Reference"] = "Imported CSV"
    else:
        imported["Source_Reference"] = imported["Source_Reference"].fillna("Imported CSV")
    return save_personal_data(pd.concat([load_personal_data(), imported], ignore_index=True))


def personal_quality_report(df: pd.DataFrame) -> dict:
    """Expose the existing quality checks for the current personal store."""
    return build_quality_report(df, set(), []) if not df.empty else {
        "rows": 0, "missing_values": {}, "duplicate_rows": 0, "invalid_dates": 0,
        "invalid_numeric_values": {}, "negative_values": {}, "suspicious_outliers_iqr": {},
        "missing_required_standard_columns": [], "unmapped_source_columns": [],
    }
