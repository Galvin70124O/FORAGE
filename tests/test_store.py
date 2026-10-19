"""The data-access module: per-user isolation, idempotent setup, retries, imports; and identity rules."""

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError

from identity import LOCAL_EMAIL, mode, resolve_identity
from store import NotFound, Store


@pytest.fixture
def store():
    s = Store(create_engine("sqlite://"), retry_wait=0)
    s.create_tables()
    return s


@pytest.fixture
def two_users(store):
    alice = store.user_id_for("alice@example.com", "Alice")
    bob = store.user_id_for("bob@example.com", "Bob")
    store.add_purchase(alice, "2026-03-01", "Milk", 2, "L", 120, category="Dairy", shelf_life_days=5)
    store.add_check(alice, "2026-03-04", "Milk", remaining=0.5, wasted=0.25)
    store.add_purchase(bob, "2026-03-01", "Rice", 5, "kg", 350)
    return alice, bob


def test_create_tables_is_idempotent(store):
    store.create_tables()
    store.create_tables()
    assert store.foods(store.user_id_for("a@b.c")).empty


def test_user_ids_are_stable_and_case_insensitive(store):
    first = store.user_id_for("Alice@Example.com", "Alice")
    assert store.user_id_for("alice@example.com") == first
    assert store.user_id_for("bob@example.com") != first


def test_users_only_read_their_own_rows(store, two_users):
    alice, bob = two_users
    assert store.purchases(alice)["food"].tolist() == ["Milk"]
    assert store.purchases(bob)["food"].tolist() == ["Rice"]
    assert store.checks(bob).empty and len(store.checks(alice)) == 1
    assert store.foods(bob)["name"].tolist() == ["Rice"]


def test_users_cannot_change_or_delete_each_others_rows(store, two_users):
    alice, bob = two_users
    alice_purchase = int(store.purchases(alice)["id"].iloc[0])
    alice_check = int(store.checks(alice)["id"].iloc[0])
    with pytest.raises(NotFound):
        store.update_purchase(bob, alice_purchase, quantity=99)
    with pytest.raises(NotFound):
        store.delete_purchase(bob, alice_purchase)
    with pytest.raises(NotFound):
        store.update_check(bob, alice_check, remaining=9)
    with pytest.raises(NotFound):
        store.delete_check(bob, alice_check)
    alice_food = int(store.foods(alice)["id"].iloc[0])
    with pytest.raises(NotFound):
        store.update_food(bob, alice_food, category="Hacked")
    assert store.purchases(alice)["quantity"].tolist() == [2]
    assert store.foods(alice)["category"].tolist() == ["Dairy"]


def test_same_food_name_is_separate_per_user(store, two_users):
    alice, bob = two_users
    store.add_purchase(bob, "2026-03-02", "milk", 1, "L", 60, category="Bob's dairy")
    assert store.foods(alice).set_index("name").loc["Milk", "category"] == "Dairy"
    assert store.foods(bob).set_index("name").loc["milk", "category"] == "Bob's dairy"


def test_food_names_match_regardless_of_case_and_spacing(store):
    user = store.user_id_for("c@d.e")
    store.add_purchase(user, "2026-03-01", "Brown  Bread", 1, "loaf", 45)
    store.add_purchase(user, "2026-03-03", " brown bread ", 1, "loaf", 45)
    assert len(store.foods(user)) == 1 and len(store.purchases(user)) == 2


def test_validation_rejects_impossible_values(store):
    user = store.user_id_for("v@x.y")
    with pytest.raises(ValueError):
        store.add_purchase(user, "2026-03-01", "Milk", 0)
    with pytest.raises(ValueError):
        store.add_check(user, "2026-03-01", "Milk", remaining=-1)
    with pytest.raises(ValueError):
        store.add_purchase(user, "2026-03-01", "  ", 1)


def test_one_check_per_food_per_day_is_updated_not_duplicated(store):
    user = store.user_id_for("p@q.r")
    store.add_check(user, "2026-03-01", "Milk", 1.0, 0)
    store.add_check(user, "2026-03-01", "milk", 0.5, 0.2)
    checks = store.checks(user)
    assert len(checks) == 1 and checks.iloc[0]["remaining"] == 0.5


def test_imports_skip_rows_already_present(store):
    user = store.user_id_for("i@j.k")
    rows = pd.DataFrame({"date": ["2026-03-01", "2026-03-02"], "food": ["Milk", "Eggs"],
                         "quantity": [2, 12], "unit": ["L", "piece"], "total_price": [120, 84]})
    assert store.import_purchases(user, rows) == (2, 0)
    assert store.import_purchases(user, rows) == (0, 2)
    checks = pd.DataFrame({"date": ["2026-03-05"], "food": ["milk"], "remaining": [0.5], "wasted": [0.0]})
    assert store.import_checks(user, checks) == (1, 0)
    assert store.import_checks(user, checks) == (0, 1)


def test_settings_are_per_user(store, two_users):
    alice, bob = two_users
    store.set_setting(alice, "week_start", "Monday")
    store.set_setting(alice, "week_start", "Sunday")
    assert store.get_setting(alice, "week_start") == "Sunday"
    assert store.get_setting(bob, "week_start", "unset") == "unset"


def test_a_dropped_connection_is_retried_once(store, monkeypatch):
    user = store.user_id_for("r@s.t")
    calls = {"n": 0}
    real_connect = store.engine.connect

    def flaky_connect():
        calls["n"] += 1
        if calls["n"] == 1:
            raise OperationalError("SELECT 1", {}, Exception("server closed the connection"))
        return real_connect()

    monkeypatch.setattr(store.engine, "connect", flaky_connect)
    assert store.foods(user).empty and calls["n"] == 2


AUTH = {"auth": {"client_id": "x", "client_secret": "y", "redirect_uri": "z", "cookie_secret": "c",
                 "server_metadata_url": "m"}}
SQL = {"connections": {"sql": {"url": "postgresql+psycopg://example"}}}


def test_local_user_is_impossible_when_auth_is_configured():
    assert resolve_identity(AUTH, None) is None
    assert resolve_identity(AUTH, {"is_logged_in": False}) is None
    assert resolve_identity({**AUTH, **SQL}, {"is_logged_in": True}) is None  # logged in but no email
    signed_in = resolve_identity(AUTH, {"is_logged_in": True, "email": "A@B.com", "name": "A"})
    assert signed_in.email == "a@b.com" and not signed_in.local and signed_in.email != LOCAL_EMAIL


def test_local_user_only_without_auth_and_modes():
    assert resolve_identity({}, None).local
    assert resolve_identity(SQL, None).local
    assert mode({}) == "single_user" and mode(SQL) == "single_user"
    assert mode({**AUTH, **SQL}) == "online" and mode(AUTH) == "misconfigured"


def test_database_urls_get_the_psycopg_driver():
    from store import normalise_database_url
    assert normalise_database_url("postgresql://u:p@h/db?sslmode=require").startswith("postgresql+psycopg://u:p@h/db")
    assert normalise_database_url("postgres://u@h/db").startswith("postgresql+psycopg://")
    assert normalise_database_url("sqlite:///x.db") == "sqlite:///x.db"
