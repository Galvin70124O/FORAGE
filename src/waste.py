"""Waste and expiry analysis for sources that record waste (demo data and My Data).

Definitions used throughout FORAGE:

* Stock balance per record: purchased = consumed + wasted + remaining.
  My Data is built from purchases and pantry checks, so its balance includes
  the stock carried over from the previous check (an `Opening_Stock` column):
  opening + purchased = consumed + wasted + remaining.
  Waste is the recorded `Quantity_Wasted`; it is never derived as
  purchased - consumed, because that would count unused stock as waste.
* Waste rate of a food = total wasted / total purchased for that food (x100).
  Quantities are only summed within a food, so units never mix.
* Category and overall waste rates are the unweighted mean of the food-level
  rates, so a food sold in kilograms does not outweigh one sold in dozens.
* Shelf life = `Expiry_Days` at purchase (days from purchase to expiry).

M5 and Instacart do not record waste, stock or expiry; every function here
raises `WasteNotSupported` for frames without the required columns.
"""

from __future__ import annotations

import pandas as pd

BALANCE_TOLERANCE = 0.011  # quantities are rounded to 2 dp in the source
SHORT_SHELF_LIFE_DAYS = 7
WASTE_COLUMNS = {"Food", "Quantity_Purchased", "Quantity_Wasted"}


class WasteNotSupported(ValueError):
    """Raised when a source has no recorded waste (for example M5 or Instacart)."""


def require_waste_columns(df: pd.DataFrame, extra: set[str] = frozenset()) -> None:
    missing = (WASTE_COLUMNS | set(extra)) - set(df.columns)
    if missing:
        raise WasteNotSupported(f"Waste analysis needs recorded waste; missing columns: {sorted(missing)}")


def is_stock_flow(df: pd.DataFrame) -> bool:
    """True for My Data periods, whose stock carries over from one pantry check to the next."""
    return "Opening_Stock" in df.columns


def balance_residual(df: pd.DataFrame) -> pd.Series:
    """(opening +) purchased - consumed - wasted - remaining per record; 0 when balanced.

    For stock-flow logs the opening stock is the previous day's remaining; it is
    unknown on a food's first logged day, so that day is not checked (NaN).
    """
    require_waste_columns(df, {"Quantity_Consumed", "Remaining_Quantity"})
    opening = df["Opening_Stock"] if is_stock_flow(df) else 0
    return (opening + df["Quantity_Purchased"] - df["Quantity_Consumed"]
            - df["Quantity_Wasted"] - df["Remaining_Quantity"])


def balance_check(df: pd.DataFrame, tolerance: float = BALANCE_TOLERANCE) -> dict:
    """How many records satisfy the stock balance within rounding tolerance."""
    residual = balance_residual(df).dropna()
    failing = int((residual.abs() > tolerance).sum())
    return {"checked": int(residual.size), "failing": failing,
            "max_abs_residual": float(residual.abs().max()) if residual.size else 0.0}


def _rate(wasted: pd.Series, purchased: pd.Series) -> pd.Series:
    """Waste % with zero purchases treated as undefined (NaN), never as 0% or infinity."""
    return wasted / purchased.where(purchased > 0) * 100


def food_waste(df: pd.DataFrame) -> pd.DataFrame:
    """Per-food purchased, wasted, waste rate and shelf life, highest rate first."""
    require_waste_columns(df)
    keys = ["Food"] + [c for c in ("Category", "Quantity_Unit") if c in df]
    table = df.groupby(keys, dropna=False).agg(
        Purchased=("Quantity_Purchased", "sum"),
        Wasted=("Quantity_Wasted", "sum"),
        Records=("Quantity_Wasted", "size"),
    )
    if "Expiry_Days" in df:
        table["Shelf_Life_Days"] = df.groupby(keys, dropna=False)["Expiry_Days"].median()
    table["Waste_Rate"] = _rate(table["Wasted"], table["Purchased"])
    return table.reset_index().sort_values("Waste_Rate", ascending=False, na_position="last").reset_index(drop=True)


def category_waste(df: pd.DataFrame) -> pd.DataFrame:
    """Per-category mean of food-level waste rates, plus the number of foods."""
    foods = food_waste(df)
    if "Category" not in foods:
        raise WasteNotSupported("Category waste needs a Category column.")
    return (foods.groupby("Category")
            .agg(Waste_Rate=("Waste_Rate", "mean"), Foods=("Food", "nunique"))
            .sort_values("Waste_Rate", ascending=False))


def overall_waste(df: pd.DataFrame) -> dict:
    """Headline waste figures. `rate` is the mean food-level rate; `pooled_rate` sums all units."""
    foods = food_waste(df)
    purchased = df["Quantity_Purchased"].sum()
    return {
        "rate": float(foods["Waste_Rate"].mean()),
        "pooled_rate": float(df["Quantity_Wasted"].sum() / purchased * 100) if purchased > 0 else float("nan"),
        "records": int(len(df)),
    }


def waste_vs_shelf_life(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Food-level waste rate against shelf life, with the Pearson r across foods."""
    require_waste_columns(df, {"Expiry_Days"})
    foods = food_waste(df).dropna(subset=["Waste_Rate", "Shelf_Life_Days"])
    r = foods["Waste_Rate"].corr(foods["Shelf_Life_Days"]) if len(foods) > 2 else float("nan")
    return foods, float(r)


def perishable_waste_by_category(df: pd.DataFrame, max_shelf_life: int = SHORT_SHELF_LIFE_DAYS) -> pd.DataFrame:
    """Waste rate of short-shelf-life foods (expiry within `max_shelf_life` days), by category.

    The source does not record why food was thrown away, so waste on foods
    that expire within a week is used as the expiry-driven share.
    """
    require_waste_columns(df, {"Expiry_Days", "Category"})
    perishable = df[df["Expiry_Days"] <= max_shelf_life]
    if perishable.empty:
        return pd.DataFrame(columns=["Waste_Rate", "Foods", "Food_List"])
    foods = food_waste(perishable)
    return (foods.groupby("Category")
            .agg(Waste_Rate=("Waste_Rate", "mean"), Foods=("Food", "nunique"),
                 Food_List=("Food", lambda names: ", ".join(sorted(names))))
            .sort_values("Waste_Rate", ascending=False))


def expiring_stock(df: pd.DataFrame, as_of: pd.Timestamp, within_days: int) -> pd.DataFrame:
    """Remaining stock whose estimated expiry falls in [as_of, as_of + within_days].

    Batches already past expiry are excluded (they are waste, not a warning),
    as are batches with no remaining quantity or no expiry date. (My Data uses
    pantry.stock_batches instead, because its stock carries over between checks.)
    """
    require_waste_columns(df, {"Remaining_Quantity", "Estimated_Expiry_Date"})
    as_of = pd.Timestamp(as_of).normalize()
    expiry = pd.to_datetime(df["Estimated_Expiry_Date"], errors="coerce")
    days_left = (expiry - as_of).dt.days
    mask = (df["Remaining_Quantity"] > 0) & days_left.between(0, within_days)
    batches = df.loc[mask].assign(Days_Left=days_left[mask], Expiry=expiry[mask])
    keys = ["Food"] + [c for c in ("Category", "Quantity_Unit") if c in df]
    if batches.empty:
        return pd.DataFrame(columns=keys + ["Remaining", "Batches", "Earliest_Expiry", "Days_Left"])
    return (batches.groupby(keys, dropna=False)
            .agg(Remaining=("Remaining_Quantity", "sum"), Batches=("Remaining_Quantity", "size"),
                 Earliest_Expiry=("Expiry", "min"), Days_Left=("Days_Left", "min"))
            .reset_index().sort_values(["Days_Left", "Remaining"], ascending=[True, False])
            .reset_index(drop=True))
