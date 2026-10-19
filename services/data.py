"""Cached data loaders and model results shared by every view."""


import pandas as pd
import streamlit as st


from prediction import (
    build_models,
    chronological_split,
    create_forecasting_features,
    evaluate_predictions,
    load_data,
)
from recommendations import (
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    NUMERIC_FEATURES,
    generate_recommendations,
)
from m5_forecasting import forecast_retail_demand
from dataset_registry import get_dataset



DATA_PATH = get_dataset("demo")["path"]

M5_DATA_PATH = get_dataset("m5")["path"]

INSTACART_DATA_PATH = get_dataset("instacart")["path"]

M5_QUALITY_PATH = M5_DATA_PATH.parent / "quality_report.json"

INSTACART_QUALITY_PATH = INSTACART_DATA_PATH.parent / "quality_report.json"

@st.cache_data
def get_cleaned_data():
    return pd.read_csv(DATA_PATH, parse_dates=["Date", "Estimated_Expiry_Date"])


@st.cache_data
def get_m5_data():
    """Load only the one-time M5 extract, never the raw wide M5 files."""
    return pd.read_csv(M5_DATA_PATH, parse_dates=["Date"], dtype={
        "Product_ID": "category", "Store_ID": "category", "Department": "category",
        "Category": "category", "Quantity_Sold": "int16", "Price": "float32",
        "Weekday": "category", "Month": "int8", "Event_Name": "category", "Event_Type": "category",
    })


@st.cache_data
def get_instacart_data():
    """Load only the one-time Instacart relational extract."""
    return pd.read_csv(INSTACART_DATA_PATH, dtype={
        "Order_ID": "int32", "User_ID": "int32", "Order_Set": "category",
        "Order_Number": "int16", "Order_Day_Of_Week": "int8", "Order_Hour": "int8",
        "Days_Since_Prior_Order": "float32", "Product_ID": "int32", "Product_Name": "category",
        "Aisle": "category", "Department": "category", "Add_To_Cart_Order": "int16", "Reordered": "int8",
    })


@st.cache_data(show_spinner="Evaluating the chronological retail-demand test period...")
def get_m5_forecast_results():
    return forecast_retail_demand(get_m5_data())


@st.cache_data(show_spinner="Evaluating forecasting models on the chronological test period...")
def get_forecast_results():
    """Reuse the tested forecasting logic from prediction.py."""
    raw_df = load_data()
    featured_df = create_forecasting_features(raw_df)
    train_df, test_df, cutoff_date = chronological_split(featured_df)
    x_train, x_test = train_df[FEATURE_COLUMNS], test_df[FEATURE_COLUMNS]
    y_train, y_test = train_df["Quantity_Consumed"], test_df["Quantity_Consumed"]

    predictions = {"Moving Average": test_df["Rolling_Mean_7"]}
    for model_name, model in build_models(NUMERIC_FEATURES, CATEGORICAL_FEATURES).items():
        model.fit(x_train, y_train)
        predictions[model_name] = pd.Series(model.predict(x_test), index=x_test.index)

    comparison = pd.DataFrame(
        [{"Model": name, **evaluate_predictions(y_test, values)} for name, values in predictions.items()]
    ).sort_values("MAE").reset_index(drop=True)
    best_model = comparison.loc[0, "Model"]
    chart_data = test_df[["Date", "Food", "Quantity_Unit", "Quantity_Consumed"]].copy()
    chart_data["Predicted_Consumption"] = predictions[best_model]
    return comparison, chart_data, best_model, pd.Timestamp(cutoff_date)


@st.cache_data(show_spinner="Preparing explainable purchase recommendations...")
def get_recommendations():
    return generate_recommendations()[0]


def quantity_summary(df, quantity_column):
    return df.groupby(["Food", "Quantity_Unit"], as_index=False)[quantity_column].sum().sort_values(quantity_column, ascending=False)
