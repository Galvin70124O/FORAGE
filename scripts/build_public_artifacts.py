"""Build data/public/: aggregated M5 and Instacart results for the online app (committed; raw files are not).

Run from the project root, on a machine that has the raw extracts in data/real/:
    python scripts/build_public_artifacts.py

It uses the same functions as the app, so the online pages show exactly the
numbers the local version computes. Instacart is published as aggregates only
(no user IDs, no order-level rows). All models use random_state=42.
"""

import logging
import sys
import warnings
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
warnings.filterwarnings("ignore")
logging.getLogger("streamlit").setLevel(logging.ERROR)

import pandas as pd  # noqa: E402

import public_data  # noqa: E402
from services import data  # noqa: E402
from stats import descriptive_statistics  # noqa: E402

M5_TEST_COLUMNS = ["Date", "Product_ID", "Department", "Quantity_Sold"]
WEEK_TEST_COLUMNS = ["Date", "Product_ID", "Target_7"]


def m5_bundle() -> tuple[dict, dict]:
    df = data.load_m5()
    tested, _, comparison, meta = data.m5_forecast()
    per_fold, summary = data.m5_rolling()
    week = data.m5_week()
    info = data.forecaster_explanations("m5")
    models = list(comparison["Model"])
    numeric = ["Quantity_Sold", "Price"]
    tables = {
        "item_day": df,
        "summary_statistics": descriptive_statistics(df, numeric).reset_index(),
        "forecast_comparison": comparison,
        "forecast_test": tested[M5_TEST_COLUMNS + models].assign(Product_ID=lambda d: d["Product_ID"].astype(str),
                                                                 Department=lambda d: d["Department"].astype(str)),
        "rolling_per_fold": per_fold, "rolling_summary": summary,
        "week_comparison": week["comparison"], "week_rolling": week["rolling"], "week_per_fold": week["per_fold"],
        "week_test": week["test"][WEEK_TEST_COLUMNS + list(week["comparison"]["Model"])],
        "week_latest": week["latest"].rename("Forecast").rename_axis("Product_ID").reset_index(),
        "explain_importance": info["importance"], "explain_residuals": info["residuals"],
        "explain_by_item": info["by_item"], "explain_by_group": info["by_group"],
        "tests": public_data.tests_frame(data.source_tests("m5")),
    }
    values = {
        "forecast": {"cutoff": str(meta["cutoff"].date()), "best_model": meta["best_model"],
                     "train_rows": meta["train_rows"], "test_rows": meta["test_rows"]},
        "week": {"best": week["best"], "cutoff": str(pd.Timestamp(week["cutoff"]).date()),
                 "train_rows": week["train_rows"], "test_rows": week["test_rows"]},
        "explanations": {"model_name": info["model_name"], "selected_overall": info["selected_overall"],
                         "keys": list(info["keys"])},
        "quality_report": data.quality_report("m5"),
    }
    return tables, values


def instacart_bundle() -> tuple[dict, dict]:
    tables, values = public_data.instacart_summary(data.load_instacart())
    (orders, products), rules = data.instacart_rules()
    tables["rules"] = public_data.rules_frame(rules)
    tables["tests"] = public_data.tests_frame(data.source_tests("instacart"))
    values.update(rules_orders=int(orders), rules_products=int(products), quality_report=data.quality_report("instacart"))
    return tables, values


def main() -> None:
    built = date.today().isoformat()
    for name, build in (("m5", m5_bundle), ("instacart", instacart_bundle)):
        if not data.has_raw(name):
            print(f"{name}: raw extract not found in data/real/, skipped (run python src/real_data_processor.py)")
            continue
        manifest = public_data.write_bundle(name, *build(), built=built)
        rows = sum(info["rows"] or 0 for info in manifest["files"].values())
        print(f"{name}: {len(manifest['files'])} files, {rows:,} table rows, {manifest['total_bytes'] / 1e6:.2f} MB")
    total = sum(p.stat().st_size for p in public_data.PUBLIC_DIR.rglob("*") if p.is_file())
    print(f"data/public/ total: {total / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
