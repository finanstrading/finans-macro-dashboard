"""MacroFX | Divergencias de Tipos FX: diferenciales soberanos 2Y vs FX spot."""
import os
from itertools import combinations
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


def _directional_bias(frame, window):
    """Descriptive 2Y directional bias; not a calibrated forecast."""
    if len(frame) <= window:
        return None
    spread = frame['Spread_pb'].astype(float)
    fx = frame['FX'].astype(float)
    change_pb = float(spread.iloc[-1] - spread.iloc[-window - 1])
    fx_return = float((fx.iloc[-1] / fx.iloc[-window - 1] - 1) * 100)

    # Correlate changes, not nonstationary levels; use a trailing window.
    changes = pd.DataFrame({'spread': spread.diff(), 'fx': fx.pct_change()}).dropna().tail(90)
    corr = float(changes['spread'].corr(changes['fx'])) if len(changes) >= 30 and changes['spread'].std() > 0 and changes['fx'].std() > 0 else np.nan

    # Compare the current move with past moves over the SAME observation horizon.
    historical = spread.diff(window).abs().dropna()
    reference = float(historical.median()) if len(historical) >= 10 else np.nan
    if np.isfinite(reference) and reference > 0:
        strength_ratio = abs(change_pb) / reference
    else:
        strength_ratio = np.nan

    # Only present a directional reading if the observed relation is positive.
    # A negative/weak relationship invalidates a simple carry-spread interpretation.
    if not np.isfinite(corr) or corr < 0.2:
        bias = 'Neutral / relación no confirmada'
        reason = 'La correlación reciente no respalda suficientemente la lectura direccional basada en el spread.'
    elif not np.isfinite(strength_ratio) or strength_ratio < 0.5:
        bias = 'Neutral / cambio de spread pequeño'
        reason = 'El movimiento reciente del diferencial es pequeño respecto a su historial comparable.'
    elif change_pb > 0:
        bias = 'Alcista para A/B'
        reason = 'El diferencial 2Y se ha ampliado a favor de la divisa base.'
    elif change_pb < 0:
        bias = 'Bajista para A/B'
        reason = 'El diferencial 2Y se ha reducido en contra de la divisa base.'
    else:
        bias = 'Neutral'
        reason = 'El diferencial no ha cambiado.'

    if bias.startswith(('Alcista', 'Bajista')):
        if corr >= 0.6 and strength_ratio >= 1.5:
            strength = 'Alta'
        elif corr >= 0.35 and strength_ratio >= 1:
            strength = 'Media'
        else:
            strength = 'Baja'
    else:
        strength = 'No aplicable'
    divergence = ('FX no acompaña al spread' if change_pb * fx_return < 0 else 'FX acompaña al spread') if abs(change_pb) > 1e-9 and abs(fx_return) > 1e-9 else 'Sin movimiento concluyente'
    return dict(bias=bias, strength=strength, reason=reason, corr=corr,
                spread_change=change_pb, fx_return=fx_return, divergence=divergence,
                relative_strength=strength_ratio, observations=len(changes))


def _scan_g10_pairs(window=20, months=12):
    """Escaneo bajo demanda: 8 series de bonos, 28 históricos FX, sin duplicar pares."""
    # Orden de cotización convencional para que EUR/USD, GBP/USD, USD/JPY, etc.
    # aparezcan con la orientación más habitual.
    priority = ('EUR', 'GBP', 'AUD', 'NZD', 'USD', 'CAD', 'CHF', 'JPY')
    bond_key = 'Bono 2Y (%)'
    bonds = {}
    failures = []
    for currency in priority:
        try:
            rates, _, warnings = load_rates(currency)
            series = rates.get(bond_key)
            if series is None or len(series) == 0:
                failures.append(f'{currency}: bono 2Y no disponible')
            else:
                bonds[currency] = series
        except Exception as exc:
            failures.append(f'{currency}: {type(exc).__name__} al cargar bono')
    token = _eodhd_key()
    rows = []
    for a, b in combinations(priority, 2):
        pair = a + '/' + b
        if a not in bonds or b not in bonds:
            failures.append(f'{pair}: falta bono 2Y')
            continue
        try:
            spot, source = _spot_with_fallback(a, b, token)
            frame = _prepare(bonds[a], bonds[b], spot)
            if frame.empty:
                raise ValueError('sin fechas comunes')
            end = frame.index.max()
            frame = frame.loc[frame.index >= end - pd.DateOffset(months=months)]
            signal = _directional_bias(frame, window)
            if signal is None:
                raise ValueError('histórico común insuficiente')
            change, fx_change = signal['spread_change'], signal['fx_return']
            corr, ratio = signal['corr'], signal['relative_strength']
            direction = ('Alcista' if change > 0 else 'Bajista') if abs(change) > 1e-8 else 'Neutral'
            divergence = 'No' if change * fx_change >= 0 or abs(change) < 1e-8 or abs(fx_change) < 1e-8 else 'Sí'
            if divergence == 'Sí':
                kind = direction
            else:
                kind = 'Alineado'
            if not np.isfinite(corr) or corr < 0.2 or not np.isfinite(ratio):
                relevance = 'No confirmada'
            elif ratio < 0.5:
                relevance = 'Baja'
            elif corr >= 0.6 and ratio >= 1.5:
                relevance = 'Alta'
            elif corr >= 0.35 and ratio >= 1.0:
                relevance = 'Media'
            else:
                relevance = 'Baja'
            # Ordena por evidencia exploratoria; no representa probabilidad.
            score = float(max(corr, 0) * ratio) if np.isfinite(corr) and np.isfinite(ratio) else np.nan
            rows.append({
                'Par': pair, 'Divergencia': kind, 'Presión 2Y': direction,
                'Δ spread (pb)': round(change, 1),
                'Δ FX (%)': round(fx_change, 2),
                'Corr. 90d': round(corr, 2) if np.isfinite(corr) else np.nan,
                'Magnitud relativa': round(ratio, 2) if np.isfinite(ratio) else np.nan,
                'Índice exploratorio': round(score, 3) if np.isfinite(score) else np.nan,
                'Última fecha': end.date().isoformat(), 'Fuente FX': source,
            })
        except Exception as exc:
            failures.append(f'{pair}: {type(exc).__name__} ({str(exc)[:80]})')
    return pd.DataFrame(rows), failures


def _render_g10_scanner():
    st.markdown('#### Escáner de divergencias G10 · 28 pares')
    st.caption('Escaneo bajo demanda: últimos 12 meses, ventana de 20 observaciones comunes. '
               'Se muestran magnitudes relativas y se priorizan divergencias; el orden no es una probabilidad de éxito.')
    if st.button('Actualizar ranking de 28 pares', key='fxdiv_scan_button'):
        with st.spinner('Consultando bonos 2Y y los históricos FX de hasta 28 pares; puede tardar...'):
            ranking, errors = _scan_g10_pairs()
        st.session_state['fxdiv_rank_data'] = ranking
        st.session_state['fxdiv_rank_errors'] = errors
    ranking = st.session_state.get('fxdiv_rank_data')
    if ranking is None:
        st.info('Pulsa «Actualizar ranking de 28 pares» para ejecutar el escaneo. '
                'No se realizan 28 solicitudes cada vez que cambias el gráfico.')
        return
    if ranking.empty:
        st.warning('No se pudieron calcular pares. Revisa el diagnóstico de fuentes.')
    else:
        f1, f3 = st.columns([2, 1])
        with f1:
            filter_div = st.selectbox('Divergencia', ['Todas', 'Alcista', 'Bajista', 'Alineado'], key='fxdiv_rank_div')
        with f3:
            only_recent = st.checkbox('Solo datos recientes (≤ 7 días)', value=True, key='fxdiv_rank_recent')
        view = ranking.copy()
        if filter_div != 'Todas':
            view = view[view['Divergencia'] == filter_div]
        if only_recent:
            latest = pd.to_datetime(ranking['Última fecha']).max()
            view = view[pd.to_datetime(view['Última fecha']) >= latest - pd.Timedelta(days=7)]
        view = view.assign(_es_divergencia=view['Divergencia'].isin(['Alcista', 'Bajista']))
        view = view.sort_values(['_es_divergencia', 'Índice exploratorio'], ascending=[False, False], na_position='last').drop(columns=['_es_divergencia'])
        st.caption(f'{len(view)} pares visibles de {len(ranking)} calculados. '
                   '«Recientes» se compara con la última fecha del conjunto, no con la hora actual.')
        visible_columns = [c for c in view.columns if c not in ('Fuente FX', 'Corr. 90d', 'Índice exploratorio')]
        st.dataframe(view[visible_columns], use_container_width=True, hide_index=True)
        if not view.empty:
            selected = st.selectbox('Abrir gráfico de un par del ranking', view['Par'].tolist(), key='fxdiv_rank_selected')
            if st.button('Ver par seleccionado', key='fxdiv_rank_open'):
                a, b = selected.split('/')
                st.session_state['fxdiv_base'] = a
                st.session_state['fxdiv_quote'] = b
                st.rerun()
        export_columns = [c for c in ranking.columns if c not in ('Fuente FX', 'Corr. 90d', 'Índice exploratorio')]
        st.download_button('Descargar ranking CSV', ranking[export_columns].to_csv(index=False).encode('utf-8'),
                           file_name='ranking_divergencias_g10.csv', mime='text/csv', key='fxdiv_rank_csv')
    errors = st.session_state.get('fxdiv_rank_errors', [])
    if errors:
        with st.expander(f'Diagnóstico: {len(errors)} pares/fuentes no disponibles'):
            for msg in errors:
                st.caption(msg)
    st.divider()


def render_fx_divergences():
    st.markdown('### Divergencias de Tipos FX')
    st.caption('Bonos soberanos 2Y · diferencial A − B frente al precio de A/B · Finans Trading')
    _render_g10_scanner()
    col_a, col_b, col_period = st.columns([1, 1, 1])
    with col_a:
        base = st.selectbox('Divisa A (base)', CURRENCIES, index=0, key='fxdiv_base')
    with col_b:
        choices = [c for c in CURRENCIES if c != base]
        if st.session_state.get('fxdiv_quote') not in choices and 'fxdiv_quote' in st.session_state:
            st.session_state['fxdiv_quote'] = choices[0]
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

    # Zoom estable: filtrar las fechas antes de crear el gráfico obliga a
    # Plotly a recalcular los rangos de ambos ejes verticales.
    st.markdown('#### Intervalo visible del gráfico')
    min_date = frame.index.min().date()
    max_date = frame.index.max().date()
    zoom_key = f'fxdiv_zoom_{base}_{quote}_{period}'
    reset_col, help_col = st.columns([1, 5])
    with reset_col:
        if st.button('Restablecer vista', key=f'fxdiv_reset_{base}_{quote}_{period}'):
            st.session_state[zoom_key] = (min_date, max_date)
    with help_col:
        st.caption('Selecciona las fechas para ampliar el gráfico. Los dos ejes Y se ajustan automáticamente.')
    if min_date < max_date:
        selected_dates = st.slider(
            'Fechas visibles', min_value=min_date, max_value=max_date,
            value=(min_date, max_date), format='DD/MM/YYYY', key=zoom_key,
        )
        chart_frame = frame.loc[
            (frame.index.date >= selected_dates[0]) &
            (frame.index.date <= selected_dates[1])
        ]
    else:
        chart_frame = frame
    if len(chart_frame) < 2:
        st.warning('Amplía el intervalo: hacen falta al menos dos fechas con datos.')
        return

    fig = make_subplots(specs=[[{'secondary_y': True}]])
    if display_mode.startswith('Doble eje'):
        spread_values = chart_frame['Spread_pb']
        fx_values = chart_frame['FX']
        left_label, right_label = 'Diferencial 2Y (puntos básicos)', f'{base}/{quote} (precio)'
    else:
        # Percentage change of the spread is unstable around zero; use basis-point
        # change from start on the left, FX percentage return on the right.
        spread_values = chart_frame['Spread_pb'] - chart_frame['Spread_pb'].iloc[0]
        fx_values = (chart_frame['FX'] / chart_frame['FX'].iloc[0] - 1) * 100
        left_label, right_label = 'Cambio diferencial desde inicio (pb)', f'Retorno {base}/{quote} desde inicio (%)'
    fig.add_trace(go.Scatter(x=chart_frame.index, y=spread_values, mode='lines', name=f'Spread 2Y {base} − {quote}', line=dict(color='#C9A227', width=3), hovertemplate='%{x|%d/%m/%Y}<br>%{y:.2f}<extra>%{fullData.name}</extra>'), secondary_y=False)
    fig.add_trace(go.Scatter(x=chart_frame.index, y=fx_values, mode='lines', name=f'{base}/{quote}', line=dict(color='#2563EB', width=2.5), hovertemplate='%{x|%d/%m/%Y}<br>%{y:.3f}<extra>%{fullData.name}</extra>'), secondary_y=True)
    if display_mode.startswith('Doble eje'):
        fig.add_hline(y=0, line_dash='dot', line_color='#9CA3AF', opacity=0.65)
    fig.update_layout(dragmode=False, height=560, template='plotly_white', hovermode='x unified', title=f'{base}/{quote} · diferencial 2Y frente al tipo de cambio', legend=dict(orientation='h', y=-0.18), margin=dict(l=25, r=25, t=60, b=35))
    fig.update_yaxes(title_text=left_label, secondary_y=False)
    fig.update_yaxes(title_text=right_label, secondary_y=True)
    fig.update_xaxes(fixedrange=True)
    fig.update_yaxes(autorange=True, fixedrange=True, secondary_y=False)
    fig.update_yaxes(autorange=True, fixedrange=True, secondary_y=True)
    st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': False, 'displayModeBar': False}, key=f'fxdiv_chart_{base}_{quote}')
    st.caption('El zoom solo modifica el gráfico. El diagnóstico inferior sigue usando el período completo seleccionado arriba.')

    st.markdown('#### Diagnóstico macro: presión de tipos y divergencia')
    window = st.select_slider('Ventana de comparación (observaciones comunes)',
                              options=[5, 10, 20, 40, 60, 90], value=20, key='fxdiv_window')
    signal = _directional_bias(frame, window)
    if signal is None:
        st.info('No hay observaciones suficientes para evaluar la ventana elegida.')
    else:
        change = signal['spread_change']
        fx_change = signal['fx_return']
        corr = signal['corr']
        ratio = signal['relative_strength']
        # Direction of rates and disagreement with FX are descriptive, not forecasts.
        if abs(change) < 1e-8:
            pressure = 'Sin cambio'
        else:
            pressure = 'Alcista' if change > 0 else 'Bajista'
        if abs(change) < 1e-8 or abs(fx_change) < 1e-8:
            divergence = 'No definida'
        elif change * fx_change < 0:
            divergence = 'Alcista' if change > 0 else 'Bajista'
        else:
            divergence = 'Alineados'
        c1, c2 = st.columns(2)
        c1.metric('Presión de tipos 2Y', pressure)
        c2.metric('Divergencia con FX', divergence)
        st.caption(f'En {window} observaciones: diferencial {change:+.1f} pb · '
                   f'{base}/{quote} {fx_change:+.2f}% · '
                   f'correlación móvil (hasta 90 cambios) '
                   f'{corr:+.2f}' if np.isfinite(corr) else
                   f'En {window} observaciones: diferencial {change:+.1f} pb · '
                   f'{base}/{quote} {fx_change:+.2f}% · correlación móvil N/D')
        if divergence in ('Alcista', 'Bajista'):
            st.info(f'Divergencia {divergence.lower()} potencial para {base}/{quote}. '
                    'La dirección de tipos es descriptiva, '
                    'no una señal de entrada ni una previsión del precio.')
        elif divergence == 'Alineados':
            st.info('El diferencial 2Y y el precio FX se han movido en la misma dirección durante la ventana.')
        else:
            st.info('No hay una divergencia direccional definida durante la ventana.')
        with st.expander('Metodología del diagnóstico'):
            st.write('**Presión de tipos:** signo de la variación del spread A − B en la ventana. '
                     'No depende de la correlación y no indica por sí sola que el par vaya a subir o bajar.')
            st.write('**Divergencia:** signo contrario entre la variación del spread y el retorno del par. '
                     'Alcista significa spread al alza y FX a la baja; bajista, lo contrario.')
            st.caption('La divergencia describe un desacuerdo de dirección, no una señal validada de trading.')

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
