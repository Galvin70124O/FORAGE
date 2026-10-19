"""Data Quality: what was checked, what was removed and why, and what is flagged but kept."""

import pandas as pd
import streamlit as st

from data_quality import column_profile, iqr_outliers
from services.data import (
    demo_cleaning_summary,
    messy_sample_cleaning,
    quality_report,
    raw_demo,
)
from ui.components import (
    date,
    empty_state,
    fmt_num,
    formula,
    kpi_row,
    methods,
    number,
    section,
    table,
    text,
)
from views.common import begin
from waste import balance_check

CLEANING_STEPS = [
    ("rows_read", "Rows read from the file", "–"),
    ("names_fixed", "Food or category name with odd case or spacing", "Fixed (tidied)"),
    ("duplicates_removed", "Exact duplicate row (after tidying names)", "Removed"),
    ("missing_or_unparseable_removed", "Missing or unreadable date or number", "Removed"),
    ("invalid_values_removed", "Impossible value (negative, zero purchase, bad flag)", "Removed"),
    ("expiry_before_purchase_removed", "Expiry date before the purchase date", "Removed"),
    ("unbalanced_removed", "Stock does not balance (beyond ±0.011)", "Removed"),
    ("inconsistent_expiry_removed", "Expiry ≠ purchase date + shelf life", "Removed"),
    ("outliers_flagged", "IQR outlier (quantities or price)", "Flagged, kept"),
    ("rows_kept", "Rows kept for analysis", "–"),
]
STEP_COLUMNS = {"Check": text("Check", "large"), "Rows": number("Rows", "%d"), "Action": text("Action", "small")}


def steps_table(summary: dict) -> pd.DataFrame:
    return pd.DataFrame([{"Check": label, "Rows": summary.get(key, 0), "Action": action}
                         for key, label, action in CLEANING_STEPS])
HOUSEHOLD_NUMERIC = ["Quantity_Purchased", "Quantity_Consumed", "Quantity_Wasted", "Remaining_Quantity",
                     "Price", "Expiry_Days"]


def profile_table(df: pd.DataFrame) -> None:
    table(column_profile(df), {
        "Missing": number("Missing", "%d"),
        "Missing (%)": number("Missing (%)", "%.1f"),
        "Distinct": number("Distinct values", "%d"),
    }, max_rows=None)


def outlier_table(df: pd.DataFrame, columns: list[str]) -> None:
    table(iqr_outliers(df, columns), {
        "Lower bound": number("Lower bound"), "Upper bound": number("Upper bound"),
        "Outliers": number("Outliers", "%d"), "Outliers (%)": number("Outliers (%)", "%.1f"),
    })


source, df = begin("Data Quality",
                   "What was checked before analysis, which rows were removed and why, and what was flagged but kept.",
                   feature=None)
methods(['Every row is checked against the rules in a fixed order; a removed row is counted under the first rule it fails. Nothing is filled in or guessed.',
         'Outliers use the IQR rule: values below Q1 − 1.5×IQR or above Q3 + 1.5×IQR are flagged for review and kept, because a big purchase can be genuine.'])

if source == "personal":
    from services.personal import personal_data
    data = personal_data()
    if data is None:
        empty_state("Sign in to see your data quality", "Your purchases and pantry checks are private to you.")
    else:
        buys, checks = data
        frame = df if df is not None else pd.DataFrame()
        impossible = int(frame["Impossible"].sum()) if not frame.empty else 0
        kpi_row([("Purchases", f"{len(buys):,}"), ("Pantry checks", f"{len(checks):,}"),
                 ("Completed periods", f"{len(frame):,}"),
                 ("Impossible periods", f"{impossible:,}", "More left at a check than could possibly be there."),
                 ("Foods without a price", f"{int(buys.groupby('food')['total_price'].apply(lambda s: s.isna().all()).sum()) if not buys.empty else 0}")])
        section("How consumption is derived", "You record purchases and pantry checks; consumption is calculated.")
        formula("consumed = remaining at previous check + bought since - thrown away - remaining now")
        st.caption("A period runs from one pantry check to the next (a food's first period starts at its first "
                   "purchase, assuming none was on hand before). Purchases on a check day count towards that "
                   "check. A negative result is impossible, so it is shown as 0 and flagged below, never "
                   "silently corrected.")
        if frame.empty:
            st.write("No completed periods yet: log a purchase, then do a pantry check.")
        else:
            shown = frame[["Food", "Period_Start", "Date", "Days", "Opening_Stock", "Quantity_Purchased",
                           "Quantity_Wasted", "Remaining_Quantity", "Quantity_Consumed", "Impossible"]]
            table(shown.sort_values(["Impossible", "Date"], ascending=[False, False]), {
                "Period_Start": date("From"), "Date": date("To (check)"), "Days": number("Days", "%d"),
                "Opening_Stock": number("Left at start"), "Quantity_Purchased": number("Bought"),
                "Quantity_Wasted": number("Thrown away"), "Remaining_Quantity": number("Left now"),
                "Quantity_Consumed": number("Consumed (derived)"),
                "Impossible": st.column_config.CheckboxColumn("Impossible")}, max_rows=10)
            if impossible:
                st.warning(f"{impossible} period(s) have more left at the check than was available. Usually a "
                           "purchase is missing or a check was entered for the wrong food; fix it on My data.")
            section("Outliers (IQR rule)", "Flagged for review and kept.")
            outlier_table(frame, ["Quantity_Purchased", "Quantity_Consumed", "Quantity_Wasted", "Daily_Consumption"])
elif df is not None:
    if source == "demo":
        dataset_tab, pipeline_tab = st.tabs(["Demo dataset", "Try the cleaning pipeline"])
        with dataset_tab:
            balance = balance_check(df)
            summary = demo_cleaning_summary()
            removed = summary["rows_read"] - summary["rows_kept"]
            kpi_row([("Rows read", f"{summary['rows_read']:,}"), ("Rows removed", f"{removed:,}"),
                     ("Rows kept", f"{summary['rows_kept']:,}"),
                     ("Missing values in raw file", f"{int(raw_demo().isna().sum().sum()):,}"),
                     ("Balance check", "All pass" if not balance["failing"] else f"{balance['failing']:,} fail",
                      "purchased = consumed + wasted + remaining, within ±0.011.")])
            left, right = st.columns([1.7, 1], gap="large")
            with left:
                section("Cleaning steps", "Each removed row is counted once, under the first rule it fails.")
                table(steps_table(summary), STEP_COLUMNS, max_rows=None)
                st.caption("No values are filled in: rows with missing values are removed. Blank text fields become the label “Unknown”. The demo file "
                           "is generated, so it has no problems to remove; the next tab runs the same pipeline on a "
                           "deliberately messy sample.")
            with right:
                section("Stock balance", "Every record must satisfy:")
                formula("purchased = consumed + wasted + remaining")
                st.write("")
                st.write(f"Largest difference found: {fmt_num(balance['max_abs_residual'], 3)} "
                         "(rounding to two decimals in the source).")
                st.caption("Waste is the recorded quantity wasted. It is not computed as purchased − consumed, "
                           "because that would count food still in stock as waste.")
            section("Columns", "Type, missing values and distinct values in the cleaned data")
            profile_table(df)
            section("Outliers (IQR rule)",
                    "Values outside Q1 − 1.5×IQR to Q3 + 1.5×IQR. They are flagged for review and kept, "
                    "because large purchases can be genuine.")
            outlier_table(df, HOUSEHOLD_NUMERIC)

        with pipeline_tab:
            messy, cleaned, summary, audit = messy_sample_cleaning()
            st.write(f"`data/samples/messy_food_data.csv` has {len(messy)} rows with deliberate problems: duplicates, "
                     "inconsistent case and spacing in food names, missing values, bad dates, negative quantities, "
                     "text in numeric columns, expiry dates before the purchase date and a few huge purchases. "
                     "It is generated by `scripts/make_messy_sample.py` (seeded, so it is the same every time).")
            kpi_row([("Rows in", f"{summary['rows_read']:,}"), ("Fixed", f"{summary['names_fixed']:,}"),
                     ("Removed", f"{summary['rows_read'] - summary['rows_kept']:,}"),
                     ("Flagged and kept", f"{summary['outliers_flagged']:,}"), ("Rows out", f"{summary['rows_kept']:,}")])
            section("Before and after, per rule", "Rules run in this order; a removed row is counted once")
            table(steps_table(summary), STEP_COLUMNS, max_rows=None)
            section("Example rows", "Row = line number in the CSV file")
            for action in ("Fixed", "Removed", "Flagged (kept)"):
                examples = audit[audit["Action"] == action].groupby("Rule").head(2)
                st.markdown(f"**{action}** ({(audit['Action'] == action).sum()} rows)")
                table(examples[["Row", "Food", "Rule", "Detail"]], {
                    "Row": number("Row", "%d"), "Food": "Food as written", "Rule": text("Rule", "medium"),
                    "Detail": text("What was wrong", "large")}, max_rows=10)
            st.download_button("Download the messy sample", messy.to_csv(index=False).encode("utf-8"),
                               "messy_food_data.csv", "text/csv")

    else:
        report = quality_report(source) or {}
        numeric = (["Quantity_Sold", "Price"] if source == "m5"
                   else ["Order_Hour", "Days_Since_Prior_Order", "Add_To_Cart_Order", "Order_Number"])
        key = ["Date", "Product_ID", "Store_ID"] if source == "m5" else ["Order_ID", "Product_ID"]
        kpi_row([("Rows", f"{len(df):,}"), ("Columns", f"{len(df.columns)}"),
                 ("Missing values", f"{int(df.isna().sum().sum()):,}"),
                 ("Duplicate keys", f"{int(df.duplicated(subset=key).sum()):,}", f"Rows sharing {' + '.join(key)}.")])
        selection = report.get("selection", {})
        if selection:
            st.caption("How the extract was selected: " + selection.get("reason", ""))
        left, right = st.columns([1.3, 1], gap="large")
        with left:
            section("Columns")
            profile_table(df)
        with right:
            section("Extraction checks", "Recorded when the extract was built from the raw files")
            checks = {k: v for k, v in report.items() if isinstance(v, (int, float)) and k != "rows"}
            table(pd.DataFrame({"Check": [k.replace("_", " ").capitalize() for k in checks], "Count": list(checks.values())}),
                  {"Count": number("Count", "%d")})
            if source == "m5":
                st.caption("Event_Name and Event_Type are blank on days without a calendar event; that is expected, "
                           "not missing data.")
            else:
                st.caption("Days_Since_Prior_Order is blank for each customer's first order; that is expected, "
                           "not missing data.")
        section("Outliers (IQR rule)", "Flagged for review and kept.")
        outlier_table(df, numeric)
