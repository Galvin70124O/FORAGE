"""Supabase login/signup screens (only shown when AUTH_ENABLED is True)."""


import streamlit as st


from auth import login, logout, signup

from ui.theme import current_theme


def render_authentication_page():
    """Render the public authentication flow before any dashboard data loads."""
    if "auth_mode" not in st.session_state:
        st.session_state.auth_mode = "login"

    top_left, top_right = st.columns([8, 1])
    with top_right:
        toggle_label = "Light mode" if current_theme() == "dark" else "Dark mode"
        st.toggle(toggle_label, key="dark_mode", help="Switch between the light and dark FORAGE interface.")

    _, auth_column, _ = st.columns([1, 1.05, 1])
    with auth_column:
        st.markdown(
            "<div class='auth-brand'><span class='auth-mark'>F</span><span class='auth-name'>FORAGE</span></div>",
            unsafe_allow_html=True,
        )
        with st.container(border=True):
            if st.session_state.auth_mode == "login":
                st.markdown("<div class='auth-kicker'>FOOD INTELLIGENCE PLATFORM</div>", unsafe_allow_html=True)
                st.markdown("<div class='auth-title'>Welcome back</div>", unsafe_allow_html=True)
                st.markdown("<div class='auth-subtitle'>Sign in to explore food demand, consumption, and waste insights.</div>", unsafe_allow_html=True)
                with st.form("forage_login_form"):
                    email = st.text_input("Email", key="login_email", placeholder="you@example.com")
                    password = st.text_input("Password", type="password", key="login_password")
                    submitted = st.form_submit_button("Log in", width="stretch")
                if submitted:
                    success, message = login(email, password)
                    if success:
                        st.rerun()
                    st.error(message)
                st.markdown("<div class='auth-switch'>Don't have an account?</div>", unsafe_allow_html=True)
                if st.button("Create account", key="show_signup", width="stretch"):
                    st.session_state.auth_mode = "signup"
                    st.rerun()
            else:
                st.markdown("<div class='auth-kicker'>FOOD INTELLIGENCE PLATFORM</div>", unsafe_allow_html=True)
                st.markdown("<div class='auth-title'>Create your account</div>", unsafe_allow_html=True)
                st.markdown("<div class='auth-subtitle'>Start using FORAGE to make clearer food purchasing decisions.</div>", unsafe_allow_html=True)
                with st.form("forage_signup_form"):
                    name = st.text_input("Name", key="signup_name", placeholder="Your name")
                    email = st.text_input("Email", key="signup_email", placeholder="you@example.com")
                    password = st.text_input("Password", type="password", key="signup_password")
                    confirmation = st.text_input("Confirm password", type="password", key="signup_confirmation")
                    submitted = st.form_submit_button("Create account", width="stretch")
                if submitted:
                    success, message, authenticated = signup(name, email, password, confirmation)
                    if not success:
                        st.error(message)
                    elif authenticated:
                        st.success(message)
                        st.rerun()
                    else:
                        st.session_state.auth_mode = "login"
                        st.session_state.auth_notice = message
                        st.rerun()
                st.markdown("<div class='auth-switch'>Already have an account?</div>", unsafe_allow_html=True)
                if st.button("Log in", key="show_login", width="stretch"):
                    st.session_state.auth_mode = "login"
                    st.rerun()

        notice = st.session_state.pop("auth_notice", None)
        if notice:
            st.success(notice)


def render_authenticated_sidebar_controls():
    """Show account context and provide a local-session logout control."""
    user = st.session_state.get("user")
    email = getattr(user, "email", None) if user is not None else None
    if email:
        st.sidebar.caption(f"Signed in as {email}")
    if st.sidebar.button("Log out", key="logout", width="stretch"):
        logout()
        st.rerun()
