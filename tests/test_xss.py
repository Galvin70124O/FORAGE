"""User text (food names, categories, CSV and bill text) shown through raw HTML must render as text, never as markup."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from ui import components, kitchen  # noqa: E402

FOOD = "<img src=x onerror=alert(1)>"


def assert_text_only(html: str) -> None:
    assert "<img" not in html and "&lt;img src=x onerror=alert(1)&gt;" in html


def capture(monkeypatch, module) -> list[str]:
    """Collect what `module` sends to st.html / st.markdown instead of rendering it."""
    sent = []
    monkeypatch.setattr(module.st, "html", lambda body, **_: sent.append(body))
    monkeypatch.setattr(module.st, "markdown", lambda body, **_: sent.append(body))
    return sent


def test_card_builders_escape_food_names():
    assert_text_only(components.jar(FOOD, FOOD, 2))
    assert_text_only(components.demand_card(FOOD, FOOD, FOOD, stamp="more", note=FOOD))
    assert_text_only(components.label_card(FOOD, FOOD, compare=FOOD, help=FOOD))


def test_shelf_and_label_row_escape_food_names(monkeypatch):
    sent = capture(monkeypatch, components)
    components.shelf(FOOD, [{"name": FOOD, "quantity": FOOD, "days_left": 1}], note=FOOD)
    components.kpi_row([(FOOD, FOOD, FOOD)])
    components.chips([(FOOD, FOOD)])
    assert len(sent) == 3
    for html in sent:
        assert_text_only(html)


def test_home_messages_escape_food_names(monkeypatch):
    sent = capture(monkeypatch, kitchen)
    kitchen.message_list([(f"Use {FOOD} first", FOOD, FOOD)])
    kitchen.message(FOOD)
    assert len(sent) == 2
    for html in sent:
        assert_text_only(html)
