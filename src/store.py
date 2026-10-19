"""The only module that reads or writes personal data.

Every query is filtered by `user_id`: there is no function that returns or
changes another user's rows, and no SQL is written anywhere else in FORAGE.
The same code runs on Neon Postgres (online) and SQLite (offline/dev), because
it only uses SQLAlchemy Core.

Data model (one row per event, consumption is derived later):
    users          one row per signed-in email
    foods          a user's foods with default category, unit and shelf life
    purchases      "I bought": date, food, quantity, unit, total price paid
    pantry_checks  "Pantry check": date, food, quantity remaining, quantity wasted
    settings       per-user key/value preferences
"""

from __future__ import annotations

import re
import time
from datetime import date as Date, datetime, timezone
from functools import wraps

import pandas as pd
from sqlalchemy import (
    Column,
    DateTime,
    Index,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    and_,
    delete,
    func,
    insert,
    select,
    update,
)
from sqlalchemy import Date as SqlDate
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError, OperationalError

metadata = MetaData()


def _now() -> datetime:
    return datetime.now(timezone.utc)


users = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("email", String(320), nullable=False, unique=True),
    Column("name", String(200)),
    Column("created_at", DateTime(timezone=True), default=_now),
)
foods = Table(
    "foods", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("name", String(120), nullable=False),
    Column("name_key", String(120), nullable=False),
    Column("category", String(80)),
    Column("unit", String(20)),
    Column("shelf_life_days", Integer),
    Column("created_at", DateTime(timezone=True), default=_now),
    UniqueConstraint("user_id", "name_key", name="uq_foods_user_name"),
)
purchases = Table(
    "purchases", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("food_id", Integer, ForeignKey("foods.id", ondelete="CASCADE"), nullable=False),
    Column("date", SqlDate, nullable=False),
    Column("quantity", Float, nullable=False),
    Column("unit", String(20)),
    Column("total_price", Float),
    Column("created_at", DateTime(timezone=True), default=_now),
)
pantry_checks = Table(
    "pantry_checks", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("food_id", Integer, ForeignKey("foods.id", ondelete="CASCADE"), nullable=False),
    Column("date", SqlDate, nullable=False),
    Column("remaining", Float, nullable=False),
    Column("wasted", Float, nullable=False, default=0.0),
    Column("created_at", DateTime(timezone=True), default=_now),
    UniqueConstraint("user_id", "food_id", "date", name="uq_checks_user_food_date"),
)
settings = Table(
    "settings", metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("key", String(80), primary_key=True),
    Column("value", Text),
)

# Every personal query filters by user and usually sorts by date.
INDEXES = [
    Index("ix_purchases_user_date", purchases.c.user_id, purchases.c.date),
    Index("ix_pantry_checks_user_date", pantry_checks.c.user_id, pantry_checks.c.date),
    Index("ix_foods_user", foods.c.user_id),
]

PURCHASE_COLUMNS = ["id", "date", "food", "category", "quantity", "unit", "total_price", "shelf_life_days"]
CHECK_COLUMNS = ["id", "date", "food", "category", "unit", "remaining", "wasted", "shelf_life_days"]


class NotFound(LookupError):
    """The row does not exist for this user (it may belong to someone else)."""


def name_key(name: str) -> str:
    return re.sub(r"\s+", " ", str(name).strip()).lower()


def clean_name(name: str) -> str:
    text = re.sub(r"\s+", " ", str(name).strip())
    if not text:
        raise ValueError("A food name is required.")
    return text


def with_retry(method):
    """Retry once after a short wait if the connection drops (e.g. a Neon cold start)."""
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except (OperationalError, DBAPIError) as error:
            if isinstance(error, DBAPIError) and not getattr(error, "connection_invalidated", False) \
                    and not isinstance(error, OperationalError):
                raise
            time.sleep(self.retry_wait)
            return method(self, *args, **kwargs)
    return wrapper


def _as_date(value) -> Date:
    return pd.Timestamp(value).date()


class Store:
    def __init__(self, engine: Engine, *, retry_wait: float = 1.5):
        self.engine = engine
        self.retry_wait = retry_wait

    # schema -----------------------------------------------------------------
    def create_tables(self) -> None:
        """Create any missing tables; safe to run any number of times."""
        metadata.create_all(self.engine, checkfirst=True)  # CREATE TABLE IF NOT EXISTS
        for index in INDEXES:  # also add indexes to tables created by an older version
            index.create(self.engine, checkfirst=True)

    # users ------------------------------------------------------------------
    @with_retry
    def user_id_for(self, email: str, name: str | None = None) -> int:
        """The id for this email, creating the user on first sign-in."""
        email = str(email).strip().lower()
        if not email:
            raise ValueError("An email is required to identify the user.")
        with self.engine.begin() as conn:
            found = conn.execute(select(users.c.id).where(users.c.email == email)).scalar()
            if found is not None:
                if name:
                    conn.execute(update(users).where(users.c.id == found).values(name=name))
                return int(found)
            return int(conn.execute(insert(users).values(email=email, name=name)).inserted_primary_key[0])

    # foods ------------------------------------------------------------------
    @with_retry
    def foods(self, user_id: int) -> pd.DataFrame:
        with self.engine.connect() as conn:
            rows = conn.execute(select(foods.c.id, foods.c.name, foods.c.category, foods.c.unit,
                                       foods.c.shelf_life_days)
                                .where(foods.c.user_id == user_id).order_by(foods.c.name)).mappings().all()
        return pd.DataFrame(rows, columns=["id", "name", "category", "unit", "shelf_life_days"])

    def _food_id(self, conn, user_id: int, name: str, category=None, unit=None, shelf_life_days=None) -> int:
        """This user's food id for `name` (case/spacing-insensitive), creating it if new.

        Defaults (category, unit, shelf life) fill gaps but never overwrite
        values the user already set.
        """
        key = name_key(name)
        row = conn.execute(select(foods).where(and_(foods.c.user_id == user_id, foods.c.name_key == key))).mappings().first()
        if row is None:
            return int(conn.execute(insert(foods).values(
                user_id=user_id, name=clean_name(name), name_key=key, category=category or None,
                unit=unit or None, shelf_life_days=None if shelf_life_days is None else int(shelf_life_days),
            )).inserted_primary_key[0])
        fills = {k: v for k, v in {"category": category, "unit": unit, "shelf_life_days": shelf_life_days}.items()
                 if v not in (None, "") and row[k] in (None, "")}
        if fills:
            conn.execute(update(foods).where(foods.c.id == row["id"]).values(**fills))
        return int(row["id"])

    @with_retry
    def update_food(self, user_id: int, food_id: int, **fields) -> None:
        allowed = {k: v for k, v in fields.items() if k in {"category", "unit", "shelf_life_days"}}
        if "name" in fields:
            allowed.update(name=clean_name(fields["name"]), name_key=name_key(fields["name"]))
        with self.engine.begin() as conn:
            result = conn.execute(update(foods).where(and_(foods.c.id == food_id, foods.c.user_id == user_id))
                                  .values(**allowed))
        if result.rowcount == 0:
            raise NotFound(f"Food {food_id} not found.")

    # purchases --------------------------------------------------------------
    @with_retry
    def add_purchase(self, user_id: int, date, food: str, quantity: float, unit: str | None = None,
                     total_price: float | None = None, *, category: str | None = None,
                     shelf_life_days: int | None = None) -> int:
        if quantity is None or float(quantity) <= 0:
            raise ValueError("Quantity bought must be greater than 0.")
        if total_price is not None and float(total_price) < 0:
            raise ValueError("Price cannot be negative.")
        with self.engine.begin() as conn:
            food_id = self._food_id(conn, user_id, food, category, unit, shelf_life_days)
            return int(conn.execute(insert(purchases).values(
                user_id=user_id, food_id=food_id, date=_as_date(date), quantity=float(quantity), unit=unit,
                total_price=None if total_price in (None, "") else float(total_price),
            )).inserted_primary_key[0])

    @with_retry
    def purchases(self, user_id: int) -> pd.DataFrame:
        query = (select(purchases.c.id, purchases.c.date, foods.c.name.label("food"), foods.c.category,
                        purchases.c.quantity, func.coalesce(purchases.c.unit, foods.c.unit).label("unit"),
                        purchases.c.total_price, foods.c.shelf_life_days)
                 .join(foods, foods.c.id == purchases.c.food_id)
                 .where(and_(purchases.c.user_id == user_id, foods.c.user_id == user_id))
                 .order_by(purchases.c.date, foods.c.name, purchases.c.id))
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        frame = pd.DataFrame(rows, columns=PURCHASE_COLUMNS)
        frame["date"] = pd.to_datetime(frame["date"])
        return frame

    @with_retry
    def update_purchase(self, user_id: int, purchase_id: int, **fields) -> None:
        values = {k: v for k, v in fields.items() if k in {"quantity", "unit", "total_price"}}
        if "date" in fields:
            values["date"] = _as_date(fields["date"])
        if "quantity" in values and float(values["quantity"]) <= 0:
            raise ValueError("Quantity bought must be greater than 0.")
        with self.engine.begin() as conn:
            if "food" in fields:
                values["food_id"] = self._food_id(conn, user_id, fields["food"])
            result = conn.execute(update(purchases)
                                  .where(and_(purchases.c.id == purchase_id, purchases.c.user_id == user_id))
                                  .values(**values))
        if result.rowcount == 0:
            raise NotFound(f"Purchase {purchase_id} not found.")

    @with_retry
    def delete_purchase(self, user_id: int, purchase_id: int) -> None:
        with self.engine.begin() as conn:
            result = conn.execute(delete(purchases).where(and_(purchases.c.id == purchase_id,
                                                               purchases.c.user_id == user_id)))
        if result.rowcount == 0:
            raise NotFound(f"Purchase {purchase_id} not found.")

    # pantry checks ----------------------------------------------------------
    @with_retry
    def add_check(self, user_id: int, date, food: str, remaining: float, wasted: float = 0.0) -> int:
        """Record what is left (and what was thrown away) for a food; one check per food per day."""
        if remaining is None or float(remaining) < 0 or float(wasted or 0) < 0:
            raise ValueError("Remaining and wasted quantities cannot be negative.")
        with self.engine.begin() as conn:
            food_id = self._food_id(conn, user_id, food)
            day = _as_date(date)
            existing = conn.execute(select(pantry_checks.c.id).where(and_(
                pantry_checks.c.user_id == user_id, pantry_checks.c.food_id == food_id,
                pantry_checks.c.date == day))).scalar()
            values = dict(remaining=float(remaining), wasted=float(wasted or 0))
            if existing is not None:
                conn.execute(update(pantry_checks).where(pantry_checks.c.id == existing).values(**values))
                return int(existing)
            return int(conn.execute(insert(pantry_checks).values(
                user_id=user_id, food_id=food_id, date=day, **values)).inserted_primary_key[0])

    @with_retry
    def checks(self, user_id: int) -> pd.DataFrame:
        query = (select(pantry_checks.c.id, pantry_checks.c.date, foods.c.name.label("food"), foods.c.category,
                        foods.c.unit, pantry_checks.c.remaining, pantry_checks.c.wasted, foods.c.shelf_life_days)
                 .join(foods, foods.c.id == pantry_checks.c.food_id)
                 .where(and_(pantry_checks.c.user_id == user_id, foods.c.user_id == user_id))
                 .order_by(pantry_checks.c.date, foods.c.name))
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        frame = pd.DataFrame(rows, columns=CHECK_COLUMNS)
        frame["date"] = pd.to_datetime(frame["date"])
        return frame

    @with_retry
    def update_check(self, user_id: int, check_id: int, **fields) -> None:
        values = {k: float(v) for k, v in fields.items() if k in {"remaining", "wasted"}}
        if "date" in fields:
            values["date"] = _as_date(fields["date"])
        if any(v < 0 for k, v in values.items() if k != "date"):
            raise ValueError("Remaining and wasted quantities cannot be negative.")
        with self.engine.begin() as conn:
            result = conn.execute(update(pantry_checks)
                                  .where(and_(pantry_checks.c.id == check_id, pantry_checks.c.user_id == user_id))
                                  .values(**values))
        if result.rowcount == 0:
            raise NotFound(f"Pantry check {check_id} not found.")

    @with_retry
    def delete_check(self, user_id: int, check_id: int) -> None:
        with self.engine.begin() as conn:
            result = conn.execute(delete(pantry_checks).where(and_(pantry_checks.c.id == check_id,
                                                                   pantry_checks.c.user_id == user_id)))
        if result.rowcount == 0:
            raise NotFound(f"Pantry check {check_id} not found.")

    # bulk import with de-duplication -----------------------------------------
    def import_purchases(self, user_id: int, rows: pd.DataFrame) -> tuple[int, int]:
        """Add purchases not already present (same date, food, quantity and price). Returns (added, skipped)."""
        existing = self.purchases(user_id)
        seen = {(d.date(), name_key(f), round(float(q), 3), None if pd.isna(p) else round(float(p), 2))
                for d, f, q, p in zip(existing["date"], existing["food"], existing["quantity"], existing["total_price"])}
        added = skipped = 0
        for row in rows.to_dict("records"):
            price = row.get("total_price")
            price = None if price is None or pd.isna(price) else round(float(price), 2)
            key = (_as_date(row["date"]), name_key(row["food"]), round(float(row["quantity"]), 3), price)
            if key in seen:
                skipped += 1
                continue
            self.add_purchase(user_id, row["date"], row["food"], row["quantity"], row.get("unit"), price,
                              category=row.get("category"), shelf_life_days=row.get("shelf_life_days"))
            seen.add(key)
            added += 1
        return added, skipped

    def import_checks(self, user_id: int, rows: pd.DataFrame) -> tuple[int, int]:
        """Add pantry checks for (date, food) pairs not already checked. Returns (added, skipped)."""
        existing = self.checks(user_id)
        seen = {(d.date(), name_key(f)) for d, f in zip(existing["date"], existing["food"])}
        added = skipped = 0
        for row in rows.to_dict("records"):
            key = (_as_date(row["date"]), name_key(row["food"]))
            if key in seen:
                skipped += 1
                continue
            self.add_check(user_id, row["date"], row["food"], row["remaining"], row.get("wasted") or 0)
            seen.add(key)
            added += 1
        return added, skipped

    @with_retry
    def delete_user(self, user_id: int) -> None:
        """Remove a user and every row they own (explicit deletes, so it works on SQLite and Postgres)."""
        with self.engine.begin() as conn:
            for table in (pantry_checks, purchases, settings, foods):
                conn.execute(delete(table).where(table.c.user_id == user_id))
            conn.execute(delete(users).where(users.c.id == user_id))

    # settings ---------------------------------------------------------------
    @with_retry
    def get_setting(self, user_id: int, key: str, default: str | None = None) -> str | None:
        with self.engine.connect() as conn:
            value = conn.execute(select(settings.c.value).where(and_(settings.c.user_id == user_id,
                                                                     settings.c.key == key))).scalar()
        return default if value is None else value

    @with_retry
    def set_setting(self, user_id: int, key: str, value: str) -> None:
        with self.engine.begin() as conn:
            updated = conn.execute(update(settings).where(and_(settings.c.user_id == user_id, settings.c.key == key))
                                   .values(value=value)).rowcount
            if not updated:
                conn.execute(insert(settings).values(user_id=user_id, key=key, value=value))


def normalise_database_url(url: str) -> str:
    """Use the psycopg 3 driver for Postgres URLs given in Neon's default form (postgresql://...)."""
    url = str(url).strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url
