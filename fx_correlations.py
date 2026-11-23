"""MacroFX — comparador de indicadores macroeconómicos FX.
Reutiliza los DataFrames y conversores de la aplicación principal.
"""
import re
import unicodedata
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots
from fx_rates import load_rates

PRESETS = {
    'USD': {'Inflación y empleo': ['Core CPI', 'Unemployment'], 'Mercado laboral': ['Non Farm Payroll', 'Unemployment'], 'Actividad': ['ISM Services', 'GDP'], 'Inflación y Fed': ['CPI', 'Tipo oficial (%)']},
    'EUR': {'Inflación y empleo': ['Core CPI', 'Unemployment'], 'Actividad': ['Services PMI', 'GDP'], 'Industria': ['Manufacturing PMI', 'GDP'], 'Inflación y tipos': ['CPI', 'Tipo oficial (%)']},
    'GBP': {'Inflación y empleo': ['Core CPI', 'Unemployment'], 'Salarios e inflación': ['Average Earnings', 'CPI'], 'Actividad': ['Services PMI', 'GDP'], 'Inflación y tipos': ['CPI', 'Tipo oficial (%)']},
    'AUD': {'Inflación y empleo': ['CPI', 'Unemployment'], 'Mercado laboral': ['Employment', 'Unemployment'], 'Actividad': ['Manufacturing PMI', 'GDP'], 'Inflación y tipos': ['CPI', 'Tipo oficial (%)']},
    'CAD': {'Inflación y empleo': ['CPI', 'Unemployment'], 'Mercado laboral': ['Employment', 'Unemployment'], 'Actividad': ['GDP', 'Retail Sales'], 'Inflación y tipos': ['CPI', 'Tipo oficial (%)']},
    'JPY': {'Inflación y empleo': ['CPI', 'Unemployment'], 'Salarios e inflación': ['Cash Earnings', 'CPI'], 'Actividad': ['Manufacturing PMI', 'GDP'], 'Inflación y tipos': ['CPI', 'Tipo oficial (%)']},
    'NZD': {'Inflación y empleo': ['CPI', 'Unemployment'], 'Mercado laboral': ['Employment', 'Unemployment'], 'Actividad': ['GDP', 'Retail Sales'], 'Inflación y tipos': ['CPI', 'Tipo oficial (%)']},
    'CHF': {'Inflación y empleo': ['CPI', 'Unemployment'], 'Actividad': ['Manufacturing PMI', 'GDP'], 'Inflación y tipos': ['CPI', 'Tipo oficial (%)']},
}
COLORS = ['#C9A227', '#3689C9', '#20A17A', '#AD72C7']

def _norm(value):
    value = unicodedata.normalize('NFKD', str(value).lower())
    return re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in value if not unicodedata.combining(c))).strip()

def _match(hint, available_names):
    needle = _norm(hint)
    exact = [x for x in available_names if _norm(x) == needle]
    if exact:
        return exact[0]
    partial = [x for x in available_names if needle in _norm(x)]
    if partial:
        return sorted(partial, key=lambda x: (len(_norm(x)), x))[0]
    return None

def _series(df, name, convert_values):
    data = pd.DataFrame({'Fecha': df['Fecha'], 'Valor': convert_values(df[name])})
    data = data.dropna().sort_values('Fecha').drop_duplicates('Fecha', keep='last')
    return data.set_index('Fecha')['Valor'].astype(float)

def render_fx_correlations(markets, load_market, convert_dates, convert_values, get_indicators):
    st.markdown('### Correlaciones FX')
    st.caption('Comparador macroeconómico · Finans Trading · datos históricos de MacroFX')
    currency = st.selectbox('Divisa', list(markets), index=list(markets).index('USD') if 'USD' in markets else 0, key='fxcorr_currency')
    try:
        df, sheet = load_market(tuple(markets[currency]))
        df = df.copy()
        df['Fecha'] = convert_dates(df['DATE'])
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        indicators = get_indicators(df)
    except Exception as exc:
        st.error(f'No se pudo cargar la hoja de {currency}: {exc}')
        return
    rates, rate_sources, rate_warnings = load_rates(currency, df, convert_values)
    rate_labels = ['Tipo oficial (%)', 'Bono 2Y (%)', 'Bono 10Y (%)']
    available_names = list(dict.fromkeys(list(indicators) + rate_labels))
    presets = PRESETS.get(currency, {})
    preset_name = st.selectbox('Relación predeterminada', ['Personalizada'] + list(presets), key=f'fxcorr_preset_{currency}')
    preset_matches = []
    missing = []
    if preset_name != 'Personalizada':
        for hint in presets[preset_name]:
            found = _match(hint, available_names)
            if found and found not in preset_matches:
                preset_matches.append(found)
            elif not found:
                missing.append(hint)
    selection_key = f'fxcorr_selected_{currency}'
    previous_key = f'fxcorr_previous_preset_{currency}'
    if selection_key not in st.session_state:
        st.session_state[selection_key] = preset_matches or available_names[:min(2, len(available_names))]
    st.session_state[selection_key] = [n for n in st.session_state[selection_key] if n in available_names][:4]
    if st.session_state.get(previous_key) != preset_name:
        if preset_name != 'Personalizada':
            st.session_state[selection_key] = preset_matches
        st.session_state[previous_key] = preset_name
    st.caption('Tipos oficiales y bonos soberanos 2Y/10Y disponibles en el mismo comparador.')
    selected = st.multiselect('Indicadores (máximo 4)', available_names, max_selections=4, key=selection_key)
    with st.expander('Estado de datos de tipos y bonos', expanded=not all(k in rates for k in rate_labels)):
        for label in rate_labels:
            if label in rates and not rates[label].empty:
                item = rates[label]
                st.success(f'{label}: {item.iloc[-1]:.3f}% · {item.index[-1]:%d/%m/%Y} · {rate_sources.get(label, "Fuente desconocida")}')
            else:
                st.warning(f'{label}: datos no disponibles. El indicador permanece en el selector.')
        for warning in rate_warnings:
            st.caption(warning)
    if missing:
        st.info('No se han encontrado en esta hoja: ' + ', '.join(missing) + '. Puedes seleccionar alternativas manualmente.')
    if not selected:
        st.info('Selecciona al menos un indicador.')
        return
    col1, col2 = st.columns(2)
    with col1:
        period = st.selectbox('Período', ['3M', '6M', '1A', '3A', '5A', '10A', 'Todo'], index=3, key='fxcorr_period')
    with col2:
        mode = st.radio('Escala', ['Normalizada (base 100)', 'Valores originales'], horizontal=True, key='fxcorr_scale')
    series = {}
    end = max([df['Fecha'].max()] + [s.index.max() for s in rates.values() if not s.empty])
    months = {'3M': 3, '6M': 6, '1A': 12, '3A': 36, '5A': 60, '10A': 120}
    start = end - pd.DateOffset(months=months[period]) if period in months else df['Fecha'].min()
    for name in selected:
        if name in rate_labels and name not in rates:
            st.warning(f'{name}: datos no disponibles; revisa el estado de fuentes.')
            continue
        s = rates[name] if name in rates else _series(df, name, convert_values)
        s = s.loc[s.index >= start]
        if not s.empty:
            series[name] = s
    if not series:
        st.warning('No hay observaciones para el período seleccionado.')
        return
    fig = make_subplots(specs=[[{'secondary_y': True}]])
    for i, (name, s) in enumerate(series.items()):
        if mode.startswith('Normalizada'):
            first = float(s.iloc[0])
            if abs(first) < 1e-12:
                st.warning(f'{name}: el primer valor es cero; no puede normalizarse a base 100.')
                continue
            plotted = s / first * 100
            secondary = False
        else:
            plotted = s
            secondary = i > 0
        fig.add_trace(go.Scatter(x=plotted.index, y=plotted.values, name=name, mode='lines+markers', line={'color': COLORS[i % len(COLORS)], 'width': 2.5}, marker={'size': 4}, connectgaps=False, hovertemplate='%{x|%d/%m/%Y}<br>%{y:.2f}<extra>%{fullData.name}</extra>'), secondary_y=secondary)
    fig.update_layout(height=510, hovermode='x unified', template='plotly_white', legend={'orientation': 'h', 'y': -0.2}, margin={'l': 20, 'r': 30, 't': 30, 'b': 30})
    fig.update_yaxes(title_text='Índice base 100' if mode.startswith('Normalizada') else 'Primer indicador (unidades originales)', secondary_y=False)
    if mode == 'Valores originales' and len(series) > 1:
        fig.update_yaxes(title_text='Otros indicadores (unidades originales)', secondary_y=True)
        st.caption('En escala original, los indicadores 2–4 comparten el eje derecho; si sus unidades difieren, utiliza la escala normalizada.')
    st.plotly_chart(fig, use_container_width=True, key=f'fxcorr_plot_{currency}')
    st.caption(f'Fuentes: {sheet} (macro) y fuentes detalladas en Estado de datos de tipos y bonos. Última fecha del conjunto: {end:%d/%m/%Y}. Sin interpolación.')
    if len(series) >= 2:
        st.markdown('#### Correlación de variaciones mensuales')
        st.caption('Se utiliza la última observación disponible de cada mes. Se calculan diferencias mensuales para tasas/índices macro, no niveles de precio. No se rellenan meses ausentes ni se asume causalidad.')
        monthly = pd.concat({name: s.resample('MS').last() for name, s in series.items()}, axis=1)
        changes = monthly.diff()
        rows = []
        names = list(series)
        for i, a in enumerate(names):
            for b in names[i+1:]:
                pair = changes[[a, b]].dropna()
                r = pair[a].corr(pair[b]) if len(pair) >= 6 and pair[a].std() > 0 and pair[b].std() > 0 else np.nan
                rows.append({'Indicadores': f'{a} / {b}', 'Pearson (Δ mensual)': round(float(r), 3) if pd.notna(r) else 'N/D', 'Meses comparables': len(pair)})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption('N/D significa menos de seis cambios mensuales comparables o variación nula. La correlación no implica causalidad; las series trimestrales pueden requerir un análisis específico.')
