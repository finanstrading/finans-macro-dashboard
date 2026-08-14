def motor_inflacion(serie, resultado, indicador, objetivo):
    ultimo = resultado["ultimo_valor"]
    anterior = resultado.get("valor_anterior")
    frecuencia = detectar_frecuencia(indicador)

    if frecuencia == "mensual":
        # Aproximación anualizada compuesta para evitar comparar directamente
        # un dato mensual con un objetivo anual.
        ritmo_equivalente = ((1.0 + ultimo / 100.0) ** 12 - 1.0) * 100.0
        desviacion = ritmo_equivalente - objetivo
        score_mandato = 50.0 + 32.0 * np.tanh(desviacion / 1.5)

        referencia_persistencia = (
            (1.0 + objetivo / 100.0) ** (1.0 / 12.0) - 1.0
        ) * 100.0

        etiqueta_nivel = (
            f"ritmo mensual anualizado aproximado de "
            f"{ritmo_equivalente:.1f}%"
        )

    else:
        desviacion = ultimo - objetivo
        score_mandato = 50.0 + 32.0 * np.tanh(desviacion / 1.5)
        referencia_persistencia = objetivo

        etiqueta_nivel = (
            f"{ultimo:.2f}% frente a un objetivo de "
            f"{objetivo:.1f}%"
        )

    # ==========================================================
    # MOMENTUM DE INFLACIÓN CON COHERENCIA DIRECCIONAL
    #
    # El momentum conserva información sobre aceleración /
    # desaceleración, pero no puede invertir la dirección
    # económica del último dato.
    #
    # Inflación baja  -> momentum <= neutral (50)
    # Inflación sube  -> momentum >= neutral (50)
    # Sin cambio      -> se conserva el cálculo original
    # ==========================================================

    score_impulso = score_momentum(resultado)

    if anterior is not None:

        if ultimo < anterior:
            # Desinflación: puede ser más o menos intensa,
            # pero no puede convertirse en señal hawkish.
            score_impulso = min(score_impulso, 50.0)

        elif ultimo > anterior:
            # Aceleración de inflación: puede ser más o menos
            # intensa, pero no puede convertirse en señal dovish.
            score_impulso = max(score_impulso, 50.0)

    componentes = {
        "Mandato de estabilidad de precios": _limitar(score_mandato),
        "Tendencia": score_tendencia(resultado),
        "Impulso reciente": _limitar(score_impulso),
        "Persistencia": score_persistencia(
            serie,
            referencia_persistencia,
            inverso=False,
            ventana=6,
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
