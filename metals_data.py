"""Read-only daily market and FRED data for MacroFX metals."""
import pandas as pd
import requests
import streamlit as st
from fx_rates import _token, _get_json, _as_series, _fred_usd

FRED_IDS = ('DFII10','DFII5','DGS10','DGS2','T10YIE','T5YIE','WALCL','WDTGAL','RRPONTSYD','WRBWFRBL','M2SL')

@st.cache_data(ttl=3600, show_spinner=False)
def market_series(symbol, token):
    rows = _get_json(f'https://eodhd.com/api/eod/{symbol}', {'api_token':token,'fmt':'json','order':'a','from':(pd.Timestamp.today()-pd.DateOffset(years=6)).strftime('%Y-%m-%d')})
    return _as_series(rows,'close')

def load_gold_data():
    data, sources, errors = {}, {}, []
    token = _token()
    for name, default in [('Oro','XAUUSD.FOREX'),('DXY','DXY.INDX')]:
        try:
            symbol = str(st.secrets.get('METALS_'+('GOLD' if name=='Oro' else 'DXY')+'_SYMBOL',default))
        except Exception:
            symbol = default
        try:
            if not token: raise ValueError('Sin credencial')
            s = market_series(symbol,token)
            if s.empty: raise ValueError('Sin observaciones')
            data[name], sources[name] = s, 'EODHD · '+symbol
        except Exception as exc:
            if isinstance(exc, requests.HTTPError):
                status = exc.response.status_code if exc.response is not None else None
                hints = {401: 'revisar autenticación', 403: 'revisar permisos del plan o acceso al mercado', 404: 'revisar símbolo y endpoint', 429: 'límite de peticiones', 400: 'revisar parámetros'}
                errors.append(f'{name} ({symbol}): HTTP {status}; {hints.get(status, "revisar proveedor")}.')
            elif not token:
                errors.append(f'{name} ({symbol}): credencial EODHD no detectada.')
            elif isinstance(exc, ValueError):
                errors.append(f'{name} ({symbol}): respuesta inválida o sin observaciones.')
            else:
                errors.append(f'{name} ({symbol}): {type(exc).__name__}; revisar conexión.')
    for code in FRED_IDS:
        try:
            s = _fred_usd(code)
            if s.empty: raise ValueError('Sin observaciones')
            data[code], sources[code] = s, 'FRED · '+code
        except Exception as exc:
            errors.append(f'FRED {code}: {type(exc).__name__}')
    return data,sources,errors
