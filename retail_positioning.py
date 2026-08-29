import requests
import streamlit as st


MYFXBOOK_BASE_URL = "https://www.myfxbook.com/api"


def myfxbook_login(http_session):

    email = st.secrets["MYFXBOOK_EMAIL"]
    password = st.secrets["MYFXBOOK_PASSWORD"]

    response = http_session.get(
        f"{MYFXBOOK_BASE_URL}/login.json",
        params={
            "email": email,
            "password": password,
        },
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    if data.get("error"):
        raise ValueError(
            f"Error de login Myfxbook: {data.get('message')}"
        )

    session_id = data.get("session")

    if not session_id:
        raise ValueError(
            f"Myfxbook no devolvió Session ID. Respuesta: {data}"
        )

    return session_id


def cargar_retail_outlook():

    with requests.Session() as http_session:

        session_id = myfxbook_login(http_session)

        st.write("Session recibida:", session_id[:6] + "...")

        # Prueba 1: comprobar si la sesión funciona
        test_response = http_session.get(
            f"{MYFXBOOK_BASE_URL}/get-my-accounts.json",
            params={"session": session_id},
            timeout=20,
        )

        test_data = test_response.json()

        st.write(
            "Test sesión:",
            {
                "error": test_data.get("error"),
                "message": test_data.get("message"),
            },
        )

        # Prueba 2: Community Outlook
        response = http_session.get(
            f"{MYFXBOOK_BASE_URL}/get-community-outlook.json",
            params={"session": session_id},
            timeout=20,
        )

        response.raise_for_status()

        data = response.json()

        st.write(
            "Test Community Outlook:",
            {
                "error": data.get("error"),
                "message": data.get("message"),
            },
        )

        if data.get("error"):
            raise ValueError(
                f"Error de Myfxbook: {data.get('message')}"
            )

        return data.get("symbols", [])


def render_retail_test():

    st.title("Test · Posicionamiento Retail")

    try:

        symbols = cargar_retail_outlook()

        if not symbols:
            st.warning(
                "Myfxbook respondió correctamente, "
                "pero no devolvió símbolos."
            )
            return

        st.success(
            f"Conexión correcta con Myfxbook · "
            f"{len(symbols)} mercados recibidos."
        )

        pares_objetivo = {
            "EURUSD",
            "GBPUSD",
            "USDJPY",
            "USDCHF",
            "USDCAD",
            "AUDUSD",
            "NZDUSD",
        }

        encontrados = [
            item
            for item in symbols
            if item.get("name") in pares_objetivo
        ]

        st.write("Pares encontrados:")

        for item in encontrados:

            st.write(
                item.get("name"),
                {
                    "Long %": item.get("longPercentage"),
                    "Short %": item.get("shortPercentage"),
                    "Long Volume": item.get("longVolume"),
                    "Short Volume": item.get("shortVolume"),
                    "Long Positions": item.get("longPositions"),
                    "Short Positions": item.get("shortPositions"),
                    "Avg Long Price": item.get("avgLongPrice"),
                    "Avg Short Price": item.get("avgShortPrice"),
                },
            )

    except Exception as error:

        st.error(
            f"Error conectando con Myfxbook: {error}"
        )

    if __name__ == "__main__":
        render_retail_test()
