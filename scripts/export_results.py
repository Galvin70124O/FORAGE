"""Write every key FORAGE result to outputs/results.json and report charts to outputs/*.png.

Run from the project root (outputs/ is git-ignored):
    python scripts/export_results.py

Uses the same functions as the app, so the numbers match the pages exactly.
M5 and Instacart sections are included only when their local extracts exist.
All models use random_state=42.
"""

import json
import logging
import sys
import warnings
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
warnings.filterwarnings("ignore")
logging.getLogger("streamlit").setLevel(logging.ERROR)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from services import data  # noqa: E402
from waste import overall_waste, rupee_summary  # noqa: E402

OUT = ROOT / "outputs"
ACCENT, GREY = "#2368c4", "#a3a29d"


def records(frame: pd.DataFrame, digits: int = 4) -> list[dict]:
    return json.loads(frame.round(digits).to_json(orient="records", date_format="iso"))


def save_bar(labels, values, title, xlabel, name, highlight=None, fmt="{:.3f}"):
    fig, ax = plt.subplots(figsize=(7, 0.45 * len(labels) + 1.2))
    colors = [ACCENT if (highlight is None and i == 0) or label == highlight else GREY for i, label in enumerate(labels)]
    ax.barh(list(labels)[::-1], list(values)[::-1], color=colors[::-1])
    for y, v in enumerate(list(values)[::-1]):
        ax.text(v, y, " " + fmt.format(v), va="center", fontsize=9)
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / name, dpi=150)
    plt.close(fig)


def forecasting_section(source: str) -> dict:
    per_fold, rolling = data.demo_rolling() if source == "demo" else data.m5_rolling()
    week = data.demo_week() if source == "demo" else data.m5_week()
    final = data.demo_forecast()["comparison"] if source == "demo" else data.m5_forecast()[2]
    save_bar(rolling["Model"], rolling["MAE_mean"], f"{source.upper()} next day: mean MAE over 5 rolling folds",
             "MAE (lower is better)", f"{source}_rolling_mae.png")
    save_bar(week["rolling"]["Model"], week["rolling"]["MAE_mean"],
             f"{source.upper()} next 7 days: mean MAE over 5 rolling folds", "MAE of the 7-day total",
             f"{source}_week_mae.png")
    return {"next_day_selected": rolling.iloc[0]["Model"], "next_day_rolling": records(rolling),
            "next_day_per_fold": records(per_fold.drop(columns=["Cutoff"])),
            "next_day_final_split": records(final),
            "seven_day_selected": week["best"], "seven_day_rolling": records(week["rolling"]),
            "seven_day_final_split": records(week["comparison"])}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    demo = data.load_demo()
    results = {"generated": date.today().isoformat(), "random_state": 42,
               "datasets": {"demo_rows": len(demo), "demo_foods": int(demo["Food"].nunique())}}

    # Waste in rupees (demo prices are synthetic)
    headline, rupees = overall_waste(demo), rupee_summary(demo)
    results["waste"] = {
        "label": "synthetic demo data; prices are illustrative",
        "waste_rate_mean_of_foods_pct": headline["rate"], "waste_rate_pooled_pct": headline["pooled_rate"],
        "rupees_wasted_total": rupees["total"],
        "rupees_wasted_per_month": {k.strftime("%Y-%m"): v for k, v in rupees["monthly"].round(0).items()},
        "rupees_by_category": rupees["by_category"].round(0).to_dict(),
        "rupees_top_foods": rupees["by_food"].head(5).round(0).to_dict()}
    monthly = rupees["monthly"]
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.plot(monthly.index, monthly.values, color=ACCENT)
    ax.set_title("₹ wasted per month (demo data, illustrative prices)", loc="left", fontsize=11, fontweight="bold")
    ax.set_ylabel("₹ wasted")
    ax.set_ylim(bottom=0)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / "demo_rupees_per_month.png", dpi=150)
    plt.close(fig)

    # Forecasting: final split, rolling origin, 7 days
    results["forecasting"] = {"demo": forecasting_section("demo")}
    if data.M5_PATH.exists():
        m5 = data.load_m5()
        results["datasets"]["m5_rows"] = len(m5)
        results["forecasting"]["m5"] = forecasting_section("m5")

    # Classifier, with and without purchased quantity
    clf = data.demo_classifier()
    best = clf["comparison"][clf["comparison"]["Features"] == "All features"].iloc[0]
    results["waste_risk_classifier"] = {
        "definition": "high waste = more than 30% of a purchase thrown away",
        "positive_rate": clf["positive_rate"], "selected": clf["best"], "threshold": clf["threshold"],
        "train_rows": clf["train_rows"], "test_rows": clf["test_rows"], "comparison": records(clf["comparison"]),
        "confusion_matrix_selected": {"TP": int(best["TP"]), "FP": int(best["FP"]), "FN": int(best["FN"]), "TN": int(best["TN"])},
        "permutation_importance_roc_auc": records(clf["importance"])}
    fig, ax = plt.subplots(figsize=(3.6, 3.2))
    matrix = np.array([[best["TP"], best["FN"]], [best["FP"], best["TN"]]])
    ax.imshow(matrix, cmap="Blues")
    for (i, j), v in np.ndenumerate(matrix):
        ax.text(j, i, f"{v}", ha="center", va="center", color="white" if v > matrix.max() / 2 else "black")
    ax.set_xticks([0, 1], ["Alert", "No alert"])
    ax.set_yticks([0, 1], ["High waste", "Not high"])
    ax.set_title(f"{best['Model']}: confusion matrix", fontsize=10, fontweight="bold")
    fig.tight_layout()
    fig.savefig(OUT / "classifier_confusion_matrix.png", dpi=150)
    plt.close(fig)
    save_bar(clf["importance"]["Feature"], clf["importance"]["Importance"], "Waste-risk classifier: permutation importance",
             "Drop in ROC-AUC when shuffled", "classifier_importance.png")

    # Forecaster explanations
    results["forecaster_importance"] = {}
    for source in ("demo", "m5") if data.M5_PATH.exists() else ("demo",):
        info = data.forecaster_explanations(source)
        results["forecaster_importance"][source] = {
            "model": info["model_name"], "importance_mae": records(info["importance"]),
            "worst_items_relative_mae_pct": records(info["by_item"].head(5)[[info["keys"][0], "Relative_MAE"]], 2)}
        save_bar(info["importance"]["Feature"], info["importance"]["Importance"],
                 f"{source.upper()} {info['model_name']}: permutation importance", "Rise in MAE when shuffled",
                 f"{source}_forecaster_importance.png")

    # Recommendation backtest
    summary, per_food, reference, days = data.demo_backtest()
    recorded, weekly = summary.loc["Recorded"], summary.loc["FORAGE weekly"]
    wasted = per_food.groupby("Policy")["Wasted"].sum()
    results["recommendation_backtest"] = {
        "label": "synthetic demo data", "days_simulated": days, "recorded_waste_reference_pct": reference,
        "policies": records(summary.reset_index()),
        "weekly_vs_recorded": {
            "waste_pct_before": recorded["Waste_Pct"], "waste_pct_after": weekly["Waste_Pct"],
            "waste_reduction_recorded_units": float(wasted["Recorded"] - wasted["FORAGE weekly"]),
            "units_note": "recorded units, mostly kg (some foods in L, dozen, loaf or pack)",
            "rupees_saved": float(recorded["Wasted_Rupees"] - weekly["Wasted_Rupees"]),
            "stockout_food_days_pct": weekly["Stockout_Pct"], "demand_unmet_pct": weekly["Unmet_Pct"]}}
    save_bar(summary.index, summary["Waste_Pct"], "Backtest: waste by household (demo, synthetic)",
             "Waste (% of purchases)", "backtest_waste.png", highlight="FORAGE weekly", fmt="{:.1f}%")

    # Hypothesis tests
    results["hypothesis_tests"] = {}
    for source in ["demo"] + [s for s in ("m5", "instacart") if (data.M5_PATH if s == "m5" else data.INSTACART_PATH).exists()]:
        results["hypothesis_tests"][source] = [
            {"test": t.name, "question": t.question, "H0": t.h0, "H1": t.h1, "statistic_name": t.statistic_name,
             "statistic": round(t.statistic, 4), "p_value": t.p_value, "effect_name": t.effect_name,
             "effect_size": round(t.effect, 4), "effect_label": t.effect_label, "n": t.n, "conclusion": t.conclusion}
            for t in data.source_tests(source)]

    # Instacart association rules
    if data.INSTACART_PATH.exists():
        from basket import strongest_rules
        insta = data.load_instacart()
        results["datasets"].update(instacart_order_lines=len(insta), instacart_orders=int(insta["Order_ID"].nunique()))
        (orders, products), rules = data.instacart_rules()
        top = strongest_rules(rules, 10)
        results["association_rules"] = {"orders_used": orders, "products": products, "rules_found": len(rules),
                                        "top_by_lift": records(top[["If", "Then", "Support", "Confidence", "Lift"]])}
        save_bar([f"{a} → {b}" for a, b in zip(top["If"], top["Then"])], top["Lift"],
                 "Instacart: top association rules by lift", "Lift", "instacart_top_rules.png", fmt="{:.2f}")

    # Cleaning on the messy sample
    _, _, cleaning, _ = data.messy_sample_cleaning()
    results["cleaning_messy_sample"] = cleaning

    (OUT / "results.json").write_text(json.dumps(results, indent=2, default=float), encoding="utf-8")
    print(f"Wrote outputs/results.json and {len(list(OUT.glob('*.png')))} charts to outputs/")


if __name__ == "__main__":
    main()
