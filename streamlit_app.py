import streamlit as st
import pandas as pd
import plotly.express as px

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

st.title("📈 Finans Trading Dashboard")
st.subheader("GBP — Indicadores macroeconómicos")


@st.cache_data(ttl=600)
def cargar_datos():
    return pd.read_csv(csv_url)


try:
    df = cargar_datos()

    # Convertir fechas como ene-10, feb-10, mar-10...
    meses = {
        "ene": "01",
        "feb": "02",
        "mar": "03",
        "abr": "04",
        "may": "05",
        "jun": "06",
        "jul": "07",
        "ago": "08",
        "sept": "09",
        "sep": "09",
        "oct": "10",
        "nov": "11",
        "dic": "12"
    }

    fechas_separadas = df["DATE"].astype(str).str.lower().str.strip().str.split("-", expand=True)

    df["Mes"] = fechas_separadas[0].replace(meses)
    df["Año"] = fechas_separadas[1].astype(str)

    df["Año"] = df["Año"].apply(
        lambda x: "20" + x if len(x) == 2 else x
    )

    df["Fecha"] = pd.to_datetime(
        df["Año"] + "-" + df["Mes"] + "-01",
        errors="coerce"
    )

    df = df.dropna(subset=["Fecha"]).sort_values("Fecha")

    indicadores = [
        columna for columna in df.columns
        if columna not in ["DATE", "Fecha", "Mes", "Año"]
    ]

    indicador = st.selectbox(
        "Selecciona un indicador:",
        indicadores
    )

    # Convertir porcentajes y números escritos con coma
    df["Valor"] = (
        df[indicador]
        .astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .str.strip()
    )

    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce")

    datos_grafico = df.dropna(subset=["Valor"]).copy()

    if datos_grafico.empty:
        st.warning("Este indicador no contiene datos disponibles.")
    else:
        fecha_minima = datos_grafico["Fecha"].min().date()
        fecha_maxima = datos_grafico["Fecha"].max().date()

        rango_fechas = st.date_input(
            "Selecciona el periodo:",
            value=(fecha_minima, fecha_maxima),
            min_value=fecha_minima,
            max_value=fecha_maxima,
            format="MM/YYYY"
        )

        if len(rango_fechas) == 2:
            fecha_inicio = pd.Timestamp(rango_fechas[0])
            fecha_final = pd.Timestamp(rango_fechas[1])

            datos_grafico = datos_grafico[
                (datos_grafico["Fecha"] >= fecha_inicio)
                & (datos_grafico["Fecha"] <= fecha_final)
            ]

        figura = px.line(
            datos_grafico,
            x="Fecha",
            y="Valor",
            markers=True,
            title=f"Evolución histórica de {indicador}"
        )

        figura.update_layout(
            xaxis_title="Fecha",
            yaxis_title=indicador,
            hovermode="x unified",
            height=600
        )

        figura.update_xaxes(
            rangeslider_visible=True,
            tickformat="%b %Y"
        )

        figura.update_traces(
            hovertemplate="%{x|%b %Y}<br>%{y:.2f}<extra></extra>"
        )

        st.plotly_chart(
            figura,
            use_container_width=True,
            config={
                "displaylogo": False,
                "scrollZoom": True
            }
        )

except Exception as e:
    st.error("No se pudo cargar el dashboard.")
    st.exception(e)
