# Dataset licences and what FORAGE publishes

Checked on 19 October 2026 before deciding whether derived extracts may be committed for the online app.

## M5 Forecasting (Walmart, via Kaggle)

- Source: <https://www.kaggle.com/competitions/m5-forecasting-accuracy/rules>. The data was provided by Walmart for the Kaggle M5 competition.
- The competition rules, as indexed by search, limit the Competition Data to **non-commercial purposes only**: participating in the competition, Kaggle forums, and **academic research and education**.
- The rules page renders with JavaScript and could not be fetched, so its clause on redistributing the Competition Data could not be read. No separate Walmart licence was found.

## Instacart Online Grocery Shopping Dataset 2017

- Source: Instacart's announcement, <https://tech.instacart.com/3-million-instacart-orders-open-sourced-d40d29ead6f2>. Download page: <https://www.instacart.com/datasets/grocery-shopping-2017>.
- The announcement states: "The dataset is provided as-is for non-commercial use … and is subject to our Terms and Conditions." Contact: open.data@instacart.com.
- The Terms and Conditions text could not be retrieved (the page returned 403), so no permission to redistribute could be confirmed.

## Decision (updated 20 October 2026)

The **raw and row-level data are not redistributed**: `dataset/` and `data/real/` stay git-ignored. The project owner decided to publish **aggregated results** instead, in `data/public/` (about 2 MB), so the online app can show the M5 and Instacart pages for academic and educational use with attribution:

- **M5 (`data/public/m5/`):** daily unit-sales totals for the 100 selected food items at store CA_1 over 180 days, with the item price and calendar fields used by the models. It contains no transaction data. It also holds every model result the pages show: metrics, rolling-origin folds, test-window predictions, residuals, permutation importance and hypothesis tests.
- **Instacart (`data/public/instacart/`):** aggregates only. These are counts and reorder rates by department, aisle and product (products with 50+ order lines), basket-size and day/hour distributions, per-order summary statistics and correlations, the association rules table and the χ² test. There are **no user IDs and no order-level rows**, and a test enforces this.

Each folder has a `manifest.json` with the source, licence note, attribution, build date, row counts and a SHA-256 hash per file. The app shows the attribution under **Source & licence** in the sidebar.

- **Locally (raw files present):** download both datasets yourself, accept their terms, place them in `dataset/` and run `python src/real_data_processor.py`. The pages then compute everything from the extracts. Run `python scripts/build_public_artifacts.py` to refresh `data/public/`.
- **Online (no raw files):** the pages read `data/public/` and note that results were computed offline on the full dataset.

If Kaggle, Walmart or Instacart object, delete `data/public/m5` or `data/public/instacart` and redeploy. Those pages then say the results have not been built.
