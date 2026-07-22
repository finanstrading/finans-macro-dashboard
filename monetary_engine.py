import re
import unicodedata

import numpy as np
import pandas as pd

ENGINE_VERSION = "2026-07-22-MONETARY-V2"


# ============================================================
# CONFIGURACIÓN
# ============================================================

BANCOS_CENTRALES = {
    "USD": {
        "nombre": "Reserva Federal",
        "objetivo_inflacion": 2.0,
        "relevancia": {
            "inflacion": 1.00,
            "empleo": 1.00,
            "salarios": 0.90,
            "crecimiento": 0.70,
            "consumo": 0.65,
            "pmi": 0.55,
            "confianza": 0.35,
            "industria": 0.45,
        },
    },
    "EUR": {
        "nombre": "Banco Central Europeo",
        "objetivo_inflacion": 2.0,
        "relevancia": {
            "inflacion": 1.00,
            "empleo": 0.50,
            "salarios": 0.75,
            "crecimiento": 0.65,
            "consumo": 0.50,
            "pmi": 0.60,
            "confianza": 0.40,
            "industria": 0.50,
        },
    },
    "GBP": {
        "nombre": "Banco de Inglaterra",
        "objetivo_inflacion": 2.0,
        "relevancia": {
            "inflacion": 1.00,
            "empleo": 0.80,
            "salarios": 0.95,
            "crecimiento": 0.65,
            "consumo": 0.60,
            "pmi": 0.55,
            "confianza": 0.35,
            "industria": 0.45,
        },
    },
    "CAD": {
        "nombre": "Banco de Canadá",
        "objetivo_inflacion": 2.0,
        "relevancia": {
            "inflacion": 1.00,
            "empleo": 0.80,
            "salarios": 0.75,
            "crecimiento": 0.75,
            "consumo": 0.65,
            "pmi": 0.50,
            "confianza": 0.35,
            "industria": 0.50,
        },
    },
    "JPY": {
        "nombre": "Banco de Japón",
        "objetivo_inflacion": 2.0,
        "relevancia": {
            "inflacion": 1.00,
            "empleo": 0.65,
            "salarios": 1.00,
            "crecimiento": 0.60,
            "consumo": 0.70,
            "pmi": 0.50,
            "confianza": 0.30,
            "industria": 0.45,
        },
    },
    "AUD": {
        "nombre": "Banco de la Reserva de Australia",
        "objetivo_inflacion": 2.5,
        "relevancia": {
            "inflacion": 1.00,
            "empleo": 0.90,
            "salarios": 0.85,
            "crecimiento": 0.70,
            "consumo": 0.65,
            "pmi": 0.55,
            "confianza": 0.35,
            "industria": 0.45,
        },
    },
    "NZD": {
        "nombre": "Banco de la Reserva de Nueva Zelanda",
        "objetivo_inflacion": 2.0,
        "relevancia": {
            "inflacion": 1.00,
            "empleo": 0.90,
            "salarios": 0.85,
            "crecimiento": 0.70,
            "consumo": 0.65,
            "pmi": 0.50,
            "confianza": 0.35,
            "industria": 0.45,
        },
    },
    "CHF": {
        "nombre": "Banco Nacional Suizo",
        "objetivo_inflacion": 1.0,
        "relevancia": {
            "inflacion": 1.00,
            "empleo": 0.40,
            "salarios": 0.45,
            "crecimiento": 0.60,
            "consumo": 0.45,
            "pmi": 0.50,
            "confianza": 0.35,
            "industria": 0.45,
        },
    },
}


# ============================================================
# UTILIDADES ESTADÍSTICAS
# ============================================================

def _serie(valores):
    return pd.Series(valores, dtype=float).dropna().reset_index(drop=True)


def _limitar(valor, minimo=0.0, maximo=100.0):
    return float(max(minimo, min(maximo, valor)))


def _normalizar_texto(texto):
    texto = str(texto or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"\s+", " ", texto)
    return texto


def _pendiente(serie):
    if len(serie) < 2:
        return 0.0
    x = np.arange(len(serie))
    return float(np.polyfit(x, serie.values, 1)[0])


def calcular_tendencia(valores, ventana):
    serie = _serie(valores)
    if len(serie) < ventana:
        ventana = len(serie)
    if ventana < 2:
        return "Sin datos"

    pendiente = _pendiente(serie.tail(ventana))
    umbral = max(float(serie.std()) * 0.01, 1e-9)

    if pendiente > umbral:
        return "Alcista"
    if pendiente < -umbral:
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
    desviacion = float(h.std())
    if desviacion == 0:
        return 0.0
    return round((valor - float(h.mean())) / desviacion, 2)


def calcular_momentum(valores, periodos):
    serie = _serie(valores)
    if len(serie) <= periodos:
        return None
    return round(float(serie.iloc[-1] - serie.iloc[-periodos - 1]), 2)


def calcular_volatilidad(valores):
    serie = _serie(valores)
    if len(serie) < 5:
        return None
    return round(float(serie.std()), 2)


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


# ============================================================
# CLASIFICACIÓN DEL INDICADOR
# ============================================================

def clasificar_indicador(indicador):
    nombre = _normalizar_texto(indicador)

    if any(p in nombre for p in (
        "cpi", "inflation", "inflacion", "pce", "ppi",
        "consumer price", "producer price", "deflator"
    )):
        return "inflacion"

    if any(p in nombre for p in (
        "average earnings", "wage", "wages", "salario", "salary",
        "labor cost", "labour cost", "employment cost", "unit labor"
    )):
        return "salarios"

    if any(p in nombre for p in (
        "unemployment", "desempleo", "employment", "empleo",
        "payroll", "jobless", "claims", "claimant", "vacancies",
        "labor force", "labour force", "participation rate", "ccc"
    )):
        return "empleo"

    if any(p in nombre for p in (
        "gdp", "gross domestic product", "growth rate", "economic growth"
    )):
        return "crecimiento"

    if any(p in nombre for p in (
        "retail sales", "core retail", "consumer spending",
        "personal spending", "household spending", "consumption"
    )):
        return "consumo"

    if "pmi" in nombre or "purchasing managers" in nombre or "ism" in nombre:
        return "pmi"

    if any(p in nombre for p in (
        "consumer confidence", "business confidence", "economic sentiment",
        "zew", "ifo", "business climate", "confidence"
    )):
        return "confianza"

    if any(p in nombre for p in (
        "industrial production", "manufacturing production",
        "factory orders", "durable goods", "capacity utilization",
        "capacity utilisation", "industrial"
    )):
        return "industria"

    return "sin_clasificar"


def detectar_direccion_inversa(indicador):
    """
    True cuando una subida del indicador implica, en general,
    menos presión hawkish.
    """
    nombre = _normalizar_texto(indicador)
    return any(p in nombre for p in (
        "unemployment", "desempleo", "jobless", "claims",
        "claimant", "layoff"
    ))


def detectar_frecuencia(indicador):
    nombre = _normalizar_texto(indicador)

    if any(p in nombre for p in ("yoy", "y/y", "annual", "anual", "year over year")):
        return "interanual"
    if any(p in nombre for p in ("qoq", "q/q", "quarterly", "trimestral")):
        return "trimestral"
    if any(p in nombre for p in ("mom", "m/m", "monthly", "mensual")):
        return "mensual"

    # Convención usada en el dashboard: CPI sin YoY suele ser mensual.
    if "cpi" in nombre and "yoy" not in nombre:
        return "mensual"

    return "desconocida"


# ============================================================
# CLASIFICACIÓN DEL SCORE
# ============================================================

def clasificar_presion(score):
    if score >= 85:
        return "Fuertemente hawkish"
    if score >= 66:
        return "Hawkish"
    if score >= 56:
        return "Ligeramente hawkish"
    if score >= 45:
        return "Neutral"
    if score >= 35:
        return "Ligeramente dovish"
    if score >= 16:
        return "Dovish"
    return "Fuertemente dovish"


def relevancia_texto(relevancia):
    if relevancia >= 0.90:
        return "Muy alta"
    if relevancia >= 0.70:
        return "Alta"
    if relevancia >= 0.50:
        return "Media"
    return "Baja"


# ============================================================
# COMPONENTES COMUNES
# ============================================================

def score_tendencia(resultado, inverso=False):
    tendencia = resultado["tendencia_12"]
    if tendencia == "Alcista":
        valor = 70.0
    elif tendencia == "Bajista":
        valor = 30.0
    else:
        valor = 50.0
    return 100.0 - valor if inverso else valor


def score_momentum(resultado, inverso=False):
    momentum = resultado["momentum_3"]
    volatilidad = resultado["volatilidad"]

    if momentum is None:
        return 50.0

    escala = max(abs(volatilidad or 0.0), abs(resultado["media_historica"]) * 0.10, 0.10)
    valor = 50.0 + 25.0 * np.tanh(momentum / escala)
    if inverso:
        valor = 100.0 - valor
    return _limitar(valor)


def score_historico(resultado, inverso=False):
    percentil = resultado["percentil"]
    if percentil is None:
        return 50.0
    return 100.0 - percentil if inverso else percentil


def score_persistencia(serie, referencia, inverso=False, ventana=6):
    reciente = _serie(serie).tail(ventana)
    if reciente.empty:
        return 50.0

    if inverso:
        proporcion = float((reciente < referencia).mean())
    else:
        proporcion = float((reciente > referencia).mean())

    return _limitar(proporcion * 100.0)


def score_nivel_relativo(resultado, inverso=False):
    zscore = resultado["zscore"]
    if zscore is None:
        return 50.0

    valor = 50.0 + 22.0 * np.tanh(zscore / 1.5)
    if inverso:
        valor = 100.0 - valor
    return _limitar(valor)


# ============================================================
# MOTORES POR FAMILIA
# ============================================================

def motor_inflacion(serie, resultado, indicador, objetivo):
    ultimo = resultado["ultimo_valor"]
    frecuencia = detectar_frecuencia(indicador)

    if frecuencia == "mensual":
        # Aproximación anualizada compuesta para evitar comparar directamente
        # un dato mensual con un objetivo anual.
        ritmo_equivalente = ((1.0 + ultimo / 100.0) ** 12 - 1.0) * 100.0
        desviacion = ritmo_equivalente - objetivo
        score_mandato = 50.0 + 32.0 * np.tanh(desviacion / 1.5)
        referencia_persistencia = ((1.0 + objetivo / 100.0) ** (1.0 / 12.0) - 1.0) * 100.0
        etiqueta_nivel = f"ritmo mensual anualizado aproximado de {ritmo_equivalente:.1f}%"
    else:
        desviacion = ultimo - objetivo
        score_mandato = 50.0 + 32.0 * np.tanh(desviacion / 1.5)
        referencia_persistencia = objetivo
        etiqueta_nivel = f"{ultimo:.2f}% frente a un objetivo de {objetivo:.1f}%"

    componentes = {
        "Mandato de estabilidad de precios": _limitar(score_mandato),
        "Tendencia": score_tendencia(resultado),
        "Impulso reciente": score_momentum(resultado),
        "Persistencia": score_persistencia(
            serie, referencia_persistencia, inverso=False, ventana=6
        ),
        "Posición histórica": score_historico(resultado),
    }

    pesos = {
        "Mandato de estabilidad de precios": 0.45,
        "Tendencia": 0.20,
        "Impulso reciente": 0.15,
        "Persistencia": 0.15,
        "Posición histórica": 0.05,
    }

    return componentes, pesos, etiqueta_nivel


def motor_crecimiento(serie, resultado, indicador, objetivo):
    ultimo = resultado["ultimo_valor"]
    frecuencia = detectar_frecuencia(indicador)

    if frecuencia == "trimestral":
        # Neutral aproximado: crecimiento trimestral positivo pero moderado.
        neutral = 0.4
        escala = 0.6
    elif frecuencia == "interanual":
        neutral = 1.5
        escala = 1.5
    else:
        neutral = float(resultado["media_historica"])
        escala = max(abs(resultado["volatilidad"] or 1.0), 0.5)

    nivel = 50.0 + 28.0 * np.tanh((ultimo - neutral) / escala)

    recientes = _serie(serie).tail(2)
    riesgo_recesion = 50.0
    if len(recientes) == 2 and (recientes < 0).all():
        riesgo_recesion = 10.0
    elif ultimo < 0:
        riesgo_recesion = 25.0
    elif ultimo > 0:
        riesgo_recesion = 65.0

    componentes = {
        "Ritmo de crecimiento": _limitar(nivel),
        "Tendencia": score_tendencia(resultado),
        "Impulso reciente": score_momentum(resultado),
        "Riesgo de contracción": riesgo_recesion,
        "Posición histórica": score_historico(resultado),
    }

    pesos = {
        "Ritmo de crecimiento": 0.35,
        "Tendencia": 0.25,
        "Impulso reciente": 0.20,
        "Riesgo de contracción": 0.15,
        "Posición histórica": 0.05,
    }

    return componentes, pesos, f"crecimiento actual de {ultimo:.2f}%"


def motor_empleo(serie, resultado, indicador, objetivo):
    inverso = detectar_direccion_inversa(indicador)
    ultimo = resultado["ultimo_valor"]

    componentes = {
        "Nivel del mercado laboral": score_nivel_relativo(resultado, inverso=inverso),
        "Tendencia": score_tendencia(resultado, inverso=inverso),
        "Impulso reciente": score_momentum(resultado, inverso=inverso),
        "Persistencia": score_persistencia(
            serie,
            float(resultado["media_historica"]),
            inverso=inverso,
            ventana=6,
        ),
        "Posición histórica": score_historico(resultado, inverso=inverso),
    }

    pesos = {
        "Nivel del mercado laboral": 0.35,
        "Tendencia": 0.25,
        "Impulso reciente": 0.20,
        "Persistencia": 0.15,
        "Posición histórica": 0.05,
    }

    direccion = "una lectura menor es más hawkish" if inverso else "una lectura mayor es más hawkish"
    return componentes, pesos, f"{ultimo:.2f}; {direccion}"


def motor_salarios(serie, resultado, indicador, objetivo):
    componentes = {
        "Presión salarial": score_nivel_relativo(resultado),
        "Tendencia": score_tendencia(resultado),
        "Impulso reciente": score_momentum(resultado),
        "Persistencia": score_persistencia(
            serie, float(resultado["media_historica"]), ventana=6
        ),
        "Posición histórica": score_historico(resultado),
    }

    pesos = {
        "Presión salarial": 0.40,
        "Tendencia": 0.20,
        "Impulso reciente": 0.20,
        "Persistencia": 0.15,
        "Posición histórica": 0.05,
    }

    return componentes, pesos, f"crecimiento salarial actual de {resultado['ultimo_valor']:.2f}%"


def motor_consumo(serie, resultado, indicador, objetivo):
    componentes = {
        "Fortaleza del consumo": score_nivel_relativo(resultado),
        "Tendencia": score_tendencia(resultado),
        "Impulso reciente": score_momentum(resultado),
        "Persistencia": score_persistencia(
            serie, float(resultado["media_historica"]), ventana=6
        ),
        "Posición histórica": score_historico(resultado),
    }

    pesos = {
        "Fortaleza del consumo": 0.35,
        "Tendencia": 0.25,
        "Impulso reciente": 0.20,
        "Persistencia": 0.15,
        "Posición histórica": 0.05,
    }

    return componentes, pesos, f"consumo actual de {resultado['ultimo_valor']:.2f}%"


def motor_pmi(serie, resultado, indicador, objetivo):
    ultimo = resultado["ultimo_valor"]
    nivel = 50.0 + 30.0 * np.tanh((ultimo - 50.0) / 5.0)

    componentes = {
        "Expansión o contracción": _limitar(nivel),
        "Tendencia": score_tendencia(resultado),
        "Impulso reciente": score_momentum(resultado),
        "Persistencia sobre 50": score_persistencia(serie, 50.0, ventana=6),
        "Posición histórica": score_historico(resultado),
    }

    pesos = {
        "Expansión o contracción": 0.35,
        "Tendencia": 0.25,
        "Impulso reciente": 0.20,
        "Persistencia sobre 50": 0.15,
        "Posición histórica": 0.05,
    }

    return componentes, pesos, f"PMI actual de {ultimo:.2f} puntos"


def motor_confianza(serie, resultado, indicador, objetivo):
    componentes = {
        "Nivel de confianza": score_nivel_relativo(resultado),
        "Tendencia": score_tendencia(resultado),
        "Impulso reciente": score_momentum(resultado),
        "Persistencia": score_persistencia(
            serie, float(resultado["media_historica"]), ventana=6
        ),
        "Posición histórica": score_historico(resultado),
    }

    pesos = {
        "Nivel de confianza": 0.30,
        "Tendencia": 0.30,
        "Impulso reciente": 0.25,
        "Persistencia": 0.10,
        "Posición histórica": 0.05,
    }

    return componentes, pesos, f"confianza actual de {resultado['ultimo_valor']:.2f}"


def motor_industria(serie, resultado, indicador, objetivo):
    componentes = {
        "Actividad industrial": score_nivel_relativo(resultado),
        "Tendencia": score_tendencia(resultado),
        "Impulso reciente": score_momentum(resultado),
        "Persistencia": score_persistencia(
            serie, float(resultado["media_historica"]), ventana=6
        ),
        "Posición histórica": score_historico(resultado),
    }

    pesos = {
        "Actividad industrial": 0.35,
        "Tendencia": 0.25,
        "Impulso reciente": 0.20,
        "Persistencia": 0.15,
        "Posición histórica": 0.05,
    }

    return componentes, pesos, f"actividad industrial actual de {resultado['ultimo_valor']:.2f}%"


MOTORES = {
    "inflacion": motor_inflacion,
    "crecimiento": motor_crecimiento,
    "empleo": motor_empleo,
    "salarios": motor_salarios,
    "consumo": motor_consumo,
    "pmi": motor_pmi,
    "confianza": motor_confianza,
    "industria": motor_industria,
}


# ============================================================
# INTERPRETACIÓN
# ============================================================

def calcular_score(componentes, pesos):
    return round(
        sum(componentes[nombre] * pesos[nombre] for nombre in pesos),
        1,
    )


def ajustar_por_relevancia(score_base, relevancia):
    """
    La relevancia no cambia la dirección del indicador.
    Reduce su distancia respecto a 50 cuando el bloque tiene menos peso
    en la función de reacción del banco central.
    """
    return round(50.0 + (score_base - 50.0) * relevancia, 1)


def generar_impulso_monetario(resultado, indicador):
    momentum = resultado["momentum_3"]
    if momentum is None:
        return "Sin datos"

    inverso = detectar_direccion_inversa(indicador)
    impulso_hawkish = -momentum if inverso else momentum

    if impulso_hawkish > 0:
        return "Más hawkish"
    if impulso_hawkish < 0:
        return "Más dovish"
    return "Neutral"


def generar_resumen(resultado):
    familia = resultado["tipo_indicador"]
    score = resultado["macro_score"]
    rating = resultado["macro_rating"]
    banco = resultado["banco_central"]
    nivel = resultado["descripcion_nivel"]
    tendencia = resultado["tendencia_12"]
    impulso = resultado["impulso_monetario"]

    frases_inicio = {
        "inflacion": f"La lectura de inflación refleja {nivel}.",
        "crecimiento": f"El indicador de crecimiento refleja {nivel}.",
        "empleo": f"El indicador laboral refleja {nivel}.",
        "salarios": f"El indicador salarial refleja {nivel}.",
        "consumo": f"El indicador de consumo refleja {nivel}.",
        "pmi": f"El indicador de actividad refleja {nivel}.",
        "confianza": f"El indicador de confianza refleja {nivel}.",
        "industria": f"El indicador industrial refleja {nivel}.",
    }

    inicio = frases_inicio.get(
        familia,
        f"El indicador seleccionado refleja {nivel}."
    )

    if tendencia == "Alcista":
        frase_tendencia = "La tendencia de los últimos 12 periodos es alcista."
    elif tendencia == "Bajista":
        frase_tendencia = "La tendencia de los últimos 12 periodos es bajista."
    else:
        frase_tendencia = "La tendencia de los últimos 12 periodos es lateral."

    if impulso == "Más hawkish":
        frase_impulso = "El impulso reciente aumenta la presión monetaria."
    elif impulso == "Más dovish":
        frase_impulso = "El impulso reciente reduce la presión monetaria."
    else:
        frase_impulso = "El impulso reciente es neutral."

    cierre = (
        f"Considerando su relevancia para {banco}, la presión derivada "
        f"de este indicador es {rating.lower()} ({score:.1f}/100)."
    )

    return " ".join((inicio, frase_tendencia, frase_impulso, cierre))


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================

def analizar_indicador(fechas, valores, indicador, divisa):
    serie = _serie(valores)
    if len(serie) < 2:
        return None

    ultimo = float(serie.iloc[-1])
    anterior = float(serie.iloc[-2])
    percentil = calcular_percentil(ultimo, serie)

    resultado = {
        "divisa": divisa,
        "indicador": indicador,
        "ultimo_valor": round(ultimo, 2),
        "valor_anterior": round(anterior, 2),
        "variacion": round(ultimo - anterior, 2),
        "media_historica": round(float(serie.mean()), 2),
        "maximo_historico": round(float(serie.max()), 2),
        "minimo_historico": round(float(serie.min()), 2),
        "percentil": percentil,
        "categoria_percentil": clasificar_percentil(percentil),
        "zscore": calcular_zscore(ultimo, serie),
        "volatilidad": calcular_volatilidad(serie),
        "momentum_3": calcular_momentum(serie, 3),
        "momentum_6": calcular_momentum(serie, 6),
        "momentum_12": calcular_momentum(serie, 12),
        "distancia_maximo": round(float(serie.max() - ultimo), 2),
        "distancia_minimo": round(float(ultimo - serie.min()), 2),
        "tendencia_3": calcular_tendencia(serie, 3),
        "tendencia_6": calcular_tendencia(serie, 6),
        "tendencia_12": calcular_tendencia(serie, 12),
    }

    tipo = clasificar_indicador(indicador)
    config_banco = BANCOS_CENTRALES.get(
        str(divisa).upper(),
        {
            "nombre": "el banco central",
            "objetivo_inflacion": 2.0,
            "relevancia": {},
        },
    )

    resultado["tipo_indicador"] = tipo
    resultado["banco_central"] = config_banco["nombre"]

    if tipo not in MOTORES:
        resultado.update({
            "macro_score": None,
            "macro_rating": "Pendiente de clasificación",
            "impulso_monetario": "Sin evaluación",
            "componentes_score": {},
            "relevancia_texto": "Sin clasificar",
            "descripcion_nivel": f"un valor actual de {ultimo:.2f}",
            "summary": (
                "El indicador todavía no está clasificado dentro de un motor "
                "de presión monetaria. Las métricas estadísticas sí están disponibles."
            ),
        })
        return resultado

    relevancia = float(config_banco["relevancia"].get(tipo, 0.50))
    motor = MOTORES[tipo]

    componentes, pesos, descripcion_nivel = motor(
        serie,
        resultado,
        indicador,
        float(config_banco["objetivo_inflacion"]),
    )

    score_base = calcular_score(componentes, pesos)
    score_ajustado = ajustar_por_relevancia(score_base, relevancia)

    resultado.update({
        "macro_score": score_ajustado,
        "macro_score_base": score_base,
        "macro_rating": clasificar_presion(score_ajustado),
        "impulso_monetario": generar_impulso_monetario(resultado, indicador),
        "componentes_score": {
            nombre: round(float(valor), 1)
            for nombre, valor in componentes.items()
        },
        "pesos_score": pesos,
        "relevancia": relevancia,
        "relevancia_texto": relevancia_texto(relevancia),
        "descripcion_nivel": descripcion_nivel,
    })

    resultado["summary"] = generar_resumen(resultado)
    return resultado
