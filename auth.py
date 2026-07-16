import streamlit as st
from supabase import create_client


SESSION_KEYS = (
    "sb_access_token",
    "sb_refresh_token",
    "sb_user_id",
    "sb_user_email",
    "sb_profile",
)


def _client():
    try:
        url = st.secrets["supabase"]["url"]
        anon_key = st.secrets["supabase"]["anon_key"]
    except Exception:
        st.error(
            "Falta configurar Supabase en los secretos de Streamlit."
        )
        st.stop()

    return create_client(url, anon_key)


def _clear_session():
    for key in SESSION_KEYS:
        st.session_state.pop(key, None)


def _restore_session(client):
    access_token = st.session_state.get("sb_access_token")
    refresh_token = st.session_state.get("sb_refresh_token")

    if not access_token or not refresh_token:
        return False

    try:
        response = client.auth.set_session(
            access_token,
            refresh_token,
        )

        if response.session:
            st.session_state["sb_access_token"] = (
                response.session.access_token
            )
            st.session_state["sb_refresh_token"] = (
                response.session.refresh_token
            )

        return response.user is not None

    except Exception:
        _clear_session()
        return False


def _load_profile(client, user_id):
    try:
        response = (
            client.table("profiles")
            .select(
                "id,email,nombre,estado,plan,role,kajabi_offer"
            )
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        return response.data
    except Exception:
        return None


def _is_active(profile):
    if not profile:
        return False

    return (
        str(profile.get("estado", "")).strip().lower()
        == "activo"
    )


def _perform_login(email, password):
    client = _client()

    try:
        response = client.auth.sign_in_with_password(
            {
                "email": email.strip().lower(),
                "password": password,
            }
        )

        if not response.user or not response.session:
            return False, "No se pudo iniciar sesión."

        profile = _load_profile(client, response.user.id)

        if not _is_active(profile):
            try:
                client.auth.sign_out()
            except Exception:
                pass

            return False, (
                "Tu cuenta no tiene acceso activo a Macro FX."
            )

        st.session_state["sb_access_token"] = (
            response.session.access_token
        )
        st.session_state["sb_refresh_token"] = (
            response.session.refresh_token
        )
        st.session_state["sb_user_id"] = response.user.id
        st.session_state["sb_user_email"] = (
            response.user.email or email
        )
        st.session_state["sb_profile"] = profile

        return True, ""

    except Exception as error:
        message = str(error).lower()

        if "invalid login credentials" in message:
            return False, "Correo o contraseña incorrectos."

        if "email not confirmed" in message:
            return False, "Confirma tu correo antes de entrar."

        return False, f"Error Supabase: {error}"


def _render_login():
    st.markdown(
        """
        <style>
            section[data-testid="stSidebar"] {
                display: none !important;
            }

            [data-testid="collapsedControl"] {
                display: none !important;
            }

            .block-container {
                max-width: 520px !important;
                padding-top: 8vh !important;
            }

            .login-shell {
                background: linear-gradient(
                    145deg,
                    #111111,
                    #202020
                );
                border: 1px solid #2f2f2f;
                border-radius: 20px;
                padding: 2rem;
                margin-bottom: 1rem;
                box-shadow: 0 18px 50px rgba(0,0,0,.16);
            }

            .login-eyebrow {
                color: #E3C85B;
                font-size: .76rem;
                font-weight: 800;
                letter-spacing: .14em;
                text-transform: uppercase;
                margin-bottom: .55rem;
            }

            .login-title {
                color: white;
                font-size: 2rem;
                font-weight: 850;
                line-height: 1.08;
            }

            .login-subtitle {
                color: #BFC3CA;
                margin-top: .7rem;
                line-height: 1.5;
            }

            div[data-testid="stForm"] {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 16px;
                padding: 1.25rem;
                box-shadow: 0 6px 22px rgba(17,24,39,.06);
            }

            div[data-testid="stFormSubmitButton"] button {
                width: 100%;
                background: #C9A227;
                color: #111111;
                border: none;
                font-weight: 800;
                border-radius: 9px;
            }

            #MainMenu, footer {
                visibility: hidden;
            }
        </style>

        <div class="login-shell">
            <div class="login-eyebrow">Finans Trading</div>
            <div class="login-title">
                Acceso privado a Macro FX
            </div>
            <div class="login-subtitle">
                Inicia sesión con el correo autorizado.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("macro_fx_login"):
        email = st.text_input("Correo electrónico")
        password = st.text_input(
            "Contraseña",
            type="password",
        )
        submitted = st.form_submit_button(
            "Iniciar sesión"
        )

    if submitted:
        if not email.strip() or not password:
            st.warning(
                "Introduce tu correo y contraseña."
            )
            st.stop()

        ok, error = _perform_login(email, password)

        if ok:
            st.rerun()

        st.error(error)

    st.caption(
        "Acceso reservado a usuarios autorizados."
    )


def require_authenticated_user():
    profile = st.session_state.get("sb_profile")

    if profile and _is_active(profile):
        return profile

    client = _client()

    if _restore_session(client):
        response = client.auth.get_user()
        user = response.user

        if user:
            profile = _load_profile(client, user.id)

            if _is_active(profile):
                st.session_state["sb_user_id"] = user.id
                st.session_state["sb_user_email"] = (
                    user.email or ""
                )
                st.session_state["sb_profile"] = profile
                return profile

    _clear_session()
    _render_login()
    st.stop()


def render_logout(profile):
    nombre = (
        str(profile.get("nombre") or "").strip()
        or str(profile.get("email") or "").strip()
        or "Usuario"
    )
    plan = str(
        profile.get("plan") or "Macro FX"
    ).strip()

    st.markdown(
        f"""
        <div class="sidebar-info">
            <strong>{nombre}</strong><br>
            Plan: {plan}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        "Cerrar sesión",
        use_container_width=True,
    ):
        try:
            client = _client()
            _restore_session(client)
            client.auth.sign_out()
        except Exception:
            pass

        _clear_session()
        st.rerun()
