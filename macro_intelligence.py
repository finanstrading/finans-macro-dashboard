import numpy as np
import pandas as pd


def _serie(valores):
    return pd.Series(valores, dtype=float).dropna().reset_index(drop=True)


def _pendiente(serie):
    if len(serie) < 2:
        return 0.0
    x = np.arange(len(serie))
    return np.polyfit(x, serie.values, 1)[0]


def calcular_tendencia(valores, ventana):
    serie = _serie(valores)
    if len(serie) < ventana:
        ventana = len(serie)
    if ventana < 2:
        return "Sin datos"

    p = _pendiente(serie.tail(ventana))
    umbral = max(serie.std() * 0.01, 1e-9)

    if p > umbral:
        return "Alcista"
    if p < -umbral:
        return "Bajista"
    return "Lateral"


def calcular_percentil(valor, historico):
    h = _serie(historico)
    if h.empty:
        return None
    return round(((h <= valor).sum() / len(h)) * 100, 1)


def calcular_zscore(valor, historico):
    h = _serie(historico)
    if len(h) < 2:
        return None
    std = h.std()
    if std == 0:
        return 0.0
    return round((valor - h.mean()) / std, 2)


def calcular_momentum(valores, periodos):
    s = _serie(valores)
    if len(s) <= periodos:
        return None
    return round(float(s.iloc[-1] - s.iloc[-periodos-1]), 2)


def calcular_volatilidad(valores):
    s = _serie(valores)
    if len(s) < 5:
        return None
    return round(float(s.std()), 2)


def clasificar_percentil(percentil):
    if percentil is None:
        return "Sin datos"
    if percentil >= 90:
        return "Muy Alto"
    if percentil >= 70:
        return "Alto"
    if percentil >= 30:
        return "Normal"
    if percentil >= 10:
        return "Bajo"
    return "Muy Bajo"


def generar_resumen(r):
    frases = []

    p = r["percentil"]
    if p >= 90:
        frases.append("The indicator remains historically elevated.")
    elif p <= 10:
        frases.append("The indicator remains historically depressed.")
    else:
        frases.append("The indicator is trading within its historical range.")

    t = r["tendencia_12"]
    if t == "Alcista":
        frases.append("Long-term trend remains positive.")
    elif t == "Bajista":
        frases.append("Long-term trend remains negative.")
    else:
        frases.append("Long-term trend is neutral.")

    m = r["momentum_3"]
    if m is not None:
        if m > 0:
            frases.append("Recent momentum is improving.")
        elif m < 0:
            frases.append("Recent momentum is weakening.")

    z = r["zscore"]
    if z is not None:
        if z >= 2:
            frases.append("Current reading is well above its historical average.")
        elif z <= -2:
            frases.append("Current reading is well below its historical average.")

    return " ".join(frases)


def analizar_indicador(fechas, valores, indicador, divisa):
    s = _serie(valores)
    if len(s) < 2:
        return None

    ultimo = float(s.iloc[-1])
    anterior = float(s.iloc[-2])
    percentil = calcular_percentil(ultimo, s)

    resultado = {
        "divisa": divisa,
        "indicador": indicador,
        "ultimo_valor": round(ultimo, 2),
        "valor_anterior": round(anterior, 2),
        "variacion": round(ultimo - anterior, 2),
        "media_historica": round(float(s.mean()), 2),
        "maximo_historico": round(float(s.max()), 2),
        "minimo_historico": round(float(s.min()), 2),
        "percentil": percentil,
        "categoria_percentil": clasificar_percentil(percentil),
        "zscore": calcular_zscore(ultimo, s),
        "volatilidad": calcular_volatilidad(s),
        "momentum_3": calcular_momentum(s, 3),
        "momentum_6": calcular_momentum(s, 6),
        "momentum_12": calcular_momentum(s, 12),
        "distancia_maximo": round(float(s.max() - ultimo), 2),
        "distancia_minimo": round(float(ultimo - s.min()), 2),
        "tendencia_3": calcular_tendencia(s, 3),
        "tendencia_6": calcular_tendencia(s, 6),
        "tendencia_12": calcular_tendencia(s, 12),
    }

    resultado["summary"] = generar_resumen(resultado)
    return resultado
