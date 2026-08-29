import streamlit as st
import pandas as pd
import time
import hashlib
import requests
import plotly.graph_objects as go
from urllib.parse import quote  

from auth import require_authenticated_user, render_logout
from monetary_engine import analizar_indicador, ENGINE_VERSION

from currency_score_engine import (
    calcular_currency_score,
    clasificar_currency_score,
)

from cftc_positioning import render_cftc_positioning

import feedparser
from datetime import datetime, timezone, timedelta

from openai import OpenAI
import json
import html

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

RELEASE_AWARE_CURRENCIES = {
    "USD",
    "GBP",
    "EUR",
    "CAD",
    "JPY",
    "AUD",
    "NZD",
    "CHF",
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

        section[data-testid="stSidebar"] {{
            color: white;
        }}

        section[data-testid="stSidebar"] label,
        section[data-testid="stSidebar"] p,
        section[data-testid="stSidebar"] span {{
            color: white;
        }}

        section[data-testid="stSidebar"] div[data-baseweb="select"],
        section[data-testid="stSidebar"] div[data-baseweb="select"] *,
        section[data-testid="stSidebar"] div[role="combobox"],
        section[data-testid="stSidebar"] div[role="combobox"] *,
        section[data-testid="stSidebar"] input[aria-label="Divisa"],
        section[data-testid="stSidebar"] input[aria-label="Indicador"] {{
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
            opacity: 1 !important;
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

        section[data-testid="stSidebar"] div[data-baseweb="select"] * {{
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
        }}

        section[data-testid="stSidebar"] div[data-baseweb="select"] div {{
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
        }}

        section[data-testid="stSidebar"] div[data-baseweb="select"] input {{
            color: #111111 !important;
            -webkit-text-fill-color: #111111 !important;
        }}

        section[data-testid="stSidebar"] div[data-baseweb="select"] svg {{
            fill: #111111 !important;
            color: #111111 !important;
        }}
        
        section[data-testid="stSidebar"] div[data-baseweb="select"] div[data-testid="stMarkdownContainer"] {{
            color: #111111 !important;
        }}

        section[data-testid="stSidebar"] div[data-baseweb="select"] div[data-testid="stMarkdownContainer"] p {{
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

        .score-detail-grid {{
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.75rem;
            margin: 0.35rem 0 1rem 0;
        }}

        .score-detail-card {{
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 12px;
            padding: 0.85rem 0.95rem;
        }}

        .score-detail-label {{
            color: #6B7280;
            font-size: 0.7rem;
            font-weight: 750;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }}

        .score-detail-value {{
            color: #111111;
            font-size: 1.05rem;
            font-weight: 800;
        }}

        .score-component {{
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-radius: 12px;
            padding: 0.8rem 0.95rem;
            margin-bottom: 0.65rem;
        }}

        .score-component-header {{
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            gap: 1rem;
            margin-bottom: 0.45rem;
        }}

        .score-component-name {{
            color: #111111;
            font-size: 0.88rem;
            font-weight: 750;
        }}

        .score-component-meta {{
            color: #6B7280;
            font-size: 0.76rem;
            white-space: nowrap;
        }}

        .score-bar-track {{
            width: 100%;
            height: 8px;
            background: #ECEFF3;
            border-radius: 999px;
            overflow: hidden;
        }}

        .score-bar-fill {{
            height: 100%;
            background: linear-gradient(90deg, #C9A227 0%, #E3C85B 100%);
            border-radius: 999px;
        }}

        .score-formula-note {{
            color: #6B7280;
            font-size: 0.76rem;
            line-height: 1.5;
            margin-top: 0.85rem;
        }}

        @media (max-width: 900px) {{
            .score-detail-grid {{
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
        }}

        .macro-analysis-card {{
            background: #FFFFFF;
            border: 1px solid #E5E7EB;
            border-top: 3px solid #C9A227;
            border-radius: 14px;
            padding: 1.05rem 1.15rem;
            min-height: 145px;
            box-shadow: 0 5px 18px rgba(17, 24, 39, 0.045);
        }}

        .macro-analysis-title {{
            color: #111111;
            font-size: 0.76rem;
            font-weight: 800;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 0.65rem;
        }}

        .macro-analysis-text {{
            color: #4B5563;
            font-size: 0.86rem;
            line-height: 1.65;
        }}

        .macro-summary-box {{
            background: linear-gradient(135deg, #111111 0%, #202020 100%);
            border: 1px solid #2C2C2C;
            border-radius: 14px;
            padding: 1.05rem 1.2rem;
            margin-top: 0.35rem;
        }}

        .macro-summary-label {{
            color: #E3C85B;
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            margin-bottom: 0.45rem;
        }}

        .macro-summary-text {{
            color: #F3F4F6;
            font-size: 0.9rem;
            line-height: 1.6;
        }}

        .confidence-badge {{
            display: inline-block;
            border-radius: 999px;
            padding: 0.32rem 0.7rem;
            font-size: 0.74rem;
            font-weight: 800;
            margin-top: 0.85rem;
            margin-bottom: 0.35rem;
        }}

        .confidence-high {{
            background: #DCFCE7;
            color: #166534;
        }}

        .confidence-medium {{
            background: #FEF3C7;
            color: #92400E;
        }}

        .confidence-low {{
            background: #FEE2E2;
            color: #991B1B;
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


# ===================================================
# FX LIVE DRIVERS — IA + WEB SEARCH (TEST)
# ===================================================

@st.cache_data(ttl=900, show_spinner=False)
def buscar_bancos_centrales_ia_test(divisa):

    client = OpenAI(
        api_key=st.secrets["OPENAI_API_KEY"]
    )

    configuracion = {

        "USD": {
            "banco": "Federal Reserve",
            "miembros": """
Kevin Warsh, John Williams, Michael Barr, Michelle Bowman,
Lisa Cook, Beth Hammack, Philip Jefferson, Neel Kashkari,
Lorie Logan, Anna Paulson, Jerome Powell, Christopher Waller,
Austan Goolsbee, Susan Collins, Mary Daly, Thomas Barkin,
Alberto Musalem, Jeffrey Schmid
""",
        },

        "EUR": {
            "banco": "European Central Bank / Eurosystem",
            "miembros": """
Christine Lagarde, Boris Vujcic, Philip Lane, Isabel Schnabel,
Piero Cipollone, Luis de Guindos, Joachim Nagel, Olli Rehn,
Martin Kocher, Bostjan Vasle, Primoz Dolenc, Martins Kazaks,
Klaas Knot, Mario Centeno, Francois Villeroy de Galhau,
Fabio Panetta, Gabriel Makhlouf, Pierre Wunsch
""",
        },
    }

    if divisa not in configuracion:
        return ""

    datos = configuracion[divisa]

    prompt = f"""
Search the web for RECENT statements, interviews, speeches,
media appearances or direct comments made during approximately
the last 48 hours by members of the {datos["banco"]}.

Currency: {divisa}

Relevant people include:
{datos["miembros"]}

The objective is NOT to provide general news about the central bank.

I specifically want statements or comments actually made by
central-bank officials that could matter for monetary policy
or the {divisa} currency.

Search broadly across:
- official central-bank websites
- Reuters
- Bloomberg when publicly indexed
- CNBC
- financial press
- interviews
- speeches
- conference appearances
- reputable financial news websites

Do NOT include:
- analyst forecasts
- market expectations without a direct central-bank statement
- articles that merely mention the central bank
- generic market commentary

For each relevant event provide:

DATE/TIME:
MEMBER:
CENTRAL BANK:
STATEMENT:
CONTEXT:
MONETARY BIAS: Hawkish / Dovish / Neutral
IMPORTANCE: High / Medium / Low
SOURCE:
SOURCE URL:

IMPORTANT OUTPUT RULES:

- SOURCE must contain only the publisher or original source name.
  Example: Reuters, CNBC, Federal Reserve.

- SOURCE URL must contain ONLY one raw absolute URL beginning with https://
  Do not use Markdown links.
  Do not use brackets.
  Do not add citations or source names inside SOURCE URL.

- DATE/TIME must be ISO 8601 UTC when the exact time is known.
  Example: 2026-08-28T16:00:00Z

- If the exact time cannot be reliably established, return null for datetime.
  Do not invent a time.

If several articles report the same comments, consolidate them
into one event.

Prioritize completeness over speed.

If there are no relevant comments, say:
NO RELEVANT STATEMENTS FOUND.
"""

    response = client.responses.create(
        model="gpt-5.6-luna",
        tools=[
            {
                "type": "web_search",
                "search_context_size": "high",
            }
        ],
        input=prompt,

        text={
            "format": {
                "type": "json_schema",
                "name": "central_bank_drivers",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "events": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "datetime": {
                                        "type": [
                                            "string",
                                            "null"
                                        ]
                                    },
                                    "currency": {
                                        "type": "string"
                                    },
                                    "member": {
                                        "type": "string"
                                    },
                                    "central_bank": {
                                        "type": "string"
                                    },
                                    "statement": {
                                        "type": "string"
                                    },
                                    "context": {
                                        "type": "string"
                                    },
                                    "bias": {
                                        "type": "string",
                                        "enum": [
                                            "Hawkish",
                                            "Dovish",
                                            "Neutral"
                                        ]
                                    },
                                    "importance": {
                                        "type": "string",
                                        "enum": [
                                            "High",
                                            "Medium",
                                            "Low"
                                        ]
                                    },
                                    "source": {
                                        "type": "string"
                                    },
                                    "source_url": {
                                        "type": "string"
                                    }
                                },
                                "required": [
                                    "datetime",
                                    "currency",
                                    "member",
                                    "central_bank",
                                    "statement",
                                    "context",
                                    "bias",
                                    "importance",
                                    "source",
                                    "source_url"
                                ],
                                "additionalProperties": False
                            }
                        }
                    },
                    "required": [
                        "events"
                    ],
                    "additionalProperties": False
                }
            }
        },
    )

    return response.output_text

def preparar_central_bank_drivers(resultado_ia):
    """
    Convierte la respuesta JSON de OpenAI Web Search
    en filas preparadas para CentralBank_Drivers.

    Todavía NO escribe en Google Sheets.
    """

    if not resultado_ia:
        return []

    try:
        data = json.loads(resultado_ia)
    except Exception as error:
        raise ValueError(
            f"No se pudo interpretar la respuesta de OpenAI como JSON: {error}"
        )

    eventos = data.get("events", [])

    if not isinstance(eventos, list):
        return []

    detected_at = datetime.now(timezone.utc).isoformat()

    filas = []

    for evento in eventos:

        currency = str(
            evento.get("currency") or ""
        ).strip().upper()

        member = str(
            evento.get("member") or ""
        ).strip()

        statement = str(
            evento.get("statement") or ""
        ).strip()

        if not currency or not member or not statement:
            continue

        # ID estable para evitar guardar el mismo comentario
        # más de una vez en búsquedas posteriores.
        texto_id = (
            f"{currency}|"
            f"{member.lower()}|"
            f"{statement.lower()}"
        )

        event_id = hashlib.sha256(
            texto_id.encode("utf-8")
        ).hexdigest()[:24]

        fila = {
            "EventID": event_id,
            "DateTime": evento.get("datetime"),
            "Currency": currency,
            "Member": member,
            "CentralBank": str(
                evento.get("central_bank") or ""
            ).strip(),
            "Statement": statement,
            "Context": str(
                evento.get("context") or ""
            ).strip(),
            "Bias": str(
                evento.get("bias") or ""
            ).strip(),
            "Importance": str(
                evento.get("importance") or ""
            ).strip(),
            "Source": str(
                evento.get("source") or ""
            ).strip(),
            "SourceURL": str(
                evento.get("source_url") or ""
            ).strip(),
            "DetectedAt": detected_at,
        }

        filas.append(fila)

    return filas


def guardar_central_bank_drivers(filas):
    """
    Envía eventos preparados al Web App de Apps Script.
    Apps Script se encarga de evitar duplicados por EventID.
    """

    if not filas:
        return {
            "ok": True,
            "received": 0,
            "inserted": 0,
            "duplicates": 0,
        }

    try:
        url = st.secrets[
            "CENTRAL_BANK_DRIVERS_WEBAPP_URL"
        ]
    except Exception:
        raise ValueError(
            "Falta CENTRAL_BANK_DRIVERS_WEBAPP_URL "
            "en Streamlit Secrets."
        )

    payload = {
        "action": "save_central_bank_drivers",
        "events": filas,
    }

    response = requests.post(
        url,
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    try:
        data = response.json()
    except Exception:
        raise ValueError(
            "Apps Script respondió, pero no devolvió JSON válido: "
            + response.text[:500]
        )

    if not data.get("ok"):
        raise ValueError(
            "Apps Script devolvió error: "
            + str(data.get("error"))
        )

    return data

def probar_central_bank_webapp():

    url = st.secrets[
        "CENTRAL_BANK_DRIVERS_WEBAPP_URL"
    ]

    response = requests.post(
        url,
        json={"action": "ping"},
        timeout=20,
    )

    return {
        "status_code": response.status_code,
        "text": response.text,
    }

@st.cache_data(ttl=300, show_spinner=False)
def cargar_live_drivers_oficiales(divisa):
    """
    TEST INDEPENDIENTE
    Fuentes oficiales para FX Live Drivers.

    Por ahora:
    - USD -> Federal Reserve
    - EUR -> European Central Bank

    NO modifica NewsAPI ni Finnhub.
    """

    feeds = {
        "USD": [
            {
                "source": "Federal Reserve",
                "url": "https://www.federalreserve.gov/feeds/speeches.xml",
            },
            {
                "source": "Federal Reserve",
                "url": "https://www.federalreserve.gov/feeds/press_monetary.xml",
            },
            {
                "source": "Chicago Fed",
                "url": "https://www.chicagofed.org/rss/speeches.xml",
            },
        ],

        "EUR": [
            {
                "source": "European Central Bank",
                "url": "https://www.ecb.europa.eu/rss/press.html",
            },
        ],
    }

    if divisa not in feeds:
        return {
            "ok": True,
            "error": None,
            "articles": [],
        }

    articles = []

    try:

        for feed_config in feeds[divisa]:

            feed = feedparser.parse(
                feed_config["url"]
            )

            for entry in feed.entries:

                title = str(
                    entry.get("title", "")
                ).strip()

                url = str(
                    entry.get("link", "")
                ).strip()

                summary = str(
                    entry.get("summary", "")
                ).strip()

                published_at = None

                if entry.get("published_parsed"):
                    published_at = datetime(
                        *entry.published_parsed[:6],
                        tzinfo=timezone.utc,
                    )

                elif entry.get("updated_parsed"):
                    published_at = datetime(
                        *entry.updated_parsed[:6],
                        tzinfo=timezone.utc,
                    )

                if not published_at:
                    continue

                articles.append(
                    {
                        "title": title,
                        "url": url,
                        "description": summary,
                        "publishedAt": published_at.isoformat(),
                        "source": feed_config["source"],
                        "_provider": "Official",
                        "_currency": divisa,
                    }
                )

        fecha_limite = (
            datetime.now(timezone.utc)
            - timedelta(days=7)
        )

        articles = [
            article
            for article in articles
            if datetime.fromisoformat(
                article["publishedAt"]
            ) >= fecha_limite
        ]

        articles_unicos = []
        vistos = set()

        for article in articles:

            clave = (
                article.get("url")
                or article.get("title", "").lower()
            )

            if not clave or clave in vistos:
                continue

            vistos.add(clave)
            articles_unicos.append(article)

        articles_unicos.sort(
            key=lambda x: x["publishedAt"],
            reverse=True,
        )

        return {
            "ok": True,
            "error": None,
            "articles": articles_unicos,
        }

    except Exception as e:

        return {
            "ok": False,
            "error": str(e),
            "articles": [],
        }


def test_fuentes_oficiales():

    st.subheader("TEST — Fuentes oficiales")

    for divisa in ["USD", "EUR"]:

        resultado = cargar_live_drivers_oficiales(divisa)

        st.write(
            divisa,
            "OK:",
            resultado["ok"],
            "TOTAL:",
            len(resultado["articles"]),
        )

        if resultado["error"]:
            st.error(resultado["error"])

        for article in resultado["articles"][:10]:
            st.write(
                article["publishedAt"],
                article["source"],
                article["title"],
            )

def test_ia_web_bancos_centrales():

    st.subheader("TEST — IA + Web Search")

    col1, col2 = st.columns(2)

    with col1:
        ejecutar_usd = st.button("Buscar USD")

    with col2:
        ejecutar_eur = st.button("Buscar EUR")

    if st.button("Probar conexión CentralBank API"):

        try:
            resultado_ping = probar_central_bank_webapp()

            st.write(
                "Respuesta CentralBank API:",
                resultado_ping
            )

        except Exception as e:
            st.error(
                f"Error conexión CentralBank API: {str(e)}"
        )

    if ejecutar_usd:

        st.markdown("### USD")

        try:
            st.write("PASO 1 — iniciando búsqueda")

            resultado = buscar_bancos_centrales_ia_test("USD")

            st.write("PASO 2 — respuesta recibida")
            st.write("Tipo respuesta:", type(resultado).__name__)
            st.write("Longitud respuesta:", len(resultado) if resultado else 0)

            filas = preparar_central_bank_drivers(
                resultado
            )

            resultado_guardado = guardar_central_bank_drivers(
                filas
            )

            st.write(
                "Guardado en Google Sheets:",
                resultado_guardado
            )

            st.write("PASO 3 — JSON procesado — VERSION NUEVA")
            st.write(
                "Eventos preparados:",
                len(filas)
            )

            st.dataframe(
                pd.DataFrame(filas),
                use_container_width=True,
                hide_index=True,
            )

            if st.button("TEST — Reenviar mismos eventos"):

                try:
                    resultado_duplicados = guardar_central_bank_drivers(
                        filas
                    )

                    st.write(
                        "Resultado test duplicados:",
                        resultado_duplicados
                    )

                except Exception as e:
                    st.error(
                        f"Error test duplicados: {str(e)}"
                    )

        except Exception as e:
            st.error(
                f"Error USD: {str(e)}"
            )

    if ejecutar_eur:

        st.markdown("### EUR")

        try:
            resultado = buscar_bancos_centrales_ia_test("EUR")
            st.write(resultado)

        except Exception as e:
            st.error(
                f"Error EUR: {str(e)}"
            )

def construir_url(nombre_hoja):
    nombre_codificado = quote(nombre_hoja, safe="")
    return (
        f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?"
        f"tqx=out:csv&sheet={nombre_codificado}"
    )

@st.cache_data(ttl=60, show_spinner=False)
def cargar_central_bank_drivers(divisa):
    try:
        df = pd.read_csv(
            construir_url("CentralBank_Drivers")
        )

        df.columns = [
            str(col).strip()
            for col in df.columns
        ]

        if df.empty:
            return {
                "ok": True,
                "drivers": [],
                "error": None,
            }

        # ---------------------------------------
        # Divisa
        # ---------------------------------------

        df["Currency"] = (
            df["Currency"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
        )

        df = df[
            df["Currency"] == str(divisa).upper()
        ].copy()

        if df.empty:
            return {
                "ok": True,
                "drivers": [],
                "error": None,
            }

        # ---------------------------------------
        # Fecha
        #
        # Prioridad:
        # 1. DateTime del evento
        # 2. DetectedAt si OpenAI no pudo
        #    determinar una hora exacta
        # ---------------------------------------

        df["_event_time"] = pd.to_datetime(
            df["DateTime"],
            utc=True,
            errors="coerce",
        )

        detected = pd.to_datetime(
            df["DetectedAt"],
            utc=True,
            errors="coerce",
        )

        df["_sort_time"] = (
            df["_event_time"]
            .fillna(detected)
        )

        # ---------------------------------------
        # Máximo 7 días
        # ---------------------------------------

        fecha_limite = (
            pd.Timestamp.now(tz="UTC")
            - pd.Timedelta(days=7)
        )

        df = df[
            df["_sort_time"].notna()
            & (df["_sort_time"] >= fecha_limite)
        ].copy()

        df = df.sort_values(
            "_sort_time",
            ascending=False,
        )

        # ---------------------------------------
        # Convertir a diccionarios
        # ---------------------------------------

        drivers = []

        for _, row in df.iterrows():

            drivers.append({
                "EventID": str(
                    row.get("EventID") or ""
                ).strip(),

                "DateTime": (
                    row["_event_time"].isoformat()
                    if pd.notna(row["_event_time"])
                    else None
                ),

                "Currency": str(
                    row.get("Currency") or ""
                ).strip(),

                "Member": str(
                    row.get("Member") or ""
                ).strip(),

                "CentralBank": str(
                    row.get("CentralBank") or ""
                ).strip(),

                "Statement": str(
                    row.get("Statement") or ""
                ).strip(),

                "Context": str(
                    row.get("Context") or ""
                ).strip(),

                "Bias": str(
                    row.get("Bias") or ""
                ).strip(),

                "Importance": str(
                    row.get("Importance") or ""
                ).strip(),

                "Source": str(
                    row.get("Source") or ""
                ).strip(),

                "SourceURL": str(
                    row.get("SourceURL") or ""
                ).strip(),

                "DetectedAt": str(
                    row.get("DetectedAt") or ""
                ).strip(),
            })

        return {
            "ok": True,
            "drivers": drivers,
            "error": None,
        }

    except Exception as error:

        return {
            "ok": False,
            "drivers": [],
            "error": str(error),
        }

def render_central_bank_drivers(divisa):
    resultado = cargar_central_bank_drivers(
        divisa
    )

    if not resultado["ok"]:
        st.error(
            "No se pudo cargar CentralBank_Drivers."
        )
        st.caption(
            resultado["error"]
        )
        return

    drivers = resultado["drivers"]

    if not drivers:
        st.info(
            f"No hay declaraciones recientes de bancos centrales "
            f"para {divisa}."
        )
        return

    # Máximo 7 visibles
    drivers = drivers[:7]

    st.caption(
        f"{len(drivers)} drivers de bancos centrales · "
        "Fuente: OpenAI Web Search"
    )

    for driver in drivers:

        member = html.escape(
            driver.get("Member") or "Banco central"
        )

        statement = html.escape(
            driver.get("Statement") or ""
        )

        context = html.escape(
            driver.get("Context") or ""
        )

        bias = html.escape(
            driver.get("Bias") or "Neutral"
        )

        importance = html.escape(
            driver.get("Importance") or "Medium"
        )

        central_bank = html.escape(
            driver.get("CentralBank") or ""
        )

        source = html.escape(
            driver.get("Source") or ""
        )

        source_url = str(
            driver.get("SourceURL") or ""
        ).strip()

        datetime_evento = str(
            driver.get("DateTime") or ""
        ).strip()

        if (
            datetime_evento
            and datetime_evento.lower()
            not in ["none", "nan", "nat"]
        ):
            fecha = pd.to_datetime(
                datetime_evento,
                utc=True,
                errors="coerce",
            )

            if pd.notna(fecha):
                fecha_texto = fecha.strftime(
                    "%d %b %Y · %H:%M UTC"
                )
            else:
                fecha_texto = "Fecha exacta no disponible"

        else:
            fecha_texto = "Fecha exacta no disponible"

        etiqueta = (
            f"{divisa} · {bias.upper()} · "
            f"{importance.upper()}"
        )

        html_driver = (
            f'<div style="background:#FFFFFF;'
            f'border:1px solid #E5E7EB;'
            f'border-radius:14px;'
            f'padding:1rem 1.15rem;'
            f'margin-bottom:0.85rem;">'

            f'<div style="color:#9A7A10;'
            f'font-size:0.72rem;'
            f'font-weight:800;'
            f'letter-spacing:0.05em;'
            f'margin-bottom:0.35rem;">'
            f'{etiqueta}'
            f'</div>'

            f'<div style="color:#111111;'
            f'font-size:0.82rem;'
            f'font-weight:750;'
            f'margin-bottom:0.35rem;">'
            f'{member}'
            f'{" · " + central_bank if central_bank else ""}'
            f'</div>'

            f'<div style="color:#111111;'
            f'font-size:1.02rem;'
            f'font-weight:750;'
            f'line-height:1.5;">'
            f'{statement}'
            f'</div>'
        )

        if context:
            html_driver += (
                f'<div style="color:#6B7280;'
                f'font-size:0.82rem;'
                f'line-height:1.5;'
                f'margin-top:0.55rem;">'
                f'{context}'
                f'</div>'
            )

        meta = []

        if fecha_texto:
            meta.append(fecha_texto)

        if source:
            meta.append(source)

        if meta:
            html_driver += (
                f'<div style="color:#9CA3AF;'
                f'font-size:0.74rem;'
                f'margin-top:0.65rem;">'
                f'{" · ".join(meta)}'
                f'</div>'
            )

        if source_url.startswith("http"):
            url_segura = html.escape(
                source_url,
                quote=True,
            )

            html_driver += (
                f'<div style="margin-top:0.65rem;'
                f'font-size:0.82rem;">'
                f'<a href="{url_segura}" '
                f'target="_blank" '
                f'style="color:#2563EB;'
                f'text-decoration:none;">'
                f'Abrir fuente ↗'
                f'</a>'
                f'</div>'
            )

        html_driver += "</div>"

        st.markdown(
            html_driver,
            unsafe_allow_html=True,
        )

@st.cache_data(ttl=60, show_spinner=False)
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


@st.cache_data(ttl=60, show_spinner=False)
def cargar_interpretaciones_ia():
    """
    Carga la hoja AI_Interpretations desde Google Sheets.
    """
    nombre_hoja = "AI_Interpretations"

    df_ia = pd.read_csv(
        construir_url(nombre_hoja)
    )

    df_ia.columns = [
        str(columna).strip()
        for columna in df_ia.columns
    ]

    df_ia = df_ia.dropna(
        axis=0,
        how="all"
    )

    return df_ia

@st.cache_data(ttl=60, show_spinner=False)
def cargar_macro_releases():

    nombre_hoja = "Macro_Releases"

    df_releases = pd.read_csv(
        construir_url(nombre_hoja)
    )

    df_releases.columns = [
        str(columna).strip()
        for columna in df_releases.columns
    ]

    df_releases = (
        df_releases
        .dropna(axis=0, how="all")
        .reset_index(drop=True)
    )

    columnas_necesarias = {
        "Currency",
        "Country",
        "Indicator",
        "ReleaseDate",
        "Period",
        "Comparison",
        "Actual",
        "Previous",
        "Estimate",
    }

    faltantes = columnas_necesarias - set(df_releases.columns)

    if faltantes:
        raise ValueError(
            "Faltan columnas en Macro_Releases: "
            + ", ".join(sorted(faltantes))
        )

    df_releases["ReleaseDate"] = pd.to_datetime(
        df_releases["ReleaseDate"],
        errors="coerce",
    )

    df_releases["Currency"] = (
        df_releases["Currency"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    df_releases["Indicator"] = (
        df_releases["Indicator"]
        .astype(str)
        .str.strip()
    )

    df_releases["Comparison"] = (
        df_releases["Comparison"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.lower()
    )

    df_releases = (
        df_releases
        .dropna(subset=["ReleaseDate"])
        .sort_values("ReleaseDate")
        .reset_index(drop=True)
    )

    return df_releases

def obtener_releases_intervalo(
    df_releases,
    currency,
    fecha_anterior,
    fecha_actual,
):

    if df_releases is None or df_releases.empty:
        return pd.DataFrame()

    currency = str(currency).strip().upper()

    fecha_anterior = pd.to_datetime(fecha_anterior)
    fecha_actual = pd.to_datetime(fecha_actual)

    resultado = df_releases[
        (df_releases["Currency"] == currency)
        &
        (df_releases["ReleaseDate"] > fecha_anterior)
        &
        (df_releases["ReleaseDate"] <= fecha_actual)
    ].copy()

    return (
        resultado
        .sort_values("ReleaseDate")
        .reset_index(drop=True)
    )

MAPA_INDICADORES_IA = {
    "GBP": {
        "CPI": "CPI MoM",
        "CPI YoY": "CPI YoY",
        "Core CPI": "Core CPI MoM",
        "Core CPI YoY": "Core CPI YoY",
        "Retail Sales": "Retail Sales MoM",
        "Core Retail Sales": "Core Retail Sales",
        "Employment (3M/3M)": "Employment Change (3M/3M)",
        "%Desempleo": "Unemployment Rate",
        "% Salario + Bonus": "Average Earnings (+ Bonus)",
        "% Salario - Bonus": "Average Earnings (- Bonus)",
        "PMI Manufactura": "Manufacturing PMI",
        "PMI Servicios": "Services PMI",
        "Confianza del Consumidor": "Consumer Confidence",
    },

    "USD": {
        "CPI": "CPI YoY",
        "Core CPI": "Core CPI YoY",
        "Core PCE YoY": "Core PCE YoY",
        "PPI MoM": "PPI MoM",
        "Core PPI MoM": "Core PPI MoM",
        "Retail Sales": "Retail Sales MoM",
        "Core Retail Sales": "Core Retail Sales",
        "NFP": "Non Farm Payrolls",
        "%Desempleo": "Unemployment Rate",
        "% Salario": "Average Hourly Earnings",
        "JOLTS": "JOLTS",
        "ADP": "ADP Employment",
        "PMI Manufactura": "ISM Manufacturing",
        "PMI Servicios": "ISM Services",
        "Confianza CB": "Consumer Confidence CB",
    },

    "EUR": {
        "CPI": "CPI MoM",
        "CPI YoY": "CPI YoY",
        "Core CPI": "Core CPI MoM",
        "Core CPI YoY": "Core CPI YoY",
        "Retail Sales": "Retail Sales MoM",
        "Retail Sales YoY": "Retail Sales YoY",
        "%Desempleo": "Unemployment Rate",
        "Salario Eurozona": "Euro Area Wage Growth",
        "PMI Manufactura": "Manufacturing PMI",
        "PMI Servicios": "Services PMI",
        "ZEW": "ZEW Economic Sentiment",
        "Clima Empresarial Eurozona": "Eurozone Business Climate",
        "Producción Industrial": "Industrial Production YoY",
        "Confianza del Consumidor": "Consumer Confidence",
    },

    "CAD": {},
    "JPY": {},
    "AUD": {
        "Household Spending MoM": "Household Spending MoM",
    },

    "NZD": {
        "Inflation Expectations": "Inflation Expectations",
    },
    "CHF": {},
}

def filtrar_drivers_por_releases(
    drivers,
    releases_intervalo,
):
    """
    Conserva únicamente drivers cuyo indicador tuvo
    una publicación real dentro del intervalo.

    Además añade la fecha real de publicación
    y el nombre utilizado por EODHD.
    """

    if not drivers:
        return []

    if releases_intervalo is None or releases_intervalo.empty:
        return []

    releases = releases_intervalo.copy()

    releases["_indicator_clean"] = (
        releases["Indicator"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.lower()
    )

    # Equivalencias entre nombres internos del dashboard
    # y nombres utilizados por EODHD.
    aliases = {
        "non farm payrolls": [
            "non farm payrolls",
        ],
        "consumer confidence cb": [
            "cb consumer confidence",
        ],
        "ism services": [
            "ism services",
            "ism services pmi",
        ],
        "unemployment rate": [
            "unemployment rate",
        ],
        "adp employment": [
            "adp employment change",
            "adp employment",
        ],
    }

    drivers_filtrados = []

    for driver in drivers:

        indicador = str(
            driver.get("Indicador", "")
        ).strip().lower()

        candidatos = aliases.get(
            indicador,
            [indicador],
        )

        coincidencias = []

        for candidato in candidatos:

            coincidencias_candidato = releases[
                releases["_indicator_clean"].apply(
                    lambda publicado:
                        candidato == publicado
                        or candidato in publicado
                        or publicado in candidato
                )
            ]

            if not coincidencias_candidato.empty:
                coincidencias.append(
                    coincidencias_candidato
                )

        if not coincidencias:
            continue

        coincidencias = pd.concat(
            coincidencias,
            ignore_index=True,
        )

        # Si existe más de una publicación compatible
        # dentro del intervalo, usamos la más reciente.
        coincidencias = coincidencias.sort_values(
            "ReleaseDate"
        )

        release = coincidencias.iloc[-1]

        driver_nuevo = driver.copy()

        driver_nuevo["Fecha publicación"] = (
            release["ReleaseDate"]
        )

        driver_nuevo["Indicador EODHD"] = (
            release["Indicator"]
        )

        driver_nuevo["Periodo publicación"] = (
            release.get("Period", "")
        )

        driver_nuevo["Actual publicación"] = (
            release.get("Actual")
        )

        driver_nuevo["Previous publicación"] = (
            release.get("Previous")
        )

        driver_nuevo["Estimate publicación"] = (
            release.get("Estimate")
        )

        drivers_filtrados.append(
            driver_nuevo
        )

    return drivers_filtrados

def obtener_interpretacion_ia(divisa, indicador):
    """
    Devuelve la interpretación IA correspondiente
    a la divisa y al indicador seleccionado.
    """

    df_ia = cargar_interpretaciones_ia().copy()


    divisa_normalizada = str(divisa).strip().upper()
    indicador_dashboard = str(indicador).strip()

    aliases = {
        "GBP": {
            "PMI Manufactura": "Manufacturing PMI",
            "PMI Servicios": "Services PMI",
            "CPI": "CPI MoM",
            "CPI YoY": "CPI YoY",
            "Core CPI": "Core CPI MoM",
            "Core CPI YoY": "Core CPI YoY",
            "Retail Sales": "Retail Sales MoM",
            "Core Retail Sales": "Core Retail Sales",
            "Employment (3M/3M)": "Employment Change (3M/3M)",
            "%Desempleo": "Unemployment Rate",
            "% Salario + Bonus": "Average Earnings (+ Bonus)",
            "% Salario - Bonus": "Average Earnings (- Bonus)",
            "Confianza del Consumidor": "Consumer Confidence",
        },

        "EUR": {
            "PMI Manufactura": "Manufacturing PMI",
            "PMI Servicios": "Services PMI",
            "CPI": "CPI MoM",
            "CPI YoY": "CPI YoY",
            "Core CPI": "Core CPI MoM",
            "Core CPI YoY": "Core CPI YoY",
            "Retail Sales": "Retail Sales MoM",
            "Retail Sales YoY": "Retail Sales YoY",
            "%Desempleo": "Unemployment Rate",
            "Salario Eurozona": "Euro Area Wage Growth",
            "ZEW": "ZEW Economic Sentiment",
            "Clima Empresarial Eurozona": "Eurozone Business Climate",
            "Producción Industrial": "Industrial Production YoY",
            "Confianza del Consumidor": "Consumer Confidence",
        },

        "USD": {
            "CPI": "CPI YoY",
            "Core CPI": "Core CPI YoY",
            "Core PCE YoY": "Core PCE YoY",
            "PPI MoM": "PPI MoM",
            "Core PPI MoM": "Core PPI MoM",
            "Retail Sales": "Retail Sales MoM",
            "Core Retail Sales": "Core Retail Sales",
            "NFP": "Non Farm Payrolls",
            "%Desempleo": "Unemployment Rate",
            "% Salario": "Average Hourly Earnings",
            "JOLTS": "JOLTS",
            "ADP": "ADP Employment",
            "PMI Manufactura": "ISM Manufacturing",
            "PMI Servicios": "ISM Services",
            "Confianza CB": "Consumer Confidence CB",
        },

        "AUD": {
            "Household Spending MoM": "Household Spending MoM",
        },

        "NZD": {
            "Inflation Expectations": "Inflation Expectations",
        },
    }

    indicador_ia = aliases.get(
        divisa_normalizada,
        {}
    ).get(
        indicador_dashboard,
        indicador_dashboard
    )

    columnas_requeridas = {
        "Currency",
        "Indicator",
        "Current Situation",
        "Trend",
        "Latest Release",
        "Monetary Policy",
        "FX Impact",
        "Summary",
        "Confidence",
        "Updated At",
    }

    columnas_faltantes = columnas_requeridas.difference(df_ia.columns)

    if columnas_faltantes:
        raise ValueError(
            "Faltan columnas en AI_Interpretations: "
            + ", ".join(sorted(columnas_faltantes))
        )

    df_ia["_currency_clean"] = (
        df_ia["Currency"]
        .astype(str)
        .str.replace("\u00a0", " ", regex=False)
        .str.replace("\u200b", "", regex=False)
        .str.strip()
        .str.upper()
    )

    df_ia["_indicator_clean"] = (
        df_ia["Indicator"]
        .astype(str)
        .str.replace("\u00a0", " ", regex=False)
        .str.replace("\u200b", "", regex=False)
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )

    indicador_ia_limpio = (
        str(indicador_ia)
        .replace("\u00a0", " ")
        .replace("\u200b", "")
        .strip()
    )

    coincidencia = df_ia[
        df_ia["_currency_clean"].eq(divisa_normalizada)
        &
        df_ia["_indicator_clean"].eq(indicador_ia_limpio)
    ].copy()

    if coincidencia.empty:
        return None

    if "Updated At" in coincidencia.columns:
        coincidencia["_updated_at_order"] = pd.to_datetime(
            coincidencia["Updated At"],
            errors="coerce"
        )

        coincidencia = coincidencia.sort_values(
            "_updated_at_order",
            na_position="first"
        )

    resultado = coincidencia.iloc[-1].to_dict()

    resultado.pop("_currency_clean", None)
    resultado.pop("_indicator_clean", None)
    resultado.pop("_updated_at_order", None)

    return resultado


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

def calcular_data_version(df_currency, currency):
    """
    Genera una huella de los datos utilizados por Currency Score.

    Si cambia cualquier valor del Dashboard o cualquier release
    relevante de la divisa, cambia también data_version.
    """

    currency = str(currency).strip().upper()

    hash_obj = hashlib.sha256()

    # -----------------------------------------------
    # 1. Datos del Dashboard / Google Sheet
    # -----------------------------------------------

    df_version = (
        df_currency
        .copy()
        .fillna("<NA>")
        .astype(str)
    )

    hash_dashboard = pd.util.hash_pandas_object(
        df_version,
        index=True,
    ).values.tobytes()

    hash_obj.update(hash_dashboard)

    # -----------------------------------------------
    # 2. Macro Releases
    # -----------------------------------------------

    try:
        releases = cargar_macro_releases()

        releases_currency = (
            releases[
                releases["Currency"].eq(currency)
            ]
            .copy()
            .fillna("<NA>")
            .astype(str)
        )

        hash_releases = pd.util.hash_pandas_object(
            releases_currency,
            index=True,
        ).values.tobytes()

        hash_obj.update(hash_releases)

    except Exception:
        pass

    return hash_obj.hexdigest()[:20]

def analizar_divisa_completa(
    df,
    divisa,
    indicadores,
    fecha_corte=None,
):
    """
    Ejecuta monetary_engine para todos los indicadores disponibles
    de una divisa y prepara los resultados para currency_score_engine.

    Si fecha_corte está definida, solamente utiliza información
    disponible hasta esa fecha.
    """

    resultados = {}

    for nombre_indicador in indicadores:

        valores = convertir_valores(
            df[nombre_indicador]
        )

        datos_indicador = pd.DataFrame({
            "Fecha": df["Fecha"],
            "Valor": valores,
        })

        if fecha_corte is not None:
            datos_indicador = datos_indicador[
                datos_indicador["Fecha"] <= fecha_corte
            ].copy()

        datos_indicador = (
            datos_indicador
            .dropna()
            .sort_values("Fecha")
            .reset_index(drop=True)
        )

        if len(datos_indicador) < 2:
            continue

        try:
            nombre_currency_score = (
                MAPA_INDICADORES_IA
                .get(str(divisa).strip().upper(), {})
                .get(nombre_indicador, nombre_indicador)
            )

            resultado = analizar_indicador(
                datos_indicador["Fecha"],
                datos_indicador["Valor"],
                nombre_currency_score,
                divisa,
            )

            if resultado is not None:
                resultados[nombre_currency_score] = resultado

        except Exception:
            # Un indicador defectuoso no debe impedir
            # calcular toda la divisa.
            continue

    return resultados

def construir_df_currency_por_release(
    df_currency,
    currency,
    indicadores_currency,
):
    """
    Mantiene los valores ORIGINALES de Dashboard_USD y utiliza
    Macro_Releases/EODHD únicamente para asignar la fecha real
    en la que cada observación estuvo disponible para el mercado.

    DATE representa el periodo económico.
    ReleaseDate representa el momento real de publicación.
    """

    currency = str(currency).strip().upper()

   # Esta arquitectura se aplica a las divisas RELEASE_AWARE.
    if currency not in RELEASE_AWARE_CURRENCIES:
        return {}

    df_releases = cargar_macro_releases()

    df_releases = df_releases[
        df_releases["Currency"].eq(currency)
    ].copy()

    if df_releases.empty:
        return {}

    # ===================================================
    # ALIASES DASHBOARD / CURRENCY SCORE -> EODHD
    # ===================================================

    aliases_eodhd_por_divisa = {

        # ===================================================
        # USD
        # ===================================================

        "USD": {

            "Non Farm Payrolls": {
                "names": ["Non Farm Payrolls"],
                "comparison": "",
            },

            "Unemployment Rate": {
                "names": ["Unemployment Rate"],
                "comparison": "",
            },

            "Average Hourly Earnings": {
                "names": ["Average Hourly Earnings"],
                "comparison": "mom",
            },

            "ADP Employment": {
                "names": [
                    "ADP Employment Change",
                    "ADP Employment",
                ],
                "comparison": "",
            },

            "Consumer Confidence CB": {
                "names": ["CB Consumer Confidence"],
                "comparison": "",
            },

            "ISM Services": {
                "names": [
                    "ISM Services PMI",
                    "ISM Services",
                    "ISM Non-Manufacturing PMI",
                ],
                "comparison": "",
            },


            "ISM Manufacturing": {
                "names": [
                    "ISM Manufacturing PMI",
                    "ISM Manufacturing",
                ],
                "comparison": "",
            },

            "PMI Manufactura": {
                "names": [
                    "ISM Manufacturing PMI",
                    "ISM Manufacturing",
                ],
                "comparison": "",
            },

            "CPI YoY": {
                "names": ["CPI"],
                "comparison": "yoy",
            },

            "Core CPI YoY": {
                "names": ["Core CPI"],
                "comparison": "yoy",
            },

            "PPI MoM": {
                "names": [
                    "PPI",
                    "Producer Price Index",
                ],
                "comparison": "mom",
            },

            "Core PPI MoM": {
                "names": ["Core PPI"],
                "comparison": "mom",
            },

            "Retail Sales MoM": {
                "names": ["Retail Sales"],
                "comparison": "mom",
            },

            "Core Retail Sales": {
                "names": [
                    "Retail Sales Ex Autos",
                    "Retail Sales Ex Gas/Autos",
                ],
                "comparison": "mom",
            },

            "JOLTS": {
                "names": ["JOLTS Job Openings"],
                "comparison": "",
            },

            "Confianza UoM": {
                "names": [
                    "Michigan Consumer Sentiment",
                    "University of Michigan Consumer Sentiment",
                ],
                "comparison": "",
            },

            "GDP Growth Rate (QoQ)": {
                "names": ["GDP Growth Rate"],
                "comparison": "qoq",
            },

            "GDP Annual Growth Rate (YoY)": {
                "names": ["GDP Growth Rate"],
                "comparison": "yoy",
            },
        },


        # ===================================================
        # GBP
        # ===================================================

        "GBP": {

            "CPI MoM": {
                "names": ["CPI"],
                "comparison": "mom",
            },

            "CPI YoY": {
                "names": ["CPI"],
                "comparison": "yoy",
            },

            "Core CPI MoM": {
                "names": ["Core CPI"],
                "comparison": "mom",
            },

            "Core CPI YoY": {
                "names": ["Core CPI"],
                "comparison": "yoy",
            },

            "Retail Sales MoM": {
                "names": ["Retail Sales"],
                "comparison": "mom",
            },

            "Core Retail Sales": {
                "names": ["Retail Sales Ex Fuel"],
                "comparison": "mom",
            },

            "Employment Change (3M/3M)": {
                "names": ["Employment Change"],
                "comparison": "",
            },

            "Unemployment Rate": {
                "names": ["Unemployment Rate"],
                "comparison": "",
            },

            "Average Earnings (+ Bonus)": {
                "names": ["Average Earnings incl. Bonus"],
                "comparison": "",
            },

            "Average Earnings (- Bonus)": {
                "names": ["Average Earnings excl. Bonus"],
                "comparison": "",
            },

            "Manufacturing PMI": {
                "names": [
                    "S&P Global Manufacturing PMI",
                    "S&P Global Manufacturing PMI Flash",
                ],
                "comparison": "",
            },

            "Services PMI": {
                "names": [
                    "S&P Global Services PMI",
                    "S&P Global Services PMI Flash",
                ],
                "comparison": "",
            },

            "Consumer Confidence": {
                "names": ["Consumer Confidence"],
                "comparison": "",
            },

            "GDP Growth Rate (QoQ)": {
                "names": ["GDP Growth Rate"],
                "comparison": "qoq",
            },

            "GDP Annual Growth Rate (YoY)": {
                "names": ["GDP Growth Rate"],
                "comparison": "yoy",
            },
        },


        # ===================================================
        # EUR
        # ===================================================

        "EUR": {

            "CPI MoM": {
                "names": ["CPI"],
                "comparison": "mom",
            },

            "CPI YoY": {
                "names": ["CPI"],
                "comparison": "yoy",
            },

            "Core CPI MoM": {
                "names": ["Core CPI"],
                "comparison": "mom",
            },

            "Core CPI YoY": {
                "names": ["Core CPI"],
                "comparison": "yoy",
            },

            "Retail Sales MoM": {
                "names": ["Retail Sales"],
                "comparison": "mom",
            },

            "Retail Sales YoY": {
                "names": ["Retail Sales"],
                "comparison": "yoy",
            },

            "Unemployment Rate": {
                "names": ["Unemployment Rate"],
                "comparison": "",
            },

            "Euro Area Wage Growth": {
                "names": ["Wage Growth"],
                "comparison": "yoy",
            },

            "Manufacturing PMI": {
                "names": [
                    "HCOB Manufacturing PMI",
                    "S&P Global Manufacturing PMI",
                    "Manufacturing PMI",
                ],
                "comparison": "",
            },

            "Services PMI": {
                "names": [
                    "HCOB Services PMI",
                    "S&P Global Services PMI",
                    "Services PMI",
                ],
                "comparison": "",
            },

            "ZEW Economic Sentiment": {
                "names": [
                    "ZEW Economic Sentiment Index",
                    "ZEW Economic Sentiment",
                ],
                "comparison": "",
            },

            "Eurozone Business Climate": {
                "names": [
                    "Business Climate",
                ],
                "comparison": "",
            },

            "Industrial Production YoY": {
                "names": ["Industrial Production"],
                "comparison": "yoy",
            },

            "Consumer Confidence": {
                "names": ["Consumer Confidence"],
                "comparison": "",
            },

            "GDP Growth Rate (QoQ)": {
                "names": [
                    "GDP Growth Rate",
                    "Gross Domestic Product",
                ],
                "comparison": "qoq",
            },

            "GDP Annual Growth Rate (YoY)": {
                "names": [
                    "GDP Growth Rate",
                    "Gross Domestic Product",
                ],
                "comparison": "yoy",
            },
        },


        # ===================================================
        # CAD
        # ===================================================

        "CAD": {

            "GDP Growth Rate (QoQ)": {
                "names": ["GDP Growth Rate"],
                "comparison": "qoq",
            },

            "GDP Annual Growth Rate (YoY)": {
                "names": ["GDP Growth Rate"],
                "comparison": "yoy",
            },

            "Employment": {
                "names": ["Employment Change"],
                "comparison": "",
            },

            "Manufacturing PMI": {
                "names": ["S&P Global Manufacturing PMI"],
                "comparison": "",
            },

            "Business Confidence": {
                "names": [
                    "CFIB Business Barometer",
                    "BoC Business Outlook Survey",
                ],
                "comparison": "",
            },

            "CPI YoY": {
                "names": ["CPI"],
                "comparison": "yoy",
            },

            "Core CPI YoY": {
                "names": ["Core CPI"],
                "comparison": "yoy",
            },

            "Retail Sales MoM": {
                "names": ["Retail Sales"],
                "comparison": "mom",
            },

            "Unemployment Rate": {
                "names": ["Unemployment Rate"],
                "comparison": "",
            },

            "Services PMI": {
                "names": [
                    "Services PMI",
                    "S&P Global Services PMI",
                ],
                "comparison": "",
            },

        },


        # ===================================================
        # JPY
        # ===================================================

        "JPY": {

            "GDP Growth Rate (QoQ)": {
                "names": ["GDP Growth Rate"],
                "comparison": "qoq",
            },

            "GDP Annual Growth Rate (YoY)": {
                "names": ["Gross Domestic Product"],
                "comparison": "yoy",
            },

            "Manufacturing PMI": {
                "names": [
                    "S&P Global Manufacturing PMI",
                    "Jibun Bank Manufacturing PMI",
                    "S&P Global Manufacturing PMI Flash",
                ],
                "comparison": "",
            },

            "CPI YoY": {
                "names": [
                    "CPI",
                    "Inflation Rate",
                    "Inflation Rate YoY",
                ],
                "comparison": "yoy",
            },

            "Core CPI YoY": {
                "names": [
                    "Core CPI",
                    "Core Inflation Rate",
                    "Core Inflation Rate YoY",
                ],
                "comparison": "yoy",
            },

            "Retail Sales MoM": {
                "names": ["Retail Sales"],
                "comparison": "mom",
            },

            "Unemployment Rate": {
                "names": ["Unemployment Rate"],
                "comparison": "",
            },

            "Services PMI": {
                "names": [
                    "Services PMI",
                    "S&P Global Services PMI",
                    "Jibun Bank Services PMI",
                ],
                "comparison": "",
            },

            "Consumer Confidence": {
                "names": ["Consumer Confidence"],
                "comparison": "",
            },

            "Household Spending YoY": {
                "names": ["Household Spending"],
                "comparison": "yoy",
            },

            "Average Cash Earnings YoY": {
                "names": ["Average Cash Earnings"],
                "comparison": "yoy",
            },

            "Business Confidence": {
                "names": ["Tankan Large Manufacturers Index"],
                "comparison": "",
            },


        },


        # ===================================================
        # AUD
        # ===================================================

        "AUD": {

            "GDP Growth Rate (QoQ)": {
                "names": ["GDP Growth Rate"],
                "comparison": "qoq",
            },

            "GDP Annual Growth Rate (YoY)": {
                "names": ["GDP Growth Rate"],
                "comparison": "yoy",
            },

            "Employment": {
                "names": ["Employment Change"],
                "comparison": "",
            },

            "Consumer Confidence": {
                "names": [
                    "Westpac Consumer Confidence Index",
                    "Westpac Consumer Confidence Change",
                ],
                "comparison": "",
            },

            "Household Spending MoM": {
                "names": ["Household Spending"],
                "comparison": "mom",
            },

            "CPI YoY": {
                "names": ["CPI"],
                "comparison": "yoy",
            },

            "Core CPI YoY": {
                "names": [
                    "RBA Trimmed Mean CPI",
                ],
                "comparison": "yoy",
            },

            "Unemployment Rate": {
                "names": ["Unemployment Rate"],
                "comparison": "",
            },

            "Manufacturing PMI": {
                "names": [
                    "Manufacturing PMI",
                    "Judo Bank Manufacturing PMI",
                    "S&P Global Manufacturing PMI",
                ],
                "comparison": "",
            },

            "Services PMI": {
                "names": [
                    "Services PMI",
                    "Judo Bank Services PMI",
                    "S&P Global Services PMI",
                ],
                "comparison": "",
            },

            "Business Confidence": {
                "names": [
                    "NAB Business Confidence",
                    "Business Confidence",
                ],
                "comparison": "",
            },

            # No sustituimos Core CPI por Median CPI /
            # Trimmed Mean CPI sin verificar que sea exactamente
            # la serie que usa Dashboard_AUD.
        },


        # ===================================================
        # NZD
        # ===================================================

        "NZD": {

            "GDP Growth Rate (QoQ)": {
                "names": ["GDP Growth Rate"],
                "comparison": "qoq",
            },

            "GDP Annual Growth Rate (YoY)": {
                "names": ["GDP Growth Rate"],
                "comparison": "yoy",
            },

            "Employment": {
                "names": ["Employment Change"],
                "comparison": "",
            },

            "Manufacturing PMI": {
                "names": ["Business NZ PMI"],
                "comparison": "",
            },

            "Services PMI": {
                "names": ["Services NZ PSI"],
                "comparison": "",
            },

            "Consumer Confidence": {
                "names": [
                    "Westpac Consumer Confidence",
                    "ANZ Roy Morgan Consumer Confidence",
                ],
                "comparison": "",
            },

            "Retail Sales MoM": {
                "names": ["Retail Sales"],
                "comparison": "mom",
            },

            "Unemployment Rate": {
                "names": ["Unemployment Rate"],
                "comparison": "",
            },

            "Business Confidence": {
                "names": [
                    "Business Confidence",
                    "ANZ Business Confidence",
                ],
                "comparison": "",
            },

            "CPI YoY": {
                "names": ["Inflation Rate"],
                "comparison": "yoy",
            },


        },


        # ===================================================
        # CHF
        # ===================================================

        "CHF": {

            "GDP Growth Rate (QoQ)": {
                "names": ["GDP Growth Rate"],
                "comparison": "qoq",
            },

            "GDP Annual Growth Rate (YoY)": {
                "names": ["GDP Growth Rate"],
                "comparison": "yoy",
            },

            "Employment": {
                "names": ["Employment Level"],
                "comparison": "",
            },

            "Manufacturing PMI": {
                "names": ["procure.ch Manufacturing PMI"],
                "comparison": "",
            },

            "CPI YoY": {
                "names": ["CPI"],
                "comparison": "yoy",
            },

            "Core CPI YoY": {
                "names": ["CPI"],
                "comparison": "yoy",
            },

            "Retail Sales MoM": {
                "names": ["Retail Sales"],
                "comparison": "mom",
            },

            "Unemployment Rate": {
                "names": ["Unemployment Rate"],
                "comparison": "",
            },

            "Consumer Confidence": {
                "names": ["Consumer Confidence"],
                "comparison": "",
            },

        },

        }  # cierra aliases_eodhd_por_divisa



# ===================================================
# PROXIES TEMPORALES EODHD
# Indicador Dashboard -> indicador EODHD cuyo
# ReleaseDate se utiliza como reloj
# ===================================================

    proxies_release_eodhd_por_divisa = {

        "JPY": {

            "Tokyo CPI YoY": {
                "names": ["Core CPI"],
                "comparison": "yoy",
            },

            "GDP Annual Growth Rate (YoY)": {
                "names": ["GDP Growth Rate"],
                "comparison": "qoq",
            },

            "Employment": {
                "names": ["Unemployment Rate"],
                "comparison": "",
            },
        },

        "CAD": {

            "GDP Annual Growth Rate (YoY)": {
                "names": ["GDP Growth Rate"],
                "comparison": "qoq",
            },
        },

        "NZD": {

            "Core CPI YoY": {
                "names": ["Inflation Rate"],
                "comparison": "yoy",
            },

        },

    }


    aliases_eodhd = aliases_eodhd_por_divisa.get(
        currency,
        {},
    )

    mapa_currency = MAPA_INDICADORES_IA.get(
        currency,
        {},
    )


    # ===================================================
    # PREPARAR PERIODOS DEL DASHBOARD
    # ===================================================

    dashboard = df_currency.copy()

    dashboard["_Periodo"] = (
        pd.to_datetime(
            dashboard["Fecha"],
            errors="coerce",
        )
        .dt.to_period("M")
    )

    series_por_indicador = {}

    # ===================================================
    # CONSTRUIR CADA SERIE
    # ===================================================

    for columna in indicadores_currency:

        columna_limpia = (
            str(columna)
            .replace("\u00a0", " ")
            .replace("\u200b", "")
        )

        columna_limpia = " ".join(
            columna_limpia.split()
        )

        mapa_currency_limpio = {
            " ".join(
                str(clave)
                .replace("\u00a0", " ")
                .replace("\u200b", "")
                .split()
            ): valor
            for clave, valor in mapa_currency.items()
        }

        nombre_score = mapa_currency_limpio.get(
            columna_limpia,
            columna_limpia,
        )


        config = aliases_eodhd.get(nombre_score)

        # ===================================================
        # PROXY TEMPORAL DE RELEASEDATE
        # ===================================================

        es_proxy_release = False

        proxies_currency = proxies_release_eodhd_por_divisa.get(
            str(currency).strip().upper(),
            {},
        )

        config_proxy = proxies_currency.get(
            nombre_score
        )

        # Si existe proxy explícito, tiene prioridad como reloj
        if config_proxy is not None:
            config = config_proxy
            es_proxy_release = True

        if config is None:

            serie_fallback = pd.DataFrame({
                "Fecha": dashboard["Fecha"],
                "FechaPeriodo": dashboard["Fecha"],
                "Valor": convertir_valores(
                    dashboard[columna]
                ),
                "Period": dashboard["_Periodo"].astype(str),
                "Previous": None,
                "Estimate": None,
                "FuenteFecha": "Fallback Dashboard",
            })

            serie_fallback = (
                serie_fallback
                .dropna(subset=["Fecha", "Valor"])
                .sort_values("Fecha")
                .reset_index(drop=True)
            )

            if not serie_fallback.empty:
                series_por_indicador[nombre_score] = serie_fallback

            continue



        # -----------------------------------------------
        # Valores originales del Dashboard
        # -----------------------------------------------

        valores_dashboard = convertir_valores(
            dashboard[columna]
        )

        datos_dashboard = pd.DataFrame({
            "Periodo": dashboard["_Periodo"],
            "Valor": valores_dashboard,
        })

        datos_dashboard = (
            datos_dashboard
            .dropna(
                subset=[
                    "Periodo",
                    "Valor",
                ]
            )
            .sort_values("Periodo")
            .drop_duplicates(
                subset=["Periodo"],
                keep="last",
            )
            .reset_index(drop=True)
        )

        if datos_dashboard.empty:
            continue

        # -----------------------------------------------
        # Releases EODHD compatibles
        # -----------------------------------------------

        nombres_eodhd = [
            str(nombre).strip().lower()
            for nombre in config["names"]
        ]

        comparison_objetivo = (
            str(config.get("comparison", ""))
            .strip()
            .lower()
        )

        releases_indicador = df_releases[
            df_releases["Indicator"]
            .astype(str)
            .str.strip()
            .str.lower()
            .isin(nombres_eodhd)
        ].copy()


        if comparison_objetivo:

            releases_indicador = releases_indicador[
                releases_indicador["Comparison"]
                .fillna("")
                .astype(str)
                .str.strip()
                .str.lower()
                .eq(comparison_objetivo)
            ]

        releases_indicador = (
            releases_indicador
            .dropna(
                subset=[
                    "ReleaseDate",
                ]
            )
            .sort_values("ReleaseDate")
            .reset_index(drop=True)
        )

        if releases_indicador.empty:

            # ===================================================
            # FALLBACK SI EXISTE CONFIG EODHD PERO NO HAY MATCH
            #
            # Ejemplo actual: PPI MoM.
            # No eliminamos el indicador del Currency Score.
            # Conservamos la serie original de Dashboard_USD.
            # ===================================================

            serie_fallback = pd.DataFrame({
                "Fecha": dashboard["Fecha"],
                "FechaPeriodo": dashboard["Fecha"],
                "Valor": convertir_valores(
                    dashboard[columna]
                ),
                "Period": dashboard["_Periodo"].astype(str),
                "Previous": None,
                "Estimate": None,
                "FuenteFecha": "Fallback Dashboard",
            })

            serie_fallback = (
                serie_fallback
                .dropna(
                    subset=[
                        "Fecha",
                        "Valor",
                    ]
                )
                .sort_values("Fecha")
                .reset_index(drop=True)
            )

            if not serie_fallback.empty:
                series_por_indicador[nombre_score] = (
                    serie_fallback
                )

            continue

        # ===================================================
        # CONVERTIR "Jul", "Jun", etc. EN PERIODO ECONÓMICO
        #
        # El año se deduce de ReleaseDate.
        # Si el mes económico es posterior al mes de release,
        # pertenece al año anterior.
        # ===================================================

        meses_periodo = {
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "may": 5,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "oct": 10,
            "nov": 11,
            "dec": 12,
        }

        def obtener_periodo_release(fila):

            release_date = pd.to_datetime(
                fila["ReleaseDate"],
                errors="coerce",
            )

            if pd.isna(release_date):
                return pd.NaT

            periodo_texto = str(
                fila.get("Period", "")
            ).strip()

            # ===================================================
            # SIN PERIOD EXPLÍCITO
            # Ej.: Business Climate.
            # Se considera correspondiente al mes de publicación.
            # ===================================================

            if (
                not periodo_texto
                or periodo_texto.lower() == "nan"
            ):

                return release_date.to_period("M")


            # ===================================================
            # PERIODOS TRIMESTRALES
            # Q1 -> marzo
            # Q2 -> junio
            # Q3 -> septiembre
            # Q4 -> diciembre
            # ===================================================

            periodo_upper = periodo_texto.upper()

            if periodo_upper in {
                "Q1",
                "Q2",
                "Q3",
                "Q4",
            }:

                trimestre = int(
                    periodo_upper[1]
                )

                mes = trimestre * 3
                año = release_date.year

                # Ejemplo:
                # Q4 publicado en enero/febrero
                # pertenece al año anterior.
                if mes > release_date.month:
                    año -= 1

                return pd.Period(
                    year=año,
                    month=mes,
                    freq="M",
                )


            # ===================================================
            # PERIODOS MENSUALES
            # ===================================================

            mes_texto = (
                periodo_texto[:3]
                .lower()
            )

            mes = meses_periodo.get(
                mes_texto
            )

            if mes is None:
                return pd.NaT

            año = release_date.year

            if mes > release_date.month:
                año -= 1

            return pd.Period(
                year=año,
                month=mes,
                freq="M",
            )

        releases_indicador["Periodo"] = (
            releases_indicador.apply(
                obtener_periodo_release,
                axis=1,
            )
        )

        releases_indicador = (
            releases_indicador
            .dropna(
                subset=["Periodo"]
            )
            .sort_values("ReleaseDate")
            .drop_duplicates(
                subset=["Periodo"],
                keep="last",
            )
            .reset_index(drop=True)
        )

        if releases_indicador.empty:

            # ===================================================
            # FALLBACK SI EXISTE CONFIG EODHD PERO NO HAY MATCH
            #
            # Ejemplo actual: PPI MoM.
            # No eliminamos el indicador del Currency Score.
            # Conservamos la serie original de Dashboard_USD.
            # ===================================================

            serie_fallback = pd.DataFrame({
                "Fecha": dashboard["Fecha"],
                "FechaPeriodo": dashboard["Fecha"],
                "Valor": convertir_valores(
                    dashboard[columna]
                ),
                "Period": dashboard["_Periodo"].astype(str),
                "Previous": None,
                "Estimate": None,
                "FuenteFecha": "Fallback Dashboard",
            })
            serie_fallback = (
                serie_fallback
                .dropna(
                    subset=[
                        "Fecha",
                        "Valor",
                    ]
                )
                .sort_values("Fecha")
                .reset_index(drop=True)
            )

            if not serie_fallback.empty:
                series_por_indicador[nombre_score] = (
                    serie_fallback
                )

            continue

# ===================================================
# CONSERVAR TODA LA SERIE ORIGINAL DEL DASHBOARD
#
# EODHD solamente sustituye la fecha económica
# por la fecha real de publicación cuando existe
# matching para ese periodo.
# ===================================================

        datos_dashboard_completo = pd.DataFrame({
            "Fecha_original": dashboard["Fecha"],
            "Periodo": dashboard["_Periodo"],
            "Valor": convertir_valores(
                dashboard[columna]
            ),
        })

        datos_dashboard_completo = (
            datos_dashboard_completo
            .dropna(
                subset=[
                    "Fecha_original",
                    "Periodo",
                    "Valor",
                ]
            )
            .sort_values("Fecha_original")
            .drop_duplicates(
                subset=["Periodo"],
                keep="last",
            )
            .reset_index(drop=True)
        )

        if datos_dashboard_completo.empty:
            continue

        # ===================================================
        # PMI AUTOMÁTICOS:
        # AÑADIR PERIODOS NUEVOS PROCEDENTES DE EODHD
        # ===================================================

        indicadores_pmi_api = {
            "Manufacturing PMI",
            "Services PMI",
        }

        usar_pmi_eodhd = (
            nombre_score in indicadores_pmi_api
            and not es_proxy_release
        )


        if usar_pmi_eodhd:

            periodos_dashboard = set(
                datos_dashboard_completo["Periodo"]
                .dropna()
                .astype(str)
            )

            releases_nuevos = releases_indicador[
                ~releases_indicador["Periodo"]
                .astype(str)
                .isin(periodos_dashboard)
            ].copy()

            releases_nuevos["Actual_EODHD"] = convertir_valores(
                releases_nuevos["Actual"]
            )

            releases_nuevos = releases_nuevos.dropna(
                subset=[
                    "Periodo",
                    "ReleaseDate",
                    "Actual_EODHD",
                ]
            )

            if not releases_nuevos.empty:

                nuevos_dashboard = pd.DataFrame({
                    "Periodo": releases_nuevos["Periodo"],
                    "Fecha_original": releases_nuevos["ReleaseDate"],
                    "Valor": releases_nuevos["Actual_EODHD"],
                })

                datos_dashboard_completo = pd.concat(
                    [
                        datos_dashboard_completo,
                        nuevos_dashboard,
                    ],
                    ignore_index=True,
                )

                datos_dashboard_completo = (
                    datos_dashboard_completo
                    .drop_duplicates(
                        subset=["Periodo"],
                        keep="last",
                    )
                    .sort_values("Fecha_original")
                    .reset_index(drop=True)
                )

        # -----------------------------------------------
        # LEFT JOIN:
        # ningún valor del Dashboard desaparece
        # -----------------------------------------------


        serie = datos_dashboard_completo.merge(
            releases_indicador[
                [
                    "Periodo",
                    "ReleaseDate",
                    "Period",
                    "Actual",
                    "Previous",
                    "Estimate",
                    "Indicator",
                ]
            ],
            on="Periodo",
            how="left",
        )

        # ===================================================
        # PROXIES TEMPORALES:
        # usar únicamente ReleaseDate como reloj.
        # Nunca heredar Actual / Previous / Estimate
        # del indicador proxy.
        # ===================================================

        if es_proxy_release:
            serie["Actual"] = None
            serie["Previous"] = None
            serie["Estimate"] = None

        # ===================================================
        # PMI: USAR VALOR ACTUAL DE EODHD CUANDO ESTÉ DISPONIBLE
        # ===================================================

        indicadores_pmi_api = {
            "Manufacturing PMI",
            "Services PMI",
        }

        usar_valor_pmi_eodhd = (
            nombre_score in indicadores_pmi_api
            and not es_proxy_release
        )

        if usar_valor_pmi_eodhd:

            serie["Actual_EODHD"] = convertir_valores(
                serie["Actual"]
            )

            serie.loc[
                serie["Actual_EODHD"].notna(),
                "Valor",
            ] = serie.loc[
                serie["Actual_EODHD"].notna(),
                "Actual_EODHD",
            ]


        # -----------------------------------------------
        # FECHA EFECTIVA
        #
        # Si conocemos ReleaseDate:
        #     usamos fecha real de publicación.
        #
        # Si no:
        #     conservamos la fecha histórica original.
        # -----------------------------------------------

        serie["Fecha"] = serie[
            "ReleaseDate"
        ].fillna(
            serie["Fecha_original"]
        )

        serie["FuenteFecha"] = (
            "Fallback Dashboard"
        )

        if es_proxy_release:

            serie.loc[
                serie["ReleaseDate"].notna(),
                "FuenteFecha",
            ] = "EODHD Proxy ReleaseDate"

        else:

            serie.loc[
                serie["ReleaseDate"].notna(),
                "FuenteFecha",
            ] = "EODHD ReleaseDate"

        serie = (
            serie
            .dropna(
                subset=[
                    "Fecha",
                    "Valor",
                ]
            )
            .sort_values("Fecha")
            .reset_index(drop=True)
        )


        # -----------------------------------------------
        # Mantener Period incluso cuando no existe EODHD
        # -----------------------------------------------

        serie["Period"] = (
            serie["Period"]
            .fillna(
                serie["Periodo"]
                .astype(str)
            )
        )

        # ===================================================
        # FECHA DEL PERIODO ECONÓMICO
        # Solo para representación en la vista Indicador.
        # NO sustituye ReleaseDate para Currency Score.
        # ===================================================

        serie["FechaPeriodo"] = (
            serie["Periodo"]
            .dt.to_timestamp()
        )


        series_por_indicador[nombre_score] = (
            serie[
                [
                    "Fecha",
                    "FechaPeriodo",
                    "Valor",
                    "Period",
                    "Previous",
                    "Estimate",
                    "FuenteFecha",
                ]
            ].copy()
        )

    return series_por_indicador

def analizar_divisa_por_release(
    series_por_indicador,
    divisa,
    fecha_corte,
):

    resultados = {}

    fecha_corte = pd.to_datetime(
        fecha_corte
    )

    for nombre_indicador, datos in (
        series_por_indicador.items()
    ):

        datos_indicador = (
            datos[
                datos["Fecha"] <= fecha_corte
            ]
            .dropna(
                subset=[
                    "Fecha",
                    "Valor",
                ]
            )
            .sort_values("Fecha")
            .reset_index(drop=True)
        )

        if len(datos_indicador) < 2:
            continue

        try:

            resultado = analizar_indicador(
                datos_indicador["Fecha"],
                datos_indicador["Valor"],
                nombre_indicador,
                divisa,
            )

            if resultado is not None:
                resultados[
                    nombre_indicador
                ] = resultado

        except Exception:
            continue

    return resultados

@st.cache_data(ttl=60, show_spinner=False)
def calcular_historico_currency_score(
    currency,
    data_version,
    frecuencia="W",
    periodos=26,
    revision="release_v18",
):



    df_currency, _ = cargar_datos_mercado(
        tuple(MERCADOS[currency])
    )

    df_currency["Fecha"] = convertir_fechas(
        df_currency["DATE"]
    )

    df_currency = (
        df_currency
        .dropna(subset=["Fecha"])
        .sort_values("Fecha")
        .reset_index(drop=True)
    )
        
    if df_currency.empty:
        return pd.DataFrame(
            columns=[
                "Fecha",
                "Score",
                "Coverage",
            ]
        )

    indicadores_currency = obtener_indicadores(
        df_currency
    )
    

    series_release = construir_df_currency_por_release(
        df_currency,
        currency,
        indicadores_currency,
    )


    usar_release_dates = (
        str(currency).strip().upper() in RELEASE_AWARE_CURRENCIES
        and bool(series_release)
    )

    if usar_release_dates:

        fechas_disponibles = []

        for datos_indicador in series_release.values():

            if datos_indicador.empty:
                continue

            fechas_disponibles.append(
                datos_indicador["Fecha"].max()
            )

        if fechas_disponibles:
            fecha_final = max(
                fechas_disponibles
            )
        else:
            usar_release_dates = False
            fecha_final = df_currency["Fecha"].max()

    else:
        fecha_final = df_currency["Fecha"].max()

    if frecuencia == "W":

        fechas_corte = pd.date_range(
            end=fecha_final,
            periods=periodos,
            freq="W",
        )

    elif frecuencia == "M":

        fechas_corte = pd.date_range(
            end=fecha_final,
            periods=periodos,
            freq="ME",
        )

    else:
        raise ValueError(
            "La frecuencia debe ser 'W' o 'M'."
        )

    # ===================================================
    # ASEGURAR QUE LA ÚLTIMA FECHA REAL ESTÁ INCLUIDA
    # ===================================================

    fechas_corte = list(fechas_corte)

    if (
        not fechas_corte
        or fechas_corte[-1] != fecha_final
    ):
        fechas_corte.append(fecha_final)

    fechas_corte = sorted(
        set(fechas_corte)
    )

    historico = []

    for fecha_corte in fechas_corte:

        if usar_release_dates:

            resultados = analizar_divisa_por_release(
                series_release,
                currency,
                fecha_corte,
            )

        else:

            resultados = analizar_divisa_completa(
                df_currency,
                currency,
                indicadores_currency,
                fecha_corte=fecha_corte,
            )

        resultado_score = calcular_currency_score(
            currency,
            resultados,
        )

        score_historico = resultado_score.get(
            "score"
        )

        coverage_historica = resultado_score.get(
            "coverage",
            0,
        )

        if score_historico is None:
            continue

        historico.append({
            "Fecha": fecha_corte,
            "Score": float(score_historico),
            "Coverage": float(coverage_historica),
        })

    historico_df = pd.DataFrame(
        historico
    )

    if historico_df.empty:
        return historico_df

    historico_df = (
        historico_df
        .sort_values("Fecha")
        .drop_duplicates(
            subset=["Fecha"],
            keep="last",
        )
        .reset_index(drop=True)
    )

    return historico_df

def calcular_drivers_currency_score(
    resultados_actuales,
    resultados_anteriores,
):
    drivers = []

    if not resultados_actuales or not resultados_anteriores:
        return drivers

    familias = set(resultados_actuales.keys()) | set(
        resultados_anteriores.keys()
    )

    for familia in familias:

        actual = resultados_actuales.get(familia, {})
        anterior = resultados_anteriores.get(familia, {})

        indicadores_actuales = actual.get("indicators", {})
        indicadores_anteriores = anterior.get("indicators", {})

        indicadores = set(indicadores_actuales.keys()) | set(
            indicadores_anteriores.keys()
        )

        for indicador in indicadores:

            dato_actual = indicadores_actuales.get(indicador, {})
            dato_anterior = indicadores_anteriores.get(indicador, {})

            score_actual = dato_actual.get("score")
            score_anterior = dato_anterior.get("score")

            if score_actual is None or score_anterior is None:
                continue

            cambio_score = score_actual - score_anterior

            if abs(cambio_score) < 0.01:
                continue

            peso_familia = actual.get(
                "peso_normalizado",
                actual.get("peso_original", 0),
            )

            peso_indicador = dato_actual.get(
                "peso_normalizado",
                dato_actual.get("peso_original", 0),
            )

            impacto_estimado = (
                cambio_score
                * peso_indicador
                * peso_familia
            )

            drivers.append({
                "Familia": familia,
                "Indicador": indicador,
                "Score anterior": round(score_anterior, 1),
                "Score actual": round(score_actual, 1),
                "Cambio indicador": round(cambio_score, 1),
                "Impacto estimado": round(impacto_estimado, 2),
            })

    drivers = sorted(
        drivers,
        key=lambda x: abs(x["Impacto estimado"]),
        reverse=True,
    )

    return drivers

@st.cache_data(ttl=60, show_spinner=False)
def calcular_drivers_historicos_currency_score(
    currency,
    historico_score,
):

    if historico_score is None or historico_score.empty:
        return []

    historico = (
        historico_score
        .copy()
        .sort_values("Fecha")
        .reset_index(drop=True)
    )

    if len(historico) < 2:
        return []

    # ===================================================
    # CARGAR DATOS UNA SOLA VEZ
    # ===================================================

    df_currency, _ = cargar_datos_mercado(
        tuple(MERCADOS[currency])
    )

    df_currency["Fecha"] = convertir_fechas(
        df_currency["DATE"]
    )

    df_currency = (
        df_currency
        .dropna(subset=["Fecha"])
        .sort_values("Fecha")
        .reset_index(drop=True)
    )

    indicadores_currency = obtener_indicadores(
        df_currency
    )

    if not indicadores_currency:
        return []

    currency_normalizada = (
        str(currency).strip().upper()
    )

    # ===================================================
    # PARA USD USAR EXACTAMENTE EL MISMO RELOJ
    # QUE EL HISTÓRICO DEL CURRENCY SCORE
    # ===================================================

    series_release = {}

    if currency_normalizada in RELEASE_AWARE_CURRENCIES:

        series_release = construir_df_currency_por_release(
            df_currency,
            currency,
            indicadores_currency,
        )


    macro_releases = cargar_macro_releases()

    cambios_historicos = []

    # ===================================================
    # COMPARAR CADA PUNTO CON EL ANTERIOR
    # ===================================================

    for i in range(1, len(historico)):

        fila_anterior = historico.iloc[i - 1]
        fila_actual = historico.iloc[i]

        fecha_anterior = pd.to_datetime(
            fila_anterior["Fecha"]
        )

        fecha_actual = pd.to_datetime(
            fila_actual["Fecha"]
        )

        score_anterior = float(
            fila_anterior["Score"]
        )

        score_actual = float(
            fila_actual["Score"]
        )

        cambio_score = (
            score_actual - score_anterior
        )

        # -----------------------------------------------
        # Sin cambio
        # -----------------------------------------------

        if abs(cambio_score) < 0.01:

            cambios_historicos.append({
                "Fecha": fecha_actual,
                "Fecha anterior": fecha_anterior,
                "Score anterior": score_anterior,
                "Score actual": score_actual,
                "Cambio": 0.0,
                "Drivers": [],
            })

            continue

        # ===================================================
        # RECONSTRUIR LOS DOS ESTADOS
        # ===================================================

        if (
            currency_normalizada in RELEASE_AWARE_CURRENCIES
            and series_release
        ):

            resultados_anteriores = analizar_divisa_por_release(
                series_release,
                currency,
                fecha_anterior,
            )

            resultados_actuales = analizar_divisa_por_release(
                series_release,
                currency,
                fecha_actual,
            )

        else:

            resultados_anteriores = analizar_divisa_completa(
                df_currency,
                currency,
                indicadores_currency,
                fecha_corte=fecha_anterior,
            )

            resultados_actuales = analizar_divisa_completa(
                df_currency,
                currency,
                indicadores_currency,
                fecha_corte=fecha_actual,
            )

        # ===================================================
        # CURRENCY SCORE DE AMBOS ESTADOS
        # ===================================================

        currency_score_anterior = calcular_currency_score(
            currency,
            resultados_anteriores,
        )

        currency_score_actual = calcular_currency_score(
            currency,
            resultados_actuales,
        )

        familias_anteriores = (
            currency_score_anterior.get(
                "families",
                {},
            )
        )

        familias_actuales = (
            currency_score_actual.get(
                "families",
                {},
            )
        )

        # ===================================================
        # DRIVERS BRUTOS
        # ===================================================

        drivers = calcular_drivers_currency_score(
            familias_actuales,
            familias_anteriores,
        )

        # ===================================================
        # PUBLICACIONES REALES DEL INTERVALO
        # ===================================================

        releases_intervalo = obtener_releases_intervalo(
            macro_releases,
            currency,
            fecha_anterior,
            fecha_actual,
        )

        # ===================================================
        # CONSERVAR SOLO INDICADORES REALMENTE PUBLICADOS
        # ===================================================

        drivers = filtrar_drivers_por_releases(
            drivers,
            releases_intervalo,
        )

        # ===================================================
        # GUARDAR ESTE INTERVALO
        # ===================================================

        cambios_historicos.append({
            "Fecha": fecha_actual,
            "Fecha anterior": fecha_anterior,
            "Score anterior": score_anterior,
            "Score actual": score_actual,
            "Cambio": round(
                cambio_score,
                2,
            ),
            "Drivers": drivers,
        })

    return cambios_historicos

@st.cache_data(ttl=60, show_spinner=False)
def calcular_drivers_ultimo_cambio(
    currency,
    historico_score,
):

    if historico_score is None or historico_score.empty:
        return None

    historico = (
        historico_score
        .copy()
        .sort_values("Fecha")
        .reset_index(drop=True)
    )

    if len(historico) < 2:
        return None

    ultima_fila = historico.iloc[-1]

    fecha_actual = ultima_fila["Fecha"]
    score_actual = float(ultima_fila["Score"])

    # Buscar hacia atrás el último punto
    # donde el Currency Score era diferente.
    historico_anterior = historico.iloc[:-1].copy()

    historico_anterior = historico_anterior[
        abs(
            historico_anterior["Score"]
            - score_actual
        ) > 0.01
    ]

    if historico_anterior.empty:
        return None

    fila_anterior = historico_anterior.iloc[-1]

    fecha_anterior = fila_anterior["Fecha"]
    score_anterior = float(
        fila_anterior["Score"]
    )

    # ===================================================
    # CARGAR DATOS DE LA DIVISA
    # ===================================================

    df_currency, _ = cargar_datos_mercado(
        tuple(MERCADOS[currency])
    )

    df_currency["Fecha"] = convertir_fechas(
        df_currency["DATE"]
    )

    df_currency = (
        df_currency
        .dropna(subset=["Fecha"])
        .sort_values("Fecha")
        .reset_index(drop=True)
    )

    indicadores_currency = obtener_indicadores(
        df_currency
    )

    # ===================================================
    # RECONSTRUIR LOS DOS ESTADOS
    # ===================================================

    resultados_anteriores = analizar_divisa_completa(
        df_currency,
        currency,
        indicadores_currency,
        fecha_corte=fecha_anterior,
    )

    resultados_actuales = analizar_divisa_completa(
        df_currency,
        currency,
        indicadores_currency,
        fecha_corte=fecha_actual,
    )

    currency_score_anterior = calcular_currency_score(
        currency,
        resultados_anteriores,
    )

    currency_score_actual = calcular_currency_score(
        currency,
        resultados_actuales,
    )

    familias_anteriores = (
        currency_score_anterior.get(
            "families",
            {},
        )
    )

    familias_actuales = (
        currency_score_actual.get(
            "families",
            {},
        )
    )

    drivers = calcular_drivers_currency_score(
        familias_actuales,
        familias_anteriores,
    )

    return {
        "fecha_anterior": fecha_anterior,
        "fecha_actual": fecha_actual,
        "score_anterior": score_anterior,
        "score_actual": score_actual,
        "cambio_score": round(
            score_actual - score_anterior,
            2,
        ),
        "drivers": drivers,
    }

@st.cache_data(ttl=60, show_spinner=False)
def calcular_ranking_divisas():

    ranking = []

    for currency, hojas in MERCADOS.items():

        try:
            df_currency, _ = cargar_datos_mercado(
                tuple(hojas)
            )

            df_currency["Fecha"] = convertir_fechas(
                df_currency["DATE"]
            )

            df_currency = (
                df_currency
                .dropna(subset=["Fecha"])
                .sort_values("Fecha")
                .reset_index(drop=True)
            )

            if df_currency.empty:
                continue

            indicadores_currency = obtener_indicadores(
                df_currency
            )

            if not indicadores_currency:
                continue

            resultados_currency = analizar_divisa_completa(
                df_currency,
                currency,
                indicadores_currency,
            )

            resultado_score = calcular_currency_score(
                currency,
                resultados_currency,
            )

            score = resultado_score.get("score")

            if score is None:
                continue

            ranking.append({
                "currency": currency,
                "score": float(score),
                "rating": clasificar_currency_score(score),
                "coverage": float(
                    resultado_score.get(
                        "coverage",
                        0
                    )
                ),
            })

        except Exception as error:
            ranking.append({
                "currency": currency,
                "score": None,
                "rating": "Error",
                "coverage": 0.0,
                "error": str(error),
            })

    ranking_validos = [
        item
        for item in ranking
        if item["score"] is not None
    ]

    ranking_validos.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    ranking_errores = [
        item
        for item in ranking
        if item["score"] is None
    ]

    return ranking_validos + ranking_errores



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

def crear_tarjeta_inteligencia(titulo, valor, nota=""):
    return f"""
        <div class="metric-card">
            <div class="metric-label">{titulo}</div>
            <div class="metric-value">{valor}</div>
            <div class="metric-note">{nota}</div>
        </div>
    """


def crear_tarjeta_interpretacion(titulo, contenido):
    return f"""
        <div class="macro-analysis-card">
            <div class="macro-analysis-title">{titulo}</div>
            <div class="macro-analysis-text">{contenido}</div>
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
        "household spending",
        "earnings"
    ]

    # Los PMI son índices, por tanto no llevan %.
    return "%" if any(
        palabra in nombre
        for palabra in palabras_porcentaje
    ) else ""

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
        "household spending",
        "earnings"
    ]

    return "%" if any(
        palabra in nombre
        for palabra in palabras_porcentaje
    ) else ""


# ===================================================
# FX LIVE DRIVERS — NEWSAPI
# ===================================================

@st.cache_data(ttl=1, show_spinner=False)
def cargar_live_drivers_newsapi(divisa, modo="Todos"):
    """
    MVP inicial:
    obtiene titulares recientes desde NewsAPI.ai
    para USD y CHF.
    """

    try:
        api_key = st.secrets["newsapi"]["api_key"]

    except Exception:
        return {
            "ok": False,
            "error": "Falta configurar NewsAPI.ai en Streamlit Secrets.",
            "articles": [],
        }

    divisa = str(divisa).strip().upper()
    modo = str(modo or "Todos").strip()

    queries = {

        "USD": [
            "dollar",
        ],

        "EUR": [
            "euro",
        ],

        "GBP": [
            "Bank of England",
            "BOE",
            "Andrew Bailey",
            "UK Treasury",
            "pound sterling",
            "GBP",
        ],

        "JPY": [
            "Bank of Japan",
            "BOJ",
            "Kazuo Ueda",
            "Japanese yen",
            "Japan Ministry of Finance",
            "currency intervention",
            "JGB",
        ],

        "CHF": [
            "Swiss National Bank",
            "SNB",
            "Martin Schlegel",
            "Petra Tschudin",
            "Swiss franc",
        ],

        "AUD": [
            "Reserve Bank of Australia",
            "RBA",
            "Michele Bullock",
            "Australian dollar",
            "AUD",
        ],

        "NZD": [
            "Reserve Bank of New Zealand",
            "RBNZ",
            "New Zealand dollar",
            "NZD",
        ],

        "CAD": [
            "Bank of Canada",
            "BOC",
            "Tiff Macklem",
            "Canadian dollar",
            "CAD",
        ],
    }

    queries_bancos_centrales = {

        "USD": [
            "Federal Reserve",
            "Fed",
            "FOMC",
            "Fed Chair",
            "Fed Governor",
            "Fed President",
            "Kevin Warsh",
        ],

        "EUR": [
            "European Central Bank",
            "ECB",
            "ECB President",
            "ECB Governing Council",
        ],

        "GBP": [
            "Bank of England",
            "BoE",
            "Monetary Policy Committee",
            "MPC",
        ],

        "JPY": [
            "Bank of Japan",
            "BoJ",
            "Kazuo Ueda",
        ],

        "CHF": [
            "Swiss National Bank",
            "SNB",
            "Martin Schlegel",
            "Petra Tschudin",
        ],

        "AUD": [
            "Reserve Bank of Australia",
            "RBA",
            "Michele Bullock",
        ],

        "NZD": [
            "Reserve Bank of New Zealand",
            "RBNZ",
        ],

        "CAD": [
            "Bank of Canada",
            "Tiff Macklem",
        ],
    }   

    queries_miembros_bancos_centrales = {

        "USD": [
            "Austan Goolsbee",
            "Christopher Waller",
            "Susan Collins",
            "Beth Hammack",
            "Jeffrey Schmid",
            "Neel Kashkari",
            "John Williams",
            "Lorie Logan",
            "Michelle Bowman",
            "Lisa Cook",
            "Philip Jefferson",
        ],

        "EUR": [
            "Christine Lagarde",
            "Philip Lane",
            "Isabel Schnabel",
            "Joachim Nagel",
            "Martins Kazaks",
            "Olli Rehn",
            "Pierre Wunsch",
            "Dimitar Radev",
            "Primoz Dolenc",
        ],

        "GBP": [
            "Andrew Bailey",
            "Sarah Breeden",
            "Swati Dhingra",
            "Megan Greene",
            "Clare Lombardelli",
            "Catherine Mann",
            "Huw Pill",
            "Dave Ramsden",
            "Alan Taylor",
        ],

        "JPY": [
            "Kazuo Ueda",
            "Shinichi Uchida",
            "Ryozo Himino",
            "Hajime Takata",
            "Naoki Tamura",
        ],

        "CHF": [
            "Martin Schlegel",
            "Antoine Martin",
            "Petra Tschudin",
        ],

        "AUD": [
            "Michele Bullock",
            "Andrew Hauser",
            "Renee Fry-McKibbin",
        ],

        "NZD": [
            "Anna Breman",
            "Karen Silk",
            "Paul Conway",
            "Carl Hansen",
        ],

        "CAD": [
            "Tiff Macklem",
            "Carolyn Rogers",
            "Toni Gravelle",
            "Marc-Andre Gosselin",
            "Nicolas Vincent",
            "Michelle Alexopoulos",
        ],
    }

    if modo == "Bancos centrales":
        query_activa = queries_bancos_centrales.get(divisa, [])
    else:
        query_activa = queries.get(divisa, [])

    if divisa not in queries:
        return {
            "ok": True,
            "error": None,
            "articles": [],
        }

    payload = {
        "action": "getArticles",

        # NewsAPI.ai acepta varios keywords como lista.
        # "or" significa que basta con que coincida uno.
        "keyword": query_activa,
        "keywordOper": "or",

        # Buscar tanto en título como en cuerpo
        "keywordLoc": "title",

        "articlesPage": 1,
        "articlesCount": 50,
        "articlesSortBy": "date",
        "articlesSortByAsc": False,

        "resultType": "articles",
        "dataType": ["news"],

        # Últimos 7 días
        "forceMaxDataTimeWindow": 7,

        "apiKey": api_key,
    }

    try:

        # ===================================================
        # CONSULTA 1 — BÚSQUEDA GENERAL
        # ===================================================

        response = requests.post(
            "https://eventregistry.org/api/v1/article/getArticles",
            json=payload,
            timeout=20,
        )

        response.raise_for_status()

        data = response.json()

        articles = (
            data
            .get("articles", {})
            .get("results", [])
        )


        # ===================================================
        # CONSULTA 2 — MIEMBROS DE BANCOS CENTRALES
        # Solo para el modo "Bancos centrales"
        # ===================================================

        if modo == "Bancos centrales":

            query_miembros = (
                queries_miembros_bancos_centrales
                .get(divisa, [])
            )

            if query_miembros:

                payload_miembros = payload.copy()

                payload_miembros["keyword"] = query_miembros

                response_miembros = requests.post(
                    "https://eventregistry.org/api/v1/article/getArticles",
                    json=payload_miembros,
                    timeout=20,
                )

                response_miembros.raise_for_status()

                data_miembros = response_miembros.json()

                articles_miembros = (
                    data_miembros
                    .get("articles", {})
                    .get("results", [])
                )

                print(
                    f"[NEWSAPI {divisa}] "
                    f"general={len(articles)} | "
                    f"miembros={len(articles_miembros)}"
                )

                articles.extend(articles_miembros)


        # ===================================================
        # ELIMINAR DUPLICADOS ENTRE AMBAS CONSULTAS
        # ===================================================

        articles_unicos = []
        vistos = set()

        for article in articles:

            clave = (
                str(article.get("uri", "")).strip()
                or str(article.get("url", "")).strip()
                or str(article.get("title", "")).strip().lower()
            )

            if not clave:
                continue

            if clave in vistos:
                continue

            vistos.add(clave)

            articles_unicos.append(
                article
            )


        return {
            "ok": True,
            "error": None,
            "articles": articles_unicos,
        }

    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
            "articles": [],
        }
    
@st.cache_data(ttl=60, show_spinner=False)
def cargar_live_drivers_finnhub(divisa):

    try:
        api_key = st.secrets["finnhub"]["api_key"]

    except Exception:
        return {
            "ok": False,
            "error": "Falta configurar Finnhub en Streamlit Secrets.",
            "articles": [],
        }

    divisa = str(divisa or "").strip().upper()

    try:
        response = requests.get(
            "https://finnhub.io/api/v1/news",
            params={
                "category": "general",
                "token": api_key,
            },
            timeout=20,
        )

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, list):
            data = []

        articles = []

        for item in data:

            titulo = str(
                item.get("headline")
                or ""
            ).strip()

            if not titulo:
                continue

            articles.append({
                "title": titulo,
                "body": item.get("summary") or "",
                "summary": item.get("summary") or "",
                "url": item.get("url") or "",
                "source": item.get("source") or "Finnhub",
                "publishedAt": item.get("datetime"),
                "_provider": "Finnhub",
            })

        return {
            "ok": True,
            "error": None,
            "articles": articles,
        }

    except Exception as error:
        return {
            "ok": False,
            "error": str(error),
            "articles": [],
        }

def filtrar_articulos_fx(articles, divisa):
    """
    Filtro estricto de relevancia para FX Live Drivers.

    Principios:
    1. La noticia debe tratar realmente sobre la divisa/economía.
    2. Debe existir un catalizador macro/monetario/fiscal/geopolítico
       relevante para FX.
    3. Las siglas ambiguas (RBA, CAD, etc.) no son suficientes solas.
    4. El titular tiene prioridad.
    5. El body sirve solamente como confirmación secundaria.
    """

    import re

    divisa = str(divisa or "").strip().upper()

    # ============================================================
    # FUNCIONES AUXILIARES
    # ============================================================

    def contiene(texto, terminos):
        return any(
            termino in texto
            for termino in terminos
        )

    def contiene_palabra(texto, palabra):
        return bool(
            re.search(
                rf"(?<![a-z]){re.escape(palabra.lower())}(?![a-z])",
                texto,
            )
        )

    def contiene_alguna_palabra(texto, palabras):
        return any(
            contiene_palabra(texto, palabra)
            for palabra in palabras
        )

    # ============================================================
    # 1. REFERENCIAS FX / MACRO POR DIVISA
    # ============================================================

    referencias_fuertes = {

        "USD": [
            "federal reserve",
            "fomc",
            "fed chair",
            "fed governor",
            "fed president",
            "u.s. treasury",
            "us treasury",
            "u.s. dollar",
            "us dollar",
            "dollar index",
            "dxy",
            "usd/",
            "/usd",
            "scott bessent",
        ],

        "EUR": [
            "european central bank",
            "ecb",
            "eurozone",
            "euro area",
            "euro-area",
            "eur/usd",
            "eurusd",
            "eur/gbp",
            "eurgbp",
            "christine lagarde",
        ],

        "GBP": [
            "bank of england",
            "boe",
            "monetary policy committee",
            "pound sterling",
            "british pound",
            "sterling",
            "gbp/usd",
            "gbpusd",
            "eur/gbp",
            "eurgbp",
            "andrew bailey",
            "uk treasury",
        ],

        "JPY": [
            "bank of japan",
            "boj",
            "japanese yen",
            "yen",
            "jpy/",
            "/jpy",
            "kazuo ueda",
            "japan ministry of finance",
            "japanese ministry of finance",
            "jgb",
            "japanese government bond",
        ],

        "CHF": [
            "swiss national bank",
            "snb",
            "swiss franc",
            "chf/",
            "/chf",
            "martin schlegel",
            "petra tschudin",
        ],

        "AUD": [
            "reserve bank of australia",
            "australian dollar",
            "aussie dollar",
            "aud/usd",
            "audusd",
            "aud/jpy",
            "audjpy",
            "michele bullock",
        ],

        "NZD": [
            "reserve bank of new zealand",
            "rbnz",
            "new zealand dollar",
            "kiwi dollar",
            "nzd/usd",
            "nzdusd",
            "nzd/",
            "/nzd",
        ],

        "CAD": [
            "bank of canada",
            "canadian dollar",
            "usd/cad",
            "usdcad",
            "cad/",
            "/cad",
            "tiff macklem",
        ],
    }

    # ============================================================
    # 2. SIGLAS AMBIGUAS
    # ============================================================

    # Estas NO son suficientes por sí solas.
    # Necesitan contexto macro adicional.

    siglas_ambiguas = {
        "AUD": ["rba", "aud"],
        "CAD": ["cad", "boc"],
        "EUR": ["eur"],
        "GBP": ["gbp"],
        "JPY": ["jpy"],
        "CHF": ["chf"],
        "NZD": ["nzd"],
        "USD": ["usd"],
    }

    # ============================================================
    # 3. TÉRMINOS MACRO / MONETARIOS RELEVANTES
    # ============================================================

    monetary_terms = [
        "central bank",
        "interest rate",
        "interest rates",
        "rate hike",
        "rate hikes",
        "rate cut",
        "rate cuts",
        "rate rise",
        "rate increase",
        "rate decision",
        "policy rate",
        "monetary policy",
        "hawkish",
        "dovish",
        "tightening",
        "easing",
        "quantitative tightening",
        "quantitative easing",
        "yield curve",
        "terminal rate",
        "neutral rate",
        "rate path",
        "rate outlook",
    ]

    inflation_terms = [
        "inflation",
        "cpi",
        "core cpi",
        "consumer prices",
        "price pressures",
        "inflation expectations",
        "wage inflation",
        "price growth",
        "disinflation",
    ]

    activity_terms = [
        "gdp",
        "economic growth",
        "growth outlook",
        "recession",
        "economic slowdown",
        "economic contraction",
        "economic expansion",
        "pmi",
        "manufacturing",
        "services activity",
        "industrial production",
        "retail sales",
        "consumer spending",
        "household spending",
        "employment",
        "unemployment",
        "wages",
        "labor market",
        "labour market",
    ]

    fiscal_terms = [
        "fiscal policy",
        "government spending",
        "budget",
        "budget deficit",
        "fiscal deficit",
        "tax cuts",
        "tax increase",
        "tax rises",
        "public spending",
        "debt issuance",
        "government debt",
        "treasury issuance",
    ]

    trade_terms = [
        "tariff",
        "tariffs",
        "trade war",
        "trade talks",
        "trade dispute",
        "trade deal",
        "trade agreement",
        "trade restrictions",
        "import duties",
        "export restrictions",
        "retaliatory tariffs",
    ]

    bond_terms = [
        "bond yield",
        "bond yields",
        "treasury yield",
        "treasury yields",
        "government bond",
        "government bonds",
        "jgb",
        "gilts",
        "bund yield",
        "bund yields",
        "yield surge",
        "yields rise",
        "yields fall",
        "bond selloff",
        "bond rally",
    ]

    fx_terms = [
        "currency intervention",
        "fx intervention",
        "foreign exchange intervention",
        "currency market",
        "foreign exchange market",
        "exchange rate",
        "currency weakness",
        "currency strength",
        "currency depreciation",
        "currency appreciation",
    ]

    geopolitical_terms = [
        "sanctions",
        "war",
        "military",
        "missile",
        "attack",
        "strike",
        "ceasefire",
        "invasion",
        "conflict",
        "escalation",
        "nuclear",
        "blockade",
        "iran",
        "israel",
        "russia",
        "ukraine",
        "china",
        "taiwan",
    ]

    catalyst_terms = (
        monetary_terms
        + inflation_terms
        + activity_terms
        + fiscal_terms
        + trade_terms
        + bond_terms
        + fx_terms
        + geopolitical_terms
    )

    # ============================================================
    # 4. MOVIMIENTOS DE DIVISA
    # ============================================================

    currency_movement_terms = [
        "rises",
        "rise",
        "gains",
        "gain",
        "advances",
        "strengthens",
        "firms",
        "higher",
        "jumps",
        "surges",
        "rallies",
        "falls",
        "fall",
        "drops",
        "declines",
        "retreats",
        "weakens",
        "slides",
        "slips",
        "lower",
        "plunges",
    ]

    # ============================================================
    # 5. RUIDO DURO
    # ============================================================

    technical_terms = [
        "rsi",
        "overbought",
        "oversold",
        "moving average",
        "support level",
        "resistance level",
        "technical analysis",
        "technical outlook",
        "chart pattern",
        "fibonacci",
        "price prediction",
        "price forecast",
        "bulls target",
        "bears target",
    ]

    irrelevant_terms = [
        "football",
        "soccer",
        "real madrid",
        "lottery",
        "jackpot",
        "casino",
        "gaming",
        "playstation",
        "xbox",
        "murder",
        "robbery",
        "stolen",
        "theft",
        "criminal",
        "fraud",
        "recipe",
        "restaurant",
        "supermarket",
        "parmigiano",
        "cheese",
        "medical centre",
        "medical center",
        "real estate listing",
        "property listing",
        "jogging track",
        "jogging",
    ]

    # ============================================================
    # 6. CONTEXTO NECESARIO PARA SIGLAS AMBIGUAS
    # ============================================================

    contexto_macro_ambiguo = (
        monetary_terms
        + inflation_terms
        + activity_terms
        + fiscal_terms
        + trade_terms
        + bond_terms
        + fx_terms
        + [
            "australia",
            "australian",
            "canada",
            "canadian",
            "eurozone",
            "euro area",
            "japan",
            "japanese",
            "switzerland",
            "swiss",
            "new zealand",
            "britain",
            "british",
            "united kingdom",
            "united states",
        ]
    )

    # ============================================================
    # 7. FILTRADO
    # ============================================================

    relevant = []

    for article in articles:

        title = str(
            article.get("title")
            or ""
        ).strip().lower()

        body = str(
            article.get("body")
            or article.get("summary")
            or ""
        ).strip().lower()

        if not title:
            continue

        texto_completo = f"{title} {body}"

        # --------------------------------------------------------
        # A. RUIDO CLARO
        # --------------------------------------------------------

        if contiene(title, technical_terms):
            continue

        if contiene(title, irrelevant_terms):
            continue

        # --------------------------------------------------------
        # B. REFERENCIA FUERTE A LA DIVISA
        # --------------------------------------------------------

        referencia_fuerte = contiene(
            title,
            referencias_fuertes.get(divisa, []),
        )

        # --------------------------------------------------------
        # C. SIGLA AMBIGUA
        # --------------------------------------------------------

        referencia_ambigua = contiene_alguna_palabra(
            title,
            siglas_ambiguas.get(divisa, []),
        )

        if referencia_ambigua and not referencia_fuerte:

            contexto_valido = contiene(
                title,
                contexto_macro_ambiguo,
            )

            if not contexto_valido:
                continue

        # --------------------------------------------------------
        # D. CASO ESPECIAL AUD / RBA
        # --------------------------------------------------------

        if divisa == "AUD" and contiene_palabra(title, "rba"):

            contexto_rba_real = contiene(
                title,
                [
                    "reserve bank",
                    "australia",
                    "australian",
                    "interest rate",
                    "rate hike",
                    "rate cut",
                    "monetary policy",
                    "inflation",
                    "cpi",
                    "bullock",
                    "minutes",
                    "board members",
                    "cash rate",
                ],
            )

            if not contexto_rba_real:
                continue

        # --------------------------------------------------------
        # E. CASO ESPECIAL EUR
        # --------------------------------------------------------

        if divisa == "EUR":

            contexto_eur_fuerte = contiene(
                title,
                [
                    "european central bank",
                    "ecb",
                    "eurozone",
                    "euro area",
                    "euro-area",
                    "eur/usd",
                    "eurusd",
                    "eur/gbp",
                    "eurgbp",
                    "euro rises",
                    "euro falls",
                    "euro gains",
                    "euro weakens",
                    "euro strengthens",
                    "euro slides",
                    "euro rallies",
                    "euro retreats",
                    "euro edges",
                    "euro holds",
                    "euro climbs",
                    "euro drops",
                    "euro under pressure",
                ],
            )

            contexto_macro_eur = contiene(
                title,
                catalyst_terms,
            )

            # Si aparece "euro" pero no hay ni contexto FX fuerte
            # ni catalizador macro, se descarta.
            if (
                "euro" in title
                and not contexto_eur_fuerte
                and not contexto_macro_eur
            ):
                continue

        # --------------------------------------------------------
        # F. CASO ESPECIAL CAD
        # --------------------------------------------------------

        if divisa == "CAD":

            if (
                "boc aviation" in title
                or "boc kenya" in title
            ):
                continue

            cantidad_cad = bool(
                re.search(
                    r"\bcad\s?\$?\s*\d",
                    title,
                )
            )

            if cantidad_cad and not contiene(
                title,
                [
                    "bank of canada",
                    "canadian dollar",
                    "usd/cad",
                    "usdcad",
                ],
            ):
                continue

        # --------------------------------------------------------
        # G. CASO ESPECIAL USD
        # --------------------------------------------------------

        if divisa == "USD":

            cantidad_dolares = bool(
                re.search(
                    r"(?:\$|usd\s*)\d[\d.,]*",
                    title,
                )
            )

            contexto_usd_real = contiene(
                title,
                [
                    "federal reserve",
                    "fomc",
                    "u.s. treasury",
                    "us treasury",
                    "us dollar",
                    "u.s. dollar",
                    "usd/",
                    "/usd",
                    "dollar rises",
                    "dollar falls",
                    "dollar gains",
                    "dollar weakens",
                    "dollar strengthens",
                ],
            )

            if cantidad_dolares and not contexto_usd_real:
                continue

        # --------------------------------------------------------
        # H. DEBE EXISTIR REFERENCIA REAL
        # --------------------------------------------------------

        if not (
            referencia_fuerte
            or referencia_ambigua
        ):
            continue

        # --------------------------------------------------------
        # I. CATALIZADOR MACRO
        # --------------------------------------------------------

        catalyst_in_title = contiene(
            title,
            catalyst_terms,
        )

        currency_move_in_title = contiene(
            title,
            currency_movement_terms,
        )

        catalyst_in_body = contiene(
            body,
            catalyst_terms,
        )

        # --------------------------------------------------------
        # J. DECISIÓN
        # --------------------------------------------------------

        # Mejor caso:
        # divisa + catalizador explícito en titular.
        if catalyst_in_title:
            relevant.append(article)
            continue

        # Segundo caso:
        # movimiento explícito de la divisa +
        # cuerpo que confirma un catalizador macro.
        if (
            currency_move_in_title
            and catalyst_in_body
        ):
            relevant.append(article)
            continue

        # Todo lo demás se descarta.

    return relevant


def filtrar_bancos_centrales(articles, divisa):
    """
    Filtro estricto para el modo "Bancos centrales".

    Incluye únicamente noticias donde exista una comunicación,
    decisión o señal REAL procedente del banco central o de uno
    de sus responsables.

    Excluye:
    - expectativas del mercado
    - probabilidades de subidas/bajadas
    - análisis de bancos comerciales
    - forecasts de analistas
    - exmiembros
    - regulación bancaria
    - coincidencias falsas con siglas
    """

    divisa = str(divisa or "").strip().upper()

    # ===================================================
    # 1. IDENTIDAD DEL BANCO CENTRAL
    # ===================================================

    bancos = {

        "USD": [
            "federal reserve",
            "the fed",
            "fomc",
        ],

        "EUR": [
            "european central bank",
            "ecb",
            "bce",
        ],

        "GBP": [
            "bank of england",
            "boe",
            "monetary policy committee",
            "mpc",
        ],

        "JPY": [
            "bank of japan",
            "boj",
        ],

        "CHF": [
            "swiss national bank",
            "snb",
        ],

        "AUD": [
            "reserve bank of australia",
            "rba",
        ],

        "NZD": [
            "reserve bank of new zealand",
            "rbnz",
        ],

        "CAD": [
            "bank of canada",
        ],
    }

    # ===================================================
    # 2. MIEMBROS / RESPONSABLES CONOCIDOS
    # ===================================================
    #
    # No es necesario que esta lista sea exhaustiva.
    # Sirve para capturar titulares donde aparece el nombre
    # del responsable pero no el nombre completo del banco.
    #

    miembros = {

        # ===================================================
        # USD — FED / FOMC 2026
        # ===================================================
        "USD": [
            "kevin warsh",
            "john williams",
            "john c. williams",
            "michael barr",
            "michael s. barr",
            "michelle bowman",
            "michelle w. bowman",
            "lisa cook",
            "lisa d. cook",
            "philip jefferson",
            "philip n. jefferson",
            "christopher waller",
            "christopher j. waller",
            "jerome powell",
            "jerome h. powell",
            "beth hammack",
            "neel kashkari",
            "lorie logan",
            "anna paulson",

            # Aliases / otros responsables Fed
            "austan goolsbee",
            "goolsbee",
            "susan collins",
            "jeffrey schmid",
        ],

        # ===================================================
        # EUR — ECB
        # Miembros con comunicación monetaria frecuente
        # ===================================================
        "EUR": [
            "christine lagarde",
            "boris vujcic",
            "boris vujčić",
            "philip lane",
            "philip r. lane",
            "isabel schnabel",
            "piero cipollone",
            "frank elderson",
            "joachim nagel",
            "martins kazaks",
            "mārtiņš kazāks",
            "peter kazimir",
            "peter kažimír",
            "martin kocher",
            "gabriel makhlouf",
            "fabio panetta",
            "olli rehn",
            "gediminas simkus",
            "gediminas šimkus",
            "yannis stournaras",
            "pierre wunsch",
            "dimitar radev",
            "primoz dolenc",
            "primož dolenc",
            "jose luis escriva",
            "josé luis escrivá",
            "olaf sleijpen",
            "martin kocher",
            "kocher",
        ],

        # ===================================================
        # GBP — BANK OF ENGLAND MPC
        # ===================================================
        "GBP": [
            "andrew bailey",
            "sarah breeden",
            "swati dhingra",
            "megan greene",
            "clare lombardelli",
            "catherine mann",
            "catherine l mann",
            "huw pill",
            "dave ramsden",
            "alan taylor",
        ],

        # ===================================================
        # JPY — BOJ POLICY BOARD
        # ===================================================
        "JPY": [
            "kazuo ueda",
            "shinichi uchida",
            "ryozo himino",
            "hajime takata",
            "naoki tamura",
            "junko koeda",
            "kazuyuki masu",
            "toichiro asada",
            "ayano sato",
        ],

        # ===================================================
        # CHF — SNB GOVERNING BOARD
        # ===================================================
        "CHF": [
            "martin schlegel",
            "antoine martin",
            "petra tschudin",
        ],

        # ===================================================
        # AUD — RBA MONETARY POLICY BOARD
        # ===================================================
        "AUD": [
            "michele bullock",
            "andrew hauser",
            "marnie baker",
            "renee fry-mckibbin",
            "renée fry-mckibbin",
            "ian harper",
            "carolyn hewson",
            "bruce preston",
            "iain ross",
            "jenny wilkinson",
        ],

        # ===================================================
        # NZD — RBNZ MONETARY POLICY COMMITTEE
        # ===================================================
        "NZD": [
            "anna breman",
            "karen silk",
            "paul conway",
            "carl hansen",
            "prasanna gai",
            "hayley gourley",
        ],

        # ===================================================
        # CAD — BANK OF CANADA GOVERNING COUNCIL
        # ===================================================
        "CAD": [
            "tiff macklem",
            "carolyn rogers",
            "toni gravelle",
            "marc-andre gosselin",
            "marc-andré gosselin",
            "nicolas vincent",
            "michelle alexopoulos",
        ],
    }

    # ===================================================
    # 3. COMUNICACIÓN / ACCIÓN REAL
    # ===================================================

    comunicacion_directa = [

        # Declaraciones
        "says",
        "said",
        "warns",
        "warned",
        "signals",
        "signaled",
        "indicates",
        "indicated",
        "remarks",
        "comments",
        "commented",
        "speech",
        "speaks",
        "speaking",
        "interview",
        "testimony",
        "testifies",
        "sees",
        "see",
        "hints",
        "hinted",
        "backs",
        "backed",
        "reiterates",
        "reiterated",
        "maintains",
        "maintained",

        # Publicaciones oficiales
        "minutes",
        "meeting minutes",
        "statement",
        "policy statement",
        "press conference",
        "decision",
        "rate decision",
        "monetary policy decision",
        "monetary policy statement",

        # Acciones
        "holds rates",
        "keeps rates",
        "raises rates",
        "raised rates",
        "cuts rates",
        "cut rates",
        "leaves rates",
        "left rates",
        "votes",
        "voted",

        # Orientación
        "guidance",
        "outlook",
        "projects",
        "projection",
        "forecasts",
    ]

    # ===================================================
    # 4. CONTENIDO DE POLÍTICA MONETARIA
    # ===================================================

    politica_monetaria = [

        "interest rate",
        "interest rates",
        "policy rate",
        "cash rate",
        "bank rate",
        "fed funds",
        "federal funds",

        "rate hike",
        "rate hikes",
        "rate cut",
        "rate cuts",
        "tightening",
        "easing",

        "inflation",
        "price pressures",
        "price stability",

        "monetary policy",
        "policy stance",
        "restrictive",
        "accommodative",

        "balance sheet",
        "quantitative tightening",
        "quantitative easing",
        "bond purchases",

        "economic outlook",
        "growth outlook",
        "labor market",
        "labour market",

        "currency intervention",
        "foreign exchange intervention",
        "yen intervention",

        "hawkish",
        "dovish",
    ]

    # ===================================================
    # 5. EXPECTATIVAS DEL MERCADO — EXCLUIR
    # ===================================================

    expectativas_mercado = [

        "rate hike odds",
        "rate cut odds",
        "hike odds",
        "cut odds",

        "odds of a hike",
        "odds of a cut",

        "markets price",
        "market prices",
        "market pricing",
        "markets pricing",
        "priced in",
        "pricing in",

        "traders expect",
        "traders bet",
        "traders see",

        "investors expect",
        "investors see",

        "analysts expect",
        "analysts forecast",
        "economists expect",
        "economists forecast",
        "strategists expect",

        "according to analysts",
        "according to economists",

        "swap markets",
        "futures markets",
        "money markets",

        "probability of a hike",
        "probability of a cut",
        "chance of a hike",
        "chance of a cut",

        "hike bets",
        "cut bets",
        "hike prospects",
        "cut prospects",
        "hike expectations",
        "cut expectations",
        "hike case",
        "cut case",
        "expected to hike",
        "expected to cut",
        "expected hike",
        "expected cut",
        "likely to hike",
        "likely to cut",
        "should hike",
        "should cut",
        "price forecast",

        "experts say",
        "analysts say",
        "economists say",
        "strategists say",
        "preview:",
        "price forecast",
        "outlook",
        "brace for",
        "bets",
        "betting",
        "tipped",
        "expected to",
        "likely to",
        "should hold",
        "should hike",
        "should cut",
    ]

    # ===================================================
    # 6. ANÁLISIS DE TERCEROS — EXCLUIR
    # ===================================================

    analisis_terceros = [

        "td securities",
        "td economics",
        "commerzbank",
        "goldman sachs",
        "jpmorgan",
        "jp morgan",
        "morgan stanley",
        "citigroup",
        "citi ",
        "barclays",
        "ubs ",
        "deutsche bank",
        "bank of america",
        "bofa",
        "societe generale",
        "ing ",
        "nomura",
        "rabobank",
        "wells fargo",

        "analyst says",
        "analysts say",
        "strategist says",
        "strategists say",
        "economist says",
        "economists say",

        "experts say",
        "analysts say",
        "economists say",
        "strategists say",
        "preview:",
        "price forecast",
        "brace for",
        "rate hike bets",
        "rate cut bets",
        "hike bets",
        "cut bets",
        "tipped",
        "expected to hike",
        "expected to cut",
        "likely to hike",
        "likely to cut",

        # Alemán
        "zinserhöhungswetten",
        "zinssenkungswetten",
        "wetten auf eine zinserhöhung",
        "wetten auf eine zinssenkung",



    ]

    # ===================================================
    # 7. EXMIEMBROS — EXCLUIR
    # ===================================================

    excluir_antiguos = [

        "former ",
        "former-",
        "ex-official",
        "ex official",
        "ex-governor",
        "ex governor",
        "former governor",
        "former policymaker",
        "former policy maker",
        "former board member",
        "former fed",
        "former ecb",
        "former boe",
        "former boj",
        "former rba",
        "former rbnz",
        "former boc",
        "former snb",
    ]

    # ===================================================
    # 8. RUIDO NO MONETARIO
    # ===================================================

    ruido = [

        "bank regulation",
        "bank regulations",
        "banking regulation",
        "capital requirements",
        "stress test",
        "stress tests",

        "bank merger",
        "bank acquisition",

        "consumer protection",
        "financial regulation",
        "regulatory framework",
    ]

    # ===================================================
    # 9. FILTRADO
    # ===================================================

    resultado = []

    for article in articles:

        title = str(
            article.get("title")
            or ""
        ).strip().lower()

        body = str(
            article.get("body")
            or article.get("summary")
            or ""
        ).strip().lower()

        if not title:
            continue

        texto = f"{title} {body}"


        # ===================================================
        # FALSAS COINCIDENCIAS / ENTIDADES NO CENTRALES
        # ===================================================

        falsas_identidades = {

            "EUR": [
                "england cricket board",
                "cricket",
            ],

            "GBP": [
                "marathon petroleum",
                "mpc capital",
                "mpc oceanic",
            ],

            "CAD": [
                "royal bank of canada",
                "national bank of canada",
                "rbc ",
                "tsx:",
                "earnings call",
                "earnings transcript",
                "quarter results",
                "quarterly results",
            ],
        }

        if any(
            termino in title
            for termino in falsas_identidades.get(divisa, [])
        ):
            continue

        # ---------------------------------------------------
        # A. EXCLUSIONES FUERTES
        # ---------------------------------------------------

        if any(
            termino in title
            for termino in excluir_antiguos
        ):
            continue

        if any(
            termino in title
            for termino in analisis_terceros
        ):
            continue

        if any(
            termino in title
            for termino in ruido
        ):
            continue

        # ---------------------------------------------------
        # RUIDO TEMÁTICO ESPECÍFICO
        # ---------------------------------------------------

        ruido_bancos_centrales = [
            "week ahead",
            "forecast news",
            "capital rules",
            "capital requirements",
        ]

        if any(
            termino in title
            for termino in ruido_bancos_centrales
        ):
            continue

        # ---------------------------------------------------
        # B. IDENTIDAD DEL BANCO CENTRAL
        # ---------------------------------------------------

        banco_titulo = any(
            termino in title
            for termino in bancos.get(divisa, [])
        )

        miembro_titulo = any(
            termino in title
            for termino in miembros.get(divisa, [])
        )

        banco_body = any(
            termino in body
            for termino in bancos.get(divisa, [])
        )

        miembro_body = any(
            termino in body
            for termino in miembros.get(divisa, [])
        )

        identidad_titulo = (
            banco_titulo
            or miembro_titulo
        )

        identidad_body = (
            banco_body
            or miembro_body
        )


        # ---------------------------------------------------
        # C. COMUNICACIÓN / CONTENIDO MONETARIO
        # ---------------------------------------------------

        comunicacion_titulo = any(
            termino in title
            for termino in comunicacion_directa
        )

        contenido_monetario_titulo = any(
            termino in title
            for termino in politica_monetaria
        )

        contenido_monetario_body = any(
            termino in body
            for termino in politica_monetaria
        )

        evento_oficial = any(
            termino in title
            for termino in [
                "minutes",
                "meeting minutes",
                "rate decision",
                "monetary policy decision",
                "monetary policy statement",
                "policy statement",
                "press conference",
            ]
        )


        # ---------------------------------------------------
        # D. EXPECTATIVAS DE MERCADO
        # ---------------------------------------------------

        expectativa_mercado = any(
            termino in title
            for termino in expectativas_mercado
        )


        # ===================================================
        # NIVEL 1 — EVIDENCIA FUERTE EN EL TITULAR
        # ===================================================

        # Banco/miembro identificado +
        # comunicación real +
        # contenido monetario.
        if (
            identidad_titulo
            and comunicacion_titulo
            and (
                contenido_monetario_titulo
                or contenido_monetario_body
            )
            and not expectativa_mercado
        ):
            resultado.append(article)
            continue


        # ===================================================
        # NIVEL 2 — TITULAR MONETARIO + IDENTIDAD EN BODY
        # ===================================================

        # Permite titulares donde el nombre del banco/miembro
        # no aparece explícitamente, pero el cuerpo confirma
        # inequívocamente que procede del banco central.
        if (
            comunicacion_titulo
            and contenido_monetario_titulo
            and identidad_body
            and not expectativa_mercado
        ):
            resultado.append(article)
            continue


        # ===================================================
        # NIVEL 3 — EVENTOS OFICIALES
        # ===================================================

        # Minutes, decisiones, statements y ruedas de prensa
        # tienen suficiente evidencia por sí mismos cuando
        # están asociados al banco central.
        if (
            evento_oficial
            and (
                identidad_titulo
                or identidad_body
            )
            and not expectativa_mercado
        ):
            resultado.append(article)
            continue

        # Todo lo demás se descarta.

    return resultado


# ===================================================
# NAVEGACIÓN PRINCIPAL
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
        '<div class="control-title">Navegación</div>',
        unsafe_allow_html=True
    )

    pagina_principal = st.radio(
        "Navegación",
        options=[
            "Dashboard",
            "FX Live Drivers",
            "CFTC Positioning",
        ],
        index=0,
        label_visibility="collapsed",
        key="pagina_principal",
    )

def clasificar_catalizador_fx(article, divisa):
    """
    Clasificación contextual de catalizadores FX.

    Prioriza el tema principal del TITULAR.
    El cuerpo se utiliza solamente como contexto secundario.
    """

    divisa = str(divisa).strip().upper()

    title = str(article.get("title") or "").lower()

    body = str(
        article.get("body")
        or article.get("summary")
        or ""
    ).lower()

    texto = f"{title} {body}"


    # ===================================================
    # FUNCIONES AUXILIARES
    # ===================================================

    def contiene(texto_objetivo, terminos):
        return any(
            termino in texto_objetivo
            for termino in terminos
        )

    def en_titulo(terminos):
        return contiene(title, terminos)


    # ===================================================
    # REFERENCIAS A BANCOS CENTRALES
    # ===================================================

    central_bank_terms = {

        "USD": [
            "federal reserve",
            "fomc",
            "fed chair",
            "fed governor",
            "fed president",
            "kevin warsh",
        ],

        "EUR": [
            "european central bank",
            "ecb",
            "ecb president",
        ],

        "GBP": [
            "bank of england",
            "boe",
            "monetary policy committee",
            "mpc",
        ],

        "JPY": [
            "bank of japan",
            "boj",
        ],

        "CHF": [
            "swiss national bank",
            "snb",
            "martin schlegel",
        ],

        "AUD": [
            "reserve bank of australia",
            "rba",
        ],

        "NZD": [
            "reserve bank of new zealand",
            "rbnz",
        ],

        "CAD": [
            "bank of canada",
            "boc",
        ],
    }

    cb_terms = central_bank_terms.get(
        divisa,
        []
    )


    # ===================================================
    # 1. INTERVENCIÓN FX
    # Máxima prioridad
    # ===================================================

    intervention_terms = [
        "currency intervention",
        "fx intervention",
        "foreign exchange intervention",
        "intervene in currency",
        "intervene in foreign exchange",
        "intervene in the currency market",
        "support the yen",
        "support the franc",
        "support the currency",
        "weaken the currency",
    ]

    if en_titulo(intervention_terms):

        return {
            "categoria": "INTERVENCIÓN FX",
            "relevancia": "ALTA",
        }


    # ===================================================
    # 2. COMERCIO / ARANCELES
    # ===================================================

    trade_terms = [
        "tariff",
        "tariffs",
        "trade war",
        "trade deal",
        "trade agreement",
        "trade talks",
        "trade negotiations",
        "trade deadline",
        "import tariff",
        "import tariffs",
        "export tariff",
        "import duties",
        "export restrictions",
        "trade restrictions",
    ]

    if en_titulo(trade_terms):

        return {
            "categoria": "COMERCIO / ARANCELES",
            "relevancia": "ALTA",
        }


    # ===================================================
    # 3. RENDIMIENTOS / BONOS
    #
    # Va ANTES que Banco Central.
    # ===================================================

    bond_title_terms = [
        "treasury yield",
        "treasury yields",
        "bond yield",
        "bond yields",
        "treasury market",
        "bond market",
        "treasuries",
        "government bonds",
        "treasury bonds",
        "bond buyback",
        "bond buybacks",
        "treasury buyback",
        "treasury buybacks",
        "borrowing costs",
        "long-term yields",
        "long term yields",
        "gilts",
        "bunds",
        "bond selloff",
        "bond sell-off",
    ]

    treasury_terms = [
        "u.s. treasury",
        "us treasury",
        "treasury department",
        "scott bessent",
    ]

    generic_bond_terms = [
        "bond",
        "bonds",
        "yield",
        "yields",
        "buyback",
        "buybacks",
        "debt market",
        "borrowing costs",
    ]

    # Caso fuerte:
    # el titular habla directamente de bonos/yields.
    if en_titulo(bond_title_terms):

        return {
            "categoria": "RENDIMIENTOS / BONOS",
            "relevancia": "ALTA",
        }

    # Treasury/Bessent + bonos/yields en el titular.
    if (
        en_titulo(treasury_terms)
        and en_titulo(generic_bond_terms)
    ):

        return {
            "categoria": "RENDIMIENTOS / BONOS",
            "relevancia": "ALTA",
        }

    # El titular habla de Treasury/Bessent,
    # y el cuerpo confirma el contexto de deuda/yields.
    if (
        en_titulo(treasury_terms)
        and contiene(body, generic_bond_terms)
    ):

        return {
            "categoria": "RENDIMIENTOS / BONOS",
            "relevancia": "MEDIA",
        }

    # Titular sobre acciones/mercados cuyo movimiento se explica
    # explícitamente por yields/bonos.
    market_terms = [
        "stocks",
        "shares",
        "wall street",
        "equities",
        "markets",
        "european stocks",
        "futures",
    ]

    if (
        en_titulo(market_terms)
        and en_titulo(generic_bond_terms)
    ):

        return {
            "categoria": "RENDIMIENTOS / BONOS",
            "relevancia": "MEDIA",
        }


    # ===================================================
    # 4. BANCO CENTRAL
    # ===================================================

    monetary_terms = [
        "interest rate",
        "interest rates",
        "rate hike",
        "rate hikes",
        "rate cut",
        "rate cuts",
        "cut rates",
        "cuts rates",
        "raise rates",
        "raises rates",
        "hike rates",
        "hikes rates",
        "lower rates",
        "lowers rates",
        "negative rates",
        "below zero",
        "policy rate",
        "monetary policy",
        "hawkish",
        "dovish",
        "tightening",
        "easing",
        "inflation outlook",
    ]

    # Expresiones que implican una señal de política monetaria
    # especialmente directa para la divisa.
    strong_policy_terms = [
        "rate hike",
        "rate hikes",
        "rate cut",
        "rate cuts",
        "cut rates",
        "cuts rates",
        "raise rates",
        "raises rates",
        "hike rates",
        "hikes rates",
        "lower rates",
        "lowers rates",
        "negative rates",
        "below zero",
        "policy rate",
        "further easing",
        "further tightening",
        "pause rates",
        "hold rates",
        "keep rates",
    ]

    cb_en_titulo = en_titulo(
        cb_terms
    )

    monetario_en_titulo = en_titulo(
        monetary_terms
    )

    politica_fuerte_en_titulo = en_titulo(
        strong_policy_terms
    )


    # ===================================================
    # CASO 1
    # Banco central / miembro claramente protagonista
    # ===================================================

    if cb_en_titulo:

        # Declaración explícita sobre tipos o stance monetario:
        # driver directo de la divisa.
        if politica_fuerte_en_titulo:

            return {
                "categoria": "BANCO CENTRAL",
                "relevancia": "ALTA",
            }

        # El titular habla del banco central y tiene
        # contexto monetario, pero no una señal directa.
        if monetario_en_titulo:

            return {
                "categoria": "BANCO CENTRAL",
                "relevancia": "MEDIA",
            }

        # Comentario general de un miembro del banco central.
        return {
            "categoria": "BANCO CENTRAL",
            "relevancia": "MEDIA",
        }


    # ===================================================
    # CASO 2
    # Banco central solo aparece en el cuerpo
    # ===================================================

    if (
        contiene(body, cb_terms)
        and politica_fuerte_en_titulo
    ):

        return {
            "categoria": "BANCO CENTRAL",
            "relevancia": "MEDIA",
        }


    # ===================================================
    # 5. INFLACIÓN
    # ===================================================

    inflation_terms = [
        "inflation",
        "consumer price index",
        "core cpi",
        "cpi",
        "pce inflation",
        "core pce",
        "producer prices",
        "ppi",
        "price pressures",
    ]

    if en_titulo(inflation_terms):

        return {
            "categoria": "INFLACIÓN",
            "relevancia": "ALTA",
        }


    # ===================================================
    # 6. FISCAL
    # ===================================================

    fiscal_terms = [
        "fiscal policy",
        "budget deficit",
        "federal deficit",
        "government deficit",
        "debt ceiling",
        "government spending",
        "fiscal stimulus",
        "tax cuts",
        "tax increase",
        "government debt",
        "national debt",
    ]

    if en_titulo(fiscal_terms):

        return {
            "categoria": "FISCAL",
            "relevancia": "MEDIA",
        }


    # ===================================================
    # 7. GEOPOLÍTICA
    #
    # Exigimos que el contexto geopolítico sea realmente
    # protagonista del titular.
    # ===================================================

    geo_entities = [
        "iran",
        "israel",
        "ukraine",
        "russia",
        "north korea",
        "middle east",
        "hormuz",
        "taiwan",
        "hezbollah",
    ]

    geo_actions = [
        "war",
        "sanctions",
        "attack",
        "strike",
        "missile",
        "military",
        "ceasefire",
        "invasion",
        "conflict",
        "escalation",
        "nuclear",
        "blockade",
    ]

    geo_entity_title = en_titulo(
        geo_entities
    )

    geo_action_title = en_titulo(
        geo_actions
    )

    # Los dos aparecen en el titular:
    # catalizador geopolítico claro.
    if (
        geo_entity_title
        and geo_action_title
    ):

        return {
            "categoria": "GEOPOLÍTICA",
            "relevancia": "ALTA",
        }

    # Entidad geopolítica en titular +
    # acción relevante confirmada en cuerpo.
    if (
        geo_entity_title
        and contiene(body, geo_actions)
    ):

        return {
            "categoria": "GEOPOLÍTICA",
            "relevancia": "MEDIA",
        }


    # ===================================================
    # 8. RIESGO POLÍTICO
    # ===================================================

    political_terms = [
        "government collapse",
        "snap election",
        "confidence vote",
        "no confidence vote",
        "coalition collapse",
        "political crisis",
        "finance minister resigns",
        "prime minister resigns",
        "president resigns",
    ]

    if en_titulo(political_terms):

        return {
            "categoria": "RIESGO POLÍTICO",
            "relevancia": "MEDIA",
        }


    # ===================================================
    # SIN CATALIZADOR CLARO
    # ===================================================

    return {
        "categoria": "OTROS",
        "relevancia": "BAJA",
    }

# ===================================================
# FX LIVE DRIVERS
# ===================================================

# ===================================================
# CFTC POSITIONING
# ===================================================

if pagina_principal == "CFTC Positioning":

    with st.sidebar:
        render_logout(AUTH_PROFILE)

    render_cftc_positioning()

    st.stop()

if pagina_principal == "FX Live Drivers":

    with st.sidebar:
        render_logout(AUTH_PROFILE)

    st.markdown(
        """
        <div class="dashboard-header">
            <div class="dashboard-eyebrow">
                MACRO FX · LIVE
            </div>
            <div class="dashboard-title">
                FX Live Drivers
            </div>
            <div class="dashboard-subtitle">
                Declaraciones de bancos centrales, política económica
                y catalizadores relevantes para el mercado FX.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ===================================================
    # FX LIVE DRIVERS — SELECTOR DE DIVISA
    # ===================================================

    st.markdown(
        """
        <style>
        div[data-testid="stSegmentedControl"] button {
            font-weight: 700;
        }

        .live-drivers-status {
            margin-top: 1.2rem;
            padding: 1rem 1.2rem;
            border: 1px solid #E5E7EB;
            border-radius: 12px;
            background: #FFFFFF;
        }

        .live-drivers-status-title {
            font-size: 0.72rem;
            font-weight: 800;
            letter-spacing: 0.08em;
            color: #9A7A10;
            margin-bottom: 0.35rem;
        }

        .live-drivers-status-text {
            font-size: 0.95rem;
            font-weight: 600;
            color: #111827;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    divisa_live = st.segmented_control(
        "Divisa",
        options=[
            "USD",
            "EUR",
            "GBP",
            "JPY",
            "CHF",
            "AUD",
            "NZD",
            "CAD",
        ],
        default="USD",
        selection_mode="single",
        label_visibility="collapsed",
        key="live_currency",
    )

    modo_live = st.segmented_control(
        "Tipo de información",
        options=[
            "Todos",
            "Bancos centrales",
        ],
        default="Todos",
        selection_mode="single",
        label_visibility="collapsed",
        key="live_driver_mode",
    )


    # ===================================================
    # BANCOS CENTRALES — OPENAI WEB SEARCH GUARDADO
    # ===================================================

    if modo_live == "Bancos centrales":

        render_central_bank_drivers(
            divisa_live
        )

        st.stop()

    # ===================================================
    # FX LIVE DRIVERS — DATOS REALES
    # ===================================================

    live_container = st.container()

    with live_container:

        resultado_newsapi = cargar_live_drivers_newsapi(
            divisa_live,
            modo_live,
        )

        resultado_finnhub = cargar_live_drivers_finnhub(
            divisa_live
        )

        articles_raw = []

        # ===================================================
        # NEWSAPI.AI
        # ===================================================

        if resultado_newsapi["ok"]:
            for article in resultado_newsapi["articles"]:
                article = article.copy()
                article["_provider"] = "NewsAPI.ai"
                articles_raw.append(article)

        # ===================================================
        # FINNHUB
        # ===================================================

        if resultado_finnhub["ok"]:
            articles_raw.extend(
                resultado_finnhub["articles"]
            )

        from datetime import datetime, timezone, timedelta

        # ===================================================
        # MÁXIMO 7 DÍAS
        # ===================================================

        fecha_limite = datetime.now(timezone.utc) - timedelta(days=7)

        articles_7d = []

        for article in articles_raw:

            fecha_raw = (
                article.get("publishedAt")
                or article.get("dateTimePub")
                or article.get("date")
            )

            if fecha_raw is None:
                continue

            try:

                # Finnhub entrega timestamp Unix
                if isinstance(fecha_raw, (int, float)):
                    fecha_articulo = datetime.fromtimestamp(
                        fecha_raw,
                        tz=timezone.utc,
                    )

                else:
                    fecha_articulo = pd.to_datetime(
                        fecha_raw,
                        utc=True,
                        errors="coerce",
                    )

                    if pd.isna(fecha_articulo):
                        continue

                    fecha_articulo = fecha_articulo.to_pydatetime()

                if fecha_articulo >= fecha_limite:
                    article["_fecha_live"] = fecha_articulo
                    articles_7d.append(article)

            except Exception:
                continue

        articles_raw = articles_7d

        articles_raw.sort(
            key=lambda article: article.get(
                "_fecha_live",
                datetime.min.replace(tzinfo=timezone.utc),
            ),
            reverse=True,
        )

        # ===================================================
        # SI FALLAN LAS DOS
        # ===================================================

        if (
            not resultado_newsapi["ok"]
            and not resultado_finnhub["ok"]
        ):

            st.error(
                "No se pudieron cargar noticias desde "
                "NewsAPI.ai ni Finnhub."
            )

            st.caption(
                f"NewsAPI.ai: {resultado_newsapi['error']}"
            )

            st.caption(
                f"Finnhub: {resultado_finnhub['error']}"
            )

            articles = []

        else:

            # ===================================================
            # COMPROBACIÓN TEMPORAL DE LAS DOS APIs
            # ===================================================

            st.write(
                "NewsAPI RAW:",
                len(resultado_newsapi["articles"])
                if resultado_newsapi["ok"]
                else 0,
            )

            st.write(
                "Finnhub RAW:",
                len(resultado_finnhub["articles"])
                if resultado_finnhub["ok"]
                else 0,
            )

            st.write(
                "Total combinado:",
                len(articles_raw),
            )

            # ===================================================
            # FILTRO FX COMÚN PARA LAS DOS FUENTES
            # ===================================================

            if modo_live == "Bancos centrales":

                articles = filtrar_bancos_centrales(
                    articles_raw,
                    divisa_live,
                )

            else:

                articles = filtrar_articulos_fx(
                    articles_raw,
                    divisa_live,
                )

            st.write(
                "Después del filtro:",
                len(articles),
            )

            # ===================================================
            # TEST — CANDIDATOS PARA CENTRALBANK_DRIVERS
            # ===================================================

            if modo_live == "Bancos centrales":

                candidatos_bc = []

                for article in articles:

                    titulo = str(
                        article.get("title")
                        or ""
                    ).strip()

                    url = str(
                        article.get("url")
                        or article.get("link")
                        or ""
                    ).strip()

                    fecha = article.get("_fecha_live")

                    provider = str(
                        article.get("_provider")
                        or article.get("source")
                        or ""
                    ).strip()

                    if not titulo:
                        continue

                    # Identificador provisional.
                    # Más adelante servirá para saber si ya fue analizado.
                    clave = url if url else titulo.lower()

                    candidatos_bc.append(
                        {
                            "key": clave,
                            "currency": divisa_live,
                            "title": titulo,
                            "url": url,
                            "published_at": (
                                fecha.isoformat()
                                if fecha is not None
                                else None
                            ),
                            "provider": provider,
                        }
                    )

                st.markdown("### TEST — CentralBank Drivers")

                st.write(
                    "Candidatos BC:",
                    len(candidatos_bc),
                )

                for candidato in candidatos_bc[:10]:

                    st.write(
                        candidato["published_at"],
                        candidato["provider"],
                        candidato["title"],
                    )
            # ===================================================
            # ELIMINAR TITULARES DUPLICADOS / MUY SIMILARES
            # ===================================================

            from difflib import SequenceMatcher
            import re

            def normalizar_titulo_noticia(titulo):
                titulo = str(titulo or "").lower()

                # Quitar nombre del medio al final: "| WNYC", "- Reuters", etc.
                titulo = re.sub(r"\s*[|\-–—]\s*[^|\-–—]{2,40}$", "", titulo)

                # Quitar puntuación
                titulo = re.sub(r"[^\w\s]", " ", titulo)

                # Normalizar espacios
                titulo = " ".join(titulo.split())

                return titulo


            def titulos_son_similares(titulo_1, titulo_2):
                t1 = normalizar_titulo_noticia(titulo_1)
                t2 = normalizar_titulo_noticia(titulo_2)

                if not t1 or not t2:
                    return False

                # Coincidencia casi literal
                similitud = SequenceMatcher(
                    None,
                    t1,
                    t2
                ).ratio()

                if similitud >= 0.82:
                    return True

                # Comprobar cuánto vocabulario importante comparten
                palabras_1 = set(t1.split())
                palabras_2 = set(t2.split())

                if not palabras_1 or not palabras_2:
                    return False

                palabras_comunes = palabras_1 & palabras_2

                cobertura = len(palabras_comunes) / min(
                    len(palabras_1),
                    len(palabras_2)
                )

                if cobertura >= 0.80:
                    return True

                return False


            articles_unicos = []

            for article in articles:

                titulo_actual = str(
                    article.get("title")
                    or ""
                ).strip()

                if not titulo_actual:
                    continue

                es_duplicado = False

                for article_guardado in articles_unicos:

                    titulo_guardado = str(
                        article_guardado.get("title")
                        or ""
                    ).strip()

                    if titulos_son_similares(
                        titulo_actual,
                        titulo_guardado
                    ):
                        es_duplicado = True
                        break

                if not es_duplicado:
                    articles_unicos.append(article)

            articles = articles_unicos


            if not articles:

                st.info(
                    f"No se encontraron titulares recientes para "
                    f"{divisa_live}."
                )

            else:

                # ===================================================
                # PREPARAR SOLO LOS DRIVERS QUE REALMENTE SE MOSTRARÁN
                # ===================================================

                articles_finales = []

                for article in articles[:20]:

                    clasificacion = clasificar_catalizador_fx(
                        article,
                        divisa_live
                    )

                    categoria = clasificacion["categoria"]
                    relevancia = clasificacion["relevancia"]

                    # Eliminar ruido
                    if relevancia == "BAJA" or categoria == "OTROS":
                        continue

                    # ===================================================
                    # FILTRO EXCLUSIVO DE BANCOS CENTRALES
                    # ===================================================


                    articles_finales.append(
                        (article, categoria, relevancia)
                    )

                    # Máximo 7 tarjetas visibles
                    if len(articles_finales) >= 7:
                        break


                # ===================================================
                # CONTADOR REAL DE DRIVERS VISIBLES
                # ===================================================

                st.caption(
                    f"{len(articles_finales)} drivers activos · "
                    "Actualización máxima cada 10 minutos"
                )


                # ===================================================
                # RENDERIZAR TARJETAS
                # ===================================================

                if not articles_finales:

                    st.info(
                        f"No se encontraron catalizadores relevantes "
                        f"para {divisa_live} en este momento."
                    )

                else:

                    for article, categoria, relevancia in articles_finales:

                        title = str(
                            article.get("title")
                            or "Sin título"
                        ).strip()

                        url = (
                            article.get("url")
                            or ""
                        )

                        html_article = (
                            f'<div style="background:#FFFFFF;'
                            f'border:1px solid #E5E7EB;'
                            f'border-radius:14px;'
                            f'padding:1rem 1.15rem;'
                            f'margin-bottom:0.85rem;">'

                            f'<div style="color:#9A7A10;'
                            f'font-size:0.72rem;'
                            f'font-weight:800;'
                            f'letter-spacing:0.05em;'
                            f'margin-bottom:0.45rem;">'
                            f'{divisa_live} · {categoria} · {relevancia}'
                            f'</div>'

                            f'<div style="color:#111111;'
                            f'font-size:1.02rem;'
                            f'font-weight:750;'
                            f'line-height:1.45;">'
                            f'{title}'
                            f'</div>'

                            f'<div style="margin-top:0.65rem;'
                            f'font-size:0.82rem;">'
                            f'<a href="{url}" target="_blank" '
                            f'style="color:#2563EB;text-decoration:none;">'
                            f'Abrir fuente ↗'
                            f'</a>'
                            f'</div>'

                            f'</div>'
                        )

                        st.markdown(
                            html_article,
                            unsafe_allow_html=True,
                        )
                


    st.stop()


# ===================================================
# DASHBOARD
# ===================================================

with st.sidebar:

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

    data_version = calcular_data_version(
        df,
        divisa,
    )

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
                <strong>Datos:</strong> Macro FX Database<br>
                <strong>Actualización:</strong> Automática
            </div>
            """,
            unsafe_allow_html=True
        )

        render_logout(AUTH_PROFILE)


    # ===================================================
    # CONVERSIÓN DE VALORES
    # PMI RELEASE-AWARE: usar EODHD cuando esté disponible
    # ===================================================

    df["Valor"] = convertir_valores(df[indicador])

    datos_completos = (
        df[["Fecha", "Valor"]]
        .dropna()
        .sort_values("Fecha")
        .reset_index(drop=True)
    )

    # Para indicadores con serie release-aware, usamos la misma
    # serie que utiliza el Currency Score.
    indicadores_divisa = obtener_indicadores(df)

    series_release_vista = construir_df_currency_por_release(
        df,
        divisa,
        indicadores_divisa,
    )

    nombre_score_vista = (
        MAPA_INDICADORES_IA
        .get(str(divisa).strip().upper(), {})
        .get(indicador, indicador)
    )

    serie_release_vista = series_release_vista.get(
        nombre_score_vista
    )

    if (
        serie_release_vista is not None
        and not serie_release_vista.empty
    ):

        datos_release_vista = (
            serie_release_vista[
                [
                    "FechaPeriodo",
                    "Valor",
                    "Previous",
                    "Estimate",
                ]
            ]
            .dropna(
                subset=[
                    "FechaPeriodo",
                    "Valor",
                ]
            )
            .rename(
                columns={
                    "FechaPeriodo": "Fecha"
                }
            )
            .sort_values("Fecha")
            .reset_index(drop=True)
        )

        if not datos_release_vista.empty:
            datos_completos = datos_release_vista

    if datos_completos.empty:
        st.warning("Este indicador todavía no contiene datos disponibles.")
        st.stop()

    analisis = analizar_indicador(
        datos_completos["Fecha"],
        datos_completos["Valor"],
        indicador,
        divisa
    )

    resultados_divisa = analizar_divisa_completa(
        df,
        divisa,
        indicadores,
    )

# ===================================================
# SELECTOR DE VISTA
# ===================================================

    vista = st.sidebar.radio(
        "VISTA",
        ["Indicador", "Currency Score"],
        index=0,
    )

    currency_score = calcular_currency_score(
        divisa,
        resultados_divisa,
    )

    if vista == "Currency Score":

        t_total = time.perf_counter()

        # 1. Currency Score actual
        t0 = time.perf_counter()

        score = currency_score.get("score")
        coverage = currency_score.get("coverage", 0)
        families = currency_score.get("families", {})

        print(
            f"[TIEMPO] Score actual {divisa}: "
            f"{time.perf_counter() - t0:.2f}s"
        )

        # 2. Ranking de divisas
        t0 = time.perf_counter()

        ranking_divisas = calcular_ranking_divisas()

        print(
            f"[TIEMPO] Ranking: "
            f"{time.perf_counter() - t0:.2f}s"
        )

        # 3. Histórico
        t0 = time.perf_counter()

        historico_score = calcular_historico_currency_score(
            divisa,
            data_version,
            frecuencia="W",
            periodos=26,
            revision="release_18",
        )

        print(
            f"[TIEMPO] Histórico {divisa}: "
            f"{time.perf_counter() - t0:.2f}s"
        )

        if (
            historico_score is not None
            and not historico_score.empty
        ):
            ultima_fila_score = (
                historico_score
                .sort_values("Fecha")
                .iloc[-1]
            )

            score = float(
                ultima_fila_score["Score"]
            )

            coverage = float(
                ultima_fila_score["Coverage"]
            )

            t0 = time.perf_counter()

            drivers_historicos = (
                calcular_drivers_historicos_currency_score(
                    divisa,
                    historico_score,
                )
            )

            print(
                f"[TIEMPO] Drivers históricos {divisa}: "
                f"{time.perf_counter() - t0:.2f}s"
            )

            t0 = time.perf_counter()

            drivers_ultimo_cambio = calcular_drivers_ultimo_cambio(
                divisa,
                historico_score,
            )

            print(
                f"[TIEMPO] Drivers último cambio {divisa}: "
                f"{time.perf_counter() - t0:.2f}s"
            )

            print(
                f"[TIEMPO] TOTAL Currency Score {divisa}: "
                f"{time.perf_counter() - t_total:.2f}s"
            )



        def obtener_score_historico(historico, semanas_atras):
            if historico.empty:
                return None

            historico = historico.sort_values("Fecha").reset_index(drop=True)

            fecha_actual = historico["Fecha"].max()
            fecha_objetivo = fecha_actual - pd.Timedelta(weeks=semanas_atras)

            datos_previos = historico[
                historico["Fecha"] <= fecha_objetivo
            ]

            if datos_previos.empty:
                return None

            return float(datos_previos.iloc[-1]["Score"])


        score_1s = obtener_score_historico(
            historico_score,
            1,
        )

        score_1m = obtener_score_historico(
            historico_score,
            4,
        )

        score_3m = obtener_score_historico(
            historico_score,
            13,
        )


        cambio_1s = (
            score - score_1s
            if score is not None and score_1s is not None
            else None
        )

        cambio_1m = (
            score - score_1m
            if score is not None and score_1m is not None
            else None
        )

        cambio_3m = (
            score - score_3m
            if score is not None and score_3m is not None
            else None
        )     



        rating = (
            clasificar_currency_score(score)
            if score is not None
            else "Sin evaluación"
        )

        # ===================================================
        # CABECERA CURRENCY SCORE
        # ===================================================

        st.markdown(
            f'<div style="background:linear-gradient(135deg,#111111,#202020);'
            f'border-radius:18px;padding:28px 30px;margin-bottom:22px;">'
            f'<div style="color:#d4a514;font-size:12px;font-weight:800;'
            f'letter-spacing:1.4px;">'
            f'FINANS TRADING · CURRENCY SCORE'
            f'</div>'
            f'<div style="color:white;font-size:32px;font-weight:800;'
            f'margin-top:8px;">'
            f'{divisa} · Macro Score'
            f'</div>'
            f'<div style="color:#b7bcc7;font-size:15px;margin-top:6px;">'
            f'Lectura macroeconómica agregada de la divisa'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        if score is None:
            st.warning(
                "Todavía no existen suficientes datos para calcular "
                "el Currency Score."
            )
            st.stop()

        # ===================================================
        # MÉTRICAS PRINCIPALES
        # ===================================================

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "CURRENCY SCORE",
                f"{score:.1f}/100"
            )

        with col2:
            st.metric(
                "SEÑAL MACRO",
                rating
            )

        with col3:
            st.metric(
                "COBERTURA",
                "Indicadores clave",
                help=(
                    "El Currency Score utiliza una selección de "
                    "indicadores macroeconómicos representativos."
                ),
            )

        # ===================================================
        # MOMENTUM DEL CURRENCY SCORE
        # ===================================================

        st.markdown("## Evolución del Currency Score")

        st.caption(
            "Cambios en la presión macroeconómica agregada "
            "de la divisa."
        )

        def formatear_cambio_score(cambio):
            if cambio is None:
                return "Sin dato"

            if cambio > 0:
                return f"+{cambio:.1f} pts"

            return f"{cambio:.1f} pts"


        momentum_1, momentum_2, momentum_3, momentum_4 = st.columns(4)

        with momentum_1:
            st.metric(
                "SCORE ACTUAL",
                f"{score:.1f}/100"
            )

        with momentum_2:
            st.metric(
                "1 SEMANA",
                f"{score_1s:.1f}/100" if score_1s is not None else "Sin dato",
                delta=formatear_cambio_score(cambio_1s),
            )

        with momentum_3:
            st.metric(
                "1 MES",
                f"{score_1m:.1f}/100" if score_1m is not None else "Sin dato",
                delta=formatear_cambio_score(cambio_1m),
            )

        with momentum_4:
            st.metric(
                "3 MESES",
                f"{score_3m:.1f}/100" if score_3m is not None else "Sin dato",
                delta=formatear_cambio_score(cambio_3m),
            )

        # ===================================================
        # GRÁFICO HISTÓRICO DEL SCORE
        # ===================================================

        historico_grafico = pd.DataFrame(
        columns=[
            "Fecha",
            "Score",
            "Coverage",
            ]
        )

        if not historico_score.empty:

            historico_grafico = (
                historico_score
                .copy()
                .sort_values("Fecha")
                .reset_index(drop=True)
            )

        figura_score = go.Figure()

        figura_score.add_trace(
            go.Scatter(
                x=historico_grafico["Fecha"],
                y=historico_grafico["Score"],
                mode="lines+markers",
                name="Currency Score",
                line=dict(
                    color=COLOR_DORADO,
                    width=3,
                ),
                marker=dict(
                    size=6,
                    color=COLOR_DORADO,
                ),
                fill="tozeroy",
                fillcolor="rgba(201, 162, 39, 0.08)",
                hovertemplate=(
                    "<b>%{x|%d %b %Y}</b>"
                    "<br>Currency Score: "
                    "<b>%{y:.1f}/100</b>"
                    "<extra></extra>"
                ),
            )
        )

        # ===================================================
        # ESCALA DINÁMICA
        # ===================================================

        min_score = float(
            historico_grafico["Score"].min()
        )

        max_score = float(
            historico_grafico["Score"].max()
        )

        rango_score = max_score - min_score

        margen_score = max(
            rango_score * 0.20,
            0.8,
        )

        eje_score_min = max(
            0,
            min_score - margen_score,
        )

        eje_score_max = min(
            100,
            max_score + margen_score,
        )

        # ===================================================
        # LÍNEA NEUTRAL
        # ===================================================

        if eje_score_min <= 50 <= eje_score_max:
            figura_score.add_hline(
                y=50,
                line_width=1,
                line_dash="dot",
                line_color="rgba(107, 114, 128, 0.65)",
                annotation_text="Neutral 50",
                annotation_position="top left",
            )

        # ===================================================
        # DISEÑO DEL GRÁFICO
        # ===================================================

        figura_score.update_layout(
            height=360,
            margin=dict(
                l=10,
                r=10,
                t=10,
                b=10,
            ),
            paper_bgcolor="white",
            plot_bgcolor="white",
            showlegend=False,
            hovermode="x unified",
        )

        figura_score.update_xaxes(
            gridcolor="rgba(107, 114, 128, 0.08)",
            fixedrange=True,
        )

        figura_score.update_yaxes(
            range=[
                eje_score_min,
                eje_score_max,
            ],
            gridcolor="rgba(107, 114, 128, 0.12)",
            fixedrange=True,
        )
        st.plotly_chart(
            figura_score,
            use_container_width=True,
            config={
                "displaylogo": False,
                "displayModeBar": False,
                "scrollZoom": False,
                "responsive": True,
            },
        )

        # ===================================================
        # DRIVERS DE LOS CAMBIOS DEL CURRENCY SCORE
        # ===================================================

        st.markdown("## ¿Qué movió el Currency Score?")

        st.caption(
            "Consulta los principales indicadores que explican "
            "cada cambio observado en la evolución del score."
        )

        # Mostrar drivers únicamente de las últimas 4 semanas
        if drivers_historicos:

            fecha_driver_final = max(
                pd.to_datetime(cambio["Fecha"])
                for cambio in drivers_historicos
            )

            fecha_limite_drivers = (
                fecha_driver_final - pd.Timedelta(weeks=4)
            )

            cambios_relevantes = [
                cambio
                for cambio in drivers_historicos
                if (
                    abs(cambio["Cambio"]) >= 0.01
                    and pd.to_datetime(cambio["Fecha"]) >= fecha_limite_drivers
                )
            ]

        else:
            cambios_relevantes = []

        if not cambios_relevantes:

            st.info(
                "No se han detectado cambios relevantes "
                "del Currency Score en el periodo seleccionado."
            )

        else:

            for cambio in reversed(cambios_relevantes):

                fecha_anterior = pd.to_datetime(
                    cambio["Fecha anterior"]
                )

                fecha_actual = pd.to_datetime(
                    cambio["Fecha"]
                )

                score_anterior_cambio = float(
                    cambio["Score anterior"]
                )

                score_actual_cambio = float(
                    cambio["Score actual"]
                )

                variacion_cambio = float(
                    cambio["Cambio"]
                )

                drivers_cambio = cambio.get(
                    "Drivers",
                    []
                )

                if variacion_cambio > 0:
                    simbolo = "▲"
                    direccion = "Más hawkish"

                elif variacion_cambio < 0:
                    simbolo = "▼"
                    direccion = "Más dovish"

                else:
                    simbolo = "—"
                    direccion = "Sin cambio"

                titulo_cambio = (
                    f"{fecha_anterior.strftime('%d %b')} → "
                    f"{fecha_actual.strftime('%d %b %Y')} · "
                    f"{score_anterior_cambio:.1f} → "
                    f"{score_actual_cambio:.1f} · "
                    f"{simbolo} {variacion_cambio:+.1f} pts"
                )

                with st.expander(
                    titulo_cambio,
                    expanded=False,
                ):

                    st.caption(
                        f"Dirección macro: {direccion}"
                    )

                    if not drivers_cambio:

                        st.write(
                            "No se identificaron drivers "
                            "individuales para este movimiento."
                        )

                        continue

                    for driver in drivers_cambio:

                        nombre_driver = driver.get(
                            "Indicador",
                            "Indicador",
                        )

                        familia_driver = driver.get(
                            "Familia",
                            "",
                        )

                        score_driver_anterior = driver.get(
                            "Score anterior"
                        )

                        score_driver_actual = driver.get(
                            "Score actual"
                        )

                        impacto_driver = driver.get(
                            "Impacto estimado",
                            0,
                        )

                        cambio_driver = driver.get(
                            "Cambio indicador",
                            0,
                        )

                        col_driver_1, col_driver_2, col_driver_3 = (
                            st.columns(
                                [2.4, 1.2, 1.2]
                            )
                        )

                        with col_driver_1:

                            st.markdown(
                                f"**{nombre_driver}**"
                            )

                            if familia_driver:
                                st.caption(
                                    familia_driver.title()
                                )

                        with col_driver_2:

                            st.markdown(
                                f"{score_driver_anterior:.1f} → "
                                f"{score_driver_actual:.1f}"
                            )

                            st.caption(
                                f"Δ indicador "
                                f"{cambio_driver:+.1f}"
                            )

                        with col_driver_3:

                            if impacto_driver > 0:
                                impacto_texto = (
                                    f"▲ +{impacto_driver:.2f} pts"
                                )

                            elif impacto_driver < 0:
                                impacto_texto = (
                                    f"▼ {impacto_driver:.2f} pts"
                                )

                            else:
                                impacto_texto = "— 0.00 pts"

                            st.markdown(
                                f"**{impacto_texto}**"
                            )

                            st.caption(
                                "Impacto estimado"
                            )

        st.markdown("## Ranking macro")

        st.markdown(
            """
            <div style="
                display:inline-block;
                background:#FFF7D6;
                border:1px solid #E7C95A;
                color:#9A7200;
                border-radius:8px;
                padding:6px 12px;
                font-size:14px;
                font-weight:700;
                margin:2px 0 8px 0;
            ">🎯 ALTA PRECISIÓN</div>
            """,
            unsafe_allow_html=True,
        )

        st.caption(
            "Comparación integral basada en el conjunto completo "
            "de indicadores disponibles."
        )

        for posicion, item in enumerate(
            ranking_divisas,
            start=1,
        ):

            currency_rank = item["currency"]
            score_rank = item["score"]
            rating_rank = item["rating"]
            coverage_rank = item["coverage"]

            if score_rank is None:
                continue

            es_actual = (
                currency_rank == divisa
            )

            fondo = (
                "#FFF8E1"
                if es_actual
                else "#FFFFFF"
            )

            borde = (
                "#C9A227"
                if es_actual
                else "#E5E7EB"
            )

            html_ranking = (
                f'<div style="background:{fondo};'
                f'border:1px solid {borde};'
                f'border-radius:12px;'
                f'padding:12px 16px;'
                f'margin-bottom:8px;'
                f'display:grid;'
                f'grid-template-columns:50px 90px 1fr 130px;'
                f'align-items:center;'
                f'gap:10px;">'

                f'<div style="color:#6B7280;'
                f'font-weight:800;">'
                f'#{posicion}'
                f'</div>'

                f'<div style="font-size:18px;'
                f'font-weight:800;'
                f'color:#111111;">'
                f'{currency_rank}'
                f'</div>'

                f'<div>'
                f'<div style="font-size:20px;'
                f'font-weight:800;'
                f'color:#111111;">'
                f'{score_rank:.1f}/100'
                f'</div>'
                f'<div style="font-size:12px;'
                f'color:#6B7280;">'
                f'{rating_rank}'
                f'</div>'
                f'</div>'

                f'<div style="text-align:right;'
                f'font-size:12px;'
                f'color:#6B7280;">'
                f'Cobertura '
                f'{coverage_rank * 100:.0f}%'
                f'</div>'

                f'</div>'
            )

            st.markdown(
                html_ranking,
                unsafe_allow_html=True,
            )

        st.markdown("## Componentes macro")

        # ===================================================
        # FAMILIAS
        # ===================================================

        for nombre_familia, datos_familia in families.items():

            family_score = datos_familia.get("score")
            family_weight = datos_familia.get("peso_original", 0)
            family_coverage = datos_familia.get("coverage", 0)

            if family_score is None:
                continue

            titulo_familia = (
                nombre_familia
                .replace("_", " ")
                .title()
            )

            html_familia = (
                f'<div style="background:#ffffff;'
                f'border:1px solid #e3e6eb;'
                f'border-radius:14px;'
                f'padding:18px 20px;'
                f'margin-bottom:10px;'
                f'display:flex;'
                f'justify-content:space-between;'
                f'align-items:center;">'

                f'<div>'
                f'<div style="font-size:12px;'
                f'color:#697386;'
                f'font-weight:800;'
                f'letter-spacing:.6px;">'
                f'{titulo_familia.upper()}'
                f'</div>'

                f'<div style="font-size:25px;'
                f'font-weight:800;'
                f'color:#111;'
                f'margin-top:4px;">'
                f'{family_score:.1f}/100'
                f'</div>'
                f'</div>'

                f'<div style="text-align:right;'
                f'color:#697386;'
                f'font-size:13px;">'
                f'Peso {family_weight * 100:.0f}%<br>'
                f'Cobertura {family_coverage * 100:.0f}%'
                f'</div>'

                f'</div>'
            )

            st.markdown(
                html_familia,
                unsafe_allow_html=True,
            )

                        # ===================================================
            # DESGLOSE DE INDICADORES
            # ===================================================

            indicadores_familia = datos_familia.get(
                "indicators",
                {}
            )

            if indicadores_familia:

                with st.expander(
                    f"Ver desglose de {titulo_familia}",
                    expanded=False,
                ):

                    for nombre_indicador, datos_indicador in indicadores_familia.items():

                        indicator_score = datos_indicador.get(
                            "score"
                        )

                        peso_original = datos_indicador.get(
                            "peso_original",
                            0,
                        )

                        peso_normalizado = datos_indicador.get(
                            "peso_normalizado",
                            0,
                        )

                        contribution = datos_indicador.get(
                            "contribution",
                            0,
                        )

                        if indicator_score is None:
                            continue

                        columna_nombre, columna_score, columna_peso = st.columns(
                            [2.5, 1, 1.2]
                        )

                        with columna_nombre:
                            st.markdown(
                                f"**{nombre_indicador}**"
                            )

                        with columna_score:
                            st.markdown(
                                f"**{indicator_score:.1f}/100**"
                            )

                        with columna_peso:
                            st.markdown(
                                f"{peso_normalizado * 100:.0f}%"
                            )

                        st.progress(
                            max(
                                0.0,
                                min(
                                    1.0,
                                    indicator_score / 100,
                                ),
                            )
                        )

                        st.caption(
                            f"Peso configurado: "
                            f"{peso_original * 100:.0f}%"
                            f" · Contribución al bloque: "
                            f"{contribution:.1f} pts"
                        )



        st.stop()



    fecha_minima = datos_completos["Fecha"].min()
    fecha_maxima = datos_completos["Fecha"].max()

    ultimo_registro = datos_completos.iloc[-1]
    ultimo_valor = float(ultimo_registro["Valor"])
    estimacion_ultimo = convertir_valores(
        pd.Series([ultimo_registro.get("Estimate")])
    ).iloc[0]

    previous_release = convertir_valores(
        pd.Series([ultimo_registro.get("Previous")])
    ).iloc[0]

    # ===================================================
    # NORMALIZACIÓN DE UNIDADES EODHD -> DASHBOARD
    #
    # Algunos indicadores de empleo llegan desde EODHD
    # expresados en miles, mientras el Dashboard histórico
    # utiliza personas/unidades completas.
    # ===================================================

    factores_unidad_eodhd = {
        ("USD", "NFP"): 1000,
        ("AUD", "Employment"): 1000,
        ("CHF", "Employment"): 1000,
    }

    clave_unidad = (
        str(divisa).strip().upper(),
        str(indicador).strip(),
    )

    factor_unidad = factores_unidad_eodhd.get(
        clave_unidad,
        1,
    )

    if pd.notna(estimacion_ultimo):
        estimacion_ultimo = (
            float(estimacion_ultimo)
            * factor_unidad
        )

    if pd.notna(previous_release):
        previous_release = (
            float(previous_release)
            * factor_unidad
        )

    ultima_fecha = ultimo_registro["Fecha"]

    # ===================================================
    # DATO ANTERIOR
    #
    # Siempre procede de la propia serie histórica
    # del Dashboard.
    #
    # EODHD se utiliza como reloj de publicación,
    # no como fuente del dato anterior.
    # ===================================================

    if len(datos_completos) >= 2:
        valor_anterior = float(
            datos_completos.iloc[-2]["Valor"]
        )
    else:
        valor_anterior = None

    variacion = (
        ultimo_valor - valor_anterior
        if valor_anterior is not None
        else None
    )

    sufijo = determinar_sufijo(indicador)

    ultimo_texto = formatear_valor(ultimo_valor, sufijo)

    prevision_texto = (
        formatear_valor(
            float(estimacion_ultimo),
            sufijo,
        )
        if pd.notna(estimacion_ultimo)
        else "Sin previsión"
        )

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
                 · Último dato disponible: {fecha_texto}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


    # ===================================================
    # TARJETAS DE MÉTRICAS
    # ===================================================

    (
        columna_1,
        columna_2,
        columna_3,
        columna_4,
        columna_5,
    ) = st.columns(5)

    with columna_1:
        st.markdown(
            crear_tarjeta(
                "Último dato",
                ultimo_texto,
                f"Periodo {fecha_texto}",
            ),
            unsafe_allow_html=True,
        )

    with columna_2:
        st.markdown(
            crear_tarjeta(
                "Previsión",
                prevision_texto,
                "Consenso previo al dato",
            ),
            unsafe_allow_html=True,
        )

    with columna_3:
        st.markdown(
            crear_tarjeta(
                "Dato anterior",
                anterior_texto,
                "Lectura anterior",
            ),
            unsafe_allow_html=True,
        )

    with columna_4:
        st.markdown(
            crear_tarjeta(
                "Variación",
                signo_variacion if signo_variacion else "—",
                variacion_texto,
                clase_variacion,
            ),
            unsafe_allow_html=True,
        )

    with columna_5:
        st.markdown(
            crear_tarjeta(
                "Publicaciones",
                publicaciones_texto,
                f"Desde {fecha_minima.strftime('%m/%Y')}",
            ),
            unsafe_allow_html=True,
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
            mode="lines+markers",
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

    

    interpretacion_ia = obtener_interpretacion_ia(
        divisa,
        indicador
    )

    if interpretacion_ia is None:
        st.warning("Todavía no existe una interpretación IA para este indicador.")

    else:

        st.markdown("### Macro Analysis")

        fila_ia_1_col_1, fila_ia_1_col_2 = st.columns(2)

        with fila_ia_1_col_1:
            st.markdown(
                crear_tarjeta_interpretacion(
                    "Situación actual",
                    interpretacion_ia.get(
                        "Current Situation",
                        "Sin información disponible."
                    )
                ),
                unsafe_allow_html=True
            )

        with fila_ia_1_col_2:
            st.markdown(
                crear_tarjeta_interpretacion(
                    "Tendencia",
                    interpretacion_ia.get(
                        "Trend",
                        "Sin información disponible."
                    )
                ),
                unsafe_allow_html=True
            )

        fila_ia_2_col_1, fila_ia_2_col_2 = st.columns(2)

        with fila_ia_2_col_1:
            st.markdown(
                crear_tarjeta_interpretacion(
                    "Política monetaria",
                    interpretacion_ia.get(
                        "Monetary Policy",
                        "Sin información disponible."
                    )
                ),
                unsafe_allow_html=True
            )

        with fila_ia_2_col_2:
            st.markdown(
                crear_tarjeta_interpretacion(
                    "Impacto sobre la divisa",
                    interpretacion_ia.get(
                        "FX Impact",
                        "Sin información disponible."
                    )
                ),
                unsafe_allow_html=True
            )

        resumen_ia = interpretacion_ia.get(
            "Summary",
            "Sin resumen disponible."
        )

        st.markdown(
            f"""
<div class="macro-summary-box">
    <div class="macro-summary-label">Resumen</div>
    <div class="macro-summary-text">{resumen_ia}</div>
</div>
            """,
            unsafe_allow_html=True
        )

        confianza_ia = str(
            interpretacion_ia.get(
                "Confidence",
                "Sin evaluación"
            )
        ).strip()

        confianza_normalizada = confianza_ia.lower()

        if confianza_normalizada in {"alta", "high"}:
            clase_confianza = "confidence-high"

        elif confianza_normalizada in {"baja", "low"}:
            clase_confianza = "confidence-low"

        else:
            clase_confianza = "confidence-medium"

        st.markdown(
            f"""
<div class="confidence-badge {clase_confianza}">
    Confianza: {confianza_ia}
</div>
            """,
            unsafe_allow_html=True
        )
    st.markdown("### Macro Intelligence")
    st.caption("Análisis cuantitativo automático del indicador")
    st.caption(f"Motor activo: {ENGINE_VERSION}")

    columna_inteligencia_1, columna_inteligencia_2, columna_inteligencia_3, columna_inteligencia_4 = st.columns(4)

    with columna_inteligencia_1:
        macro_score = analisis.get("macro_score")
        macro_score_texto = f"{macro_score}/100" if macro_score is not None else "Pendiente"

        st.markdown(
            crear_tarjeta_inteligencia(
                "Presión monetaria",
                macro_score_texto,
                analisis.get("macro_rating", "Sin evaluación")
            ),
            unsafe_allow_html=True
        )

    with columna_inteligencia_2:
        percentil = analisis.get("percentil")
        percentil_texto = f"{percentil:.1f}%" if percentil is not None else "Sin datos"

        st.markdown(
            crear_tarjeta_inteligencia(
                "Posición histórica",
                percentil_texto,
                analisis["categoria_percentil"]
            ),
            unsafe_allow_html=True
        )

    with columna_inteligencia_3:
        st.markdown(
            crear_tarjeta_inteligencia(
                "Tendencia",
                analisis["tendencia_12"],
                "Tendencia de los últimos 12 periodos"
            ),
            unsafe_allow_html=True
        )

    with columna_inteligencia_4:
        momentum_3 = analisis["momentum_3"]

        if momentum_3 is None:
            momentum_texto = "Sin datos"
            momentum_nota = "No hay suficientes publicaciones"
        else:
            momentum_texto = analisis.get("impulso_monetario", "Sin evaluación")
            momentum_nota = f"{momentum_3:+.2f} respecto a la última publicación"

        st.markdown(
            crear_tarjeta_inteligencia(
                "Impulso reciente",
                momentum_texto,
                momentum_nota
            ),
            unsafe_allow_html=True
        )

    st.info(analisis["summary"])

    componentes_score = analisis.get("componentes_score", {})
    if componentes_score:
        with st.expander("Ver desglose de la presión monetaria", expanded=False):
            pesos_score = analisis.get("pesos_score", {})
            score_base = analisis.get("macro_score_base")
            score_final = analisis.get("macro_score")
            relevancia = analisis.get("relevancia")
            tipo_indicador = analisis.get("tipo_indicador", "—").replace("_", " ").capitalize()
            banco_central = analisis.get("banco_central", "—")
            relevancia_label = analisis.get("relevancia_texto", "—")

            relevancia_porcentaje = (
                f"{relevancia * 100:.0f}%"
                if isinstance(relevancia, (int, float))
                else "—"
            )
            score_base_texto = (
                f"{score_base:.1f}/100"
                if isinstance(score_base, (int, float))
                else "—"
            )
            score_final_texto = (
                f"{score_final:.1f}/100"
                if isinstance(score_final, (int, float))
                else "—"
            )

            st.markdown(
                f"""
                <div class="score-detail-grid">
                    <div class="score-detail-card">
                        <div class="score-detail-label">Familia</div>
                        <div class="score-detail-value">{tipo_indicador}</div>
                    </div>
                    <div class="score-detail-card">
                        <div class="score-detail-label">Banco central</div>
                        <div class="score-detail-value">{banco_central}</div>
                    </div>
                    <div class="score-detail-card">
                        <div class="score-detail-label">Score base</div>
                        <div class="score-detail-value">{score_base_texto}</div>
                    </div>
                    <div class="score-detail-card">
                        <div class="score-detail-label">Relevancia</div>
                        <div class="score-detail-value">
                            {relevancia_label} · {relevancia_porcentaje}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )

            for nombre_componente, valor_componente in componentes_score.items():
                peso = float(pesos_score.get(nombre_componente, 0.0))
                contribucion = float(valor_componente) * peso
                porcentaje_barra = int(max(0, min(100, round(valor_componente))))

                st.markdown(
                    f"""
                    <div class="score-component">
                        <div class="score-component-header">
                            <div class="score-component-name">{nombre_componente}</div>
                            <div class="score-component-meta">
                                {valor_componente:.1f}/100 ·
                                Peso {peso * 100:.0f}% ·
                                Aporta {contribucion:.1f} pts
                            </div>
                        </div>
                        <div class="score-bar-track">
                            <div class="score-bar-fill"
                                 style="width: {porcentaje_barra}%;">
                            </div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

            st.markdown(
                f"""
                <div class="score-formula-note">
                    <strong>Resultado:</strong> los componentes generan un score base de
                    {score_base_texto}. Después, su distancia respecto al punto neutral
                    de 50 se ajusta según la relevancia de este indicador para
                    {banco_central}, dando un resultado final de
                    <strong>{score_final_texto}</strong>.
                </div>
                """,
                unsafe_allow_html=True
            )


except Exception as error:
    st.error("No se pudo cargar el dashboard.")
    st.exception(error)
