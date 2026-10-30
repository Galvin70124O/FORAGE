"""Privacy: what FORAGE stores, why, who can see it, and how to export or delete it. Open without signing in."""

import streamlit as st

from ui.kitchen import lang, page_title, t

page_title("nav_privacy", "privacy_purpose")
if lang() != "en":
    st.caption(t("legal_english_only"))

st.markdown("""
_Last updated 30 October 2026._

### What is stored, and why

When you sign in with Google, FORAGE keeps:

- **Your Google email address and name**: to know which records are yours and to show who is signed in.
- **Your purchases** (food, date, amount, price paid), **pantry checks** (what was left and what was thrown away)
  and **your list of foods** (name, category, unit, shelf life): this is the app itself; it turns them into
  "use first" reminders, a shopping list and waste figures.
- **Two settings**: your language and whether you have seen the first-run walkthrough.

Nothing else: no location, no contacts, no payment details, no advertising identifiers.

### What FORAGE does with it

Your records are used only to calculate your own reminders, shopping list and charts. Those calculations
(averages, statistical tests and small machine-learning models) run inside FORAGE on your own data.
**Nothing is sent to any AI service**, and your data is never sold, shared with advertisers or used to train
anything outside FORAGE.

### Who can see it

Only you. Every record is tied to your account and every read, change and delete is limited to it.
The FORAGE team can technically access the database to maintain the app. We don't look at individual records
unless you ask us to help with your data.

### Services FORAGE relies on

- **Google**: sign-in (Google tells FORAGE your email and name), and the fonts the page loads.
- **Neon**: hosts the PostgreSQL database where your records are kept.
- **Streamlit Community Cloud**: runs the app. Its server logs record technical events such as errors.
- **GitHub**: holds the app's source code only. None of your records are stored there.

### Your rights: access, correction, deletion

In line with India's Digital Personal Data Protection Act, 2023:

- **Access**: *My data → Download and upload* gives you everything you have logged as files.
- **Correction**: change any entry in *My data*.
- **Deletion**: delete any entry in *My data*. To delete your whole account, email the address below and it
  will be done within 30 days.

### Contact

Questions, requests or complaints: [galvin.g.godsberry@gmail.com](mailto:galvin.g.godsberry@gmail.com)
""")
