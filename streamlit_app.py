import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from urllib.parse import quote


# =========================================================
# CONFIGURACIÓN GENERAL
# =========================================================

st.set_page_config(
    page_title="Macro FX",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

SHEET_ID = "1dJB_3wWsSOkXm59dEJKYZlkK_wMlp89Pu1GObCNnyQU"

MERCADOS = {
    "GBP": "Dashboard_GBP",
    "USD": "Dashboard_USD",
}


# =========================================================
# DISEÑO
# =========================================================

st.markdown(
    """
    <style>

    /* Fondo general */
    .stApp {
        background-color: #07111f;
    }

    /* Limitar ancho */
    .block-container {
        max-width: 1450px;
        padding-top: 2rem;
        padding-bottom: 3rem;
    }

    /* Títulos */
    h1, h2, h3 {
        color: #ffffff;
    }

    /* Texto general */
    p, label, .stMarkdown {
        color: #dce4ef;
    }

    /* Ocultar elementos de Streamlit */
    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }

    header {
        background-color: transparent;
    }

    /* Selectbox cerrado */
    div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        border: 1px solid #c7a55b !important;
        border-radius: 9px !important;
        color: #000000 !important;
    }

    /* Texto seleccionado dentro del selector */
    div[data-baseweb="select"] span {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }

    /* Flecha del selector */
    div[data-baseweb="select"] svg {
        fill: #000000 !important;
        color: #000000 !important;
    }

    /* Opciones desplegadas */
    ul[role="listbox"] {
        background-color: #ffffff !important;
    }

    li[role="option"] {
        background-color: #ffffff !important;
        color: #000000 !important;
    }

    li[role="option"] span {
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }

    li[role="option"]:hover {
        background-color: #eadcb9 !important;
        color: #000000 !important;
    }

    /* Campo de fechas */
    div[data-baseweb="input"] input {
        background-color: #ffffff !important;
        color: #000000 !important;
        -webkit-text-fill-color: #000000 !important;
    }

    /* Botones */
    .stButton > button {
        background-color: #c7a55b;
        color: #07111f;
        border: none;
        border-radius: 8px;
        font-weight: 700;
    }

    /* Cajas informativas */
    div[data-testid="stAlert"] {
        border-radius: 10px;
    }

    /* Separador */
    hr {
        border-color: rgba(199, 165, 91, 0.35);
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# CARGA DE DATOS
# =========================================================

@st.cache_data(ttl=300, show_spinner=False)
def cargar_hoja(nombre_hoja: str) -> pd.DataFrame:
    """
    Descarga una pestaña concreta del Google Sheets en formato CSV.
    """

    hoja_codificada = quote(nombre_hoja)

    url = (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq"
        f"?tqx=out:csv&sheet={hoja_codificada}"
    )

    df = pd.read_csv(url)

    # Eliminar columnas totalmente vacías
    df = df.dropna(axis=1, how="all")

    if df.empty:
        raise ValueError(
            f"La pestaña {nombre_hoja} no contiene datos."
        )

    # La primera columna debe ser la fecha
    primera_columna = df.columns[0]

    df = df.rename(columns={primera_columna: "DATE"})

    df["DATE"] = pd.to_datetime(
        df["DATE"],
        errors="coerce",
        dayfirst=False,
    )

    # Eliminar filas sin fecha válida
    df = df.dropna(subset=["DATE"])

    # Ordenar cronológicamente
    df = df.sort_values("DATE")

    # Eliminar fechas duplicadas, conservando la última
    df = df.drop_duplicates(
        subset=["DATE"],
        keep="last",
    )

    return df


# =========================================================
# FUNCIONES AUXILIARES
# =========================================================

def convertir_a_numero(serie: pd.Series) -> pd.Series:
    """
    Convierte los datos de una columna a valores numéricos.
    También admite porcentajes escritos como texto.
    """

    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(serie, errors="coerce")

    texto = serie.astype(str).str.strip()

    contiene_porcentaje = texto.str.contains(
        "%",
        regex=False,
        na=False,
    ).any()

    texto = (
        texto
        .str.replace("%", "", regex=False)
        .str.replace(" ", "", regex=False)
        .str.replace(",", ".", regex=False)
    )

    valores = pd.to_numeric(texto, errors="coerce")

    if contiene_porcentaje:
        valores = valores / 100

    return valores


def es_indicador_porcentual(nombre: str) -> bool:
    """
    Detecta indicadores que normalmente deben mostrarse como porcentaje.
    """

    nombre = nombre.lower()

    palabras_porcentuales = [
        "cpi",
        "inflación",
        "inflacion",
        "retail sales",
        "desempleo",
        "unemployment",
        "salario",
        "wage",
        "earnings",
        "gdp",
        "pce",
        "ppi",
        "ventas minoristas",
        "%",
    ]

    return any(
        palabra in nombre
        for palabra in palabras_porcentuales
    )


def formato_ultimo_valor(
    valor: float,
    indicador: str,
) -> str:
    """
    Da formato al último dato mostrado.
    """

    if pd.isna(valor):
        return "Sin dato"

    if es_indicador_porcentual(indicador):
        return f"{valor:.2%}"

    if abs(valor) >= 1000:
        return f"{valor:,.0f}"

    return f"{valor:,.2f}"


# =========================================================
# ENCABEZADO
# =========================================================

st.markdown(
    """
    <div style="
        padding: 20px 24px;
        border: 1px solid rgba(199, 165, 91, 0.45);
        border-radius: 14px;
        background:
            linear-gradient(
                135deg,
                rgba(13, 30, 50, 0.97),
                rgba(7, 17, 31, 0.97)
            );
        margin-bottom: 25px;
    ">
        <div style="
            color: #c7a55b;
            font-size: 14px;
            font-weight: 700;
            letter-spacing: 2px;
        ">
            FINANS TRADING
        </div>

        <div style="
            color: #ffffff;
            font-size: 34px;
            font-weight: 800;
            margin-top: 4px;
        ">
            Macro FX
        </div>

        <div style="
            color: #aebbd0;
            font-size: 16px;
            margin-top: 5px;
        ">
            Evolución histórica de los principales indicadores macroeconómicos
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# =========================================================
# SELECTOR DE MERCADO
# =========================================================

col_mercado, col_indicador = st.columns([1, 2])

with col_mercado:
    mercado = st.selectbox(
        "Mercado",
        options=list(MERCADOS.keys()),
        index=0,
        key="selector_mercado",
    )

nombre_hoja = MERCADOS[mercado]


# =========================================================
# CARGAR EL MERCADO SELECCIONADO
# =========================================================

try:
    datos = cargar_hoja(nombre_hoja)

except Exception as error:
    st.error(
        f"No se pudo cargar la pestaña «{nombre_hoja}»."
    )

    st.info(
        "Comprueba que el nombre de la pestaña sea exacto, "
        "que no tenga espacios delante o detrás y que el "
        "Google Sheets esté compartido para lectura."
    )

    st.code(str(error))

    st.stop()


# =========================================================
# SELECTOR DINÁMICO DE INDICADORES
# =========================================================

indicadores = []

for columna in datos.columns:
    if columna == "DATE":
        continue

    serie_numerica = convertir_a_numero(datos[columna])

    if serie_numerica.notna().any():
        indicadores.append(columna)


if not indicadores:
    st.warning(
        f"No se encontraron indicadores con datos numéricos "
        f"en la pestaña {nombre_hoja}."
    )
    st.stop()


with col_indicador:
    indicador = st.selectbox(
        "Indicador",
        options=indicadores,
        index=0,
        key=f"selector_indicador_{mercado}",
    )


# =========================================================
# PREPARAR EL INDICADOR
# =========================================================

grafico = datos[["DATE", indicador]].copy()

grafico[indicador] = convertir_a_numero(
    grafico[indicador]
)

grafico = grafico.dropna(
    subset=[indicador]
)

if grafico.empty:
    st.warning(
        f"El indicador «{indicador}» no contiene datos válidos."
    )
    st.stop()


# =========================================================
# SELECTOR DE FECHAS
# =========================================================

fecha_minima = grafico["DATE"].min().date()
fecha_maxima = grafico["DATE"].max().date()

st.markdown("---")

col_periodo, col_inicio, col_fin = st.columns([1.2, 1, 1])

with col_periodo:
    periodo = st.selectbox(
        "Periodo",
        options=[
            "Todo",
            "Últimos 12 meses",
            "Últimos 3 años",
            "Últimos 5 años",
            "Últimos 10 años",
            "Personalizado",
        ],
        index=0,
    )


if periodo == "Últimos 12 meses":
    fecha_inicio = (
        pd.Timestamp(fecha_maxima)
        - pd.DateOffset(months=12)
    ).date()

elif periodo == "Últimos 3 años":
    fecha_inicio = (
        pd.Timestamp(fecha_maxima)
        - pd.DateOffset(years=3)
    ).date()

elif periodo == "Últimos 5 años":
    fecha_inicio = (
        pd.Timestamp(fecha_maxima)
        - pd.DateOffset(years=5)
    ).date()

elif periodo == "Últimos 10 años":
    fecha_inicio = (
        pd.Timestamp(fecha_maxima)
        - pd.DateOffset(years=10)
    ).date()

else:
    fecha_inicio = fecha_minima


if fecha_inicio < fecha_minima:
    fecha_inicio = fecha_minima


with col_inicio:
    if periodo == "Personalizado":
        fecha_inicio = st.date_input(
            "Desde",
            value=fecha_minima,
            min_value=fecha_minima,
            max_value=fecha_maxima,
            format="MM/YYYY",
        )
    else:
        st.date_input(
            "Desde",
            value=fecha_inicio,
            min_value=fecha_minima,
            max_value=fecha_maxima,
            format="MM/YYYY",
            disabled=True,
        )


with col_fin:
    fecha_fin = st.date_input(
        "Hasta",
        value=fecha_maxima,
        min_value=fecha_minima,
        max_value=fecha_maxima,
        format="MM/YYYY",
        disabled=periodo != "Personalizado",
    )


if fecha_inicio > fecha_fin:
    st.error(
        "La fecha inicial no puede ser posterior a la fecha final."
    )
    st.stop()


# =========================================================
# FILTRAR FECHAS
# =========================================================

grafico_filtrado = grafico[
    (
        grafico["DATE"].dt.date >= fecha_inicio
    )
    & (
        grafico["DATE"].dt.date <= fecha_fin
    )
].copy()


if grafico_filtrado.empty:
    st.warning(
        "No existen datos para el periodo seleccionado."
    )
    st.stop()


# =========================================================
# OPCIONES DEL GRÁFICO
# =========================================================

col_ajuste, col_cero, col_espacio = st.columns([1.2, 1.2, 3])

with col_ajuste:
    ajustar_eje = st.checkbox(
        "Comprimir eje vertical",
        value=False,
        help=(
            "Reduce el espacio vacío del eje vertical para "
            "observar mejor variaciones pequeñas."
        ),
    )

with col_cero:
    mostrar_linea_cero = st.checkbox(
        "Mostrar línea de cero",
        value=True,
    )


# =========================================================
# DATOS DESTACADOS
# =========================================================

ultimo_registro = grafico_filtrado.iloc[-1]
primer_registro = grafico_filtrado.iloc[0]

ultimo_valor = ultimo_registro[indicador]
primer_valor = primer_registro[indicador]

variacion_periodo = ultimo_valor - primer_valor

col_dato, col_fecha, col_variacion = st.columns(3)

with col_dato:
    st.metric(
        label="Último dato",
        value=formato_ultimo_valor(
            ultimo_valor,
            indicador,
        ),
    )

with col_fecha:
    st.metric(
        label="Última publicación",
        value=ultimo_registro["DATE"].strftime("%m/%Y"),
    )

with col_variacion:
    if es_indicador_porcentual(indicador):
        variacion_texto = (
            f"{variacion_periodo * 100:+.2f} puntos"
        )
    elif abs(variacion_periodo) >= 1000:
        variacion_texto = f"{variacion_periodo:+,.0f}"
    else:
        variacion_texto = f"{variacion_periodo:+,.2f}"

    st.metric(
        label="Cambio en el periodo",
        value=variacion_texto,
    )


# =========================================================
# CREAR GRÁFICO
# =========================================================

fig = go.Figure()

fig.add_trace(
    go.Scatter(
        x=grafico_filtrado["DATE"],
        y=grafico_filtrado[indicador],
        mode="lines+markers",
        name=indicador,
        line=dict(
            color="#c7a55b",
            width=2.5,
        ),
        marker=dict(
            color="#f1d28e",
            size=5,
        ),
        hovertemplate=(
            "<b>%{x|%m/%Y}</b><br>"
            + indicador
            + ": %{y:,.4f}"
            + "<extra></extra>"
        ),
    )
)


if mostrar_linea_cero:
    fig.add_hline(
        y=0,
        line_width=1,
        line_dash="dot",
        line_color="rgba(255,255,255,0.35)",
    )


# Ajuste vertical opcional
rango_y = None

if ajustar_eje:
    minimo = grafico_filtrado[indicador].min()
    maximo = grafico_filtrado[indicador].max()

    diferencia = maximo - minimo

    if diferencia == 0:
        margen = abs(maximo) * 0.05

        if margen == 0:
            margen = 1
    else:
        margen = diferencia * 0.08

    rango_y = [
        minimo - margen,
        maximo + margen,
    ]


formato_eje_y = ".1%"

if not es_indicador_porcentual(indicador):
    formato_eje_y = ",.2f"


fig.update_layout(
    title=dict(
        text=f"{mercado} · {indicador}",
        font=dict(
            color="#ffffff",
            size=22,
        ),
        x=0.01,
    ),
    height=610,
    paper_bgcolor="#07111f",
    plot_bgcolor="#0b1929",
    font=dict(
        color="#dce4ef",
    ),
    margin=dict(
        l=35,
        r=25,
        t=75,
        b=35,
    ),
    hovermode="x unified",
    showlegend=False,
    dragmode=False,
    xaxis=dict(
        title="",
        showgrid=True,
        gridcolor="rgba(255,255,255,0.07)",
        linecolor="rgba(255,255,255,0.20)",
        tickformat="%m/%Y",
        rangeslider=dict(
            visible=False,
        ),
        fixedrange=True,
    ),
    yaxis=dict(
        title="",
        showgrid=True,
        gridcolor="rgba(255,255,255,0.08)",
        zeroline=False,
        tickformat=formato_eje_y,
        range=rango_y,
        fixedrange=False,
    ),
)


st.plotly_chart(
    fig,
    use_container_width=True,
    config={
        "displayModeBar": False,
        "scrollZoom": False,
        "doubleClick": False,
    },
)


# =========================================================
# TABLA OPCIONAL
# =========================================================

with st.expander("Ver datos históricos"):
    tabla = grafico_filtrado.copy()

    tabla["DATE"] = tabla["DATE"].dt.strftime(
        "%m/%Y"
    )

    tabla = tabla.rename(
        columns={
            "DATE": "Fecha",
        }
    )

    st.dataframe(
        tabla.sort_values(
            "Fecha",
            ascending=False,
        ),
        use_container_width=True,
        hide_index=True,
    )


# =========================================================
# PIE
# =========================================================

st.markdown(
    """
    <div style="
        text-align: center;
        color: #718096;
        font-size: 12px;
        margin-top: 28px;
    ">
        Macro FX · Finans Trading
    </div>
    """,
    unsafe_allow_html=True,
)
