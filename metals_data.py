
"""MacroFX — Metals market and FRED data."""

from io import StringIO
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

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


# Treasury constant-maturity par yields, in percentage points (same units as FRED).
TREASURY_MAP = {
    "DFII5": ("daily_treasury_real_yield_curve", "5 YR"),
    "DFII10": ("daily_treasury_real_yield_curve", "10 YR"),
    "DGS2": ("daily_treasury_yield_curve", "2 YR"),
    "DGS10": ("daily_treasury_yield_curve", "10 YR"),
}


@st.cache_resource(show_spinner=False)
def _treasury_store():
    return {}, Lock()


def treasury_curve(kind, month):
    url = ("https://home.treasury.gov/resource-center/data-chart-center/"
           "interest-rates/daily-treasury-rates.csv/" + month + "/all")
    r = requests.get(url, params={"type": kind,
                     "field_tdr_date_value_month": month, "page": "", "_format": "csv"},
                     timeout=(3, 15))
    r.raise_for_status()
    df = pd.read_csv(StringIO(r.text))
    df.columns = df.columns.str.strip().str.upper()
    if "DATE" not in df.columns:
        raise ValueError("Treasury: CSV sin fecha")
    df.index = pd.to_datetime(df.pop("DATE"), errors="coerce").dt.normalize()
    df = df.loc[df.index.notna()]
    df = df.loc[df.index.strftime("%Y%m") == month]
    if df.empty:
        raise ValueError("Treasury: mes sin observaciones")
    return df.loc[~df.index.duplicated(keep="last")].sort_index()


def _fetch_curve(kind, months, store, lock):
    frames, warnings = [], []
    for month in months:
        key = (kind, month)
        try:
            df = treasury_curve(kind, month)
            with lock:
                old = store.get(key)
                if old is not None:
                    df = pd.concat([old, df]).sort_index(kind="stable")
                    df = df.loc[~df.index.duplicated(keep="last")]
                store[key] = df
        except Exception as exc:
            with lock:
                df = store.get(key)
            warnings.append(f"Tesoro ({kind}, {month}): {type(exc).__name__}; " +
                            ("se usa última descarga exitosa." if df is not None else "sin descarga disponible."))
        if df is not None:
            frames.append(df)
    return (pd.concat(frames).sort_index() if frames else None), warnings


def clean_daily(s):
    s = pd.to_numeric(s, errors="coerce").dropna().copy()
    idx = pd.DatetimeIndex(pd.to_datetime(s.index))
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    s.index = idx.normalize()
    return s.loc[~s.index.duplicated(keep="last")].sort_index()


def extend_fred(fred, treasury):
    fred, treasury = clean_daily(fred), clean_daily(treasury)
    if fred.empty or treasury.empty:
        raise ValueError("Serie vacía")
    newer = treasury.loc[treasury.index > fred.index.max()]
    if newer.empty:
        return fred, False
    overlap = pd.concat([fred.rename("fred"), treasury.rename("treasury")],
                        axis=1, join="inner").dropna().tail(20)
    # Require at least five shared dates and agreement within one basis point.
    if len(overlap) < 5 or (overlap.fred - overlap.treasury).abs().max() > 0.01000001:
        raise ValueError("Históricos no compatibles (mínimo 5 fechas, tolerancia 1 pb)")
    return pd.concat([fred, newer]).sort_index(), True


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

    # Indicadores macroeconómicos FRED

    for code in FRED_IDS:

        try:

            s = clean_daily(_fred_usd(code))

            if s.empty:
                raise ValueError("Sin observaciones")

            data[code] = s
            sources[code] = "FRED · " + code

        except Exception as exc:

            errors.append(
                f"FRED {code}: {type(exc).__name__}"
            )

    # Extend only compatible FRED series; never overwrite historical observations.
    today = pd.Timestamp.now(tz="America/New_York").tz_localize(None).normalize()
    # Include previous month only when needed for the five-date validation.
    months = [today.strftime("%Y%m")]
    if today.day <= 12:
        months.insert(0, (today - pd.DateOffset(months=1)).strftime("%Y%m"))
    store, lock = _treasury_store()
    kinds = sorted({kind for code, (kind, _) in TREASURY_MAP.items() if code in data})
    curves = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {kind: pool.submit(_fetch_curve, kind, months, store, lock) for kind in kinds}
        for kind, job in jobs.items():
            curves[kind], warnings = job.result()
            errors.extend(warnings)
    for code, (kind, column) in TREASURY_MAP.items():
        if code not in data:
            continue
        curve = curves[kind]
        if curve is None:
            continue
        try:
            treasury = clean_daily(curve[column])
            treasury = treasury.loc[treasury.index <= today]
            original = clean_daily(data[code])
            merged, extended = extend_fred(original, treasury)
            if extended:
                data[code] = merged
                sources[code] = (f"FRED · {code} hasta {original.index.max():%Y-%m-%d}"
                                 f" | Tesoro EE.UU. hasta {merged.index.max():%Y-%m-%d}")
        except Exception as exc:
            errors.append(f"{code}: extensión Tesoro no aplicada ({type(exc).__name__}: {exc}); se conserva FRED.")

    return data, sources, errors


def load_gold_data():
    """Reuse a complete snapshot across Streamlit reruns, including failed sources."""
    return _load_gold_data_cached(_token())
