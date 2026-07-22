import numpy as np
import pandas as pd

# V1 del motor cuantitativo


def calcular_tendencia(valores, ventana=6):
    serie=pd.Series(valores).dropna()
    if len(serie)<ventana: ventana=len(serie)
    if ventana<2:return 'Sin datos'
    p=np.polyfit(np.arange(ventana),serie.tail(ventana).values,1)[0]
    return 'Alcista' if p>0 else 'Bajista' if p<0 else 'Lateral'

def calcular_percentil(v,h):
    h=pd.Series(h).dropna()
    return None if h.empty else round(((h<=v).sum()/len(h))*100,1)

def analizar_indicador(fechas,valores,indicador,divisa):
    s=pd.Series(valores).dropna()
    if len(s)<2:return None
    u=float(s.iloc[-1]);a=float(s.iloc[-2])
    return {'divisa':divisa,'indicador':indicador,'ultimo_valor':u,'valor_anterior':a,'variacion':round(u-a,2),'media_historica':round(float(s.mean()),2),'maximo_historico':round(float(s.max()),2),'minimo_historico':round(float(s.min()),2),'percentil':calcular_percentil(u,s),'tendencia_3':calcular_tendencia(s,3),'tendencia_6':calcular_tendencia(s,6),'tendencia_12':calcular_tendencia(s,12)}

