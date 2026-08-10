    from difflib import SequenceMatcher

    nombres_disponibles = sorted(
        df_releases["Indicator"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )

    sugerencias_matching = []

    for indicador_faltante in sin_eodhd["Indicador"]:

        indicador_lower = (
            str(indicador_faltante)
            .strip()
            .lower()
        )

        candidatos = []

        for nombre_eodhd in nombres_disponibles:

            nombre_lower = (
                str(nombre_eodhd)
                .strip()
                .lower()
            )

            similitud = SequenceMatcher(
                None,
                indicador_lower,
                nombre_lower,
            ).ratio()

            candidatos.append(
                (
                    similitud,
                    nombre_eodhd,
                )
            )

        candidatos = sorted(
            candidatos,
            reverse=True,
        )[:5]

        sugerencias_matching.append({
            "Indicador Dashboard": indicador_faltante,
            "Candidato 1": candidatos[0][1] if len(candidatos) > 0 else "",
            "Candidato 2": candidatos[1][1] if len(candidatos) > 1 else "",
            "Candidato 3": candidatos[2][1] if len(candidatos) > 2 else "",
            "Candidato 4": candidatos[3][1] if len(candidatos) > 3 else "",
            "Candidato 5": candidatos[4][1] if len(candidatos) > 4 else "",
        })

    st.dataframe(
        pd.DataFrame(
            sugerencias_matching
        ),
        use_container_width=True,
        hide_index=True,
    )
