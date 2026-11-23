"""Diagnóstico aislado de catálogo macro Finnhub para MacroFX.
Ejecutar: streamlit run diagnostico_finnhub.py
No modifica fx_rates.py ni revela la API key.
"""
import os
import requests
import streamlit as st

st.set_page_config(page_title='MacroFX · Diagnóstico Finnhub', layout='wide')
st.title('MacroFX · Diagnóstico de tipos oficiales en Finnhub')
st.caption('Solo consulta el catálogo; no altera datos ni configuración del dashboard.')

def get_token():
    for key in ('FINNHUB_API_KEY', 'FINNHUB_TOKEN', 'FINNHUB_KEY'):
        value = os.getenv(key)
        if value:
            return value.strip()
        try:
            value = st.secrets.get(key)
            if value:
                return str(value).strip()
        except Exception:
            pass
    try:
        for section in ('Finnhub', 'finnhub', 'FINNHUB'):
            config = st.secrets.get(section)
            if config:
                for key in ('FINNHUB_API_KEY', 'api_key', 'token'):
                    value = config.get(key)
                    if value:
                        return str(value).strip()
    except Exception:
        pass
    return None

@st.cache_data(ttl=21600, show_spinner=False)
def catalog():
    token = get_token()
    if not token:
        raise RuntimeError('No se detectó FINNHUB_API_KEY en entorno o Streamlit secrets')
    response = requests.get('https://finnhub.io/api/v1/economic/code',
                            params={'token': token}, timeout=15)
    if response.status_code != 200:
        raise RuntimeError(f'Finnhub HTTP {response.status_code}: verifica permisos del plan y endpoint')
    data = response.json()
    if isinstance(data, dict):
        for key in ('data', 'codes', 'results'):
            if isinstance(data.get(key), list):
                data = data[key]
                break
    if not isinstance(data, list):
        raise RuntimeError(f'Respuesta inesperada: {type(data).__name__}; no se pueden analizar códigos')
    return [x for x in data if isinstance(x, dict)]

if st.button('Consultar catálogo de Finnhub', type='primary'):
    try:
        records = catalog()
        st.success(f'Catálogo recibido: {len(records)} registros')
        if records:
            st.write('Campos disponibles:', ', '.join(map(str, records[0].keys())))
        keywords = ('interest', 'policy', 'cash rate', 'overnight', 'central bank',
                    'official cash', 'bank rate', 'tasa de interes', 'taux directeur')
        countries = {'CHF': ('CH', 'CHE', 'SWITZERLAND', 'CHF', 'SWISS'),
                     'NZD': ('NZ', 'NZL', 'NEW ZEALAND', 'NZD'),
                     'JPY': ('JP', 'JPN', 'JAPAN', 'JPY')}
        for currency, aliases in countries.items():
            matches = []
            for rec in records:
                fields = ' '.join(str(v) for v in rec.values()).lower()
                if any(word in fields for word in keywords) and any(alias.lower() in fields for alias in aliases):
                    matches.append(rec)
            st.subheader(f'{currency} · {len(matches)} posibles coincidencias')
            if matches:
                st.dataframe(matches[:100], use_container_width=True)
            else:
                st.warning('No se encontraron coincidencias automáticas. Puede que los nombres o códigos usen otro formato.')
        st.info('Si hay coincidencias, comparte únicamente sus códigos y nombres. Nunca compartas la API key.')
    except (requests.RequestException, ValueError, RuntimeError) as exc:
        st.error(str(exc))

st.divider()
st.subheader("Verificar históricos de tipos oficiales")

codes = {
    "CHF": "MA-CHE-7382",
    "NZD": "MA-NZL-7382",
    "JPY": "MA-JPN-7382",
}

if st.button("Verificar históricos Finnhub"):
    token = get_token()

    if not token:
        st.error("No se encontró FINNHUB_API_KEY")
    else:
        for currency, code in codes.items():
            st.subheader(f"{currency} — {code}")
            try:
                response = requests.get(
                    "https://finnhub.io/api/v1/economic",
                    params={"code": code, "token": token},
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()

                if isinstance(data, dict):
                    observations = data.get("data", [])
                elif isinstance(data, list):
                    observations = data
                else:
                    observations = []

                st.write("Observaciones:", len(observations))
                st.write("Últimas observaciones:")
                st.dataframe(observations[-10:])

            except Exception as exc:
                st.error(f"{type(exc).__name__}: {exc}")
