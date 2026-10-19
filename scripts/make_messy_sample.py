"""Generate data/samples/messy_food_data.csv: ~200 raw demo-format rows with deliberate problems.

Run from the project root:  python scripts/make_messy_sample.py
The output is deterministic (seed 2026). It is used by Data Quality > "Try the
cleaning pipeline" and by tests/test_cleaning.py. Each injected problem is
listed in PROBLEMS with the number of rows it affects.
"""

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "raw_food_data.csv"
TARGET = ROOT / "data" / "samples" / "messy_food_data.csv"
PROBLEMS = {
    "clean rows": 150,
    "exact duplicates": 10,
    "name case/spacing variants": 12,
    "case-variant duplicates (duplicate once names are tidied)": 3,
    "missing values": 8,
    "bad dates": 5,
    "negative quantities": 5,
    "text in numeric columns": 5,
    "expiry before purchase": 4,
    "outliers (valid, very large purchases)": 6,
}


def main() -> None:
    rng = np.random.default_rng(2026)
    base = pd.read_csv(SOURCE).sample(n=200, random_state=2026).reset_index(drop=True).astype(object)
    rows = base.iloc[:150].copy()
    pool = base.iloc[150:].reset_index(drop=True)
    take = iter(range(len(pool)))
    extra = []

    def nxt():
        return pool.iloc[next(take)].copy()

    extra += [rows.iloc[i].copy() for i in rng.choice(150, 10, replace=False)]  # exact duplicates
    for style in (str.lower, str.upper, lambda s: f"  {s} ", lambda s: s.replace(" ", "  ") if " " in s else s + " ") * 3:
        row = nxt(); row["Food"] = style(row["Food"]); extra.append(row)  # name variants
    for i in rng.choice(150, 3, replace=False):  # duplicates that only match after tidying names
        row = rows.iloc[i].copy(); row["Food"] = f" {row['Food'].upper()} "; extra.append(row)
    for column in ("Price", "Quantity_Consumed", "Date", "Expiry_Days", "Price", "Quantity_Wasted", "Price", "Is_Festival"):
        row = nxt(); row[column] = np.nan; extra.append(row)  # missing values
    for bad in ("2025-13-45", "31/02/2025", "not recorded", "2025/1/1/1", "yesterday"):
        row = nxt(); row["Date"] = bad; extra.append(row)  # bad dates
    for column in ("Quantity_Wasted", "Quantity_Consumed", "Price", "Quantity_Remaining", "Quantity_Purchased"):
        row = nxt(); row[column] = -abs(float(row[column]) or 1.0); extra.append(row)  # negatives
    for column, text in (("Quantity_Purchased", "two"), ("Price", "₹120"), ("Quantity_Consumed", "1,5"),
                         ("Expiry_Days", "a week"), ("Quantity_Wasted", "none")):
        row = nxt(); row[column] = text; extra.append(row)  # text in numeric columns
    for _ in range(4):
        row = nxt()
        row["Estimated_Expiry_Date"] = (pd.Timestamp(row["Date"]) - pd.Timedelta(days=3)).strftime("%Y-%m-%d")
        extra.append(row)  # expiry before purchase
    for factor in (8, 10, 12, 9, 15, 11):  # outliers: valid but very large purchases (balance kept)
        row = nxt()
        for column in ("Quantity_Purchased", "Quantity_Consumed", "Quantity_Wasted"):
            row[column] = round(float(row[column]) * factor, 2)
        row["Quantity_Remaining"] = round(row["Quantity_Purchased"] - row["Quantity_Consumed"] - row["Quantity_Wasted"], 2)
        row["Price"] = round(float(row["Price"]) * factor, 2)
        extra.append(row)

    messy = pd.concat([rows, pd.DataFrame(extra)], ignore_index=True)
    messy = messy.sample(frac=1, random_state=7).reset_index(drop=True)
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    messy.to_csv(TARGET, index=False)
    print(f"Wrote {len(messy)} rows to {TARGET.relative_to(ROOT)}")
    for name, count in PROBLEMS.items():
        print(f"  {count:>3}  {name}")


if __name__ == "__main__":
    main()
