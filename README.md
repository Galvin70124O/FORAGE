# FORAGE

FORAGE is a household food app and a data-science project in one.

- **Daily use:** a team logs what it buys and checks its pantry once a week, from a phone. FORAGE works out what was eaten and what was thrown away, warns before food expires, flags purchases that are likely to be wasted and says what to buy this week.
- **Insights:** public pages show the full analysis workflow on four sources it never mixes: data quality, statistics and hypothesis tests, waste in ₹, forecasting with baselines and backtests, explainable recommendations, and market-basket rules.

It is framed by UN SDG target 12.3: halve per-capita food waste by 2030. Fundamentals of Data Science project.

Live app: <https://forage-pantry.streamlit.app> · [Privacy](https://forage-pantry.streamlit.app/privacy) · [Terms](https://forage-pantry.streamlit.app/terms) (both open without signing in).

## Features

FORAGE has two modes, switched at the bottom of the sidebar. The choice is remembered for the session.

**Kitchen** (the default once signed in): built so someone non-technical can use it daily on a phone with no explanation, in plain language, in **English, हिन्दी or தமிழ்** (sidebar).

- **Home:** what to use first ("Use the spinach today"), food you may not finish in time, how many things to buy this week ("You have enough rice, skip it this week") and "About ₹450 of food was thrown away this month".
- **I bought…:** big tiles for your usual foods plus search, everyday amounts ("½ kg", "1 litre", "2 packets") stored in the food's base unit, a custom amount, **Repeat last purchase** and **Repeat last week**, the date defaulting to today, one Save button and a clear success message. You can also paste a shopping bill.
- **Pantry check:** four big buttons per food, **Full / Half / Almost empty / Finished**, as shares of what you had, plus "Thrown any away?" and an optional exact amount. **Check everything** goes one food at a time with a progress count.
- **Shopping list:** what to buy this week in everyday amounts, a tick box per item, copyable text and **Send on WhatsApp**.
- **My data:** edit and delete entries (deletes ask for confirmation), export CSVs, and import CSVs, which skips rows you already have.
- **First visit:** a skippable 3-screen walkthrough (log what you buy → check your pantry weekly → get a smart shopping list), shown once per user.
- **Install on your phone:** steps for Android Chrome and iPhone Safari are in the sidebar.

**Project insights** (the default for visitors, open without signing in), on the source chosen in the sidebar. A **Source & licence** note per dataset gives the attribution.

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
| M5 (Walmart) | Retail unit sales, store CA_1, the 100 best-selling food items, last 180 days | Kaggle competition rules: non-commercial use. Raw files not redistributed; aggregates only (department daily totals, top-10 weekly totals, model results; no prices) in `data/public/m5/` |
| Instacart | Online grocery orders from users 1–2,000 (313,404 order lines) | "Non-commercial use … subject to Instacart's Terms". Raw files not redistributed; aggregates only in `data/public/instacart/` |

`docs/data_licences.md` records the licence check. To use M5 and Instacart locally, download them yourself into `dataset/` and run `python src/real_data_processor.py`. The raw files are never committed. Online, those pages read aggregated results published in `data/public/` (built by `python scripts/build_public_artifacts.py`; no Instacart user IDs or order rows).

**Definitions.**

- Waste is the *recorded* quantity thrown away, never purchased − consumed.
- Waste rate = wasted ÷ purchased per food, averaged across foods so units never mix.
- For your data, consumption is derived: consumed = previous remaining + bought − thrown away − remaining now, per food per pantry-check period. Impossible values are flagged, not corrected.
- Personal analyses unlock gradually and say "Not enough data yet (need N more weeks)" until there is enough. Day-level analyses don't run on weekly checks, and the app explains that this is a sample-size limit.

## Architecture

```text
app.py                     page config, logo, two modes (Kitchen / Project insights) with their own navigation and sidebar
views/                     one file per page; *_section.py are shared renderers
services/
  data.py                  cached loaders and model results (st.cache_resource), precomputed-result lookup
  overview.py              dashboard KPIs, charts and actions (part of the precomputed-results fingerprint)
  pantry_view.py           Overview pantry labels, waste-gauge target and the three expiry shelves
  session.py               secrets, mode, Google sign-in + allowlist, st.connection("sql")
  personal.py              signed-in user, cached personal reads (ttl 60 s, cleared after writes)
ui/                        theme.py (Fresh Shelf tokens, the one stylesheet, Plotly template), charts.py (Plotly builders),
                           components.py (label cards, freshness meter, shelves, waste gauge, demand cards, empty states),
                           kitchen.py (tiles, walkthrough, language)
src/                       analysis logic: pure functions, no Streamlit, unit-tested
  store.py                 the ONLY database module: every query filtered by user
  identity.py              who may use the personal pages (allowlist, local user only without [auth])
  pantry.py                purchases + checks -> periods, stock, expiry, buy list, bill parser, CSV import
  kitchen.py               everyday amounts, pantry levels, repeat purchases, shopping list share text
  i18n.py                  Kitchen labels and messages in English, Hindi and Tamil
  public_data.py           data/public/ bundles: Instacart aggregates, manifest with licence and hashes
  clean_data.py, data_quality.py, stats.py, hypothesis.py, waste.py
  prediction.py, m5_forecasting.py, horizon.py (7-day + rolling origin), recommendations.py, backtest.py
  waste_risk.py (classifier), explain.py (importance, residuals), basket.py (FP-growth), artifacts.py
scripts/                   init_db, check_database, precompute_demo, export_results, make_messy_sample,
                           build_public_artifacts, crawl_pages, cloud_simulation
data/                      demo CSVs, messy sample, logging templates, precomputed demo results,
                           public/ (aggregated M5 and Instacart results for the online app)
docs/                      deploy.md, google_login_setup.md, data_licences.md
tests/                     pytest suite
```

## Look and feel: Fresh Shelf

FORAGE's visual identity is a well-kept hostel pantry shelf with handwritten jar labels: linen background, white
cards with warm 1 px borders, herb green (#2E6B4F) for the brand, **Fraunces** for titles and big numbers and
**DM Sans** for everything else (tabular figures for quantities and ₹). Status colours mean the same everywhere:
fresh = green, use soon = turmeric, expired / wasted = tomato, neutral = stone. Every text colour is at least
4.5:1 against its background in light and dark mode. Dark mode follows the device setting.

| Piece | Where |
| --- | --- |
| Jar-label KPI cards (double rule, small-caps name, value, comparison with last month) | every KPI row; Overview shows Purchased, Consumed, Wasted %, Money lost |
| Freshness meter (days left written on it) | every jar on a shelf |
| Shelves: Expired, Use within 2 days, This week | Overview preview, Waste & Expiry → Expiry |
| Waste-bin gauge against a target (half the first month's rate, SDG 12.3) | Overview |
| Demand cards with a Buy less / same / more stamp and the model's confidence | Forecasting (demo), Recommendations |

All of it is presentation: the same numbers come from the same functions. Purchased, Consumed and Money lost use the
existing valuation (quantity × each food's median price per unit), so Money lost equals ₹ wasted elsewhere.

Code: `ui/theme.py` holds the tokens, all injected CSS and the Plotly templates (applied once per run from
`app.py`); `ui/components.py` holds `label_card`/`kpi_row`, `freshness_bar`, `shelf`, `waste_gauge`, `demand_card`
and `empty_state`; `ui/charts.py` draws every chart with the one template. Pages call these and never repeat HTML.
Screenshots for review: `docs/ui-review/`.

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

1. **Every time you shop**, open **I bought…**: tap the food, tap how much ("1 kg", "1 litre"…), optionally type the *total* price paid, then Save. **Repeat last purchase** and **Repeat last week** save typing. A new food asks once for its type and how many days it stays good.
2. **Once a week** (more often is better), open **Pantry check** and tap **Check everything**. For each food, say whether you threw any away, then tap Full, Half, Almost empty or Finished. **Exact amount** is there if you prefer numbers.
3. That's all. Consumption, waste, expiry warnings, the **Shopping list** (shareable on WhatsApp) and forecasts are worked out from these two records.
4. Bulk entry: fill `data/templates/purchases_template.csv` or `pantry_checks_template.csv`, then use **My data → Import**. Rows you already have are skipped, so teammates can merge their files.

## Tests and checks

```powershell
python -m pytest                      # 187 tests
python scripts/export_results.py      # outputs/results.json + report charts (git-ignored)
python scripts/precompute_demo.py     # after changing demo data or model code; a test fails if it is stale
python scripts/build_public_artifacts.py  # where the raw M5/Instacart extracts exist: refresh data/public/
python scripts/cloud_simulation.py    # fresh clone + fresh venv from requirements.txt, every page crawled
```

The tests cover:

- **Cleaning and data:** cleaning rules, statistics against scipy and hand calculations, and waste and ₹ formulas, including that waste is never computed for M5 or Instacart.
- **Forecasting:** leakage tests for lags, rolling means, the chronological split, the 7-day target and every rolling fold.
- **Models and outputs:** the backtest simulator on hand-computed cases, classifier thresholds, association rules on a hand-checked basket, and the bill parser.
- **Security:** per-user database isolation for read, update and delete; the allowlist; and that the local user can't be enabled when `[auth]` is set.
- **Kitchen mode:** everyday amounts and pantry levels, repeat purchases, the share text, every string in all three languages with matching placeholders and no jargon, the walkthrough stored once per user, and every Kitchen page run in every language against a temporary database.
- **Published results:** `data/public/` manifests and hashes, size under 10 MB, no Instacart IDs or order rows, numbers matching `outputs/results.json`, and every Insights page rendering with the raw files hidden (`FORAGE_PUBLIC_ONLY=1`).

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
- **The M5 and Instacart extracts are bounded subsets** (one store, 100 items, 180 days; 2,000 users). Online, their pages use precomputed results, so they don't retrain models.
