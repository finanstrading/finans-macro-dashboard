
"""MacroFX — Metals market and FRED data."""

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

from fx_rates import _token, _get_json, _as_series, _fred_usd, _symbols, _bond

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


def clean_daily(s):
    s = pd.to_numeric(s, errors="coerce").dropna().copy()
    idx = pd.DatetimeIndex(pd.to_datetime(s.index))
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    s.index = idx.normalize()
    return s.loc[~s.index.duplicated(keep="last")].sort_index()


@st.cache_data(ttl=900, show_spinner=False, max_entries=8)
def real_yields_eodhd(token):
    try:
        response = requests.get(
            "https://eodhd.com/api/ust/real-yield-rates",
            params={"api_token": token, "fmt": "json"}, timeout=(3, 8))
        response.raise_for_status()
        payload = response.json()
        rows = payload["data"]
        if not isinstance(rows, list) or len(rows) != int(payload["meta"]["total"]):
            raise ValueError("Respuesta incompleta")
        result = {}
        today = pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()
        for code, tenor in (("DFII5", "5Y"), ("DFII10", "10Y")):
            series = clean_daily(_as_series([r for r in rows if r.get("tenor") == tenor], "rate"))
            result[code] = series.loc[series.index <= today]
        return result, None
    except Exception as exc:
        return {}, type(exc).__name__


def extend_real_yield(fred, recent):
    fred, recent = clean_daily(fred), clean_daily(recent)
    overlap = pd.concat([fred.rename("fred"), recent.rename("recent")], axis=1, join="inner").dropna().tail(20)
    if len(overlap) < 5 or (overlap.fred - overlap.recent).abs().max() > 0.01000001:
        raise ValueError("Históricos incompatibles")
    return pd.concat([fred, recent.loc[recent.index > fred.index.max()]]).sort_index()


@st.cache_data(ttl=900, show_spinner=False, max_entries=8)
def _load_gold_data_cached(token):

    data, sources, errors = {}, {}, []

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

            s = clean_daily(market_series(symbol, token))

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

            s = clean_daily(yahoo_series(yahoo))

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

    # Same nominal bond series and cache as FX correlations.
    symbols = set()
    if token:
        try:
            symbols = _symbols(token)
        except Exception as exc:
            errors.append(f"Catálogo GBOND: {type(exc).__name__}; alternativa FRED.")
    for code, tenor in (("DGS2", 2), ("DGS10", 10)):
        if not symbols:
            continue
        try:
            s, err = _bond("USD", tenor, token, symbols)
            s = clean_daily(s)
            if s.empty:
                raise ValueError("Sin observaciones")
            data[code] = s
            sources[code] = f"EODHD · US{tenor}Y.GBOND · rendimiento nominal"
        except Exception as exc:
            errors.append(f"{code}: EODHD no disponible ({type(exc).__name__}); alternativa FRED.")

    # Official real yields and other macro series remain FRED.
    for code in FRED_IDS:
        if code in data:
            continue
        try:
            s = clean_daily(_fred_usd(code))
            if s.empty:
                raise ValueError("Sin observaciones")
            data[code] = s
            sources[code] = "FRED · " + code
        except Exception as exc:
            errors.append(f"FRED {code}: {type(exc).__name__}")

    # Preserve the FRED history; append only validated newer real yields.
    if token:
        real, error = real_yields_eodhd(token)
        if error:
            errors.append(f"Tipos reales EODHD: {error}; se conserva FRED.")
        for code, recent in real.items():
            if recent.empty:
                errors.append(f"{code}: EODHD sin observaciones; se conserva FRED.")
                continue
            if code not in data:
                data[code] = recent
                sources[code] = "EODHD · tipo real · histórico disponible limitado"
                continue
            original = data[code]
            if recent.index.max() <= original.index.max():
                continue
            try:
                merged = extend_real_yield(original, recent)
                data[code] = merged
                sources[code] = (f"FRED hasta {original.index.max():%Y-%m-%d} | "
                                 f"EODHD hasta {merged.index.max():%Y-%m-%d}")
            except ValueError:
                errors.append(f"{code}: históricos FRED/EODHD incompatibles; se conserva FRED.")
    return data, sources, errors


def load_gold_data():
    """Reuse a complete snapshot across Streamlit reruns, including failed sources."""
    return _load_gold_data_cached(_token())
