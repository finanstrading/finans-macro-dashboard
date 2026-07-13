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

CSV_URL = (
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
            margin-bottom: 1.4rem;
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
            margin-top: 1.2rem;
            margin-bottom: 0.4rem;
        }

        div[data-testid="stRadio"] > div {
            gap: 0.6rem;
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
    return pd.read_csv(CSV_URL)


# ---------------------------------------------------
# FUNCIONES AUXILIARES
# ---------------------------------------------------

def añadir_margen(valor_minimo, valor_maximo):
    """Añade espacio visual arriba y abajo del gráfico."""

    if valor_minimo == valor_maximo:
        margen = max(abs(valor_minimo) * 0.10, 1)
    else:
        margen = (valor_maximo - valor_minimo) * 0.10

    return valor_minimo - margen, valor_maximo + margen


def formatear_valor(valor, sufijo):
    return f"{valor:,.2f}{sufijo}"


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
        lambda año: año + 2000
        if pd.notna(año) and año < 100
        else año
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
    # CONVERTIR LOS VALORES
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

    datos_completos = (
        df[["Fecha", "Valor"]]
        .dropna()
        .sort_values("Fecha")
        .reset_index(drop=True)
    )

    if datos_completos.empty:
        st.warning(
            "Este indicador todavía no contiene datos disponibles."
        )
        st.stop()

    fecha_minima = datos_completos["Fecha"].min()
    fecha_maxima = datos_completos["Fecha"].max()

    # ---------------------------------------------------
    # MÉTRICAS SUPERIORES
    # ---------------------------------------------------

    ultimo_registro = datos_completos.iloc[-1]
    ultimo_valor = ultimo_registro["Valor"]
    ultima_fecha = ultimo_registro["Fecha"]

    if len(datos_completos) >= 2:
        valor_anterior = datos_completos.iloc[-2]["Valor"]
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

    sufijo = "%" if indicador in indicadores_porcentaje else ""

    ultimo_texto = formatear_valor(
        ultimo_valor,
        sufijo
    )

    if valor_anterior is not None:
        anterior_texto = formatear_valor(
            valor_anterior,
            sufijo
        )

        variacion_texto = (
            f"{variacion:+.2f}{sufijo}"
        )
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
    # CONTROLES DEL GRÁFICO
    # ---------------------------------------------------

    st.markdown(
        f'<div class="section-title">'
        f'Evolución histórica de {indicador}'
        f'</div>',
        unsafe_allow_html=True
    )

    columna_periodo, columna_escala = st.columns([1.3, 1])

    with columna_periodo:
        periodo = st.radio(
            "Periodo",
            options=[
                "1A",
                "3A",
                "5A",
                "10A",
                "Todo"
            ],
            index=1,
            horizontal=True
        )

    with columna_escala:
        modo_escala = st.radio(
            "Escala vertical",
            options=[
                "Automática",
                "Sin extremos",
                "Manual"
            ],
            index=0,
            horizontal=True
        )

    # ---------------------------------------------------
    # FILTRAR EL PERIODO
    # ---------------------------------------------------

    años_por_periodo = {
        "1A": 1,
        "3A": 3,
        "5A": 5,
        "10A": 10
    }

    if periodo == "Todo":
        fecha_inicio = fecha_minima
    else:
        años = años_por_periodo[periodo]
        fecha_inicio = fecha_maxima - pd.DateOffset(years=años)

    datos_visibles = datos_completos[
        (datos_completos["Fecha"] >= fecha_inicio)
        & (datos_completos["Fecha"] <= fecha_maxima)
    ].copy()

    if datos_visibles.empty:
        datos_visibles = datos_completos.copy()

    # ---------------------------------------------------
    # CALCULAR LA ESCALA VERTICAL
    # ---------------------------------------------------

    minimo_real = float(datos_visibles["Valor"].min())
    maximo_real = float(datos_visibles["Valor"].max())

    if modo_escala == "Automática":

        eje_minimo, eje_maximo = añadir_margen(
            minimo_real,
            maximo_real
        )

    elif modo_escala == "Sin extremos":

        if len(datos_visibles) >= 10:
            limite_inferior = float(
                datos_visibles["Valor"].quantile(0.05)
            )

            limite_superior = float(
                datos_visibles["Valor"].quantile(0.95)
            )
        else:
            limite_inferior = minimo_real
            limite_superior = maximo_real

        eje_minimo, eje_maximo = añadir_margen(
            limite_inferior,
            limite_superior
        )

        st.caption(
            "La escala ignora visualmente el 5 % de los valores "
            "más bajos y el 5 % de los más altos. "
            "Los datos originales no se eliminan."
        )

    else:

        valor_sugerido_minimo, valor_sugerido_maximo = añadir_margen(
            minimo_real,
            maximo_real
        )

        manual_1, manual_2 = st.columns(2)

        with manual_1:
            eje_minimo = st.number_input(
                "Mínimo del eje vertical",
                value=float(round(valor_sugerido_minimo, 2)),
                step=1.0
            )

        with manual_2:
            eje_maximo = st.number_input(
                "Máximo del eje vertical",
                value=float(round(valor_sugerido_maximo, 2)),
                step=1.0
            )

        if eje_minimo >= eje_maximo:
            st.warning(
                "El máximo debe ser superior al mínimo."
            )
            st.stop()

    # ---------------------------------------------------
    # CREAR EL GRÁFICO
    # ---------------------------------------------------

    figura = go.Figure()

    figura.add_trace(
        go.Scatter(
            x=datos_visibles["Fecha"],
            y=datos_visibles["Valor"],
            mode="lines",
            name=indicador,
            line=dict(width=2.5),
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
        height=610,
        margin=dict(
            l=30,
            r=30,
            t=30,
            b=25
        ),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        hovermode="x unified",
        showlegend=False,
        xaxis_title="",
        yaxis_title=indicador,
        font=dict(size=14),
        dragmode=False
    )

    figura.update_xaxes(
        type="date",
        range=[
            datos_visibles["Fecha"].min(),
            fecha_maxima
        ],
        minallowed=fecha_minima,
        maxallowed=fecha_maxima,
        rangeslider_visible=False,
        showgrid=False,
        tickformat="%b %Y",
        fixedrange=True
    )

    figura.update_yaxes(
        range=[
            eje_minimo,
            eje_maximo
        ],
        gridcolor="rgba(120, 130, 150, 0.15)",
        zeroline=False,
        fixedrange=True
    )

    st.plotly_chart(
        figura,
        use_container_width=True,
        config={
            "displaylogo": False,
            "scrollZoom": False,
            "displayModeBar": False
        }
    )

except Exception as error:
    st.error("No se pudo cargar el dashboard.")
    st.exception(error)
