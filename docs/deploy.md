# Deploying FORAGE on Streamlit Community Cloud

The online app needs three services, all with free tiers: **Neon** (Postgres database), **Google Cloud** (sign-in) and **Streamlit Community Cloud** (hosting). Without them, FORAGE runs in demo mode, where personal entries live in a temporary local file. Never commit `.streamlit/secrets.toml`.

## 1. Neon database

1. Sign up at <https://neon.tech> and create a project named `forage`. Pick the region closest to your users, for example AWS `ap-south-1` (Mumbai).
2. In **Dashboard → Connect**, choose the default branch and database, then copy the **pooled** connection string. It looks like `postgresql://USER:PASSWORD@ep-xxx-pooler.REGION.aws.neon.tech/neondb?sslmode=require`.
3. Optional but recommended: create a branch called `test` (**Branches → New branch**) for checks, and keep the default branch for real use.

## 2. Create the tables (once)

On your computer, from the project root:

```powershell
# put the URL in .streamlit/secrets.toml under [connections.sql] (see .streamlit/secrets.example.toml), then:
python scripts/init_db.py           # creates users, foods, purchases, pantry_checks, settings (safe to re-run)
python scripts/check_database.py    # isolation smoke test with two throwaway users; prints OK
```

Both scripts read the URL from the secrets file and never print it. `postgresql://` URLs are switched to the psycopg 3 driver automatically.

## 3. Google sign-in

Follow `docs/google_login_setup.md`. In the Google OAuth client, add both redirect URIs:

- `http://localhost:8501/oauth2callback`
- `https://<your-app>.streamlit.app/oauth2callback`

The second one uses the exact subdomain you choose in step 4. Add every team member under **Test users**.

## 4. Streamlit Community Cloud

1. Go to <https://share.streamlit.io>, sign in with GitHub and select **Create app → Deploy a public app from GitHub**.
2. Repository `Galvin70124O/FORAGE`, branch `main`, main file path `app.py`.
3. **App URL**: choose the subdomain, for example `forage-team`. It must match the redirect URI in Google.
4. **Advanced settings → Python version: 3.12.** The versions in `requirements.txt` were tested with it. Community Cloud sets the Python version here; it does not read `runtime.txt`.
5. **Advanced settings → Secrets**: paste:

```toml
[auth]
redirect_uri = "https://<your-app>.streamlit.app/oauth2callback"
cookie_secret = "<a new random string: python -c \"import secrets; print(secrets.token_hex(32))\">"
client_id = "<Google OAuth client ID>"
client_secret = "<Google OAuth client secret>"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

[connections.sql]
url = "<Neon pooled connection string>"
```

6. Select **Deploy**. The first start installs the packages and takes a few minutes.

## 5. Check the live app

- The sidebar shows **Sign in with Google**. After signing in it shows your name and **Log out**, and the "Your food" pages work.
- Log a purchase, then a pantry check, and confirm they appear under **My data**. Restart the app from the Cloud menu (**⋮ → Reboot**) and confirm they are still there, because they live in Neon.
- The Insights pages work without signing in. M5 and Instacart show "available in the local version" (see `docs/data_licences.md`).
- If Neon has been idle, the first request shows **Waking up the database…** for a few seconds.

## Notes

- **Memory:** heavy models are trained once per app process and cached (`st.cache_resource`). M5 and Instacart are only loaded when chosen, and they are absent online. That keeps the app well under the Community Cloud limit.
- **Updates:** pushing to `main` redeploys automatically. Re-run `scripts/init_db.py` after a release that adds tables. It only creates missing ones.
- **Local check before pushing:** `python scripts/cloud_simulation.py` (no secrets) and `python scripts/cloud_simulation.py --secrets .streamlit/secrets.toml` (your test database). Both need Playwright installed locally (`pip install playwright && python -m playwright install chromium`).

## Verification status (cloud simulation, 19–20 Oct 2026)

`scripts/cloud_simulation.py` copies only the committed files into a fresh folder and builds a fresh virtual environment from `requirements.txt`. It then crawls every page × data source in light and dark mode and logs a purchase and a pantry check through the UI.

| Run | Secrets | Result |
| --- | --- | --- |
| (a) | none (demo mode) | 58 page checks, 0 problems; server log clean |
| (b1) | `[connections.sql]` → SQLite file (stand-in for Neon) | `init_db.py` OK, isolation check OK; 58 checks, 0 problems; log clean |
| (b2) | `[auth]` (placeholder Google client) + `[connections.sql]` | signed-out state everywhere, no local-user fallback; 44 checks, 0 problems; log clean |

**TODO: run against Neon.** Put a Neon **test-branch** URL in your local `.streamlit/secrets.toml` under `[connections.sql]`, then run:

```powershell
python scripts/cloud_simulation.py --secrets .streamlit/secrets.toml
```

It runs `init_db.py` and the isolation check against that database before crawling the app. The URL is never printed or logged. Signing in with a real Google account can't be automated, so test that by hand once (step 5 above).
