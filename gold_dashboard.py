import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from metals_data import load_gold_data
from gold_analytics import net_liquidity, aligned, divergence

GOLD='#C9A227'; BLUE='#4678A8'

def chart(series,title,unit,key):
    fig=go.Figure()
    for i,(name,s) in enumerate(series.items()):
        fig.add_scatter(x=s.index,y=s.values,name=name,mode='lines',line=dict(color=[GOLD,BLUE,'#39866B','#8D73B5'][i%4],width=2))
    fig.update_layout(title=title,yaxis_title=unit,template='plotly_white',height=340,margin=dict(l=15,r=15,t=50,b=15),legend=dict(orientation='h',y=-.2),hovermode='x unified',dragmode='zoom')
    st.plotly_chart(fig,use_container_width=True,key=key,config={'scrollZoom':True,'displaylogo':False})

def render_gold_dashboard():
    with st.spinner('Cargando datos de metales…'):
        data,sources,errors=load_gold_data()
    liquidity=net_liquidity(data)
    if not liquidity.empty: data['Liquidez neta']=liquidity
    period=st.radio('Horizonte',['1M','3M','6M','1Y','3Y','5Y'],index=3,horizontal=True,key='gold_period')
    months={'1M':1,'3M':3,'6M':6,'1Y':12,'3Y':36,'5Y':60}[period]
    start=pd.Timestamp.today().normalize()-pd.DateOffset(months=months)
    def window(s): return s.loc[s.index>=start]
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
        x=aligned(window(data['Oro']),window(data[k]))
        if len(x)<2: return
        if rate:
            # Standardized levels, not percentage returns of yields.
            std=x.std(); x=(x-x.mean())/std.replace(0,float('nan')); unit='Desviaciones estándar'
        else:
            if (x.iloc[0]<=0).any(): return
            x=x/x.iloc[0]*100; unit='Base 100'
        chart({'Oro':x.Oro,k:x.Factor},title,unit,'gold_compare_'+k)
    st.subheader('Tipos reales y dólar')
    for k,title,rate in [('DFII10','Oro vs. tipo real 10Y',True),('DFII5','Oro vs. tipo real 5Y',True),('DXY','Oro vs. DXY',False)]: compare(k,title,rate)
    rates={k:window(data[k]) for k in ('DGS10','DFII10','T10YIE') if k in data}
    if rates: chart(rates,'Rendimiento nominal, real y breakeven 10Y','%','gold_rates')
    st.subheader('Liquidez de la Fed')
    compare('Liquidez neta','Oro vs. liquidez neta Fed')
    if not liquidity.empty:
        chart({'Liquidez neta':window(liquidity)/1000},'Liquidez neta estimada','Miles de millones USD','gold_liq')
        impulse={f'{n} semanas':window(liquidity.diff(n))/1000 for n in (4,13,52)}
        chart(impulse,'Variación de liquidez neta','Miles de millones USD','gold_impulse')
    st.caption('Proxy: WALCL − WDTGAL − RRPONTSYD × 1000, en millones USD; fechas comunes, sin rellenar datos faltantes.')
    for k,label in [('WRBWFRBL','Reservas bancarias'),('M2SL','Oferta monetaria M2')]:
        if k in data: chart({label:window(data[k])/(1000 if k=='WRBWFRBL' else 1)},label,'Miles de millones USD','gold_'+k)
    st.subheader('Correlaciones móviles')
    for k in ('DFII10','DFII5','DXY'):
        if k not in data or 'Oro' not in data: continue
        x=aligned(data['Oro'],data[k]); a=x.Oro.pct_change(); b=x.Factor.diff() if k.startswith('DFII') else x.Factor.pct_change()
        chart({f'{n} sesiones':window(a.rolling(n).corr(b)) for n in (20,60,120)},'Oro vs. '+k+' · correlación de cambios','Correlación','gold_corr_'+k)
    st.subheader('Escáner de divergencias · 3M y 12M')
    table=divergence(data)
    if table.empty: st.info('Histórico común insuficiente.')
    else: st.dataframe(table,use_container_width=True,hide_index=True)
    st.caption('Umbrales exploratorios: oro 2%, tipos reales 15 pb, DXY y liquidez 2%. No son señales validadas. La liquidez se compara en fechas comunes semanales.')
    with st.expander('Fuentes y fechas de observación'):
        st.dataframe(pd.DataFrame([{'Serie':k,'Fuente':v,'Última observación':str(data[k].index[-1].date())} for k,v in sources.items()]),hide_index=True,use_container_width=True)
        st.caption('Datos de cierre y publicaciones FRED; no son cotizaciones en tiempo real. Las fechas de observación no equivalen a fechas de publicación.')
