"""Pages for the M5 and Instacart public-data extracts."""


import streamlit as st


from data_profiles import demo_profile, instacart_profile, m5_profile

from services.data import INSTACART_DATA_PATH, M5_DATA_PATH, get_cleaned_data, get_instacart_data, get_m5_data, get_m5_forecast_results
from ui.charts import bar_chart, line_chart, series_line_chart
from ui.components import data_source_badge, metric_row, page_header, real_data_missing, render_provenance, section_heading
from ui.theme import ACCENT_COLOR, ALERT_COLOR, NEUTRAL_COLOR, PRIMARY_COLOR, SUPPORT_COLOR
from views.demo import overview_page


def instacart_summary(df, *, detailed=False):
    profile = instacart_profile(df)
    orders = df["Order_ID"].nunique()
    metric_row([("Total orders", f"{orders:,}"), ("Unique users", f"{df['User_ID'].nunique():,}"), ("Products", f"{df['Product_ID'].nunique():,}"), ("Items ordered", f"{len(df):,}"), ("Reorder rate", f"{df['Reordered'].mean() * 100:.1f}%")])
    st.caption("Source: Instacart Market Basket Analysis — real order/purchase behavior. Product lines are not physical quantities or household consumption.")
    render_provenance(profile)
    top_products = df.groupby("Product_Name", as_index=False).size().rename(columns={"size": "Order_Lines"}).nlargest(12, "Order_Lines")
    departments = df.groupby("Department", as_index=False).size().rename(columns={"size": "Order_Lines"})
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Most ordered products", "Order-line count")
            bar_chart(top_products, "Product_Name", "Order_Lines", PRIMARY_COLOR, 340, ".0f")
    with right:
        with st.container(border=True):
            section_heading("Department popularity", "Order-line count")
            bar_chart(departments, "Department", "Order_Lines", SUPPORT_COLOR, 340, ".0f")
    if detailed:
        left, right = st.columns(2)
        with left:
            with st.container(border=True):
                section_heading("Orders by source weekday", "Distinct orders; source day code 0–6")
                by_day = df.groupby("Order_Day_Of_Week", as_index=False)["Order_ID"].nunique().rename(columns={"Order_ID": "Orders"})
                bar_chart(by_day, "Order_Day_Of_Week", "Orders", ACCENT_COLOR, 300, ".0f")
        with right:
            with st.container(border=True):
                section_heading("Orders by hour", "Distinct orders")
                by_hour = df.groupby("Order_Hour", as_index=False)["Order_ID"].nunique().rename(columns={"Order_ID": "Orders"})
                bar_chart(by_hour, "Order_Hour", "Orders", NEUTRAL_COLOR, 300, ".0f")


def m5_summary(df, *, detailed=False):
    profile = m5_profile(df)
    daily = df.groupby("Date", as_index=False)["Quantity_Sold"].sum()
    metric_row([("Retail unit sales", f"{df['Quantity_Sold'].sum():,.0f}"), ("Products", f"{df['Product_ID'].nunique():,}"), ("Stores", f"{df['Store_ID'].nunique()}"), ("Departments", f"{df['Department'].nunique()}"), ("Average daily demand", f"{daily['Quantity_Sold'].mean():,.1f}")])
    st.caption("Source: M5 Walmart Retail Sales — observed retail unit sales/demand, not household consumption or food waste.")
    render_provenance(profile)
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Retail sales trend", "Total daily unit sales")
            line_chart(daily, "Date", "Quantity_Sold", height=300)
    with right:
        with st.container(border=True):
            section_heading("Top-selling M5 items", "Retail unit sales")
            top = df.groupby("Product_ID", as_index=False)["Quantity_Sold"].sum().nlargest(12, "Quantity_Sold")
            bar_chart(top, "Product_ID", "Quantity_Sold", PRIMARY_COLOR, 300, ".0f")
            st.caption("Labels such as `FOODS_3_090` are original M5 item IDs, not food names.")
    if detailed:
        left, right = st.columns(2)
        with left:
            with st.container(border=True):
                section_heading("Demand by weekday")
                bar_chart(df.groupby("Weekday", as_index=False)["Quantity_Sold"].sum(), "Weekday", "Quantity_Sold", ACCENT_COLOR, 290, ".0f")
        with right:
            with st.container(border=True):
                section_heading("Demand by department")
                bar_chart(df.groupby("Department", as_index=False)["Quantity_Sold"].sum(), "Department", "Quantity_Sold", SUPPORT_COLOR, 290, ".0f")


def public_overview_page():
    page_header("Real public data", "Overview", "Choose a real public source. Metrics remain within that source and never include personal or synthetic records.")
    source = st.radio("Data source", ["Instacart", "M5 Retail Sales"], horizontal=True, key="overview_public_source")
    if source == "Instacart":
        if not INSTACART_DATA_PATH.exists():
            real_data_missing(INSTACART_DATA_PATH, "Overview")
            return
        data_source_badge("Real data", "Instacart Market Basket Analysis")
        instacart_summary(get_instacart_data())
    else:
        if not M5_DATA_PATH.exists():
            real_data_missing(M5_DATA_PATH, "Overview")
            return
        data_source_badge("Real data", "M5 / Walmart retail sales")
        m5_summary(get_m5_data())


def general_insights_page():
    page_header("Real public data", "General Insights", "Exploratory analysis of one selected data source; meanings are never combined.")
    source = st.radio("Data source", ["Instacart", "M5 Retail Sales", "Demo / Synthetic Data"], horizontal=True, key="general_public_source")
    if source == "Instacart":
        if not INSTACART_DATA_PATH.exists():
            real_data_missing(INSTACART_DATA_PATH, "General Insights")
            return
        data_source_badge("Real data", "Instacart Market Basket Analysis")
        instacart_summary(get_instacart_data(), detailed=True)
    elif source == "M5 Retail Sales":
        if not M5_DATA_PATH.exists():
            real_data_missing(M5_DATA_PATH, "General Insights")
            return
        data_source_badge("Real data", "M5 / Walmart retail sales")
        m5_summary(get_m5_data(), detailed=True)
    else:
        data_source_badge("Demo data", "Synthetic development dataset")
        st.warning("DEMO / SYNTHETIC DATA — these figures are simulated and are not used anywhere in normal real-data statistics.")
        demo = get_cleaned_data()
        render_provenance(demo_profile(demo))
        overview_page(demo)


def purchase_behavior_page():
    page_header("Real public data", "Purchase / demand behavior", "Instacart represents order behavior; M5 represents retail demand. Neither source measures household consumption.")
    source = st.radio("Data source", ["Instacart purchase behavior", "M5 retail demand"], horizontal=True, key="behavior_source")
    if source.startswith("Instacart"):
        if not INSTACART_DATA_PATH.exists():
            real_data_missing(INSTACART_DATA_PATH, "Purchase / demand behavior")
            return
        data_source_badge("Real data", "Instacart order behavior")
        df = get_instacart_data()
        basket = df.groupby("Order_ID").size().rename("Items_Per_Order")
        metric_row([("Orders", f"{len(basket):,}"), ("Average basket size", f"{basket.mean():.1f} product lines"), ("Median basket size", f"{basket.median():.0f} product lines"), ("Average days since prior order", f"{df[['Order_ID','Days_Since_Prior_Order']].drop_duplicates()['Days_Since_Prior_Order'].mean():.1f}")])
        st.caption("Proxy only: basket size and interval between orders describe ordering behavior, not food consumption or waste.")
        section_heading("Product purchase behavior")
        top = df.groupby("Product_Name", as_index=False).size().rename(columns={"size": "Order_Lines"}).nlargest(15, "Order_Lines")
        bar_chart(top, "Product_Name", "Order_Lines", PRIMARY_COLOR, 380, ".0f")
    else:
        if not M5_DATA_PATH.exists():
            real_data_missing(M5_DATA_PATH, "Purchase / demand behavior")
            return
        data_source_badge("Real data", "M5 retail demand")
        df = get_m5_data()
        daily = df.groupby("Date")["Quantity_Sold"].sum()
        metric_row([("Retail unit sales", f"{daily.sum():,.0f}"), ("Average daily demand", f"{daily.mean():.1f}"), ("Peak daily demand", f"{daily.max():.0f}"), ("Products", f"{df['Product_ID'].nunique()}")])
        st.caption("M5 provides retail demand only; it does not provide household consumption, measured food waste, household inventory, or expiry dates.")
        series_line_chart(daily, [PRIMARY_COLOR], 330)


def waste_unavailable_page():
    page_header("Real public data", "Waste analysis", "FORAGE reports only measurements supported by the selected source.")
    data_source_badge("Real data", "Instacart and M5 public extracts")
    st.info("Waste analysis requires explicit waste or disposal records. The selected real datasets do not contain household waste measurements, so FORAGE does not estimate or fabricate waste values.")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Instacart availability")
            st.write("Orders, product lines, reorders, departments, aisles, and order timing are available. Household waste, consumption, inventory, expiry, and physical quantities are not available.")
    with right:
        with st.container(border=True):
            section_heading("M5 availability")
            st.write("Retail unit sales, dates/calendar, item/category information, price, event data, and demand forecasting are available. Household consumption, measured food waste, household inventory, and expiry dates are not available.")


def retail_forecasting_page():
    page_header("M5 / Walmart — Real Public Dataset", "Retail Demand Forecast", "Forecast target: retail unit sales. This is a chronological retail-demand evaluation, not a household-consumption forecast.")
    if not M5_DATA_PATH.exists():
        real_data_missing(M5_DATA_PATH, "Retail Demand Forecast")
        return
    data_source_badge("Real data", "M5 / Walmart retail sales")
    tested, _, comparison, metadata = get_m5_forecast_results()
    best = comparison.iloc[0]
    metric_row([("Selected model", metadata["best_model"]), ("MAE", f"{best['MAE']:.2f}"), ("RMSE", f"{best['RMSE']:.2f}"), ("R²", f"{best['R2']:.3f}"), ("Chronological test begins", f"{metadata['cutoff']:%d %b %Y}")])
    st.caption("All models use the same later M5 test period. Lag and rolling inputs use only prior sales; price filling uses the training period only.")
    ranked = comparison.copy()
    ranked.insert(0, "Rank", range(1, len(ranked) + 1))
    st.dataframe(ranked.rename(columns={"R2": "R²"}).round(3), width="stretch", hide_index=True)
    product = st.selectbox("Product for actual vs predicted retail sales", sorted(tested["Product_ID"].unique()), key="retail_forecast_product")
    selected = tested[tested["Product_ID"] == product].groupby("Date")[["Quantity_Sold", "Predicted_Sales"]].sum()
    series_line_chart(selected, [PRIMARY_COLOR, SUPPORT_COLOR], 350)


def real_recommendations_page():
    page_header("Real public data", "Explainable insights", "Public data can support demand and reorder insights, but not household purchase quantities without inventory and physical units.")
    source = st.radio("Data source", ["Instacart reorder behavior", "M5 expected retail demand"], horizontal=True, key="real_recommendation_source")
    if source.startswith("Instacart"):
        if not INSTACART_DATA_PATH.exists():
            real_data_missing(INSTACART_DATA_PATH, "Recommendations")
            return
        data_source_badge("Real data", "Instacart reorder behavior")
        df = get_instacart_data()
        table = df.groupby("Product_Name").agg(Order_Lines=("Order_ID", "size"), Reorders=("Reordered", "sum"), Reorder_Rate=("Reordered", "mean")).sort_values(["Reorders", "Order_Lines"], ascending=False).head(20).reset_index()
        st.caption("These are observed repeat-purchase patterns, not recommendations to buy a quantity.")
        metric_row([("Products with reorders", f"{(table['Reorders'] > 0).sum()} of top 20"), ("Overall reorder rate", f"{df['Reordered'].mean() * 100:.1f}%"), ("Top product", table.iloc[0]['Product_Name'])])
        st.dataframe(table.round({"Reorder_Rate": 3}), width="stretch", hide_index=True)
    else:
        if not M5_DATA_PATH.exists():
            real_data_missing(M5_DATA_PATH, "Recommendations")
            return
        data_source_badge("Real data", "M5 expected retail demand")
        tested, _, comparison, metadata = get_m5_forecast_results()
        best = comparison.iloc[0]
        st.caption("Expected retail demand only. FORAGE does not turn M5 sales into a household grocery purchase recommendation.")
        expected = tested.groupby("Product_ID", as_index=False).agg(Actual_Unit_Sales=("Quantity_Sold", "sum"), Predicted_Unit_Sales=("Predicted_Sales", "sum")).sort_values("Predicted_Unit_Sales", ascending=False).head(20)
        metric_row([("Selected model", metadata["best_model"]), ("Forecast MAE", f"{best['MAE']:.2f}"), ("Forecast RMSE", f"{best['RMSE']:.2f}"), ("Forecast R²", f"{best['R2']:.3f}")])
        st.dataframe(expected.round(2), width="stretch", hide_index=True)


def m5_demand_page():
    if not M5_DATA_PATH.exists():
        real_data_missing(M5_DATA_PATH, "M5 Demand")
        return
    df = get_m5_data()
    page_header("M5 Forecasting / Walmart retail sales dataset", "M5 Demand", "Retail unit sales and demand—not household consumption, food waste, or personal inventory.")
    daily = df.groupby("Date", as_index=False)["Quantity_Sold"].sum()
    metric_row([("Total units sold", f"{df['Quantity_Sold'].sum():,.0f}"), ("Products", f"{df['Product_ID'].nunique():,}"), ("Stores", f"{df['Store_ID'].nunique()}"), ("Departments", f"{df['Department'].nunique()}"), ("Average daily demand", f"{daily['Quantity_Sold'].mean():,.1f}")])
    st.caption(f"Coverage: {df['Date'].min():%d %b %Y} – {df['Date'].max():%d %b %Y}. Source: M5 Walmart retail unit-sales data; prices are weekly sell prices where available.")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Retail demand over time", "Total unit sales for the selected M5 food subset")
            line_chart(daily, "Date", "Quantity_Sold", height=280)
    with right:
        with st.container(border=True):
            section_heading("Demand by department")
            bar_chart(df.groupby("Department", as_index=False)["Quantity_Sold"].sum(), "Department", "Quantity_Sold", SUPPORT_COLOR, 280, ".0f")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Top-selling M5 items", "Highest retail unit sales")
            top = df.groupby("Product_ID", as_index=False)["Quantity_Sold"].sum().nlargest(10, "Quantity_Sold")
            bar_chart(top, "Product_ID", "Quantity_Sold", PRIMARY_COLOR, 320, ".0f")
            st.caption("Labels such as `FOODS_3_090` are original M5 item IDs, not food names.")
    with right:
        with st.container(border=True):
            section_heading("Demand by weekday")
            weekday = df.groupby("Weekday", as_index=False)["Quantity_Sold"].sum()
            bar_chart(weekday, "Weekday", "Quantity_Sold", ACCENT_COLOR, 320, ".0f")
    with st.container(border=True):
        section_heading("Retail Demand Forecasting", "Chronological split; lagged and rolling sales features use only earlier observed sales.")
        try:
            tested, _, comparison, metadata = get_m5_forecast_results()
            best = comparison.iloc[0]
            metric_row([("Selected model", metadata["best_model"]), ("MAE", f"{best['MAE']:.2f}"), ("RMSE", f"{best['RMSE']:.2f}"), ("R²", f"{best['R2']:.3f}"), ("Test begins", f"{metadata['cutoff']:%d %b %Y}")])
            st.dataframe(comparison.rename(columns={"R2": "R²"}).round(3), width="stretch", hide_index=True)
            choices = sorted(tested["Product_ID"].unique())
            product = st.selectbox("M5 item ID / store for actual vs predicted retail sales", choices, key="m5_product")
            shown = tested[tested["Product_ID"] == product].groupby("Date")[["Quantity_Sold", "Predicted_Sales"]].sum()
            series_line_chart(shown, [PRIMARY_COLOR, SUPPORT_COLOR], 325)
        except Exception as error:
            st.warning(f"Retail forecast could not be calculated: {error}")


def instacart_insights_page():
    if not INSTACART_DATA_PATH.exists():
        real_data_missing(INSTACART_DATA_PATH, "Instacart Insights")
        return
    df = get_instacart_data()
    page_header("Instacart Market Basket dataset", "Instacart Insights", "Purchase and reorder behavior from the preprocessed public-data subset. The source does not provide calendar dates, quantities, consumption, or waste.")
    order_count = df["Order_ID"].nunique()
    metric_row([("Total orders", f"{order_count:,}"), ("Unique users", f"{df['User_ID'].nunique():,}"), ("Unique products", f"{df['Product_ID'].nunique():,}"), ("Reorder rate", f"{df['Reordered'].mean() * 100:.1f}%"), ("Departments", f"{df['Department'].nunique()}"), ("Aisles", f"{df['Aisle'].nunique()}")])
    st.caption("Derived subset: users with IDs 1–2,000 and their available prior/train order lines. Order day is the source’s day-of-week code (0–6), not a calendar date.")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Top products", "Most frequently purchased product lines")
            top = df.groupby("Product_Name", as_index=False).size().rename(columns={"size": "Purchases"}).nlargest(12, "Purchases")
            bar_chart(top, "Product_Name", "Purchases", PRIMARY_COLOR, 360, ".0f")
    with right:
        with st.container(border=True):
            section_heading("Most reordered products", "Reordered product lines")
            reordered = df[df["Reordered"] == 1].groupby("Product_Name", as_index=False).size().rename(columns={"size": "Reorders"}).nlargest(12, "Reorders")
            bar_chart(reordered, "Product_Name", "Reorders", ALERT_COLOR, 360, ".0f")
    left, right = st.columns(2)
    with left:
        with st.container(border=True):
            section_heading("Department distribution")
            dept = df.groupby("Department", as_index=False).size().rename(columns={"size": "Purchases"})
            bar_chart(dept, "Department", "Purchases", SUPPORT_COLOR, 360, ".0f")
    with right:
        with st.container(border=True):
            section_heading("Orders by hour", "Distinct orders by source hour-of-day")
            hourly = df.groupby("Order_Hour", as_index=False)["Order_ID"].nunique().rename(columns={"Order_ID": "Orders"})
            bar_chart(hourly, "Order_Hour", "Orders", ACCENT_COLOR, 360, ".0f")
    with st.container(border=True):
        section_heading("Orders by day of week and reorder behavior")
        by_day = df.groupby("Order_Day_Of_Week", as_index=False)["Order_ID"].nunique().rename(columns={"Order_ID": "Orders"})
        bar_chart(by_day, "Order_Day_Of_Week", "Orders", NEUTRAL_COLOR, 230, ".0f")
