import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from urllib.parse import quote


# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

st.set_page_config(
    page_title="Macro FX",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)


SHEET_ID = "1dJB_3wWsSOkXm59dEJKYZlkK_wMlp89Pu1GObCNnyQU"


# Se incluyen varias posibilidades por si alguna pestaña
# tiene accidentalmente un espacio delante o detrás.
MERCADOS = {
    "GBP": [
        "Dashboard_GBP",
        " Dashboard_GBP",
        "Dashboard_GBP ",
    ],
    "USD": [
        "Dashboard_USD",
        " Dashboard_USD",
        "Dashboard_USD ",
    ],
}


# ============================================================
# ESTILOS Y DISEÑO
# ============================================================

st.markdown(
    """
    <style>
    :root {
        --macro-bg: #071321;
        --macro-panel: #0d1d2d;
        --macro-panel-2: #112438;
        --macro-gold: #c7a55b;
        --macro-gold-light: #e4cc92;
        --macro-white: #f7f9fc;
        --macro-muted: #aebbd0;
        --macro-border: rgba(199, 165, 91, 0.32);
    }

    html,
    body,
    [class*="css"] {
        font-family: Arial, Helvetica, sans-serif;
    }

    .stApp {
        background:
            radial-gradient(
                circle at top right,
                rgba(31, 66, 99, 0.16),
                transparent 35%
            ),
            #071321;
    }

    .block-container {
        max-width: 1280px;
        padding-top: 2.2rem;
        padding-bottom: 3rem;
    }

    #MainMenu {
        visibility: hidden;
    }

    footer {
        visibility: hidden;
    }

    header[data-testid="stHeader"] {
        background: transparent;
    }

    div[data-testid="stToolbar"] {
        visibility: hidden;
        height: 0%;
        position: fixed;
    }

    h1,
    h2,
    h3,
    h4 {
        color: var(--macro-white);
    }

    p,
    label,
    span {
        color: var(--macro-muted);
    }

    /* Etiquetas de los controles */
    div[data-testid="stWidgetLabel"] p {
        color: #dbe4ef !important;
        font-weight: 600 !important;
        font-size: 0.88rem !important;
    }

    /* Selectores cerrados */
    div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        border: 1px solid #d5b66e !important;
        border-radius: 8px !important;
        min-height: 42px !important;
        box-shadow: none !important;
    }

    div[data-baseweb="select"] span,
    div[data-baseweb="select"] input {
        color: #111111 !important;
        -webkit-text-fill-color: #111111 !important;
        font-weight: 500 !important;
    }

    div[data-baseweb="select"] svg {
        fill: #111111 !important;
        color: #111111 !important;
    }

    /* Menú desplegable */
    ul[role="listbox"] {
        background-color: #ffffff !important;
        border: 1px solid #d5b66e !important;
    }

    li[role="option"] {
        background-color: #ffffff !important;
        color: #111111 !important;
    }

    li[role="option"] span {
        color: #111111 !important;
        -webkit-text-fill-color: #111111 !important;
    }

    li[role="option"]:hover,
    li[role="option"][aria-selected="true"] {
        background-color: #f2e6ca !important;
        color: #111111 !important;
    }

    /* Campos de fecha */
    div[data-baseweb="input"] {
        background-color: #ffffff !important;
        border-radius: 8px !important;
    }

    div[data-baseweb="input"] input {
        background-color: #ffffff !important;
        color: #111111 !important;
        -webkit-text-fill-color: #111111 !important;
    }

    div[data-baseweb="input"] svg {
        fill: #111111 !important;
        color: #111111 !important;
    }

    /* Métricas */
    div[data-testid="stMetric"] {
        background:
            linear-gradient(
                145deg,
                rgba(17, 36, 56, 0.98),
                rgba(10, 25, 40, 0.98)
            );
        border: 1px solid var(--macro-border);
        border-radius: 12px;
        padding: 18px 20px;
        min-height: 112px;
    }

    div[data-testid="stMetricLabel"] p {
        color: var(--macro-muted) !important;
        font-weight: 600 !important;
    }

    div[data-testid="stMetricValue"] {
        color: var(--macro-white) !important;
    }

    div[data-testid="stMetricDelta"] {
        color: var(--macro-gold-light) !important;
    }

    /* Checkbox */
    div[data-testid="stCheckbox"] label p {
        color: #dbe4ef !important;
    }

    /* Expander */
    details {
        background-color: rgba(13, 29, 45, 0.85) !important;
        border: 1px solid var(--macro-border) !important;
        border-radius: 10px !important;
    }

    details summary p {
        color: #ffffff !important;
        font-weight: 600 !important;
    }

    /* Alertas */
    div[data-testid="stAlert"] {
        border-radius: 10px;
    }

    hr {
        border-color: rgba(199, 165, 91, 0.24);
        margin-top: 1.2rem;
        margin-bottom: 1.2rem;
    }

    /* Tabla */
    div[data-testid="stDataFrame"] {
        border: 1px solid rgba(199, 165, 91, 0.22);
        border-radius: 9px;
        overflow: hidden;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# ENCABEZADO
# ============================================================

st.markdown(
    """
    <div style="
        width:100%;
        box-sizing:border-box;
        padding:24px 28px;
        margin-bottom:24px;
        border:1px solid rgba(199,165,91,0.42);
        border-radius:14px;
        background:linear-gradient(
            135deg,
            rgba(16,36,56,0.98),
            rgba(7,19,33,0.98)
        );
        box-shadow:0 12px 30px rgba(0,0,0,0.16);
    ">
        <div style="
            margin:0 0 5px 0;
            color:#c7a55b;
            font-size:13px;
            line-height:1.2;
            font-weight:800;
            letter-spacing:2.2px;
        ">
            FINANS TRADING
        </div>
        <div style="
            margin:0;
            color:#ffffff;
            font-size:36px;
            line-height:1.15;
            font-weight:800;
        ">
            Macro FX
        </div>
        <div style="
            margin-top:7px;
            color:#aebbd0;
            font-size:16px;
            line-height:1.5;
        ">
            Evolución histórica de los principales indicadores macroeconómicos
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# FUNCIONES DE CARGA
# ============================================================

def construir_url(nombre_hoja: str) -> str:
    hoja_codificada = quote(
        nombre_hoja,
        safe="",
    )

    return (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq"
        f"?tqx=out:csv&sheet={hoja_codificada}"
    )


def limpiar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df.columns = [
        str(columna).strip()
        if str(columna).strip().lower() != "nan"
        else ""
        for columna in df.columns
    ]

    columnas_validas = [
        columna
        for columna in df.columns
        if columna
        and not columna.lower().startswith("unnamed")
    ]

    df = df[columnas_validas]

    df = df.dropna(
        axis=0,
        how="all",
    )

    df = df.dropna(
        axis=1,
        how="all",
    )

    return df


def convertir_a_numero(serie: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(serie):
        return pd.to_numeric(
            serie,
            errors="coerce",
        )

    texto = serie.astype(str).str.strip()

    texto = texto.replace(
        {
            "": None,
            "nan": None,
            "None": None,
            "-": None,
            "—": None,
        }
    )

    texto = (
        texto
        .str.replace("%", "", regex=False)
        .str.replace("\u00a0", "", regex=False)
        .str.replace(" ", "", regex=False)
    )

    tiene_coma = texto.str.contains(
        ",",
        regex=False,
        na=False,
    )

    tiene_punto = texto.str.contains(
        ".",
        regex=False,
        na=False,
    )

    ambos_separadores = tiene_coma & tiene_punto

    texto.loc[ambos_separadores] = (
        texto.loc[ambos_separadores]
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )

    solo_coma = tiene_coma & ~tiene_punto

    texto.loc[solo_coma] = (
        texto.loc[solo_coma]
        .str.replace(",", ".", regex=False)
    )

    return pd.to_numeric(
        texto,
        errors="coerce",
    )


def detectar_indicadores(df: pd.DataFrame) -> list[str]:
    indicadores = []

    for columna in df.columns:
        if columna == "DATE":
            continue

        valores = convertir_a_numero(
            df[columna]
        )

        if valores.notna().any():
            indicadores.append(columna)

    return indicadores


@st.cache_data(
    ttl=300,
    show_spinner=False,
)
def cargar_mercado(
    nombres_posibles: tuple[str, ...],
) -> tuple[pd.DataFrame, str]:
    errores = []

    for nombre_hoja in nombres_posibles:
        try:
            url = construir_url(nombre_hoja)

            df = pd.read_csv(url)

            df = limpiar_columnas(df)

            if df.empty or len(df.columns) < 2:
                raise ValueError(
                    "La pestaña no contiene una tabla válida."
                )

            primera_columna = df.columns[0]

            df = df.rename(
                columns={
                    primera_columna: "DATE",
                }
            )

            df["DATE"] = pd.to_datetime(
                df["DATE"],
                errors="coerce",
            )

            df = df.dropna(
                subset=["DATE"],
            )

            if df.empty:
                raise ValueError(
                    "No se detectaron fechas válidas."
                )

            indicadores = detectar_indicadores(df)

            if not indicadores:
                raise ValueError(
                    "No se detectaron columnas numéricas."
                )

            df = df.sort_values(
                "DATE",
            )

            df = df.drop_duplicates(
                subset=["DATE"],
                keep="last",
            )

            return df, nombre_hoja

        except Exception as error:
            errores.append(
                f"{repr(nombre_hoja)}: {error}"
            )

    detalle = "\n".join(errores)

    raise ValueError(
        "No se pudo encontrar una pestaña válida.\n"
        + detalle
    )


# ============================================================
# FUNCIONES DE FORMATO
# ============================================================

def es_porcentual(
    nombre: str,
    serie_original: pd.Series,
) -> bool:
    nombre_normalizado = nombre.lower()

    contiene_signo_porcentaje = (
        serie_original
        .astype(str)
        .str.contains(
            "%",
            regex=False,
            na=False,
        )
        .any()
    )

    if contiene_signo_porcentaje:
        return True

    palabras_porcentuales = [
        "cpi",
        "ppi",
        "pce",
        "inflation",
        "inflación",
        "inflacion",
        "%desempleo",
        "% salario",
        "unemployment",
        "earnings",
        "wage",
        "retail sales",
        "ventas minoristas",
        "interest rate",
        "bank rate",
        "tipo de interés",
        "tipo de interes",
        "gdp",
        "pib",
    ]

    return any(
        palabra in nombre_normalizado
        for palabra in palabras_porcentuales
    )


def formatear_valor(
    valor: float,
    porcentual: bool,
) -> str:
    if pd.isna(valor):
        return "Sin dato"

    if porcentual:
        return f"{valor:.2%}"

    if abs(valor) >= 1_000_000:
        return f"{valor / 1_000_000:,.2f} M"

    if abs(valor) >= 1_000:
        return f"{valor:,.0f}"

    return f"{valor:,.2f}"


def formatear_variacion(
    variacion: float,
    porcentual: bool,
) -> str:
    if pd.isna(variacion):
        return "Sin dato"

    if porcentual:
        return f"{variacion * 100:+.2f} puntos"

    if abs(variacion) >= 1_000:
        return f"{variacion:+,.0f}"

    return f"{variacion:+,.2f}"


def calcular_rango_vertical(
    serie: pd.Series,
) -> list[float] | None:
    minimo = serie.min()
    maximo = serie.max()

    if pd.isna(minimo) or pd.isna(maximo):
        return None

    diferencia = maximo - minimo

    if diferencia == 0:
        margen = abs(maximo) * 0.08

        if margen == 0:
            margen = 1
    else:
        margen = diferencia * 0.08

    return [
        minimo - margen,
        maximo + margen,
    ]


# ============================================================
# SELECTORES DE MERCADO E INDICADOR
# ============================================================

col_mercado, col_indicador = st.columns(
    [1, 2.2],
    gap="large",
)

with col_mercado:
    mercado = st.selectbox(
        "Mercado",
        options=list(MERCADOS.keys()),
        index=0,
        key="mercado",
    )


try:
    datos, hoja_detectada = cargar_mercado(
        tuple(MERCADOS[mercado])
    )

except Exception as error:
    st.error(
        f"No se pudieron cargar los datos de {mercado}."
    )

    st.info(
        "Comprueba que la pestaña exista en el mismo Google Sheets "
        "y que el documento pueda consultarse mediante el enlace."
    )

    st.code(
        str(error)
    )

    st.stop()


indicadores = detectar_indicadores(
    datos
)


with col_indicador:
    indicador = st.selectbox(
        "Indicador",
        options=indicadores,
        index=0,
        key=f"indicador_{mercado}",
    )


# ============================================================
# PREPARACIÓN DE LOS DATOS
# ============================================================

serie_original = datos[indicador].copy()

indicador_porcentual = es_porcentual(
    indicador,
    serie_original,
)

grafico = datos[
    [
        "DATE",
        indicador,
    ]
].copy()

grafico[indicador] = convertir_a_numero(
    grafico[indicador]
)

grafico = grafico.dropna(
    subset=[indicador]
)

grafico = grafico.sort_values(
    "DATE"
)


if grafico.empty:
    st.warning(
        f"El indicador «{indicador}» no contiene datos válidos."
    )

    st.stop()


# ============================================================
# SELECCIÓN DEL PERIODO
# ============================================================

fecha_minima = grafico["DATE"].min().date()
fecha_maxima = grafico["DATE"].max().date()

st.markdown("---")


col_periodo, col_desde, col_hasta = st.columns(
    [1.25, 1, 1],
    gap="large",
)


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
        key=f"periodo_{mercado}_{indicador}",
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


if periodo == "Personalizado":
    with col_desde:
        fecha_inicio = st.date_input(
            "Desde",
            value=fecha_minima,
            min_value=fecha_minima,
            max_value=fecha_maxima,
            format="DD/MM/YYYY",
            key=f"desde_{mercado}_{indicador}",
        )

    with col_hasta:
        fecha_fin = st.date_input(
            "Hasta",
            value=fecha_maxima,
            min_value=fecha_minima,
            max_value=fecha_maxima,
            format="DD/MM/YYYY",
            key=f"hasta_{mercado}_{indicador}",
        )

else:
    fecha_fin = fecha_maxima

    with col_desde:
        st.date_input(
            "Desde",
            value=fecha_inicio,
            min_value=fecha_minima,
            max_value=fecha_maxima,
            format="DD/MM/YYYY",
            disabled=True,
            key=f"desde_fijo_{mercado}_{indicador}_{periodo}",
        )

    with col_hasta:
        st.date_input(
            "Hasta",
            value=fecha_fin,
            min_value=fecha_minima,
            max_value=fecha_maxima,
            format="DD/MM/YYYY",
            disabled=True,
            key=f"hasta_fijo_{mercado}_{indicador}_{periodo}",
        )


if fecha_inicio > fecha_fin:
    st.error(
        "La fecha inicial no puede ser posterior a la fecha final."
    )

    st.stop()


grafico_filtrado = grafico[
    (
        grafico["DATE"].dt.date >= fecha_inicio
    )
    &
    (
        grafico["DATE"].dt.date <= fecha_fin
    )
].copy()


if grafico_filtrado.empty:
    st.warning(
        "No existen datos para el periodo seleccionado."
    )

    st.stop()


# ============================================================
# CONTROLES DEL GRÁFICO
# ============================================================

col_comprimir, col_cero, col_espacio = st.columns(
    [1.35, 1.25, 3],
)

with col_comprimir:
    comprimir_eje = st.checkbox(
        "Comprimir eje vertical",
        value=False,
        key=f"comprimir_{mercado}_{indicador}",
        help=(
            "Reduce el espacio vertical vacío para apreciar "
            "mejor las variaciones pequeñas."
        ),
    )

with col_cero:
    mostrar_cero = st.checkbox(
        "Mostrar línea de cero",
        value=True,
        key=f"cero_{mercado}_{indicador}",
    )


# ============================================================
# MÉTRICAS
# ============================================================

primer_registro = grafico_filtrado.iloc[0]
ultimo_registro = grafico_filtrado.iloc[-1]

primer_valor = primer_registro[indicador]
ultimo_valor = ultimo_registro[indicador]

variacion = ultimo_valor - primer_valor


col_metrica_1, col_metrica_2, col_metrica_3 = st.columns(
    3,
    gap="large",
)


with col_metrica_1:
    st.metric(
        "Último dato",
        formatear_valor(
            ultimo_valor,
            indicador_porcentual,
        ),
    )


with col_metrica_2:
    st.metric(
        "Última publicación",
        ultimo_registro["DATE"].strftime(
            "%m/%Y"
        ),
    )


with col_metrica_3:
    st.metric(
        "Cambio en el periodo",
        formatear_variacion(
            variacion,
            indicador_porcentual,
        ),
    )


# ============================================================
# GRÁFICO
# ============================================================

fig = go.Figure()


if indicador_porcentual:
    texto_hover = "%{y:.2%}"
    formato_eje_y = ".1%"

else:
    texto_hover = "%{y:,.2f}"
    formato_eje_y = ",.2f"


fig.add_trace(
    go.Scatter(
        x=grafico_filtrado["DATE"],
        y=grafico_filtrado[indicador],
        mode="lines+markers",
        name=indicador,
        line=dict(
            color="#c7a55b",
            width=2.7,
        ),
        marker=dict(
            color="#e4cc92",
            size=5.5,
            line=dict(
                color="#c7a55b",
                width=1,
            ),
        ),
        hovertemplate=(
            "<b>%{x|%m/%Y}</b><br>"
            + indicador
            + ": "
            + texto_hover
            + "<extra></extra>"
        ),
    )
)


if mostrar_cero:
    fig.add_hline(
        y=0,
        line_width=1,
        line_dash="dot",
        line_color="rgba(255,255,255,0.30)",
    )


rango_vertical = None

if comprimir_eje:
    rango_vertical = calcular_rango_vertical(
        grafico_filtrado[indicador]
    )


fig.update_layout(
    title=dict(
        text=f"{mercado} · {indicador}",
        x=0.015,
        xanchor="left",
        font=dict(
            size=22,
            color="#ffffff",
        ),
    ),
    height=610,
    paper_bgcolor="#071321",
    plot_bgcolor="#0b1b2b",
    font=dict(
        color="#dce4ef",
        family="Arial, Helvetica, sans-serif",
    ),
    margin=dict(
        l=42,
        r=25,
        t=75,
        b=42,
    ),
    hovermode="x unified",
    showlegend=False,
    dragmode=False,
    xaxis=dict(
        title="",
        showgrid=True,
        gridcolor="rgba(255,255,255,0.065)",
        linecolor="rgba(255,255,255,0.18)",
        tickformat="%m/%Y",
        fixedrange=True,
        rangeslider=dict(
            visible=False,
        ),
    ),
    yaxis=dict(
        title="",
        showgrid=True,
        gridcolor="rgba(255,255,255,0.075)",
        linecolor="rgba(255,255,255,0.18)",
        zeroline=False,
        tickformat=formato_eje_y,
        range=rango_vertical,
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
        "responsive": True,
    },
)


# ============================================================
# TABLA HISTÓRICA
# ============================================================

with st.expander(
    "Ver datos históricos",
):
    tabla = grafico_filtrado.copy()

    tabla = tabla.sort_values(
        "DATE",
        ascending=False,
    )

    tabla["DATE"] = tabla["DATE"].dt.strftime(
        "%m/%Y"
    )

    tabla = tabla.rename(
        columns={
            "DATE": "Fecha",
        }
    )

    if indicador_porcentual:
        tabla[indicador] = tabla[indicador].map(
            lambda valor: f"{valor:.2%}"
            if pd.notna(valor)
            else ""
        )

    st.dataframe(
        tabla,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# PIE DE PÁGINA
# ============================================================

st.markdown(
    """
    <div style="
        margin-top:28px;
        padding-top:16px;
        border-top:1px solid rgba(199,165,91,0.18);
        text-align:center;
        color:#718096;
        font-size:12px;
    ">
        Macro FX · Finans Trading
    </div>
    """,
    unsafe_allow_html=True,
)
