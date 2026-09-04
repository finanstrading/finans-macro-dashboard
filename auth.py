import requests
import streamlit as st
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from supabase import create_client

SESSION_KEYS = (
    "sb_access_token",
    "sb_refresh_token",
    "sb_user_id",
    "sb_user_email",
    "sb_profile",
)

PERSISTENT_COOKIE_NAME = "macrofx_session"
PERSISTENT_SESSION_DAYS = 30


PERSISTENT_COOKIE_JS = """
export default function(component) {
    const { data, setStateValue } = component;

    const cookieName = "macrofx_session";

    function readCookie(name) {
        const prefix = name + "=";
        const parts = document.cookie.split(";");

        for (const part of parts) {
            const value = part.trim();

            if (value.startsWith(prefix)) {
                return decodeURIComponent(
                    value.substring(prefix.length)
                );
            }
        }

        return null;
    }

    if (data?.action === "write" && data?.value) {
        console.log(
            "MACROFX COOKIE WRITE",
            window.location.hostname,
            data.value
        );

    const maxAge = 60 * 60 * 24 * 30;

        document.cookie =
            cookieName +
            "=" +
            encodeURIComponent(data.value) +
            "; Max-Age=" +
            maxAge +
            "; Path=/; SameSite=Lax; Secure";
    }

    console.log(
        "MACROFX COOKIE AFTER WRITE",
        document.cookie
    );

    if (data?.action === "delete") {
        document.cookie =
            cookieName +
            "=; Max-Age=0; Path=/; SameSite=Lax; Secure";

        return;
    }

    setStateValue(
        "cookie_value",
        readCookie(cookieName)
    );
}
"""


_persistent_cookie_component = st.components.v2.component(
    "macrofx_persistent_session",
    js=PERSISTENT_COOKIE_JS,
)


def _session_admin_client():
    try:
        url = st.secrets["supabase"]["url"]
        secret_key = st.secrets["supabase"]["secret_key"]
    except Exception:
        return None

    return create_client(url, secret_key)


def _hash_session_token(token):
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def _persistent_cookie(action="read", value=None):
    result = _persistent_cookie_component(
        data={
            "action": action,
            "value": value,
        },
        default={
            "cookie_value": None,
        },
        key="macrofx_persistent_cookie",
        on_cookie_value_change=lambda: None,
        height=0,
    )

    return result.cookie_value

def _create_persistent_session(user_id):
    admin = _session_admin_client()

    if admin is None:
        st.session_state["persistent_debug"] = (
            "ERROR: no se pudo crear admin client"
        )
        return None

    token = secrets.token_urlsafe(48)
    token_hash = _hash_session_token(token)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        days=PERSISTENT_SESSION_DAYS
    )

    try:
        admin.table("user_sessions").insert(
            {
                "user_id": str(user_id),
                "session_token_hash": token_hash,
                "expires_at": expires_at.isoformat(),
                "last_seen_at": now.isoformat(),
            }
        ).execute()

        st.session_state["persistent_debug"] = (
            "OK: sesión persistente creada"
        )

        return token

    except Exception as error:
        st.session_state["persistent_debug"] = (
            f"ERROR SUPABASE: {error}"
        )
        return None


def _restore_persistent_user(token):
    if not token:
        return None

    admin = _session_admin_client()

    if admin is None:
        return None

    token_hash = _hash_session_token(token)

    try:
        response = (
            admin.table("user_sessions")
            .select(
                "id,user_id,expires_at,revoked_at"
            )
            .eq(
                "session_token_hash",
                token_hash,
            )
            .maybe_single()
            .execute()
        )

        session = response.data

        if not session:
            return None

        if session.get("revoked_at"):
            return None

        expires_at = datetime.fromisoformat(
            session["expires_at"].replace(
                "Z",
                "+00:00",
            )
        )

        now = datetime.now(timezone.utc)

        if expires_at <= now:
            return None

        admin.table("user_sessions").update(
            {
                "last_seen_at": now.isoformat(),
            }
        ).eq(
            "id",
            session["id"],
        ).execute()

        return session["user_id"]

    except Exception:
        return None


def _revoke_persistent_session(token):
    if not token:
        return

    admin = _session_admin_client()

    if admin is None:
        return

    try:
        admin.table("user_sessions").update(
            {
                "revoked_at": datetime.now(
                    timezone.utc
                ).isoformat()
            }
        ).eq(
            "session_token_hash",
            _hash_session_token(token),
        ).execute()

    except Exception:
        pass

   


def render_cookie_test():
    st.markdown("### Prueba cookie persistente")

    col1, col2 = st.columns(2)

    with col1:
        escribir = st.button(
            "Crear cookie de prueba",
            key="create_cookie_test",
        )

    with col2:
        borrar = st.button(
            "Borrar cookie de prueba",
            key="delete_cookie_test",
        )

    action = "read"
    value = None

    if escribir:
        action = "write"
        value = "MACROFX_OK"

    elif borrar:
        action = "delete"

    result = _cookie_test_component(
        data={
            "action": action,
            "value": value,
        },
        default={
            "cookie_value": None,
        },
        key="macrofx_cookie_test",
        on_cookie_value_change=lambda: None,
        height=0,
    )

    st.write(
        "Cookie detectada:",
        result.cookie_value or "NINGUNA",
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


def _get_make_webhook_url():
    try:
        return st.secrets["make"]["resend_access_webhook"]
    except Exception:
        st.error(
            "Falta configurar el webhook de recuperación "
            "en los secretos de Streamlit."
        )
        st.stop()


def send_password_reset_request(email: str) -> bool:
    normalized_email = email.strip().lower()

    if not normalized_email:
        return False

    try:
        response = requests.post(
            _get_make_webhook_url(),
            json={"email": normalized_email},
            timeout=15,
        )

        return 200 <= response.status_code < 300

    except requests.RequestException:
        return False


def _clear_session():
    for key in SESSION_KEYS:
        st.session_state.pop(key, None)


def _save_session(response):
    session = getattr(response, "session", None)
    user = getattr(response, "user", None)

    if not session or not user:
        return False

    st.session_state["sb_access_token"] = session.access_token
    st.session_state["sb_refresh_token"] = session.refresh_token
    st.session_state["sb_user_id"] = user.id
    st.session_state["sb_user_email"] = user.email or ""

    return True


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

        if not response.user:
            _clear_session()
            return False

        if response.session:
            st.session_state["sb_access_token"] = (
                response.session.access_token
            )

            st.session_state["sb_refresh_token"] = (
                response.session.refresh_token
            )

        st.session_state["sb_user_id"] = response.user.id
        st.session_state["sb_user_email"] = (
            response.user.email or ""
        )

        return True

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
    return (
        bool(profile)
        and str(profile.get("estado", "")).strip().lower()
        == "activo"
    )


def _perform_login(email, password):
    client = _client()
    normalized_email = email.strip().lower()

    try:
        response = client.auth.sign_in_with_password(
            {
                "email": normalized_email,
                "password": password,
            }
        )

        if not response.user or not response.session:
            return False, "No se pudo iniciar sesión."

        profile = _load_profile(
            client,
            response.user.id,
        )

        if not _is_active(profile):
            try:
                client.auth.sign_out()
            except Exception:
                pass

            return (
                False,
                "Tu cuenta no tiene acceso activo a Macro FX.",
            )

        _save_session(response)
        st.session_state["sb_profile"] = profile

        persistent_token = _create_persistent_session(
            response.user.id
        )

        if persistent_token:
            st.session_state[
                "pending_persistent_cookie"
            ] = persistent_token

        st.session_state["debug_token_created"] = bool(persistent_token)
        return True, ""

    except Exception as error:
        message = str(error).lower()

        if "invalid login credentials" in message:
            return False, "Correo o contraseña incorrectos."

        if "email not confirmed" in message:
            return False, "Confirma tu correo antes de entrar."

        return False, f"No se pudo iniciar sesión: {error}"

def _auth_page_styles():
    st.markdown(
        """
        <style>
            section[data-testid="stSidebar"],
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
                box-shadow:
                    0 18px 50px rgba(0, 0, 0, .16);
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
                box-shadow:
                    0 6px 22px rgba(17, 24, 39, .06);
            }

            div[data-testid="stFormSubmitButton"] button {
                width: 100%;
                border-radius: 9px;
                font-weight: 800;
            }

            div[data-testid="stFormSubmitButton"]
            button[kind="primary"] {
                background: #C9A227;
                color: #111111;
                border: none;
            }

            #MainMenu,
            footer {
                visibility: hidden;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_login():
    _auth_page_styles()

    st.markdown(
        """
<div class="login-shell">
<div class="login-eyebrow">FINANS TRADING</div>
<div class="login-title">Acceso privado a Macro FX</div>
<div class="login-subtitle">Inicia sesión con el correo y la contraseña recibidos.</div>
</div>
""",
        unsafe_allow_html=True,
    )

    if st.session_state.pop("password_updated", False):
        st.success("Contraseña actualizada correctamente.")

    with st.form("macro_fx_login"):
        email = st.text_input("Correo electrónico")
        password = st.text_input("Contraseña", type="password")

        login_column, recovery_column = st.columns([1, 1])

        with login_column:
            submitted = st.form_submit_button(
                "Iniciar sesión",
                type="primary",
                use_container_width=True,
            )

        with recovery_column:
            forgot = st.form_submit_button(
                "¿Olvidaste tu contraseña?",
                use_container_width=True,
            )

    if forgot:
        if not email.strip():
            st.warning(
                "Introduce primero tu correo electrónico."
            )
            st.stop()

        request_sent = send_password_reset_request(
            email
        )

        if request_sent:
            st.success(
                "Si el correo existe en nuestro sistema, "
                "te hemos enviado una nueva contraseña "
                "temporal."
            )
        else:
            st.error(
                "No se ha podido procesar la solicitud. "
                "Inténtalo de nuevo."
            )

        st.stop()

    if submitted:
        if not email.strip() or not password:
            st.warning(
                "Introduce tu correo y contraseña."
            )
            st.stop()

        ok, error = _perform_login(
            email,
            password,
        )

        if ok:
            st.rerun()

        st.error(error)

    st.caption(
        "Acceso reservado a usuarios autorizados."
    )


def require_authenticated_user():
    client = _client()

    # --------------------------------------------------------
    # 1. Determinar qué debe hacer EL ÚNICO componente
    #    persistente de cookies en este rerun
    # --------------------------------------------------------

    logout_pending = st.session_state.pop(
        "logout_cookie_pending",
        False,
    )

    pending_token = st.session_state.get(
        "pending_persistent_cookie"
    )

    if pending_token:
        st.session_state["debug_pending_token"] = True
    elif "debug_pending_token" not in st.session_state:
        st.session_state["debug_pending_token"] = False

    st.warning(
        f"DEBUG — token creado: "
        f"{st.session_state.get('debug_token_created', False)}"
        f" · pending recibido: "
        f"{bool(pending_token)}"
    )

    cookie_action = "read"
    cookie_value_to_write = None

    if logout_pending:
        cookie_action = "delete"

    elif pending_token:
        cookie_action = "write"
        cookie_value_to_write = pending_token

        st.session_state[
            "persistent_cookie_token"
        ] = pending_token

    # IMPORTANTE:
    # El mismo componente y la misma key se renderizan
    # siempre, independientemente del estado del login.
    browser_cookie = _persistent_cookie(
        action=cookie_action,
        value=cookie_value_to_write,
    )

    # --------------------------------------------------------
    # 2. Logout
    # --------------------------------------------------------

    if logout_pending:
        st.session_state.pop(
            "persistent_cookie_token",
            None,
        )

        _clear_session()
        _render_login()
        st.stop()

    # --------------------------------------------------------
    # 3. Si el componente ya nos devuelve la cookie,
    #    conservarla para restauración/logout
    # --------------------------------------------------------

    if browser_cookie:
        st.session_state[
            "persistent_cookie_token"
        ] = browser_cookie

    # --------------------------------------------------------
    # 4. Sesión normal de Streamlit
    # --------------------------------------------------------

    profile = st.session_state.get(
        "sb_profile"
    )

    if profile and _is_active(profile):
        return profile

    # --------------------------------------------------------
    # 5. Intentar restaurar sesión Supabase existente
    # --------------------------------------------------------

    if _restore_session(client):
        try:
            response = client.auth.get_user()
            user = response.user

        except Exception:
            user = None

        if user:
            profile = _load_profile(
                client,
                user.id,
            )

            if _is_active(profile):
                st.session_state[
                    "sb_profile"
                ] = profile

                return profile

    # --------------------------------------------------------
    # 6. F5 / nueva sesión Streamlit:
    #    restaurar desde cookie persistente
    # --------------------------------------------------------

    persistent_token = (
        browser_cookie
        or st.session_state.get(
            "persistent_cookie_token"
        )
    )

    persistent_user_id = (
        _restore_persistent_user(
            token=persistent_token
        )
    )

    if persistent_user_id:
        admin = _session_admin_client()

        if admin is not None:
            profile = _load_profile(
                admin,
                persistent_user_id,
            )

            if _is_active(profile):
                st.session_state[
                    "sb_user_id"
                ] = persistent_user_id

                st.session_state[
                    "sb_user_email"
                ] = (
                    profile.get("email")
                    or ""
                )

                st.session_state[
                    "sb_profile"
                ] = profile

                return profile

    # --------------------------------------------------------
    # 7. No hay ninguna sesión válida
    # --------------------------------------------------------

    _clear_session()
    _render_login()
    st.stop()

def _change_password_form():
    with st.expander(
        "Mi cuenta · Cambiar contraseña",
        expanded=False,
    ):
        with st.form(
            "macro_fx_change_password",
            clear_on_submit=True,
        ):
            new_password = st.text_input(
                "Nueva contraseña",
                type="password",
            )

            confirmation = st.text_input(
                "Repetir nueva contraseña",
                type="password",
            )

            submitted = st.form_submit_button(
                "Guardar contraseña"
            )

        if submitted:
            if len(new_password) < 8:
                st.warning(
                    "La contraseña debe tener "
                    "al menos 8 caracteres."
                )
                return

            if new_password != confirmation:
                st.warning(
                    "Las contraseñas no coinciden."
                )
                return

            try:
                client = _client()

                if not _restore_session(client):
                    st.error(
                        "La sesión ha caducado. "
                        "Cierra sesión y vuelve a entrar."
                    )
                    return

                client.auth.update_user(
                    {"password": new_password}
                )

                st.success(
                    "Contraseña actualizada "
                    "correctamente."
                )

            except Exception as error:
                message = str(error).lower()

                if (
                    "different from the old password"
                    in message
                ):
                    st.warning(
                        "La nueva contraseña debe ser "
                        "diferente de la actual."
                    )
                else:
                    st.error(
                        "No se pudo cambiar la "
                        f"contraseña: {error}"
                    )


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

    _change_password_form()

    if st.button(
        "Cerrar sesión",
        use_container_width=True,
    ):
        token = st.session_state.get(
            "persistent_cookie_token"
        )

        _revoke_persistent_session(token)

        try:
            client = _client()
            _restore_session(client)
            client.auth.sign_out()
        except Exception:
            pass

        _clear_session()

        st.session_state[
            "logout_cookie_pending"
        ] = True

        st.rerun()
