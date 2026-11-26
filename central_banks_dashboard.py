import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from central_banks_data import BANKS,LINKS,load_bank,japan_interventions_raw


def draw(items,title,mode='Original',unit=''):
    fig=go.Figure()
    for name,s in items.items():
        if s.empty: continue
        y=s
        if mode=='Base 100':
            if s.iloc[0]==0: continue
            y=100*s/s.iloc[0]
        elif mode=='Z-score':
            if not s.std()>0: continue
            y=(s-s.mean())/s.std()
        fig.add_scatter(x=s.index,y=y,name=name,customdata=s.to_numpy(),hovertemplate='%{x|%d/%m/%Y}<br>%{y:,.2f}<br>Original: %{customdata:,.2f}<extra>%{fullData.name}</extra>')
    fig.update_layout(title=title,height=360,template='plotly_white',dragmode='pan',yaxis_title=unit if mode=='Original' else mode,legend=dict(orientation='h',y=-.2),margin=dict(l=35,r=20,t=55,b=65))
    fig.add_annotation(text='FINANS TRADING · MacroFX',xref='paper',yref='paper',x=1,y=.03,showarrow=False,opacity=.4)
    st.plotly_chart(fig,use_container_width=True,config={'scrollZoom':True,'displaylogo':False,'toImageButtonOptions':{'format':'png','scale':2}})


def render_central_banks_dashboard():
    st.title('Balance de Bancos Centrales')
    st.caption('Balances, reservas oficiales y seguimiento de intervenciones FX. Fechas de observación, no de publicación.')
    bank=st.radio('Banco central',['Resumen global',*BANKS],horizontal=True,key='cb_bank')
    horizon=st.radio('Horizonte',['1 año','3 años','5 años','10 años'],index=1,horizontal=True,key='cb_horizon')
    cutoff=pd.Timestamp.today().normalize()-pd.DateOffset(years=int(horizon.split()[0])); mode=st.radio('Normalización',['Base 100','Z-score'],horizontal=True,key='cb_normal')
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
            monthly=s.groupby(s.index.to_period('M')).last(); monthly=monthly.reindex(pd.period_range(monthly.index.min(),monthly.index.max(),freq='M')); changes=monthly.diff().dropna(); changes.index=changes.index.to_timestamp(); changes=w(changes)
            fig=go.Figure(go.Bar(x=changes.index,y=changes,marker_color=['#549D86' if x>=0 else '#CB7070' for x in changes])); fig.update_layout(title=f'Variación mensual · {label}',height=300,template='plotly_white'); st.plotly_chart(fig,use_container_width=True)
        for name,s in d.items():
            if name not in ('Activos totales','Reservas oficiales sin oro',fx): draw({name:w(s)},name,unit='Mil millones USD')
        st.subheader('Intervenciones cambiarias')
        st.info('Los cambios en reservas o liquidez no confirman una intervención. Consulta los comunicados oficiales.')
        st.markdown(f'[Fuente oficial · {b}]({LINKS[b]})')
        if b=='BOJ':
            st.caption('Histórico oficial del Ministerio de Finanzas. Tabla original, pendiente de validar esquema y unidades para graficar importes.')
            if st.button('Consultar histórico oficial japonés'):
                try:
                    raw=japan_interventions_raw(); st.dataframe(raw, use_container_width=True); st.download_button('Descargar tabla original',raw.to_csv(index=False,header=False).encode('utf-8'),'mof_intervenciones.csv','text/csv')
                except Exception as e: st.warning(f'Histórico no disponible: {type(e).__name__}')
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
