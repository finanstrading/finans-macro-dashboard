import numpy as np
import pandas as pd


INDICADORES_INFLACION = {
    "cpi", "cpi yoy", "core cpi", "core cpi yoy",
    "pce", "pce yoy", "core pce", "core pce yoy",
    "inflation", "inflation yoy", "core inflation", "core inflation yoy",
}

# El peso refleja cuánto domina la estabilidad de precios dentro del mandato.
# No pretende sustituir la lectura completa de empleo, crecimiento o estabilidad financiera.
PERFILES_BANCO_CENTRAL = {
    "USD": {"banco": "Reserva Federal", "objetivo": 2.0, "peso_precios": 0.72, "medida_preferida": "PCE"},
    "EUR": {"banco": "BCE", "objetivo": 2.0, "peso_precios": 0.95, "medida_preferida": "HICP"},
    "GBP": {"banco": "Banco de Inglaterra", "objetivo": 2.0, "peso_precios": 0.90, "medida_preferida": "CPI"},
    "CAD": {"banco": "Banco de Canadá", "objetivo": 2.0, "peso_precios": 0.90, "medida_preferida": "CPI"},
    "JPY": {"banco": "Banco de Japón", "objetivo": 2.0, "peso_precios": 0.90, "medida_preferida": "CPI"},
    "AUD": {"banco": "RBA", "objetivo": 2.5, "peso_precios": 0.75, "medida_preferida": "CPI"},
    "NZD": {"banco": "RBNZ", "objetivo": 2.0, "peso_precios": 0.90, "medida_preferida": "CPI"},
    "CHF": {"banco": "BNS", "objetivo": 1.0, "peso_precios": 0.95, "medida_preferida": "CPI"},
}


def _serie(valores):
    return pd.Series(valores, dtype=float).dropna().reset_index(drop=True)


def _pendiente(serie):
    if len(serie) < 2:
        return 0.0
    x = np.arange(len(serie))
    return float(np.polyfit(x, serie.values, 1)[0])


def _limitar(valor, minimo=0.0, maximo=100.0):
    return float(max(minimo, min(maximo, valor)))


def _es_interanual(indicador):
    nombre = str(indicador).strip().lower()
    return "yoy" in nombre or "annual" in nombre or "interanual" in nombre


def _es_subyacente(indicador):
    nombre = str(indicador).strip().lower()
    return "core" in nombre or "subyacente" in nombre


def _anualizar_mensual(valor_mensual):
    if valor_mensual <= -100:
        return -100.0
    return ((1.0 + valor_mensual / 100.0) ** 12 - 1.0) * 100.0


def calcular_tendencia(valores, ventana):
    serie = _serie(valores)
    if len(serie) < ventana:
        ventana = len(serie)
    if ventana < 2:
        return "Sin datos"

    p = _pendiente(serie.tail(ventana))
    umbral = max(float(serie.std()) * 0.01, 1e-9)
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
    std = float(h.std())
    if std == 0:
        return 0.0
    return round((valor - float(h.mean())) / std, 2)


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


def clasificar_presion(score):
    if score is None:
        return "No disponible"
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


def es_indicador_inflacion(indicador):
    nombre = str(indicador).strip().lower()
    return nombre in INDICADORES_INFLACION or "inflation" in nombre or "cpi" in nombre or "pce" in nombre


def _relevancia_medida(indicador, divisa):
    nombre = str(indicador).strip().lower()
    if divisa == "USD":
        return 1.0 if "pce" in nombre else 0.88
    return 1.0


def calcular_presion_inflacion(resultado):
    """Score 0-100: bajo=dovish, alto=hawkish para el banco central."""
    perfil = PERFILES_BANCO_CENTRAL.get(
        resultado["divisa"],
        {"banco": "Banco central", "objetivo": 2.0, "peso_precios": 0.85, "medida_preferida": "CPI"},
    )
    indicador = resultado["indicador"]
    interanual = _es_interanual(indicador)
    subyacente = _es_subyacente(indicador)
    objetivo = float(perfil["objetivo"])

    lectura_comparable = (
        float(resultado["ultimo_valor"])
        if interanual
        else _anualizar_mensual(float(resultado["ultimo_valor"]))
    )

    # Componente principal: brecha frente al objetivo oficial.
    # La tangente hiperbólica evita que un solo dato extremo monopolice el score.
    sensibilidad = 1.6 if interanual else 2.2
    brecha = lectura_comparable - objetivo
    score_nivel = 50.0 + 42.0 * np.tanh(brecha / sensibilidad)

    tendencia = resultado["tendencia_12"]
    score_tendencia = {"Alcista": 72.0, "Lateral": 50.0, "Bajista": 28.0}.get(tendencia, 50.0)

    momentum = resultado["momentum_3"]
    if momentum is None:
        score_momentum = 50.0
    else:
        escala_momentum = 0.35 if interanual else 0.12
        score_momentum = 50.0 + 35.0 * np.tanh(float(momentum) / escala_momentum)

    percentil = resultado["percentil"]
    score_historico = 50.0 if percentil is None else float(percentil)

    zscore = resultado["zscore"]
    score_extremo = 50.0 if zscore is None else 50.0 + 22.0 * np.tanh(float(zscore) / 1.5)

    # El mandato determina cuánto pesa la brecha de inflación.
    peso_precios = float(perfil["peso_precios"])
    if interanual:
        pesos = {
            "nivel": 0.45 + 0.15 * peso_precios,
            "tendencia": 0.18,
            "momentum": 0.12,
            "historico": 0.10,
            "extremo": 0.05,
        }
    else:
        # El dato mensual es más ruidoso: se reduce el peso del nivel anualizado
        # y se aumenta la persistencia (tendencia + momentum).
        pesos = {
            "nivel": 0.30 + 0.12 * peso_precios,
            "tendencia": 0.24,
            "momentum": 0.20,
            "historico": 0.10,
            "extremo": 0.06,
        }

    total_pesos = sum(pesos.values())
    score = (
        score_nivel * pesos["nivel"]
        + score_tendencia * pesos["tendencia"]
        + score_momentum * pesos["momentum"]
        + score_historico * pesos["historico"]
        + score_extremo * pesos["extremo"]
    ) / total_pesos

    # La inflación subyacente suele ser más persistente y, por tanto, más útil
    # para inferir la reacción monetaria. Se amplifica moderadamente su señal.
    if subyacente:
        score = 50.0 + (score - 50.0) * 1.10

    # En EE. UU. el PCE es la referencia oficial; el CPI mantiene gran relevancia,
    # pero su señal se modera ligeramente.
    relevancia = _relevancia_medida(indicador, resultado["divisa"])
    score = 50.0 + (score - 50.0) * relevancia
    score = int(round(_limitar(score)))

    return {
        "score": score,
        "sesgo": clasificar_presion(score),
        "objetivo": objetivo,
        "lectura_comparable": round(lectura_comparable, 2),
        "es_interanual": interanual,
        "banco": perfil["banco"],
        "medida_preferida": perfil["medida_preferida"],
        "peso_precios": peso_precios,
        "componentes": {
            "nivel": round(score_nivel, 1),
            "tendencia": round(score_tendencia, 1),
            "momentum": round(score_momentum, 1),
            "historico": round(score_historico, 1),
            "extremo": round(score_extremo, 1),
        },
    }


def generar_resumen_generico(r):
    p = r["percentil"]
    if p is None:
        posicion = "No hay suficientes datos para situar el indicador históricamente."
    elif p >= 90:
        posicion = "El indicador se encuentra en una zona históricamente muy elevada."
    elif p <= 10:
        posicion = "El indicador se encuentra en una zona históricamente muy baja."
    else:
        posicion = "El indicador se mantiene dentro de su rango histórico habitual."

    tendencia = r["tendencia_12"]
    return f"{posicion} La tendencia de los últimos 12 periodos es {tendencia.lower()}."


def generar_resumen_inflacion(r):
    score = r["macro_score"]
    sesgo = r["macro_rating"]
    objetivo = r["objetivo_bc"]
    comparable = r["lectura_comparable"]
    banco = r["banco_central"]
    interanual = r["es_interanual"]
    tendencia = r["tendencia_12"]

    if interanual:
        referencia = f"La lectura interanual es del {comparable:.2f}%, frente al objetivo del {objetivo:.1f}%."
    else:
        referencia = (
            f"El dato mensual equivale aproximadamente a un ritmo anualizado del {comparable:.2f}%, "
            f"comparado con el objetivo del {objetivo:.1f}%."
        )

    if score >= 66:
        direccion = "En conjunto, aumenta la presión para mantener o endurecer la política monetaria."
    elif score <= 34:
        direccion = "En conjunto, aumenta el margen para flexibilizar la política monetaria."
    else:
        direccion = "En conjunto, la señal para la política monetaria es limitada o equilibrada."

    persistencia = {
        "Alcista": "La tendencia de fondo refuerza la presión inflacionista.",
        "Bajista": "La tendencia de fondo modera la presión inflacionista.",
        "Lateral": "La tendencia de fondo no altera de forma clara la señal.",
    }.get(tendencia, "")

    return (
        f"{referencia} {persistencia} {direccion} "
        f"Presión estimada sobre {banco}: {sesgo} ({score}/100)."
    )


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
        presion = calcular_presion_inflacion(resultado)
        resultado["macro_score"] = presion["score"]
        resultado["macro_rating"] = presion["sesgo"]
        resultado["objetivo_bc"] = presion["objetivo"]
        resultado["lectura_comparable"] = presion["lectura_comparable"]
        resultado["es_interanual"] = presion["es_interanual"]
        resultado["banco_central"] = presion["banco"]
        resultado["medida_preferida"] = presion["medida_preferida"]
        resultado["peso_precios"] = presion["peso_precios"]
        resultado["componentes_score"] = presion["componentes"]
        resultado["summary"] = generar_resumen_inflacion(resultado)
    else:
        resultado["macro_score"] = None
        resultado["macro_rating"] = "Pendiente de motor específico"
        resultado["summary"] = generar_resumen_generico(resultado)

    return resultado
