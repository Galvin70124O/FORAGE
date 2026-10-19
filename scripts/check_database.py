"""Smoke-test the configured database: tables, per-user isolation, cleanup. Never prints the URL.

Usage (from the project root):
    python scripts/check_database.py                    # [connections.sql] in .streamlit/secrets.toml
    python scripts/check_database.py --secrets path/to/secrets.toml
    FORAGE_DATABASE_URL=... python scripts/check_database.py

Creates two throwaway users (forage-check-<random>@example.invalid), checks that neither can read, change
or delete the other's rows, then deletes both. Exits non-zero on any failure.
"""

import argparse
import os
import sys
import tomllib
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import create_engine, inspect  # noqa: E402

from store import NotFound, Store, normalise_database_url  # noqa: E402


def database_url(secrets_path: Path) -> str:
    if os.environ.get("FORAGE_DATABASE_URL"):
        return os.environ["FORAGE_DATABASE_URL"]
    if secrets_path.exists():
        url = tomllib.loads(secrets_path.read_text(encoding="utf-8")).get("connections", {}).get("sql", {}).get("url")
        if url:
            return url
    sys.exit("No database configured ([connections.sql] url or FORAGE_DATABASE_URL).")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--secrets", type=Path, default=ROOT / ".streamlit" / "secrets.toml")
    args = parser.parse_args()
    engine = create_engine(normalise_database_url(database_url(args.secrets)), pool_pre_ping=True)
    store = Store(engine)
    store.create_tables()
    print(f"database: {engine.dialect.name}; tables: {', '.join(sorted(inspect(engine).get_table_names()))}")
    tag = uuid.uuid4().hex[:10]
    alice = store.user_id_for(f"forage-check-a-{tag}@example.invalid", "Check A")
    bob = store.user_id_for(f"forage-check-b-{tag}@example.invalid", "Check B")
    failures = []
    try:
        store.add_purchase(alice, "2026-01-01", "Milk", 2, "L", 120, category="Dairy", shelf_life_days=5)
        store.add_check(alice, "2026-01-03", "Milk", 0.5, 0.25)
        purchase = int(store.purchases(alice)["id"].iloc[0])
        check = int(store.checks(alice)["id"].iloc[0])
        if not store.purchases(bob).empty or not store.checks(bob).empty or not store.foods(bob).empty:
            failures.append("user B can read user A's rows")
        for name, call in (("update purchase", lambda: store.update_purchase(bob, purchase, quantity=9)),
                           ("delete purchase", lambda: store.delete_purchase(bob, purchase)),
                           ("update check", lambda: store.update_check(bob, check, remaining=9)),
                           ("delete check", lambda: store.delete_check(bob, check))):
            try:
                call()
                failures.append(f"user B could {name} for user A")
            except NotFound:
                pass
        if store.purchases(alice)["quantity"].tolist() != [2.0]:
            failures.append("user A's purchase changed")
    finally:
        store.delete_user(alice)
        store.delete_user(bob)
    if failures:
        print("FAILED: " + "; ".join(failures))
        sys.exit(1)
    print("OK: per-user isolation holds for read, update and delete; test users removed")


if __name__ == "__main__":
    main()
