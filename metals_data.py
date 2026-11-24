
"""MacroFX — Metals market and FRED data."""

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

from fx_rates import _token, _get_json, _as_series, _fred_usd

FRED_IDS = (
    "DFII10", "DFII5", "DGS10", "DGS2",
    "T10YIE", "T5YIE", "WALCL", "WDTGAL",
    "RRPONTSYD", "WRBWFRBL", "M2SL"
)


@st.cache_data(ttl=3600, show_spinner=False)
def market_series(symbol, token):

    rows = _get_json(
        f"https://eodhd.com/api/eod/{symbol}",
        {
            "api_token": token,
            "fmt": "json",
            "order": "a",
            "from": (
                pd.Timestamp.today()
                - pd.DateOffset(years=6)
            ).strftime("%Y-%m-%d")
        }
    )

    return _as_series(rows, "close")


@st.cache_data(ttl=3600, show_spinner=False)
def yahoo_series(symbol):

    df = yf.Ticker(symbol).history(
        period="5y",
        interval="1d",
        auto_adjust=False,
        timeout=15
    )

    if df.empty or "Close" not in df.columns:
        raise ValueError("Yahoo Finance: sin datos")

    s = pd.to_numeric(
        df["Close"], errors="coerce"
    ).dropna()

    s.index = pd.DatetimeIndex(s.index)

    if s.index.tz is not None:
        s.index = s.index.tz_localize(None)

    s.index = s.index.normalize()

    return s[~s.index.duplicated(
        keep="last"
    )].sort_index()


def load_gold_data():

    data, sources, errors = {}, {}, []

    token = _token()

    assets = [
        ("Oro", "XAUUSD.FOREX", "GC=F", "GOLD"),
        ("DXY", "DXY.INDX", "DX-Y.NYB", "DXY")
    ]

    for name, default, yahoo, secret in assets:

        try:
            symbol = str(
                st.secrets.get(
                    "METALS_" + secret + "_SYMBOL",
                    default
                )
            )
        except Exception:
            symbol = default

        # Fuente principal: EODHD

        try:

            if not token:
                raise ValueError("Sin credencial")

            s = market_series(symbol, token)

            if s.empty:
                raise ValueError("Sin observaciones")

            data[name] = s
            sources[name] = "EODHD · " + symbol

            continue

        except Exception as exc:

            if isinstance(exc, requests.HTTPError):
                status = (
                    exc.response.status_code
                    if exc.response is not None
                    else "desconocido"
                )
                reason = f"HTTP {status}"
            else:
                reason = type(exc).__name__

        # Fuente alternativa: Yahoo Finance

        try:

            s = yahoo_series(yahoo)

            if s.empty:
                raise ValueError("Sin observaciones")

            data[name] = s

            label = (
                "Futuros de oro"
                if name == "Oro"
                else "Índice dólar"
            )

            sources[name] = (
                f"Yahoo Finance · {yahoo} · {label}"
            )

            errors.append(
                f"{name}: EODHD no disponible "
                f"({reason}). "
                f"Fuente alternativa activa: {yahoo}."
            )

        except Exception as exc:

            errors.append(
                f"{name}: EODHD ({reason}) y "
                f"Yahoo Finance ({type(exc).__name__}) "
                "no disponibles."
            )

    # Indicadores macroeconómicos FRED

    for code in FRED_IDS:

        try:

            s = _fred_usd(code)

            if s.empty:
                raise ValueError("Sin observaciones")

            data[code] = s
            sources[code] = "FRED · " + code

        except Exception as exc:

            errors.append(
                f"FRED {code}: {type(exc).__name__}"
            )

    return data, sources, errors
