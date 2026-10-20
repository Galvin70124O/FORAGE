"""Aggregated public results for M5 and Instacart, published in data/public/ instead of the raw extracts.

The raw M5 and Instacart files are not redistributed (their terms do not clearly
allow it). scripts/build_public_artifacts.py runs where the raw extracts exist and
writes small tables here; the online app reads them when the raw files are absent.

- M5: aggregates only. Department-day unit totals, distributions, the 10 best
  sellers' weekly totals, 10 trend rows, and every model result the pages show
  (metrics, rolling-origin folds, department-level predictions vs actuals, a
  residual distribution, importance, hypothesis tests). No prices and no per-item
  daily rows.
- Instacart: aggregates only (departments, aisles, products, distributions, the
  association rules, χ² results). No user IDs and no order-level rows.

Every table is a CSV; scalars go in values.json; manifest.json records the source,
licence note, build date, row counts and a SHA-256 hash of each file.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from hypothesis import TestResult

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = ROOT / "data" / "public"

LICENCES = {
    "m5": {
        "source": "M5 Forecasting - Accuracy (Walmart), Kaggle competition data, store CA_1",
        "url": "https://www.kaggle.com/competitions/m5-forecasting-accuracy/data",
        "attribution": "Data: Walmart via the M5 Forecasting competition (University of Nicosia / MOFC, Kaggle).",
        "licence": ("Kaggle competition rules: non-commercial, academic use. The raw files are not redistributed; "
                    "this folder holds aggregates only: department daily totals, the 10 best sellers' weekly totals "
                    "and model results. No prices and no per-item daily rows."),
    },
    "instacart": {
        "source": "The Instacart Online Grocery Shopping Dataset 2017, users 1-2,000",
        "url": "https://www.kaggle.com/datasets/psparks/instacart-market-basket-analysis",
        "attribution": "Data: \"The Instacart Online Grocery Shopping Dataset 2017\", Instacart.",
        "licence": ("Non-commercial use, subject to Instacart's terms. The raw files are not redistributed; this "
                    "folder holds aggregates only: no user IDs and no order-level rows."),
    },
}


# --- writing and reading bundles ------------------------------------------------
def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_bundle(name: str, tables: dict[str, pd.DataFrame], values: dict, built: str,
                 directory: Path = PUBLIC_DIR) -> dict:
    """Write each table as CSV plus values.json and manifest.json; return the manifest."""
    folder = directory / name
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.csv"):
        old.unlink()
    files = {}
    for key, frame in tables.items():
        path = folder / f"{key}.csv"
        dates = [c for c in frame.columns if pd.api.types.is_datetime64_any_dtype(frame[c])]
        frame.to_csv(path, index=False, lineterminator="\n", float_format="%.10g")
        files[path.name] = {"rows": len(frame), "columns": list(map(str, frame.columns)), "dates": dates}
    values_path = folder / "values.json"
    # newline="\n": the bytes (and so the hashes) must be the same on every OS; .gitattributes keeps them LF.
    values_path.write_text(json.dumps(values, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    files[values_path.name] = {"rows": None}
    for file, info in files.items():
        info["sha256"] = _sha256(folder / file)
    manifest = {"dataset": name, **LICENCES[name], "built": built, "files": files,
                "total_bytes": sum((folder / f).stat().st_size for f in files)}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    return manifest


def manifest(name: str, directory: Path = PUBLIC_DIR) -> dict | None:
    path = directory / name / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def available(name: str, directory: Path = PUBLIC_DIR) -> bool:
    return manifest(name, directory) is not None


def read_table(name: str, key: str, directory: Path = PUBLIC_DIR) -> pd.DataFrame:
    info = manifest(name, directory)["files"][f"{key}.csv"]
    return pd.read_csv(directory / name / f"{key}.csv", parse_dates=info["dates"] or False)


def read_values(name: str, directory: Path = PUBLIC_DIR) -> dict:
    return json.loads((directory / name / "values.json").read_text(encoding="utf-8"))


# --- conversions for objects that are not plain tables ----------------------------
def _encode(value):
    if isinstance(value, pd.DataFrame):  # e.g. a χ² contingency table (aggregate counts)
        return {"__frame__": json.loads(value.to_json(orient="split"))}
    return float(value) if hasattr(value, "item") else value


def _decode(value):
    if isinstance(value, dict) and "__frame__" in value:
        frame = value["__frame__"]
        return pd.DataFrame(frame["data"], index=frame["index"], columns=frame["columns"])
    return value


def tests_frame(results: list[TestResult]) -> pd.DataFrame:
    return pd.DataFrame([{**{k: v for k, v in asdict(r).items() if k != "extra"},
                          "extra": json.dumps({k: _encode(v) for k, v in r.extra.items()})} for r in results])


def tests_from_frame(frame: pd.DataFrame) -> list[TestResult]:
    rows = frame.to_dict("records")
    return [TestResult(**{**row, "n": int(row["n"]),
                          "extra": {k: _decode(v) for k, v in json.loads(row["extra"]).items()}}) for row in rows]


def rules_frame(rules: pd.DataFrame) -> pd.DataFrame:
    """Association rules with item sets stored as text (items joined by ' | ')."""
    return rules.assign(Antecedents=rules["Antecedents"].map(lambda s: " | ".join(sorted(s))),
                        Consequents=rules["Consequents"].map(lambda s: " | ".join(sorted(s))))


def rules_from_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.assign(Antecedents=frame["Antecedents"].map(lambda s: frozenset(s.split(" | "))),
                        Consequents=frame["Consequents"].map(lambda s: frozenset(s.split(" | "))))


# --- Instacart aggregates ------------------------------------------------------------
ORDER_COLUMNS = {"Basket": "Items per order", "Reorder_Share": "Reordered share of basket",
                 "Days_Since": "Days since previous order", "Order_Hour": "Hour of day (0–23)",
                 "Order_Day": "Day code (0–6)", "Order_Number": "Customer's order number"}
INSTACART_NUMERIC = ["Order_Hour", "Days_Since_Prior_Order", "Add_To_Cart_Order", "Order_Number"]
REPEAT_MIN_LINES = 50


def per_order(df: pd.DataFrame) -> pd.DataFrame:
    """One row per order (used only while building aggregates; never published)."""
    orders = df.groupby("Order_ID").agg(
        Basket=("Product_ID", "size"), Reorder_Share=("Reordered", "mean"), Order_Hour=("Order_Hour", "first"),
        Order_Day=("Order_Day_Of_Week", "first"), Days_Since=("Days_Since_Prior_Order", "first"),
        Order_Number=("Order_Number", "first"))
    return orders.rename(columns=ORDER_COLUMNS).reset_index(drop=True)


def instacart_summary(df: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], dict]:
    """Every Instacart figure the app shows, as aggregate tables and scalars (no IDs, no order rows)."""
    from data_quality import column_profile, iqr_outliers
    from stats import correlation_matrix, descriptive_statistics, frequency_table

    orders = per_order(df)
    columns = list(ORDER_COLUMNS.values())
    lines = df.assign(Department=df["Department"].astype(str), Aisle=df["Aisle"].astype(str),
                      Product_Name=df["Product_Name"].astype(str))
    departments = (lines.groupby("Department").agg(Lines=("Order_ID", "size"), Reorder_Rate=("Reordered", "mean"))
                   .assign(Reorder_Rate=lambda d: d["Reorder_Rate"] * 100)
                   .sort_values("Lines", ascending=False).reset_index())
    aisles = (lines.groupby(["Aisle", "Department"]).agg(Lines=("Order_ID", "size"), Reorder_Rate=("Reordered", "mean"))
              .assign(Reorder_Rate=lambda d: d["Reorder_Rate"] * 100)
              .sort_values("Lines", ascending=False).reset_index())
    products = (lines.groupby(["Product_Name", "Department"])
                .agg(Order_Lines=("Order_ID", "size"), Customers=("User_ID", "nunique"), Reorder_Rate=("Reordered", "mean"))
                .reset_index())
    products = products[products["Order_Lines"] >= REPEAT_MIN_LINES].assign(
        Reorder_Rate=lambda d: d["Reorder_Rate"] * 100).sort_values(["Order_Lines"], ascending=False)
    first = df.drop_duplicates("Order_ID")
    day_hour = (first.groupby(["Order_Day_Of_Week", "Order_Hour"]).size().rename("Orders").reset_index()
                .rename(columns={"Order_Day_Of_Week": "Day_Code", "Order_Hour": "Hour"}))
    basket_sizes = orders.groupby("Items per order").size().rename("Orders").reset_index()
    days_since = (first["Days_Since_Prior_Order"].value_counts(dropna=False).rename("Orders")
                  .rename_axis("Days_Since").reset_index().sort_values("Days_Since"))
    tables = {
        "departments": departments, "aisles": aisles, "products": products,
        "frequency": frequency_table(lines["Department"], label="Department").reset_index(),
        "order_statistics": descriptive_statistics(orders, columns).reset_index(),
        "order_correlation": correlation_matrix(orders, columns).reset_index(names="Variable"),
        "basket_sizes": basket_sizes, "day_hour": day_hour, "days_since": days_since,
        "profile": column_profile(df), "outliers": iqr_outliers(df, INSTACART_NUMERIC),
    }
    values = {
        "order_lines": len(df), "orders": int(df["Order_ID"].nunique()), "products": int(df["Product_ID"].nunique()),
        "customers": int(df["User_ID"].nunique()), "columns": len(df.columns),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_keys": int(df.duplicated(subset=["Order_ID", "Product_ID"]).sum()),
        "reorder_rate": float(df["Reordered"].mean()), "items_per_order": float(orders["Items per order"].mean()),
        "order_columns": columns, "repeat_min_lines": REPEAT_MIN_LINES,
    }
    return tables, values


# --- M5 aggregates -----------------------------------------------------------------
M5_TOP_ITEMS = 10  # the only per-item detail published: weekly totals of the 10 best sellers
M5_COLUMNS = {"Quantity_Sold": "Units sold (per item-day)", "Price": "Price (USD)", "Day_Number": "Weekday (0 = Monday)",
              "Month": "Month", "Event_Day": "Event day (1 = yes)"}
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def m5_trends(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Mean daily units per item, last 28 days vs the previous 28, for items selling at least 1 a day before."""
    end = df["Date"].max()
    recent = df[df["Date"] > end - pd.Timedelta(days=28)]
    previous = df[(df["Date"] <= end - pd.Timedelta(days=28)) & (df["Date"] > end - pd.Timedelta(days=56))]
    trend = pd.DataFrame({"Recent": recent.groupby("Product_ID", observed=True)["Quantity_Sold"].mean(),
                          "Previous": previous.groupby("Product_ID", observed=True)["Quantity_Sold"].mean()}).dropna()
    trend = trend[trend["Previous"] >= 1]
    trend["Change"] = (trend["Recent"] - trend["Previous"]) / trend["Previous"] * 100
    trend = trend.sort_values("Change", ascending=False).rename_axis("Product_ID").reset_index()
    trend["Product_ID"] = trend["Product_ID"].astype(str)
    counts = {"compared": len(trend), "rising": int((trend["Change"] >= 20).sum()),
              "falling": int((trend["Change"] <= -20).sum()), "window_end": str(end.date()),
              "daily_now": float(recent.groupby("Date")["Quantity_Sold"].sum().mean()),
              "daily_before": float(previous.groupby("Date")["Quantity_Sold"].sum().mean())}
    return trend, counts


def m5_summary(df: pd.DataFrame, *, include_price: bool) -> tuple[dict[str, pd.DataFrame], dict]:
    """Every M5 figure the pages show, as aggregates. Published with include_price=False:
    no prices and no per-item daily rows (only the top items' weekly totals and 10 trend rows)."""
    from data_quality import column_profile, iqr_outliers
    from stats import correlation_matrix, descriptive_statistics, frequency_table

    frame = df.assign(Day_Number=df["Date"].dt.dayofweek, Event_Day=df["Event_Name"].notna().astype(int))
    columns = {k: v for k, v in M5_COLUMNS.items() if include_price or k != "Price"}
    frame = frame.rename(columns=columns)
    stat_columns = list(columns.values())
    lines = df.assign(Department=df["Department"].astype(str), Category=df["Category"].astype(str),
                      Product_ID=df["Product_ID"].astype(str))
    department_day = (lines.groupby(["Date", "Category", "Department"])
                      .agg(Units=("Quantity_Sold", "sum"), Items=("Product_ID", "nunique")).reset_index())
    weekday = lines.groupby("Weekday", observed=True)["Quantity_Sold"].mean().reindex(WEEKDAYS)
    top = lines.groupby("Product_ID")["Quantity_Sold"].sum().nlargest(M5_TOP_ITEMS).index
    top_weekly = (lines[lines["Product_ID"].isin(top)]
                  .assign(Week=lambda d: d["Date"].dt.to_period("W").dt.start_time)
                  .groupby(["Week", "Product_ID"])["Quantity_Sold"].sum().rename("Units").reset_index())
    trend, counts = m5_trends(lines)
    shown_trend = pd.concat([trend.head(M5_TOP_ITEMS // 2), trend.tail(M5_TOP_ITEMS // 2)]).drop_duplicates("Product_ID")
    weekend = weekday[["Saturday", "Sunday"]].mean()
    numeric = ["Quantity_Sold"] + (["Price"] if include_price else [])
    profile = column_profile(df)
    tables = {
        "department_day": department_day,
        "statistics": descriptive_statistics(frame, stat_columns).reset_index(),
        "correlation": correlation_matrix(frame, stat_columns).reset_index(names="Variable"),
        "frequency": frequency_table(lines["Department"], label="Department").reset_index(),
        "units_distribution": lines["Quantity_Sold"].value_counts().sort_index().rename("Item_days")
                              .rename_axis("Units").reset_index(),
        "weekday": weekday.rename("Mean_Units").rename_axis("Weekday").reset_index(),
        "top_items_weekly": top_weekly,
        "trends": shown_trend if not include_price else trend,
        "profile": profile if include_price else profile[profile["Column"] != "Price"],
        "outliers": iqr_outliers(df, numeric),
    }
    values = {
        "rows": len(df), "columns": len(df.columns), "items": int(lines["Product_ID"].nunique()),
        "missing_values": int(df.isna().sum().sum()),
        "duplicate_keys": int(df.duplicated(subset=["Date", "Product_ID", "Store_ID"]).sum()),
        "date_min": str(df["Date"].min().date()), "date_max": str(df["Date"].max().date()),
        "stat_columns": stat_columns, "units_q75": float(lines["Quantity_Sold"].quantile(0.75)),
        "weekend_uplift_pct": float((weekend / weekday.drop(["Saturday", "Sunday"]).mean() - 1) * 100),
        "trend_counts": counts, "top_items": [str(i) for i in top],
    }
    return tables, values


class PublicSummary:
    """Aggregates for a public source: tables as attributes, scalars in .values, .offline when read from disk."""

    def __init__(self, tables: dict[str, pd.DataFrame], values: dict, *, offline: bool):
        self.tables, self.values, self.offline = tables, values, offline
        key = "order_correlation" if "order_correlation" in tables else "correlation"
        self.correlation = tables[key].set_index("Variable") if key in tables else None
        if self.correlation is not None:
            self.correlation.index.name = None

    def __getattr__(self, name: str) -> pd.DataFrame:
        try:
            return self.__dict__["tables"][name]
        except KeyError as error:
            raise AttributeError(name) from error

    def __len__(self) -> int:
        return self.values.get("order_lines", self.values.get("rows", 0))


InstacartSummary = PublicSummary
