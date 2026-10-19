"""Data-source registry, cached loaders and cached model results shared by every page."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from clean_data import RAW_DATA_PATH, clean_records
from dataset_registry import get_dataset
from m5_forecasting import forecast_retail_demand
from personal_data import load_personal_data
from prediction import run_demo_forecast
from recommendations import generate_recommendations
from ui.components import fmt_date

SOURCES = {
    "demo": "Demo data",
    "personal": "My Data",
    "m5": "M5 (Walmart)",
    "instacart": "Instacart",
}
HOUSEHOLD_SOURCES = {"demo", "personal"}
M5_PATH = get_dataset("m5")["path"]
INSTACART_PATH = get_dataset("instacart")["path"]
DEMO_PATH = get_dataset("demo")["path"]
EXTRACT_COMMAND = "python src/real_data_processor.py"


def current_source() -> str:
    return st.session_state.get("source", "demo")


def set_source(key: str) -> None:
    st.session_state["source"] = key


@st.cache_data(show_spinner="Loading demo data...")
def load_demo() -> pd.DataFrame:
    return pd.read_csv(DEMO_PATH, parse_dates=["Date", "Estimated_Expiry_Date"])


@st.cache_data(show_spinner="Loading the M5 extract...")
def load_m5() -> pd.DataFrame:
    return pd.read_csv(M5_PATH, parse_dates=["Date"], dtype={
        "Product_ID": "category", "Store_ID": "category", "Department": "category",
        "Category": "category", "Quantity_Sold": "int16", "Price": "float32",
        "Weekday": "category", "Month": "int8", "Event_Name": "category", "Event_Type": "category",
    })


@st.cache_data(show_spinner="Loading the Instacart extract...")
def load_instacart() -> pd.DataFrame:
    return pd.read_csv(INSTACART_PATH, dtype={
        "Order_ID": "int32", "User_ID": "int32", "Order_Set": "category",
        "Order_Number": "int16", "Order_Day_Of_Week": "int8", "Order_Hour": "int8",
        "Days_Since_Prior_Order": "float32", "Product_ID": "int32", "Product_Name": "category",
        "Aisle": "category", "Department": "category", "Add_To_Cart_Order": "int16", "Reordered": "int8",
    })


def load(source: str) -> pd.DataFrame | None:
    """The selected source's records, or None when a public extract has not been built."""
    if source == "demo":
        return load_demo()
    if source == "personal":
        return load_personal_data()
    if source == "m5":
        return load_m5() if M5_PATH.exists() else None
    return load_instacart() if INSTACART_PATH.exists() else None


def quality_report(source: str) -> dict | None:
    path = (M5_PATH if source == "m5" else INSTACART_PATH).parent / "quality_report.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def describe(source: str, df: pd.DataFrame | None) -> str:
    """One line for the data-source label under each page title."""
    if df is None:
        return "extract not built yet"
    if source == "demo":
        return f"synthetic household records · {len(df):,} rows · {fmt_date(df['Date'].min())} to {fmt_date(df['Date'].max())}"
    if source == "personal":
        if df.empty:
            return "no records yet"
        return f"your records · {len(df):,} rows · {fmt_date(df['Date'].min())} to {fmt_date(df['Date'].max())}"
    if source == "m5":
        return (f"Walmart retail unit sales, store CA_1, top {df['Product_ID'].nunique()} food items · "
                f"{len(df):,} rows · {fmt_date(df['Date'].min())} to {fmt_date(df['Date'].max())}")
    return (f"online grocery orders from users 1–2,000 · {len(df):,} order lines · "
            f"{df['Order_ID'].nunique():,} orders · no calendar dates")


@st.cache_data(show_spinner="Evaluating forecasting models on the held-out period...")
def demo_forecast() -> dict:
    return run_demo_forecast(load_demo())


@st.cache_data(show_spinner="Evaluating forecasting models on the held-out period...")
def personal_forecast(df: pd.DataFrame) -> dict:
    return run_demo_forecast(df.sort_values(["Food", "Date"]).reset_index(drop=True))


@st.cache_data(show_spinner="Evaluating M5 forecasting models on the held-out period...")
def m5_forecast():
    return forecast_retail_demand(load_m5())


@st.cache_data(show_spinner="Building the purchase plan...")
def demo_recommendations():
    return generate_recommendations(load_demo(), demo_forecast()["best_model"])


@st.cache_data
def demo_cleaning_summary() -> dict:
    return clean_records(pd.read_csv(RAW_DATA_PATH))[1]


@st.cache_data
def raw_demo() -> pd.DataFrame:
    return pd.read_csv(RAW_DATA_PATH)
