"""Exploratory data analysis for the Food Demand and Supply (FDS) dataset.

Run from the project root with:
    python src/analysis.py

The script reads only the cleaned dataset, prints calculated descriptive results,
and saves a small set of useful charts in outputs/eda/.
"""

from pathlib import Path

import matplotlib
import pandas as pd

# Save charts directly to files; this works in terminals without a desktop GUI.
matplotlib.use("Agg")
import matplotlib.pyplot as plt


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PATH = PROJECT_ROOT / "data" / "cleaned_food_data.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "eda"

QUANTITY_COLUMNS = [
    "Quantity_Purchased",
    "Quantity_Consumed",
    "Quantity_Wasted",
    "Remaining_Quantity",
]
NUMERIC_COLUMNS = QUANTITY_COLUMNS + [
    "Price",
    "Expiry_Days",
    "Waste_Percentage",
    "Consumption_Rate",
]


def print_table(title, table, rows=None):
    """Print a labelled table without changing the underlying analysis values."""
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")
    if rows is not None:
        table = table.head(rows)
    print(table.to_string())


def load_data():
    """Load the cleaned data and parse the purchase date."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Cleaned dataset not found: {DATA_PATH}")
    return pd.read_csv(DATA_PATH, parse_dates=["Date"])


def dataset_overview(df):
    """Print dataset structure, quality checks, and general numeric summaries."""
    print("FDS EXPLORATORY DATA ANALYSIS")
    print(f"Dataset shape: {df.shape[0]:,} rows x {df.shape[1]} columns")
    print(f"Date range: {df['Date'].min():%Y-%m-%d} to {df['Date'].max():%Y-%m-%d}")
    print(f"Unique foods: {df['Food'].nunique()} | Categories: {df['Category'].nunique()}")

    column_info = pd.DataFrame({
        "Data_Type": df.dtypes.astype(str),
        "Missing_Values": df.isna().sum(),
    })
    print_table("COLUMNS, DATA TYPES, AND MISSING VALUES", column_info)
    print_table("BASIC SUMMARY STATISTICS", df[NUMERIC_COLUMNS].describe().round(2))


def descriptive_statistics(df):
    """Calculate the requested central tendency and spread measures."""
    summary = df[NUMERIC_COLUMNS].agg(["mean", "median", "std", "min", "max"]).T
    quartiles = df[NUMERIC_COLUMNS].quantile([0.25, 0.75]).T
    quartiles.columns = ["Q1 (25%)", "Q3 (75%)"]
    summary = summary.join(quartiles)
    print_table("DESCRIPTIVE STATISTICS", summary.round(2))


def consumption_analysis(df):
    """Examine consumption totals and average consumption by food/category."""
    print_table(
        "CONSUMPTION TOTAL",
        pd.DataFrame({"Total_Recorded_Consumption": [df["Quantity_Consumed"].sum()]})
        .round(2),
    )

    by_food = df.groupby("Food")["Quantity_Consumed"].agg(
        Total_Consumed="sum", Average_Consumed="mean"
    ).sort_values("Total_Consumed", ascending=False)
    by_category = df.groupby("Category")["Quantity_Consumed"].agg(
        Total_Consumed="sum", Average_Consumed="mean"
    ).sort_values("Total_Consumed", ascending=False)
    print_table("CONSUMPTION BY FOOD", by_food.round(2))
    print_table("CONSUMPTION BY CATEGORY", by_category.round(2))
    print_table("HIGHEST CONSUMED FOODS", by_food.round(2), rows=5)
    print_table("LOWEST CONSUMED FOODS", by_food.sort_values("Total_Consumed").round(2), rows=5)
    return by_food, by_category


def waste_analysis(df):
    """Measure food waste in recorded quantities and as a purchase percentage."""
    total_waste = df["Quantity_Wasted"].sum()
    total_purchased = df["Quantity_Purchased"].sum()
    waste_overall = pd.DataFrame({
        "Total_Recorded_Waste": [total_waste],
        "Average_Waste_Per_Record": [df["Quantity_Wasted"].mean()],
        "Overall_Waste_Percentage": [total_waste / total_purchased * 100],
    })
    print_table("WASTE OVERVIEW", waste_overall.round(2))

    by_food = df.groupby("Food").agg(
        Total_Waste=("Quantity_Wasted", "sum"),
        Average_Waste=("Quantity_Wasted", "mean"),
        Waste_Percentage=("Quantity_Wasted", lambda x: x.sum() / df.loc[x.index, "Quantity_Purchased"].sum() * 100),
    ).sort_values("Total_Waste", ascending=False)
    by_category = df.groupby("Category").agg(
        Total_Waste=("Quantity_Wasted", "sum"),
        Average_Waste=("Quantity_Wasted", "mean"),
        Waste_Percentage=("Quantity_Wasted", lambda x: x.sum() / df.loc[x.index, "Quantity_Purchased"].sum() * 100),
    ).sort_values("Total_Waste", ascending=False)
    print_table("WASTE BY FOOD", by_food.round(2))
    print_table("WASTE BY CATEGORY", by_category.round(2))
    print_table("HIGHEST-WASTE FOODS", by_food.round(2), rows=5)
    return by_food, by_category


def purchase_vs_consumption(df):
    """Compare purchasing behaviour with subsequent consumption."""
    comparison = df.groupby("Food").agg(
        Average_Purchased=("Quantity_Purchased", "mean"),
        Average_Consumed=("Quantity_Consumed", "mean"),
        Purchase_Exceeds_Consumption_Rate=("Quantity_Purchased", lambda x: (x > df.loc[x.index, "Quantity_Consumed"]).mean() * 100),
    )
    comparison["Average_Excess_Purchased"] = (
        comparison["Average_Purchased"] - comparison["Average_Consumed"]
    )
    comparison = comparison.sort_values("Average_Excess_Purchased", ascending=False)
    print_table("PURCHASE VS CONSUMPTION BY FOOD", comparison.round(2))
    consistently_higher = comparison[
        comparison["Purchase_Exceeds_Consumption_Rate"] == 100
    ]
    print_table("FOODS WHERE PURCHASED QUANTITY ALWAYS EXCEEDS CONSUMED QUANTITY", consistently_higher.round(2))
    return comparison


def time_based_analysis(df):
    """Summarise monthly, weekend, and festival consumption/waste patterns."""
    monthly = df.groupby("Month").agg(
        Total_Consumption=("Quantity_Consumed", "sum"),
        Total_Waste=("Quantity_Wasted", "sum"),
    )
    day_type = df.assign(Day_Type=df["Is_Weekend"].map({0: "Weekday", 1: "Weekend"})).groupby("Day_Type").agg(
        Average_Consumption=("Quantity_Consumed", "mean"),
        Total_Consumption=("Quantity_Consumed", "sum"),
        Records=("Quantity_Consumed", "size"),
    ).reindex(["Weekday", "Weekend"])
    festival = df.assign(Event_Type=df["Is_Festival"].map({0: "Non-festival", 1: "Festival"})).groupby("Event_Type").agg(
        Average_Consumption=("Quantity_Consumed", "mean"),
        Total_Consumption=("Quantity_Consumed", "sum"),
        Average_Waste=("Quantity_Wasted", "mean"),
        Records=("Quantity_Consumed", "size"),
    ).reindex(["Non-festival", "Festival"])
    print_table("MONTHLY CONSUMPTION AND WASTE", monthly.round(2))
    print_table("WEEKDAY VS WEEKEND CONSUMPTION", day_type.round(2))
    print_table("FESTIVAL VS NON-FESTIVAL CONSUMPTION", festival.round(2))
    return monthly, day_type, festival


def correlation_analysis(df):
    """Calculate correlations among the numeric FDS measures."""
    correlation = df[NUMERIC_COLUMNS].corr()
    print_table("NUMERIC CORRELATION MATRIX", correlation.round(2))
    return correlation


def create_visualizations(df, consumption_by_food, waste_by_food, monthly, correlation):
    """Save six targeted charts that support FDS purchasing and waste decisions."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")

    def save_current_plot(filename):
        plt.tight_layout()
        plt.savefig(OUTPUT_DIR / filename, dpi=150, bbox_inches="tight")
        plt.close()

    top_consumed = consumption_by_food.head(10).sort_values("Total_Consumed")
    top_consumed["Total_Consumed"].plot.barh(color="#2a9d8f")
    plt.title("Top 10 Foods by Recorded Consumption")
    plt.xlabel("Total recorded quantity")
    plt.ylabel("Food")
    save_current_plot("top_consumed_foods.png")

    top_waste = waste_by_food.head(10).sort_values("Total_Waste")
    top_waste["Total_Waste"].plot.barh(color="#e76f51")
    plt.title("Top 10 Foods by Recorded Waste")
    plt.xlabel("Total recorded quantity")
    plt.ylabel("Food")
    save_current_plot("top_waste_foods.png")

    monthly[["Total_Consumption", "Total_Waste"]].plot(marker="o")
    plt.title("Monthly Consumption and Waste")
    plt.xlabel("Month")
    plt.ylabel("Total recorded quantity")
    plt.xticks(range(1, 13))
    save_current_plot("monthly_consumption_waste.png")

    plt.scatter(df["Quantity_Purchased"], df["Quantity_Consumed"], alpha=0.25, color="#457b9d")
    maximum = max(df["Quantity_Purchased"].max(), df["Quantity_Consumed"].max())
    plt.plot([0, maximum], [0, maximum], "--", color="gray", label="Purchased = consumed")
    plt.title("Purchased vs Consumed Quantity")
    plt.xlabel("Quantity purchased")
    plt.ylabel("Quantity consumed")
    plt.legend()
    save_current_plot("purchased_vs_consumed.png")

    fig, ax = plt.subplots(figsize=(10, 8))
    image = ax.imshow(correlation, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_xticks(range(len(correlation.columns)), correlation.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(correlation.index)), correlation.index)
    for row in range(len(correlation.index)):
        for column in range(len(correlation.columns)):
            ax.text(column, row, f"{correlation.iloc[row, column]:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=ax, label="Correlation")
    ax.set_title("Correlation of FDS Numeric Measures")
    save_current_plot("numeric_correlations.png")

    category_waste = df.groupby("Category").apply(
        lambda group: group["Quantity_Wasted"].sum() / group["Quantity_Purchased"].sum() * 100,
        include_groups=False,
    ).sort_values()
    category_waste.plot.barh(color="#f4a261")
    plt.title("Waste Percentage by Category")
    plt.xlabel("Waste as % of purchased quantity")
    plt.ylabel("Category")
    save_current_plot("category_waste_percentage.png")

    print(f"\nSaved 6 visualizations to: {OUTPUT_DIR}")


def main():
    """Run the complete descriptive and exploratory analysis."""
    df = load_data()
    dataset_overview(df)
    descriptive_statistics(df)
    consumption_by_food, _ = consumption_analysis(df)
    waste_by_food, _ = waste_analysis(df)
    purchase_vs_consumption(df)
    monthly, _, _ = time_based_analysis(df)
    correlation = correlation_analysis(df)
    create_visualizations(df, consumption_by_food, waste_by_food, monthly, correlation)
    print("\nNote: quantities use their recorded units (kg, L, dozen, loaf, or pack).")
    print("Do not interpret totals across different units as one physical unit.")


if __name__ == "__main__":
    main()
