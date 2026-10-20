"""Kitchen-mode building blocks: translated text, the language picker, big tiles, messages and the walkthrough."""

from __future__ import annotations

import streamlit as st

from i18n import LANGUAGES, translate

WALKTHROUGH = [("walk1_title", "walk1_body"), ("walk2_title", "walk2_body"), ("walk3_title", "walk3_body")]
ONBOARDED = "onboarded"


def lang() -> str:
    return st.session_state.get("lang", "en")


def t(key: str, **values) -> str:
    return translate(key, lang(), **values)


def language_picker(db=None, uid: int | None = None) -> None:
    """English / हिन्दी / தமிழ், remembered per session and, when signed in, in the user's settings."""
    def changed() -> None:
        if db is not None and uid is not None and st.session_state.get("lang"):
            db.set_setting(uid, "lang", st.session_state["lang"])

    if "lang" not in st.session_state:
        stored = db.get_setting(uid, "lang") if db is not None and uid is not None else None
        st.session_state["lang"] = stored if stored in LANGUAGES else "en"
    st.segmented_control(t("language"), list(LANGUAGES), format_func=LANGUAGES.get, key="lang",
                         on_change=changed, required=True)


def page_title(title_key: str, purpose_key: str) -> None:
    st.title(t(title_key), anchor=False)
    st.markdown(f'<p class="fg-purpose">{t(purpose_key)}</p>', unsafe_allow_html=True)


def tiles(options: list[str], key: str, *, selected: str | None = None, labels: dict | None = None) -> str | None:
    """Big tappable text tiles that wrap on a phone; returns the option tapped in this run, if any."""
    tapped = None
    with st.container(horizontal=True, key=f"fg-tiles-{key}"):
        for i, option in enumerate(options):
            label = (labels or {}).get(option, option)
            if st.button(label, key=f"{key}_{i}", type="primary" if option == selected else "secondary"):
                tapped = option
    return tapped


def success(message: str) -> None:
    """Call after a write: clears the cached reads and shows `message` at the top of the next run."""
    from services.personal import saved
    saved(message)
    st.session_state["flash"] = st.session_state.pop("toast", message)


def flash() -> None:
    """Show the success message queued before the last rerun."""
    if message := st.session_state.pop("flash", None):
        st.success(message)


def walkthrough(db, uid: int) -> bool:
    """Three short screens shown once per user (stored in settings). True while it is showing."""
    if st.session_state.get(ONBOARDED) or db.get_setting(uid, ONBOARDED) == "1":
        st.session_state[ONBOARDED] = True
        return False
    step = st.session_state.setdefault("walk_step", 0)

    def finish() -> None:
        db.set_setting(uid, ONBOARDED, "1")
        st.session_state[ONBOARDED] = True

    def advance() -> None:
        st.session_state["walk_step"] += 1

    title, body = WALKTHROUGH[step]
    with st.container(border=True, key="fg-walkthrough"):
        st.caption(t("walk_step", i=step + 1, n=len(WALKTHROUGH)))
        st.subheader(t(title))
        st.write(t(body))
        st.progress((step + 1) / len(WALKTHROUGH))
        with st.container(horizontal=True, key="fg-walk-buttons"):
            last = step == len(WALKTHROUGH) - 1
            st.button(t("start") if last else t("next"), type="primary", on_click=finish if last else advance)
            if not last:
                st.button(t("skip"), on_click=finish)
    return True


def install_help() -> None:
    with st.expander(t("install_title")):
        st.markdown(f"**Android**  \n{t('install_android')}")
        st.markdown(f"**iPhone**  \n{t('install_iphone')}")
        st.caption(t("install_after"))


KITCHEN_CSS = """
<style>
/* Kitchen mode: readable text and touch targets of at least 44 px. */
.block-container p, .block-container li, .block-container label p { font-size: 1.02rem; }
[class*="st-key-fg-tiles"] button { min-height: 56px; min-width: 104px; font-size: 1.02rem; padding: 0 1rem; }
[class*="st-key-fg-levels"] button { min-height: 64px; min-width: 120px; font-size: 1.05rem; flex: 1 1 40%; }
[class*="st-key-fg-tiles"], [class*="st-key-fg-levels"] { gap: 0.5rem; }
[data-testid="stButtonGroup"] button { min-height: 44px; padding: 0 1rem; font-size: 1rem; }
.fg-message { padding: 0.75rem 1rem; border: 1px solid var(--fg-border); border-radius: 8px; margin: 0; }
.fg-message b { font-weight: 600; }
.fg-list { margin: 0; padding-left: 1.2rem; }
.fg-list li { padding: 0.2rem 0; }
@media (max-width: 640px) {
  [class*="st-key-fg-tiles"] button { flex: 1 1 calc(33% - 0.5rem); min-width: 96px; }
}
</style>
"""


def apply_kitchen_styles() -> None:
    st.markdown(KITCHEN_CSS, unsafe_allow_html=True)


def message(text: str) -> None:
    """A plain bordered message line (no colour coding, readable on a phone)."""
    from html import escape
    st.markdown(f'<p class="fg-message">{escape(text)}</p>', unsafe_allow_html=True)
