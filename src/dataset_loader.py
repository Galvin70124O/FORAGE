"""Entry point for inspecting, mapping, and standardising external food CSVs.

Example:
    python src/dataset_loader.py path/to/external_food.csv --output data/standardised_external.csv
"""

import argparse
from pathlib import Path

import pandas as pd

from data_quality import build_quality_report, clean_and_derive_features, print_quality_report
from schema_mapper import MINIMUM_REQUIRED_COLUMNS, standardise_columns


def load_external_csv(csv_path):
    """Load a CSV without changing the source file."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"External CSV not found: {path}")
    return pd.read_csv(path)


def inspect_dataset(df):
    """Return a lightweight first-look inspection of an external dataset."""
    useful_unique_values = {}
    for column in df.columns:
        unique_count = df[column].nunique(dropna=True)
        if unique_count <= 10:
            useful_unique_values[column] = df[column].dropna().unique().tolist()
    return {
        "shape": df.shape,
        "columns": list(df.columns),
        "data_types": {column: str(dtype) for column, dtype in df.dtypes.items()},
        "missing_values": {column: int(value) for column, value in df.isna().sum().items()},
        "duplicate_rows": int(df.duplicated().sum()),
        "useful_unique_values": useful_unique_values,
    }


def process_external_csv(csv_path, output_path=None):
    """Inspect, map, report on, and safely standardise one external CSV.

    A missing required field is reported but does not cause invented values or a
    crash. The caller can decide whether the resulting partial dataset suits its
    intended analysis.
    """
    raw_df = load_external_csv(csv_path)
    inspection = inspect_dataset(raw_df)
    mapped_df, mapping, unmapped_columns = standardise_columns(raw_df)
    missing_required = MINIMUM_REQUIRED_COLUMNS - set(mapped_df.columns)
    report = build_quality_report(mapped_df, missing_required, unmapped_columns)
    cleaned_df, cleaning_summary = clean_and_derive_features(mapped_df)

    if output_path is not None:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cleaned_df.to_csv(output_path, index=False, date_format="%Y-%m-%d")

    return {
        "inspection": inspection,
        "column_mapping": mapping,
        "quality_report": report,
        "cleaning_summary": cleaning_summary,
        "standardised_data": cleaned_df,
    }


def main():
    parser = argparse.ArgumentParser(description="Standardise an external food-related CSV.")
    parser.add_argument("csv_path", help="Path to the external CSV file")
    parser.add_argument("--output", help="Optional path for the standardised CSV")
    args = parser.parse_args()

    result = process_external_csv(args.csv_path, args.output)
    print("EXTERNAL DATASET INSPECTION")
    print(f"Shape: {result['inspection']['shape']}")
    print("Columns:", result["inspection"]["columns"])
    print("Data types:", result["inspection"]["data_types"])
    print("Column mapping (standard <- source):", result["column_mapping"])
    print_quality_report(result["quality_report"])
    print("Cleaning summary:", result["cleaning_summary"])
    print(f"Standardised output: {result['standardised_data'].shape}")
    if args.output:
        print(f"Saved standardised CSV to: {args.output}")


if __name__ == "__main__":
    main()
