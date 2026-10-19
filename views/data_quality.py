"""Data Quality: what was checked, what was removed and why, and what is flagged but kept."""

import pandas as pd
import streamlit as st

from data_quality import column_profile, iqr_outliers
from services.data import demo_cleaning_summary, quality_report, raw_demo
from ui.components import date, empty_state, fmt_num, formula, kpi_row, number, section, table, text
from views.common import begin
from waste import balance_check

CLEANING_STEPS = [
    ("rows_read", "Rows read from raw file", "–"),
    ("duplicates_removed", "Exact duplicate rows", "Removed"),
    ("missing_or_unparseable_removed", "Missing or unparseable date / number", "Removed, not imputed"),
    ("invalid_values_removed", "Impossible values (negative quantity or price, purchase of 0, flag not 0/1)", "Removed"),
    ("unbalanced_removed", "Purchased ≠ consumed + wasted + remaining (beyond ±0.011 rounding)", "Removed"),
    ("inconsistent_expiry_removed", "Expiry date ≠ purchase date + shelf-life days", "Removed"),
    ("rows_kept", "Rows kept for analysis", "–"),
]
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
        balance = balance_check(df)
        if source == "demo":
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
                steps = pd.DataFrame([{"Check": label, "Rows": summary[key], "Action": action}
                                      for key, label, action in CLEANING_STEPS])
                table(steps, {"Check": text("Check", "large"), "Rows": number("Rows", "%d"),
                              "Action": text("Action", "small")})
                st.caption("No values are filled in. Blank text fields become the label “Unknown”. "
                           "Duplicates, missing values and failures are all zero in this file because the demo "
                           "data is generated; the unit tests exercise every rule on deliberately messy input.")
            with right:
                section("Stock balance", "Every record must satisfy:")
                formula("purchased = consumed + wasted + remaining")
                st.write("")
                st.write(f"Largest difference found: {fmt_num(balance['max_abs_residual'], 3)} "
                         "(rounding to two decimals in the source).")
                st.caption("Waste is the recorded quantity wasted. It is not computed as purchased − consumed, "
                           "because that would count food still in stock as waste.")

        section("Columns", "Type, missing values and distinct values in the cleaned data")
        profile_table(df.drop(columns=["Record_ID"], errors="ignore"))
        section("Outliers (IQR rule)",
                "Values outside Q1 − 1.5×IQR to Q3 + 1.5×IQR. They are flagged for review and kept, "
                "because large purchases can be genuine.")
        outlier_table(df, HOUSEHOLD_NUMERIC)

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
