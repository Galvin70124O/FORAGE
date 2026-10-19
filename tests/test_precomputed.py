"""The committed demo results must match the current data, model code and package versions."""

import artifacts

EXPECTED = {"demo_forecast", "demo_rolling", "demo_week", "demo_recommendations", "demo_backtest", "demo_classifier",
            "demo_plan_with_risk", "forecaster_explanations_demo", "source_tests_demo", "demo_dashboard"}


def test_committed_results_are_current():
    results = artifacts.load()
    assert results is not None, ("data/precomputed/demo_results.pkl is missing or stale: "
                                 "run `python scripts/precompute_demo.py` and commit it")
    assert EXPECTED <= set(results)
    assert "models" not in results["demo_forecast"] and "fitted" not in results["demo_classifier"]


def test_results_are_ignored_when_disabled(monkeypatch):
    monkeypatch.setenv("FORAGE_NO_PRECOMPUTED", "1")
    assert artifacts.load() is None


def test_fingerprint_changes_with_inputs_and_ignores_line_endings(tmp_path, monkeypatch):
    (tmp_path / "a.py").write_bytes(b"x = 1\n")
    monkeypatch.setattr(artifacts, "ROOT", tmp_path)
    monkeypatch.setattr(artifacts, "INPUTS", ["a.py"])
    first = artifacts.fingerprint()
    (tmp_path / "a.py").write_bytes(b"x = 1\r\n")
    assert artifacts.fingerprint() == first          # CRLF checkout on Windows, LF on Linux: same hash
    (tmp_path / "a.py").write_bytes(b"x = 2\n")
    assert artifacts.fingerprint() != first          # any real change invalidates the saved results
