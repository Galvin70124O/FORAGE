"""Compute every heavy demo result once and save it for instant cold starts (see src/artifacts.py).

Run from the project root after changing the demo data or any model code:
    python scripts/precompute_demo.py

Fitted models are not saved; only tables and numbers. tests/test_precomputed.py fails if the saved file
no longer matches the current data, code or package versions.
"""

import os
import sys
import time
import warnings
from pathlib import Path

os.environ["FORAGE_NO_PRECOMPUTED"] = "1"  # compute live, ignoring any existing file
ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "src"), str(ROOT)]
warnings.filterwarnings("ignore", message=".*ScriptRunContext.*")

import logging  # noqa: E402

logging.getLogger("streamlit").setLevel(logging.ERROR)

from artifacts import save  # noqa: E402
from services import data  # noqa: E402
from services.overview import demo_dashboard  # noqa: E402


def without(result: dict, *keys: str) -> dict:
    return {k: v for k, v in result.items() if k not in keys}


def main() -> None:
    start = time.time()
    explanations = data.forecaster_explanations("demo")  # needs the fitted forecaster, so it runs first
    results = {
        "demo_forecast": without(data.demo_forecast(), "models", "test_features"),
        "demo_rolling": data.demo_rolling(),
        "demo_week": data.demo_week(),
        "demo_recommendations": data.demo_recommendations(),
        "demo_backtest": data.demo_backtest(),
        "demo_classifier": without(data.demo_classifier(), "model", "fitted"),
        "demo_plan_with_risk": data.demo_plan_with_risk(),
        "forecaster_explanations_demo": explanations,
        "source_tests_demo": data.source_tests("demo"),
        "demo_dashboard": demo_dashboard(),
    }
    path = save(results)
    print(f"Saved {len(results)} results to {path.relative_to(ROOT)} ({path.stat().st_size / 1e6:.1f} MB) "
          f"in {time.time() - start:.0f} s")


if __name__ == "__main__":
    main()
