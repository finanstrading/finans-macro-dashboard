import requests
import streamlit as st


MYFXBOOK_BASE_URL = "https://www.myfxbook.com/api"


def myfxbook_login():

    email = st.secrets["MYFXBOOK_EMAIL"]
    password = st.secrets["MYFXBOOK_PASSWORD"]

    response = requests.get(
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
            f"Error de Myfxbook: {data.get('message')}"
        )

    session = data.get("session")

    if not session:
        raise ValueError(
            "Myfxbook no devolvió un Session ID."
        )

    return session


def cargar_retail_outlook():

    session = myfxbook_login()

    response = requests.get(
        f"{MYFXBOOK_BASE_URL}/get-community-outlook.json",
        params={
            "session": session,
        },
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

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
