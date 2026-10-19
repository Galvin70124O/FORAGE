"""Pages for the synthetic demo dataset."""

from html import escape

import altair as alt
import streamlit as st



from services.data import get_forecast_results, get_recommendations, quantity_summary
from ui.charts import bar_chart, chart_colors, configure_chart, series_bar_chart, series_line_chart
from ui.components import inventory_signal, metric_row, page_header, recorded_quantity_note, render_filters, section_heading
from ui.theme import ACCENT_COLOR, ALERT_COLOR, NEUTRAL_COLOR, PRIMARY_COLOR, SUPPORT_COLOR


def overview_page(df):
    page_header("Demo / Synthetic Data", "Demo Insights", "Simulated 7,300-row development data. These statistics are never used for normal real-data views or My Stats.")
    total_purchased = df["Quantity_Purchased"].sum()
    total_consumed = df["Quantity_Consumed"].sum()
    total_wasted = df["Quantity_Wasted"].sum()
    waste_percentage = total_wasted / total_purchased * 100
    monthly = df.groupby("Month").agg(Consumption=("Quantity_Consumed", "sum"), Waste=("Quantity_Wasted", "sum"))
    month_delta = monthly["Waste"].iloc[-1] - monthly["Waste"].iloc[-2]
    highest_waste = quantity_summary(df, "Quantity_Wasted").iloc[0]
    highest_consumption = quantity_summary(df, "Quantity_Consumed").iloc[0]

    metric_row([
        ("Purchased", f"{total_purchased:,.2f}", None, "Total recorded purchase quantity"),
        ("Consumed", f"{total_consumed:,.2f}", None, "Total recorded consumption quantity"),
        ("Wasted", f"{total_wasted:,.2f}", f"{month_delta:+.2f} vs previous month"),
        ("Overall waste", f"{waste_percentage:.2f}%", None, "Total waste divided by total purchased quantity"),
        ("Food items", f"{df['Food'].nunique()}", None, "Unique food names in the dataset"),
    ])
    recorded_quantity_note()

    st.caption(f"Coverage: {df['Date'].min():%d %b %Y} – {df['Date'].max():%d %b %Y}  ·  Cleaned dataset active")
    left, right = st.columns([1.65, 1])
    with left:
        with st.container(border=True):
            section_heading("Consumption & waste trend", "Monthly recorded consumption and waste")
            monthly_long = monthly.reset_index().melt("Month", var_name="Measure", value_name="Quantity")
            palette = chart_colors()
            chart = alt.Chart(monthly_long).mark_line(point=alt.OverlayMarkDef(size=34, filled=True), strokeWidth=2.8).encode(
                x=alt.X("Month:O", title=None), y=alt.Y("Quantity:Q", title=None),
                color=alt.Color("Measure:N", scale=alt.Scale(range=[palette["consumption"], palette["trend_waste"]]), legend=alt.Legend(title=None)),
                tooltip=["Month:O", "Measure:N", alt.Tooltip("Quantity:Q", format=".2f")],
            ).properties(height=300)
            st.altair_chart(configure_chart(chart), width="stretch")
    with right:
        with st.container(border=True):
            section_heading("Inventory signals", "Highest item-level totals")
            inventory_signal("Highest consumption", highest_consumption["Food"], highest_consumption["Quantity_Consumed"], highest_consumption["Quantity_Unit"])
            inventory_signal("Highest waste", highest_waste["Food"], highest_waste["Quantity_Wasted"], highest_waste["Quantity_Unit"])
            st.caption("Use the waste workspace to review high-waste alerts and food-level actions.")
    first, second = st.columns(2)
    category_consumption = df.groupby("Category", as_index=False)["Quantity_Consumed"].sum()
    category_waste = df.groupby("Category", as_index=False)["Quantity_Wasted"].sum()
    with first:
        with st.container(border=True):
            section_heading("Consumption by category", "Recorded consumption by food category")
            bar_chart(category_consumption, "Category", "Quantity_Consumed", PRIMARY_COLOR, 255)
    with second:
        with st.container(border=True):
            section_heading("Waste by category", "Recorded waste by food category")
            bar_chart(category_waste, "Category", "Quantity_Wasted", ALERT_COLOR, 255)
    first, second = st.columns(2)
    with first:
        with st.container(border=True):
            section_heading("Most consumed foods", "Top recorded consumption totals")
            bar_chart(quantity_summary(df, "Quantity_Consumed").head(8), "Food", "Quantity_Consumed", PRIMARY_COLOR, 235)
    with second:
        with st.container(border=True):
            section_heading("Most wasted foods", "Top recorded waste totals")
            bar_chart(quantity_summary(df, "Quantity_Wasted").head(8), "Food", "Quantity_Wasted", ALERT_COLOR, 235)


def consumption_page(df):
    page_header("FORAGE Dataset", "Consumption analysis", "General/demo analysis only. Personal records are available in My Stats.")
    filtered = render_filters(df)
    if filtered.empty:
        st.warning("No records match the selected filters. Change a filter to view consumption results.")
        return
    total_consumption = filtered["Quantity_Consumed"].sum()
    average_consumption = filtered["Quantity_Consumed"].mean()
    weekend_average = filtered.loc[filtered["Is_Weekend"] == 1, "Quantity_Consumed"].mean()
    metric_row([("Matching records", f"{len(filtered):,}"), ("Recorded consumption", f"{total_consumption:,.2f}"), ("Average per record", f"{average_consumption:.2f}"), ("Weekend average", f"{weekend_average:.2f}")])
    recorded_quantity_note()

    trend = filtered.groupby("Date")["Quantity_Consumed"].sum()
    food = quantity_summary(filtered, "Quantity_Consumed").set_index("Food")
    category = filtered.groupby("Category")["Quantity_Consumed"].sum().sort_values(ascending=False)
    day_type = filtered.assign(Day_Type=filtered["Is_Weekend"].map({0: "Weekday", 1: "Weekend"})).groupby("Day_Type")["Quantity_Consumed"].mean().reindex(["Weekday", "Weekend"])
    with st.container(border=True):
        st.subheader("Consumption trend")
        st.caption("Daily recorded consumption for the active filters")
        series_line_chart(trend, [PRIMARY_COLOR], height=285)
    first, second = st.columns(2)
    with first:
        with st.container(border=True):
            st.subheader("By food")
            series_bar_chart(food["Quantity_Consumed"], PRIMARY_COLOR, height=345)
    with second:
        with st.container(border=True):
            st.subheader("By category")
            series_bar_chart(category, NEUTRAL_COLOR, height=345)
    with st.container(border=True):
        st.subheader("Weekday versus weekend")
        st.caption("Average recorded consumption per row")
        series_bar_chart(day_type, ACCENT_COLOR, height=225)


def waste_page(df):
    page_header("FORAGE Dataset", "Waste analysis", "General/demo analysis only. Personal records are available in My Stats.")
    total_waste = df["Quantity_Wasted"].sum()
    overall_waste = total_waste / df["Quantity_Purchased"].sum() * 100
    food_waste = df.groupby(["Food", "Quantity_Unit"]).agg(
        Total_Waste=("Quantity_Wasted", "sum"),
        Waste_Percentage=("Quantity_Wasted", lambda values: values.sum() / df.loc[values.index, "Quantity_Purchased"].sum() * 100),
    ).sort_values("Waste_Percentage", ascending=False)
    category_waste = df.groupby("Category").agg(
        Total_Waste=("Quantity_Wasted", "sum"),
        Waste_Percentage=("Quantity_Wasted", lambda values: values.sum() / df.loc[values.index, "Quantity_Purchased"].sum() * 100),
    ).sort_values("Waste_Percentage", ascending=False)
    highest_food, _ = food_waste.index[0]
    metric_row([
        ("Total waste", f"{total_waste:,.2f}"),
        ("Overall waste rate", f"{overall_waste:.2f}%"),
        ("Highest waste-rate food", highest_food, f"{food_waste.iloc[0]['Waste_Percentage']:.2f}%"),
        ("Highest waste category", category_waste.index[0], f"{category_waste.iloc[0]['Waste_Percentage']:.2f}%"),
    ])
    recorded_quantity_note()

    with st.container(border=True):
        st.subheader("Waste trend")
        st.caption("Daily recorded waste")
        series_line_chart(df.groupby("Date")["Quantity_Wasted"].sum(), [ALERT_COLOR], height=275, markers=True)
    first, second = st.columns(2)
    with first:
        with st.container(border=True):
            st.subheader("Waste rate by food")
            food_rate_chart = food_waste.reset_index().set_index("Food")["Waste_Percentage"].head(12)
            series_bar_chart(food_rate_chart, ALERT_COLOR, height=360)
    with second:
        with st.container(border=True):
            st.subheader("Waste rate by category")
            series_bar_chart(category_waste["Waste_Percentage"], ACCENT_COLOR, height=360)
    with st.container(border=True):
        st.subheader("High-waste items")
        st.dataframe(food_waste.head(10).reset_index().round(2), width="stretch", hide_index=True)


def forecasting_page():
    page_header("FORAGE Dataset", "General demand forecast", "General/demo forecast only; personal forecasting is available in My Stats when enough history exists.")
    comparison, chart_data, best_model, cutoff_date = get_forecast_results()
    best_metrics = comparison.iloc[0]
    metric_row([
        ("Selected model", best_model),
        ("MAE", f"{best_metrics['MAE']:.4f}", None, "Average absolute prediction error; lower is better"),
        ("RMSE", f"{best_metrics['RMSE']:.4f}", None, "Penalizes larger prediction errors; lower is better"),
        ("R²", f"{best_metrics['R2']:.4f}", None, "How much variation the model explains; higher is better"),
    ])
    st.caption(f"Chronological test period starts on {cutoff_date:%d %b %Y}; later dates are never used for training.")
    first, second = st.columns([1, 1.25])
    with first:
        with st.container(border=True):
            st.subheader("How to read these metrics")
            st.markdown("- **MAE:** typical prediction error.\n- **RMSE:** gives extra weight to larger errors.\n- **R²:** fit compared with observed consumption.")
    with second:
        with st.container(border=True):
            st.subheader("Model comparison")
            st.dataframe(comparison.rename(columns={"R2": "R²"}).round(4), width="stretch", hide_index=True)
    with st.container(border=True):
        selected_food = st.selectbox("Food for actual versus predicted comparison", sorted(chart_data["Food"].unique()))
        selected = chart_data[chart_data["Food"] == selected_food].set_index("Date")
        st.subheader(f"Actual versus predicted: {selected_food}")
        st.caption(f"Quantity unit: {selected['Quantity_Unit'].iloc[0]}")
        series_line_chart(selected[["Quantity_Consumed", "Predicted_Consumption"]], [PRIMARY_COLOR, SUPPORT_COLOR], height=350)
    recommendations = get_recommendations()
    with st.container(border=True):
        st.subheader("Next-day predicted demand")
        st.info("The next-day forecast uses Is_Festival = 0 because no confirmed future event calendar is supplied.")
        st.dataframe(recommendations[["Food", "Quantity_Unit", "Forecast_Date", "Predicted_Demand"]].round(2), width="stretch", hide_index=True)


def recommendations_page():
    page_header("FORAGE Dataset", "General purchase plan", "General/demo recommendations based on the FORAGE Dataset, not your personal records.")
    recommendations = get_recommendations()
    needs_purchase = recommendations["Recommended_Purchase_Quantity"] > 0
    active_alerts = recommendations["Alerts"].ne("No alert")
    highest_purchase = recommendations.iloc[0]
    metric_row([
        ("Forecast date", f"{recommendations['Forecast_Date'].iloc[0]:%d %b %Y}"),
        ("Items to purchase", f"{needs_purchase.sum()}"),
        ("Already covered", f"{(~needs_purchase).sum()}"),
        ("High-risk alerts", f"{active_alerts.sum()}"),
    ])
    st.caption("Quantities remain food-specific: mixed units are not summed into one misleading total.")
    st.markdown(f"<div class='chart-note'>Highest immediate purchase action: <b>{escape(str(highest_purchase['Food']))}</b> · {highest_purchase['Recommended_Purchase_Quantity']:.2f} {escape(str(highest_purchase['Quantity_Unit']))}</div>", unsafe_allow_html=True)

    section_heading("Recommended actions", "Cards are ordered by recommended purchase quantity")
    card_rows = recommendations.head(12).reset_index(drop=True)
    for start in range(0, len(card_rows), 2):
        columns = st.columns(2)
        for column, (_, row) in zip(columns, card_rows.iloc[start:start + 2].iterrows()):
            labels = []
            if "highest 25%" in row["Alerts"]:
                labels.append("<span class='badge badge-waste'>HIGH WASTE</span>")
            if "below predicted demand" in row["Alerts"]:
                labels.append("<span class='badge badge-low'>LOW STOCK</span>")
            if row["Recommended_Purchase_Quantity"] == 0:
                labels.append("<span class='badge badge-covered'>STOCK COVERED</span>")
            badges = "".join(labels) or "<span class='badge badge-covered'>MONITOR</span>"
            with column:
                st.markdown(
                    f"""<div class='rec-card'>
                    <div class='rec-name'>{escape(str(row['Food']))}</div>
                    <div class='rec-category'>{escape(str(row['Category']))} · {escape(str(row['Quantity_Unit']))}</div>
                    <div class='rec-quantity'>{row['Recommended_Purchase_Quantity']:.2f} {escape(str(row['Quantity_Unit']))}</div>
                    <div class='rec-label'>RECOMMENDED PURCHASE</div>
                    <div style='margin-top:.65rem;font-size:.84rem'>Demand <b>{row['Predicted_Demand']:.2f}</b> · Remaining <b>{row['Current_Remaining_Quantity']:.2f}</b> · Waste <b>{row['Historical_Waste_Percentage']:.1f}%</b></div>
                    <div>{badges}</div></div>""",
                    unsafe_allow_html=True,
                )
                with st.expander(f"Why {row['Food']}?"):
                    st.write(row["Reason"])
                    st.caption(f"Alert status: {row['Alerts']}")
    with st.expander("View the complete purchase plan table"):
        display_columns = ["Food", "Category", "Quantity_Unit", "Predicted_Demand", "Current_Remaining_Quantity", "Historical_Waste_Percentage", "Recommended_Purchase_Quantity", "Alerts"]
        st.dataframe(recommendations[display_columns].round(2), width="stretch", hide_index=True)
    st.download_button("Download recommendations CSV", recommendations.to_csv(index=False).encode("utf-8"), file_name="purchase_recommendations.csv", mime="text/csv")
