import requests
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

# ============================================================
# CONFIGURACIÓN CFTC
# ============================================================

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
    }


# ============================================================
# RENDER STREAMLIT
# ============================================================

def render_cftc_positioning():

    st.markdown(
        """
        <div class="dashboard-header">
            <div class="dashboard-eyebrow">
                MACRO FX · POSITIONING
            </div>
            <div class="dashboard-title">
                CFTC Positioning
            </div>
            <div class="dashboard-subtitle">
                Posicionamiento especulativo de Leveraged Funds
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    currency = st.segmented_control(
        "Divisa",
        options=["JPY"],
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

    col1, col2, col3, col4 = st.columns(4)

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
            "Historical Percentile",
            f"{lectura['percentile']:.1f}%",
        )

    with col6:
        st.metric(
            "Positioning Score",
            f"{lectura['positioning_score']:+.0f}",
        )


    score = lectura["positioning_score"]

    if score >= 70:
        clasificacion = "Extreme Long"
    elif score >= 30:
        clasificacion = "Long"
    elif score > -30:
        clasificacion = "Neutral"
    elif score > -70:
        clasificacion = "Short"
    else:
        clasificacion = "Extreme Short"

    st.markdown(
        f"### Lectura actual: **{clasificacion}**"
    )

    st.caption(
        "Última lectura CFTC: "
        + lectura["date"].strftime("%d/%m/%Y")
    )

    # ============================================================
    # GRÁFICO HISTÓRICO
    # ============================================================

    df_historico = preparar_cftc_currency(currency)

    st.markdown("### Evolución histórica del posicionamiento")

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=df_historico["Fecha"],
            y=df_historico["Net_OI_Pct"],
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
    )

    fig.update_yaxes(
        gridcolor="#EAEAEA",
        zeroline=False,
    )

    st.plotly_chart(
        fig,
        use_container_width=True,
    )
    st.markdown("### Detalle Leveraged Funds")

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
