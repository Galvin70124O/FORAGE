"""Terms of use. Open without signing in."""

import streamlit as st

from ui.kitchen import lang, page_title, t

page_title("nav_terms", "terms_purpose")
if lang() != "en":
    st.caption(t("legal_english_only"))

st.markdown("""
_Last updated 30 October 2026._

### A student project

FORAGE was built as a student project for the course *Fundamentals of Data Science* at Meenakshi Sundararajan
Engineering College (MSEC), Chennai. It is free to
use and is not a commercial service.

### Provided as is

FORAGE is provided "as is", without any warranty. It may be unavailable, change or stop at any time, and
data may be lost, so keep your own copy (*My data → Download and upload*) of anything that matters to you.

### Not food-safety advice

Expiry dates, "use first" reminders and freshness meters are **estimates** from typical shelf lives and what
you entered. They are not a guarantee that food is safe to eat. Always check the food itself and its
packaging, and follow official food-safety guidance.

### Using FORAGE

Use it for your own household records. Don't try to reach other people's data or disrupt the service.

### Your data

How your data is stored and used is described on the [Privacy](/privacy) page.

### Contact

[galvin.g.godsberry@gmail.com](mailto:galvin.g.godsberry@gmail.com)
""")
