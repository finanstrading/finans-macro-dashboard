import numpy as np
import pandas as pd


# ==========================================================
# UTILIDADES
# ==========================================================

def _serie(valores):
    return pd.Series(valores, dtype=float).dropna().reset_index(drop=True)


def _pendiente(serie):
    if len(serie) < 2:
        return 0

    x = np.arange(len(serie))
    return np.polyfit(x, serie.values, 1)[0]


# ==========================================================
# TENDENCIA
# ==========================================================

def calcular_tendencia(valores, ventana):

    serie = _serie(valores)

    if len(serie) < ventana:
        ventana = len(serie)

    if ventana < 2:
        return "Sin datos"

    p = _pendiente(serie.tail(ventana))

    desviacion = serie.std()

    umbral = desviacion * 0.01

    if p > umbral:
        return "Alcista"

    if p < -umbral:
        return "Bajista"

    return "Lateral"


# ==========================================================
# PERCENTIL
# ==========================================================

def calcular_percentil(valor, historico):

    historico = _serie(historico)

    if historico.empty:
        return None

    return round(
        ((historico <= valor).sum() / len(historico)) * 100,
        1
    )


# ==========================================================
# Z SCORE
# ==========================================================

def calcular_zscore(valor, historico):

    historico = _serie(historico)

    if len(historico) < 2:
        return None

    std = historico.std()

    if std == 0:
        return 0

    return round((valor - historico.mean()) / std, 2)


# ==========================================================
# MOMENTUM
# ==========================================================

def calcular_momentum(serie, periodos):

    serie = _serie(serie)

    if len(serie) <= periodos:
        return None

    return round(
        serie.iloc[-1] - serie.iloc[-periodos-1],
        2
    )


# ==========================================================
# VOLATILIDAD
# ==========================================================

def calcular_volatilidad(serie):

    serie = _serie(serie)

    if len(serie) < 5:
        return None

    return round(float(serie.std()), 2)


# ==========================================================
# DISTANCIA A EXTREMOS
# ==========================================================

def distancia_maximo(valor, historico):

    historico = _serie(historico)

    return round(
        historico.max() - valor,
        2
    )


def distancia_minimo(valor, historico):

    historico = _serie(historico)

    return round(
        valor - historico.min(),
        2
    )


# ==========================================================
# CLASIFICACIÓN
# ==========================================================

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


# ==========================================================
# MOTOR PRINCIPAL
# ==========================================================

def analizar_indicador(
        fechas,
        valores,
        indicador,
        divisa
):

    serie = _serie(valores)

    if len(serie) < 2:
        return None

    ultimo = float(serie.iloc[-1])

    anterior = float(serie.iloc[-2])

    media = float(serie.mean())

    maximo = float(serie.max())

    minimo = float(serie.min())

    percentil = calcular_percentil(
        ultimo,
        serie
    )

    resultado = {

        "divisa": divisa,

        "indicador": indicador,

        "ultimo_valor": round(ultimo,2),

        "valor_anterior": round(anterior,2),

        "variacion": round(
            ultimo-anterior,
            2
        ),

        "media_historica": round(media,2),

        "maximo_historico": round(maximo,2),

        "minimo_historico": round(minimo,2),

        "percentil": percentil,

        "categoria_percentil":
            clasificar_percentil(percentil),

        "zscore":
            calcular_zscore(
                ultimo,
                serie
            ),

        "volatilidad":
            calcular_volatilidad(
                serie
            ),

        "momentum_3":
            calcular_momentum(
                serie,
                3
            ),

        "momentum_6":
            calcular_momentum(
                serie,
                6
            ),

        "momentum_12":
            calcular_momentum(
                serie,
                12
            ),

        "distancia_maximo":
            distancia_maximo(
                ultimo,
                serie
            ),

        "distancia_minimo":
            distancia_minimo(
                ultimo,
                serie
            ),

        "tendencia_3":
            calcular_tendencia(
                serie,
                3
            ),

        "tendencia_6":
            calcular_tendencia(
                serie,
                6
            ),

        "tendencia_12":
            calcular_tendencia(
                serie,
                12
            )

    }

    return resultado
