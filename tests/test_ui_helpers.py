"""Shared UI helpers that need no browser: table heights."""

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
