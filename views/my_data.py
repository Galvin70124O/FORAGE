"""My data: edit or delete purchases, pantry checks and foods; export and import CSVs (in memory)."""

import io
from pathlib import Path

import pandas as pd
import streamlit as st

from pantry import read_import
from services.data import set_source
from services.personal import queue_toast, require_user, toast_pending
from ui.components import kpi_row, number, page_header, section, table

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "data" / "templates"
TEMPLATES = {"purchases": TEMPLATE_DIR / "purchases_template.csv",
             "pantry checks": TEMPLATE_DIR / "pantry_checks_template.csv"}

page_header("My data", pill="My data", purpose="Everything you have logged. Edit or delete entries, and export or import CSV files.")
db, uid = require_user()
toast_pending()
buys, checks, foods = db.purchases(uid), db.checks(uid), db.foods(uid)

kpi_row([("Purchases", f"{len(buys):,}"), ("Pantry checks", f"{len(checks):,}"), ("Foods", f"{len(foods):,}")])
st.button("Analyse my data in Insights", on_click=set_source, args=("personal",),
          help="Sets the Insights data source to My data.")


@st.dialog("Delete entries")
def confirm_delete(kind: str, ids: list[int]) -> None:
    st.write(f"Delete {len(ids)} {kind}? This cannot be undone.")
    with st.container(horizontal=True):
        if st.button("Delete", type="primary"):
            for entry in ids:
                (db.delete_purchase if kind == "purchases" else db.delete_check)(uid, int(entry))
            queue_toast(f"Deleted {len(ids)} {kind}.")
            st.rerun()
        if st.button("Cancel"):
            st.rerun()


def editable_table(frame: pd.DataFrame, kind: str, editable: list[str], config: dict) -> None:
    if frame.empty:
        st.write(f"No {kind} yet.")
        return
    view = frame.sort_values(["date", "id"], ascending=False).reset_index(drop=True)
    view.insert(0, "Select", False)
    disabled = [c for c in view.columns if c not in editable + ["Select"]]
    edited = st.data_editor(view, hide_index=True, width="stretch", num_rows="fixed", key=f"edit_{kind}",
                            disabled=disabled, column_config={"id": None, "Select": st.column_config.CheckboxColumn(
                                "Select", width="small"), **config}, height=380)
    selected = edited.loc[edited["Select"], "id"].astype(int).tolist()
    changed = edited.drop(columns="Select").compare(view.drop(columns="Select")).index
    with st.container(horizontal=True):
        if st.button(f"Save {len(changed)} change(s)", type="primary", disabled=len(changed) == 0, key=f"save_{kind}"):
            try:
                for index in changed:
                    row = edited.loc[index]
                    if kind == "purchases":
                        db.update_purchase(uid, int(row["id"]), date=row["date"], quantity=row["quantity"],
                                           unit=row["unit"], total_price=None if pd.isna(row["total_price"]) else row["total_price"])
                    else:
                        db.update_check(uid, int(row["id"]), date=row["date"], remaining=row["remaining"],
                                        wasted=row["wasted"])
                queue_toast(f"Saved {len(changed)} change(s).")
                st.rerun()
            except ValueError as error:
                st.error(str(error))
        if st.button(f"Delete selected ({len(selected)})", disabled=not selected, key=f"delete_{kind}"):
            confirm_delete(kind, selected)


purchases_tab, checks_tab, foods_tab, files_tab = st.tabs(["Purchases", "Pantry checks", "Foods", "Import and export"])
date_column = st.column_config.DateColumn("Date", format="D MMM YYYY")

with purchases_tab:
    editable_table(buys, "purchases", ["date", "quantity", "unit", "total_price"], {
        "date": date_column, "food": "Food", "category": "Category", "quantity": number("Quantity"),
        "unit": "Unit", "total_price": number("Total paid (₹)"), "shelf_life_days": None})

with checks_tab:
    editable_table(checks, "pantry checks", ["date", "remaining", "wasted"], {
        "date": date_column, "food": "Food", "category": None, "unit": "Unit", "remaining": number("Left"),
        "wasted": number("Thrown away"), "shelf_life_days": None})

with foods_tab:
    if foods.empty:
        st.write("Foods appear here when you log a purchase.")
    else:
        edited = st.data_editor(foods, hide_index=True, width="stretch", num_rows="fixed", key="edit_foods",
                                disabled=["id"], column_config={
                                    "id": None, "name": "Food", "category": "Category", "unit": "Default unit",
                                    "shelf_life_days": st.column_config.NumberColumn("Shelf life (days)", min_value=1, step=1)})
        changed = edited.compare(foods).index
        if st.button(f"Save {len(changed)} change(s)", type="primary", disabled=len(changed) == 0, key="save_foods"):
            for index in changed:
                row = edited.loc[index]
                db.update_food(uid, int(row["id"]), name=row["name"], category=row["category"], unit=row["unit"],
                               shelf_life_days=None if pd.isna(row["shelf_life_days"]) else int(row["shelf_life_days"]))
            queue_toast(f"Saved {len(changed)} food change(s).")
            st.rerun()

with files_tab:
    left, right = st.columns(2, gap="large")
    with left:
        section("Export", "Your data as CSV, in the same columns the importer reads.")
        export_buys = buys.drop(columns="id").assign(date=buys["date"].dt.strftime("%Y-%m-%d"))
        export_checks = checks[["date", "food", "remaining", "wasted"]].assign(
            date=checks["date"].dt.strftime("%Y-%m-%d"))
        st.download_button("Download purchases", export_buys.to_csv(index=False), "forage_purchases.csv",
                           "text/csv", disabled=buys.empty)
        st.download_button("Download pantry checks", export_checks.to_csv(index=False), "forage_pantry_checks.csv",
                           "text/csv", disabled=checks.empty)
        for name, path in TEMPLATES.items():
            st.download_button(f"Blank {name} template", path.read_bytes(), path.name, "text/csv")
    with right:
        section("Import", "Purchases or pantry checks. Rows already in your data are skipped.")
        uploaded = st.file_uploader("CSV file", type="csv")
        if uploaded is not None:
            try:
                raw = pd.read_csv(io.BytesIO(uploaded.getvalue()))  # in memory: nothing is written to disk
            except Exception as error:
                st.error(f"The file could not be read as CSV: {error}")
                raw = None
            if raw is not None:
                kind, rows, report = read_import(raw)
                if kind is None:
                    st.error("Not recognised: a purchases file needs date, food and quantity columns; a pantry-check "
                             "file needs date, food and remaining.")
                else:
                    removed = report["duplicates"] + report["missing_date_or_food"] + report["invalid_numbers"]
                    st.write(f"Recognised as **{kind}**: {len(rows):,} valid rows, {removed:,} removed "
                             f"({report['duplicates']} duplicates, {report['missing_date_or_food']} missing date or "
                             f"food, {report['invalid_numbers']} impossible numbers); {report['names_unified']} food "
                             "names unified for case and spacing.")
                    table(rows.head(8), max_rows=8)
                    if st.button(f"Import {len(rows):,} rows", type="primary", disabled=rows.empty):
                        with st.spinner("Importing..."):
                            added, skipped = (db.import_checks if kind == "checks" else db.import_purchases)(uid, rows)
                        queue_toast(f"Imported {added:,} {kind}; skipped {skipped:,} already present.")
                        st.rerun()
