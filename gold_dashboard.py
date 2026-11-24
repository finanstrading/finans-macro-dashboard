import pandas as pd
import json
import streamlit.components.v1 as components
from plotly.offline import get_plotlyjs
import streamlit as st
import plotly.graph_objects as go
from metals_data import load_gold_data
from gold_analytics import net_liquidity, aligned, divergence, correlation_series
from gold_cot import load_gold_cot

GOLD='#C9A227'; BLUE='#4678A8'

def chart(series, title, unit, key, bounds, revision, originals=None, secondary=None, fixed_y=None, bars=None):
    fig = go.Figure()
    for i, (name, s) in enumerate(series.items()):
        s = s.dropna().sort_index()
        if s.empty:
            continue
        raw = originals[name].reindex(s.index) if originals else s
        if name == bars:
            fig.add_bar(x=[v.isoformat() for v in s.index], y=s.tolist(), name=name, yaxis='y2' if name == secondary else 'y', marker_color=['#39866B' if v >= 0 else '#C65C5C' for v in s], opacity=.65)
            continue
        fig.add_scatter(x=[v.isoformat() for v in s.index], y=s.tolist(), name=name, mode='lines',
                        customdata=raw.tolist(),
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
    # Plotly's native autorange does not follow horizontal zoom.
    # Use a local Plotly bundle and a relayout listener for visible data.
    fig.update_layout(dragmode='pan', yaxis=dict(fixedrange=True))
    if secondary:
        fig.update_layout(yaxis2=dict(fixedrange=True))
    if fixed_y is not None:
        fig.update_yaxes(range=list(fixed_y), autorange=False)
    payload = fig.to_json().replace("</", "<\\/")
    html = """<div id="goldplot" style="width:100%;height:360px"></div>
<script>""" + get_plotlyjs() + """</script><script>
const revision = """ + json.dumps(revision) + """;
const spec = """ + payload + """;
const gd = document.getElementById('goldplot');
const correlation = spec.layout.yaxis.title.text === 'Correlación';
const initialRange = spec.layout.xaxis.range.map(v => new Date(v).getTime());
let busy = false;
function autoscale() {
  if (busy || (!correlation && spec.layout.yaxis.autorange === false)) return;
  const xr = gd._fullLayout.xaxis.range.map(v => new Date(v).getTime());
  const updates = {};
  for (const axis of ['y','y2']) {
    const vals = [];
    for (const tr of gd.data) {
      if ((tr.yaxis || 'y') !== axis || tr.visible === 'legendonly' || tr.visible === false) continue;
      for (let i=0;i<tr.x.length;i++) {
        const t = new Date(tr.x[i]).getTime(), v = tr.y[i];
        if (t >= xr[0] && t <= xr[1] && v != null && Number.isFinite(Number(v))) vals.push(Number(v));
      }
    }
    if (!vals.length) continue;
    const lo=Math.min(...vals), hi=Math.max(...vals);
    const pad=(hi-lo)*0.08 || Math.max(Math.abs(lo)*0.01,0.01);
    const k=axis==='y'?'yaxis':'yaxis2';
    const full = xr[0] <= initialRange[0]+86400000 && xr[1] >= initialRange[1]-86400000;
    updates[k+'.range']=correlation ? (full ? [-1,1] : [Math.max(-1,Math.min(-0.05,lo-pad)),Math.min(1,Math.max(0.05,hi+pad))]) : [lo-pad,hi+pad];
    updates[k+'.autorange']=false;
  }
  busy=true;
  Promise.resolve(Plotly.relayout(gd,updates)).catch(console.error).finally(()=>{busy=false;});
}
Plotly.newPlot(gd,spec.data,spec.layout,{responsive:true,scrollZoom:true,displaylogo:false,doubleClick:'reset',displayModeBar:true,modeBarButtonsToRemove:['autoScale2d','zoomIn2d','zoomOut2d']}).then(()=>{
  autoscale();
  gd.on('plotly_relayout', e=>{if(Object.keys(e).some(k=>k.startsWith('xaxis.'))) autoscale();});
  gd.on('plotly_restyle',()=>autoscale());
});
</script>"""
    components.html(html, height=370, scrolling=False)

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
    def draw(series,title,unit,key,originals=None,secondary=None, fixed_y=None, bars=None):
        chart(series,title,unit,key+'_'+revision,bounds,revision,originals,secondary,fixed_y,bars)
    st.caption('Zoom horizontal con rueda, desplazamiento arrastrando y doble clic para restablecer. El eje vertical se adapta al intervalo visible; la normalización permanece fija.')
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
        if mode == 'Base 100' and (rate or (x <= 0).any().any()):
            effective = 'Z-score'
            st.caption(f'{title}: Z-score en lugar de base 100 para evitar ratios engañosos en tipos o valores no positivos.')
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
    tab = st.radio('Sección', ['Resumen','Tipos y dólar','Liquidez FED','COT','Correlaciones'], horizontal=True, key='gold_section', label_visibility='collapsed')
    def cot_metrics(cot):
        last = cot.iloc[-1]
        st.caption(f'COMEX Gold · futuros exclusivamente · fecha de posiciones: {cot.index[-1]:%d/%m/%Y}. No es la fecha de publicación; normalmente se publica el viernes.')
        cols = st.columns(4)
        for col, k in zip(cols, ['Net','Net / OI','Cambio semanal','Open Interest']):
            col.metric(k, '—' if pd.isna(last[k]) else (f'{last[k]:.1f}%' if k=='Net / OI' else f'{last[k]:,.0f}'))
        for col,k in zip(st.columns(2), ['COT 52','COT 156']):
            col.metric(k+' semanas','—' if pd.isna(last[k]) else f'{last[k]:.1f}')
    if tab in ('Resumen','COT'):
        try:
            cot = load_gold_cot()
        except Exception as exc:
            cot = None
            st.warning(f'CFTC Gold no disponible: {type(exc).__name__}: {exc}')
        if cot is not None:
            st.subheader('Posicionamiento COT · Managed Money')
            cot_metrics(cot)
    if tab == 'Resumen':
        st.subheader('Escáner de divergencias · 3M y 12M')
        table=divergence(data)
        if table.empty: st.info('Histórico común insuficiente.')
        else:
            only=st.checkbox('Solo divergencias relevantes',value=True,key='gold_relevant')
            shown=table[table['Relevancia'].isin(['Media','Alta'])] if only else table
            if shown.empty: st.info('Sin divergencias que cumplan el filtro.')
            else: st.dataframe(shown,use_container_width=True,hide_index=True)
        st.caption('Umbrales exploratorios: oro 2%, tipos reales 15 pb, DXY y liquidez 2%. No son señales validadas. La liquidez se compara en fechas comunes semanales.')
    elif tab == 'Tipos y dólar':
        st.subheader('Tipos reales y dólar')
        left,right = st.columns(2)
        with left: compare('DFII10','Oro vs. tipo real 10Y',True)
        with right: compare('DFII5','Oro vs. tipo real 5Y',True)
        left,right = st.columns(2)
        with left: compare('DXY','Oro vs. DXY')
        with right:
            rates={k:window(data[k]) for k in ('DGS10','DFII10','T10YIE') if k in data}
            if rates: draw(rates,'Rendimiento nominal, real y breakeven 10Y','%','gold_rates')
    elif tab == 'Liquidez FED':
        st.subheader('Liquidez de la Fed')
        left,right=st.columns(2)
        with left: compare('Liquidez neta','Oro vs. liquidez neta Fed')
        with right:
            if not liquidity.empty: draw({'Liquidez neta':window(liquidity)/1000},'Liquidez neta estimada','Miles de millones USD','gold_liq')
        if not liquidity.empty:
            draw({f'{n} semanas':window(liquidity.diff(n))/1000 for n in (4,13,52)},'Variación de liquidez neta','Miles de millones USD','gold_impulse')
        st.caption('Proxy: WALCL − WDTGAL − RRPONTSYD × 1000, en millones USD; fechas comunes, sin rellenar datos faltantes.')
        with st.expander('Componentes de liquidez, reservas y M2'):
            cols=st.columns(2)
            for i,(k,label,scale) in enumerate([('WALCL','Balance Fed',.001),('WDTGAL','TGA',.001),('RRPONTSYD','RRP',1),('WRBWFRBL','Reservas bancarias',.001),('M2SL','Oferta monetaria M2',1)]):
                if k in data:
                    with cols[i%2]: draw({label:window(data[k])*scale},label,'Miles de millones USD','gold_'+k)
    elif tab == 'COT' and cot is not None:
        left,right=st.columns(2)
        with left: draw({k:window(cot[k]) for k in ('Long','Short')},'Managed Money · Long y Short','Contratos','cot_ls')
        with right: draw({'Net':window(cot.Net),'Cambio semanal':window(cot['Cambio semanal'])},'Posición neta y cambio semanal','Contratos netos','cot_net',secondary='Cambio semanal',bars='Cambio semanal')
        left,right=st.columns(2)
        with left: draw({k:window(cot[k]) for k in ('COT 52','COT 156')},'COT Index · 52 y 156 semanas','Índice 0–100','cot_index',fixed_y=(0,100))
        with right:
            if 'Oro' in data:
                pair=aligned(window(data['Oro']),window(cot['Net / OI']))
                if len(pair)>1: draw({'Oro':pair.Oro,'Net / OI':pair.Factor},'Oro vs. posicionamiento relativo','USD/oz','cot_gold',secondary='Net / OI')
        with st.expander('Histórico del interés abierto'):
            draw({'Open Interest':window(cot['Open Interest'])},'Interés abierto','Contratos','cot_open')
        st.caption('COT Index: rango mínimo–máximo móvil del Net/OI, no percentil. 80/20 indica extremos relativos, no señales de giro. Comparación por fecha de observación, no backtest.')
    elif tab == 'Correlaciones':
        st.subheader('Correlaciones móviles')
        st.caption('Escala inicial −1 a +1; al ampliar, el eje vertical se adapta a los datos visibles incluyendo el cero.')
        summary=[]
        all_curves={}
        for k in ('DFII10','DFII5','DXY'):
            if k not in data or 'Oro' not in data: continue
            curves=correlation_series(data,k)
            all_curves[k]=curves
            summary.append({'Factor':k,**{f'{n}D':(round(v.dropna().iloc[-1],2) if not v.dropna().empty else None) for n,v in curves.items()}})
        if summary: st.dataframe(pd.DataFrame(summary),hide_index=True,use_container_width=True)
        cols=st.columns(2)
        for i,(k,curves) in enumerate(all_curves.items()):
            with cols[i%2]: draw({f'{n} sesiones':window(v) for n,v in curves.items()},'Oro vs. '+k+' · correlación de cambios','Correlación','gold_corr_'+k,fixed_y=(-1,1))
    with st.expander('Fuentes y fechas de observación'):
        st.dataframe(pd.DataFrame([{'Serie':k,'Fuente':v,'Última observación':str(data[k].index[-1].date())} for k,v in sources.items()]),hide_index=True,use_container_width=True)
        st.caption('Datos de cierre y publicaciones FRED; no son cotizaciones en tiempo real. Las fechas de observación no equivalen a fechas de publicación.')
