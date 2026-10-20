"""The published M5 / Instacart results (data/public/): present, small, aggregate-only, and enough for every page."""

import hashlib
import json
from pathlib import Path

import pandas as pd
import pytest

import public_data
from hypothesis import chi_square, welch_t

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "data" / "public"
RESULTS = ROOT / "outputs" / "results.json"
FORBIDDEN_COLUMNS = {"User_ID", "Order_ID", "Add_To_Cart_Order", "Order_Number"}


@pytest.mark.parametrize("name", ["m5", "instacart"])
def test_manifest_lists_every_file_with_matching_hash(name):
    manifest = public_data.manifest(name)
    assert manifest is not None, f"run scripts/build_public_artifacts.py ({name})"
    assert {"source", "licence", "attribution", "built", "files"} <= set(manifest)
    on_disk = {p.name for p in (PUBLIC / name).iterdir()} - {"manifest.json"}
    assert on_disk == set(manifest["files"])
    for file, info in manifest["files"].items():
        assert hashlib.sha256((PUBLIC / name / file).read_bytes()).hexdigest() == info["sha256"], file
        if info["rows"] is not None:
            assert len(pd.read_csv(PUBLIC / name / file)) == info["rows"], file


def test_public_folder_is_small():
    total = sum(p.stat().st_size for p in PUBLIC.rglob("*") if p.is_file())
    assert total < 10_000_000


def test_instacart_files_have_no_ids_or_order_rows():
    manifest = public_data.manifest("instacart")
    for file, info in manifest["files"].items():
        if file.endswith(".csv"):
            assert not FORBIDDEN_COLUMNS & set(info["columns"]), file
            assert info["rows"] < 5_000, f"{file} looks row-level"


def test_m5_item_day_is_daily_totals_per_item():
    item_day = public_data.read_table("m5", "item_day")
    assert not item_day.duplicated(["Date", "Product_ID"]).any()
    assert item_day["Product_ID"].nunique() == 100


def test_test_results_round_trip():
    a, b = pd.Series([1.0, 2.0, 3.0, 4.0]), pd.Series([2.0, 3.0, 4.0, 6.0])
    results = [welch_t(a, b, question="q", h0="h0", h1="h1"),
               chi_square(pd.Series(list("aabbab")), pd.Series(list("xyxyyy")), question="q", h0="h0", h1="h1")]
    back = public_data.tests_from_frame(public_data.tests_frame(results))
    assert [r.statistic for r in back] == pytest.approx([r.statistic for r in results])
    assert back[0].extra["mean_a"] == pytest.approx(2.5)
    assert isinstance(back[1].extra["table"], pd.DataFrame)


def test_rules_round_trip():
    rules = pd.DataFrame({"If": ["A + B"], "Then": ["C"], "Support": [0.1], "Confidence": [0.5], "Lift": [2.0],
                          "Antecedents": [frozenset({"A", "B"})], "Consequents": [frozenset({"C"})]})
    back = public_data.rules_from_frame(public_data.rules_frame(rules))
    assert back.loc[0, "Antecedents"] == frozenset({"A", "B"})


@pytest.fixture
def public_only(monkeypatch):
    """The app as it runs online: raw extracts ignored, data/public/ only."""
    import streamlit as st
    monkeypatch.setenv("FORAGE_PUBLIC_ONLY", "1")
    st.cache_data.clear()
    st.cache_resource.clear()
    yield
    st.cache_data.clear()
    st.cache_resource.clear()


def test_public_only_mode_ignores_raw_files(public_only):
    from services import data
    assert not data.has_raw("m5") and not data.has_raw("instacart")
    assert data.offline("m5") and data.offline("instacart")
    assert len(data.load_m5()) == public_data.manifest("m5")["files"]["item_day.csv"]["rows"]


@pytest.mark.skipif(not RESULTS.exists(), reason="outputs/results.json is git-ignored; run scripts/export_results.py")
def test_published_numbers_match_results_json(public_only):
    from services import data
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    if "m5" in results["forecasting"]:
        expected = results["forecasting"]["m5"]
        per_fold, rolling = data.m5_rolling()
        assert rolling.iloc[0]["Model"] == expected["next_day_selected"]
        for row, want in zip(rolling.to_dict("records"), expected["next_day_rolling"]):
            assert row["MAE_mean"] == pytest.approx(want["MAE_mean"], abs=1e-4)
        assert data.m5_week()["best"] == expected["seven_day_selected"]
        tests = {t.name: t.statistic for t in data.source_tests("m5")}
        for want in results["hypothesis_tests"]["m5"]:
            assert tests[want["test"]] == pytest.approx(want["statistic"], abs=1e-3)
    if "association_rules" in results:
        (orders, _), rules = data.instacart_rules()
        assert orders == results["association_rules"]["orders_used"]
        assert len(rules) == results["association_rules"]["rules_found"]
        summary = data.instacart_summary()
        assert summary.values["order_lines"] == results["datasets"]["instacart_order_lines"]
        assert summary.values["orders"] == results["datasets"]["instacart_orders"]
        chi = data.source_tests("instacart")[0]
        assert chi.statistic == pytest.approx(results["hypothesis_tests"]["instacart"][0]["statistic"], abs=1e-3)


PAGES = ["views/overview.py", "views/data_quality.py", "views/eda.py", "views/waste.py", "views/forecasting.py",
         "views/recommendations.py"]


@pytest.mark.parametrize("source", ["m5", "instacart"])
def test_every_insights_page_renders_from_public_results(public_only, source):
    from streamlit.testing.v1 import AppTest
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    app.session_state["source"] = source
    app.run()
    for page in PAGES:
        app.switch_page(page).run()
        assert not app.exception, f"{source} {page}: {[e.value for e in app.exception]}"
        text = " ".join(m.value for m in app.markdown) + " ".join(c.value for c in app.caption)
        assert "local version" not in text
        assert "computed offline" in text.lower() or "Computed offline" in text, f"{source} {page}: no offline note"
