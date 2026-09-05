import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# ============================================================
# CONFIGURACIÓN CFTC
# ============================================================
CFTC_TFF_URL = (
    "https://publicreporting.cftc.gov/resource/gpe5-46if.json"
)

CFTC_MARKETS = {
    "EUR": {
        "code": "099741",
        "name": "Euro FX",
    },
    "GBP": {
        "code": "096742",
        "name": "British Pound",
    },
    "JPY": {
        "code": "097741",
        "name": "Japanese Yen",
    },
    "CHF": {
        "code": "092741",
        "name": "Swiss Franc",
    },
    "CAD": {
        "code": "090741",
        "name": "Canadian Dollar",
    },
    "AUD": {
        "code": "232741",
        "name": "Australian Dollar",
    },
    "NZD": {
        "code": "112741",
        "name": "New Zealand Dollar",
    },
}

# ============================================================
# DESCARGA DE DATOS
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def cargar_cftc_currency(currency: str) -> pd.DataFrame:

    currency = str(currency).strip().upper()

    if currency not in CFTC_MARKETS:
        raise ValueError(
            f"Divisa CFTC no configurada: {currency}"
        )

    market_code = CFTC_MARKETS[currency]["code"]

    params = {
        "$where": (
            f"cftc_contract_market_code='{market_code}'"
        ),
        "$order": "report_date_as_yyyy_mm_dd DESC",
        "$limit": 1000,
    }

    response = requests.get(
        CFTC_TFF_URL,
        params=params,
        timeout=20,
    )

    response.raise_for_status()

    data = response.json()

    if not data:
        raise ValueError(
            f"No se recibieron datos CFTC para {currency}."
        )

    df = pd.DataFrame(data)

    return df


# ============================================================
# NORMALIZACIÓN
# ============================================================

def preparar_cftc_currency(currency: str) -> pd.DataFrame:

    df = cargar_cftc_currency(currency).copy()

    columnas_requeridas = {
        "report_date_as_yyyy_mm_dd",
        "open_interest_all",
        "lev_money_positions_long",
        "lev_money_positions_short",
    }

    faltantes = columnas_requeridas - set(df.columns)

    if faltantes:
        raise ValueError(
            "Faltan columnas CFTC: "
            + ", ".join(sorted(faltantes))
        )

    df["Fecha"] = pd.to_datetime(
        df["report_date_as_yyyy_mm_dd"],
        errors="coerce",
    )

    columnas_numericas = [
        "open_interest_all",
        "lev_money_positions_long",
        "lev_money_positions_short",
    ]

    for columna in columnas_numericas:
        df[columna] = pd.to_numeric(
            df[columna],
            errors="coerce",
        )

    df = (
        df
        .dropna(
            subset=[
                "Fecha",
                "open_interest_all",
                "lev_money_positions_long",
                "lev_money_positions_short",
            ]
        )
        .sort_values("Fecha")
        .reset_index(drop=True)
    )

    # ========================================================
    # CÁLCULOS
    # ========================================================

    df["Long"] = df["lev_money_positions_long"]

    df["Short"] = df["lev_money_positions_short"]

    df["Net"] = (
        df["Long"]
        - df["Short"]
    )

    df["Net_OI_Pct"] = (
        df["Net"]
        / df["open_interest_all"]
        * 100
    )

    df["Weekly_Change_Net"] = (
        df["Net"].diff()
    )

    df["Weekly_Change_Net_OI"] = (
        df["Net_OI_Pct"].diff()
    )

        # ========================================================
    # HISTÓRICO PARA POSITIONING SCORE
    # ========================================================

    df = df[
        df["Fecha"] >= pd.Timestamp("2010-01-01")
    ].copy()

    # Percentil móvil de 3 años (156 semanas)
    df["Percentile"] = (
        df["Net_OI_Pct"]
        .rolling(window=156, min_periods=52)
        .rank(pct=True)
        * 100
    )

    df["Positioning_Score"] = (
        (df["Percentile"] * 2) - 100
    )

    # ========================================================
    # POSITIONING MOMENTUM
    # ========================================================

    df["Momentum_Percentile"] = (
        df["Weekly_Change_Net_OI"]
        .rolling(window=156, min_periods=52)
        .rank(pct=True)
        * 100
    )

    df["Momentum_Score"] = (
        (df["Momentum_Percentile"] * 2) - 100
    )

    return df


# ============================================================
# ÚLTIMA LECTURA
# ============================================================

def obtener_ultima_lectura(currency: str) -> dict:

    df = preparar_cftc_currency(currency)

    if df.empty:
        raise ValueError(
            f"No existen datos válidos para {currency}."
        )

    ultima = df.iloc[-1]

    return {
        "currency": currency,
        "date": ultima["Fecha"],
        "long": int(ultima["Long"]),
        "short": int(ultima["Short"]),
        "net": int(ultima["Net"]),
        "open_interest": int(
            ultima["open_interest_all"]
        ),
        "net_oi_pct": float(
            ultima["Net_OI_Pct"]
        ),
        "weekly_change_net": float(
            ultima["Weekly_Change_Net"]
        ),
        "weekly_change_net_oi": float(
            ultima["Weekly_Change_Net_OI"]
        ),

        "percentile": float(
            ultima["Percentile"]
        ),
        "positioning_score": float(
            ultima["Positioning_Score"]
        ),

        "momentum_percentile": float(
            ultima["Momentum_Percentile"]
        ),
        "momentum_score": float(
            ultima["Momentum_Score"]
        ),
    }


# ============================================================
# RENDER STREAMLIT
# ============================================================
def generar_analisis_cftc(currency, lectura):

    net = lectura["net"]
    net_oi = lectura["net_oi_pct"]
    weekly_change = lectura["weekly_change_net"]
    weekly_change_oi = lectura["weekly_change_net_oi"]

    percentile = lectura["percentile"]
    positioning = lectura["positioning_score"]
    momentum = lectura["momentum_score"]


    # ========================================================
    # DIRECCIÓN REAL DEL POSICIONAMIENTO
    # ========================================================

    if net_oi >= 5:
        direccion = "long"
    elif net_oi <= -5:
        direccion = "short"
    else:
        direccion = "neutral"


    # ========================================================
    # CROWDING / EXTREMIDAD HISTÓRICA
    # ========================================================

    if abs(positioning) >= 70:
        crowding = "extremo"
    elif abs(positioning) >= 40:
        crowding = "elevado"
    else:
        crowding = "moderado"

    # ========================================================
    # MOMENTUM
    # ========================================================

    if momentum >= 70:
        tendencia = "una fuerte acumulación de posiciones long"
    elif momentum >= 30:
        tendencia = "una acumulación moderada de posiciones long"
    elif momentum > -30:
        tendencia = "un cambio semanal relativamente estable"
    elif momentum > -70:
        tendencia = "una acumulación moderada de posiciones short"
    else:
        tendencia = "una fuerte acumulación de posiciones short"

    # ========================================================
    # DIRECCIÓN DEL CAMBIO
    # ========================================================

    if weekly_change > 0:
        cambio_texto = (
            f"La posición neta mejoró en "
            f"{abs(weekly_change):,.0f} contratos durante la última semana."
        )
    elif weekly_change < 0:
        cambio_texto = (
            f"La posición neta empeoró en "
            f"{abs(weekly_change):,.0f} contratos durante la última semana."
        )
    else:
        cambio_texto = (
            "La posición neta prácticamente no cambió durante la última semana."
        )

    # ========================================================
    # IMPACTO FX
    # ========================================================

    if direccion == "short" and momentum <= -30:
        impacto = (
            f"Los Fondos Apalancados mantienen un posicionamiento claramente "
            f"short en {currency} y, además, están aumentando la presión "
            f"vendedora. El momentum actual refuerza el sesgo bajista. "
            f"Sin embargo, el crowding histórico es {crowding}, por lo que "
            f"el riesgo de short squeeze debe valorarse por separado."
        )

    elif direccion == "short" and momentum > -30:
        impacto = (
            f"Los Fondos Apalancados mantienen un posicionamiento short en "
            f"{currency}, aunque no existe actualmente una acumulación "
            f"agresiva de nuevas posiciones bajistas. El sesgo de "
            f"posicionamiento continúa siendo negativo, pero la presión "
            f"marginal es más limitada."
        )

    elif direccion == "long" and momentum >= 30:
        impacto = (
            f"Los Fondos Apalancados mantienen un posicionamiento claramente "
            f"long en {currency} y continúan aumentando posiciones "
            f"compradoras. El flujo especulativo refuerza el sesgo "
            f"favorable para la divisa."
        )

    elif direccion == "long" and momentum < 30:
        impacto = (
            f"Los Fondos Apalancados continúan posicionados long en {currency}, "
            f"pero el momentum reciente no muestra una acumulación fuerte "
            f"de nuevas posiciones compradoras."
        )

    else:
        impacto = (
            f"El posicionamiento agregado en {currency} se encuentra cerca "
            f"de neutral. En este escenario, el momentum semanal adquiere "
            f"más relevancia para interpretar el flujo reciente."
        )
        
    # ========================================================
    # TEXTOS FINALES
    # ========================================================

    situacion_actual = (
        f"Los Fondos Apalancados mantienen una posición neta de "
        f"{net:,.0f} contratos en {currency}, equivalente al "
        f"{net_oi:.1f}% del Open Interest. Esto refleja un "
        f"posicionamiento claramente {direccion}. "
        f"El Crowding Score de {positioning:+.0f} indica un grado "
        f"de saturación histórica {crowding}, situado en el percentil "
        f"{percentile:.1f} de los últimos tres años."
    )

    tendencia_texto = (
        f"{cambio_texto} El Momentum Score de {momentum:+.0f} indica "
        f"{tendencia}."
    )

    resumen = (
        f"{currency}: posicionamiento {direccion}, "
        f"crowding histórico {crowding} y "
        f"Momentum Score {momentum:+.0f}."
    )

    return {
        "situacion": situacion_actual,
        "tendencia": tendencia_texto,
        "impacto": impacto,
        "resumen": resumen,
    }

# ============================================================
# TARJETAS DE ANÁLISIS CFTC
# ============================================================

def crear_tarjeta_cftc(titulo, contenido):
    return (
        '<div class="macro-analysis-card">'
        f'<div class="macro-analysis-title">{titulo}</div>'
        f'<div class="macro-analysis-text">{contenido}</div>'
        '</div>'
    )

def render_cftc_positioning():

    st.markdown(
        """
        <style>
        /* ==========================================
           CFTC POSITIONING — RESPONSIVE
           ========================================== */

        /* TARJETAS DE MÉTRICAS */
        div[data-testid="stMetric"] {
            background: #FFFFFF !important;
            border: 1px solid #E5E7EB !important;
            border-radius: 12px !important;
            padding: 0.8rem 0.9rem !important;
        }

        /* LABELS DE MÉTRICAS */
        div[data-testid="stMetric"] label,
        div[data-testid="stMetric"] label *,
        div[data-testid="stMetric"] [data-testid="stMetricLabel"],
        div[data-testid="stMetric"] [data-testid="stMetricLabel"] * {
            color: #6B7280 !important;
            -webkit-text-fill-color: #6B7280 !important;
            opacity: 1 !important;
        }

        /* VALORES DE MÉTRICAS */
        div[data-testid="stMetric"] [data-testid="stMetricValue"],
        div[data-testid="stMetric"] [data-testid="stMetricValue"] *,
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
            opacity: 1 !important;
        }

        /* TEXTO NORMAL DE CFTC */
        div[data-testid="stMainBlockContainer"] h3 {
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
            opacity: 1 !important;
        }

        div[data-testid="stMainBlockContainer"]
        div[data-testid="stMarkdownContainer"] p,
        div[data-testid="stMainBlockContainer"]
        div[data-testid="stMarkdownContainer"] strong {
            color: #374151 !important;
            -webkit-text-fill-color: #374151 !important;
            opacity: 1 !important;
        }

        div[data-testid="stMainBlockContainer"]
        div[data-testid="stCaptionContainer"],
        div[data-testid="stMainBlockContainer"]
        div[data-testid="stCaptionContainer"] * {
            color: #6B7280 !important;
            -webkit-text-fill-color: #6B7280 !important;
            opacity: 1 !important;
        }

        /* EXPANDER CFTC — SOLO CONTENIDO PRINCIPAL */
        div[data-testid="stMainBlockContainer"]
        div[data-testid="stExpander"] {
            color: #374151 !important;
        }

        div[data-testid="stMainBlockContainer"]
        div[data-testid="stExpander"] summary,
        div[data-testid="stMainBlockContainer"]
        div[data-testid="stExpander"] summary *,
        div[data-testid="stMainBlockContainer"]
        div[data-testid="stExpander"] details,
        div[data-testid="stMainBlockContainer"]
        div[data-testid="stExpander"] details * {
            color: #374151 !important;
            -webkit-text-fill-color: #374151 !important;
            opacity: 1 !important;
        }

        /* TABLET */
        @media (max-width: 900px) {

            div[data-testid="stMetric"] {
                padding: 0.65rem 0.7rem !important;
                min-height: 88px !important;
            }

            div[data-testid="stMetric"] [data-testid="stMetricValue"] {
                font-size: 1.25rem !important;
            }

            div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
                font-size: 0.70rem !important;
            }

            .dashboard-title {
                font-size: 1.55rem !important;
            }

            .dashboard-subtitle {
                font-size: 0.85rem !important;
            }
        }

        /* MÓVIL */
        @media (max-width: 600px) {

            div[data-testid="stMetric"] {
                min-height: 78px !important;
            }

            div[data-testid="stMetric"] [data-testid="stMetricValue"] {
                font-size: 1.1rem !important;
            }

            div[data-testid="stMetric"] [data-testid="stMetricLabel"] {
                font-size: 0.66rem !important;
            }

            /* Selector de divisas — una sola fila */
            div[data-testid="stSegmentedControl"]:first-of-type {
                overflow-x: auto !important;
                overflow-y: hidden !important;
                white-space: nowrap !important;
                -webkit-overflow-scrolling: touch;
            }

            div[data-testid="stSegmentedControl"]:first-of-type > div {
                flex-wrap: nowrap !important;
                width: max-content !important;
                min-width: max-content !important;
            }

            div[data-testid="stSegmentedControl"]:first-of-type button {
                flex: 0 0 auto !important;
                min-width: 68px !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    

    st.markdown(
        """
        <div class="dashboard-header">
            <div class="dashboard-eyebrow">
                MACRO FX · POSITIONING
            </div>
        <div class="dashboard-title">
            Posicionamiento Apalancado
        </div>
        <div class="dashboard-subtitle">
            Posicionamiento de operadores apalancados · Datos CFTC
        </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    currency = st.segmented_control(
        "Divisa",
        options=[
            "EUR",
            "GBP",
            "JPY",
            "CHF",
            "CAD",
            "AUD",
            "NZD",
        ],
        default="JPY",
        selection_mode="single",
        label_visibility="collapsed",
        key="cftc_currency",
    )

    try:

        lectura = obtener_ultima_lectura(
            currency
        )

    except Exception as error:

        st.error(
            f"No se pudieron cargar los datos CFTC: {error}"
        )

        return

    # ============================================================
    # MÉTRICAS PRINCIPALES
    # ============================================================

    col1, col2, col3, col4 = st.columns(
        4,
        gap="small",
    )
    with col1:
        st.metric(
            "Net Position",
            f"{lectura['net']:,.0f}",
        )

    with col2:
        st.metric(
            "Net / Open Interest",
            f"{lectura['net_oi_pct']:.1f}%",
        )

    with col3:
        st.metric(
            "Weekly Change",
            f"{lectura['weekly_change_net']:,.0f}",
        )

    with col4:
        st.metric(
            "Open Interest",
            f"{lectura['open_interest']:,.0f}",
        )


    # ============================================================
    # LECTURA DE POSICIONAMIENTO
    # ============================================================

    col5, col6 = st.columns(2)

    with col5:
        st.metric(
            "3Y Crowding Percentile",
            f"{lectura['percentile']:.1f}%",
        )

    with col6:
        st.metric(
            "Crowding Score",
            f"{lectura['positioning_score']:+.0f}",
        )


    net_oi = lectura["net_oi_pct"]
    score = lectura["positioning_score"]

    # ============================================================
    # DIRECCIÓN ACTUAL
    # ============================================================

    if net_oi >= 5:
        direccion = "Long"
    elif net_oi <= -5:
        direccion = "Short"
    else:
        direccion = "Neutral"


    # ============================================================
    # CROWDING / EXTREMIDAD HISTÓRICA
    # ============================================================

    if abs(score) >= 70:
        crowding = "Extreme"
    elif abs(score) >= 40:
        crowding = "Elevated"
    else:
        crowding = "Moderate"


    momentum = lectura["momentum_score"]

    if momentum >= 70:
        momentum_label = "Strong Long Build"
    elif momentum >= 30:
        momentum_label = "Long Build"
    elif momentum > -30:
        momentum_label = "Stable"
    elif momentum > -70:
        momentum_label = "Short Build"
    else:
        momentum_label = "Strong Short Build"

    st.markdown(
        f"### Posicionamiento actual: **{direccion}**"
    )

    st.markdown(
        f"**Crowding histórico:** {crowding} "
        f"({score:+.0f})"
    )
    st.markdown(
        f"**Momentum semanal:** {momentum_label} "
        f"({momentum:+.0f})"
    )

    st.caption(
        "Última lectura CFTC: "
        + lectura["date"].strftime("%d/%m/%Y")
    )

    # ============================================================
    # GUÍA DE INTERPRETACIÓN
    # ============================================================

    with st.expander("¿Cómo interpretar estos datos?"):

        st.markdown(
            """
    **Net Position**  
    Diferencia entre las posiciones **Long y Short** de los Fondos Apalancados.  
    Un valor positivo indica posicionamiento neto comprador; un valor negativo, posicionamiento neto vendedor.

    **Net / Open Interest**  
    Posición neta de los Fondos Apalancados en relación con el tamaño total del mercado de futuros.  
    Permite medir mejor la **dirección y magnitud relativa** del posicionamiento que el número de contratos por sí solo.

    **Weekly Change**  
    Cambio de la posición neta respecto a la semana anterior.  
    Un valor positivo indica movimiento hacia posiciones más **Long**; uno negativo, hacia posiciones más **Short**.

    **Open Interest**  
    Número total de contratos de futuros abiertos en ese mercado.  
    Sirve como referencia del tamaño y participación existente en el mercado.

    **3Y Crowding Percentile**  
    Compara el posicionamiento actual con las lecturas de los últimos **3 años**.  
    Ayuda a saber si el posicionamiento se encuentra cerca de niveles históricamente elevados o extremos.

    **Crowding Score · −100 a +100**  
    Mide dónde se encuentra el posicionamiento dentro de su distribución histórica.  
    Valores próximos a **−100** representan extremos hacia el lado Short y valores próximos a **+100**, extremos hacia el lado Long.

    **Momentum semanal · −100 a +100**  
    Mide la intensidad del cambio reciente del posicionamiento.  
    Valores próximos a **−100** indican fuerte construcción de posiciones Short; valores próximos a **+100**, fuerte construcción de posiciones Long.
            """
        )

    # ============================================================
    # GRÁFICO HISTÓRICO
    # ============================================================
    periodo_grafico = st.segmented_control(
        "Periodo histórico",
        options=[
            "1A",
            "3A",
            "5A",
            "Todo",
        ],
        default="3A",
        selection_mode="single",
        key=f"cftc_period_{currency}",
    )

    tipo_grafico = st.segmented_control(
        "Tipo de gráfico",
        options=[
            "Línea",
            "Barras",
        ],
        default="Línea",
        selection_mode="single",
        key=f"cftc_chart_type_{currency}",
    )


    df_historico = preparar_cftc_currency(currency).copy()

    fecha_maxima = df_historico["Fecha"].max()

    if periodo_grafico == "1A":
        fecha_inicio = fecha_maxima - pd.DateOffset(years=1)

    elif periodo_grafico == "3A":
        fecha_inicio = fecha_maxima - pd.DateOffset(years=3)

    elif periodo_grafico == "5A":
        fecha_inicio = fecha_maxima - pd.DateOffset(years=5)

    else:
        fecha_inicio = df_historico["Fecha"].min()


    df_grafico = df_historico[
        df_historico["Fecha"] >= fecha_inicio
    ].copy()

    st.markdown("### Evolución histórica del posicionamiento")

    fig = go.Figure()

    if tipo_grafico == "Línea":

        fig.add_trace(
            go.Scatter(
                x=df_grafico["Fecha"],
                y=df_grafico["Net_OI_Pct"],
                mode="lines",
                name="Net / Open Interest",
                line=dict(
                    color="#D4A017",
                    width=2,
                ),
                hovertemplate=(
                    "%{x|%d/%m/%Y}<br>"
                    "Net / OI: %{y:.2f}%"
                    "<extra></extra>"
                ),
            )
        )

    else:

        fig.add_trace(
            go.Bar(
                x=df_grafico["Fecha"],
                y=df_grafico["Net_OI_Pct"],
                name="Net / Open Interest",
                marker_color="#D4A017",
                hovertemplate=(
                    "%{x|%d/%m/%Y}<br>"
                    "Net / OI: %{y:.2f}%"
                    "<extra></extra>"
                ),
            )
        )

    fig.add_hline(
        y=0,
        line_width=1,
        line_dash="dash",
        line_color="#888888",
    )

    fig.update_layout(
        height=430,
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
        showlegend=False,
        xaxis_title=None,
        yaxis_title="Net / Open Interest (%)",
        hovermode="x unified",
    )

    fig.update_xaxes(
        showgrid=False,
        fixedrange=True,
        tickfont=dict(
            color="#4B5563",
            size=12,
        ),
    )

    fig.update_yaxes(
        gridcolor="#D1D5DB",
        zeroline=False,
        fixedrange=True,
        tickfont=dict(
            color="#4B5563",
            size=12,
        ),
        title_font=dict(
            color="#4B5563",
            size=13,
        ),
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
        config={
            "displayModeBar": True,
            "displaylogo": False,
            "modeBarButtons": [
                ["toImage"]
            ],
            "scrollZoom": False,
            "doubleClick": False,
        },
    )

    analisis = generar_analisis_cftc(
        currency,
        lectura,
    )

    st.markdown("### Positioning Analysis")

    fila_1_col_1, fila_1_col_2 = st.columns(2)

    with fila_1_col_1:
        st.markdown(
            crear_tarjeta_cftc(
                "Situación actual",
                analisis["situacion"],
            ),
            unsafe_allow_html=True,
        )

    with fila_1_col_2:
        st.markdown(
            crear_tarjeta_cftc(
                "Tendencia",
                analisis["tendencia"],
            ),
            unsafe_allow_html=True,
        )


    fila_2_col_1, fila_2_col_2 = st.columns(2)

    with fila_2_col_1:
        st.markdown(
            crear_tarjeta_cftc(
                "Impacto sobre la divisa",
                analisis["impacto"],
            ),
            unsafe_allow_html=True,
        )

    with fila_2_col_2:
        st.markdown(
            crear_tarjeta_cftc(
                "Resumen",
                analisis["resumen"],
            ),
            unsafe_allow_html=True,
        )

    st.markdown("### Detalle del Posicionamiento Apalancado")

    detalle = pd.DataFrame(
        {
            "Métrica": [
                "Long",
                "Short",
                "Net",
                "Net / Open Interest",
                "Cambio semanal Net",
            ],
            "Valor": [
                f"{lectura['long']:,.0f}",
                f"{lectura['short']:,.0f}",
                f"{lectura['net']:,.0f}",
                f"{lectura['net_oi_pct']:.2f}%",
                f"{lectura['weekly_change_net']:,.0f}",
            ],
        }
    )

    st.dataframe(
        detalle,
        use_container_width=True,
        hide_index=True,
    )
