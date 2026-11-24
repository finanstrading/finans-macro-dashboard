import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from metals_data import load_gold_data
from gold_analytics import net_liquidity, aligned, divergence

GOLD='#C9A227'; BLUE='#4678A8'

def chart(series, title, unit, key, bounds, revision, originals=None, secondary=None):
    fig = go.Figure()
    for i, (name, s) in enumerate(series.items()):
        s = s.dropna().sort_index()
        if s.empty:
            continue
        raw = originals[name].reindex(s.index) if originals else s
        fig.add_scatter(x=s.index, y=s.values, name=name, mode='lines',
                        customdata=raw.values,
                        hovertemplate='%{y:.2f}<br>Original: %{customdata:.2f}<extra>%{fullData.name}</extra>',
                        yaxis='y2' if name == secondary else 'y',
                        line=dict(color=[GOLD, BLUE, '#39866B', '#8D73B5'][i % 4], width=2))
    if not fig.data:
        st.caption('Sin observaciones para el horizonte seleccionado.')
        return
    fig.update_layout(title=title, yaxis_title=unit, template='plotly_white',
                      height=360, margin=dict(l=55,r=65,t=50,b=55),
                      legend=dict(orientation='h',y=-.2), hovermode='x unified',
                      dragmode='zoom', uirevision=revision,
                      xaxis=dict(type='date',range=list(bounds),autorange=False),
                      yaxis=dict(autorange=True, fixedrange=False))
    if secondary:
        fig.update_layout(yaxis2=dict(title=secondary, overlaying='y', side='right',
                                     showgrid=False, autorange=True, fixedrange=False))
    st.plotly_chart(fig, use_container_width=True, key=key,
                    config={'scrollZoom':True,'displaylogo':False,'doubleClick':'reset',
                            'displayModeBar':True,'modeBarButtonsToRemove':['autoScale2d']})

def render_gold_dashboard():
    with st.spinner('Cargando datos de metales…'):
        data,sources,errors=load_gold_data()
    liquidity=net_liquidity(data)
    if not liquidity.empty: data['Liquidez neta']=liquidity
    period=st.radio('Horizonte',['1M','3M','6M','1Y','3Y','5Y'],index=3,horizontal=True,key='gold_period')
    months={'1M':1,'3M':3,'6M':6,'1Y':12,'3Y':36,'5Y':60}[period]
    mode = st.radio('Normalización de comparaciones', ['Base 100','Z-score','Valores originales'], horizontal=True, key='gold_normalization')
    available = [v.index.max() for v in data.values() if not v.empty]
    gold = data.get('Oro', pd.Series(dtype=float))
    end = gold.index.max() if not gold.empty else (max(available) if available else pd.Timestamp.today().normalize())
    start = end - pd.DateOffset(months=months)
    bounds = (start, end)
    if st.button('Restablecer zoom de todos los gráficos', key='gold_reset'):
        st.session_state['gold_zoom_revision'] = st.session_state.get('gold_zoom_revision', 0) + 1
    revision = f"{period}:{mode}:{end}:{st.session_state.get('gold_zoom_revision',0)}"
    def window(s): return s.loc[(s.index >= start) & (s.index <= end)]
    def draw(series,title,unit,key,originals=None,secondary=None):
        chart(series,title,unit,key+'_'+revision,bounds,revision,originals,secondary)
    st.caption('Zoom independiente: rueda o selección; doble clic para restablecer. La normalización se fija al horizonte seleccionado.')
    cols=st.columns(4)
    for col,k,label,unit in zip(cols,['Oro','DXY','DFII10','Liquidez neta'],['Oro · USD/oz','DXY','Tipo real 10Y','Liquidez neta'],['','', '%',' B USD']):
        with col:
            s=data.get(k,pd.Series(dtype=float))
            st.metric(label, '—' if s.empty else f'{s.iloc[-1]/(1000 if k=="Liquidez neta" else 1):,.2f}{unit}')
            if not s.empty: st.caption(str(s.index[-1].date()))
    if errors:
        with st.expander('Diagnóstico de fuentes',expanded=True):
            for e in errors: st.warning(e)
    def compare(k,title,rate=False):
        if 'Oro' not in data or k not in data: return
        x = aligned(window(data['Oro']), window(data[k])).dropna().sort_index()
        if len(x) < 2:
            st.caption(f'{title}: histórico común insuficiente.')
            return
        raw = x.copy()
        if k == 'Liquidez neta':
            raw['Factor'] /= 1000
        effective = mode
        if mode == 'Base 100' and (x <= 0).any().any():
            effective = 'Z-score'
            st.caption(f'{title}: Z-score en lugar de base 100 por valores no positivos.')
        secondary = None
        if effective == 'Z-score':
            std = x.std(ddof=0)
            x = (x-x.mean()) / std.replace(0,float('nan'))
            unit = 'Desviaciones estándar'
        elif effective == 'Base 100':
            x = x / x.iloc[0] * 100
            unit = 'Base 100'
        else:
            x = raw.copy()
            unit = 'Oro · USD/oz'
            secondary = k + (' (%)' if rate else ' (miles de millones USD)' if k == 'Liquidez neta' else '')
        factor = secondary or k
        draw({'Oro':x.Oro,factor:x.Factor},title,unit,'gold_compare_'+k,
             originals={'Oro':raw.Oro,factor:raw.Factor},secondary=secondary)
    st.subheader('Tipos reales y dólar')
    for k,title,rate in [('DFII10','Oro vs. tipo real 10Y',True),('DFII5','Oro vs. tipo real 5Y',True),('DXY','Oro vs. DXY',False)]: compare(k,title,rate)
    rates={k:window(data[k]) for k in ('DGS10','DFII10','T10YIE') if k in data}
    if rates: draw(rates,'Rendimiento nominal, real y breakeven 10Y','%','gold_rates')
    st.subheader('Liquidez de la Fed')
    compare('Liquidez neta','Oro vs. liquidez neta Fed')
    if not liquidity.empty:
        draw({'Liquidez neta':window(liquidity)/1000},'Liquidez neta estimada','Miles de millones USD','gold_liq')
        impulse={f'{n} semanas':window(liquidity.diff(n))/1000 for n in (4,13,52)}
        draw(impulse,'Variación de liquidez neta','Miles de millones USD','gold_impulse')
    st.caption('Proxy: WALCL − WDTGAL − RRPONTSYD × 1000, en millones USD; fechas comunes, sin rellenar datos faltantes.')
    for k,label in [('WRBWFRBL','Reservas bancarias'),('M2SL','Oferta monetaria M2')]:
        if k in data: draw({label:window(data[k])/(1000 if k=='WRBWFRBL' else 1)},label,'Miles de millones USD','gold_'+k)
    st.subheader('Correlaciones móviles')
    for k in ('DFII10','DFII5','DXY'):
        if k not in data or 'Oro' not in data: continue
        x=aligned(data['Oro'],data[k]); a=x.Oro.pct_change(); b=x.Factor.diff() if k.startswith('DFII') else x.Factor.pct_change()
        draw({f'{n} sesiones':window(a.rolling(n).corr(b)) for n in (20,60,120)},'Oro vs. '+k+' · correlación de cambios','Correlación','gold_corr_'+k)
    st.subheader('Escáner de divergencias · 3M y 12M')
    table=divergence(data)
    if table.empty: st.info('Histórico común insuficiente.')
    else: st.dataframe(table,use_container_width=True,hide_index=True)
    st.caption('Umbrales exploratorios: oro 2%, tipos reales 15 pb, DXY y liquidez 2%. No son señales validadas. La liquidez se compara en fechas comunes semanales.')
    with st.expander('Fuentes y fechas de observación'):
        st.dataframe(pd.DataFrame([{'Serie':k,'Fuente':v,'Última observación':str(data[k].index[-1].date())} for k,v in sources.items()]),hide_index=True,use_container_width=True)
        st.caption('Datos de cierre y publicaciones FRED; no son cotizaciones en tiempo real. Las fechas de observación no equivalen a fechas de publicación.')
