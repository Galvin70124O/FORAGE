"""Supabase login/signup screens. Only shown when AUTH_ENABLED is True in app.py."""

import streamlit as st

from auth import login, logout, signup


def render_authentication_page():
    """Render the sign-in / sign-up flow before any dashboard data loads."""
    st.session_state.setdefault("auth_mode", "login")
    _, column, _ = st.columns([1, 1.1, 1])
    with column:
        st.markdown('<p class="fg-brand">FORAGE</p>', unsafe_allow_html=True)
        if st.session_state.auth_mode == "login":
            st.subheader("Sign in")
            with st.form("forage_login_form"):
                email = st.text_input("Email", key="login_email", placeholder="you@example.com")
                password = st.text_input("Password", type="password", key="login_password")
                submitted = st.form_submit_button("Sign in", width="stretch", type="primary")
            if submitted:
                success, message = login(email, password)
                if success:
                    st.rerun()
                st.error(message)
            if st.button("Create an account", key="show_signup", width="stretch"):
                st.session_state.auth_mode = "signup"
                st.rerun()
        else:
            st.subheader("Create an account")
            with st.form("forage_signup_form"):
                name = st.text_input("Name", key="signup_name")
                email = st.text_input("Email", key="signup_email", placeholder="you@example.com")
                password = st.text_input("Password", type="password", key="signup_password")
                confirmation = st.text_input("Confirm password", type="password", key="signup_confirmation")
                submitted = st.form_submit_button("Create account", width="stretch", type="primary")
            if submitted:
                success, message, authenticated = signup(name, email, password, confirmation)
                if not success:
                    st.error(message)
                elif authenticated:
                    st.rerun()
                else:
                    st.session_state.auth_mode = "login"
                    st.session_state.auth_notice = message
                    st.rerun()
            if st.button("I already have an account", key="show_login", width="stretch"):
                st.session_state.auth_mode = "login"
                st.rerun()
        notice = st.session_state.pop("auth_notice", None)
        if notice:
            st.success(notice)


def render_authenticated_sidebar_controls():
    """Show the signed-in account and a sign-out control."""
    user = st.session_state.get("user")
    email = getattr(user, "email", None) if user is not None else None
    if email:
        st.sidebar.caption(f"Signed in as {email}")
    if st.sidebar.button("Sign out", key="logout", width="stretch"):
        logout()
        st.rerun()
