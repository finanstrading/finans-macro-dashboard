import streamlit as st
import pandas as pd
import plotly.express as px

# ---------------------------------------------------
# CONFIGURACIÓN
# ---------------------------------------------------

st.set_page_config(
    page_title="Finans Trading Dashboard",
    page_icon="📈",
    layout="wide"
)

SHEET_ID = "1dJB_3wWsSOkXm59dEJKYZlkK_wMlp89Pu1GObCNnyQU"
SHEET_NAME = "Dashboard_GBP"

csv_url = (
    f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?"
    f"tqx=out:csv&sheet={SHEET_NAME}"
)

# ---------------------------------------------------
# CARGAR DATOS
# ---------------------------------------------------

@st.cache_data
def cargar_datos():
    return pd.read_csv(csv_url)

st.title("📈 Finans Trading Dashboard")
st.subheader("GBP — Indicadores macroeconómicos")

try:

    df = cargar_datos()

    # ----------------------------
    # Convertir fecha
    # ----------------------------

    meses = {
        "ene":1,
        "feb":2,
        "mar":3,
        "abr":4,
        "may":5,
        "jun":6,
        "jul":7,
        "ago":8,
        "sep":9,
        "sept":9,
        "oct":10,
        "nov":11,
        "dic":12
    }

    fechas = df["DATE"].astype(str).str.lower().str.split("-")

    df["Mes"] = fechas.str[0].map(meses)
    df["Año"] = fechas.str[1].astype(int) + 2000

    df["Fecha"] = pd.to_datetime(
        dict(
            year=df["Año"],
            month=df["Mes"],
            day=1
        )
    )

    # ----------------------------
    # Indicadores disponibles
    # ----------------------------

    excluir = [
        "DATE",
        "Fecha",
        "Mes",
        "Año"
    ]

    indicadores = [
        c for c in df.columns
        if c not in excluir
    ]

    indicador = st.selectbox(
        "Selecciona un indicador",
        indicadores
    )

    # ----------------------------
    # Convertir valores
    # ----------------------------

    serie = (
        df[indicador]
        .astype(str)
        .str.replace("%","",regex=False)
        .str.replace(",",".",regex=False)
    )

    df["Valor"] = pd.to_numeric(
        serie,
        errors="coerce"
    )

    datos = df.dropna(subset=["Valor"])

    # ----------------------------
    # Gráfico
    # ----------------------------

    fig = px.line(
        datos,
        x="Fecha",
        y="Valor",
        markers=True,
        title=indicador
    )

    fig.update_layout(
        height=650,
        hovermode="x unified"
    )

    fig.update_xaxes(
        rangeslider_visible=True
    )

    st.plotly_chart(
        fig,
        use_container_width=True
    )

except Exception as e:

    st.error("Ha ocurrido un error.")

    st.exception(e)
