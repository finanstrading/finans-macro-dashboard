import pandas as pd
import json
import streamlit.components.v1 as components
from plotly.offline import get_plotlyjs
from chart_branding import apply_chart_branding
GOLD="#C9A227"; BLUE="#4678A8"
import streamlit as st
import plotly.graph_objects as go
from central_banks_data import BANKS,LINKS,load_bank,japan_interventions_raw,snb_transactions_raw,snb_transactions


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
                        hovertemplate='%{x|%d/%m/%Y}<br>%{y:.2f}<br>Original: %{customdata:.2f}<extra>%{fullData.name}</extra>',
                        yaxis='y2' if name == secondary else 'y',
                        line=dict(color=[GOLD, BLUE, '#39866B', '#8D73B5'][i % 4], width=2))
    if not fig.data:
        st.caption('Sin observaciones para el horizonte seleccionado.')
        return
    render_figure(fig, title, unit, revision, secondary, fixed_y)

def render_figure(fig, title, unit, revision, secondary=None, fixed_y=None):
    # Bound each chart to its actual plotted observations, not the gold calendar.
    dates = [pd.Timestamp(v) for tr in fig.data for v in tr.x]
    first, last = min(dates), max(dates)
    if first == last:
        first -= pd.Timedelta(hours=12)
        last += pd.Timedelta(hours=12)
    for tr in fig.data:
        if tr.type == 'bar':
            width_days = 3 if 'diarias' in title else 23 if 'mensual' in title else 70 if 'trimestral' in title else 270 if ('anuales' in title or 'por año' in title) else 5
            tr.width = width_days * 86400000
            first = min(first, min(pd.Timestamp(v) for v in tr.x) - pd.Timedelta(days=width_days/2))
            last = max(last, max(pd.Timestamp(v) for v in tr.x) + pd.Timedelta(days=width_days/2))
    bounds = (first, last)
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
    # Paper coordinates keep branding fixed during zoom and PNG export.
    apply_chart_branding(fig)
    payload = fig.to_json().replace("</", "<\\/")
    html = """<div id="goldplot" style="width:100%;height:360px"></div>
<script>""" + get_plotlyjs() + """</script><script>
const revision = """ + json.dumps(revision) + """;
const spec = """ + payload + """;
const gd = document.getElementById('goldplot');
const correlation = spec.layout.yaxis.title.text === 'Correlación';
function timestamp(v) {
  if (typeof v === 'number') return v;
  const s = String(v).replace(' ', 'T');
  return Date.parse(/(?:Z|[+-]\\d{2}:?\\d{2})$/i.test(s) ? s : (s.length === 10 ? s+'T00:00:00Z' : s+'Z'));
}
const initialRange = spec.layout.xaxis.range.map(timestamp);
function boundedRange(xr) {
  const [lo, hi] = initialRange;
  if (!xr.every(Number.isFinite) || xr[1] <= xr[0]) return [lo, hi];
  const width = Math.min(Math.max(xr[1]-xr[0], 7*86400000), hi-lo);
  const left = Math.max(lo, Math.min(xr[0], hi-width));
  return [left, left+width];
}
let busy = false;
function autoscale() {
  if (busy) return;
  const requested = gd._fullLayout.xaxis.range.map(timestamp);
  const xr = boundedRange(requested);
  const updates = {};
  if (!requested.every(Number.isFinite) || requested.some((v,i)=>Math.abs(v-xr[i])>1)) {
    updates['xaxis.range'] = xr.map(v=>new Date(v).toISOString());
    updates['xaxis.autorange'] = false;
  }
  for (const axis of ((!correlation && spec.layout.yaxis.autorange === false) ? [] : ['y','y2'])) {
    const vals = [];
    for (const tr of gd.data) {
      if ((tr.yaxis || 'y') !== axis || tr.visible === 'legendonly' || tr.visible === false) continue;
      for (let i=0;i<tr.x.length;i++) {
        const t = timestamp(tr.x[i]), v = tr.y[i];
        const half = tr.type === 'bar' ? Number(tr.width || 0)/2 : 0;
        if (t+half >= xr[0] && t-half <= xr[1] && v != null && Number.isFinite(Number(v))) vals.push(Number(v));
        if (tr.type === 'scatter' && (tr.mode || '').includes('lines') && i>0) {
          const prev=timestamp(tr.x[i-1]), pv=tr.y[i-1];
          if (t>prev && pv!=null && v!=null && Number.isFinite(Number(pv)) && Number.isFinite(Number(v))) {
            for (const edge of xr) if (prev<edge && edge<t) vals.push(Number(pv)+(Number(v)-Number(pv))*(edge-prev)/(t-prev));
          }
        }
      }
    }
    if (!vals.length) {
      for (const tr of gd.data) if (tr.type==='bar' && (tr.yaxis||'y')===axis && tr.visible!==false && tr.visible!=='legendonly') vals.push(0);
    }
    if (!vals.length) continue;
    if (gd.data.some(tr=>tr.type === "bar" && (tr.yaxis || "y") === axis)) vals.push(0);
    const lo=Math.min(...vals), hi=Math.max(...vals);
    const pad=(hi-lo)*0.08 || Math.max(Math.abs(lo)*0.01,0.01);
    const k=axis==='y'?'yaxis':'yaxis2';
    const full = xr[0] <= initialRange[0]+86400000 && xr[1] >= initialRange[1]-86400000;
    updates[k+'.range']=correlation ? (full ? [-1,1] : [Math.max(-1,Math.min(-0.05,lo-pad)),Math.min(1,Math.max(0.05,hi+pad))]) : [lo-pad,hi+pad];
    updates[k+'.autorange']=false;
  }
  if (!Object.keys(updates).length) return;
  busy=true;
  Promise.resolve(Plotly.relayout(gd,updates)).catch(console.error).finally(()=>{busy=false;});
}
// Native bounds prevent dragging beyond the data on supported Plotly versions.
const xSchema = Plotly.PlotSchema && Plotly.PlotSchema.get().layout.layoutAttributes.xaxis;
if (xSchema && xSchema.minallowed && xSchema.maxallowed) {
  spec.layout.xaxis.minallowed = new Date(initialRange[0]).toISOString();
  spec.layout.xaxis.maxallowed = new Date(initialRange[1]).toISOString();
}
Plotly.newPlot(gd,spec.data,spec.layout,{responsive:true,scrollZoom:true,displaylogo:false,doubleClick:'reset',displayModeBar:true,toImageButtonOptions:{format:"png",scale:2},modeBarButtonsToRemove:['autoScale2d','zoomIn2d','zoomOut2d']}).then(()=>{
  autoscale();
  gd.on('plotly_relayout', e=>{if(Object.keys(e).some(k=>k.startsWith('xaxis.'))) { if(e['xaxis.autorange']===true && !busy) {busy=true; Plotly.relayout(gd,{'xaxis.range':spec.layout.xaxis.range,'xaxis.autorange':false}).finally(()=>{busy=false;autoscale();});} else autoscale(); }});
  gd.on('plotly_restyle',()=>autoscale());
});
</script>"""
    components.html(html, height=370, scrolling=False)

def compact_selector(label, options, key, default):
    state_key = key + '_selected'
    if st.session_state.get(state_key) not in options:
        st.session_state[state_key] = default
    st.markdown(f'**{label}**')
    cols = st.columns(len(options) + 1)
    for i, option in enumerate(options):
        cols[i].button(option, key=f'{key}_btn_{i}',
                       type='primary' if st.session_state[state_key] == option else 'secondary',
                       use_container_width=True,
                       on_click=lambda value=option: st.session_state.update({state_key: value}))
    return st.session_state[state_key]

def draw(items,title,mode='Original',unit='',bars=None):
    values={}; originals={}
    for name,s in items.items():
        s=s.dropna().sort_index()
        if s.empty: continue
        y=s
        if mode=='Base 100':
            if s.iloc[0]==0: continue
            y=100*s/s.iloc[0]
        elif mode=='Z-score':
            if not s.std()>0: continue
            y=(s-s.mean())/s.std()
        values[name]=y; originals[name]=s
    chart(values,title,unit if mode=='Original' else mode,title,None,title,originals=originals,bars=bars)


def parse_japan(raw):
    import re
    months={m:i for i,m in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split(),1)}
    year=month=None; rows=[]; coverage=[]
    for row in raw.fillna('').astype(str).itertuples(index=False,name=None):
        y,m,day,amount,pair=(row[i].strip() for i in (3,4,5,6,8))
        if re.fullmatch(r'\d{4}',y): year=int(y)
        elif y:
            match=re.search(r'(\d{4})$',y)
            if match and '-' in y:
                end=y.split('-')[-1].strip().split()[0][:3]
                if end in months: coverage.append(pd.Timestamp(int(match[1]),months[end],1)+pd.offsets.MonthEnd(0))
            year=month=None; continue
        if m: month=months.get(m[:3])
        if not day.isdigit() or not pair: continue
        if year is None or month is None: raise ValueError('Fecha de intervención incompleta')
        pair=pair.lower()
        if 'japanese yen (sold)' in pair: sign=1
        elif 'japanese yen (bought)' in pair: sign=-1
        elif 'japanese yen' in pair: raise ValueError('Dirección JPY desconocida')
        else: continue
        rows.append((pd.Timestamp(year,month,int(day)),sign*float(amount.replace(',',''))/10,pair))
    if not rows or not coverage: raise ValueError('Histórico o cobertura no reconocidos')
    return pd.DataFrame(rows,columns=['Fecha','Neto (mil M JPY)','Divisas']).sort_values('Fecha'),max(coverage)


def render_central_banks_dashboard():
    st.title('Balance de Bancos Centrales')
    st.caption('Balances, reservas oficiales y seguimiento de intervenciones FX. Fechas de observación, no de publicación.')
    bank=compact_selector('Banco central',['Resumen global',*BANKS],'cb_bank','Resumen global')
    horizon=compact_selector('Horizonte',['1 año','3 años','5 años','10 años'],'cb_horizon','3 años')
    cutoff=pd.Timestamp.today().normalize()-pd.DateOffset(years=int(horizon.split()[0])); mode=compact_selector('Normalización',['Base 100','Z-score'],'cb_normal','Base 100')
    def w(s): return s[s.index>=cutoff]
    banks=list(BANKS) if bank=='Resumen global' else [bank]; all_data={}; diagnostics=[]
    for b in banks:
        d,src,err=load_bank(b); all_data[b]=d; diagnostics.extend(f'{b}: {e}' for e in err)
        if bank=='Resumen global': continue
        ccy=BANKS[b][1]; fx=BANKS[b][3]
        cols=st.columns(2)
        for col,label,unit in zip(cols,['Activos totales','Reservas oficiales sin oro'],[ccy,'USD']):
            with col:
                s=d.get(label,pd.Series(dtype=float))
                if s.empty: st.metric(label,'No disponible'); continue
                prev=s[s.index<=s.index[-1]-pd.DateOffset(months=12)]
                delta=f'{(s.iloc[-1]/prev.iloc[-1]-1)*100:+.2f}% interanual' if not prev.empty and prev.iloc[-1]!=0 else None
                st.metric(label,f'{s.iloc[-1]:,.1f} mil M {unit}',delta); st.caption(f'{s.index[-1]:%d/%m/%Y} · {src[label]}')
        for label in ['Activos totales','Reservas oficiales sin oro']:
            if label not in d: continue
            s=d[label]; draw({label:w(s)},label,unit=f'Mil millones de {ccy if label=="Activos totales" else "USD"}')
            if fx in d: draw({label:w(s),fx:w(d[fx])},f'{fx} vs. {label}',mode)
            if 'Banco Mundial' in src[label]:
                st.caption('Serie anual de respaldo; no permite detectar cambios mensuales.')
                continue
            monthly=s.groupby(s.index.to_period('M')).last(); monthly=monthly.reindex(pd.period_range(monthly.index.min(),monthly.index.max(),freq='M')); changes=monthly.diff().dropna(); changes.index=changes.index.to_timestamp(); changes=w(changes)
            draw({'Cambio mensual':changes},f'Variación mensual · {label}',unit=f'Mil millones de {ccy if label=="Activos totales" else "USD"}',bars='Cambio mensual')
        for name,s in d.items():
            if name not in ('Activos totales','Reservas oficiales sin oro',fx):
                draw({name:w(s)},name,unit=f'Mil millones {ccy}')
                if name.startswith('Sight deposits'):
                    changes=s.diff().where(s.index.to_series().diff().dt.days.between(6,8)).dropna()
                    draw({'Cambio semanal':w(changes)},f'{name} · variación semanal',unit='Mil millones CHF',bars='Cambio semanal')
                    if fx in d: draw({name:w(s),fx:w(d[fx])},f'{fx} vs. {name}',mode)
                    st.caption('Media semanal de depósitos a la vista; no equivale a intervención.')
        st.subheader('Intervenciones cambiarias')
        st.info('Los cambios en reservas o liquidez no confirman una intervención. Consulta los comunicados oficiales.')
        st.markdown(f'[Fuente oficial · {b}]({LINKS[b]})')
        if b=='BOJ':
            st.caption('Ministerio de Finanzas de Japón · ventas de JPY (+), compras de JPY (−). Solo operaciones con JPY; detalle diario publicado trimestralmente.')
            try:
                raw=japan_interventions_raw(); table,end=parse_japan(raw)
                daily=table.groupby('Fecha')['Neto (mil M JPY)'].sum()
                monthly=daily.groupby(daily.index.to_period('M')).sum().reindex(pd.period_range('1991-04',end.to_period('M'),freq='M'),fill_value=0)
                annual=monthly.groupby(monthly.index.year).sum(); annual.index=pd.to_datetime(annual.index.astype(str)+'-01-01')
                monthly.index=monthly.index.to_timestamp()
                last=daily.index[-1]; c1,c2,c3=st.columns(3)
                c1.metric('Último día publicado con intervención',last.strftime('%d/%m/%Y'))
                c2.metric('Importe neto del día',f'{daily.iloc[-1]:+,.1f} mil M JPY')
                c3.metric(f'Acumulado {end.year} hasta {end:%m/%Y}',f'{annual.iloc[-1]:+,.1f} mil M JPY')
                st.caption(f'Cobertura oficial hasta {end:%d/%m/%Y}; no implica ausencia de operaciones posteriores. Sumas de importes diarios redondeados.')
                draw({'Intervenciones':w(daily)},'Japón · Intervenciones diarias',unit='Mil millones JPY',bars='Intervenciones')
                draw({'Intervenciones':w(monthly)},'Japón · Intervenciones mensuales',unit='Mil millones JPY',bars='Intervenciones')
                draw({'Intervenciones':annual[annual.index.year>=cutoff.year]},'Japón · Intervenciones anuales (último año parcial)',unit='Mil millones JPY',bars='Intervenciones')
                if fx in d:
                    price=w(d[fx]); events=daily[daily.index>=cutoff]; events=events[events.index.isin(price.index)]
                    fig=go.Figure(go.Scatter(x=[v.isoformat() for v in price.index],y=price.tolist(),mode='lines',name=fx,line=dict(color=BLUE)))
                    fig.add_trace(go.Scatter(x=[v.isoformat() for v in events.index],y=price.reindex(events.index).tolist(),mode='markers',name='Intervención',marker=dict(size=9,color=['#549e88' if v>0 else '#ce8285' for v in events]),customdata=events.tolist(),hovertemplate='%{x|%d/%m/%Y}<br>USD/JPY: %{y:.2f}<br>Neto: %{customdata:,.1f} mil M JPY<extra></extra>'))
                    if not price.empty:
                        render_figure(fig, 'USD/JPY · días de intervención', 'JPY por USD', 'boj_fx_events')
                    st.caption('Marcadores solo en fechas con cotización FRED disponible; no representan el precio exacto de ejecución.')
                st.dataframe(table.sort_values('Fecha',ascending=False),use_container_width=True)
                st.download_button('Descargar intervenciones JPY',table.to_csv(index=False).encode('utf-8'),'mof_intervenciones_jpy.csv','text/csv')
            except Exception as e: st.warning(f'Histórico no disponible: {type(e).__name__}: {e}')
            st.markdown('[Último comunicado mensual y trimestral](https://www.mof.go.jp/english/policy/international_policy/reference/feio/index.html)')
        if b=='BNS':
            st.caption('Compras netas de divisas (+) y ventas netas (−). Importes oficiales trimestrales, en miles de millones CHF.')
            try:
                q=snb_transactions()
                if q.empty: raise ValueError('Sin observaciones trimestrales')
                last=q.index[-1]; year=q[q.index.year==last.year]
                c1,c2=st.columns(2)
                c1.metric(f'Último trimestre · {last.year} Q{last.quarter}',f'{q.iloc[-1]:+,.3f} mil M CHF')
                c2.metric(f'Acumulado {last.year} · {len(year)} trimestres',f'{year.sum():+,.3f} mil M CHF')
                draw({'Intervenciones netas':w(q)},'BNS · Intervenciones trimestrales',unit='Mil millones CHF',bars='Intervenciones netas')
                annual=q.groupby(q.index.year).sum(); annual.index=pd.to_datetime(annual.index.astype(str)+'-12-31')
                draw({'Acumulado anual':w(annual)},'BNS · Intervenciones por año (último año parcial si procede)',unit='Mil millones CHF',bars='Acumulado anual')
                if fx in d:
                    # Compare quarterly FX changes with flows, without treating flows as a price index.
                    fxq=d[fx].groupby(d[fx].index.to_period('Q')).last(); changes=fxq.pct_change()*100; changes.index=changes.index.to_timestamp(how='end').normalize()
                    aligned=pd.concat([q.rename('Intervenciones (mil M CHF)'),changes.rename('USD/CHF cambio (%)')],axis=1,join='inner').dropna(); aligned=aligned[aligned.index>=cutoff]
                    if not aligned.empty:
                        draw({k:aligned[k] for k in aligned},'Intervenciones vs. variación trimestral USD/CHF · Z-score','Z-score')
                        st.caption('Comparación estandarizada de flujos y rendimientos trimestrales; no implica causalidad.')
                table=q.rename('Intervenciones netas (mil M CHF)').to_frame().sort_index(ascending=False)
                st.dataframe(table,use_container_width=True)
                st.download_button('Descargar transacciones BNS',table.to_csv().encode('utf-8'),'snb_transacciones.csv','text/csv')
            except Exception as e: st.warning(f'Transacciones BNS no disponibles: {type(e).__name__}: {e}')
            st.markdown('[Serie oficial de transacciones](https://data.snb.ch/en/topics/snb/cube/snbfxtr)')
        with st.expander('Fuentes y últimas observaciones'):
            st.dataframe(pd.DataFrame([{'Serie':k,'Fuente':src[k],'Última observación':s.index[-1].strftime('%d/%m/%Y')} for k,s in d.items()]),use_container_width=True)
    if bank=='Resumen global':
        rows=[]; items={}
        for b,d in all_data.items():
            s=d.get('Activos totales',pd.Series(dtype=float)); r=d.get('Reservas oficiales sin oro',pd.Series(dtype=float)); items[b]=w(s) if not s.empty else s
            rows.append({'Banco':b,'Activos (mil M moneda local)':s.iloc[-1] if not s.empty else None,'Moneda':BANKS[b][1],'Fecha balance':s.index[-1].date() if not s.empty else None,'Reservas sin oro (mil M USD)':r.iloc[-1] if not r.empty else None,'Fecha reservas':r.index[-1].date() if not r.empty else None})
        st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True); draw(items,'Balances comparados',mode)
        st.caption('Cada balance se normaliza desde su primera observación disponible en el horizonte; no se suman monedas distintas.')
    if diagnostics:
        with st.expander('Diagnóstico de fuentes'): st.write(diagnostics)
