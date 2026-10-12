"""Transparent column mapping for external food-related CSV files."""

import re

import pandas as pd


# Each key is a project-standard column. Add new aliases here as new data sources
# are encountered; no AI or hidden matching is used.
COLUMN_ALIASES = {
    "Date": ["date", "transaction_date", "purchase_date", "record_date"],
    "Food": ["food", "food_name", "item", "item_name", "product", "product_name"],
    "Category": ["category", "food_category", "product_category", "type"],
    "Quantity_Unit": ["quantity_unit", "unit", "units", "measurement_unit"],
    "Quantity_Purchased": [
        "quantity_purchased", "qty_bought", "purchased", "quantity_bought",
        "qty_purchased", "bought_quantity", "purchase_quantity",
    ],
    "Quantity_Consumed": [
        "quantity_consumed", "qty_used", "consumed", "quantity_used",
        "used_quantity", "consumption_quantity",
    ],
    "Quantity_Wasted": [
        "quantity_wasted", "waste", "wasted", "discarded", "quantity_discarded",
        "waste_quantity",
    ],
    "Remaining_Quantity": [
        "remaining_quantity", "quantity_remaining", "remaining", "stock_remaining",
    ],
    "Price": ["price", "cost", "amount", "purchase_cost", "total_cost"],
    "Expiry_Days": ["expiry_days", "shelf_life_days", "days_to_expiry"],
    "Estimated_Expiry_Date": ["estimated_expiry_date", "expiry_date", "expiration_date"],
    "Storage_Type": ["storage_type", "storage", "storage_location"],
    "Is_Festival": ["is_festival", "festival", "festival_flag"],
}

# These fields make a row usable for a basic food purchase/consumption record.
# Other project columns remain optional for external data.
MINIMUM_REQUIRED_COLUMNS = {"Food", "Date"}


def normalise_column_name(name):
    """Make column matching insensitive to spaces, hyphens, and letter case."""
    return re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")


def find_column_mapping(columns):
    """Return standard-to-source mapping and source columns not recognised."""
    normalised_sources = {normalise_column_name(column): column for column in columns}
    mapping = {}
    used_sources = set()

    for standard_name, aliases in COLUMN_ALIASES.items():
        candidates = [normalise_column_name(standard_name), *aliases]
        for candidate in candidates:
            source = normalised_sources.get(normalise_column_name(candidate))
            if source is not None and source not in used_sources:
                mapping[standard_name] = source
                used_sources.add(source)
                break

    unmapped = [column for column in columns if column not in used_sources]
    return mapping, unmapped


def standardise_columns(df):
    """Keep recognised columns and rename them to the project-standard schema."""
    mapping, unmapped = find_column_mapping(df.columns)
    source_to_standard = {source: standard for standard, source in mapping.items()}
    standardised = df[list(source_to_standard)].rename(columns=source_to_standard).copy()
    return standardised, mapping, unmapped
