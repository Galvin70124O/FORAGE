"""EDA: descriptive statistics, category frequencies, correlations and the main patterns."""

import streamlit as st

from stats import (
    correlation_matrix,
    describe_strength,
    descriptive_statistics,
    frequency_table,
    strongest_correlations,
)
from ui import charts
from ui.components import number, section, table
from services.data import source_tests
from views import tests_section
from views.common import UNIT_NOTE, begin

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def household_config(df):
    columns = {
        "Quantity_Purchased": "Purchased (unit)", "Quantity_Consumed": "Consumed (unit)",
        "Quantity_Wasted": "Wasted (unit)", "Remaining_Quantity": "Remaining (unit)",
        "Price": "Price (currency)", "Expiry_Days": "Shelf life (days)",
        "Waste_Percentage": "Waste (% of purchase)", "Consumption_Rate": "Consumed (share of purchase)",
    }
    derived = {frozenset(("Wasted (unit)", "Waste (% of purchase)")),
               frozenset(("Consumed (unit)", "Consumed (share of purchase)")),
               frozenset(("Waste (% of purchase)", "Consumed (share of purchase)"))}
    return df.rename(columns=columns), list(columns.values()), "Category", "Records per category", derived, UNIT_NOTE


def m5_config(df):
    frame = df.assign(Day_Number=df["Date"].dt.dayofweek, Event_Day=df["Event_Name"].notna().astype(int))
    columns = {"Quantity_Sold": "Units sold (per item-day)", "Price": "Price (USD)",
               "Day_Number": "Weekday (0 = Monday)", "Month": "Month", "Event_Day": "Event day (1 = yes)"}
    return (frame.rename(columns=columns), list(columns.values()), "Department", "Item-days per department",
            set(), "Each row is one item on one day at store CA_1.")


def instacart_config(df):
    orders = df.groupby("Order_ID").agg(
        Basket=("Product_ID", "size"), Reorder_Share=("Reordered", "mean"), Order_Hour=("Order_Hour", "first"),
        Order_Day=("Order_Day_Of_Week", "first"), Days_Since=("Days_Since_Prior_Order", "first"),
        Order_Number=("Order_Number", "first"))
    columns = {"Basket": "Items per order", "Reorder_Share": "Reordered share of basket",
               "Days_Since": "Days since previous order", "Order_Hour": "Hour of day (0–23)",
               "Order_Day": "Day code (0–6)", "Order_Number": "Customer's order number"}
    frame = orders.rename(columns=columns)
    frame["Department"] = None
    return (frame, list(columns.values()), None, "Order lines per department", set(),
            "Statistics are per order (one row per order). Days since previous order is blank for first orders "
            "and capped at 30 by Instacart, which is why its mode and maximum are both 30.")


source, df = begin("EDA", "Descriptive statistics, category frequencies, correlations and the main patterns "
                   "in the selected source.")

if df is not None:
    configs = {"demo": household_config, "personal": household_config, "m5": m5_config, "instacart": instacart_config}
    frame, stat_columns, category, frequency_title, derived_pairs, note = configs[source](df)

    st.header("Descriptive statistics")
    st.caption(note + " Missing values are excluded from each statistic and counted separately. "
               "Std is the sample standard deviation; IQR = Q3 − Q1; the mode is the most frequent recorded value.")
    stats = descriptive_statistics(frame, stat_columns).reset_index()
    table(stats, {
        "Column": "Variable", "Count": number("Count", "%d"), "Missing": number("Missing", "%d"),
        **{name: number(name, "%.2f") for name in ["Mean", "Median", "Mode", "Std", "Min", "Max", "Q1", "Q3", "IQR"]},
    })

    left, right = st.columns([1, 1.35], gap="large")
    with left:
        section("Frequency table", frequency_title)
        if source == "instacart":
            frequencies = frequency_table(df["Department"].astype(str), label="Department")
        else:
            frequencies = frequency_table(df[category], label=category)
        table(frequencies.reset_index(), {"Count": number("Count", "%d"), "Share (%)": number("Share (%)", "%.1f")})
    with right:
        section("Correlation matrix", "Pearson r between the variables above")
        corr = correlation_matrix(frame, stat_columns)
        charts.correlation_heatmap(corr, height=380)
        st.caption("Blue is positive, red is negative, grey is no linear relationship.")
        top = strongest_correlations(corr, 1, exclude_pairs=derived_pairs)
        if not top.empty:
            pair = top.iloc[0]
            first, second = (name.split(" (")[0].lower() for name in (pair["First"], pair["Second"]))
            excluded = " (ignoring pairs where one variable is calculated from the other)" if derived_pairs else ""
            st.markdown(f"**Reading:** the strongest relationship{excluded} is a {describe_strength(pair['r'])} "
                        f"correlation between {first} and {second} (r = {pair['r']:.2f}). Correlation does not "
                        "show cause.")
            if source in ("demo", "personal"):
                st.caption("Correlations between raw quantities partly reflect that some foods are bought in larger "
                           "amounts than others.")

    st.header("Statistical tests")
    if source == "personal":
        from hypothesis import household_tests
        from services.personal import gate
        from views.common import PERIOD_NOTE
        shown, reliable, note = gate("tests")
        st.caption(PERIOD_NOTE + " The weekend vs weekday t-test is therefore not run on My data.")
        if not shown:
            st.write("Statistical tests need at least 12 completed pantry-check periods. " + note)
        else:
            if not reliable:
                st.warning(note)
            tests_section.render(household_tests(df, daily=False), source=source)
    else:
        tests_section.render(source_tests(source), source=source)

    st.header("Patterns")
    if source == "personal":
        from views.common import PERIOD_NOTE
        section("Distribution of waste per period", "Waste as a share of what was available in each period")
        charts.histogram(df.dropna(subset=["Waste_Percentage"]), "Waste_Percentage",
                         value_title="Waste (% of available)", slot=1, bins=20)
        st.caption(PERIOD_NOTE)
    elif source == "demo":
        left, right = st.columns(2, gap="large")
        with left:
            section("Distribution of waste per record", "Waste as a share of each purchase")
            charts.histogram(df, "Waste_Percentage", value_title="Waste (% of purchase)", slot=1)
        with right:
            section("Consumption by weekday", "Difference from each food's own average consumption")
            index = df.assign(Difference=(df["Quantity_Consumed"] / df.groupby("Food")["Quantity_Consumed"]
                                          .transform("mean") - 1) * 100)
            by_day = index.groupby("Day_of_Week", as_index=False)["Difference"].mean()
            charts.bar(by_day, "Day_of_Week", "Difference", value_title="Difference from average (%)",
                       category_title="Weekday", horizontal=False, sort=WEEKDAYS, value_format="+.1f", height=260)
            if df["Is_Festival"].nunique() > 1:
                festival = index.groupby("Is_Festival")["Difference"].mean()
                st.caption(f"Festival days: {festival.get(1, float('nan')):+.1f}% against each food's average; "
                           f"other days {festival.get(0, float('nan')):+.1f}%.")
    elif source == "m5":
        left, right = st.columns(2, gap="large")
        with left:
            section("Distribution of daily unit sales", "Units sold per item per day")
            charts.histogram(df, "Quantity_Sold", value_title="Units sold per item-day", bins=40)
        with right:
            section("Unit sales by weekday", "Mean units per item-day")
            by_day = df.groupby("Weekday", as_index=False, observed=True)["Quantity_Sold"].mean()
            charts.bar(by_day, "Weekday", "Quantity_Sold", value_title="Mean units per item-day", category_title="Weekday",
                       horizontal=False, sort=WEEKDAYS, value_format=".2f", height=260)
        section("Top 15 items by unit sales", "M5 item IDs; the dataset does not include product names")
        top_items = df.groupby("Product_ID", as_index=False, observed=True)["Quantity_Sold"].sum().nlargest(15, "Quantity_Sold")
        charts.bar(top_items, "Product_ID", "Quantity_Sold", value_title="Units sold", category_title="Item",
                   value_format=",.0f", height=380)
    else:
        left, right = st.columns(2, gap="large")
        with left:
            section("Top 15 products", "Order lines")
            top_products = df.groupby("Product_Name", as_index=False, observed=True).size().nlargest(15, "size")
            charts.bar(top_products, "Product_Name", "size", value_title="Order lines", category_title="Product",
                       value_format=",.0f", height=420)
        with right:
            section("Reorder rate by department", "Share of order lines the customer had bought before")
            reorder = df.groupby("Department", as_index=False, observed=True)["Reordered"].mean()
            reorder["Reorder rate"] = reorder["Reordered"] * 100
            charts.bar(reorder, "Department", "Reorder rate", value_title="Reorder rate (%)", category_title="Department",
                       value_format=".1f", height=420)
        section("Distribution of basket size", "Items per order")
        charts.histogram(frame, "Items per order", value_title="Items per order", bins=40)
