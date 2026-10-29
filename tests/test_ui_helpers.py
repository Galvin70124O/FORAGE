"""Shared UI helpers that need no browser: table heights and number formats."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ui import components  # noqa: E402


@pytest.mark.parametrize("base, row", [(15, 33), (16, 35), (14, 31)])
def test_row_height_follows_the_base_font_size(monkeypatch, base, row):
    monkeypatch.setattr(components.st, "get_option", lambda name: base)
    assert components.row_px() == row


def test_fit_height_shows_whole_rows_only(monkeypatch):
    monkeypatch.setattr(components.st, "get_option", lambda name: 15)  # .streamlit/config.toml
    # header + rows, 33 px each, + 1 px border top and bottom: never a partial row
    assert components.fit_height(3) == 33 * 4 + 2
    assert components.fit_height(40, 10) == 33 * 11 + 2
    assert components.fit_height(4, 10) == components.fit_height(4)
    assert (components.fit_height(40, 10) - 2) % 33 == 0


# --- number formats --------------------------------------------------------------------
@pytest.mark.parametrize("value, unit, text", [
    (12.0, "piece", "12 pieces"), (200.0, "g", "200 g"), (0.5, "kg", "0.5 kg"), (1234.5, "g", "1,234.5 g"),
    (1.0, "loaf", "1 loaf"), (2.0, "loaf", "2 loaves"), (0.15000000000000002, "L", "0.15 L"), (2.0, None, "2"),
    (123456789.0, "g", "123,456,789 g"), (0.0, "kg", "0 kg"), (0.004, "kg", "<0.01 kg"), (float("nan"), "kg", "–"),
])
def test_quantities_drop_trailing_zeros_and_group_thousands(value, unit, text):
    assert components.fmt_qty(value, unit) == text


def test_tidy_numbers_only_drops_trailing_zeros():
    assert components.tidy_numbers("Use up 200.00 g of Paneer") == "Use up 200 g of Paneer"
    assert components.tidy_numbers("Buy no more than 1.20 kg") == "Buy no more than 1.2 kg"
    assert components.tidy_numbers("Use the 0.54 kg of Chicken") == "Use the 0.54 kg of Chicken"
    assert components.tidy_numbers("₹1,234.50 at 22.30%") == "₹1,234.5 at 22.3%"


def test_table_formats_group_thousands_like_the_kpi_cards():
    assert components.rupees("₹ wasted")["type_config"]["format"] == "₹%,.0f"
    assert components.count("Rows")["type_config"]["format"] == "%,d"
    assert components.quantity("Left")["type_config"]["format"] == "%,.6g"


# --- KPI change colours -------------------------------------------------------------------
@pytest.mark.parametrize("delta, delta_color, tone", [
    ("+₹623 vs last month", "off", "fs-flat"),          # Purchased / Consumed: neutral either way
    ("-₹1,294 vs last month", "off", "fs-flat"),
    ("+1.1 pts vs last month", "inverse", "fs-bad"),     # waste up is bad
    ("-2.5 pts vs last month", "inverse", "fs-good"),
    ("+0.0 pts vs last month", "inverse", "fs-flat"),    # no change is never coloured
    ("+₹0 vs last month", "inverse", "fs-flat"),
    ("+4.2 pts vs last month", "normal", "fs-good"),     # forecast accuracy up is good
])
def test_change_colour_follows_the_metric_not_the_direction(delta, delta_color, tone):
    assert components._change(delta, delta_color)[1] == tone


def test_pantry_labels_colour_spending_and_eating_neutral_and_waste_inverse():
    from services.pantry_view import label_items
    month = {"spent": 100.0, "eaten": 80.0, "lost": 20.0, "rate": 12.0, "rows": 3}
    items = label_items({"now": month, "before": dict(month, eaten=50.0, rate=10.0)}, illustrative=False)
    assert [item[4] for item in items] == ["off", "off", "inverse", "inverse"]
