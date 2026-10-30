# FORAGE: next pass (after 2 Nov 2026)

Same rules for every item: test only from a copy without `secrets.toml` (Demo mode), one small commit each,
run the tests, show `git diff --cached`, wait for an OK, then commit.

## First, in this order

- [ ] **(c) Delete my account and data.** In My data: "Delete my account and data", with a typed confirmation
  that names exactly what is deleted (email and name, purchases, pantry checks, foods, settings). Calls the
  existing `store.delete_user` for the signed-in user only, signs them out, shows a success message. Extend the
  isolation test: deleting user A leaves user B's rows untouched. EN/HI/TA labels. Then change the Privacy page's
  "email us to delete your account" line to point at this button.
- [ ] **(d) Open sign-in, opt-in.** In `src/identity.py`, `ALLOWED_EMAILS = ["*"]` lets in any signed-in Google
  account whose `email_verified` is true (missing means not verified). Explicit emails still work alongside
  `"*"`; a missing or empty list still lets nobody in. Update the docstring, `.streamlit/secrets.example.toml`
  and README. Tests in `tests/test_store.py`: `"*"` + verified → allowed; `"*"` + unverified or missing → not
  allowed; `[]` and missing → not allowed; a normal list still works. Per-user isolation tests to point to:
  `tests/test_store.py` (every read, update and delete filters on `user_id`).
- [ ] **(e) Push.** `git log --oneline origin/main..main`, full test suite, then `git push`.

## Then

- [ ] **Pantry check, fast taps lost (P2).** The "Saved" line is inserted above the card (`views/pantry.py:20`,
  `:62`) and a past-date expander collapses after the first save; the level buttons move 70-128 px under the
  thumb, so a quick second tap misses with no message (slow taps saved 5/5). Fix: show the queue's "Saved" as
  `st.toast`; `[data-stale="true"] button { pointer-events: none; }` so a tap during a rerun can't land on an
  old food's button. Confirm buttons re-enable after a normal, an error and a slow run. Regression test: two
  taps in one run save exactly one check and the queue advances by one.
- [ ] **Starter tiles vanish (P2).** After the first purchase, "Your usual foods" drops from 9 starter tiles to
  1 (`src/kitchen.py:141-146`). Top up with `STARTER_FOODS` not yet bought.
- [ ] **Undo instead of confirm (B).** My data deletes happen at once with a "Deleted N purchase(s) · Undo"
  toast; Undo restores the rows. Singular/plural via `translate()`; EN/HI/TA.
- [ ] **No "terminal" look (step 3).** `views/shopping.py:52`: replace `st.code(text)` with the list in the app
  font plus a "Copy list" button (keep Send on WhatsApp); drop "copy button on the right" from `share_help`.
  Waste & Expiry: move the monospace formulas and the long methods paragraph into the Methods expander as
  plain text (audit row 18).
- [ ] **Radius scale (step 4).** `ui/theme.py` + `config.toml` `baseRadius`: cards, gauge, shelf, expander 8px;
  jars 6px; buttons and inputs at most 10px; full pills only for small tags and chips (today: 16/12/10/6/3/999).
- [ ] **Forecasting skeleton (step 5).** While forecasts compute, 8 demand-card outlines and the chart frame as
  grey placeholders at final size (reuse `placeholder_lines`). Fix "this needs 1 periods" (singular,
  `src/pantry.py:36,38`) and the repeated "Not enough data yet" under its own title.
- [ ] **Balanced headings (C).** `text-wrap: balance` on h1/h2 and chart titles in `ui/theme.py`.
- [ ] **Audit rows 15-19.** 15: content stops 195px short at 1440 (centre it). 16: text 15px from the edge at
  768/390 (16-20px). 17: food tiles leave a gap at 390 (stretch). 18: see "terminal look". 19: Forecasting dates
  on one line, drop the "Date" axis title.
- [ ] **Smaller items.** h1 → h3 skip (use h2); 11.25px footer text (12px minimum); rupees in Indian grouping
  (₹1,25,05,552); skeleton shimmer animates `background-position` (use a transform); unknown URLs go to Home
  silently; tab title is always "FORAGE"; no `theme-color`; `lang="en"` in Hindi/Tamil; bill paste text area
  has no `max_chars`.
- [ ] **pip-audit** `requirements.txt`; list unused packages (don't remove without asking).
- [ ] **Full review run** (skipped on 30 Oct to save usage): crawl every page light/dark at 1440/390 with
  `scripts/crawl_pages.py` (retry the mode switch in light mode), then impeccable audit, design-taste-frontend
  inspector, emil-design-eng, apple-design, mobile-native, break-ui (long names, ₹ crores, empty data,
  Hindi/Tamil, `<img src=x onerror=alert(1)>` in the browser), find-animation-opportunities; time Home
  "This month" for Doherty (< 400 ms). Merge into one table before fixing.
- [ ] **Seeder note.** The UI seeder stalled at week 4 on 30 Oct. Reload Pantry check each week, tap `.last`
  buttons, wait for no `data-stale`; investigate the stall before relying on it.
