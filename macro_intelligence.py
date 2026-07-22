import numpy as np
import pandas as pd


INDICADORES_INFLACION = {
    "cpi",
    "cpi yoy",
    "core cpi",
    "core cpi yoy",
    "pce",
    "pce yoy",
    "core pce",
    "core pce yoy",
}


def _serie(valores):
    return pd.Series(valores, dtype=float).dropna().reset_index(drop=True)


def _pendiente(serie):
    if len(serie) < 2:
        return 0.0
    x = np.arange(len(serie))
    return np.polyfit(x, serie.values, 1)[0]


def _limitar(valor, minimo=0.0, maximo=100.0):
    return float(max(minimo, min(maximo, valor)))


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
    return round(float(s.iloc[-1] - s.iloc[-periodos - 1]), 2)


def calcular_volatilidad(valores):
    s = _serie(valores)
    if len(s) < 5:
        return None
    return round(float(s.std()), 2)


def clasificar_percentil(percentil):
    if percentil is None:
        return "Sin datos"
    if percentil >= 90:
        return "Muy alto"
    if percentil >= 70:
        return "Alto"
    if percentil >= 30:
        return "Normal"
    if percentil >= 10:
        return "Bajo"
    return "Muy bajo"


def clasificar_macro_score(score):
    if score is None:
        return "No disponible"
    if score >= 90:
        return "Excelente"
    if score >= 75:
        return "Favorable"
    if score >= 60:
        return "Moderadamente favorable"
    if score >= 40:
        return "Neutral"
    if score >= 20:
        return "Desfavorable"
    return "Muy desfavorable"


def es_indicador_inflacion(indicador):
    nombre = str(indicador).strip().lower()
    return nombre in INDICADORES_INFLACION or "inflation" in nombre


def calcular_macro_score_inflacion(resultado):
    """Calcula una lectura de salud macroeconómica de la inflación (0-100)."""
    nombre = str(resultado["indicador"]).strip().lower()
    ultimo = resultado["ultimo_valor"]

    # Los indicadores interanuales se comparan con el objetivo del 2 %.
    # Para las variaciones mensuales se usa su equivalente aproximado (0,17 %).
    es_interanual = "yoy" in nombre or "annual" in nombre
    objetivo = 2.0 if es_interanual else 0.17
    tolerancia = 3.0 if es_interanual else 0.45

    distancia_objetivo = abs(ultimo - objetivo)
    score_objetivo = _limitar(100 - (distancia_objetivo / tolerancia) * 100)

    tendencia = resultado["tendencia_12"]
    if ultimo > objetivo:
        score_tendencia = {"Bajista": 100, "Lateral": 60, "Alcista": 20}.get(tendencia, 50)
    elif ultimo < objetivo:
        score_tendencia = {"Alcista": 100, "Lateral": 60, "Bajista": 20}.get(tendencia, 50)
    else:
        score_tendencia = 100

    momentum = resultado["momentum_3"]
    if momentum is None:
        score_momentum = 50
    elif ultimo > objetivo:
        score_momentum = 80 if momentum < 0 else 30 if momentum > 0 else 60
    elif ultimo < objetivo:
        score_momentum = 80 if momentum > 0 else 30 if momentum < 0 else 60
    else:
        score_momentum = 70

    percentil = resultado["percentil"]
    score_percentil = 50 if percentil is None else _limitar(100 - abs(percentil - 50) * 1.4)

    zscore = resultado["zscore"]
    score_zscore = 50 if zscore is None else _limitar(100 - abs(zscore) * 25)

    volatilidad = resultado["volatilidad"]
    if volatilidad is None:
        score_volatilidad = 50
    else:
        escala = max(abs(resultado["media_historica"]), 1.0)
        score_volatilidad = _limitar(100 - (volatilidad / escala) * 35)

    score = (
        score_objetivo * 0.40
        + score_tendencia * 0.20
        + score_momentum * 0.15
        + score_percentil * 0.10
        + score_zscore * 0.10
        + score_volatilidad * 0.05
    )

    return int(round(_limitar(score)))


def generar_resumen_generico(r):
    frases = []
    p = r["percentil"]

    if p is None:
        frases.append("No hay suficientes datos para situar el indicador históricamente.")
    elif p >= 90:
        frases.append("El indicador se encuentra en una zona históricamente muy elevada.")
    elif p <= 10:
        frases.append("El indicador se encuentra en una zona históricamente muy baja.")
    else:
        frases.append("El indicador se mantiene dentro de su rango histórico habitual.")

    t = r["tendencia_12"]
    if t == "Alcista":
        frases.append("La tendencia de los últimos 12 periodos es alcista.")
    elif t == "Bajista":
        frases.append("La tendencia de los últimos 12 periodos es bajista.")
    else:
        frases.append("La tendencia de fondo es lateral.")

    return " ".join(frases)


def generar_resumen_inflacion(r):
    nombre = str(r["indicador"]).strip().lower()
    objetivo = 2.0 if ("yoy" in nombre or "annual" in nombre) else 0.17
    ultimo = r["ultimo_valor"]
    tendencia = r["tendencia_12"]

    if ultimo > objetivo + (0.25 if objetivo == 2.0 else 0.08):
        nivel = "La inflación permanece por encima del nivel compatible con el objetivo del banco central."
        if tendencia == "Bajista":
            evolucion = "Sin embargo, la tendencia reciente apunta a una moderación gradual de las presiones inflacionistas."
        elif tendencia == "Alcista":
            evolucion = "Además, la tendencia continúa al alza, lo que indica una intensificación de las presiones inflacionistas."
        else:
            evolucion = "La tendencia se mantiene estable y todavía no confirma una normalización clara."
    elif ultimo < objetivo - (0.25 if objetivo == 2.0 else 0.08):
        nivel = "La inflación se sitúa por debajo del nivel de referencia del banco central."
        if tendencia == "Alcista":
            evolucion = "La tendencia reciente muestra una recuperación gradual hacia niveles más normales."
        elif tendencia == "Bajista":
            evolucion = "La tendencia continúa descendiendo, aumentando el riesgo de una inflación excesivamente débil."
        else:
            evolucion = "La evolución reciente se mantiene estable en niveles reducidos."
    else:
        nivel = "La inflación se encuentra cerca del nivel de referencia del banco central."
        evolucion = "La lectura actual es compatible con un entorno de mayor estabilidad de precios."

    return f"{nivel} {evolucion} Evaluación macro: {r['macro_rating']} ({r['macro_score']}/100)."


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
        "tipo_indicador": "inflacion" if es_indicador_inflacion(indicador) else "generico",
    }

    if resultado["tipo_indicador"] == "inflacion":
        resultado["macro_score"] = calcular_macro_score_inflacion(resultado)
        resultado["macro_rating"] = clasificar_macro_score(resultado["macro_score"])
        resultado["summary"] = generar_resumen_inflacion(resultado)
    else:
        resultado["macro_score"] = None
        resultado["macro_rating"] = "Pendiente de motor específico"
        resultado["summary"] = generar_resumen_generico(resultado)

    return resultado
