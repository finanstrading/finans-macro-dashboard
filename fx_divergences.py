"""MacroFX | Divergencias de Tipos FX: diferenciales soberanos 2Y vs FX spot."""
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from fx_rates import load_rates

CURRENCIES = ('USD', 'EUR', 'GBP', 'AUD', 'NZD', 'CAD', 'JPY', 'CHF')
PERIODS = {'1M': 1, '3M': 3, '6M': 6, '1A': 12, '3A': 36, '5A': 60, 'Todo': None}


def _eodhd_key():
    for key in ('EODHD_API_KEY', 'EODHD_TOKEN', 'EODHD_API_TOKEN'):
        val = os.environ.get(key)
        if val and val.strip():
            return val.strip()
        try:
            val = st.secrets.get(key)
            if val and str(val).strip():
                return str(val).strip()
        except Exception:
            pass
    for section in ('Eodhd', 'eodhd', 'EODHD'):
        try:
            config = st.secrets.get(section)
            if config:
                for key in ('EODHD_API_KEY', 'EODHD_TOKEN', 'api_key', 'api_token'):
                    val = config.get(key)
                    if val and str(val).strip():
                        return str(val).strip()
        except Exception:
            pass
    return None


@st.cache_data(ttl=21600, show_spinner=False)
def _spot_eodhd(base, quote, token):
    """FX daily closes; inverted quote only if direct instrument unavailable."""
    import requests
    failures = []
    for symbol, invert in ((base + quote, False), (quote + base, True)):
        try:
            response = requests.get(
                f'https://eodhd.com/api/eod/{symbol}.FOREX',
                params={'api_token': token, 'fmt': 'json', 'order': 'a'},
                timeout=(5, 20),
            )
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, list):
                raise ValueError('Respuesta FX no contiene observaciones')
            df = pd.DataFrame(data)
            if not {'date', 'close'}.issubset(df.columns):
                raise ValueError('Sin columnas date/close')
            dates = pd.to_datetime(df['date'], errors='coerce')
            values = pd.to_numeric(df['close'], errors='coerce')
            series = pd.Series(values.to_numpy(dtype=float), index=pd.DatetimeIndex(dates))
            series = series.replace([np.inf, -np.inf], np.nan).dropna()
            series = series[series > 0].sort_index()
            series = series[~series.index.duplicated(keep='last')]
            if len(series) < 3:
                raise ValueError('Histórico FX insuficiente')
            if invert:
                series = 1.0 / series
            return series, f'EODHD · {symbol}.FOREX' + (' (invertido)' if invert else '')
        except Exception as exc:
            failures.append(f'{symbol}.FOREX: {type(exc).__name__}')
    raise RuntimeError('No se pudo descargar el precio FX: ' + ', '.join(failures) + '. Revisa acceso EODHD FOREX.')



@st.cache_data(ttl=21600, show_spinner=False)
def _spot_yahoo(base, quote):
    """Yahoo Finance daily FX closes using public chart endpoint; no API key."""
    import requests
    # Yahoo's canonical USD crosses are often XXX=X (e.g. JPY=X for USD/JPY).
    candidates = [f'{base}{quote}=X']
    if base == 'USD':
        candidates.insert(0, f'{quote}=X')
    if quote == 'USD':
        candidates.insert(0, f'{base}=X')
    # Inverted symbols are only used after direct quotes fail.
    inverse = [f'{quote}{base}=X']
    if quote == 'USD':
        inverse.insert(0, f'{base}=X')
    if base == 'USD':
        inverse.insert(0, f'{quote}=X')
    attempts = [(symbol, False) for symbol in dict.fromkeys(candidates)]
    attempts += [(symbol, True) for symbol in dict.fromkeys(inverse) if symbol not in candidates]
    failures = []
    for symbol, invert in attempts:
        for host in ('query1.finance.yahoo.com', 'query2.finance.yahoo.com'):
            try:
                response = requests.get(
                    f'https://{host}/v8/finance/chart/{symbol}',
                    params={'range': '10y', 'interval': '1d'},
                    headers={'User-Agent': 'Mozilla/5.0 (compatible; MacroFX/1.0)',
                             'Accept': 'application/json'},
                    timeout=(4, 12),
                )
                response.raise_for_status()
                payload = response.json().get('chart', {})
                result = payload.get('result') or []
                if not result:
                    raise ValueError(str(payload.get('error') or 'Sin resultados'))
                item = result[0]
                timestamps = item.get('timestamp') or []
                quotes = item.get('indicators', {}).get('quote') or []
                closes = quotes[0].get('close', []) if quotes else []
                if len(timestamps) != len(closes) or len(closes) < 3:
                    raise ValueError('Histórico insuficiente')
                dates = pd.to_datetime(timestamps, unit='s', utc=True).tz_localize(None).normalize()
                series = pd.Series(pd.to_numeric(closes, errors='coerce'), index=dates)
                series = series.replace([np.inf, -np.inf], np.nan).dropna()
                series = series[series > 0].sort_index()
                series = series[~series.index.duplicated(keep='last')]
                if len(series) < 3:
                    raise ValueError('Sin suficientes cierres válidos')
                if invert:
                    series = 1.0 / series
                return series, f'Yahoo Finance · {symbol}' + (' (invertido)' if invert else '')
            except (requests.RequestException, ValueError, KeyError, IndexError, TypeError) as exc:
                failures.append(f'{symbol} ({host}): {type(exc).__name__}')
    raise RuntimeError('Yahoo Finance no devolvió precios históricos: ' + ', '.join(failures[:6]))


def _spot_with_fallback(base, quote, token):
    """Prefer Yahoo to avoid EODHD Forex subscription requirements; EODHD backup."""
    errors = []
    try:
        return _spot_yahoo(base, quote)
    except Exception as exc:
        errors.append(str(exc))
    if token:
        try:
            return _spot_eodhd(base, quote, token)
        except Exception as exc:
            errors.append(str(exc))
    raise RuntimeError('No se pudo obtener el histórico FX. ' + ' | '.join(errors))

def _clean(series):
    s = pd.Series(series).copy()
    s.index = pd.to_datetime(s.index, errors='coerce')
    s = s.loc[~s.index.isna()]
    s.index = s.index.normalize()
    s = pd.to_numeric(s, errors='coerce').replace([np.inf, -np.inf], np.nan).dropna()
    return s.sort_index()[lambda x: ~x.index.duplicated(keep='last')]


def _prepare(yield_a, yield_b, fx):
    """Intersection of actual observation dates; no interpolation or future leakage."""
    a, b, spot = (_clean(s) for s in (yield_a, yield_b, fx))
    aligned = pd.concat({'A': a, 'B': b, 'FX': spot}, axis=1, join='inner').dropna()
    aligned = aligned[(aligned['FX'] > 0) & aligned['A'].between(-20, 100) & aligned['B'].between(-20, 100)]
    aligned['Spread_pp'] = aligned['A'] - aligned['B']
    aligned['Spread_pb'] = aligned['Spread_pp'] * 100
    return aligned


def _divergence(frame, lookback):
    if len(frame) <= lookback:
        return 'Datos insuficientes', None, None
    before, last = frame.iloc[-lookback - 1], frame.iloc[-1]
    delta_spread = float(last['Spread_pb'] - before['Spread_pb'])
    delta_fx = float((last['FX'] / before['FX'] - 1) * 100)
    if abs(delta_spread) < 1e-8 or abs(delta_fx) < 1e-8:
        return 'Sin divergencia definida', delta_spread, delta_fx
    if delta_spread > 0 and delta_fx < 0:
        return 'Divergencia alcista potencial para A/B', delta_spread, delta_fx
    if delta_spread < 0 and delta_fx > 0:
        return 'Divergencia bajista potencial para A/B', delta_spread, delta_fx
    return 'Movimiento alineado', delta_spread, delta_fx


def render_fx_divergences():
    st.markdown('### Divergencias de Tipos FX')
    st.caption('Bonos soberanos 2Y · diferencial A − B frente al precio de A/B · Finans Trading')
    col_a, col_b, col_period = st.columns([1, 1, 1])
    with col_a:
        base = st.selectbox('Divisa A (base)', CURRENCIES, index=0, key='fxdiv_base')
    with col_b:
        choices = [c for c in CURRENCIES if c != base]
        default = choices.index('JPY') if 'JPY' in choices else 0
        quote = st.selectbox('Divisa B (cotizada)', choices, index=default, key='fxdiv_quote')
    with col_period:
        period = st.selectbox('Período', list(PERIODS), index=3, key='fxdiv_period')
    display_mode = st.radio('Visualización', ('Doble eje: spread (pb) y FX', 'Comparación normalizada: cambios desde el inicio'), horizontal=True, key='fxdiv_mode')

    with st.spinner(f'Cargando bonos 2Y y {base}/{quote}...'):
        a_rates, a_sources, a_warnings = load_rates(base)
        b_rates, b_sources, b_warnings = load_rates(quote)
        bond_key = 'Bono 2Y (%)'
        if bond_key not in a_rates or bond_key not in b_rates or a_rates[bond_key].empty or b_rates[bond_key].empty:
            st.warning('Faltan datos de bonos soberanos 2Y para calcular el diferencial. Comprueba EODHD.')
            with st.expander('Diagnóstico'):
                st.write(a_warnings + b_warnings)
            return
        token = _eodhd_key()
        try:
            spot, spot_source = _spot_with_fallback(base, quote, token)
        except Exception as exc:
            st.error(str(exc))
            st.info('Los bonos 2Y están disponibles, pero no se obtuvo el histórico FX ni desde Yahoo Finance ni desde EODHD. Consulta los registros de Streamlit.')
            return

    frame = _prepare(a_rates[bond_key], b_rates[bond_key], spot)
    if frame.empty:
        st.warning('No existen fechas comunes entre ambos bonos 2Y y el par FX. No se interpolan datos.')
        return
    end = frame.index.max()
    months = PERIODS[period]
    if months is not None:
        frame = frame.loc[frame.index >= end - pd.DateOffset(months=months)]
    if len(frame) < 3:
        st.warning('No hay suficientes observaciones comunes en este período.')
        return

    latest = frame.iloc[-1]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f'Bono 2Y {base}', f"{latest['A']:.3f}%")
    c2.metric(f'Bono 2Y {quote}', f"{latest['B']:.3f}%")
    c3.metric(f'Spread {base} − {quote}', f"{latest['Spread_pb']:+.1f} pb")
    c4.metric(f'{base}/{quote}', f"{latest['FX']:.5f}")

    fig = make_subplots(specs=[[{'secondary_y': True}]])
    if display_mode.startswith('Doble eje'):
        spread_values = frame['Spread_pb']
        fx_values = frame['FX']
        left_label, right_label = 'Diferencial 2Y (puntos básicos)', f'{base}/{quote} (precio)'
    else:
        # Percentage change of the spread is unstable around zero; use basis-point
        # change from start on the left, FX percentage return on the right.
        spread_values = frame['Spread_pb'] - frame['Spread_pb'].iloc[0]
        fx_values = (frame['FX'] / frame['FX'].iloc[0] - 1) * 100
        left_label, right_label = 'Cambio diferencial desde inicio (pb)', f'Retorno {base}/{quote} desde inicio (%)'
    fig.add_trace(go.Scatter(x=frame.index, y=spread_values, mode='lines', name=f'Spread 2Y {base} − {quote}', line=dict(color='#C9A227', width=3), hovertemplate='%{x|%d/%m/%Y}<br>%{y:.2f}<extra>%{fullData.name}</extra>'), secondary_y=False)
    fig.add_trace(go.Scatter(x=frame.index, y=fx_values, mode='lines', name=f'{base}/{quote}', line=dict(color='#2563EB', width=2.5), hovertemplate='%{x|%d/%m/%Y}<br>%{y:.3f}<extra>%{fullData.name}</extra>'), secondary_y=True)
    if display_mode.startswith('Doble eje'):
        fig.add_hline(y=0, line_dash='dot', line_color='#9CA3AF', opacity=0.65)
    fig.update_layout(height=560, template='plotly_white', hovermode='x unified', title=f'{base}/{quote} · diferencial 2Y frente al tipo de cambio', legend=dict(orientation='h', y=-0.18), margin=dict(l=25, r=25, t=60, b=35))
    fig.update_yaxes(title_text=left_label, secondary_y=False)
    fig.update_yaxes(title_text=right_label, secondary_y=True)
    st.plotly_chart(fig, use_container_width=True, key=f'fxdiv_chart_{base}_{quote}')

    st.markdown('#### Lectura de divergencia')
    window = st.select_slider('Ventana de comparación (observaciones comunes)', options=[5, 10, 20, 40, 60, 90], value=20, key='fxdiv_window')
    label, delta_spread, delta_fx = _divergence(frame, window)
    if delta_spread is not None:
        st.info(f'**{label}** · Spread: {delta_spread:+.1f} pb · {base}/{quote}: {delta_fx:+.2f}% en {window} observaciones comunes.')
    else:
        st.caption('Necesitas más observaciones para calcular la divergencia de la ventana elegida.')

    returns = frame['FX'].pct_change()
    spread_changes = frame['Spread_pb'].diff()
    valid = pd.concat([returns.rename('FX'), spread_changes.rename('Spread')], axis=1).dropna()
    if len(valid) >= 20 and valid['FX'].std() > 0 and valid['Spread'].std() > 0:
        corr = valid['FX'].corr(valid['Spread'])
        st.caption(f'Correlación de cambios diarios (retorno FX vs variación spread): {corr:+.2f} · {len(valid)} observaciones.')
    st.caption(f'Fuentes: {base} 2Y: {a_sources.get(bond_key, "N/D")} · {quote} 2Y: {b_sources.get(bond_key, "N/D")} · FX: {spot_source}. Última fecha común: {end:%d/%m/%Y}. Sin interpolación.')
    st.caption('Lectura exploratoria, no señal de trading. Los diferenciales 2Y reflejan expectativas de tipos y primas de mercado; otros factores también afectan al FX.')
    with st.expander('Descargar datos y revisar observaciones'):
        output = frame.rename(columns={'A': f'{base}_2Y_pct', 'B': f'{quote}_2Y_pct', 'FX': f'{base}{quote}'})
        st.download_button('Descargar CSV', output.to_csv(index_label='Fecha').encode('utf-8'), file_name=f'divergencia_2Y_{base}{quote}.csv', mime='text/csv', key='fxdiv_download')
        st.dataframe(output.tail(100).sort_index(ascending=False), use_container_width=True)
