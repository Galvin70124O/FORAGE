# FORAGE

FORAGE is a household food app and a data-science project in one.

- **Daily use:** a team logs what it buys and checks its pantry once a week, from a phone. FORAGE works out what was eaten and what was thrown away, warns before food expires, flags purchases that are likely to be wasted and says what to buy this week.
- **Insights:** public pages show the full analysis workflow on four sources it never mixes: data quality, statistics and hypothesis tests, waste in ₹, forecasting with baselines and backtests, explainable recommendations, and market-basket rules.

It is framed by UN SDG target 12.3: halve per-capita food waste by 2030. Fundamentals of Data Science project.

## Features

**Your food** (sign in with Google; personal and private):

- **Home:** ₹ wasted this month, waste rate, stock expiring in 3 days, food likely to be wasted at your usual pace, and what to buy this week.
- **I bought…:**
  - repeat chips for your 8 most frequent purchases, so a chip and Save logs a purchase
  - a food picker with recent items first, quantity steppers, and a date that defaults to today
  - paste-a-bill parsing, confirmed in a table before anything is saved
- **Pantry check:** a one-food form (two steppers) or the whole pantry, prefilled with what you should still have. Impossible entries are rejected with the arithmetic shown.
- **My data:** edit and delete entries (deletes ask for confirmation), export CSVs, and import CSVs, which skips rows you already have.

**Insights** (open to everyone), on the source chosen in the sidebar:

| Page | What it shows |
| --- | --- |
| Overview | 4 KPIs with month-on-month change, ₹ waste trend, top wasted foods, action list |
| Data Quality | Cleaning rules and rows removed per rule; outliers flagged and kept; "Try the cleaning pipeline" on a deliberately messy sample; for your data, how consumption is derived |
| EDA | Descriptive statistics (mean, median, mode, std, min, max, Q1, Q3, IQR), frequency tables, correlation heatmap; hypothesis tests (Welch t + Cohen's d, ANOVA + η² with Kruskal–Wallis, χ² + Cramér's V); patterns |
| Waste & Expiry | ₹ and % waste by month, category and food; expiring stock; waste against shelf life; waste-risk classifier |
| Forecasting | Next-day and 7-day forecasts against baselines, chosen by 5-fold rolling-origin backtests; actual against predicted; permutation importance and residuals |
| Recommendations | Daily and weekly purchase plans with waste-risk alerts, and a backtest of whether following them wastes less; M5 demand trends; Instacart repeat purchases and "bought together" rules |

Every analysis page has a **Methods** note explaining the technique in plain words. Every chart and table states its data source.

## Data sources

| Source | What it is | Licence / availability |
| --- | --- | --- |
| Demo data | 7,300 synthetic household records (20 foods × 365 days, 2025) made by `src/generate_data.py`. In the raw file, `Price` is the total paid per purchase, so price per unit = Price ÷ Quantity_Purchased. ₹ figures from it are labelled *illustrative (synthetic prices)*. | Ours; committed |
| My data | Each user's own purchases and pantry checks, in Neon Postgres (online) or a local SQLite file | Private to each Google account |
| M5 (Walmart) | Retail unit sales, store CA_1, the 100 best-selling food items, last 180 days | Kaggle competition rules: non-commercial use. Not redistributed; **local only** |
| Instacart | Online grocery orders from users 1–2,000 (313,404 order lines) | "Non-commercial use … subject to Instacart's Terms". Not redistributed; **local only** |

`docs/data_licences.md` records the licence check. To use M5 and Instacart locally, download them yourself into `dataset/` and run `python src/real_data_processor.py`. Online, those pages say "available in the local version".

**Definitions.**

- Waste is the *recorded* quantity thrown away, never purchased − consumed.
- Waste rate = wasted ÷ purchased per food, averaged across foods so units never mix.
- For your data, consumption is derived: consumed = previous remaining + bought − thrown away − remaining now, per food per pantry-check period. Impossible values are flagged, not corrected.
- Personal analyses unlock gradually and say "Not enough data yet (need N more weeks)" until there is enough. Day-level analyses don't run on weekly checks, and the app explains that this is a sample-size limit.

## Architecture

```text
app.py                     page config, logo, st.navigation (Your food / Insights), sidebar source + account
views/                     one file per page; *_section.py are shared renderers
services/
  data.py                  cached loaders and model results (st.cache_resource), precomputed-result lookup
  overview.py              dashboard KPIs, charts and actions
  session.py               secrets, mode, Google sign-in + allowlist, st.connection("sql")
  personal.py              signed-in user, cached personal reads (ttl 60 s, cleared after writes)
ui/                        theme (registered Altair theme, CSS), charts, components
src/                       analysis logic: pure functions, no Streamlit, unit-tested
  store.py                 the ONLY database module: every query filtered by user
  identity.py              who may use the personal pages (allowlist, local user only without [auth])
  pantry.py                purchases + checks -> periods, stock, expiry, buy list, bill parser, CSV import
  clean_data.py, data_quality.py, stats.py, hypothesis.py, waste.py
  prediction.py, m5_forecasting.py, horizon.py (7-day + rolling origin), recommendations.py, backtest.py
  waste_risk.py (classifier), explain.py (importance, residuals), basket.py (FP-growth), artifacts.py
scripts/                   init_db, check_database, precompute_demo, export_results, make_messy_sample,
                           crawl_pages, cloud_simulation
data/                      demo CSVs, messy sample, logging templates, precomputed demo results
docs/                      deploy.md, google_login_setup.md, data_licences.md
tests/                     pytest suite
```

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

With no `.streamlit/secrets.toml`, FORAGE runs in **demo mode**: one local user, entries in `data/forage_local.db` (git-ignored), and a banner saying the data is temporary. Everything works offline, which is useful for development and the viva.

To use sign-in and Neon locally, copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` and fill it in (see `docs/google_login_setup.md` and `docs/deploy.md`).

## How to log (for the team)

1. **Every time you shop**, open **I bought…**: tap a chip or pick the food, check the quantity and the *total* price paid, then Save. A new food asks once for its category and shelf life.
2. **Once a week** (more often is better), open **Pantry check**. For each food, enter what is left and what you threw away. The amounts are prefilled with what you should still have.
3. That's all. Consumption, waste, expiry warnings, buy lists and forecasts are worked out from these two records.
4. Bulk entry: fill `data/templates/purchases_template.csv` or `pantry_checks_template.csv`, then use **My data → Import**. Rows you already have are skipped, so teammates can merge their files.

## Tests and checks

```powershell
python -m pytest                      # 124 tests
python scripts/export_results.py      # outputs/results.json + report charts (git-ignored)
python scripts/precompute_demo.py     # after changing demo data or model code; a test fails if it is stale
python scripts/cloud_simulation.py    # fresh clone + fresh venv from requirements.txt, every page crawled
```

The tests cover:

- **Cleaning and data:** cleaning rules, statistics against scipy and hand calculations, and waste and ₹ formulas, including that waste is never computed for M5 or Instacart.
- **Forecasting:** leakage tests for lags, rolling means, the chronological split, the 7-day target and every rolling fold.
- **Models and outputs:** the backtest simulator on hand-computed cases, classifier thresholds, association rules on a hand-checked basket, and the bill parser.
- **Security:** per-user database isolation for read, update and delete; the allowlist; and that the local user can't be enabled when `[auth]` is set.

The crawler and cloud simulation need Playwright: `pip install playwright` and `python -m playwright install chromium`.

## Deploy (Streamlit Community Cloud)

`docs/deploy.md` has the full steps. In short:

1. **Neon:** create a project and copy the pooled connection string.
2. **Tables:** put the string in `.streamlit/secrets.toml` and run `python scripts/init_db.py` once, then `python scripts/check_database.py`.
3. **Google OAuth client:** set it up following `docs/google_login_setup.md`, with redirect URIs `http://localhost:8501/oauth2callback` and `https://<app>.streamlit.app/oauth2callback`, and every team member added as a test user.
4. **Streamlit Cloud:** repo `Galvin70124O/FORAGE`, branch `main`, file `app.py`, **Python 3.12**. Paste the secrets: `ALLOWED_EMAILS`, `[auth]`, `[auth.google]`, `[connections.sql]` (format in `.streamlit/secrets.example.toml`).

Never commit `.streamlit/secrets.toml`, `.env`, `dataset/` or `data/real/`.

## Limitations

- **The demo data is synthetic.** Its waste is a random share of unused food, independent of expiry, so long-shelf-life foods waste the most there. Its prices are illustrative.
- **Personal data is weekly.** It supports period-level analyses only, and models trained on it become reliable only after several weeks.
- **The M5 and Instacart extracts are bounded subsets** (one store, 100 items, 180 days; 2,000 users) and are not available online.
