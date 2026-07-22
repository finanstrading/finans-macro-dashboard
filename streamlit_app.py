import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from urllib.parse import quote

from auth import require_authenticated_user, render_logout
from macro_intelligence import analizar_indicador

# ===================================================  
# CONFIGURACIÓN GENERAL
# ===================================================  

st.set_page_config(
    page_title="Finans Trading | Fundamental Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

AUTH_PROFILE = require_authenticated_user()

SHEET_ID = "1dJB_3wWsSOkXm59dEJKYZlkK_wMlp89Pu1GObCNnyQU" 

# Cada divisa se conecta exclusivamente con su pestaña.
# Se incluye una alternativa con espacio para Dashboard_USD,
# porque el archivo original tenía accidentalmente ese espacio.
MERCADOS = {
    "GBP": ["Dashboard_GBP"],
    "USD": ["Dashboard_USD", " Dashboard_USD"],
    "EUR": ["Dashboard_EUR", " Dashboard_EUR"],
    "CAD": ["Dashboard_CAD", " Dashboard_CAD"],
    "JPY": ["Dashboard_JPY", " Dashboard_JPY"],
    "AUD": ["Dashboard_AUD", " Dashboard_AUD"],
    "NZD": ["Dashboard_NZD", " Dashboard_NZD"],
    "CHF": ["Dashboard_CHF", " Dashboard_CHF"],
}

COLOR_DORADO = "#C9A227"
COLOR_DORADO_CLARO = "#E3C85B"
COLOR_NEGRO = "#111111"
COLOR_TEXTO_SECUNDARIO = "#6B7280"
COLOR_FONDO = "#F6F7F9"
COLOR_TARJETA = "#FFFFFF"
COLOR_BORDE = "#E5E7EB"


# ===================================================
# ESTILOS — DISEÑO ORIGINAL CONSERVADO
# ===================================================

st.markdown(
    f"""
    <style>
        html, body, [class*="css"] {{
            font-family: Inter, Arial, sans-serif;
        }}

        .stApp {{
            background: {COLOR_FONDO};
        }}

        .block-container {{
            max-width: 1550px;
            padding-top: 1.6rem;
            padding-bottom: 3rem;
            padding-left: 2.2rem;
            padding-right: 2.2rem;
        }}

        section[data-testid="stSidebar"] {{
            background: {COLOR_NEGRO};
            border-right: 1px solid #252525;
        }}

        section[data-testid="stSidebar"] > div {{
            padding-top: 1.3rem;
        }}

        section[data-testid="stSidebar"] * {{
            color: white;
        }}

        section[data-testid="stSidebar"] label {{
            color: #D1D5DB !important;
            font-size: 0.82rem !important;
            font-weight: 650 !important;
            letter-spacing: 0.02em;
        }}

        section[data-testid="stSidebar"] div[data-baseweb="select"] > div {{
            background-color: white;
            border-color: #E5E7EB;
            color: #111111 !important;
            border-radius: 9px;
        }}

        section[data-testid="stSidebar"] div[data-baseweb="select"] span {{
            color: #111111 !important;
            font-weight: 700 !important;
        }}

        section[data-testid="stSidebar"] div[data-baseweb="select"] input {{
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
        }}

        section[data-testid="stSidebar"] div[data-baseweb="select"] svg {{
            fill: #111111 !important;
            color: #111111 !important;
        }}

        div[role="listbox"] {{
            background: white !important;
        }}

        div[role="option"] {{
            color: #111111 !important;
            background: white !important;
        }}

        div[role="option"] * {{
            color: #111111 !important;
        }}

        div[role="option"]:hover {{
            background: #F3F4F6 !important;
        }}

        section[data-testid="stSidebar"] div[role="radiogroup"] label {{
            background: #1B1B1B;
            border: 1px solid #353535;
            border-radius: 8px;
            padding: 0.35rem 0.55rem;
        }}

        section[data-testid="stSidebar"] hr {{
            border-color: #333333;
            margin-top: 1rem;
            margin-bottom: 1rem;
        }}

        .brand-box {{
            padding: 0.35rem 0 1.2rem 0;
        }}

        .brand-name {{
            color: white;
            font-size: 1.45rem;
            font-weight: 800;
            letter-spacing: 0.03em;
            line-height: 1.1;
        }}

        .brand-accent {{
            color: {COLOR_DORADO};
        }}

        .brand-subtitle {{
            color: #9CA3AF;
            font-size: 0.77rem;
            margin-top: 0.35rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }}

        .dashboard-header {{
            background: linear-gradient(135deg, #111111 0%, #202020 100%);
            border: 1px solid #2C2C2C;
            border-radius: 18px;
            padding: 1.6rem 1.8rem;
            margin-bottom: 1.2rem;
            box-shadow: 0 10px 28px rgba(0, 0, 0, 0.09);
        }}

        .dashboard-eyebrow {{
            color: {COLOR_DORADO_CLARO};
            font-size: 0.74rem;
            font-weight: 750;
            letter-spacing: 0.14em;
            text-transform: uppercase;
            margin-bottom: 0.45rem;
        }}

        .dashboard-title {{
            color: white;
            font-size: 2.05rem;
            line-height: 1.1;
            font-weight: 800;
            margin: 0;
        }}

        .dashboard-subtitle {{
            color: #BFC3CA;
            font-size: 0.95rem;
            margin-top: 0.55rem;
        }}

        .metric-card {{
            background: {COLOR_TARJETA};
            border: 1px solid {COLOR_BORDE};
            border-radius: 14px;
            padding: 1rem 1.1rem;
            min-height: 112px;
            box-shadow: 0 5px 18px rgba(17, 24, 39, 0.045);
        }}

        .metric-label {{
            color: {COLOR_TEXTO_SECUNDARIO};
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }}

        .metric-value {{
            color: {COLOR_NEGRO};
            font-size: 1.75rem;
            font-weight: 800;
            line-height: 1.05;
        }}

        .metric-note {{
            color: {COLOR_TEXTO_SECUNDARIO};
            font-size: 0.8rem;
            margin-top: 0.5rem;
        }}

        .metric-positive {{
            color: #16803B;
            font-weight: 700;
        }}

        .metric-negative {{
            color: #C62828;
            font-weight: 700;
        }}

        .metric-neutral {{
            color: {COLOR_TEXTO_SECUNDARIO};
            font-weight: 700;
        }}

        .chart-card {{
            background: {COLOR_TARJETA};
            border: 1px solid {COLOR_BORDE};
            border-radius: 16px;
            padding: 1.1rem 1.2rem 0.7rem 1.2rem;
            margin-top: 1.2rem;
            box-shadow: 0 5px 18px rgba(17, 24, 39, 0.045);
        }}

        .chart-title {{
            color: {COLOR_NEGRO};
            font-size: 1.08rem;
            font-weight: 800;
            margin-bottom: 0.1rem;
        }}

        .chart-subtitle {{
            color: {COLOR_TEXTO_SECUNDARIO};
            font-size: 0.82rem;
            margin-bottom: 0.5rem;
        }}

        .control-title {{
            color: #D1D5DB;
            font-size: 0.74rem;
            font-weight: 750;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-top: 0.35rem;
            margin-bottom: 0.25rem;
        }}

        .sidebar-info {{
            background: #191919;
            border: 1px solid #303030;
            border-radius: 10px;
            padding: 0.8rem;
            color: #BFC3CA;
            font-size: 0.76rem;
            line-height: 1.45;
            margin-top: 1rem;
        }}

        .sidebar-info strong {{
            color: {COLOR_DORADO_CLARO};
        }}

        div[data-testid="stNumberInput"] input {{
            border-radius: 9px;
        }}

        div[data-testid="stAlert"] {{
            border-radius: 12px;
        }}

        #MainMenu {{
            visibility: hidden;
        }}

        footer {{
            visibility: hidden;
        }}

        header[data-testid="stHeader"] {{
            background: transparent;
        }}

        @media (max-width: 900px) {{
            .block-container {{
                padding-left: 1rem;
                padding-right: 1rem;
                padding-top: 1rem;
            }}

            .dashboard-title {{
                font-size: 1.55rem;
            }}

            .metric-value {{
                font-size: 1.4rem;
            }}
        }}
    </style>
    """,
    unsafe_allow_html=True
)


# ===================================================
# FUNCIONES
# ===================================================

def construir_url(nombre_hoja):
    nombre_codificado = quote(nombre_hoja, safe="")
    return (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?"
        f"tqx=out:csv&sheet={nombre_codificado}"
    )


@st.cache_data(ttl=600, show_spinner=False)
def cargar_datos_mercado(nombres_posibles):
    errores = []

    for nombre_hoja in nombres_posibles:
        try:
            df = pd.read_csv(construir_url(nombre_hoja))
            df.columns = [str(columna).strip() for columna in df.columns]

            # Elimina columnas vacías o creadas accidentalmente.
            columnas_validas = [
                columna
                for columna in df.columns
                if columna
                and not columna.lower().startswith("unnamed")
            ]
            df = df[columnas_validas].dropna(axis=0, how="all")

            if "DATE" not in df.columns:
                raise ValueError("No contiene una columna llamada DATE.")

            return df, nombre_hoja

        except Exception as error:
            errores.append(f"{nombre_hoja}: {error}")

    raise ValueError(
        "No se pudo cargar ninguna pestaña válida. "
        + " | ".join(errores)
    )


def convertir_fechas(serie):
    """
    Admite tanto las fechas originales tipo ene-24 como fechas
    reales procedentes de Google Sheets: 01/01/2024, 2024-01-01, etc.
    Nunca interpreta números aislados como fechas del año 0001.
    """
    meses = {
        "ene": 1, "jan": 1,
        "feb": 2,
        "mar": 3,
        "abr": 4, "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "ago": 8, "aug": 8,
        "sep": 9, "sept": 9,
        "oct": 10,
        "nov": 11,
        "dic": 12, "dec": 12
    }

    texto = serie.astype(str).str.lower().str.strip()

    partes = texto.str.extract(
        r"^([a-záéíóúñ]+)[\-/\s](\d{2,4})$"
    )

    mes = partes[0].map(meses)
    año = pd.to_numeric(partes[1], errors="coerce")
    año = año.where(año >= 100, año + 2000)

    fecha_mes_año = pd.to_datetime(
        {
            "year": año,
            "month": mes,
            "day": 1
        },
        errors="coerce"
    )

    # Excluye números sueltos para evitar años 0001.
    texto_fecha = texto.where(
        ~texto.str.fullmatch(r"\d+([.,]\d+)?")
    )

    fecha_general = pd.to_datetime(
        texto_fecha,
        errors="coerce",
        dayfirst=True
    )

    return fecha_mes_año.fillna(fecha_general)


def convertir_valores(serie):
    texto = (
        serie
        .astype(str)
        .str.strip()
        .str.replace("\u00a0", "", regex=False)   # espacio no separable
        .str.replace(" ", "", regex=False)        # espacios
        .str.replace("−", "-", regex=False)       # signo menos Unicode
        .str.replace("–", "-", regex=False)       # guion largo
        .str.replace("—", "-", regex=False)       # em dash
        .str.replace("'", "", regex=False)        # apóstrofo
        .str.replace("’", "", regex=False)        # apóstrofo tipográfico
        .str.replace("%", "", regex=False)
        .str.replace(",", ".", regex=False)
    )

    texto = texto.replace(
        {
            "": None,
            "nan": None,
            "None": None,
            "-": None,
            "--": None,
        }
    )

    return pd.to_numeric(texto, errors="coerce")


def obtener_indicadores(df):
    columnas_excluidas = {"DATE", "Fecha"}

    return [
        columna
        for columna in df.columns
        if columna not in columnas_excluidas
        and convertir_valores(df[columna]).notna().any()
    ]


def añadir_margen(valor_minimo, valor_maximo):
    if valor_minimo == valor_maximo:
        margen = max(abs(valor_minimo) * 0.10, 1)
    else:
        margen = (valor_maximo - valor_minimo) * 0.10

    return valor_minimo - margen, valor_maximo + margen


def formatear_valor(valor, sufijo):
    return f"{valor:,.2f}{sufijo}"


def crear_tarjeta(titulo, valor, nota="", clase_nota="metric-neutral"):
    return f"""
        <div class="metric-card">
            <div class="metric-label">{titulo}</div>
            <div class="metric-value">{valor}</div>
            <div class="metric-note {clase_nota}">{nota}</div>
        </div>
    """


def determinar_sufijo(nombre_indicador):
    nombre = nombre_indicador.lower()

    palabras_porcentaje = [
        "cpi",
        "inflation",
        "retail sales",
        "unemployment",
        "desempleo",
        "salario",
        "wage",
        "% change",
        "gdp",
        "pce",
        "ppi",
        "earnings"
    ]

    # Los PMI son índices, por tanto no llevan %.
    return "%" if any(
        palabra in nombre
        for palabra in palabras_porcentaje
    ) else ""


# ===================================================
# BARRA LATERAL — MERCADO
# ===================================================

with st.sidebar:
    st.markdown(
        """
        <div class="brand-box">
            <div class="brand-name">
                FINANS <span class="brand-accent">TRADING</span>
            </div>
            <div class="brand-subtitle">
                Macro FX
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    st.markdown(
        '<div class="control-title">Mercado</div>',
        unsafe_allow_html=True
    )

    divisa = st.selectbox(
        "Divisa",
        options=list(MERCADOS.keys()),
        index=0,
        label_visibility="collapsed",
        key="selector_divisa"
    )


# ===================================================
# CARGA Y PREPARACIÓN DE DATOS
# ===================================================

try:
    df, hoja_cargada = cargar_datos_mercado(
        tuple(MERCADOS[divisa])
    )

    df["Fecha"] = convertir_fechas(df["DATE"])

    df = (
        df
        .dropna(subset=["Fecha"])
        .sort_values("Fecha")
        .reset_index(drop=True)
    )

    if df.empty:
        st.error(
            f"No se encontraron fechas válidas en la hoja {hoja_cargada}."
        )
        st.stop()

    indicadores = obtener_indicadores(df)

    if not indicadores:
        st.error(
            f"No se encontraron indicadores con datos en la hoja {hoja_cargada}."
        )
        st.stop()


    # ===================================================
    # RESTO DE CONTROLES
    # ===================================================

    with st.sidebar:
        st.markdown(
            '<div class="control-title">Indicador</div>',
            unsafe_allow_html=True
        )

        indicador = st.selectbox(
            "Indicador",
            indicadores,
            label_visibility="collapsed",
            key=f"indicador_{divisa}"
        )

        st.markdown(
            '<div class="control-title">Periodo</div>',
            unsafe_allow_html=True
        )

        periodo = st.radio(
            "Periodo",
            options=["1A", "3A", "5A", "10A", "Todo"],
            index=1,
            horizontal=False,
            label_visibility="collapsed",
            key=f"periodo_{divisa}_{indicador}"
        )

        st.markdown(
            '<div class="control-title">Escala vertical</div>',
            unsafe_allow_html=True
        )

        modo_escala = st.radio(
            "Escala vertical",
            options=["Automática", "Sin extremos", "Manual"],
            index=0,
            horizontal=False,
            label_visibility="collapsed",
            key=f"escala_{divisa}_{indicador}"
        )

        st.markdown(
            """
            <div class="sidebar-info">
                <strong>Datos:</strong> Google Sheets<br>
                <strong>Actualización:</strong> automática cada 10 minutos
            </div>
            """,
            unsafe_allow_html=True
        )

        render_logout(AUTH_PROFILE)


    # ===================================================
    # CONVERSIÓN DE VALORES
    # ===================================================

    df["Valor"] = convertir_valores(df[indicador])

    datos_completos = (
        df[["Fecha", "Valor"]]
        .dropna()
        .sort_values("Fecha")
        .reset_index(drop=True)
    )

    if datos_completos.empty:
        st.warning("Este indicador todavía no contiene datos disponibles.")
        st.stop()

    analisis = analizar_indicador(
        datos_completos["Fecha"],
        datos_completos["Valor"],
        indicador,
        divisa
    )

    fecha_minima = datos_completos["Fecha"].min()
    fecha_maxima = datos_completos["Fecha"].max()

    ultimo_registro = datos_completos.iloc[-1]
    ultimo_valor = float(ultimo_registro["Valor"])
    ultima_fecha = ultimo_registro["Fecha"]

    if len(datos_completos) >= 2:
        valor_anterior = float(datos_completos.iloc[-2]["Valor"])
        variacion = ultimo_valor - valor_anterior
    else:
        valor_anterior = None
        variacion = None

    sufijo = determinar_sufijo(indicador)

    ultimo_texto = formatear_valor(ultimo_valor, sufijo)

    anterior_texto = (
        formatear_valor(valor_anterior, sufijo)
        if valor_anterior is not None
        else "Sin dato"
    )

    fecha_texto = ultima_fecha.strftime("%m/%Y")
    publicaciones_texto = f"{len(datos_completos):,}"

    if variacion is None:
        variacion_texto = "Sin comparación"
        clase_variacion = "metric-neutral"
        signo_variacion = ""
    elif variacion > 0:
        variacion_texto = (
            f"{variacion:+.2f}{sufijo} frente al dato anterior"
        )
        clase_variacion = "metric-positive"
        signo_variacion = "▲"
    elif variacion < 0:
        variacion_texto = (
            f"{variacion:+.2f}{sufijo} frente al dato anterior"
        )
        clase_variacion = "metric-negative"
        signo_variacion = "▼"
    else:
        variacion_texto = (
            f"{variacion:+.2f}{sufijo} frente al dato anterior"
        )
        clase_variacion = "metric-neutral"
        signo_variacion = "—"


    # ===================================================
    # CABECERA
    # ===================================================

    st.markdown(
        f"""
        <div class="dashboard-header">
            <div class="dashboard-eyebrow">
                Finans Trading · Fundamental Dashboard
            </div>
            <div class="dashboard-title">
                {divisa} · {indicador}
            </div>
            <div class="dashboard-subtitle">
                Evolución histórica y lectura del último dato macroeconómico
                disponible · Actualizado {fecha_texto}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


    # ===================================================
    # TARJETAS DE MÉTRICAS
    # ===================================================

    columna_1, columna_2, columna_3, columna_4 = st.columns(4)

    with columna_1:
        st.markdown(
            crear_tarjeta(
                "Último dato",
                ultimo_texto,
                f"Publicación {fecha_texto}"
            ),
            unsafe_allow_html=True
        )

    with columna_2:
        st.markdown(
            crear_tarjeta(
                "Dato anterior",
                anterior_texto,
                "Registro inmediatamente anterior"
            ),
            unsafe_allow_html=True
        )

    with columna_3:
        st.markdown(
            crear_tarjeta(
                "Variación",
                signo_variacion if signo_variacion else "—",
                variacion_texto,
                clase_variacion
            ),
            unsafe_allow_html=True
        )

    with columna_4:
        st.markdown(
            crear_tarjeta(
                "Publicaciones",
                publicaciones_texto,
                f"Desde {fecha_minima.strftime('%m/%Y')}"
            ),
            unsafe_allow_html=True
        )


    # ===================================================
    # FILTRO TEMPORAL
    # ===================================================

    años_por_periodo = {
        "1A": 1,
        "3A": 3,
        "5A": 5,
        "10A": 10
    }

    if periodo == "Todo":
        fecha_inicio = fecha_minima
    else:
        fecha_inicio = fecha_maxima - pd.DateOffset(
            years=años_por_periodo[periodo]
        )

    datos_visibles = datos_completos[
        (datos_completos["Fecha"] >= fecha_inicio)
        & (datos_completos["Fecha"] <= fecha_maxima)
    ].copy()

    if datos_visibles.empty:
        datos_visibles = datos_completos.copy()


    # ===================================================
    # ESCALA VERTICAL
    # ===================================================

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

        st.info(
            "La escala vertical ignora visualmente el 5 % de los valores "
            "más bajos y el 5 % de los más altos. Los datos no se eliminan."
        )

    else:
        valor_sugerido_minimo, valor_sugerido_maximo = añadir_margen(
            minimo_real,
            maximo_real
        )

        st.markdown("#### Ajuste manual del eje vertical")

        manual_1, manual_2 = st.columns(2)

        with manual_1:
            eje_minimo = st.number_input(
                "Mínimo",
                value=float(round(valor_sugerido_minimo, 2)),
                step=0.5,
                key=f"minimo_{divisa}_{indicador}"
            )

        with manual_2:
            eje_maximo = st.number_input(
                "Máximo",
                value=float(round(valor_sugerido_maximo, 2)),
                step=0.5,
                key=f"maximo_{divisa}_{indicador}"
            )

        if eje_minimo >= eje_maximo:
            st.warning("El máximo debe ser superior al mínimo.")
            st.stop()


    # ===================================================
    # GRÁFICO
    # ===================================================

    st.markdown(
        f"""
        <div class="chart-card">
            <div class="chart-title">
                Evolución histórica de {indicador}
            </div>
            <div class="chart-subtitle">
                Periodo seleccionado: {periodo} ·
                Desde {datos_visibles["Fecha"].min().strftime("%m/%Y")}
                hasta {fecha_maxima.strftime("%m/%Y")}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    figura = go.Figure()

    figura.add_trace(
        go.Scatter(
            x=datos_visibles["Fecha"],
            y=datos_visibles["Valor"],
            mode="lines",
            name=indicador,
            line=dict(
                color=COLOR_DORADO,
                width=3
            ),
            fill="tozeroy",
            fillcolor="rgba(201, 162, 39, 0.08)",
            hovertemplate=(
                "<b>%{x|%b %Y}</b>"
                "<br>"
                + indicador
                + ": <b>%{y:.2f}"
                + sufijo
                + "</b>"
                "<extra></extra>"
            )
        )
    )

    if eje_minimo <= 0 <= eje_maximo:
        figura.add_hline(
            y=0,
            line_width=1,
            line_dash="dot",
            line_color="rgba(107, 114, 128, 0.55)"
        )

    figura.update_layout(
        height=690,
        margin=dict(l=35, r=25, t=20, b=30),
        paper_bgcolor=COLOR_TARJETA,
        plot_bgcolor=COLOR_TARJETA,
        hovermode="x unified",
        showlegend=False,
        xaxis_title="",
        yaxis_title="",
        font=dict(
            family="Inter, Arial, sans-serif",
            size=13,
            color=COLOR_NEGRO
        ),
        dragmode=False,
        hoverlabel=dict(
            bgcolor="#111111",
            font_size=13,
            font_color="white",
            bordercolor="#111111"
        )
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
        showline=True,
        linecolor="#D1D5DB",
        tickformat="%b %Y",
        tickfont=dict(color=COLOR_TEXTO_SECUNDARIO),
        fixedrange=True
    )

    figura.update_yaxes(
        range=[eje_minimo, eje_maximo],
        gridcolor="rgba(107, 114, 128, 0.14)",
        showline=False,
        zeroline=False,
        tickfont=dict(color=COLOR_TEXTO_SECUNDARIO),
        ticksuffix=sufijo,
        fixedrange=True
    )

    st.plotly_chart(
        figura,
        use_container_width=True,
        config={
            "displaylogo": False,
            "scrollZoom": False,
            "displayModeBar": False,
            "responsive": True
        }
    )


except Exception as error:
    st.error("No se pudo cargar el dashboard.")
    st.exception(error)
