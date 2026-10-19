import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))


def make_raw_row(**overrides):
    """One valid raw demo record; override fields to make it invalid."""
    row = {
        "Date": "2025-03-01", "Food": "Milk", "Category": "Dairy", "Input_Method": "Manual Entry",
        "Source_Reference": "MAN-1", "Quantity_Unit": "L", "Quantity_Purchased": 2.0,
        "Quantity_Consumed": 1.2, "Quantity_Wasted": 0.3, "Quantity_Remaining": 0.5,
        "Price": 60.0, "Expiry_Days": 7, "Estimated_Expiry_Date": "2025-03-08",
        "Storage_Type": "Refrigerator", "Is_Festival": 0,
    }
    row.update(overrides)
    return row


@pytest.fixture
def daily_series():
    """Two foods, 60 days each, with distinct deterministic consumption patterns."""
    dates = pd.date_range("2025-01-01", periods=60, freq="D")
    rows = []
    for food, category, base in (("Milk", "Dairy", 2.0), ("Rice", "Grains", 5.0)):
        for i, date in enumerate(dates):
            rows.append({"Date": date, "Food": food, "Category": category, "Quantity_Unit": "kg",
                         "Quantity_Consumed": base + (i % 7) * 0.1 + i * 0.01, "Is_Festival": 0})
    return pd.DataFrame(rows)
