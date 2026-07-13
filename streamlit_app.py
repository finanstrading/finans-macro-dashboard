import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# ---------------------------------------------------
# CONFIGURACIÓN GENERAL
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
# ESTILO
# ---------------------------------------------------

st.markdown(
    """
    <style>
        .block-container {
            max-width: 1500px;
            padding-top: 2rem;
            padding-bottom: 2rem;
        }

        .dashboard-header {
            margin-bottom: 1.5rem;
        }

        .dashboard-title {
            font-size: 2.2rem;
            font-weight: 750;
            margin-bottom: 0.2rem;
        }

        .dashboard-subtitle {
            font-size: 1rem;
            color: #667085;
        }

        div[data-testid="stMetric"] {
            background-color: #f8fafc;
            border: 1px solid #e5e7eb;
            padding: 18px;
            border-radius: 12px;
        }

        div[data-testid="stMetricLabel"] {
            font-weight: 600;
        }

        div[data-testid="stMetricValue"] {
            font-size: 2rem;
        }

        .section-title {
            font-size: 1.1rem;
            font-weight: 700;
            margin-top: 1rem;
            margin-bottom: 0.5rem;
        }
    </style>
    """,
    unsafe_allow_html=True
)

# ---------------------------------------------------
# CARGAR DATOS
# ---------------------------------------------------

@st.cache_data(ttl=600)
def cargar_datos():
    return pd.read_csv(csv_url)


# ---------------------------------------------------
# CABECERA
# ---------------------------------------------------

st.markdown(
    """
    <div class="dashboard-header">
        <div class="dashboard-title">Finans Trading Dashboard</div>
        <div class="dashboard-subtitle">
            GBP · Indicadores macroeconómicos
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

try:
    df = cargar_datos()

    # ---------------------------------------------------
    # CONVERTIR FECHAS
    # ---------------------------------------------------

    meses = {
        "ene": 1,
        "feb": 2,
        "mar": 3,
        "abr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "ago": 8,
        "sep": 9,
        "sept": 9,
        "oct": 10,
        "nov": 11,
        "dic": 12
    }

    fecha_separada = (
        df["DATE"]
        .astype(str)
        .str.lower()
        .str.strip()
        .str.split("-", expand=True)
    )

    df["Mes"] = fecha_separada[0].map(meses)
    df["Año"] = pd.to_numeric(
        fecha_separada[1],
        errors="coerce"
    )

    df["Año"] = df["Año"].apply(
        lambda año: año + 2000 if pd.notna(año) and año < 100 else año
    )

    df["Fecha"] = pd.to_datetime(
        {
            "year": df["Año"],
            "month": df["Mes"],
            "day": 1
        },
        errors="coerce"
    )

    df = (
        df
        .dropna(subset=["Fecha"])
        .sort_values("Fecha")
        .reset_index(drop=True)
    )

    # ---------------------------------------------------
    # SELECTOR DE INDICADOR
    # ---------------------------------------------------

    columnas_excluidas = [
        "DATE",
        "Fecha",
        "Mes",
        "Año"
    ]

    indicadores = [
        columna
        for columna in df.columns
        if columna not in columnas_excluidas
    ]

    indicador = st.selectbox(
        "Selecciona un indicador",
        indicadores
    )

    # ---------------------------------------------------
    # CONVERTIR VALORES NUMÉRICOS
    # ---------------------------------------------------

    valores_limpios = (
        df[indicador]
        .astype(str)
        .str.replace("%", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False)
    )

    df["Valor"] = pd.to_numeric(
        valores_limpios,
        errors="coerce"
    )

    datos = (
        df[["Fecha", "Valor"]]
        .dropna()
        .sort_values("Fecha")
        .reset_index(drop=True)
    )

    if datos.empty:
        st.warning(
            "Este indicador todavía no contiene datos disponibles."
        )
        st.stop()

    # ---------------------------------------------------
    # MÉTRICAS
    # ---------------------------------------------------

    ultimo_registro = datos.iloc[-1]
    ultimo_valor = ultimo_registro["Valor"]
    ultima_fecha = ultimo_registro["Fecha"]

    if len(datos) >= 2:
        valor_anterior = datos.iloc[-2]["Valor"]
        variacion = ultimo_valor - valor_anterior
    else:
        valor_anterior = None
        variacion = None

    indicadores_porcentaje = [
        "CPI",
        "CPI YoY",
        "Core CPI",
        "Core CPI YoY",
        "Retail Sales",
        "Core Retail Sales",
        "% Change",
        "%Desempleo",
        "% Salario + Bonus",
        "% Salario - Bonus"
    ]

    usa_porcentaje = indicador in indicadores_porcentaje
    sufijo = "%" if usa_porcentaje else ""

    ultimo_texto = f"{ultimo_valor:,.2f}{sufijo}"

    if valor_anterior is not None:
        anterior_texto = f"{valor_anterior:,.2f}{sufijo}"
        variacion_texto = f"{variacion:+.2f}{sufijo}"
    else:
        anterior_texto = "Sin dato"
        variacion_texto = None

    fecha_texto = ultima_fecha.strftime("%m/%Y")

    columna_1, columna_2, columna_3 = st.columns(3)

    with columna_1:
        st.metric(
            label="Último dato",
            value=ultimo_texto,
            delta=variacion_texto
        )

    with columna_2:
        st.metric(
            label="Dato anterior",
            value=anterior_texto
        )

    with columna_3:
        st.metric(
            label="Última publicación",
            value=fecha_texto
        )

    # ---------------------------------------------------
    # GRÁFICO
    # ---------------------------------------------------

    st.markdown(
        f'<div class="section-title">Evolución histórica de {indicador}</div>',
        unsafe_allow_html=True
    )

    figura = go.Figure()

    figura.add_trace(
        go.Scatter(
            x=datos["Fecha"],
            y=datos["Valor"],
            mode="lines",
            name=indicador,
            line=dict(width=2.4),
            hovertemplate=(
                "%{x|%b %Y}"
                "<br><b>%{y:.2f}</b>"
                + sufijo
                + "<extra></extra>"
            )
        )
    )

    figura.add_hline(
        y=0,
        line_width=1,
        line_dash="dot",
        opacity=0.45
    )

    figura.update_layout(
        height=620,
        margin=dict(
            l=30,
            r=30,
            t=30,
            b=20
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        showlegend=False,
        xaxis_title="",
        yaxis_title=indicador,
        font=dict(size=14)
    )

    figura.update_xaxes(
        showgrid=False,
        rangeslider_visible=False,
        rangeselector=dict(
            buttons=[
                dict(
                    count=1,
                    label="1A",
                    step="year",
                    stepmode="backward"
                ),
                dict(
                    count=3,
                    label="3A",
                    step="year",
                    stepmode="backward"
                ),
                dict(
                    count=5,
                    label="5A",
                    step="year",
                    stepmode="backward"
                ),
                dict(
                    count=10,
                    label="10A",
                    step="year",
                    stepmode="backward"
                ),
                dict(
                    label="Todo",
                    step="all"
                )
            ],
            x=0,
            y=1.12
        ),
        tickformat="%Y"
    )

    figura.update_yaxes(
        gridcolor="rgba(120, 130, 150, 0.15)",
        zeroline=False
    )

    st.plotly_chart(
        figura,
        use_container_width=True,
        config={
            "displaylogo": False,
            "scrollZoom": True,
            "modeBarButtonsToRemove": [
                "select2d",
                "lasso2d"
            ]
        }
    )

except Exception as error:
    st.error("No se pudo cargar el dashboard.")
    st.exception(error)
