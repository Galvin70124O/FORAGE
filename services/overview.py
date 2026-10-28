"""Numbers for the Overview dashboard: four KPIs with month-on-month deltas, two charts and an action list.

Definitions (shown on the page):
    this month          the latest calendar month in the data (demo: Dec 2025; My data: the current month)
    forecast accuracy   1 - WAPE = 1 - sum|actual - predicted| / sum(actual), for the selected next-day model
    items at risk       demo: records the waste-risk model flags in the last 7 days of data;
                        My data: foods with stock expiring within 7 days or likely to be wasted
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from waste import food_waste, rupee_summary


def accuracy(actual: pd.Series, predicted: pd.Series) -> float:
    total = float(np.abs(actual).sum())
    return float(1 - np.abs(actual - predicted).sum() / total) if total > 0 else float("nan")


def month_rate(df: pd.DataFrame, month: pd.Period) -> float:
    part = df[df["Date"].dt.to_period("M") == month]
    return float(food_waste(part)["Waste_Rate"].mean()) if not part.empty else float("nan")


def _delta(now: float, before: float, fmt: str) -> str | None:
    """Signed change for st.metric; a leading "₹" in `fmt` goes after the sign ("+₹2,233")."""
    if pd.isna(now) or pd.isna(before):
        return None
    change = now - before
    if fmt.startswith("₹"):
        return ("+" if change >= 0 else "-") + "₹" + fmt[1:].replace("{:+", "{:").format(abs(change))
    return fmt.format(change)


def _month_label(period: pd.Period) -> str:
    return period.to_timestamp().strftime("%b %Y")


@st.cache_resource(show_spinner="Building the dashboard...")
def demo_dashboard() -> dict:
    from services.data import _precomputed
    if (hit := _precomputed("demo_dashboard")) is not None:
        return hit
    from services.data import best_next_day, demo_classifier, demo_forecast, demo_plan_with_risk, load_demo
    df = load_demo()
    rupees = rupee_summary(df)
    monthly = rupees["monthly"]
    now, before = monthly.index[-1].to_period("M"), monthly.index[-2].to_period("M")
    rate_now, rate_before = month_rate(df, now), month_rate(df, before)
    result, model = demo_forecast(), best_next_day("demo")
    tested = result["tested"]
    month_of = tested["Date"].dt.to_period("M")
    acc_now = accuracy(tested.loc[month_of == now, "Quantity_Consumed"], tested.loc[month_of == now, model])
    acc_before = accuracy(tested.loc[month_of == before, "Quantity_Consumed"], tested.loc[month_of == before, model])
    risk = demo_classifier()
    flagged = risk["test"].assign(Score=risk["scores"][risk["best"]])
    threshold = risk["threshold"]
    end = flagged["Date"].max()
    last_week = flagged[flagged["Date"] > end - pd.Timedelta(days=7)]
    month_ago = flagged[(flagged["Date"] > end - pd.Timedelta(days=35)) & (flagged["Date"] <= end - pd.Timedelta(days=28))]
    at_risk, at_risk_before = int((last_week["Score"] >= threshold).sum()), int((month_ago["Score"] >= threshold).sum())
    kpis = [
        (f"₹ wasted, {_month_label(now)}", f"₹{monthly.iloc[-1]:,.0f}",
         "Illustrative (synthetic prices): wasted quantity × median price per unit.",
         _delta(monthly.iloc[-1], monthly.iloc[-2], "₹{:+,.0f} vs last month"), "inverse"),
        ("Waste rate", f"{rate_now:.1f}%", "Wasted ÷ purchased per food, averaged across foods, this month.",
         _delta(rate_now, rate_before, "{:+.1f} pts vs last month"), "inverse"),
        ("Items at risk this week", f"{at_risk}", "Purchases in the last 7 days that the waste-risk model flags "
         "as likely high waste (recall-first threshold).", _delta(at_risk, at_risk_before, "{:+.0f} vs a month ago"),
         "inverse"),
        ("Forecast accuracy", f"{acc_now * 100:.1f}%", f"1 − WAPE of {model}'s next-day forecasts this month.",
         _delta(acc_now * 100, acc_before * 100, "{:+.1f} pts vs last month"), "normal"),
    ]
    plan = demo_plan_with_risk()  # same scoring as the Recommendations page
    actions = []
    for row in plan.sort_values(["Days_Until_Expiry", "Waste_Risk"], ascending=[True, False]).itertuples():
        unit = row.Quantity_Unit
        if "short shelf life" in row.Alerts and row.Current_Remaining_Quantity > 0:
            actions.append({"tag": "Use first", "title": f"Use the {row.Current_Remaining_Quantity:.2f} {unit} of "
                            f"{row.Food} in stock first",
                            "why": f"It reaches its shelf life in {row.Days_Until_Expiry:.0f} days."})
        elif "likely to be wasted" in row.Alerts:
            actions.append({"tag": "Buy less", "title": f"Buy no more than {row.Recommended_Purchase_Quantity:.2f} "
                            f"{unit} of {row.Food}",
                            "why": f"The waste-risk model gives this purchase a {row.Waste_Risk:.0f}% chance of "
                                   "ending up high waste."})
        if len(actions) == 5:
            break
    top_food = rupees["by_food"]
    return {"kpis": kpis, "monthly": monthly, "by_food": top_food, "actions": actions, "illustrative": True,
            "month": _month_label(now)}


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
    """kpi_row tuples (label, value, help, delta, delta_color) for the four pantry labels."""
    now, before = labels["now"], labels["before"]
    has_before = before["rows"] > 0
    note = " Illustrative (synthetic prices)." if illustrative else ""

    def money(key):
        return _delta(now[key], before[key], "₹{:+,.0f} vs last month") if has_before else None

    return [
        ("Purchased", f"₹{now['spent']:,.0f}", "Total paid for food bought this month." + note, money("spent"), "off"),
        ("Consumed", f"₹{now['eaten']:,.0f}", "Food eaten this month × each food's median price per unit." + note,
         money("eaten"), "normal"),
        ("Wasted", "–" if pd.isna(now["rate"]) else f"{now['rate']:.1f}%", "Share of food thrown away this month.",
         _delta(now["rate"], before["rate"], "{:+.1f} pts vs last month") if has_before else None, "inverse"),
        ("Money lost", f"₹{now['lost']:,.0f}", "Food thrown away × each food's median price per unit." + note,
         money("lost"), "inverse"),
    ]


SHELF_WINDOW = 7


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
        return [{"name": r.Food, "quantity": f"{r.Quantity:,.2f} {r.Unit}", "days_left": int(r.Days_Left),
                 "horizon": float(r.Shelf_Life) if pd.notna(r.Shelf_Life) else SHELF_WINDOW}
                for r in grouped.itertuples()]

    days = frame["Days_Left"]
    return {"expired": items(frame[days < 0], "max"), "soon": items(frame[days.between(0, 2)], "min"),
            "week": items(frame[days.between(3, SHELF_WINDOW)], "min")}


def personal_dashboard(purchases: pd.DataFrame, checks: pd.DataFrame) -> dict:
    from pantry import (analysis_frame, expected_stock, expiring_soon, likely_wasted, period_forecast_evaluation,
                        periods, stock_batches, wasted_value)
    today = pd.Timestamp.today().normalize()
    frame = analysis_frame(purchases, checks)
    now, before = today.to_period("M"), (today - pd.DateOffset(months=1)).to_period("M")
    value = frame.assign(Rupees=wasted_value(frame)) if not frame.empty else frame
    def month_sum(period):
        return float(value.loc[value["Date"].dt.to_period("M") == period, "Rupees"].sum()) if not value.empty else 0.0
    def month_waste(period):
        return available_rate(frame, period)
    stock = expected_stock(purchases, checks, today)
    batches = stock_batches(purchases, stock)
    soon, risk = expiring_soon(batches, today, 7), likely_wasted(batches, today)
    at_risk = sorted(set(soon["Food"]) | set(risk["Food"]))
    predictions, _ = period_forecast_evaluation(periods(purchases, checks))
    def month_accuracy(period):
        if predictions.empty:
            return float("nan")
        part = predictions[predictions["Date"].dt.to_period("M") == period]
        return accuracy(part["Actual"], part["4-period average"]) if not part.empty else float("nan")
    acc_now, acc_before = month_accuracy(now), month_accuracy(before)
    kpis = [
        (f"₹ wasted, {_month_label(now)}", f"₹{month_sum(now):,.0f}", "Thrown away at pantry checks × your price per unit.",
         _delta(month_sum(now), month_sum(before), "₹{:+,.0f} vs last month"), "inverse"),
        ("Waste rate", "–" if pd.isna(month_waste(now)) else f"{month_waste(now):.1f}%",
         "Thrown away ÷ food available, periods ending this month.",
         _delta(month_waste(now), month_waste(before), "{:+.1f} pts vs last month"), "inverse"),
        ("Items at risk this week", f"{len(at_risk)}", "Foods with stock expiring within 7 days or likely to be "
         "wasted at your usual pace.", None, "off"),
        ("Forecast accuracy", "–" if pd.isna(acc_now) else f"{acc_now * 100:.1f}%",
         "1 − WAPE of the 4-period average for periods ending this month.",
         _delta(acc_now * 100, acc_before * 100, "{:+.1f} pts vs last month"), "normal"),
    ]
    actions = []
    for row in risk.groupby("Food", as_index=False).agg(At_Risk=("At_Risk", "sum"), Unit=("Unit", "first"),
                                                        Expiry=("Expiry", "min")).sort_values("Expiry").itertuples():
        actions.append({"tag": "Use first", "title": f"Use up {row.At_Risk:.2f} {row.Unit} of {row.Food}",
                        "why": f"At your usual pace it will not be eaten before {row.Expiry:%d %b}. Do not buy more yet."})
    for row in soon[~soon["Food"].isin(risk["Food"])].itertuples():
        actions.append({"tag": "Expires soon", "title": f"{row.Quantity:.2f} {row.Unit} of {row.Food} expires "
                        f"in {row.Days_Left} days", "why": "You normally eat it in time; keep it in view."})
    monthly = (value.groupby(value["Date"].dt.to_period("M").dt.to_timestamp())["Rupees"].sum()
               if not value.empty else pd.Series(dtype=float))
    by_food = value.groupby("Food")["Rupees"].sum().sort_values(ascending=False) if not value.empty else pd.Series(dtype=float)
    return {"kpis": kpis, "monthly": monthly.rename("Rupees"), "by_food": by_food.rename("Rupees"),
            "actions": actions[:5], "illustrative": False, "month": _month_label(now)}


def m5_accuracy(tested: pd.DataFrame, model: str) -> tuple[float, float]:
    """1 − WAPE of `model` on item-days: the last 14 days of the test period and the 14 before."""
    end = tested["Date"].max()
    last = tested[tested["Date"] > end - pd.Timedelta(days=14)]
    before = tested[(tested["Date"] <= end - pd.Timedelta(days=14)) & (tested["Date"] > end - pd.Timedelta(days=28))]
    return accuracy(last["Quantity_Sold"], last[model]), accuracy(before["Quantity_Sold"], before[model])


@st.cache_resource(show_spinner="Building the dashboard...")
def m5_dashboard() -> dict:
    """KPIs, weekly totals, top items and actions, from the M5 aggregates (the same locally and online)."""
    from services.data import best_next_day, has_raw, m5_forecast, m5_summary
    summary = m5_summary()
    counts = summary.values["trend_counts"]
    model = best_next_day("m5")
    if has_raw("m5"):
        acc_now, acc_before = m5_accuracy(m5_forecast()[0], model)
    else:  # item-level predictions are not published; the accuracy was computed offline on them
        acc_now, acc_before = summary.values["accuracy_now"], summary.values["accuracy_before"]
    kpis = [
        ("Units sold per day, last 28 days", f"{counts['daily_now']:,.0f}", "All 100 items, store CA_1.",
         _delta(counts["daily_now"], counts["daily_before"], "{:+,.0f} vs previous 28 days"), "normal"),
        ("Items rising 20% or more", f"{counts['rising']}", "Mean daily units, last 28 vs previous 28 days.", None, "off"),
        ("Items falling 20% or more", f"{counts['falling']}", "Overstock risk: where retail waste starts.", None, "off"),
        ("Forecast accuracy", f"{acc_now * 100:.1f}%", f"1 − WAPE of {model}, last 14 days of the test period.",
         _delta(acc_now * 100, acc_before * 100, "{:+.1f} pts vs previous 14 days"), "normal"),
    ]
    trend = summary.trends.set_index("Product_ID")
    actions = []
    for item, row in trend.sort_values("Change").head(3).iterrows():
        actions.append({"tag": "Reduce stock", "title": f"Order less of {item}",
                        "why": f"Daily sales fell {abs(row['Change']):.0f}% ({row['Previous']:.1f} → {row['Recent']:.1f} units)."})
    for item, row in trend.sort_values("Change", ascending=False).head(2).iterrows():
        actions.append({"tag": "Restock", "title": f"Restock {item}",
                        "why": f"Daily sales rose {row['Change']:.0f}% ({row['Previous']:.1f} → {row['Recent']:.1f} units)."})
    days = summary.department_day
    weekly = days.groupby(days["Date"].dt.to_period("W").dt.to_timestamp())["Units"].sum()
    top = summary.top_items_weekly.groupby("Product_ID")["Units"].sum().sort_values(ascending=False)
    return {"kpis": kpis, "weekly": weekly.rename("Units"), "top": top.rename("Units"), "actions": actions}
