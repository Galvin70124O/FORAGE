"""Truthful metadata profiles for FORAGE's explicitly separate data sources."""
from __future__ import annotations

from pathlib import Path
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent


def instacart_profile(df: pd.DataFrame) -> dict:
    return {
        "source": "Instacart — Real Public Dataset", "type": "Food ordering and purchase behavior",
        "records": len(df), "columns": len(df.columns), "date_range": "Not available (the source provides order timing, not calendar dates)",
        "items": df["Product_ID"].nunique(), "available": "Orders, users, product lines, reorders, basket size, department/aisle and day/hour patterns",
        "unavailable": "Household consumption, waste, inventory, expiry, physical quantities, calendar dates",
        "forecasting": "No — no real calendar date series", "waste": "No", "inventory": "No",
    }


def m5_profile(df: pd.DataFrame) -> dict:
    return {
        "source": "M5 / Walmart — Real Public Dataset", "type": "Retail unit sales and demand",
        "records": len(df), "columns": len(df.columns), "date_range": f"{df['Date'].min():%d %b %Y} – {df['Date'].max():%d %b %Y}",
        "items": df["Product_ID"].nunique(), "available": "Retail unit sales, dates/calendar, M5 item/category information, weekly sell price, event patterns and demand forecasting",
        "unavailable": "Household consumption, measured food waste, household inventory and expiry dates",
        "forecasting": "Yes — chronological retail-demand forecast", "waste": "No", "inventory": "No",
    }


def demo_profile(df: pd.DataFrame) -> dict:
    return {
        "source": "Demo / Synthetic Data", "type": "Simulated household-style development data",
        "records": len(df), "columns": len(df.columns), "date_range": f"{df['Date'].min():%d %b %Y} – {df['Date'].max():%d %b %Y}",
        "items": df["Food"].nunique(), "available": "Simulated purchase, consumption, waste, inventory and expiry fields",
        "unavailable": "Real-world evidence", "forecasting": "Demo only", "waste": "Demo only", "inventory": "Demo only",
    }
