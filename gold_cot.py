"""CFTC Disaggregated Futures Only — COMEX Gold."""
import pandas as pd
import requests
import streamlit as st

URL = 'https://publicreporting.cftc.gov/resource/72hh-3qpy.json'
FIELDS = {'report_date_as_yyyy_mm_dd':'Fecha', 'open_interest_all':'Open Interest', 'm_money_positions_long_all':'Long', 'm_money_positions_short_all':'Short'}

def prepare_gold_cot(rows):
    df = pd.DataFrame(rows).rename(columns=FIELDS)
    if not set(FIELDS.values()).issubset(df.columns):
        raise ValueError('Respuesta CFTC sin columnas requeridas')
    df = df[list(FIELDS.values())].copy()
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce', utc=True).dt.tz_convert(None).dt.normalize()
    for c in ('Open Interest','Long','Short'):
        df[c] = pd.to_numeric(df[c], errors='coerce')
    df = df.dropna().sort_values('Fecha').drop_duplicates('Fecha', keep='last').set_index('Fecha')
    df = df[(df['Open Interest']>0)&(df['Long']>=0)&(df['Short']>=0)]
    if df.empty: raise ValueError('Sin observaciones CFTC válidas')
    df['Net'] = df.Long-df.Short
    df['Net / OI'] = 100*df.Net/df['Open Interest']
    df['Cambio semanal'] = df.Net.diff().where(df.index.to_series().diff().dt.days.between(5,9))
    for n in (52,156):
        r = df['Net / OI'].rolling(n,min_periods=n)
        lo,hi = r.min(),r.max()
        df[f'COT {n}'] = 100*(df['Net / OI']-lo)/(hi-lo).replace(0,float('nan'))
    return df

@st.cache_data(ttl=3600,show_spinner=False)
def load_gold_cot():
    r=requests.get(URL,params={'$where':"cftc_contract_market_code='088691'",'$order':'report_date_as_yyyy_mm_dd DESC','$limit':1000,'$select':','.join(FIELDS)},timeout=20)
    r.raise_for_status()
    return prepare_gold_cot(r.json())
