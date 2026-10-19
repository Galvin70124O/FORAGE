"""Turn a user's purchases and pantry checks into analysable periods.

The user records two kinds of event:
    purchase      on a date, bought Q of a food for a total price
    pantry check  on a date, R of the food is left and W was thrown away

Consumption is never typed; it is derived for each period between two checks:

    consumed = previous remaining + purchased in the period - wasted - remaining now

A purchase dated on a check day counts towards that check (checks are taken at
the end of the day). A food's first period starts at its first purchase with an
opening stock of 0 (we assume none was on hand before logging began); if the
first event is a check, that check is only a baseline. A negative derived
consumption is impossible and is flagged, never silently corrected.

All functions are pure: DataFrames in, DataFrames out.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

TOLERANCE = 0.011
PERIOD_COLUMNS = ["Food", "Category", "Unit", "Period_Start", "Date", "Days", "Opening_Stock", "Purchased",
                  "Spent", "Wasted", "Remaining", "Consumed", "Shelf_Life_Days", "Impossible"]

# What each personal analysis needs before it is shown (B6), and when it becomes reliable.
UNLOCK = {
    "spending": {"needs": ("purchases", 1), "reliable": ("purchases", 1)},
    "waste": {"needs": ("periods", 1), "reliable": ("periods", 8)},
    "expiry": {"needs": ("purchases", 1), "reliable": ("purchases", 1)},
    "buy_list": {"needs": ("periods", 1), "reliable": ("weeks", 3)},
    "forecast": {"needs": ("weeks", 3), "reliable": ("periods", 20)},
    "tests": {"needs": ("periods", 12), "reliable": ("periods", 30)},
    "backtest": {"needs": ("weeks", 3), "reliable": ("weeks", 6)},
    "classifier": {"needs": ("purchases", 30), "reliable": ("purchases", 100)},
}


def _food_info(purchases: pd.DataFrame, checks: pd.DataFrame) -> pd.DataFrame:
    frames = [f[["food", "category", "unit", "shelf_life_days"]] for f in (purchases, checks) if not f.empty]
    if not frames:
        return pd.DataFrame(columns=["category", "unit", "shelf_life_days"])
    return pd.concat(frames).groupby("food").agg(
        category=("category", "first"), unit=("unit", "first"), shelf_life_days=("shelf_life_days", "first"))


def periods(purchases: pd.DataFrame, checks: pd.DataFrame) -> pd.DataFrame:
    """One row per food per period ending at a pantry check, with derived consumption."""
    rows = []
    info = _food_info(purchases, checks)
    for food in sorted(set(checks["food"]) if not checks.empty else set()):
        food_checks = checks[checks["food"] == food].sort_values("date")
        food_buys = purchases[purchases["food"] == food] if not purchases.empty else purchases
        first_buy = food_buys["date"].min() if not food_buys.empty else pd.NaT
        previous_date, previous_remaining = None, None
        for check in food_checks.itertuples():
            if previous_date is None:
                if pd.isna(first_buy) or first_buy > check.date:
                    previous_date, previous_remaining = check.date, check.remaining  # baseline check
                    continue
                start, opening = first_buy - pd.Timedelta(days=1), 0.0
            else:
                start, opening = previous_date, previous_remaining
            bought = food_buys[(food_buys["date"] > start) & (food_buys["date"] <= check.date)]
            purchased = float(bought["quantity"].sum())
            consumed = opening + purchased - check.wasted - check.remaining
            rows.append({
                "Food": food, "Category": info.at[food, "category"], "Unit": info.at[food, "unit"],
                "Period_Start": start + pd.Timedelta(days=1), "Date": check.date,
                "Days": max(int((check.date - start).days), 1), "Opening_Stock": opening, "Purchased": purchased,
                "Spent": float(bought["total_price"].sum(min_count=1)) if not bought.empty else np.nan,
                "Wasted": float(check.wasted), "Remaining": float(check.remaining),
                "Consumed": round(max(consumed, 0.0), 4), "Shelf_Life_Days": info.at[food, "shelf_life_days"],
                "Impossible": consumed < -TOLERANCE,
            })
            previous_date, previous_remaining = check.date, check.remaining
    frame = pd.DataFrame(rows, columns=PERIOD_COLUMNS)
    if not frame.empty:
        available = frame["Opening_Stock"] + frame["Purchased"]
        frame["Waste_Percentage"] = frame["Wasted"] / available.where(available > 0) * 100
        frame["Daily_Consumption"] = frame["Consumed"] / frame["Days"]
    return frame


def unit_prices(purchases: pd.DataFrame) -> pd.Series:
    """Median price per unit for each food: total price paid / quantity bought."""
    priced = purchases.dropna(subset=["total_price"])
    priced = priced[priced["quantity"] > 0]
    return (priced["total_price"] / priced["quantity"]).groupby(priced["food"]).median()


def analysis_frame(purchases: pd.DataFrame, checks: pd.DataFrame) -> pd.DataFrame:
    """Periods in the column names the Insights pages use (one row per food per period)."""
    table = periods(purchases, checks)
    if table.empty:
        return pd.DataFrame()
    prices = unit_prices(purchases)
    out = pd.DataFrame({
        "Date": table["Date"], "Period_Start": table["Period_Start"], "Days": table["Days"],
        "Food": table["Food"], "Category": table["Category"].fillna("Uncategorized"),
        "Quantity_Unit": table["Unit"].fillna("unit"), "Opening_Stock": table["Opening_Stock"],
        "Quantity_Purchased": table["Purchased"], "Quantity_Consumed": table["Consumed"],
        "Quantity_Wasted": table["Wasted"], "Remaining_Quantity": table["Remaining"], "Price": table["Spent"],
        "Expiry_Days": table["Shelf_Life_Days"], "Waste_Percentage": table["Waste_Percentage"],
        "Daily_Consumption": table["Daily_Consumption"], "Impossible": table["Impossible"],
        "Unit_Price": table["Food"].map(prices),
    })
    out["Consumption_Rate"] = out["Quantity_Consumed"] / (out["Opening_Stock"] + out["Quantity_Purchased"]).where(
        lambda s: s > 0)
    out["Day_of_Week"] = out["Date"].dt.day_name()
    out["Month"] = out["Date"].dt.month
    out["Is_Weekend"] = (out["Date"].dt.dayofweek >= 5).astype(int)
    return out.sort_values(["Date", "Food"]).reset_index(drop=True)


def consumption_rates(table: pd.DataFrame, last_n: int = 4) -> pd.Series:
    """Mean daily consumption per food over its last `last_n` periods (weighted by days)."""
    if table.empty:
        return pd.Series(dtype=float)
    recent = table[~table["Impossible"]].sort_values("Date").groupby("Food").tail(last_n)
    return recent.groupby("Food")["Consumed"].sum() / recent.groupby("Food")["Days"].sum()


def expected_stock(purchases: pd.DataFrame, checks: pd.DataFrame, as_of) -> pd.DataFrame:
    """What should still be on hand: last check + purchases since - estimated use since.

    Used to prefill the pantry check. Foods never checked start from 0 at their
    first purchase. Estimated use = recent daily rate x days since the last check
    (0 when no rate is known yet).
    """
    as_of = pd.Timestamp(as_of).normalize()
    rates = consumption_rates(periods(purchases, checks))
    info = _food_info(purchases, checks)
    rows = []
    for food in info.index:
        food_checks = checks[(checks["food"] == food) & (checks["date"] <= as_of)] if not checks.empty else checks
        if not food_checks.empty:
            last = food_checks.sort_values("date").iloc[-1]
            base_date, base = last["date"], float(last["remaining"])
        else:
            base_date, base = None, 0.0
        buys = purchases[(purchases["food"] == food) & (purchases["date"] <= as_of)] if not purchases.empty else purchases
        if base_date is not None:
            buys = buys[buys["date"] > base_date]
        bought = float(buys["quantity"].sum())
        since = base_date if base_date is not None else (buys["date"].min() if not buys.empty else as_of)
        days = max(int((as_of - since).days), 0) if pd.notna(since) else 0
        rate = float(rates.get(food, np.nan))
        used = rate * days if not np.isnan(rate) else 0.0
        rows.append({"Food": food, "Category": info.at[food, "category"], "Unit": info.at[food, "unit"],
                     "Last_Check": base_date, "Bought_Since": bought,
                     "Expected": round(max(base + bought - used, 0.0), 2), "Daily_Rate": rate,
                     "Shelf_Life_Days": info.at[food, "shelf_life_days"]})
    return pd.DataFrame(rows, columns=["Food", "Category", "Unit", "Last_Check", "Bought_Since", "Expected",
                                       "Daily_Rate", "Shelf_Life_Days"])


def stock_batches(purchases: pd.DataFrame, stock: pd.DataFrame) -> pd.DataFrame:
    """Split each food's expected stock into purchase batches, newest first (FIFO use leaves the newest).

    Each batch expires `shelf_life_days` after it was bought. Stock not covered
    by logged purchases has no known expiry and is left out.
    """
    rows = []
    for item in stock.itertuples():
        left = float(item.Expected)
        if left <= 0 or purchases.empty:
            continue
        buys = purchases[purchases["food"] == item.Food].sort_values("date", ascending=False)
        for buy in buys.itertuples():
            take = min(left, float(buy.quantity))
            shelf = buy.shelf_life_days if pd.notna(buy.shelf_life_days) else item.Shelf_Life_Days
            expiry = buy.date + pd.Timedelta(days=int(shelf)) if pd.notna(shelf) else pd.NaT
            rows.append({"Food": item.Food, "Unit": item.Unit, "Quantity": take, "Bought": buy.date,
                         "Expiry": expiry, "Daily_Rate": item.Daily_Rate,
                         "Unit_Price": buy.total_price / buy.quantity if pd.notna(buy.total_price) else np.nan})
            left -= take
            if left <= 1e-9:
                break
    return pd.DataFrame(rows, columns=["Food", "Unit", "Quantity", "Bought", "Expiry", "Daily_Rate", "Unit_Price"])


def expiring_soon(batches: pd.DataFrame, as_of, within_days: int = 3) -> pd.DataFrame:
    as_of = pd.Timestamp(as_of).normalize()
    days_left = (batches["Expiry"] - as_of).dt.days
    soon = batches[days_left.between(0, within_days)].assign(Days_Left=days_left)
    return soon.sort_values(["Days_Left", "Quantity"], ascending=[True, False]).reset_index(drop=True)


def likely_wasted(batches: pd.DataFrame, as_of) -> pd.DataFrame:
    """Stock that will expire before it is eaten at the food's recent daily rate (FIFO).

    Batches are eaten oldest first at `Daily_Rate`; whatever is left of a batch on
    its expiry date is predicted waste. Foods without a known rate are skipped.
    """
    as_of = pd.Timestamp(as_of).normalize()
    rows = []
    for food, group in batches.dropna(subset=["Expiry"]).groupby("Food"):
        rate = group["Daily_Rate"].iloc[0]
        if pd.isna(rate):
            continue
        day_cursor = 0.0  # days of eating already used by older batches
        for batch in group.sort_values("Expiry").itertuples():
            days_until_expiry = max((batch.Expiry - as_of).days, 0)
            can_eat = max(rate * (days_until_expiry - day_cursor), 0.0)
            eaten = min(batch.Quantity, can_eat)
            day_cursor += eaten / rate if rate > 0 else 0.0
            lost = batch.Quantity - eaten
            if lost > 1e-6:
                rows.append({"Food": food, "Unit": batch.Unit, "At_Risk": round(lost, 2), "Expiry": batch.Expiry,
                             "Value": lost * batch.Unit_Price if pd.notna(batch.Unit_Price) else np.nan})
    return pd.DataFrame(rows, columns=["Food", "Unit", "At_Risk", "Expiry", "Value"]).sort_values(
        "Expiry").reset_index(drop=True)


def buy_list(stock: pd.DataFrame, batches: pd.DataFrame, as_of, horizon_days: int = 7) -> pd.DataFrame:
    """What to buy for the next `horizon_days`: forecast use minus stock that will still be good.

    Forecast use = recent daily rate x horizon (the 4-period average baseline).
    Stock that expires before the end of the horizon only counts up to its expiry.
    """
    as_of = pd.Timestamp(as_of).normalize()
    rows = []
    for item in stock.dropna(subset=["Daily_Rate"]).itertuples():
        need = item.Daily_Rate * horizon_days
        usable = 0.0
        for batch in batches[batches["Food"] == item.Food].itertuples():
            days_good = horizon_days if pd.isna(batch.Expiry) else max(min((batch.Expiry - as_of).days, horizon_days), 0)
            usable += min(batch.Quantity, item.Daily_Rate * days_good)
        untracked = max(item.Expected - batches.loc[batches["Food"] == item.Food, "Quantity"].sum(), 0.0)
        usable = min(usable + untracked, item.Expected)
        rows.append({"Food": item.Food, "Unit": item.Unit, "Need": round(need, 2), "Usable_Stock": round(usable, 2),
                     "Buy": round(max(need - usable, 0.0), 2)})
    return pd.DataFrame(rows, columns=["Food", "Unit", "Need", "Usable_Stock", "Buy"]).sort_values(
        "Buy", ascending=False).reset_index(drop=True)


def wasted_value(table: pd.DataFrame) -> pd.Series:
    """₹ wasted per period: wasted quantity x the food's median price per unit."""
    return table["Quantity_Wasted"] * table["Unit_Price"]


def coverage(purchases: pd.DataFrame, checks: pd.DataFrame) -> dict:
    """Sample sizes used to unlock personal analyses (B6)."""
    table = periods(purchases, checks)
    dates = pd.concat([purchases["date"], checks["date"]]) if not (purchases.empty and checks.empty) else pd.Series(dtype="datetime64[ns]")
    span = int((dates.max() - dates.min()).days) + 1 if not dates.empty else 0
    return {"purchases": len(purchases), "checks": len(checks), "periods": len(table),
            "foods": int(table["Food"].nunique()) if not table.empty else 0, "days": span, "weeks": span // 7}


def unlocked(feature: str, cover: dict) -> tuple[bool, bool, str]:
    """(shown, reliable, note) for a personal analysis given the sample sizes."""
    rule = UNLOCK[feature]
    need_key, need = rule["needs"]
    good_key, good = rule["reliable"]
    have, have_good = cover.get(need_key, 0), cover.get(good_key, 0)
    if have < need:
        return False, False, f"Needs {need} {need_key.replace('_', ' ')}; you have {have}."
    reliable = have_good >= good
    note = f"Based on {cover.get('periods', 0)} periods, {cover.get('purchases', 0)} purchases, {cover.get('weeks', 0)} weeks"
    return True, reliable, note if reliable else f"{note}. Not reliable yet: needs at least {good} {good_key}."


# --- bill / grocery-order text ------------------------------------------------
UNIT_ALIASES = {
    "kg": "kg", "kgs": "kg", "kilo": "kg", "g": "g", "gm": "g", "gms": "g", "gram": "g", "grams": "g",
    "l": "L", "lt": "L", "ltr": "L", "litre": "L", "liter": "L", "ml": "ml", "pc": "piece", "pcs": "piece",
    "piece": "piece", "pieces": "piece", "nos": "piece", "dozen": "dozen", "dz": "dozen", "pack": "pack",
    "pkt": "pack", "packet": "pack", "loaf": "loaf",
}
_QTY_UNIT = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(" + "|".join(sorted(UNIT_ALIASES, key=len, reverse=True)) + r")\b", re.I)
_TIMES = re.compile(r"(?:\bx\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*x\b)", re.I)
_PRICE = re.compile(r"(?:₹|rs\.?|inr)?\s*(\d+(?:\.\d{1,2})?)\s*$", re.I)


def parse_bill(text: str) -> tuple[pd.DataFrame, list[str]]:
    """Parse lines like 'Milk 2 L 120', 'Eggs x12 84', 'Tomato 1kg - ₹40' into purchase rows.

    Rule-based, no guessing: a line needs a food name and a final price;
    quantity and unit are optional (default 1 unit). Returns (rows, lines that
    could not be read). The user confirms the rows before anything is saved.
    """
    rows, skipped = [], []
    for raw in str(text).splitlines():
        line = raw.strip().strip("-•*").strip()
        if not line:
            continue
        price_match = _PRICE.search(line)
        if not price_match:
            skipped.append(raw)
            continue
        price = float(price_match.group(1))
        rest = line[:price_match.start()].strip(" -:=@,")
        quantity, unit = 1.0, None
        unit_match = _QTY_UNIT.search(rest)
        if unit_match:
            quantity, unit = float(unit_match.group(1)), UNIT_ALIASES[unit_match.group(2).lower()]
            rest = (rest[:unit_match.start()] + rest[unit_match.end():]).strip()
        else:
            times = _TIMES.search(rest)
            if times:
                quantity, unit = float(times.group(1) or times.group(2)), "piece"
                rest = (rest[:times.start()] + rest[times.end():]).strip()
        food = re.sub(r"\s+", " ", re.sub(r"[^\w\s&'-]", " ", rest)).strip(" -")
        if not food or food.isdigit():
            skipped.append(raw)
            continue
        rows.append({"food": food.title() if food.islower() or food.isupper() else food,
                     "quantity": quantity, "unit": unit or "unit", "total_price": price})
    return pd.DataFrame(rows, columns=["food", "quantity", "unit", "total_price"]), skipped


# --- CSV import (in memory) ----------------------------------------------------
IMPORT_ALIASES = {
    "date": ["date", "purchase_date", "check_date", "day"],
    "food": ["food", "item", "item_name", "product", "name"],
    "category": ["category", "type"],
    "quantity": ["quantity", "qty", "purchased", "bought", "quantity_purchased"],
    "unit": ["unit", "units", "uom"],
    "total_price": ["total_price", "price", "amount", "cost", "total"],
    "shelf_life_days": ["shelf_life_days", "shelf_life", "expiry_days"],
    "remaining": ["remaining", "left", "remaining_quantity", "stock"],
    "wasted": ["wasted", "waste", "thrown_away", "quantity_wasted"],
}
PURCHASE_FIELDS = ["date", "food", "category", "quantity", "unit", "total_price", "shelf_life_days"]
CHECK_FIELDS = ["date", "food", "remaining", "wasted"]


def read_import(raw: pd.DataFrame) -> tuple[str | None, pd.DataFrame, dict]:
    """Recognise a purchases or pantry-check CSV, clean it, and report what was removed.

    Returns (kind, rows, report). kind is "purchases", "checks" or None when the
    file has neither a quantity nor a remaining column. Rows with a missing or
    unreadable date or food, or an impossible number, are removed and counted;
    nothing is filled in. Food names are unified for case and spacing.
    """
    from data_quality import normalise_names

    lookup = {re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_"): c for c in raw.columns}
    mapped = {}
    for field, aliases in IMPORT_ALIASES.items():
        for alias in aliases:
            if alias in lookup and lookup[alias] not in mapped.values():
                mapped[field] = lookup[alias]
                break
    kind = "checks" if "remaining" in mapped else "purchases" if "quantity" in mapped else None
    report = {"rows_in_file": len(raw), "mapped": mapped, "duplicates": 0, "missing_date_or_food": 0,
              "invalid_numbers": 0, "names_unified": 0}
    if kind is None or not {"date", "food"} <= set(mapped):
        return None, pd.DataFrame(), report
    fields = CHECK_FIELDS if kind == "checks" else PURCHASE_FIELDS
    rows = pd.DataFrame({f: raw[mapped[f]] if f in mapped else None for f in fields})
    before = len(rows)
    rows = rows.drop_duplicates()
    report["duplicates"] = before - len(rows)
    rows["date"] = pd.to_datetime(rows["date"], errors="coerce", dayfirst=False)
    rows["food"], changed = normalise_names(rows["food"].astype("string"))
    report["names_unified"] = int(changed.sum())
    missing = rows["date"].isna() | rows["food"].isna() | rows["food"].eq("")
    report["missing_date_or_food"] = int(missing.sum())
    rows = rows[~missing].copy()
    numeric = ["remaining", "wasted"] if kind == "checks" else ["quantity", "total_price", "shelf_life_days"]
    for column in numeric:
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
    if kind == "checks":
        rows["wasted"] = rows["wasted"].fillna(0)
        bad = rows["remaining"].isna() | (rows["remaining"] < 0) | (rows["wasted"] < 0)
    else:
        bad = rows["quantity"].isna() | (rows["quantity"] <= 0) | (rows["total_price"] < 0)
    report["invalid_numbers"] = int(bad.sum())
    return kind, rows[~bad].reset_index(drop=True), report


def period_forecast_evaluation(table: pd.DataFrame, window: int = 4) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Score period-level forecasts of daily consumption on each food's later periods.

    For every period after a food's first, two baselines predict its daily
    consumption from earlier periods only: the previous period's rate, and the
    mean rate of up to `window` previous periods (weighted by days). Returns
    (predictions, comparison with MAE/RMSE/R2 and the number of periods scored).
    """
    from prediction import evaluate_predictions

    rows = []
    usable = table[~table["Impossible"]].sort_values("Date")
    for food, history in usable.groupby("Food"):
        history = history.reset_index(drop=True)
        for i in range(1, len(history)):
            past = history.iloc[max(0, i - window):i]
            rows.append({"Food": food, "Date": history.loc[i, "Date"], "Actual": history.loc[i, "Daily_Consumption"],
                         "Previous period": history.loc[i - 1, "Daily_Consumption"],
                         f"{window}-period average": past["Consumed"].sum() / past["Days"].sum()})
    predictions = pd.DataFrame(rows)
    if predictions.empty:
        return predictions, pd.DataFrame(columns=["Model", "Type", "MAE", "RMSE", "R2", "n"])
    comparison = pd.DataFrame([{"Model": name, "Type": "Baseline", "n": len(predictions),
                                **evaluate_predictions(predictions["Actual"], predictions[name])}
                               for name in ("Previous period", f"{window}-period average")])
    return predictions, comparison.sort_values(["MAE", "RMSE"]).reset_index(drop=True)
