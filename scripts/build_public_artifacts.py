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

def m5_bundle() -> tuple[dict, dict]:
    """M5 aggregates only: department-day totals, distributions, the 10 best sellers' weekly totals, 10 trend rows
    and the model results. No prices and no per-item daily rows (tests/test_public_data.py enforces this)."""
    import numpy as np

    from explain import reading
    from services.overview import m5_accuracy

    df = data.load_m5()
    tables, values = public_data.m5_summary(df, include_price=False)
    tested, _, comparison, meta = data.m5_forecast()
    per_fold, summary = data.m5_rolling()
    week = data.m5_week()
    info = data.forecaster_explanations("m5")
    department = df.drop_duplicates("Product_ID").set_index(df.drop_duplicates("Product_ID")["Product_ID"].astype(str))[
        "Department"].astype(str)
    models, week_models = list(comparison["Model"]), list(week["comparison"]["Model"])
    forecast_departments = (tested.assign(Department=tested["Department"].astype(str))
                            .groupby(["Date", "Department"])[["Quantity_Sold", *models]].sum().reset_index())
    week_test = week["test"].assign(Department=lambda d: d["Product_ID"].astype(str).map(department))
    week_departments = week_test.groupby(["Date", "Department"])[["Target_7", *week_models]].sum().reset_index()
    counts, edges = np.histogram(info["residuals"]["Residual"], bins=60)
    residual_distribution = pd.DataFrame({"Residual": (edges[:-1] + edges[1:]) / 2, "Item_days": counts})
    accuracy_now, accuracy_before = m5_accuracy(tested, data.best_next_day("m5"))
    tables.update({
        "forecast_comparison": comparison,
        "forecast_test": forecast_departments,
        "rolling_per_fold": per_fold, "rolling_summary": summary,
        "week_comparison": week["comparison"], "week_rolling": week["rolling"], "week_per_fold": week["per_fold"],
        "week_test": week_departments,
        "explain_importance": info["importance"], "explain_residual_distribution": residual_distribution,
        "explain_by_item": info["by_item"].head(public_data.M5_TOP_ITEMS), "explain_by_group": info["by_group"],
        "tests": public_data.tests_frame(data.source_tests("m5")),
    })
    values.update({
        "forecast": {"cutoff": str(meta["cutoff"].date()), "best_model": meta["best_model"],
                     "train_rows": meta["train_rows"], "test_rows": meta["test_rows"]},
        "week": {"best": week["best"], "cutoff": str(pd.Timestamp(week["cutoff"]).date()),
                 "train_rows": week["train_rows"], "test_rows": week["test_rows"]},
        "explanations": {"model_name": info["model_name"], "selected_overall": info["selected_overall"],
                         "keys": list(info["keys"]),
                         "reading": reading(info["residuals"], info["by_item"], info["keys"][0], "units sold per item-day")},
        "accuracy_now": accuracy_now, "accuracy_before": accuracy_before,
        "quality_report": without_price(data.quality_report("m5")),
    })
    return tables, values


def without_price(report: dict | None) -> dict | None:
    """The extract's quality report minus any mention of the Price column (prices are not published)."""
    if report is None:
        return None
    report = {k: v for k, v in report.items() if "price" not in k.lower()}
    report["columns"] = [c for c in report.get("columns", []) if c != "Price"]
    report["missing_values"] = {k: v for k, v in report.get("missing_values", {}).items() if k != "Price"}
    return report


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
