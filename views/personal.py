"""Pages for the user's own records (My Data)."""


import pandas as pd
import streamlit as st


from personal_data import (
    PERSONAL_DATA_PATH,
    add_personal_record,
    load_personal_data,
    personal_quality_report,
    save_personal_data,
)

from ui.charts import series_bar_chart, series_line_chart
from ui.components import data_source_badge, metric_row, page_header, recorded_quantity_note, section_heading
from ui.theme import ALERT_COLOR, NEUTRAL_COLOR, PRIMARY_COLOR, SUPPORT_COLOR


def personal_forecast_and_recommendations(df):
    """Return personal-only, history-based signals when the records support them."""
    history = df.dropna(subset=["Date", "Food", "Quantity_Consumed"]).copy()
    eligible = history.groupby("Food").filter(lambda group: len(group) >= 7)
    if eligible.empty:
        return pd.DataFrame(), pd.DataFrame()
    forecast = (eligible.sort_values("Date").groupby("Food").tail(7).groupby(["Food", "Quantity_Unit"], as_index=False)
                .agg(Predicted_Next_Use=("Quantity_Consumed", "mean"), Current_Remaining_Quantity=("Remaining_Quantity", "last"),
                     Historical_Waste=("Quantity_Wasted", "sum"), Historical_Purchased=("Quantity_Purchased", "sum")))
    forecast["Predicted_Next_Use"] = forecast["Predicted_Next_Use"].clip(lower=0)
    forecast["Current_Remaining_Quantity"] = forecast["Current_Remaining_Quantity"].fillna(0)
    forecast["Waste_Percentage"] = (forecast["Historical_Waste"] / forecast["Historical_Purchased"].replace(0, pd.NA) * 100).fillna(0)
    forecast["Suggested_Purchase"] = (forecast["Predicted_Next_Use"] - forecast["Current_Remaining_Quantity"] * (1 - forecast["Waste_Percentage"] / 100)).clip(lower=0)
    recommendations = forecast.sort_values("Suggested_Purchase", ascending=False)
    return forecast, recommendations


def personal_insights(df):
    """Generate only claims directly supported by personal records."""
    if len(df) < 2:
        return ["Not enough personal data yet."]
    insights = []
    consumed = df.groupby("Food")["Quantity_Consumed"].sum().dropna()
    wasted = df.groupby("Food")["Quantity_Wasted"].sum().dropna()
    purchased = df["Quantity_Purchased"].sum()
    if not consumed.empty and consumed.max() > 0:
        insights.append(f"{consumed.idxmax()} is your most consumed food.")
    if not wasted.empty and wasted.max() > 0:
        insights.append(f"{wasted.idxmax()} accounts for the highest share of your recorded waste.")
    if purchased > 0:
        insights.append(f"Your recorded food waste is {df['Quantity_Wasted'].sum() / purchased * 100:.1f}%.")
    if df["Date"].nunique() >= 4:
        weekend = df.assign(Weekend=df["Date"].dt.dayofweek >= 5).groupby("Weekend")["Quantity_Wasted"].sum()
        if len(weekend) == 2 and weekend.nunique() > 1:
            insights.append("Your recorded waste is highest on weekends." if weekend.get(True, 0) > weekend.get(False, 0) else "Your recorded waste is highest on weekdays.")
    return insights or ["Not enough personal data yet."]


def my_stats_page():
    personal = load_personal_data()
    page_header("Personal insights", "My Stats", "Only the food records you add or import in this development mode are used here.")
    data_source_badge("Personal data", "My Food History")
    st.caption(f"Personal storage: {PERSONAL_DATA_PATH.name}. General FORAGE Dataset records are never included.")
    if personal.empty:
        with st.container(border=True):
            st.subheader("No personal food data yet.")
            st.caption("Your personal food insights will appear here once you add or import records.")
            if st.button("Add food", key="empty_add_food"):
                st.session_state.active_page = "Add Food"
                st.rerun()
        return

    total_purchased = personal["Quantity_Purchased"].sum()
    total_consumed = personal["Quantity_Consumed"].sum()
    total_wasted = personal["Quantity_Wasted"].sum()
    spending = personal["Price"].sum(min_count=1)
    kpis = [("Total purchased", f"{total_purchased:,.2f}"), ("Total consumed", f"{total_consumed:,.2f}"),
            ("Total wasted", f"{total_wasted:,.2f}"), ("Personal waste", f"{(total_wasted / total_purchased * 100) if total_purchased else 0:.2f}%"),
            ("Food items", f"{personal['Food'].nunique()}")]
    if pd.notna(spending):
        kpis.append(("Total spending", f"{spending:,.2f}"))
    metric_row(kpis)
    recorded_quantity_note()
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Personal consumption over time")
            series_line_chart(personal.groupby("Date")["Quantity_Consumed"].sum(), [PRIMARY_COLOR], 270)
    with right:
        with st.container(border=True):
            section_heading("Personal waste over time")
            series_line_chart(personal.groupby("Date")["Quantity_Wasted"].sum(), [ALERT_COLOR], 270)
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Most consumed foods")
            series_bar_chart(personal.groupby("Food")["Quantity_Consumed"].sum().sort_values(ascending=False).head(10), PRIMARY_COLOR, 280)
    with right:
        with st.container(border=True):
            section_heading("Most wasted foods")
            series_bar_chart(personal.groupby("Food")["Quantity_Wasted"].sum().sort_values(ascending=False).head(10), ALERT_COLOR, 280)
    food_summary = personal.groupby("Food").agg(Purchased=("Quantity_Purchased", "sum"), Waste=("Quantity_Wasted", "sum"))
    food_summary["Waste percentage"] = food_summary["Waste"] / food_summary["Purchased"].replace(0, pd.NA) * 100
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Waste percentage by food")
            series_bar_chart(food_summary["Waste percentage"].dropna().sort_values(ascending=False).head(10), ALERT_COLOR, 280)
    with right:
        with st.container(border=True):
            section_heading("Personal category breakdown")
            series_bar_chart(personal.groupby("Category")["Quantity_Consumed"].sum().sort_values(ascending=False), NEUTRAL_COLOR, 280)
    if personal["Price"].notna().any():
        with st.container(border=True):
            section_heading("Spending by food")
            series_bar_chart(personal.groupby("Food")["Price"].sum().sort_values(ascending=False), SUPPORT_COLOR, 250)
    with st.container(border=True):
        section_heading("Purchased vs consumed vs wasted")
        comparison = personal.groupby("Date")[["Quantity_Purchased", "Quantity_Consumed", "Quantity_Wasted"]].sum()
        series_line_chart(comparison, [SUPPORT_COLOR, PRIMARY_COLOR, ALERT_COLOR], 280)
    with st.container(border=True):
        section_heading("Personal insights")
        for insight in personal_insights(personal):
            st.write(f"• {insight}")
    forecast, recommendations = personal_forecast_and_recommendations(personal)
    with st.container(border=True):
        section_heading("Personal forecasting")
        if forecast.empty:
            st.info("Add more personal history to unlock personal forecasting.")
        else:
            st.caption("Forecasts use each food's own latest seven personal records; no FORAGE Dataset records are used.")
            st.dataframe(forecast[["Food", "Quantity_Unit", "Predicted_Next_Use"]].round(2), width="stretch", hide_index=True)
    with st.container(border=True):
        section_heading("Personal recommendations")
        if recommendations.empty:
            st.info("Add more personal purchase and consumption history to generate personalized recommendations.")
        else:
            st.dataframe(recommendations[["Food", "Quantity_Unit", "Suggested_Purchase", "Waste_Percentage"]].round(2), width="stretch", hide_index=True)
    render_personal_data_manager(personal)


def render_personal_data_manager(personal):
    with st.expander("View, edit, or delete personal records"):
        st.caption("Changes save only to My Data. Delete rows in the table and select Save changes.")
        editable_columns = ["Record_ID", "Date", "Food", "Category", "Quantity_Purchased", "Quantity_Consumed", "Quantity_Wasted", "Price", "Expiry_Days", "Storage_Type", "Remaining_Quantity", "Quantity_Unit"]
        edited = st.data_editor(personal[editable_columns], hide_index=True, num_rows="dynamic", width="stretch", key="personal_data_editor", column_config={"Record_ID": None})
        if st.button("Save changes to My Data", key="save_personal_changes"):
            try:
                save_personal_data(edited)
                st.success("Your personal food data was updated.")
                st.rerun()
            except Exception as error:
                st.error(f"Could not save personal data: {error}")
        report = personal_quality_report(personal)
        st.caption("Personal data quality")
        metric_row([("Records", str(report["rows"])), ("Missing values", str(sum(report["missing_values"].values()))), ("Duplicates", str(report["duplicate_rows"])), ("Invalid dates", str(report["invalid_dates"])), ("Invalid numeric values", str(sum(report["invalid_numeric_values"].values())))])


def data_input_page():
    page_header("Personal data", "Add food", "Add a record to your personal local data. It will not affect General Insights or the FORAGE Dataset.")
    data_source_badge("Personal data", "My Food History")
    with st.container(border=True):
        with st.form("manual_personal_entry", clear_on_submit=True):
            st.markdown('<div class="form-section">FOOD</div>', unsafe_allow_html=True)
            first, second, third = st.columns(3)
            date = first.date_input("Date")
            food = second.text_input("Food", placeholder="e.g., Milk")
            category = third.text_input("Category", placeholder="e.g., Dairy")
            st.markdown('<div class="form-section">QUANTITY</div>', unsafe_allow_html=True)
            first, second, third, fourth = st.columns(4)
            purchased = first.number_input("Quantity purchased", min_value=0.000, format="%.2f")
            consumed = second.number_input("Quantity consumed", min_value=0.000, format="%.2f")
            wasted = third.number_input("Quantity wasted", min_value=0.000, format="%.2f")
            remaining = fourth.number_input("Remaining quantity", min_value=0.000, format="%.2f")
            st.markdown('<div class="form-section">PURCHASE AND STORAGE</div>', unsafe_allow_html=True)
            first, second, third, fourth = st.columns(4)
            price = first.number_input("Price", min_value=0.000, format="%.2f")
            expiry_days = second.number_input("Expiry days", min_value=0, step=1)
            storage = third.selectbox("Storage type", ["Refrigerator", "Pantry", "Freezer", "Room temperature", "Other"])
            unit = fourth.selectbox("Unit", ["kg", "L", "g", "ml", "dozen", "loaf", "pack", "unit"])
            submitted = st.form_submit_button("Add to My Data")
        if submitted:
            if not food.strip() or purchased <= 0:
                st.error("Enter a food name and a quantity purchased greater than zero.")
            elif consumed + wasted + remaining > purchased + 0.011:
                st.error("Consumed, wasted, and remaining quantities cannot exceed quantity purchased.")
            else:
                add_personal_record({"Date": pd.Timestamp(date), "Food": food.strip(), "Category": category.strip() or "Uncategorized", "Quantity_Purchased": purchased, "Quantity_Consumed": consumed, "Quantity_Wasted": wasted, "Remaining_Quantity": remaining, "Price": price, "Expiry_Days": expiry_days, "Storage_Type": storage, "Quantity_Unit": unit, "Estimated_Expiry_Date": pd.Timestamp(date) + pd.Timedelta(days=expiry_days)})
                st.success("Added to your personal food data.")
    st.info("To add several records at once, use Import Dataset. Imports are processed through the shared mapping and data-quality pipeline, then saved only to My Data.")
