"""My Data: add, import, edit and delete personal food records."""

import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from dataset_loader import process_external_csv
from personal_data import (
    PERSONAL_DATA_PATH,
    add_personal_record,
    append_personal_records,
    load_personal_data,
    save_personal_data,
)
from services.data import set_source
from ui.components import fmt_date, kpi_row, number, page_header, section, source_label, table

EDITABLE = ["Record_ID", "Date", "Food", "Category", "Quantity_Unit", "Quantity_Purchased", "Quantity_Consumed",
            "Quantity_Wasted", "Remaining_Quantity", "Price", "Expiry_Days", "Storage_Type"]

page_header("My Data", "Your own food records. They are stored locally, used only when the data source is "
            "My Data, and never mixed with the demo or public datasets.")
personal = load_personal_data()
source_label("My Data", f"{len(personal):,} records · stored in data/{PERSONAL_DATA_PATH.name}")

records_tab, add_tab, import_tab = st.tabs(["Records", "Add a record", "Import CSV"])

with records_tab:
    if personal.empty:
        st.write("No records yet. Add one in the next tab, or import a CSV.")
    else:
        kpi_row([("Records", f"{len(personal):,}"), ("Foods", f"{personal['Food'].nunique()}"),
                 ("First date", fmt_date(personal["Date"].min())), ("Last date", fmt_date(personal["Date"].max()))])
        st.button("Analyse these records", on_click=set_source, args=("personal",),
                  help="Sets the data source to My Data on every page.")
        st.caption("Edit cells directly, add or delete rows, then save. Saved records go through the same cleaning "
                   "rules as imports.")
        edited = st.data_editor(
            personal[EDITABLE], hide_index=True, num_rows="dynamic", width="stretch", key="personal_editor",
            column_config={
                "Record_ID": None,
                "Date": st.column_config.DateColumn("Date", format="D MMM YYYY"),
                "Quantity_Unit": "Unit", "Quantity_Purchased": number("Purchased"),
                "Quantity_Consumed": number("Consumed"), "Quantity_Wasted": number("Wasted"),
                "Remaining_Quantity": number("Remaining"), "Price": number("Price"),
                "Expiry_Days": number("Shelf life (days)", "%d"), "Storage_Type": "Storage",
            })
        if st.button("Save changes", type="primary", key="save_personal"):
            try:
                save_personal_data(edited)
                st.success("Saved.")
                st.rerun()
            except Exception as error:  # surfaced to the user, nothing is written
                st.error(f"Could not save: {error}")

with add_tab:
    with st.form("add_record", clear_on_submit=True):
        first, second, third = st.columns(3)
        date = first.date_input("Date")
        food = second.text_input("Food", placeholder="Milk")
        category = third.text_input("Category", placeholder="Dairy")
        first, second, third, fourth = st.columns(4)
        purchased = first.number_input("Purchased", min_value=0.0, format="%.2f")
        consumed = second.number_input("Consumed", min_value=0.0, format="%.2f")
        wasted = third.number_input("Wasted", min_value=0.0, format="%.2f")
        remaining = fourth.number_input("Remaining", min_value=0.0, format="%.2f")
        first, second, third, fourth = st.columns(4)
        unit = first.selectbox("Unit", ["kg", "g", "L", "ml", "dozen", "loaf", "pack", "unit"])
        price = second.number_input("Price", min_value=0.0, format="%.2f")
        expiry_days = third.number_input("Shelf life (days)", min_value=0, step=1)
        storage = fourth.selectbox("Storage", ["Refrigerator", "Freezer", "Pantry", "Room temperature", "Other"])
        st.caption("Purchased must equal consumed + wasted + remaining (to within 0.01).")
        submitted = st.form_submit_button("Add record", type="primary")
    if submitted:
        if not food.strip() or purchased <= 0:
            st.error("Enter a food name and a purchased quantity above zero.")
        elif abs(purchased - consumed - wasted - remaining) > 0.011:
            st.error(f"Consumed + wasted + remaining is {consumed + wasted + remaining:.2f}, but purchased is "
                     f"{purchased:.2f}. Adjust the quantities so they balance.")
        else:
            add_personal_record({
                "Date": pd.Timestamp(date), "Food": food.strip(), "Category": category.strip() or "Uncategorized",
                "Quantity_Purchased": purchased, "Quantity_Consumed": consumed, "Quantity_Wasted": wasted,
                "Remaining_Quantity": remaining, "Price": price, "Expiry_Days": expiry_days,
                "Storage_Type": storage, "Quantity_Unit": unit,
                "Estimated_Expiry_Date": pd.Timestamp(date) + pd.Timedelta(days=expiry_days)})
            st.success(f"Added {food.strip()}.")

with import_tab:
    st.write("Upload a food CSV. Columns are matched to the FORAGE schema by name (for example, `qty_bought` "
             "maps to Purchased). The file itself is never changed.")
    uploaded = st.file_uploader("CSV file", type="csv")
    if uploaded is not None:
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as handle:
                handle.write(uploaded.getvalue())
                temporary_path = handle.name
            with st.spinner("Checking the file..."):
                result = process_external_csv(temporary_path)
        except Exception as error:
            st.error(f"The file could not be read: {error}")
            result = None
        finally:
            if temporary_path:
                Path(temporary_path).unlink(missing_ok=True)
        if result is not None:
            inspection, report, cleaning = result["inspection"], result["quality_report"], result["cleaning_summary"]
            standardised = result["standardised_data"]
            removed = cleaning["duplicates_removed"] + sum(v for k, v in cleaning.items() if k.startswith("rows_removed"))
            kpi_row([("Rows in file", f"{inspection['shape'][0]:,}"), ("Rows removed", f"{removed:,}"),
                     ("Rows ready", f"{len(standardised):,}"),
                     ("Missing values", f"{sum(report['missing_values'].values()):,}")])
            left, right = st.columns(2, gap="large")
            with left:
                section("Column matching")
                mapping = result["column_mapping"]
                table(pd.DataFrame({"FORAGE column": list(mapping), "Your column": list(mapping.values())}))
                if report["unmapped_source_columns"]:
                    st.caption("Not used: " + ", ".join(report["unmapped_source_columns"]))
            with right:
                section("Rows removed")
                table(pd.DataFrame({
                    "Reason": ["Exact duplicates", "No food name", "Invalid date", "Negative or zero quantity, invalid flag"],
                    "Rows": [cleaning["duplicates_removed"], cleaning["rows_removed_missing_food"],
                             cleaning["rows_removed_invalid_date"], cleaning["rows_removed_invalid_values"]]}),
                      {"Rows": number("Rows", "%d")})
                st.caption("Outliers are flagged on the Data Quality page and kept. Missing values are not filled in.")
            section("Preview", f"First {min(20, len(standardised))} of {len(standardised):,} cleaned rows")
            table(standardised.head(20))
            if report["missing_required_standard_columns"]:
                st.warning("The file needs at least a food name and a date column: missing "
                           + ", ".join(report["missing_required_standard_columns"]) + ".")
            elif standardised.empty:
                st.warning("No valid rows to import.")
            elif st.button(f"Import {len(standardised):,} rows into My Data", type="primary"):
                append_personal_records(standardised)
                st.success(f"Imported {len(standardised):,} rows.")
