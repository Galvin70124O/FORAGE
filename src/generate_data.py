import pandas as pd
import numpy as np

np.random.seed(42)

foods = [
    ("Rice", "Grains", 5, 2, 90, "Pantry", "kg"),
    ("Wheat Flour", "Grains", 4, 1.5, 90, "Pantry", "kg"),
    ("Bread", "Bakery", 2, 1.2, 5, "Pantry", "loaf"),
    ("Milk", "Dairy", 3, 2.2, 7, "Refrigerator", "L"),
    ("Curd", "Dairy", 2, 1.3, 7, "Refrigerator", "kg"),
    ("Cheese", "Dairy", 1, 0.5, 30, "Refrigerator", "kg"),
    ("Eggs", "Protein", 2, 1.2, 21, "Refrigerator", "dozen"),
    ("Chicken", "Protein", 2, 1.3, 3, "Refrigerator", "kg"),
    ("Tomato", "Vegetables", 2, 1.3, 7, "Refrigerator", "kg"),
    ("Potato", "Vegetables", 3, 1.5, 30, "Pantry", "kg"),
    ("Onion", "Vegetables", 3, 1.5, 30, "Pantry", "kg"),
    ("Carrot", "Vegetables", 2, 1.0, 14, "Refrigerator", "kg"),
    ("Spinach", "Vegetables", 1.5, 0.7, 5, "Refrigerator", "kg"),
    ("Apple", "Fruits", 2, 1.0, 14, "Refrigerator", "kg"),
    ("Banana", "Fruits", 2, 1.2, 6, "Pantry", "dozen"),
    ("Orange", "Fruits", 2, 1.0, 14, "Refrigerator", "kg"),
    ("Biscuit", "Snacks", 2, 0.8, 60, "Pantry", "pack"),
    ("Cooking Oil", "Essentials", 2, 0.4, 180, "Pantry", "L"),
    ("Sugar", "Essentials", 2, 0.5, 180, "Pantry", "kg"),
    ("Dal", "Pulses", 3, 1.0, 180, "Pantry", "kg")
]

dates = pd.date_range("2025-01-01", "2025-12-31")

rows = []

for date in dates:

    weekend = date.weekday() >= 5

    festival = (
        date.month in [1, 8, 10, 11]
        and date.day in [1, 15, 20]
    )

    input_method = np.random.choice(["Receipt OCR", "Manual Entry"], p=[0.7, 0.3])
    source_reference = (
        f"RCT-{date:%Y%m%d}" if input_method == "Receipt OCR"
        else f"MAN-{date:%Y%m%d}"
    )

    for food, category, purchase, consume, expiry, storage, unit in foods:

        purchased = max(
            0.1,
            purchase * np.random.normal(1, 0.15)
        )

        consumption = consume * np.random.normal(1, 0.12)

        if weekend and food in ["Milk", "Bread", "Eggs", "Chicken"]:
            consumption *= 1.15

        if festival:
            consumption *= 1.20

        consumed = min(
            purchased,
            max(0.1, consumption)
        )

        wasted = max(
            0,
            purchased - consumed
        ) * np.random.uniform(0.2, 0.7)

        remaining = max(0, purchased - consumed - wasted)

        price = round(
            purchase * np.random.uniform(20, 150),
            2
        )

        rows.append([
            date,
            food,
            category,
            input_method,
            source_reference,
            unit,
            round(purchased, 2),
            round(consumed, 2),
            round(wasted, 2),
            round(remaining, 2),
            price,
            expiry,
            (date + pd.Timedelta(days=expiry)).date(),
            storage,
            int(festival)
        ])

columns = [
    "Date",
    "Food",
    "Category",
    "Input_Method",
    "Source_Reference",
    "Quantity_Unit",
    "Quantity_Purchased",
    "Quantity_Consumed",
    "Quantity_Wasted",
    "Quantity_Remaining",
    "Price",
    "Expiry_Days",
    "Estimated_Expiry_Date",
    "Storage_Type",
    "Is_Festival"
]

df = pd.DataFrame(rows, columns=columns)

df.to_csv("data/raw_food_data.csv", index=False)

print("Dataset created successfully!")
print("Rows:", len(df))
print("Columns:", len(df.columns))
print(df.head())
