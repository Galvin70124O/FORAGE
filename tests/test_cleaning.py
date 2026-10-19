import pandas as pd

from clean_data import RAW_DATA_PATH, clean_records
from conftest import make_raw_row
from data_quality import build_quality_report, clean_and_derive_features


def test_duplicates_are_removed_and_counted():
    raw = pd.DataFrame([make_raw_row(), make_raw_row(), make_raw_row(Food="Bread")])
    cleaned, summary = clean_records(raw)
    assert summary["duplicates_removed"] == 1
    assert len(cleaned) == 2


def test_missing_required_values_are_dropped_not_imputed():
    raw = pd.DataFrame([make_raw_row(), make_raw_row(Food="Curd", Price=None)])
    cleaned, summary = clean_records(raw)
    assert summary["missing_or_unparseable_removed"] == 1
    assert list(cleaned["Food"]) == ["Milk"]
    assert cleaned["Price"].notna().all()


def test_unparseable_types_are_coerced_then_removed():
    raw = pd.DataFrame([make_raw_row(), make_raw_row(Food="Egg", Quantity_Purchased="abc"),
                        make_raw_row(Food="Tea", Date="not a date")])
    cleaned, summary = clean_records(raw)
    assert summary["missing_or_unparseable_removed"] == 2
    assert pd.api.types.is_datetime64_any_dtype(cleaned["Date"])
    assert pd.api.types.is_float_dtype(cleaned["Quantity_Purchased"])


def test_invalid_and_unbalanced_rows_are_removed_with_reason():
    raw = pd.DataFrame([
        make_raw_row(),
        make_raw_row(Food="Neg", Quantity_Wasted=-0.1, Quantity_Remaining=0.9),
        make_raw_row(Food="Unbalanced", Quantity_Remaining=0.9),  # 1.2+0.3+0.9 != 2.0
        make_raw_row(Food="BadExpiry", Estimated_Expiry_Date="2025-03-20"),
    ])
    cleaned, summary = clean_records(raw)
    assert summary["invalid_values_removed"] == 1
    assert summary["unbalanced_removed"] == 1
    assert summary["inconsistent_expiry_removed"] == 1
    assert list(cleaned["Food"]) == ["Milk"]
    removed = sum(v for k, v in summary.items() if k.endswith("_removed"))
    assert summary["rows_read"] - removed == summary["rows_kept"]


def test_rounding_within_tolerance_is_accepted():
    raw = pd.DataFrame([make_raw_row(Quantity_Remaining=0.51)])  # off by 0.01 from rounding
    cleaned, _ = clean_records(raw)
    assert len(cleaned) == 1


def test_outliers_are_kept_and_flagged():
    rows = [make_raw_row(Food=f"F{i}") for i in range(10)]
    rows.append(make_raw_row(Food="Bulk", Quantity_Purchased=200.0, Quantity_Consumed=199.2))
    cleaned, _ = clean_records(pd.DataFrame(rows))
    assert "Bulk" in set(cleaned["Food"])
    report = build_quality_report(cleaned.rename(columns={}), set(), [])
    assert report["suspicious_outliers_iqr"]["Quantity_Purchased"]["count"] == 1


def test_blank_text_becomes_unknown_label():
    cleaned, _ = clean_records(pd.DataFrame([make_raw_row(Storage_Type="  ")]))
    assert cleaned.loc[0, "Storage_Type"] == "Unknown"


def test_derived_columns_use_correct_formulas():
    cleaned, _ = clean_records(pd.DataFrame([make_raw_row()]))
    row = cleaned.iloc[0]
    assert row["Waste_Percentage"] == 15.0  # 0.3 / 2.0
    assert row["Consumption_Rate"] == 0.6
    assert row["Day_of_Week"] == "Saturday" and row["Is_Weekend"] == 1


def test_demo_raw_file_cleans_without_loss():
    cleaned, summary = clean_records(pd.read_csv(RAW_DATA_PATH))
    assert summary["rows_read"] == 7300
    assert summary["rows_kept"] == 7300


def test_import_pipeline_drops_invalid_rows_but_keeps_outliers():
    df = pd.DataFrame({
        "Date": ["2025-01-01", "bad", "2025-01-03", "2025-01-04"],
        "Food": ["Milk", "Milk", None, "Milk"],
        "Quantity_Purchased": [1, 1, 1, 500],
        "Quantity_Wasted": [0, 0, 0, 0],
    })
    cleaned, summary = clean_and_derive_features(df)
    assert summary["rows_removed_invalid_date"] == 1
    assert summary["rows_removed_missing_food"] == 1
    assert 500 in set(cleaned["Quantity_Purchased"])


def test_days_without_a_purchase_are_kept_and_ratios_are_undefined():
    cleaned, summary = clean_and_derive_features(pd.DataFrame({
        "Date": ["2026-03-01", "2026-03-02"], "Food": ["Milk", "Milk"],
        "Quantity_Purchased": [2, 0], "Quantity_Consumed": [1, 1], "Quantity_Wasted": [0, 0]}))
    assert len(cleaned) == 2 and summary["rows_removed_invalid_values"] == 0
    assert pd.isna(cleaned.loc[1, "Waste_Percentage"])
    assert "Remaining_Quantity" not in cleaned  # never invented


def test_name_variants_are_unified_to_the_most_common_spelling():
    from data_quality import normalise_names
    names, changed = normalise_names(pd.Series(["Milk", " milk", "MILK ", "Milk", "Brown  Bread"]))
    assert names.tolist() == ["Milk", "Milk", "Milk", "Milk", "Brown Bread"]
    assert changed.tolist() == [False, True, True, False, True]


def test_messy_sample_problems_are_each_caught_by_the_right_rule():
    from pathlib import Path
    sample = Path(__file__).resolve().parent.parent / "data" / "samples" / "messy_food_data.csv"
    cleaned, summary, audit = clean_records(pd.read_csv(sample), audit=True)
    assert summary["rows_read"] == 208
    assert summary["names_fixed"] == 15                      # 12 variants + 3 that become duplicates
    assert summary["duplicates_removed"] == 13                # 10 exact + 3 after tidying names
    assert summary["missing_or_unparseable_removed"] == 18    # 8 missing + 5 bad dates + 5 text in numbers
    assert summary["invalid_values_removed"] == 5             # negative quantities / price
    assert summary["expiry_before_purchase_removed"] == 4
    assert summary["unbalanced_removed"] == 0 and summary["inconsistent_expiry_removed"] == 0
    removed = sum(v for k, v in summary.items() if k.endswith("_removed"))
    assert summary["rows_read"] - removed == summary["rows_kept"] == len(cleaned) == 168
    # outliers are flagged, never removed: the six huge purchases are still in the output
    flagged = audit[audit["Action"] == "Flagged (kept)"]
    assert summary["outliers_flagged"] == len(flagged) >= 6
    big = cleaned["Quantity_Purchased"] > 4 * cleaned["Quantity_Purchased"].median()
    assert big.sum() >= 6  # the injected huge purchases survive cleaning
    assert set(audit["Action"]) == {"Fixed", "Removed", "Flagged (kept)"}
    assert cleaned["Food"].str.strip().eq(cleaned["Food"]).all() and not cleaned["Food"].str.isupper().any()
