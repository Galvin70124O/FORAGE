"""Create FORAGE's tables in the configured database. Safe to run more than once.

Usage (from the project root):
    python scripts/init_db.py                 # uses [connections.sql] url in .streamlit/secrets.toml
    FORAGE_DATABASE_URL=... python scripts/init_db.py

The connection string is never printed.
"""

import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy import create_engine, inspect  # noqa: E402

from store import Store, normalise_database_url  # noqa: E402


def database_url() -> str:
    if os.environ.get("FORAGE_DATABASE_URL"):
        return os.environ["FORAGE_DATABASE_URL"]
    secrets = ROOT / ".streamlit" / "secrets.toml"
    if secrets.exists():
        url = tomllib.loads(secrets.read_text(encoding="utf-8")).get("connections", {}).get("sql", {}).get("url")
        if url:
            return url
    sys.exit("No database configured: set [connections.sql] url in .streamlit/secrets.toml "
             "or the FORAGE_DATABASE_URL environment variable.")


def main() -> None:
    engine = create_engine(normalise_database_url(database_url()), pool_pre_ping=True)
    Store(engine).create_tables()
    tables = sorted(inspect(engine).get_table_names())
    print(f"OK: {engine.dialect.name} database has tables: {', '.join(tables)}")


if __name__ == "__main__":
    main()
