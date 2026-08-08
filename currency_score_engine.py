from typing import Dict, Any


# ============================================================
# CONFIGURACIÓN DE PONDERACIONES
# ============================================================

CURRENCY_WEIGHTS = {
    "USD": {
        "families": {
            "inflacion": 0.30,
            "empleo": 0.30,
            "actividad": 0.20,
            "demanda": 0.12,
            "sentimiento": 0.08,
        },

        "indicators": {
            "inflacion": {
                "Core CPI YoY": 0.40,
                "CPI YoY": 0.35,
                "Core PPI MoM": 0.15,
                "PPI MoM": 0.10,
            },

            "empleo": {
                "Non Farm Payrolls": 0.35,
                "Unemployment Rate": 0.30,
                "Average Hourly Earnings": 0.25,
                "JOLTS": 0.06,
                "ADP Employment": 0.04,
            },

            "actividad": {
                "GDP Growth Rate (QoQ)": 0.35,
                "ISM Services": 0.30,
                "ISM Manufacturing": 0.25,
                "GDP Annual Growth Rate (YoY)": 0.10,
            },

            "demanda": {
                "Core Retail Sales": 0.55,
                "Retail Sales MoM": 0.45,
            },

            "sentimiento": {
                "Consumer Confidence CB": 1.00,
            },
        },
    },
}


# ============================================================
# UTILIDADES
# ============================================================

def _normalizar_divisa(divisa: str) -> str:
    return str(divisa or "").strip().upper()


def _limitar_score(valor: float) -> float:
    return max(0.0, min(100.0, float(valor)))


# ============================================================
# CÁLCULO DE FAMILIA
# ============================================================

def calcular_score_familia(
    resultados_indicadores: Dict[str, Dict[str, Any]],
    pesos_indicadores: Dict[str, float],
) -> Dict[str, Any]:
    """
    Calcula el score de una familia utilizando macro_score_base.

    Si falta algún indicador:
    - no se asigna automáticamente 50;
    - se redistribuyen los pesos entre los indicadores disponibles.
    """

    usados = {}
    peso_disponible = 0.0

    for indicador, peso in pesos_indicadores.items():
        resultado = resultados_indicadores.get(indicador)

        if not resultado:
            continue

        score = resultado.get("macro_score_base")

        if score is None:
            continue

        score = _limitar_score(score)

        usados[indicador] = {
            "score": score,
            "peso_original": peso,
        }

        peso_disponible += peso

    if not usados or peso_disponible <= 0:
        return {
            "score": None,
            "indicators": {},
            "coverage": 0.0,
        }

    score_familia = 0.0

    for indicador, datos in usados.items():
        peso_normalizado = (
            datos["peso_original"] / peso_disponible
        )

        datos["peso_normalizado"] = peso_normalizado
        datos["contribution"] = (
            datos["score"] * peso_normalizado
        )

        score_familia += datos["contribution"]

    return {
        "score": round(score_familia, 1),
        "indicators": usados,
        "coverage": round(peso_disponible, 4),
    }


# ============================================================
# CÁLCULO DE DIVISA
# ============================================================

def calcular_currency_score(
    divisa: str,
    resultados_indicadores: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:

    currency = _normalizar_divisa(divisa)

    config = CURRENCY_WEIGHTS.get(currency)

    if not config:
        raise ValueError(
            f"No existe configuración de Currency Score para {currency}."
        )

    resultados_familias = {}
    peso_familias_disponible = 0.0

    for familia, peso_familia in config["families"].items():

        pesos_indicadores = config["indicators"].get(
            familia,
            {}
        )

        resultado_familia = calcular_score_familia(
            resultados_indicadores,
            pesos_indicadores,
        )

        resultado_familia["peso_original"] = peso_familia

        resultados_familias[familia] = resultado_familia

        if resultado_familia["score"] is not None:
            peso_familias_disponible += peso_familia

    if peso_familias_disponible <= 0:
        return {
            "currency": currency,
            "score": None,
            "families": resultados_familias,
            "coverage": 0.0,
        }

    currency_score = 0.0

    for familia, resultado in resultados_familias.items():

        if resultado["score"] is None:
            continue

        peso_normalizado = (
            resultado["peso_original"]
            / peso_familias_disponible
        )

        resultado["peso_normalizado"] = peso_normalizado

        resultado["contribution"] = (
            resultado["score"] * peso_normalizado
        )

        currency_score += resultado["contribution"]

    return {
        "currency": currency,
        "score": round(currency_score, 1),
        "families": resultados_familias,
        "coverage": round(
            peso_familias_disponible,
            4,
        ),
    }


# ============================================================
# CLASIFICACIÓN
# ============================================================

def clasificar_currency_score(score):

    if score is None:
        return "Sin datos"

    if score >= 75:
        return "Fuertemente hawkish"

    if score >= 62:
        return "Hawkish"

    if score >= 55:
        return "Ligeramente hawkish"

    if score >= 45:
        return "Neutral"

    if score >= 38:
        return "Ligeramente dovish"

    if score >= 25:
        return "Dovish"

    return "Fuertemente dovish"
