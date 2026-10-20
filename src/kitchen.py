"""Kitchen mode logic: everyday amounts, pantry levels, repeat purchases and the shareable shopping list.

Pure functions (no Streamlit) so they are unit-tested. Quantities are always
stored in the food's base unit (kg, L, dozen, ...); these helpers translate
between that and what people say in a kitchen ("½ kg", "1 litre", "2 packets").
"""

from __future__ import annotations

import math
from urllib.parse import quote

import pandas as pd

UNITS = ["kg", "g", "L", "ml", "piece", "dozen", "loaf", "pack", "bunch", "unit"]
CATEGORIES = ["Dairy", "Vegetables", "Fruits", "Grains", "Pulses", "Bakery", "Protein", "Snacks", "Essentials", "Other"]

# Everyday choices per base unit: (label, quantity in the base unit).
PRESETS = {
    "kg": [("250 g", 0.25), ("½ kg", 0.5), ("1 kg", 1.0), ("2 kg", 2.0), ("5 kg", 5.0)],
    "g": [("100 g", 100.0), ("200 g", 200.0), ("250 g", 250.0), ("500 g", 500.0), ("1 kg", 1000.0)],
    "L": [("½ litre", 0.5), ("1 litre", 1.0), ("2 litres", 2.0), ("5 litres", 5.0)],
    "ml": [("200 ml", 200.0), ("500 ml", 500.0), ("1 litre", 1000.0)],
    "piece": [("1 piece", 1.0), ("2 pieces", 2.0), ("4 pieces", 4.0), ("6 pieces", 6.0), ("12 pieces", 12.0)],
    "dozen": [("½ dozen", 0.5), ("1 dozen", 1.0), ("2 dozen", 2.0)],
    "loaf": [("1 loaf", 1.0), ("2 loaves", 2.0)],
    "pack": [("1 packet", 1.0), ("2 packets", 2.0), ("3 packets", 3.0), ("5 packets", 5.0)],
    "bunch": [("1 bunch", 1.0), ("2 bunches", 2.0), ("3 bunches", 3.0)],
    "unit": [("1", 1.0), ("2", 2.0), ("3", 3.0), ("5", 5.0)],
}

# Sensible defaults for common foods: (unit, category, days it usually stays good).
COMMON_FOODS = {
    "milk": ("L", "Dairy", 3), "curd": ("kg", "Dairy", 5), "paneer": ("g", "Dairy", 5), "butter": ("g", "Dairy", 30),
    "cheese": ("g", "Dairy", 20), "eggs": ("dozen", "Protein", 21), "egg": ("dozen", "Protein", 21),
    "bread": ("loaf", "Bakery", 5), "rice": ("kg", "Grains", 180), "atta": ("kg", "Grains", 90),
    "wheat flour": ("kg", "Grains", 90), "oats": ("pack", "Grains", 180), "dal": ("kg", "Pulses", 180),
    "sugar": ("kg", "Essentials", 365), "salt": ("kg", "Essentials", 365), "cooking oil": ("L", "Essentials", 180),
    "oil": ("L", "Essentials", 180), "tea": ("g", "Essentials", 180), "onion": ("kg", "Vegetables", 30),
    "potato": ("kg", "Vegetables", 30), "tomato": ("kg", "Vegetables", 7), "spinach": ("bunch", "Vegetables", 3),
    "coriander": ("bunch", "Vegetables", 4), "carrot": ("kg", "Vegetables", 14), "banana": ("dozen", "Fruits", 5),
    "apple": ("kg", "Fruits", 21), "orange": ("kg", "Fruits", 14), "chicken": ("kg", "Protein", 2),
    "fish": ("kg", "Protein", 2), "biscuit": ("pack", "Snacks", 90),
}
STARTER_FOODS = ["Milk", "Bread", "Eggs", "Rice", "Onion", "Tomato", "Potato", "Banana", "Curd"]

# Pantry check: how full the food is, as a share of what was available.
LEVELS = {"full": 1.0, "half": 0.5, "almost_empty": 0.1, "finished": 0.0}
WASTE_LEVELS = {"nothing": 0.0, "a_little": 0.1, "about_half": 0.5}


def guess(food: str) -> tuple[str, str, int]:
    """(unit, category, shelf-life days) for a new food; a neutral default for anything unknown."""
    return COMMON_FOODS.get(" ".join(str(food).lower().split()), ("unit", "Other", 7))


def presets(unit: str | None) -> list[tuple[str, float]]:
    return PRESETS.get(unit or "unit", PRESETS["unit"])


def preset_for(unit: str | None, quantity: float | None) -> str | None:
    """The everyday label matching a stored quantity exactly, if there is one."""
    if quantity is None or pd.isna(quantity):
        return None
    return next((label for label, value in presets(unit) if math.isclose(value, float(quantity))), None)


def _fraction(value: float) -> str:
    """1.5 -> '1½', 0.5 -> '½', 2.0 -> '2', 0.25 -> '¼', 0.75 -> '¾'."""
    whole, part = divmod(round(value * 4) / 4, 1)
    tail = {0.25: "¼", 0.5: "½", 0.75: "¾"}.get(round(part, 2), "")
    return (f"{int(whole)}" if whole or not tail else "") + tail


def _plural(count: float, one: str, many: str) -> str:
    return one if count <= 1 else many


def everyday_amount(quantity: float, unit: str | None) -> tuple[str, float]:
    """Round a needed quantity UP to an amount you can buy, as (label, quantity in the base unit)."""
    quantity = max(float(quantity), 0.0)
    unit = unit or "unit"
    if unit in ("kg", "L"):
        word, small = ("kg", "g") if unit == "kg" else ("litre", "ml")
        if quantity <= 0.75:
            rounded = max(math.ceil(quantity * 4 - 1e-9) / 4, 0.25)
            label = "½ kg" if unit == "kg" and rounded == 0.5 else "½ litre" if rounded == 0.5 else \
                f"{rounded * 1000:.0f} {small}"
            return label, rounded
        rounded = math.ceil(quantity * 2 - 1e-9) / 2
        name = word if unit == "kg" else _plural(rounded, "litre", "litres")
        return f"{_fraction(rounded)} {name}", rounded
    if unit in ("g", "ml"):
        if quantity >= 1000:
            return everyday_amount(quantity / 1000, "kg" if unit == "g" else "L")[0], math.ceil(quantity / 500 - 1e-9) * 500
        rounded = max(math.ceil(quantity / 50 - 1e-9) * 50, 50)
        return f"{rounded:.0f} {unit}", float(rounded)
    if unit == "dozen":
        rounded = max(math.ceil(quantity * 2 - 1e-9) / 2, 0.5)
        return f"{_fraction(rounded)} dozen", rounded
    rounded = float(max(math.ceil(quantity - 1e-9), 1))
    names = {"piece": ("piece", "pieces"), "loaf": ("loaf", "loaves"), "pack": ("packet", "packets"),
             "bunch": ("bunch", "bunches")}
    if unit in names:
        return f"{rounded:.0f} {_plural(rounded, *names[unit])}", rounded
    return f"{rounded:.0f}", rounded


def amount_text(quantity: float, unit: str | None) -> str:
    """A stored amount in words, without rounding up (for 'you should have about ...')."""
    quantity = float(quantity)
    if unit in ("kg", "L") and quantity < 1:
        return f"{quantity * 1000:.0f} {'g' if unit == 'kg' else 'ml'}"
    shown = _fraction(quantity) if abs(quantity * 4 - round(quantity * 4)) < 1e-6 else f"{quantity:.2f}".rstrip("0").rstrip(".")
    return f"{shown} {unit or ''}".strip()


def pantry_amounts(available: float, level: str, waste: str = "nothing") -> tuple[float, float]:
    """(left, thrown away) from a level button: waste is taken first, the level applies to what remained."""
    available = max(float(available), 0.0)
    wasted = round(WASTE_LEVELS[waste] * available, 3)
    left = round(LEVELS[level] * (available - wasted), 3)
    return left, wasted


def last_purchase(purchases: pd.DataFrame) -> pd.Series | None:
    if purchases.empty:
        return None
    return purchases.sort_values(["date", "id"]).iloc[-1]


def last_week(purchases: pd.DataFrame, today) -> pd.DataFrame:
    """Purchases from the 7 days before today, to repeat as today's shop."""
    if purchases.empty:
        return purchases
    today = pd.Timestamp(today).normalize()
    window = purchases[(purchases["date"] >= today - pd.Timedelta(days=7)) & (purchases["date"] < today)]
    return window.sort_values(["date", "id"])


def frequent_foods(purchases: pd.DataFrame, n: int = 9) -> list[str]:
    """Most often bought first (ties: most recent first); starter foods before anything is logged."""
    if purchases.empty:
        return STARTER_FOODS[:n]
    stats = purchases.groupby("food").agg(times=("id", "size"), last=("date", "max"))
    return stats.sort_values(["times", "last"], ascending=False).head(n).index.tolist()


def shopping_items(plan: pd.DataFrame) -> tuple[list[tuple[str, str]], list[str]]:
    """([(food, everyday amount)], [foods you have enough of]) from pantry.buy_list."""
    to_buy = plan[plan["Buy"] > 0].sort_values("Food")
    items = [(row.Food, everyday_amount(row.Buy, row.Unit)[0]) for row in to_buy.itertuples()]
    enough = plan[(plan["Buy"] <= 0) & (plan["Need"] > 0)]["Food"].sort_values().tolist()
    return items, enough


def share_text(title: str, items: list[tuple[str, str]]) -> str:
    return "\n".join([title, *[f"- {food}: {amount}" for food, amount in items]])


def whatsapp_link(text: str) -> str:
    return "https://wa.me/?text=" + quote(text)


def default_mode(signed_in: bool) -> str:
    """Signed-in people land in the Kitchen; visitors (and the viva demo) land on Project insights."""
    return "kitchen" if signed_in else "insights"


def round_rupees(value: float) -> int:
    """'About ₹450': round to the nearest ₹10 (₹50 above ₹1,000)."""
    step = 50 if value >= 1000 else 10
    return int(round(value / step) * step)
