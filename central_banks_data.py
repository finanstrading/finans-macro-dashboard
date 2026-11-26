"""MacroFX: series oficiales, sin interpolación ni credenciales nuevas."""
import io
import pandas as pd
import requests
import streamlit as st

BANKS = {'BOJ':('JP','JPY','DEXJPUS','USD/JPY'), 'BNS':('CH','CHF','DEXSZUS','USD/CHF'), 'BOE':('GB','GBP','DEXUSUK','GBP/USD'), 'FED':('US','USD','DTWEXBGS','Dólar ponderado por comercio')}
DETAIL = {'FED': {'Bonos del Tesoro':('TREAST',.001),'MBS':('WSHOMCB',.001),'Reservas bancarias':('WRBWFRBL',.001),'TGA':('WDTGAL',.001),'Reverse repo':('RRPONTSYD',1),'Swaps de liquidez':('SWPT',.001)}}
LINKS={'BOJ':'https://www.mof.go.jp/english/policy/international_policy/reference/feio/monthly/index.html','BNS':'https://data.snb.ch/en','BOE':'https://www.bankofengland.co.uk/weekly-report/balance-sheet-and-weekly-report','FED':'https://www.newyorkfed.org/markets/quar_reports'}

@st.cache_data(ttl=3600, show_spinner=False)
def fred(code):
    r=requests.get('https://fred.stlouisfed.org/graph/fredgraph.csv',params={'id':code,'cosd':'2000-01-01'},timeout=(5,15)); r.raise_for_status()
    d=pd.read_csv(io.StringIO(r.text)); return series(d.iloc[:,0],d[code])

def series(d,v):
    s=pd.Series(pd.to_numeric(v,errors='coerce').to_numpy(),index=pd.to_datetime(d,errors='coerce')).dropna()
    s=s[~s.index.isna()].sort_index(); return s[~s.index.duplicated(keep='last')]

@st.cache_data(ttl=3600,show_spinner=False)
def bis(country):
    # Valor en moneda nacional; multiplicador publicado por BIS.
    key=f'M.{country}.B.XDC.{BANKS["BNS"][1] if country=="CH" else "GBP"}.N'
    r=requests.get(f'https://stats.bis.org/api/v1/data/BIS,WS_CBTA,1.0/{key}',params={'format':'csv','startPeriod':'2000-01'},headers={'Accept':'text/csv'},timeout=(5,20)); r.raise_for_status()
    d=pd.read_csv(io.StringIO(r.text)); d=d[d['UNIT_MULT'].notna()]; v=pd.to_numeric(d['OBS_VALUE'],errors='coerce')*10.0**(pd.to_numeric(d['UNIT_MULT'],errors='raise')-9)
    return series(d['TIME_PERIOD'],v)

@st.cache_data(ttl=3600,show_spinner=False)
def japan_interventions_raw():
    url='https://www.mof.go.jp/english/policy/international_policy/reference/feio/foreign_exchange_intervention_operations.csv'
    r=requests.get(url,timeout=(5,20)); r.raise_for_status()
    return pd.read_csv(io.BytesIO(r.content),encoding='cp932',header=None,dtype=str,on_bad_lines='error')

def load_bank(bank):
    country,ccy,fxcode,fxname=BANKS[bank]; data={}; sources={}; errors=[]
    def get(label, fn, source):
        try:
            s=fn()
            if s.empty: raise ValueError('sin observaciones')
            data[label]=s; sources[label]=source
        except Exception as e: errors.append(f'{label}: {type(e).__name__}')
    get('Activos totales',lambda: fred('WALCL')*.001 if bank=='FED' else fred('JPNASSETS')*.1 if bank=='BOJ' else bis(country),'FRED · WALCL' if bank=='FED' else 'BOJ/FRED · JPNASSETS' if bank=='BOJ' else 'BIS · WS_CBTA (mensual, moneda local)')
    code=f'TRESEG{country}M052N'; get('Reservas oficiales sin oro',lambda:fred(code)*.001,'FMI/FRED · '+code)
    if 'Reservas oficiales sin oro' not in data:
        get('Reservas oficiales sin oro',lambda:worldbank_reserves(country),'Banco Mundial · FI.RES.XGLD.CD (anual, cierre de año)')
    if bank=='BNS':
        get('Sight deposits bancos nacionales',snb_sight,'BNS · snbgwdchfsgw GI (media semanal, CHF)')
    get(fxname,lambda:fred(fxcode),'FED/FRED · '+fxcode)
    for name,(code,factor) in DETAIL.get(bank,{}).items(): get(name,lambda c=code,f=factor:fred(c)*f,'FRED · '+code)
    if bank=='FED' and all(k in data for k in ('Activos totales','TGA','Reverse repo')):
        a,b,c=(data[k] for k in ('Activos totales','TGA','Reverse repo')); d=pd.concat([a,b,c],axis=1,join='inner').dropna(); data['Liquidez neta estimada']=d.iloc[:,0]-d.iloc[:,1]-d.iloc[:,2]; sources['Liquidez neta estimada']='WALCL − WDTGAL − RRPONTSYD'
    return data,sources,errors

@st.cache_data(ttl=3600,show_spinner=False)
def worldbank_reserves(country):
    r=requests.get(f'https://api.worldbank.org/v2/country/{country}/indicator/FI.RES.XGLD.CD',params={'format':'json','per_page':100},timeout=(5,15)); r.raise_for_status()
    rows=r.json()[1]
    return series([str(x['date'])+'-12-31' for x in rows],[x['value']/1e9 if x['value'] is not None else None for x in rows])

@st.cache_data(ttl=3600,show_spinner=False)
def snb_csv(cube):
    r=requests.get(f'https://data.snb.ch/api/cube/{cube}/data/csv/en',timeout=(5,20)); r.raise_for_status()
    lines=r.content.decode('utf-8-sig').splitlines()
    for i,line in enumerate(lines):
        if line.lower().startswith('date;') and 'value' in line.lower():
            return pd.read_csv(io.StringIO('\n'.join(lines[i:])),sep=';',dtype=str)
    raise ValueError('Cabecera SNB no reconocida')

def snb_sight():
    d=snb_csv('snbgwdchfsgw'); d=d[d['D0']=='GI']; return series(d['Date'],d['Value'])*.001

def snb_transactions_raw():
    return snb_csv('snbfxtr')
