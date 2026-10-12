"""Single source-of-truth metadata for FORAGE's non-interchangeable datasets."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DATASETS = {
    "demo": {
        "label": "Demo / Synthetic Data",
        "kind": "synthetic development data",
        "path": ROOT / "data" / "cleaned_food_data.csv",
        "supports": {"consumption", "waste", "inventory", "demo_forecast"},
        "prohibits": {"real_statistics", "personal_statistics", "real_forecast", "real_recommendations"},
    },
    "personal": {
        "label": "My Personal Food Data",
        "kind": "user-entered or deliberately imported records",
        "path": ROOT / "data" / "my_food_data.csv",
        "supports": {"personal_statistics", "personal_forecast", "personal_recommendations"},
        "prohibits": {"public_data_claims"},
    },
    "m5": {
        "label": "M5 / Walmart — Real Public Dataset",
        "kind": "retail unit sales and demand",
        "path": ROOT / "data" / "real" / "m5" / "m5_food_demand.csv",
        "supports": {"retail_demand", "retail_forecast", "price_calendar_analysis"},
        "prohibits": {"consumption", "waste", "inventory", "household_purchase_recommendations"},
    },
    "instacart": {
        "label": "Instacart — Real Public Dataset",
        "kind": "market-basket ordering and reorder behavior",
        "path": ROOT / "data" / "real" / "instacart" / "instacart_purchase_history.csv",
        "supports": {"product_popularity", "order_frequency", "reorder_behavior", "category_analysis"},
        "prohibits": {"calendar_forecast", "consumption", "waste", "inventory", "physical_quantity_recommendations"},
    },
}


def get_dataset(name: str) -> dict:
    """Return immutable-in-practice source metadata or fail loudly for unknown sources."""
    try:
        return DATASETS[name]
    except KeyError as error:
        raise ValueError(f"Unknown FORAGE dataset source: {name}") from error
