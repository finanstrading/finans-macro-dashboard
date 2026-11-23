"""MacroFX: tipos oficiales y rentabilidades soberanas, fuentes verificables."""
import os
import io
import pandas as pd
import requests
import streamlit as st

COUNTRIES = {'USD':'US','EUR':'DE','GBP':'UK','AUD':'AU','NZD':'NZ','CAD':'CA','JPY':'JP','CHF':'SW'}
POLICY_CODES = {'USD':'FED_TARGET_UPPER','EUR':'ECB_DFR','GBP':'BOE_BANK_RATE'}
# Códigos candidatos EODHD: se validan contra el campo `code` de cada registro.
# No se sustituye un tipo oficial por un tipo interbancario o de mercado.
POLICY_CANDIDATES = {
    'AUD': ('RBA_CASH_RATE', 'RBA_CASH_RATE_TARGET', 'RBA_TARGET_CASH_RATE'),
    'NZD': ('RBNZ_OCR', 'RBNZ_OFFICIAL_CASH_RATE'),
    'CAD': ('BOC_OVERNIGHT_RATE', 'BOC_TARGET_OVERNIGHT', 'BOC_POLICY_RATE'),
    'JPY': ('BOJ_POLICY_RATE', 'BOJ_SHORT_TERM_POLICY_RATE'),
    'CHF': ('SNB_POLICY_RATE', 'SNB_KEY_POLICY_RATE'),
}

POLICY_HINTS = {
    'USD':['Fed Funds Rate','Federal Funds Rate','Fed Funds Target'],
    'EUR':['ECB Deposit Rate','Deposit Facility Rate','ECB Interest Rate'],
    'GBP':['Bank Rate','BoE Interest Rate','BOE Bank Rate'],
    'AUD':['RBA Cash Rate','Cash Rate Target','Interest Rate'],
    'NZD':['Official Cash Rate','RBNZ OCR','OCR'],
    'CAD':['BoC Policy Rate','Overnight Rate','Interest Rate'],
    'JPY':['BoJ Policy Rate','BOJ Interest Rate','Policy Rate'],
    'CHF':['SNB Policy Rate','SNB Interest Rate','Policy Rate'],
}

def _token():
    """Busca la clave sin ocultar un secreto válido por errores en otro origen."""
    for key in ('EODHD_API_KEY', 'EODHD_TOKEN', 'EODHD_API_TOKEN'):
        value = os.environ.get(key)
        if value and value.strip():
            return value.strip()
    for key in ('EODHD_API_KEY', 'EODHD_TOKEN', 'EODHD_API_TOKEN'):
        try:
            value = st.secrets.get(key)
            if value and str(value).strip():
                return str(value).strip()
        except Exception:
            continue
    for section in ('Eodhd', 'eodhd', 'EODHD'):
        try:
            cfg = st.secrets.get(section)
            if cfg:
                for key in ('EODHD_API_KEY', 'EODHD_TOKEN', 'api_key', 'api_token'):
                    value = cfg.get(key)
                    if value and str(value).strip():
                        return str(value).strip()
        except Exception:
            continue
    return None


def credential_status():
    """Diagnóstico seguro: jamás devuelve ni imprime el token."""
    return 'EODHD: credencial detectada' if _token() else 'EODHD: credencial no detectada en este despliegue'

@st.cache_data(ttl=21600, show_spinner=False)
def _get_json(url, params):
    resp = requests.get(url, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and ('error' in data or 'message' in data and 'data' not in data):
        raise ValueError(str(data.get('error') or data.get('message'))[:160])
    return data

@st.cache_data(ttl=86400, show_spinner=False)
def _symbols(token):
    data = _get_json('https://eodhd.com/api/exchange-symbol-list/GBOND', {'api_token':token,'fmt':'json'})
    return {str(row.get('Code','')).upper() for row in data if isinstance(row,dict)}

def _as_series(rows, field):
    df = pd.DataFrame(rows)
    if df.empty or 'date' not in df or field not in df:
        return pd.Series(dtype=float)
    df['date'] = pd.to_datetime(df['date'],errors='coerce')
    df[field] = pd.to_numeric(df[field],errors='coerce')
    df = df.dropna(subset=['date',field]).sort_values('date').drop_duplicates('date',keep='last')
    return pd.Series(df[field].to_numpy(dtype=float),index=pd.DatetimeIndex(df['date']),dtype=float)

def _bond(currency, years, token, symbols):
    ticker = f'{COUNTRIES[currency]}{years}Y'
    if ticker not in symbols:
        return pd.Series(dtype=float), f'{ticker}.GBOND no figura en el catálogo de EODHD'
    try:
        rows = _get_json(f'https://eodhd.com/api/eod/{ticker}.GBOND', {'api_token':token,'fmt':'json','order':'a'})
        return _as_series(rows,'close'), None
    except Exception as exc:
        return pd.Series(dtype=float), f'{ticker}.GBOND: {type(exc).__name__} (revisar endpoint, permisos o red)'

@st.cache_data(ttl=21600,show_spinner=False)
def _policy_eodhd(currency, token):
    code = POLICY_CODES[currency]
    out = []
    offset = 0
    while offset < 5000:
        data = _get_json('https://eodhd.com/api/rates/policy-rates', {
            'api_token':token,'filter[code]':code,'page[limit]':100,'page[offset]':offset})
        batch = data.get('data',[]) if isinstance(data,dict) else []
        out.extend(row for row in batch if row.get('code')==code)
        total = data.get('meta',{}).get('total',len(out))
        offset += len(batch)
        if not batch or offset >= total: break
    return _as_series(out,'rate')

@st.cache_data(ttl=21600, show_spinner=False)
def _policy_eodhd_candidate(code, token):
    """Consulta un código concreto; solo acepta observaciones con código idéntico."""
    rows = []
    offset = 0
    while offset < 5000:
        data = _get_json('https://eodhd.com/api/rates/policy-rates', {
            'api_token': token, 'filter[code]': code,
            'page[limit]': 100, 'page[offset]': offset})
        batch = data.get('data', []) if isinstance(data, dict) else []
        if not isinstance(batch, list):
            break
        matching = [r for r in batch if isinstance(r, dict) and
                    str(r.get('code', '')).upper() == code.upper()]
        rows.extend(matching)
        offset += len(batch)
        if not batch or offset >= data.get('meta', {}).get('total', offset):
            break
    return _as_series(rows, 'rate')


@st.cache_data(ttl=21600, show_spinner=False)
def _policy_canada_boc():
    """Banco de Canadá, serie oficial V122514: objetivo del tipo overnight."""
    url = 'https://www.bankofcanada.ca/valet/observations/V122514/json'
    data = _get_json(url, {'start_date': '2000-01-01'})
    observations = data.get('observations', []) if isinstance(data, dict) else []
    rows = []
    for obs in observations:
        value = obs.get('V122514', {})
        if isinstance(value, dict) and value.get('v') is not None:
            rows.append({'date': obs.get('d'), 'rate': value['v']})
    return _as_series(rows, 'rate')



@st.cache_data(ttl=21600, show_spinner=False)
def _policy_australia_rba():
    """RBA official cash rate TARGET decision history, not observed overnight rate."""
    from bs4 import BeautifulSoup
    url = 'https://www.rba.gov.au/statistics/cash-rate/'
    response = requests.get(url, timeout=25, headers={'User-Agent': 'MacroFX/1.0 (public statistics)'})
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    rows = []
    # Select the table by its header text rather than assuming a fixed HTML position.
    for table in soup.find_all('table'):
        headers = ' '.join(th.get_text(' ', strip=True).lower() for th in table.find_all('th'))
        if not ('effective date' in headers and 'cash rate target' in headers):
            continue
        for tr in table.find_all('tr'):
            cells = tr.find_all(['td', 'th'])
            if len(cells) < 3:
                continue
            date_text = cells[0].get_text(' ', strip=True)
            target_text = cells[2].get_text(' ', strip=True).replace('%', '').replace(',', '')
            date = pd.to_datetime(date_text, errors='coerce', dayfirst=True)
            value = pd.to_numeric(target_text, errors='coerce')
            if pd.notna(date) and pd.notna(value) and -5 < value < 30:
                rows.append({'date': date, 'rate': float(value)})
    if not rows:
        raise ValueError('RBA: no se encontró la tabla oficial de decisiones con fecha y objetivo')
    series = _as_series(rows, 'rate')
    if series.empty:
        raise ValueError('RBA: tabla sin observaciones válidas')
    return series



@st.cache_data(ttl=21600, show_spinner=False)
def _policy_bis(currency):
    """BIS CBPOL daily policy rates (central-bank-validated series).

    Source: https://data.bis.org/static/bulk/WS_CBPOL_csv_flat.zip
    Uses the published flat CSV rather than unverified vendor ticker guesses.
    BIS historical series may splice different monetary-policy instruments.
    """
    import zipfile
    from io import BytesIO

    area = {'CHF': 'CH', 'NZD': 'NZ', 'JPY': 'JP'}[currency]
    url = 'https://data.bis.org/static/bulk/WS_CBPOL_csv_flat.zip'
    response = requests.get(url, timeout=75, headers={
        'User-Agent': 'MacroFX/1.0 (research dashboard; public BIS data)',
        'Accept': 'application/zip,application/octet-stream,*/*',
    })
    response.raise_for_status()
    if not zipfile.is_zipfile(BytesIO(response.content)):
        raise ValueError('BIS: la descarga no es un archivo ZIP válido')

    frames = []
    with zipfile.ZipFile(BytesIO(response.content)) as archive:
        members = [n for n in archive.namelist() if n.lower().endswith('.csv')]
        if not members:
            raise ValueError('BIS: no se encontró un CSV en el archivo')
        for member in members:
            with archive.open(member) as handle:
                for chunk in pd.read_csv(handle, chunksize=100000, low_memory=False,
                                         on_bad_lines='skip'):
                    chunk.columns = [str(c).strip().upper() for c in chunk.columns]
                    required = {'REF_AREA', 'FREQ', 'TIME_PERIOD', 'OBS_VALUE'}
                    if not required.issubset(chunk.columns):
                        continue
                    selected = chunk.loc[
                        chunk['REF_AREA'].astype(str).str.upper().eq(area)
                        & chunk['FREQ'].astype(str).str.upper().eq('D')
                    ].copy()
                    if selected.empty:
                        continue
                    # The BIS dataset can contain more than one rate per country;
                    # prefer the main policy rate series when metadata identifies it.
                    if 'COLLECTION' in selected.columns:
                        main = selected['COLLECTION'].astype(str).str.upper().eq('A')
                        if main.any():
                            selected = selected.loc[main]
                    frames.append(selected)
    if not frames:
        raise ValueError(f'BIS: no hay observaciones diarias para {currency}')
    data = pd.concat(frames, ignore_index=True)
    # Identify a single coherent BIS time series rather than mixing instruments.
    # Full series key is the strongest discriminator when present.
    key_cols = [c for c in ('KEY', 'SERIES_KEY', 'COLLECTION', 'UNIT_MEASURE',
                             'UNIT', 'DECIMALS') if c in data.columns]
    if 'KEY' in key_cols:
        key_cols = ['KEY']
    elif 'SERIES_KEY' in key_cols:
        key_cols = ['SERIES_KEY']
    else:
        key_cols = [c for c in key_cols if c not in ('DECIMALS',)]
    if key_cols:
        groups = data.groupby(key_cols, dropna=False, sort=False)
        # Main daily policy series is expected to have the longest history.
        data = max((g for _, g in groups), key=len)
    dates = pd.to_datetime(data['TIME_PERIOD'], errors='coerce')
    values = pd.to_numeric(data['OBS_VALUE'], errors='coerce')
    clean = pd.DataFrame({'date': dates, 'rate': values}).dropna()
    clean = clean[clean['rate'].between(-20, 100)]
    series = _as_series(clean.to_dict('records'), 'rate')
    if len(series) < 10:
        raise ValueError(f'BIS: serie insuficiente para {currency}')
    return series

def _policy_sheet(currency, df, convert_values):
    if df is None or 'Fecha' not in df: return pd.Series(dtype=float)
    for hint in POLICY_HINTS[currency]:
        matches = [c for c in df.columns if str(c).strip().lower()==hint.lower()]
        if matches:
            name=matches[0]
            dates=pd.to_datetime(df['Fecha'],errors='coerce')
            values=pd.to_numeric(convert_values(df[name]),errors='coerce')
            result=pd.DataFrame({'date':dates,'value':values}).dropna().sort_values('date').drop_duplicates('date',keep='last')
            return pd.Series(result['value'].to_numpy(dtype=float),index=pd.DatetimeIndex(result['date']))
    return pd.Series(dtype=float)


@st.cache_data(ttl=21600, show_spinner=False)
def _fred_usd(series_id):
    """Public FRED CSV fallback for USD; values are percentages, not prices."""
    url = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}'
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = pd.read_csv(io.StringIO(resp.text))
    if data.empty or series_id not in data.columns:
        return pd.Series(dtype=float)
    date_col = data.columns[0]
    return _as_series(data.rename(columns={date_col: 'date', series_id: 'value'}).to_dict('records'), 'value')

def load_rates(currency, sheet_df=None, convert_values=None):
    """Return (series_by_name, source_by_name, warnings). Never fabricates missing rates."""
    result, sources, warnings = {}, {}, []
    warnings.append(credential_status())
    token = _token()
    if token:
        try:
            symbols = _symbols(token)
        except Exception as exc:
            symbols=set()
            warnings.append(f'Catálogo GBOND: {type(exc).__name__} (revisar permisos, endpoint o red)')
        for tenor in (2,10):
            label=f'Bono {tenor}Y (%)'
            s,err=_bond(currency,tenor,token,symbols) if symbols else (pd.Series(dtype=float),'Catálogo no disponible')
            if not s.empty:
                result[label]=s; sources[label]=f'EODHD · {COUNTRIES[currency]}{tenor}Y.GBOND'
            elif err: warnings.append(err)
        if currency in POLICY_CODES:
            try:
                s=_policy_eodhd(currency,token)
                if not s.empty:
                    result['Tipo oficial (%)']=s
                    sources['Tipo oficial (%)']=f'EODHD · {POLICY_CODES[currency]}'
            except Exception as exc:
                warnings.append(f'Tipo oficial EODHD: {type(exc).__name__} (revisar permisos y respuesta)')
    else:
        warnings.append('EODHD: credencial no detectada en este despliegue. Comprueba los secretos de la app que estás visualizando.')
    # Extensión para los cinco bancos centrales restantes.
    # EODHD se consulta con códigos candidatos estrictamente verificados.
    if 'Tipo oficial (%)' not in result and currency in POLICY_CANDIDATES and token:
        for code in POLICY_CANDIDATES[currency]:
            try:
                series = _policy_eodhd_candidate(code, token)
                if not series.empty:
                    result['Tipo oficial (%)'] = series
                    sources['Tipo oficial (%)'] = f'EODHD · {code}'
                    break
            except Exception as exc:
                warnings.append(f'EODHD tipo oficial {code}: {type(exc).__name__}')
    # Fuente oficial alternativa, sin credenciales, para AUD.
    if 'Tipo oficial (%)' not in result and currency == 'AUD':
        try:
            series = _policy_australia_rba()
            if not series.empty:
                result['Tipo oficial (%)'] = series
                sources['Tipo oficial (%)'] = 'Reserve Bank of Australia · Cash Rate Target'
        except Exception as exc:
            warnings.append(f'RBA Cash Rate Target: {type(exc).__name__}: {str(exc)[:110]}')
    # Fuente oficial alternativa, sin credenciales, para CAD.
    if 'Tipo oficial (%)' not in result and currency == 'CAD':
        try:
            series = _policy_canada_boc()
            if not series.empty:
                result['Tipo oficial (%)'] = series
                sources['Tipo oficial (%)'] = 'Bank of Canada · V122514'
        except Exception as exc:
            warnings.append(f'Banco de Canadá V122514: {type(exc).__name__}')
    # BIS: fuente verificable de tipos de política monetaria para las tres
    # divisas pendientes. Se ejecuta si EODHD no ofrece una serie válida.
    if 'Tipo oficial (%)' not in result and currency in ('CHF', 'NZD', 'JPY'):
        try:
            series = _policy_bis(currency)
            if not series.empty:
                result['Tipo oficial (%)'] = series
                sources['Tipo oficial (%)'] = f'BIS · CBPOL · {currency} · diario'
        except Exception as exc:
            warnings.append(f'BIS CBPOL {currency}: {type(exc).__name__}: {str(exc)[:135]}')
    if currency == 'USD':
        for label, fred_id in [('Tipo oficial (%)', 'DFEDTARU'), ('Bono 2Y (%)', 'DGS2'), ('Bono 10Y (%)', 'DGS10')]:
            if label not in result:
                try:
                    series = _fred_usd(fred_id)
                    if not series.empty:
                        result[label] = series
                        sources[label] = f'FRED · {fred_id}'
                except Exception as exc:
                    warnings.append(f'FRED {fred_id}: {exc}')
    if 'Tipo oficial (%)' not in result and convert_values is not None:
        s=_policy_sheet(currency,sheet_df,convert_values)
        if not s.empty:
            result['Tipo oficial (%)']=s; sources['Tipo oficial (%)']='Google Sheets · histórico MacroFX'
    if 'Tipo oficial (%)' not in result:
        warnings.append(f'No hay una serie verificada de tipo oficial para {currency}.')
    return result,sources,warnings
