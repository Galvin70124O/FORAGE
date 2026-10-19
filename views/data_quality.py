"""Data-quality reports and generic CSV import."""

from pathlib import Path
import tempfile
import json

import pandas as pd
import streamlit as st


from dataset_loader import process_external_csv
from personal_data import (
    append_personal_records,
)

from services.data import INSTACART_QUALITY_PATH, M5_QUALITY_PATH
from ui.components import metric_row, page_header, section_heading


def dataset_quality_page():
    page_header("Data ingestion", "Dataset quality", "Inspect a real processed extract or an uploaded food-related CSV. Source files are never modified.")
    st.markdown("""<div class="workflow">
    <div class="workflow-step"><b>01</b>Upload</div><div class="workflow-step"><b>02</b>Inspect</div>
    <div class="workflow-step"><b>03</b>Quality check</div><div class="workflow-step"><b>04</b>Schema mapping</div>
    <div class="workflow-step"><b>05</b>Preview</div><div class="workflow-step"><b>06</b>Import to My Data</div></div>""", unsafe_allow_html=True)
    source = st.radio("Quality report source", ["M5 Forecasting extract", "Instacart extract", "Upload generic food CSV"], horizontal=True)
    if source != "Upload generic food CSV":
        report_path = M5_QUALITY_PATH if source.startswith("M5") else INSTACART_QUALITY_PATH
        if not report_path.exists():
            st.warning("The processed-data quality report is unavailable. Run `python src/real_data_processor.py` to rebuild it from the raw public dataset.")
            return
        report = json.loads(report_path.read_text(encoding="utf-8"))
        st.caption("This report is produced during bounded, dataset-specific preprocessing. It describes the processed extract and join checks without loading large raw files into the interface.")
        metric_row([("Rows", f"{report.get('rows', 0):,}"), ("Columns", str(len(report.get("columns", [])))), ("Duplicate relationship keys", str(report.get("duplicate_keys", 0))), ("Invalid dates", str(report.get("invalid_dates", "Not applicable")))])
        left, right = st.columns(2)
        with left:
            section_heading("Detected schema")
            st.dataframe(pd.DataFrame({"Column": report.get("columns", [])}), width="stretch", hide_index=True)
        with right:
            section_heading("Quality and join checks")
            checks = {key: value for key, value in report.items() if key not in {"columns", "missing_values", "selection"}}
            st.json(checks)
        with st.expander("Missing values and extraction selection"):
            st.json({"missing_values": report.get("missing_values", {}), "selection": report.get("selection", {})})
        return

    st.markdown("<div class='upload-well'>", unsafe_allow_html=True)
    section_heading("Import a CSV", "Drag and drop a food-related CSV. The original file is never changed.")
    with st.container():
        uploaded_file = st.file_uploader("Upload external food CSV", type="csv", help="The original file is not changed.")
        st.caption("The existing alias mapping and data-quality pipeline are used. Missing fields are reported; no values are invented.")
    st.markdown("</div>", unsafe_allow_html=True)
    if uploaded_file is None:
        st.info("Upload a CSV to inspect detected columns, mappings, quality checks, and the processed standardized result.")
        return
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as temporary_file:
            temporary_file.write(uploaded_file.getvalue())
            temporary_path = temporary_file.name
        result = process_external_csv(temporary_path)
    except Exception as error:
        st.error(f"The uploaded CSV could not be processed: {error}")
        return
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)

    inspection, report, cleaning_summary = result["inspection"], result["quality_report"], result["cleaning_summary"]
    metric_row([("Rows", f"{inspection['shape'][0]:,}"), ("Columns", f"{inspection['shape'][1]}"), ("Duplicate rows", f"{inspection['duplicate_rows']}"), ("Missing values", f"{sum(report['missing_values'].values())}")])
    first, second = st.columns(2)
    with first:
        with st.container(border=True):
            st.subheader("Detected columns and missing values")
            st.dataframe(pd.DataFrame({"Column": inspection["data_types"].keys(), "Data type": inspection["data_types"].values(), "Missing values": inspection["missing_values"].values()}), width="stretch", hide_index=True)
    with second:
        with st.container(border=True):
            st.subheader("Schema mapping")
            mapping = result["column_mapping"]
            if mapping:
                st.dataframe(pd.DataFrame({"FDS column": mapping.keys(), "Uploaded column": mapping.values()}), width="stretch", hide_index=True)
            else:
                st.warning("No supported columns were detected in this file.")
            if report["missing_required_standard_columns"]:
                st.warning("Missing required fields: " + ", ".join(report["missing_required_standard_columns"]))
            if report["unmapped_source_columns"]:
                st.info("Unmapped uploaded columns: " + ", ".join(report["unmapped_source_columns"]))
    with st.container(border=True):
        st.subheader("Quality checks and cleaning actions")
        removed_rows = sum(value for key, value in cleaning_summary.items() if key.startswith("rows_removed")) + cleaning_summary["duplicates_removed"]
        metric_row([("Invalid dates", f"{report['invalid_dates']}"), ("Invalid numeric values", f"{sum(report['invalid_numeric_values'].values())}"), ("Negative values", f"{sum(report['negative_values'].values())}"), ("Rows removed", f"{removed_rows}")])
        outliers = pd.DataFrame.from_dict(report["suspicious_outliers_iqr"], orient="index").rename_axis("Column").reset_index()
        if not outliers.empty:
            st.caption("IQR outliers are flagged for review and are not automatically removed.")
            st.dataframe(outliers, width="stretch", hide_index=True)
        st.caption("Derived columns: " + (", ".join(cleaning_summary["derived_columns"]) or "None"))
        if inspection["useful_unique_values"]:
            with st.expander("Useful unique values"):
                st.json(inspection["useful_unique_values"])
    with st.container(border=True):
        standardized = result["standardised_data"]
        st.subheader("Processed standardized dataset")
        st.caption(f"Showing the first {min(100, len(standardized))} processed rows.")
        st.dataframe(standardized.head(100), width="stretch", hide_index=True)
        st.download_button("Download processed dataset", standardized.to_csv(index=False).encode("utf-8"), file_name="standardized_external_food_data.csv", mime="text/csv")
        if report["missing_required_standard_columns"]:
            st.warning("Import to My Data is unavailable until Food and Date are supplied.")
        elif standardized.empty:
            st.warning("There are no valid records to import.")
        elif st.button("Add processed records to My Data", key="import_to_personal"):
            append_personal_records(standardized)
            st.success(f"Added {len(standardized)} record(s) to your personal food data. The FORAGE Dataset was not changed.")
