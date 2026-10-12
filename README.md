# FORAGE — Food Demand and Supply

FORAGE keeps four deliberately separate data models.

| Data source | Purpose | Used by |
| --- | --- | --- |
| Synthetic development dataset | 7,300 simulated household-style records (20 foods × 365 days); useful for demonstrating consumption, waste and inventory workflows, but not real-world evidence. | General Insights, Consumption, Waste, Forecast, Recommendations |
| Personal data | Records manually entered or deliberately imported by the user. | My Stats and personal signals |
| M5 / Walmart | External real-world retail unit-sales data. It is retail demand, not household consumption or waste. | M5 Demand and Retail Demand Forecasting |
| Instacart | External real-world market-basket/order data. It is purchase/reorder behavior, not consumption or waste. | Instacart Insights |

## Real-data preprocessing

Raw downloads remain under `dataset/` and are never modified. The processor locates nested CSVs automatically, uses chunked reads, and writes only small derived CSVs plus quality reports:

```powershell
python src/real_data_processor.py
```

Outputs are `data/real/m5/m5_food_demand.csv` and
`data/real/instacart/instacart_purchase_history.csv`.

M5 processing selects the actual `FOODS_1`, `FOODS_2`, and `FOODS_3` departments at store `CA_1`, the 100 highest-selling M5 items over the final 180 available training days, maps `d_*` fields through `calendar.csv`, and joins weekly sell prices. Values such as `FOODS_3_090` are original M5 item IDs, not inferred food names. The extracted M5 table has Date, product/store/department/category identifiers, `Quantity_Sold`, price, weekday/month, and source event metadata. No household consumption, measured food-waste, household-inventory, or expiry fields are created.

Instacart processing joins orders, prior/train order products, products, aisles, and departments. To keep a responsive local dashboard it uses the deterministic public-data subset of users with IDs 1–2,000 and their available order lines. Timing fields remain order day-of-week/order hour; no calendar date is invented.

Quality reports record missing values, duplicate relationship keys, join failures, invalid values, selection criteria, and rows written. Suspicious records are reported rather than silently deleted.

## Forecasting

The original household forecast continues to target `Quantity_Consumed`. The separate M5 forecast targets only `Quantity_Sold`, uses chronological train/test splits, prior-sales lags, shifted rolling demand, weekday/month and known price features, and reports MAE, RMSE, and R². It does not use future target values.

## Run the dashboard

```powershell
python -m streamlit run app.py
```

The project requires the packages listed in `requirements.txt`; no new dependency was needed for real-data support.

## Limitations

M5 prices are weekly and can be missing for item/week combinations. M5 provides retail unit sales, dates/calendar and item/category information for retail-demand forecasting, but not household consumption, measured food waste, household inventory, or expiry dates. Instacart describes orders and reorders, not quantities, household inventory, consumption, waste, or real dates. The two public-data extracts are intentionally bounded for a Streamlit project and are not a complete representation of either raw dataset.

## Data integrity and workflow

The demo CSVs are `data/raw_food_data.csv` and `data/cleaned_food_data.csv`. They contain 7,300 simulated household-style records and are available only through an explicitly labeled **Demo / Synthetic Data** selector. They must never be interpreted as real business or user evidence.

`data/my_food_data.csv` is the separate personal-data store. **My Stats** reads this store only; with no records it presents “No personal food data yet,” rather than demo KPIs or placeholder charts. A generic CSV becomes personal data only after the user explicitly reviews its mapping and selects the import action.

The Dataset Quality screen has three routes: report on the bounded M5 extract, report on the bounded Instacart extract, or inspect a generic uploaded food CSV. Generic inspection reports columns, types, missing values, duplicates, invalid dates/numerics, invalid negatives, IQR-flagged outliers, useful unique values, and schema mapping. It flags outliers rather than deleting legitimate observations.

M5 forecasting targets only `Quantity_Sold`. Moving Average, Linear Regression, and Random Forest are evaluated on the same chronological unseen period using only past sales lags, shifted rolling sales, calendar fields, and price. MAE, RMSE, and R² are reported, and price imputation is fit from the training period only. Demo and personal forecasts remain separately labeled and never supply M5 metrics.

Instacart supports product popularity, order frequency, reorder behavior, aisle/department analysis, and order day/hour patterns. M5 supports retail demand history and forecasting. Neither supports household consumption, stock, expiry, physical household quantities, or food waste. Consequently the real-data Waste page reports that waste is not available instead of creating a proxy.

To add another public dataset with a fundamentally different schema, preserve its raw inputs under `dataset/`, create a bounded dataset-specific processor that writes a documented extract under `data/real/`, and add a source profile. Do not force unrelated source fields through the generic household schema.

## Project overview

FORAGE is a food-intelligence learning project that demonstrates a responsible analytical workflow for personal food records and public retail/market-basket datasets. Its purpose is to make data quality, source provenance, exploratory analysis, forecasting, and recommendations visible in one interface without treating unrelated datasets as interchangeable.

### Objectives

- ingest manually entered and CSV food records safely;
- inspect quality issues and map compatible schemas transparently;
- analyze recorded consumption and waste only where those fields exist;
- evaluate demand models chronologically; and
- present source-appropriate, explainable decision support.

## Data-science pipeline

```text
Data ingestion → Quality checks → Schema mapping → Safe cleaning →
Preprocessing → EDA/statistical & trend analysis → Forecasting →
Model evaluation → Explainable recommendations → Streamlit dashboard
```

## Architecture and sources

| Layer | Location | Responsibility |
| --- | --- | --- |
| Dashboard | `app.py` | Source-labelled Streamlit pages, themes, charts, and empty states |
| Source registry | `src/dataset_registry.py` | Allowed/prohibited uses for demo, personal, M5, and Instacart data |
| Generic ingestion | `src/dataset_loader.py`, `src/schema_mapper.py`, `src/data_quality.py` | Mapping, profiling, type checks, safe cleaning, and outlier flags |
| Personal store | `src/personal_data.py` | Persistent local records used exclusively by My Stats |
| M5/Instacart adapters | `src/real_data_processor.py` | Bounded, dataset-specific public-data extracts |
| Forecasting | `src/prediction.py`, `src/m5_forecasting.py` | Chronological model evaluation and metrics |
| Recommendations | `src/recommendations.py` | Inventory-aware, data-derived suggestions where fields support them |

### Dataset limits

M5 is Walmart retail unit-sales/demand data. Instacart describes market baskets, orders, and reorders. Neither dataset measures household consumption, household inventory, expiry, or food waste; those analyses are shown as unavailable rather than estimated. The demo CSVs are synthetic development material, clearly labelled in the UI, and are not evidence about real users or businesses.

## Quality, analysis, and recommendations

The generic import flow reports schema mapping, missing values, duplicates, invalid dates, non-numeric values, invalid negative values, and IQR outliers. It does not silently invent missing values or automatically discard legitimate outliers. Derived fields are created only when their source fields support them.

For M5, Moving Average, Linear Regression, and Random Forest are compared on a chronological held-out period using past-only lag and rolling features. MAE and RMSE are lower-is-better; R² is higher-is-better. The selected model is based on computed evaluation results, never hard-coded metrics.

Recommendations are statistical, not “AI magic”: personal recommendations use recorded demand, remaining stock, and observed waste when available; M5 reports expected retail demand; Instacart reports reorder patterns. Public sales/order data are never converted into a household grocery quantity.

## Local installation and run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

To build local real-data extracts after obtaining the source downloads, place them under `dataset/` and run:

```powershell
python src/real_data_processor.py
```

Raw public downloads, derived public extracts, personal records, logs, and generated outputs are deliberately ignored by Git. With those optional files absent, the related pages display an informative unavailable-data state; they do not substitute synthetic values.

## Deployment

The entry point for Streamlit Community Cloud is `app.py`. Commit the source code, `requirements.txt`, `.streamlit/config.toml` (if added), and the explicitly labelled demo data only if it is appropriate for the repository. Do not commit `dataset/`, `data/real/`, `data/my_food_data.csv`, `.streamlit/secrets.toml`, or any credentials. Configure the repository and deploy from the Community Cloud UI; no secrets are required for the current auth-disabled dashboard.

## Future scope

Potential extensions include user-authorized private storage, additional dataset adapters, reproducible download instructions for public sources, and stronger forecasting backtests. Each extension should preserve FORAGE’s data-source separation and avoid unsupported food-waste claims.
