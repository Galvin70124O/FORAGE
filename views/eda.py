"""EDA: descriptive statistics, category frequencies, correlations and the main patterns."""

import streamlit as st

from services.data import source_tests
from stats import (
    correlation_matrix,
    describe_strength,
    descriptive_statistics,
    frequency_table,
    strongest_correlations,
)
from ui import charts
from ui.components import count, methods, number, section, table
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


M5_NOTE = "Each record is one item on one day at store CA_1."
M5_OFFLINE_NOTE = (" Computed offline on the full dataset; prices are not published online, so price is not "
                   "among the variables here.")


INSTACART_NOTE = ("Statistics are per order (one row per order). Days since previous order is blank for first orders "
                  "and capped at 30 by Instacart, which is why its mode and maximum are both 30.")


source, df = begin("EDA", "Descriptive statistics, category frequencies, correlations and the main patterns "
                   "in the selected source.")
methods(['Descriptive statistics summarise each variable: the mode is the most frequent value, the IQR is the spread of the middle half. Pearson r runs from −1 to 1 and does not show cause.',
         "Each hypothesis test asks whether a difference could be chance (H0). p < 0.05 means it is unlikely to be chance; the effect size (Cohen's d, η², Cramér's V) says how big it is."])

if df is not None:
    if source == "instacart":  # aggregates only: the order lines are never published
        stat_columns, frequency_title, derived_pairs, note = (df.values["order_columns"], "Order lines per department",
                                                              set(), INSTACART_NOTE)
        stats, frequencies, corr = df.order_statistics, df.frequency, df.correlation
    elif source == "m5":  # aggregates of the item-day extract (item rows are never published)
        stat_columns, frequency_title, derived_pairs = df.values["stat_columns"], "Item-days per department", set()
        note = M5_NOTE + (M5_OFFLINE_NOTE if df.offline else "")
        stats, frequencies, corr = df.statistics, df.frequency, df.correlation
    else:
        configs = {"demo": household_config, "personal": household_config}
        frame, stat_columns, category, frequency_title, derived_pairs, note = configs[source](df)
        stats = descriptive_statistics(frame, stat_columns).reset_index()
        frequencies = frequency_table(df[category], label=category).reset_index()
        corr = correlation_matrix(frame, stat_columns)

    stats_tab, tests_tab, patterns_tab = st.tabs(["Descriptive statistics", "Statistical tests", "Patterns"])
    with stats_tab:
        st.caption(note + " Missing values are excluded from each statistic and counted separately. "
                   "Std is the sample standard deviation; IQR = Q3 − Q1; the mode is the most frequent recorded value.")
        table(stats, {
            "Column": "Variable", "Count": count("Count"), "Missing": count("Missing"),
            **{name: number(name, "%.2f") for name in ["Mean", "Median", "Mode", "Std", "Min", "Max", "Q1", "Q3", "IQR"]},
        })

        left, right = st.columns([1, 1.35], gap="large")
        with left:
            section("Frequency table", frequency_title)
            table(frequencies, {"Count": count("Count"), "Share (%)": number("Share (%)", "%.1f")})
        with right:
            section("Correlation matrix", "Pearson r between the variables above")
            charts.correlation_heatmap(corr, height=380)
            st.caption("Blue is positive, red is negative, grey is no linear relationship.")
            top = strongest_correlations(corr, 1, exclude_pairs=derived_pairs)
            if not top.empty:
                pair = top.iloc[0]
                first, second = (name.split(" (")[0].lower() for name in (pair["First"], pair["Second"]))
                excluded = " (ignoring pairs where one variable is calculated from the other)" if derived_pairs else ""
                strength = describe_strength(pair["r"])
                if strength == "no meaningful":
                    st.markdown(f"**Reading:** no pair of variables{excluded} is meaningfully correlated; the largest "
                                f"is between {first} and {second} (r = {pair['r']:.2f}).")
                else:
                    st.markdown(f"**Reading:** the strongest relationship{excluded} is a {strength} correlation between "
                                f"{first} and {second} (r = {pair['r']:.2f}). Correlation does not show cause.")
                if source in ("demo", "personal"):
                    st.caption("Correlations between raw quantities partly reflect that some foods are bought in larger "
                               "amounts than others.")

    with tests_tab:
        if source == "personal":
            from hypothesis import household_tests
            from services.personal import gate
            from views.common import PERIOD_NOTE
            shown, reliable, note = gate("tests")
            st.caption(PERIOD_NOTE + " The weekend vs weekday t-test is therefore not run on My data.")
            if not shown:
                st.write(note)
            else:
                if not reliable:
                    st.warning(note)
                tests_section.render(household_tests(df, daily=False), source=source)
        else:
            tests_section.render(source_tests(source), source=source)

    with patterns_tab:
        if source == "personal":
            from views.common import PERIOD_NOTE
            section("Distribution of waste per period", "Waste as a share of what was available in each period")
            charts.histogram(df.dropna(subset=["Waste_Percentage"]), "Waste_Percentage",
                             value_title="Waste (% of available)", slot=1, bins=20)
            st.caption(PERIOD_NOTE)
        elif source == "demo":
            left, right = st.columns(2, gap="large")
            with left:
                charts.histogram(df, "Waste_Percentage", value_title="Waste (% of purchase)",
                                 title=f"Half of all purchases waste more than {df['Waste_Percentage'].median():.0f}%",
                                 subtitle="Distribution of waste as a share of each purchase")
            with right:
                index = df.assign(Difference=(df["Quantity_Consumed"] / df.groupby("Food")["Quantity_Consumed"]
                                              .transform("mean") - 1) * 100)
                by_day = index.groupby("Day_of_Week", as_index=False)["Difference"].mean()
                busiest = by_day.loc[by_day["Difference"].idxmax()]
                charts.bar(by_day, "Day_of_Week", "Difference", value_title="Difference from average (%)",
                           category_title="Weekday", horizontal=False, sort=WEEKDAYS, value_format="+.1f",
                           title=f"{busiest['Day_of_Week']} is the biggest eating day: {busiest['Difference']:+.1f}% "
                                 "above average",
                           subtitle="Consumption relative to each food's own average")
                if df["Is_Festival"].nunique() > 1:
                    festival = index.groupby("Is_Festival")["Difference"].mean()
                    st.caption(f"Festival days: {festival.get(1, float('nan')):+.1f}% against each food's average; "
                               f"other days {festival.get(0, float('nan')):+.1f}%.")
        elif source == "m5":
            left, right = st.columns(2, gap="large")
            with left:
                charts.histogram(df.units_distribution, "Units", value_title="Units sold per item-day", bins=40,
                                 weight="Item_days", count_title="Item-days",
                                 title=f"Most item-days sell fewer than {df.values['units_q75']:.0f} units",
                                 subtitle="Distribution of units sold per item per day; 3 in 4 item-days are below that")
            with right:
                charts.bar(df.weekday, "Weekday", "Mean_Units", value_title="Mean units per item-day",
                           category_title="Weekday", horizontal=False, sort=WEEKDAYS, value_format=".1f",
                           highlight=["Saturday", "Sunday"],
                           title=f"Weekends sell {df.values['weekend_uplift_pct']:.0f}% more per item",
                           subtitle="Mean units sold per item-day")
            section("Top 10 items by unit sales", "M5 item IDs; the dataset does not include product names")
            top_items = df.top_items_weekly.groupby("Product_ID", as_index=False)["Units"].sum().nlargest(10, "Units")
            charts.bar(top_items, "Product_ID", "Units", value_title="Units sold", category_title="Item",
                       value_format=",.0f", height=300)
        else:
            left, right = st.columns(2, gap="large")
            with left:
                section("Top 15 products", "Order lines")
                top_products = df.products.nlargest(15, "Order_Lines")
                charts.bar(top_products, "Product_Name", "Order_Lines", value_title="Order lines",
                           category_title="Product", value_format=",.0f", height=420)
            with right:
                reorder = df.departments.rename(columns={"Reorder_Rate": "Reorder rate"})
                top = reorder.loc[reorder["Reorder rate"].idxmax()]
                charts.bar(reorder, "Department", "Reorder rate", value_title="Reorder rate (%)",
                           category_title="Department", value_format=".0f",
                           title=f"{top['Department'].capitalize()} is reordered most often ({top['Reorder rate']:.0f}%)",
                           subtitle="Share of order lines the customer had bought before")
            left, right = st.columns(2, gap="large")
            with left:
                charts.histogram(df.basket_sizes, "Items per order", value_title="Items per order", bins=40,
                                 weight="Orders", count_title="Orders",
                                 title=f"A typical order has {df.values['items_per_order']:.0f} items",
                                 subtitle="Distribution of basket size (items per order)")
            with right:
                by_hour = df.day_hour.groupby("Hour", as_index=False)["Orders"].sum()
                peak = by_hour.loc[by_hour["Orders"].idxmax()]
                charts.bar(by_hour, "Hour", "Orders", value_title="Orders", category_title="Hour of day",
                           horizontal=False, sort=list(range(24)), value_format=",.0f", labels=False,
                           title=f"Orders peak at {int(peak['Hour'])}:00",
                           subtitle="Orders by hour of day")
