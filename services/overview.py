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
        part = frame[frame["Date"].dt.to_period("M") == period] if not frame.empty else frame
        available = (part["Opening_Stock"] + part["Quantity_Purchased"]).sum() if not part.empty else 0
        return float(part["Quantity_Wasted"].sum() / available * 100) if available else float("nan")
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


@st.cache_resource(show_spinner="Building the dashboard...")
def m5_dashboard() -> dict:
    from services.data import best_next_day, load_m5, m5_forecast
    df = load_m5()
    end = df["Date"].max()
    recent = df[df["Date"] > end - pd.Timedelta(days=28)]
    previous = df[(df["Date"] <= end - pd.Timedelta(days=28)) & (df["Date"] > end - pd.Timedelta(days=56))]
    daily_now = recent.groupby("Date")["Quantity_Sold"].sum().mean()
    daily_before = previous.groupby("Date")["Quantity_Sold"].sum().mean()
    trend = pd.DataFrame({"Recent": recent.groupby("Product_ID", observed=True)["Quantity_Sold"].mean(),
                          "Previous": previous.groupby("Product_ID", observed=True)["Quantity_Sold"].mean()}).dropna()
    trend = trend[trend["Previous"] >= 1]
    trend["Change"] = (trend["Recent"] - trend["Previous"]) / trend["Previous"] * 100
    tested, _, _, _ = m5_forecast()
    model = best_next_day("m5")
    t_end = tested["Date"].max()
    last2, prev2 = tested[tested["Date"] > t_end - pd.Timedelta(days=14)], tested[
        (tested["Date"] <= t_end - pd.Timedelta(days=14)) & (tested["Date"] > t_end - pd.Timedelta(days=28))]
    acc_now, acc_before = accuracy(last2["Quantity_Sold"], last2[model]), accuracy(prev2["Quantity_Sold"], prev2[model])
    kpis = [
        ("Units sold per day, last 28 days", f"{daily_now:,.0f}", "All 100 items, store CA_1.",
         _delta(daily_now, daily_before, "{:+,.0f} vs previous 28 days"), "normal"),
        ("Items rising 20% or more", f"{int((trend['Change'] >= 20).sum())}", "Mean daily units, last 28 vs previous 28 days.",
         None, "off"),
        ("Items falling 20% or more", f"{int((trend['Change'] <= -20).sum())}", "Overstock risk: where retail waste starts.",
         None, "off"),
        ("Forecast accuracy", f"{acc_now * 100:.1f}%", f"1 − WAPE of {model}, last 14 days of the test period.",
         _delta(acc_now * 100, acc_before * 100, "{:+.1f} pts vs previous 14 days"), "normal"),
    ]
    actions = []
    for item, row in trend.sort_values("Change").head(3).iterrows():
        actions.append({"tag": "Reduce stock", "title": f"Order less of {item}",
                        "why": f"Daily sales fell {abs(row['Change']):.0f}% ({row['Previous']:.1f} → {row['Recent']:.1f} units)."})
    for item, row in trend.sort_values("Change", ascending=False).head(2).iterrows():
        actions.append({"tag": "Restock", "title": f"Restock {item}",
                        "why": f"Daily sales rose {row['Change']:.0f}% ({row['Previous']:.1f} → {row['Recent']:.1f} units)."})
    daily = df.groupby(df["Date"].dt.to_period("W").dt.to_timestamp())["Quantity_Sold"].sum()
    top = df.groupby("Product_ID", observed=True)["Quantity_Sold"].sum().sort_values(ascending=False)
    return {"kpis": kpis, "weekly": daily.rename("Units"), "top": top.rename("Units"), "actions": actions}
