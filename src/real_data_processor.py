"""One-time, bounded preprocessing for the M5 and Instacart raw datasets.

The raw downloads under ``dataset/`` are read-only inputs.  This module writes
small analytical extracts under ``data/real/`` and never feeds them into the
household/personal pipelines.

Run: ``python src/real_data_processor.py``
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "dataset"
OUT = ROOT / "data" / "real"
M5_OUT = OUT / "m5" / "m5_food_demand.csv"
INST_OUT = OUT / "instacart" / "instacart_purchase_history.csv"

M5_STORE = "CA_1"
M5_DEPARTMENTS = {"FOODS_1", "FOODS_2", "FOODS_3"}
M5_DAYS = 180
M5_PRODUCTS = 100
INST_MAX_USER_ID = 2_000


def _find(name: str) -> Path:
    """Locate a raw file even when a downloader created a same-name folder."""
    matches = list(RAW.rglob(name))
    files = [path for path in matches if path.is_file()]
    if not files:
        raise FileNotFoundError(f"Could not locate {name} below {RAW}")
    return files[0]


def raw_paths() -> dict[str, Path]:
    return {
        "m5_sales": _find("sales_train_validation.csv"), "m5_calendar": _find("calendar.csv"),
        "m5_prices": _find("sell_prices.csv"), "orders": _find("orders.csv"),
        "prior": _find("order_products__prior.csv"), "train": _find("order_products__train.csv"),
        "products": _find("products.csv"), "aisles": _find("aisles.csv"), "departments": _find("departments.csv"),
    }


def _quality(df: pd.DataFrame, key_columns: list[str]) -> dict:
    return {
        "rows": int(len(df)), "columns": list(df.columns), "missing_values": {k: int(v) for k, v in df.isna().sum().items()},
        "duplicate_keys": int(df.duplicated(key_columns).sum()),
    }


def process_m5(paths: dict[str, Path]) -> tuple[pd.DataFrame, dict]:
    calendar = pd.read_csv(paths["m5_calendar"], parse_dates=["date"])
    calendar = calendar.loc[calendar["d"].isin([f"d_{n}" for n in range(1, 1914)])].copy()
    selected_calendar = calendar.tail(M5_DAYS).copy()
    day_columns = selected_calendar["d"].tolist()
    base_columns = ["item_id", "dept_id", "cat_id", "store_id", "state_id"]
    food_chunks = []
    # Chunking keeps the 1,913-day-wide source out of the app and limits peak RAM.
    for chunk in pd.read_csv(paths["m5_sales"], usecols=base_columns + day_columns, chunksize=2_000):
        part = chunk[(chunk["store_id"] == M5_STORE) & chunk["dept_id"].isin(M5_DEPARTMENTS)]
        if not part.empty:
            food_chunks.append(part)
    food = pd.concat(food_chunks, ignore_index=True)
    totals = food[day_columns].sum(axis=1)
    food = food.loc[totals.nlargest(M5_PRODUCTS).index].copy()
    long = food.melt(id_vars=base_columns, value_vars=day_columns, var_name="d", value_name="Quantity_Sold")
    long = long.merge(selected_calendar[["d", "date", "wm_yr_wk", "weekday", "month", "event_name_1", "event_type_1"]], on="d", how="left", validate="many_to_one")
    price_parts = []
    item_ids = set(food["item_id"])
    for chunk in pd.read_csv(paths["m5_prices"], chunksize=100_000):
        part = chunk[(chunk["store_id"] == M5_STORE) & chunk["item_id"].isin(item_ids)]
        if not part.empty:
            price_parts.append(part)
    prices = pd.concat(price_parts, ignore_index=True)
    long = long.merge(prices, on=["store_id", "item_id", "wm_yr_wk"], how="left", validate="many_to_one")
    result = long.rename(columns={"date": "Date", "item_id": "Product_ID", "store_id": "Store_ID", "dept_id": "Department", "cat_id": "Category", "sell_price": "Price", "weekday": "Weekday", "event_name_1": "Event_Name", "event_type_1": "Event_Type"})[
        ["Date", "Product_ID", "Store_ID", "Department", "Category", "Quantity_Sold", "Price", "Weekday", "month", "Event_Name", "Event_Type"]
    ].rename(columns={"month": "Month"}).sort_values(["Product_ID", "Date"]).reset_index(drop=True)
    report = _quality(result, ["Date", "Product_ID", "Store_ID"])
    report.update({"selection": {"store": M5_STORE, "departments": sorted(M5_DEPARTMENTS), "days": M5_DAYS, "products": M5_PRODUCTS, "reason": "All genuine M5 food departments; one representative store and the highest-selling products in the final 180 available training days keep the dashboard responsive."}, "invalid_negative_sales": int((result["Quantity_Sold"] < 0).sum()), "missing_prices": int(result["Price"].isna().sum()), "invalid_dates": int(result["Date"].isna().sum())})
    return result, report


def process_instacart(paths: dict[str, Path]) -> tuple[pd.DataFrame, dict]:
    # The deterministic user-ID bound creates a repeatable, appropriately sized
    # relational extract without pretending it represents all 3.4m raw orders.
    order_parts = []
    for chunk in pd.read_csv(paths["orders"], chunksize=100_000):
        part = chunk[chunk["user_id"] <= INST_MAX_USER_ID]
        if not part.empty:
            order_parts.append(part)
    orders = pd.concat(order_parts, ignore_index=True)
    order_ids = set(orders["order_id"])
    line_parts = []
    for filename, label in [("prior", "prior"), ("train", "train")]:
        for chunk in pd.read_csv(paths[filename], chunksize=250_000):
            part = chunk[chunk["order_id"].isin(order_ids)].copy()
            if not part.empty:
                part["Order_Set"] = label
                line_parts.append(part)
    lines = pd.concat(line_parts, ignore_index=True)
    products = pd.read_csv(paths["products"])
    products = products.merge(pd.read_csv(paths["aisles"]), on="aisle_id", how="left", validate="many_to_one").merge(pd.read_csv(paths["departments"]), on="department_id", how="left", validate="many_to_one")
    result = lines.merge(orders, on="order_id", how="left", validate="many_to_one").merge(products, on="product_id", how="left", validate="many_to_one")
    result = result.rename(columns={"order_id": "Order_ID", "user_id": "User_ID", "order_number": "Order_Number", "order_dow": "Order_Day_Of_Week", "order_hour_of_day": "Order_Hour", "days_since_prior_order": "Days_Since_Prior_Order", "product_id": "Product_ID", "product_name": "Product_Name", "add_to_cart_order": "Add_To_Cart_Order", "reordered": "Reordered", "aisle": "Aisle", "department": "Department"})[
        ["Order_ID", "User_ID", "Order_Set", "Order_Number", "Order_Day_Of_Week", "Order_Hour", "Days_Since_Prior_Order", "Product_ID", "Product_Name", "Aisle", "Department", "Add_To_Cart_Order", "Reordered"]
    ].sort_values(["User_ID", "Order_Number", "Add_To_Cart_Order"]).reset_index(drop=True)
    report = _quality(result, ["Order_ID", "Product_ID", "Add_To_Cart_Order"])
    report.update({"selection": {"user_id_upper_bound": INST_MAX_USER_ID, "reason": "Deterministic subset of users 1–2,000, joined to all their available prior/train product lines; it avoids repeatedly processing 32m raw line items."}, "missing_product_metadata": int(result[["Product_Name", "Aisle", "Department"]].isna().any(axis=1).sum()), "missing_order_relationship": int(result["User_ID"].isna().sum()), "invalid_reordered": int((~result["Reordered"].isin([0, 1])).sum())})
    return result, report


def main() -> None:
    paths = raw_paths()
    m5, m5_report = process_m5(paths)
    M5_OUT.parent.mkdir(parents=True, exist_ok=True)
    m5.to_csv(M5_OUT, index=False, date_format="%Y-%m-%d")
    (M5_OUT.parent / "quality_report.json").write_text(json.dumps(m5_report, indent=2), encoding="utf-8")
    print(f"M5: {len(m5):,} rows written to {M5_OUT}")
    # Save the completed M5 extraction before the much larger Instacart scan.
    insta, insta_report = process_instacart(paths)
    INST_OUT.parent.mkdir(parents=True, exist_ok=True)
    insta.to_csv(INST_OUT, index=False)
    (INST_OUT.parent / "quality_report.json").write_text(json.dumps(insta_report, indent=2), encoding="utf-8")
    print(f"Instacart: {len(insta):,} rows written to {INST_OUT}")


if __name__ == "__main__":
    main()
