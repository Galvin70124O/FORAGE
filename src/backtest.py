"""Crude backtest: would a household that follows FORAGE waste less?

Two (or more) households are simulated under IDENTICAL rules over the same
days, for each food separately:

* every household eats exactly the recorded consumption of that day
  (the same demand for all of them);
* food is eaten first-in-first-out, oldest batch first;
* a batch bought on day b with shelf life s can be eaten on days b .. b+s-1
  and is thrown away at the start of day b+s (that is the only waste);
* each household starts with an empty pantry;
* a stock-out day is a day on which that day's demand could not be met.

Only the purchases differ:
    Recorded  buys what was actually bought on each day
    Daily     each day buys max(0, forecast for today - stock on hand)
    Weekly    every 7 days buys max(0, forecast for the next 7 days - stock on hand),
              but never more than can be eaten before it expires

Stock left at the end is neither waste nor consumption; it is reported
separately so the comparison is not flattered by an empty final pantry.
The recorded waste in the source data comes from a different process and is
shown only as a reference.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

EPS = 1e-9


@dataclass
class Outcome:
    purchased: float = 0.0
    eaten: float = 0.0
    wasted: float = 0.0
    unmet: float = 0.0
    stockout_days: int = 0
    leftover: float = 0.0

    @property
    def waste_pct(self) -> float:
        return self.wasted / self.purchased * 100 if self.purchased > EPS else float("nan")


def simulate(demand: list[float], shelf_life: int, policy) -> Outcome:
    """Run one food through the days. `policy(day, stock_on_hand)` returns the quantity bought that day."""
    batches: list[list[float]] = []  # [quantity, first day it is no longer edible]
    out = Outcome()
    for day, need in enumerate(demand):
        for batch in batches:  # expired stock is thrown away at the start of the day
            if batch[1] <= day and batch[0] > EPS:
                out.wasted += batch[0]
                batch[0] = 0.0
        on_hand = sum(b[0] for b in batches)
        bought = max(float(policy(day, on_hand)), 0.0)
        if bought > EPS:
            batches.append([bought, day + max(int(shelf_life), 1)])
            out.purchased += bought
        left_to_eat = float(need)
        for batch in batches:  # first in, first out
            take = min(batch[0], left_to_eat)
            batch[0] -= take
            left_to_eat -= take
            if left_to_eat <= EPS:
                break
        out.eaten += need - max(left_to_eat, 0.0)
        if left_to_eat > 1e-6:
            out.unmet += left_to_eat
            out.stockout_days += 1
    out.leftover = sum(b[0] for b in batches)
    return out


def recorded_policy(purchases: list[float]):
    return lambda day, on_hand: purchases[day]


def daily_policy(forecasts: list[float]):
    """Top stock up to today's forecast."""
    return lambda day, on_hand: max(forecasts[day] - on_hand, 0.0)


def weekly_policy(week_forecasts: list[float], shelf_life: int, every: int = 7):
    """Every `every` days, top stock up to the 7-day forecast, capped at what can be eaten before expiry."""
    def policy(day, on_hand):
        if day % every:
            return 0.0
        horizon = min(every, max(int(shelf_life), 1))
        target = week_forecasts[day] * horizon / every
        return max(target - on_hand, 0.0)
    return policy


def run_backtest(frame: pd.DataFrame, *, food: str = "Food", date: str = "Date", demand: str = "Demand",
                 bought: str = "Bought", forecast: str = "Forecast", week_forecast: str = "Week_Forecast",
                 shelf_life: str = "Shelf_Life", unit_price: str = "Unit_Price") -> pd.DataFrame:
    """Simulate every food under each policy; one row per food x policy.

    `frame` has one row per food per day over the test period, with the
    actual demand, the actual purchase, the one-step forecast for that day
    and the 7-day forecast made on that day (known at that day only).
    """
    rows = []
    for name, days in frame.sort_values(date).groupby(food):
        life = int(days[shelf_life].iloc[0])
        price = float(days[unit_price].iloc[0]) if unit_price in days else np.nan
        policies = {"Recorded": recorded_policy(days[bought].tolist()),
                    "FORAGE daily": daily_policy(days[forecast].tolist())}
        if week_forecast in days:
            policies["FORAGE weekly"] = weekly_policy(days[week_forecast].tolist(), life)
        for policy_name, policy in policies.items():
            result = simulate(days[demand].tolist(), life, policy)
            rows.append({"Food": name, "Policy": policy_name, "Days": len(days), "Shelf_Life": life,
                         "Purchased": result.purchased, "Eaten": result.eaten, "Wasted": result.wasted,
                         "Leftover": result.leftover, "Unmet": result.unmet,
                         "Stockout_Days": result.stockout_days, "Wasted_Rupees": result.wasted * price})
    return pd.DataFrame(rows)


def summarise(results: pd.DataFrame) -> pd.DataFrame:
    """Per policy: waste % (wasted ÷ purchased, mean of food-level rates), ₹ wasted, stock-out food-days
    and the share of total demand that went unmet."""
    per_food = results.assign(Waste_Pct=results["Wasted"] / results["Purchased"].where(results["Purchased"] > 0) * 100)
    summary = per_food.groupby("Policy", sort=False).agg(
        Waste_Pct=("Waste_Pct", "mean"), Wasted_Rupees=("Wasted_Rupees", "sum"), Purchased=("Purchased", "sum"),
        Stockout_Days=("Stockout_Days", "sum"), Food_Days=("Days", "sum"), Leftover=("Leftover", "sum"),
        Eaten=("Eaten", "sum"), Unmet=("Unmet", "sum"))
    summary["Stockout_Pct"] = summary["Stockout_Days"] / summary["Food_Days"] * 100
    summary["Unmet_Pct"] = summary["Unmet"] / (summary["Eaten"] + summary["Unmet"]) * 100
    return summary


def demo_frame(records: pd.DataFrame, tested: pd.DataFrame, model: str, week_forecasts: pd.Series | None = None,
               unit_prices: pd.Series | None = None) -> pd.DataFrame:
    """Backtest input for the demo data over the forecast test period.

    Demand and purchases are the recorded values; `Forecast` is `model`'s
    one-step prediction for the day. `Week_Forecast` is the 7-day forecast made
    on that day when given, otherwise 7 x the one-step forecast (both use only
    information available that day).
    """
    frame = tested[["Date", "Food", "Quantity_Consumed", model]].rename(
        columns={"Quantity_Consumed": "Demand", model: "Forecast"})
    frame["Forecast"] = frame["Forecast"].clip(lower=0)
    bought = records.set_index(["Date", "Food"])["Quantity_Purchased"]
    frame["Bought"] = [bought.get((d, f), 0.0) for d, f in zip(frame["Date"], frame["Food"])]
    frame["Shelf_Life"] = frame["Food"].map(records.groupby("Food")["Expiry_Days"].median())
    if unit_prices is not None:
        frame["Unit_Price"] = frame["Food"].map(unit_prices)
    if week_forecasts is not None:
        frame["Week_Forecast"] = [week_forecasts.get((d, f), np.nan) for d, f in zip(frame["Date"], frame["Food"])]
        frame["Week_Forecast"] = frame["Week_Forecast"].fillna(frame["Forecast"] * 7)
    else:
        frame["Week_Forecast"] = frame["Forecast"] * 7
    return frame


def personal_frame(purchases: pd.DataFrame, checks: pd.DataFrame, window: int = 4) -> pd.DataFrame:
    """Backtest input from a user's purchases and pantry checks.

    Daily demand is each period's derived consumption spread evenly over its
    days (pantry checks do not say on which day food was eaten). The forecast
    for a day is the average daily rate of up to `window` periods that ended
    before it, so days before a food's first completed period are not scored.
    """
    from pantry import periods

    table = periods(purchases, checks)
    rows = []
    for food, history in table[~table["Impossible"]].sort_values("Date").groupby("Food"):
        shelf = history["Shelf_Life_Days"].dropna()
        life = int(shelf.iloc[0]) if not shelf.empty else 7
        bought = purchases[purchases["food"] == food].groupby("date")["quantity"].sum()
        priced = purchases[(purchases["food"] == food) & purchases["total_price"].notna()]
        price = float((priced["total_price"] / priced["quantity"]).median()) if not priced.empty else np.nan
        for i, period in enumerate(history.itertuples()):
            past = history.iloc[max(0, i - window):i]
            if past.empty:
                continue
            rate = past["Consumed"].sum() / past["Days"].sum()
            for day in pd.date_range(period.Period_Start, period.Date):
                rows.append({"Food": food, "Date": day, "Demand": period.Consumed / period.Days,
                             "Bought": float(bought.get(day, 0.0)), "Forecast": rate, "Week_Forecast": rate * 7,
                             "Shelf_Life": life, "Unit_Price": price})
    return pd.DataFrame(rows, columns=["Food", "Date", "Demand", "Bought", "Forecast", "Week_Forecast",
                                       "Shelf_Life", "Unit_Price"])
