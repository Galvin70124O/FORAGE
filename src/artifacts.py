"""Precomputed demo results: load them only if they were built from exactly this data, code and library versions.

The demo dataset is fixed and every demo result is deterministic, so the heavy
model runs (rolling backtests, classifiers, explanations) are computed once by
`scripts/precompute_demo.py` and committed as `data/precomputed/demo_results.pkl`
(tables only, no fitted models). The app loads them instantly on a cold start;
if the fingerprint does not match (data, model code or package versions changed)
it ignores the file and computes everything live. `tests/test_precomputed.py`
fails when the committed file is stale.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy
import pandas
import sklearn

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT = ROOT / "data" / "precomputed" / "demo_results.pkl"
INPUTS = [
    "data/raw_food_data.csv", "data/cleaned_food_data.csv",
    "src/prediction.py", "src/horizon.py", "src/waste_risk.py", "src/recommendations.py", "src/backtest.py",
    "src/explain.py", "src/waste.py", "src/clean_data.py", "src/hypothesis.py", "src/stats.py",
    "services/data.py", "services/overview.py",
]


def fingerprint() -> str:
    """SHA-256 of the inputs (line endings normalised, so Windows and Linux checkouts agree) and versions."""
    digest = hashlib.sha256()
    for relative in INPUTS:
        digest.update(relative.encode())
        digest.update((ROOT / relative).read_bytes().replace(b"\r\n", b"\n"))
    digest.update(f"pandas {pandas.__version__} numpy {numpy.__version__} sklearn {sklearn.__version__}".encode())
    return digest.hexdigest()


def load() -> dict | None:
    """The precomputed results, or None if absent, disabled (FORAGE_NO_PRECOMPUTED=1) or stale."""
    if os.environ.get("FORAGE_NO_PRECOMPUTED") == "1" or not ARTIFACT.exists():
        return None
    try:
        payload = pandas.read_pickle(ARTIFACT)
    except Exception:
        return None
    return payload["results"] if payload.get("fingerprint") == fingerprint() else None


def save(results: dict) -> Path:
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    pandas.to_pickle({"fingerprint": fingerprint(), "results": results}, ARTIFACT)
    return ARTIFACT
