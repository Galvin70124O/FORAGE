"""Presentation numbers for the Fresh Shelf Overview and Waste & Expiry pages: the four pantry labels,
the waste-gauge target and the three expiry shelves.

Kept apart from services/overview.py, whose contents are part of the precomputed demo results' fingerprint.
Every figure reuses an existing definition (month_rate, the median unit price, the expiring-stock rules).
"""

from __future__ import annotations

import pandas as pd

from services.overview import _delta, _month_label, month_rate
from ui.components import fmt_qty


def available_rate(frame: pd.DataFrame, period: pd.Period) -> float:
    """My data: thrown away ÷ food available (opening stock + bought), periods ending in `period`."""
    part = frame[frame["Date"].dt.to_period("M") == period] if not frame.empty else frame
    available = (part["Opening_Stock"] + part["Quantity_Purchased"]).sum() if not part.empty else 0
    return float(part["Quantity_Wasted"].sum() / available * 100) if available else float("nan")


def pantry_labels(frame: pd.DataFrame, source: str, now: pd.Period) -> dict:
    """The Overview's four pantry labels for `now` and the month before, all in ₹ or %:

    purchased   total paid (Price is the total paid per purchase)
    consumed    quantity eaten × the food's median price per unit (the valuation used for ₹ wasted)
    waste rate  demo: mean of food-level rates (month_rate); My data: thrown away ÷ available
    money lost  quantity wasted × the same unit price (= the ₹ wasted figures elsewhere)
    Also the waste target for the gauge: half the rate of the first month in the data (SDG 12.3).
    """
    from waste import unit_prices
    before = now - 1
    price = frame["Unit_Price"] if "Unit_Price" in frame else frame["Food"].map(unit_prices(frame))
    value = frame.assign(Eaten=frame["Quantity_Consumed"] * price, Lost=frame["Quantity_Wasted"] * price,
                         Month=frame["Date"].dt.to_period("M"))
    rate = (lambda m: month_rate(frame, m)) if source == "demo" else (lambda m: available_rate(frame, m))
    first = value["Month"].min()

    def month(period):
        part = value[value["Month"] == period]
        return {"spent": float(part["Price"].sum()), "eaten": float(part["Eaten"].sum()),
                "lost": float(part["Lost"].sum()), "rate": rate(period), "rows": len(part)}

    return {"now": month(now), "before": month(before), "first": first, "target": rate(first) / 2,
            "first_rate": rate(first), "month": _month_label(now), "previous": _month_label(before)}


def label_items(labels: dict, *, illustrative: bool) -> list[tuple]:
    """kpi_row tuples (label, value, help, delta, delta_color) for the four pantry labels.

    Colour is semantic per metric, not per direction: buying or eating more is neither good nor bad (grey),
    waste going up is bad (red) and down is good (green); a zero change is always grey.
    """
    now, before = labels["now"], labels["before"]
    has_before = before["rows"] > 0
    note = " Illustrative (synthetic prices)." if illustrative else ""

    def money(key):
        return _delta(now[key], before[key], "₹{:+,.0f} vs last month") if has_before else None

    return [
        ("Purchased", f"₹{now['spent']:,.0f}", "Total paid for food bought this month." + note, money("spent"), "off"),
        ("Consumed", f"₹{now['eaten']:,.0f}", "Food eaten this month × each food's median price per unit." + note,
         money("eaten"), "off"),
        ("Wasted", "–" if pd.isna(now["rate"]) else f"{now['rate']:.1f}%", "Share of food thrown away this month.",
         _delta(now["rate"], before["rate"], "{:+.1f} pts vs last month") if has_before else None, "inverse"),
        ("Money lost", f"₹{now['lost']:,.0f}", "Food thrown away × each food's median price per unit." + note,
         money("lost"), "inverse"),
    ]


SHELF_WINDOW = 7
SHELVES = (("expired", "Expired", "Past its date in the last week", "Nothing has gone off. Lovely."),
           ("soon", "Use within 2 days", "Eat these first", "Nothing needs using up right now."),
           ("week", "This week", "Expiring in 3 to 7 days", "Nothing else expires this week."))


def shelf_items(source: str, df: pd.DataFrame | None, as_of) -> dict[str, list[dict]]:
    """Stock for the three expiry shelves, one jar per food per shelf (a food with batches in two
    windows sits on both, each with the quantity expiring in that window):

    expired   stock past its expiry in the last 7 days (most recent expiry shown)
    soon      stock expiring today or within 2 days (earliest shown)
    week      stock expiring in 3 to 7 days (earliest shown)
    Same stock rules as the Waste & Expiry tables: demo = each purchase's recorded remaining quantity until
    it expires; My data = expected stock split into the purchases it most likely came from.
    """
    as_of = pd.Timestamp(as_of).normalize()
    if source == "personal":
        from pantry import expected_stock, stock_batches
        from services.personal import personal_data
        buys, checks = personal_data()
        batches = stock_batches(buys, expected_stock(buys, checks, as_of)).dropna(subset=["Expiry"])
        frame = pd.DataFrame({"Food": batches["Food"], "Unit": batches["Unit"], "Quantity": batches["Quantity"],
                              "Days_Left": (batches["Expiry"] - as_of).dt.days,
                              "Shelf_Life": (batches["Expiry"] - batches["Bought"]).dt.days})
    else:
        expiry = pd.to_datetime(df["Estimated_Expiry_Date"], errors="coerce")
        frame = pd.DataFrame({"Food": df["Food"], "Unit": df["Quantity_Unit"], "Quantity": df["Remaining_Quantity"],
                              "Days_Left": (expiry - as_of).dt.days, "Shelf_Life": df["Expiry_Days"]})
        frame = frame[(frame["Quantity"] > 0) & (df["Date"] <= as_of)]
    frame = frame[frame["Days_Left"].between(-SHELF_WINDOW, SHELF_WINDOW)]

    def items(part: pd.DataFrame, pick: str) -> list[dict]:
        grouped = part.groupby(["Food", "Unit"], as_index=False).agg(
            Quantity=("Quantity", "sum"), Days_Left=("Days_Left", pick), Shelf_Life=("Shelf_Life", "median"))
        grouped = grouped.sort_values(["Days_Left", "Quantity"], ascending=[pick == "min", False])
        return [{"name": r.Food, "quantity": fmt_qty(r.Quantity, r.Unit), "days_left": int(r.Days_Left),
                 "horizon": float(r.Shelf_Life) if pd.notna(r.Shelf_Life) else SHELF_WINDOW}
                for r in grouped.itertuples()]

    days = frame["Days_Left"]
    return {"expired": items(frame[days < 0], "max"), "soon": items(frame[days.between(0, 2)], "min"),
            "week": items(frame[days.between(3, SHELF_WINDOW)], "min")}
