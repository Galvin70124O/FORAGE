"""Kitchen mode: everyday amounts, pantry levels, repeat purchases, the share text, translations and the pages."""

from pathlib import Path

import pandas as pd
import pytest

import kitchen
from i18n import LANGUAGES, STRINGS, placeholders, translate

ROOT = Path(__file__).resolve().parent.parent


# --- everyday amounts ------------------------------------------------------------
@pytest.mark.parametrize("quantity, unit, label, rounded", [
    (0.2, "kg", "250 g", 0.25), (0.4, "kg", "½ kg", 0.5), (0.7, "kg", "750 g", 0.75), (1.0, "kg", "1 kg", 1.0),
    (1.2, "kg", "1½ kg", 1.5), (0.3, "L", "½ litre", 0.5), (1.6, "L", "2 litres", 2.0), (1.0, "L", "1 litre", 1.0),
    (120, "g", "150 g", 150.0), (1300, "g", "1½ kg", 1500.0), (0.3, "dozen", "½ dozen", 0.5),
    (1.1, "dozen", "1½ dozen", 1.5), (2.3, "loaf", "3 loaves", 3.0), (0.6, "pack", "1 packet", 1.0),
    (2.0, "piece", "2 pieces", 2.0), (1.0, "bunch", "1 bunch", 1.0), (2.2, None, "3", 3.0),
])
def test_everyday_amount_rounds_up_to_something_you_can_buy(quantity, unit, label, rounded):
    assert kitchen.everyday_amount(quantity, unit) == (label, rounded)


def test_everyday_amount_never_rounds_down():
    for unit in kitchen.PRESETS:
        for quantity in (0.01, 0.33, 0.9, 1.01, 2.6, 7.3):
            assert kitchen.everyday_amount(quantity, unit)[1] >= quantity - 1e-9


def test_presets_map_to_base_units():
    assert dict(kitchen.presets("kg"))["½ kg"] == 0.5
    assert dict(kitchen.presets("g"))["1 kg"] == 1000
    assert dict(kitchen.presets("L"))["1 litre"] == 1
    assert dict(kitchen.presets("pack"))["1 packet"] == 1
    assert kitchen.presets("made-up unit") == kitchen.PRESETS["unit"]
    assert kitchen.preset_for("kg", 0.5) == "½ kg"
    assert kitchen.preset_for("kg", 0.3) is None


def test_guess_for_new_foods():
    assert kitchen.guess("  Milk ") == ("L", "Dairy", 3)
    assert kitchen.guess("Wheat  flour") == ("kg", "Grains", 90)
    assert kitchen.guess("Dragon fruit") == ("unit", "Other", 7)


# --- pantry levels -----------------------------------------------------------------
@pytest.mark.parametrize("level, waste, expected", [
    ("full", "nothing", (2.0, 0.0)), ("half", "nothing", (1.0, 0.0)), ("almost_empty", "nothing", (0.2, 0.0)),
    ("finished", "nothing", (0.0, 0.0)), ("half", "about_half", (0.5, 1.0)), ("finished", "a_little", (0.0, 0.2)),
])
def test_pantry_levels_are_shares_of_what_was_available(level, waste, expected):
    left, wasted = kitchen.pantry_amounts(2.0, level, waste)
    assert (left, wasted) == pytest.approx(expected)
    assert left + wasted <= 2.0 + 1e-9


# --- repeat purchases and the shopping list ------------------------------------------
@pytest.fixture
def buys():
    return pd.DataFrame({"id": [1, 2, 3, 4], "food": ["Milk", "Rice", "Milk", "Eggs"],
                         "date": pd.to_datetime(["2026-10-01", "2026-10-12", "2026-10-15", "2026-10-20"]),
                         "quantity": [1.0, 5.0, 1.0, 1.0], "unit": ["L", "kg", "L", "dozen"],
                         "total_price": [60.0, 400.0, 62.0, None]})


def test_last_purchase_and_last_week(buys):
    assert kitchen.last_purchase(buys)["food"] == "Eggs"
    week = kitchen.last_week(buys, "2026-10-20")
    assert week["food"].tolist() == ["Milk"]  # 13 Oct–19 Oct: today's eggs and older rice are left out
    assert kitchen.last_week(buys.iloc[0:0], "2026-10-20").empty


def test_frequent_foods(buys):
    assert kitchen.frequent_foods(buys)[0] == "Milk"
    assert kitchen.frequent_foods(buys.iloc[0:0]) == kitchen.STARTER_FOODS


def test_shopping_items_and_share_text():
    plan = pd.DataFrame({"Food": ["Rice", "Milk", "Salt"], "Unit": ["kg", "L", "kg"],
                         "Need": [1.2, 3.5, 0.1], "Usable_Stock": [0.0, 2.1, 0.5], "Buy": [1.2, 1.4, 0.0]})
    items, enough = kitchen.shopping_items(plan)
    assert items == [("Milk", "1½ litres"), ("Rice", "1½ kg")]
    assert enough == ["Salt"]
    text = kitchen.share_text("Shopping list (FORAGE)", items)
    assert text.splitlines() == ["Shopping list (FORAGE)", "- Milk: 1½ litres", "- Rice: 1½ kg"]
    assert kitchen.whatsapp_link(text).startswith("https://wa.me/?text=Shopping%20list")


def test_default_mode_and_rupee_rounding():
    assert kitchen.default_mode(True) == "kitchen"
    assert kitchen.default_mode(False) == "insights"
    assert kitchen.round_rupees(447) == 450
    assert kitchen.round_rupees(1234) == 1250


# --- translations ------------------------------------------------------------------------
def test_every_string_has_every_language_with_the_same_placeholders():
    for key, entry in STRINGS.items():
        assert set(entry) == set(LANGUAGES), key
        english = placeholders(entry["en"]) - {"s"}  # {s} is the English plural ending only
        for lang, text in entry.items():
            assert text.strip(), (key, lang)
            assert placeholders(text) - {"s"} == english, (key, lang)


def test_translate_fills_placeholders_and_falls_back_to_english():
    assert translate("use_today", "en", food="spinach") == "Use the spinach today."
    assert "spinach" in translate("use_today", "ta", food="spinach")
    assert translate("wasted_month", "hi", amount="450").startswith("इस महीने लगभग ₹450")
    assert translate("nav_home", "xx") == "Home"


def test_kitchen_text_has_no_jargon():
    banned = ("WAPE", "MAE", "RMSE", "p-value", "synthetic", "Random Forest", "Linear Regression", "classifier")
    for key, entry in STRINGS.items():
        for word in banned:
            assert word.lower() not in entry["en"].lower(), (key, word)


# --- pages (single local user, temporary database) ----------------------------------------
@pytest.fixture
def local_app(tmp_path, monkeypatch):
    """The app in single-user mode (no sign-in, no database) with its SQLite file in a temporary folder."""
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    from services import session
    monkeypatch.setattr(session, "LOCAL_DB", tmp_path / "forage_test.db")
    st.cache_data.clear()
    st.cache_resource.clear()
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    app.secrets["FORAGE_TEST"] = "1"  # replaces .streamlit/secrets.toml: no [auth], no [connections.sql]
    yield app
    st.cache_data.clear()
    st.cache_resource.clear()


def _store():
    from services import session
    return session._store(False)


def _fresh_reads():
    """Rows written straight to the store bypass the app's 60-second read cache; clear it like a save does."""
    from services.personal import _read
    _read.clear()


def _button(app, label):
    return next(b for b in app.button if b.label == label)


def test_signed_in_users_land_in_the_kitchen_with_the_walkthrough(local_app):
    local_app.run()
    assert not local_app.exception
    assert local_app.session_state["app_mode"] == "kitchen"
    assert any("Step 1 of 3" in c.value for c in local_app.caption)
    _button(local_app, "Skip").click().run()
    assert not local_app.exception
    uid = local_app.session_state["user_id"]
    assert _store().get_setting(uid, "onboarded") == "1"
    assert not any("Step 1 of 3" in c.value for c in local_app.caption)


def test_log_a_purchase_with_a_tile_and_an_everyday_amount(local_app):
    local_app.session_state["onboarded"] = True
    local_app.run()
    local_app.switch_page("views/bought.py").run()
    _button(local_app, "Milk").click().run()
    assert not local_app.exception
    _button(local_app, "Save").click().run()
    assert not local_app.exception
    assert any("Saved: Milk, 1 litre" in s.value for s in local_app.success)
    buys = _store().purchases(local_app.session_state["user_id"])
    assert buys[["food", "quantity", "unit"]].values.tolist() == [["Milk", 1.0, "L"]]


def test_pantry_level_button_stores_the_remaining_quantity(local_app):
    local_app.session_state["onboarded"] = True
    local_app.run()
    uid = local_app.session_state["user_id"]
    _store().add_purchase(uid, pd.Timestamp.today().normalize() - pd.Timedelta(days=2), "Rice", 2.0, "kg", 200.0)
    _fresh_reads()
    local_app.switch_page("views/pantry.py").run()
    _button(local_app, "Rice").click().run()
    _button(local_app, "Half").click().run()
    assert not local_app.exception
    checks = _store().checks(uid)
    assert checks[["food", "remaining", "wasted"]].values.tolist() == [["Rice", 1.0, 0.0]]


@pytest.mark.parametrize("page", ["views/home.py", "views/bought.py", "views/pantry.py", "views/shopping.py",
                                  "views/my_data.py"])
@pytest.mark.parametrize("lang", list(LANGUAGES))
def test_kitchen_pages_render_in_every_language(local_app, page, lang):
    local_app.session_state["onboarded"] = True
    local_app.session_state["lang"] = lang
    local_app.run()
    uid = local_app.session_state["user_id"]
    today = pd.Timestamp.today().normalize()
    db = _store()
    if db.purchases(uid).empty:
        db.add_purchase(uid, today - pd.Timedelta(days=9), "Milk", 2.0, "L", 120.0)
        db.add_check(uid, today - pd.Timedelta(days=2), "Milk", 0.5, 0.25)
        db.add_purchase(uid, today - pd.Timedelta(days=1), "Milk", 1.0, "L", 60.0)
        _fresh_reads()
    local_app.switch_page(page).run()
    assert not local_app.exception, [e.value for e in local_app.exception]
    assert local_app.title[0].value == translate({"views/home.py": "nav_home", "views/bought.py": "nav_bought",
                                                   "views/pantry.py": "nav_pantry", "views/shopping.py": "nav_shopping",
                                                   "views/my_data.py": "nav_my_data"}[page], lang)


def test_mode_switch_is_remembered(local_app):
    local_app.session_state["onboarded"] = True
    local_app.run()
    _button(local_app, "Open Project insights").click().run()
    assert not local_app.exception
    assert local_app.session_state["app_mode"] == "insights"
    local_app.run()
    assert local_app.session_state["app_mode"] == "insights"
    _button(local_app, "Back to Kitchen").click().run()
    assert local_app.session_state["app_mode"] == "kitchen"
