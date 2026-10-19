# Google sign-in for FORAGE

FORAGE uses Streamlit's built-in OpenID Connect login (`st.login`, `st.user`, `st.logout`) with Google. Users are identified by their Google email. Without an `[auth]` section in the secrets, the app runs as a single local user instead.

## 1. Create a Google Cloud project

1. Go to <https://console.cloud.google.com/> and choose **Select a project → New project**. Name it `forage` and create it.
2. Make sure the new project is selected in the top bar.

## 2. Configure the OAuth consent screen

1. Open **APIs & Services → OAuth consent screen** (in newer consoles: **Google Auth Platform → Branding**).
2. User type: **External**. Select **Create**.
3. App name `FORAGE`, user support email and developer contact email: your own address. Save.
4. **Scopes** (or **Data access**): add `openid`, `.../auth/userinfo.email` and `.../auth/userinfo.profile`. These are non-sensitive, so no verification is needed.
5. **Test users** (or **Audience → Test users**): add the Google address of every team member. While the app is in *Testing* status, only these accounts can sign in. That is what you want for a team app.

## 3. Create the OAuth client

1. Open **APIs & Services → Credentials → Create credentials → OAuth client ID** (or **Google Auth Platform → Clients → Create client**).
2. Application type: **Web application**. Name: `FORAGE web`.
3. Under **Authorized redirect URIs**, add both:
   - `http://localhost:8501/oauth2callback` (local development)
   - `https://<your-app>.streamlit.app/oauth2callback` (Streamlit Community Cloud, using your app's real subdomain)
4. Select **Create**, then copy the **Client ID** and **Client secret**.

## 4. Put the values in the secrets

Locally, copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml` (git-ignored) and fill in:

```toml
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "<output of: python -c \"import secrets; print(secrets.token_hex(32))\">"
client_id = "<Client ID>"
client_secret = "<Client secret>"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

On Streamlit Community Cloud, paste the same block into **App settings → Secrets** with `redirect_uri` set to the `https://<your-app>.streamlit.app/oauth2callback` address. Use a different `cookie_secret` from the local one.

## 5. Check it

Run `python -m streamlit run app.py`. The sidebar shows **Sign in with Google**. After signing in, it shows your name and **Log out**. If Google reports `redirect_uri_mismatch`, the URI in the secrets doesn't exactly match one in step 3. Check the scheme, the port and the `/oauth2callback` path.

Notes:
- `[auth]` also needs a database (`[connections.sql]`, see `docs/deploy.md`). With sign-in but no database, personal pages stay closed and the Insights pages still work.
- When `[auth]` is present, the local single-user fallback can't activate. A test (`tests/test_store.py`) checks this.
