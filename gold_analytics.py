import pandas as pd

def net_liquidity(data):
    if not all(k in data for k in ('WALCL','WDTGAL','RRPONTSYD')): return pd.Series(dtype=float)
    # Wednesday levels, millions USD; RRP is reported in billions.
    x = pd.concat([data['WALCL'],data['WDTGAL'],data['RRPONTSYD']*1000],axis=1,join='inner').dropna()
    return (x.iloc[:,0]-x.iloc[:,1]-x.iloc[:,2]).sort_index()

def aligned(a,b):
    return pd.concat([a.rename('Oro'),b.rename('Factor')],axis=1,join='inner').dropna().sort_index()

def correlation_series(data,factor,windows=(20,60,120)):
    x=aligned(data['Oro'],data[factor])
    a=x.Oro.pct_change(fill_method=None)
    b=x.Factor.diff() if factor.startswith('DFII') else x.Factor.pct_change(fill_method=None)
    return {n:a.rolling(n,min_periods=n).corr(b) for n in windows}

def divergence(data):
    rows=[]
    for factor, direction, unit, threshold in [('DFII10',-1,'pb',15),('DFII5',-1,'pb',15),('DXY',-1,'%',2),('Liquidez neta',1,'%',2)]:
        if factor not in data or 'Oro' not in data: continue
        x=aligned(data['Oro'],data[factor])
        if x.empty: continue
        for months in (3,12):
            end=x.index[-1]; target=end-pd.DateOffset(months=months)
            old=x.loc[:target]
            if old.empty or (target-old.index[-1]).days>10: continue
            a,b=old.iloc[-1],x.iloc[-1]
            if a.Oro<=0 or (unit=='%' and a.Factor<=0): continue
            gold=(b.Oro/a.Oro-1)*100
            change=(b.Factor-a.Factor)*100 if unit=='pb' else (b.Factor/a.Factor-1)*100
            expected=direction*change
            signal='Sin divergencia relevante'
            if abs(change)>=threshold and abs(gold)>=2 and expected*gold<0: signal='Alcista potencial' if expected>0 else 'Bajista potencial'
            windows=(13,26) if factor=='Liquidez neta' else (60,120)
            curves=correlation_series(data,factor,windows)
            vals=[v.loc[:end].dropna() for v in curves.values()]
            c1,c2=[v.iloc[-1] if not v.empty else float('nan') for v in vals]
            relevance='No aplica'
            if signal!='Sin divergencia relevante':
                relevance='Alta' if direction*c1>=.4 and direction*c2>=.3 else 'Media' if direction*c1>=.25 else 'Baja'
            rows.append({'Correlación reciente':round(c1,2),'Correlación larga':round(c2,2),'Ventanas corr.':'13/26 semanas' if factor=='Liquidez neta' else '60/120 sesiones','Relevancia':relevance,'Factor' :factor,'Ventana':f'{months}M','Desde':old.index[-1].date(),'Hasta':end.date(),'Oro (%)':round(gold,2),'Factor Δ':round(change,2),'Unidad':unit,'Lectura':signal})
    return pd.DataFrame(rows)
