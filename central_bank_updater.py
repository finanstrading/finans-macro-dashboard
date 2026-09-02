import os
import json
import time
import random
import hashlib
import requests

from datetime import datetime, timezone
from openai import OpenAI, RateLimitError


# ===================================================
# CONFIGURACIÓN
# ===================================================

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

CENTRAL_BANK_DRIVERS_WEBAPP_URL = os.environ.get(
    "CENTRAL_BANK_DRIVERS_WEBAPP_URL"
)


CONFIGURACION = {

    "USD": {
        "banco": "Federal Reserve",
        "miembros": """
Kevin Warsh, John Williams, Michael Barr, Michelle Bowman,
Lisa Cook, Beth Hammack, Philip Jefferson, Neel Kashkari,
Lorie Logan, Anna Paulson, Jerome Powell, Christopher Waller,
Austan Goolsbee, Susan Collins, Mary Daly, Thomas Barkin,
Alberto Musalem, Jeffrey Schmid
""",
    },

    "EUR": {
        "banco": "European Central Bank / Eurosystem",
        "miembros": """
Christine Lagarde, Boris Vujcic, Philip Lane, Isabel Schnabel,
Piero Cipollone, Luis de Guindos, Joachim Nagel, Olli Rehn,
Martin Kocher, Bostjan Vasle, Primoz Dolenc, Martins Kazaks,
Klaas Knot, Mario Centeno, Francois Villeroy de Galhau,
Fabio Panetta, Gabriel Makhlouf, Pierre Wunsch
""",
    },

    "GBP": {
        "banco": "Bank of England",
        "miembros": """
Andrew Bailey, Sarah Breeden, Swati Dhingra, Megan Greene,
Clare Lombardelli, Catherine Mann, Huw Pill, Dave Ramsden,
Alan Taylor
""",
    },

    "JPY": {
        "banco": "Bank of Japan",
        "miembros": """
Kazuo Ueda, Shinichi Uchida, Ryozo Himino,
Hajime Takata, Naoki Tamura, Junko Koeda,
Kazuyuki Masu, Toichiro Asada, Ayano Sato
""",
    },

    "CHF": {
        "banco": "Swiss National Bank",
        "miembros": """
Martin Schlegel, Antoine Martin, Petra Tschudin
""",
    },

    "AUD": {
        "banco": "Reserve Bank of Australia",
        "miembros": """
Michele Bullock, Andrew Hauser, Marnie Baker,
Renee Fry-McKibbin, Ian Harper, Carolyn Hewson,
Iain Ross, Bruce Preston, Jenny Wilkinson
""",
    },

    "NZD": {
        "banco": "Reserve Bank of New Zealand",
        "miembros": """
Anna Breman, Karen Silk, Paul Conway,
Carl Hansen, Prasanna Gai, Hayley Gourley
""",
    },

    "CAD": {
        "banco": "Bank of Canada",
        "miembros": """
Tiff Macklem, Carolyn Rogers, Toni Gravelle,
Marc-Andre Gosselin, Nicolas Vincent,
Michelle Alexopoulos
""",
    },
}


# ===================================================
# OPENAI WEB SEARCH
# ===================================================

def buscar_bancos_centrales_ia(divisa):

    divisa = str(divisa).strip().upper()

    if divisa not in CONFIGURACION:
        raise ValueError(
            f"Divisa no soportada: {divisa}"
        )

    if not OPENAI_API_KEY:
        raise ValueError(
            "Falta OPENAI_API_KEY."
        )

    client = OpenAI(
        api_key=OPENAI_API_KEY
    )

    datos = CONFIGURACION[divisa]

    prompt = f"""
Search the web for RECENT statements, interviews, speeches,
media appearances or direct comments made during approximately
the last 48 hours by members of the {datos["banco"]}.

Currency: {divisa}

Relevant people include:
{datos["miembros"]}

The objective is NOT to provide general news about the central bank.

I specifically want statements or comments actually made by
central-bank officials that could matter for monetary policy
or the {divisa} currency.

Search broadly across:
- official central-bank websites
- Reuters
- Bloomberg when publicly indexed
- CNBC
- financial press
- interviews
- speeches
- conference appearances
- reputable financial news websites

Do NOT include:
- analyst forecasts
- market expectations without a direct central-bank statement
- articles that merely mention the central bank
- generic market commentary

For each relevant event provide:

EVENT DATE:
DATE/TIME:
MEMBER:
CENTRAL BANK:
STATEMENT:
CONTEXT:
MONETARY BIAS: Hawkish / Dovish / Neutral
IMPORTANCE: High / Medium / Low
SOURCE:
SOURCE URL:

IMPORTANT OUTPUT RULES:

- SOURCE must contain only the publisher or original source name.
  Example: Reuters, CNBC, Federal Reserve.

- SOURCE URL must contain ONLY one raw absolute URL beginning with https://
  Do not use Markdown links.
  Do not use brackets.
  Do not add citations or source names inside SOURCE URL.

- DATE/TIME must be ISO 8601 UTC when the exact time is known.
  Example: 2026-08-28T16:00:00Z

- If the exact time cannot be reliably established, return null for datetime.
  Do not invent a time.

- EVENT DATE must contain the confirmed calendar date of the statement
  in YYYY-MM-DD format.
  Example: 2026-08-27

- If the calendar date cannot be reliably established, return null.

- If the exact time is unknown but the date is known:
  EVENT DATE must still contain the date,
  while DATE/TIME must be null.

- Do not invent a time.

If several articles report the same comments, consolidate them
into one event.

Prioritize completeness over speed.

If there are no relevant comments, return an empty events array.
"""

    response = client.responses.create(
        model="gpt-5.6-luna",
        tools=[
            {
                "type": "web_search",
                "search_context_size": "high",
            }
        ],
        input=prompt,
        text={
            "format": {
                "type": "json_schema",
                "name": "central_bank_drivers",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "events": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "event_date": {
                                        "type": [
                                            "string",
                                            "null",
                                        ]
                                    },
                                    "datetime": {
                                        "type": [
                                            "string",
                                            "null",
                                        ]
                                    },
                                    "currency": {
                                        "type": "string"
                                    },
                                    "member": {
                                        "type": "string"
                                    },
                                    "central_bank": {
                                        "type": "string"
                                    },
                                    "statement": {
                                        "type": "string"
                                    },
                                    "context": {
                                        "type": "string"
                                    },
                                    "bias": {
                                        "type": "string",
                                        "enum": [
                                            "Hawkish",
                                            "Dovish",
                                            "Neutral",
                                        ],
                                    },
                                    "importance": {
                                        "type": "string",
                                        "enum": [
                                            "High",
                                            "Medium",
                                            "Low",
                                        ],
                                    },
                                    "source": {
                                        "type": "string"
                                    },
                                    "source_url": {
                                        "type": "string"
                                    },
                                },
                                "required": [
                                    "event_date",
                                    "datetime",
                                    "currency",
                                    "member",
                                    "central_bank",
                                    "statement",
                                    "context",
                                    "bias",
                                    "importance",
                                    "source",
                                    "source_url",
                                ],
                                "additionalProperties": False,
                            },
                        }
                    },
                    "required": [
                        "events"
                    ],
                    "additionalProperties": False,
                },
            }
        },
    )

    return response.output_text


# ===================================================
# PREPARAR EVENTOS
# ===================================================

def preparar_central_bank_drivers(resultado_ia):

    if not resultado_ia:
        return []

    try:
        data = json.loads(resultado_ia)

    except Exception as error:
        print("DEBUG JSON INVALIDO:")
        print(repr(resultado_ia))

        raise ValueError(
            f"No se pudo interpretar la respuesta de OpenAI como JSON: {error}"
        )
    eventos = data.get(
        "events",
        []
    )

    if not isinstance(eventos, list):
        return []

    detected_at = datetime.now(
        timezone.utc
    ).isoformat()

    filas = []

    for evento in eventos:

        currency = str(
            evento.get("currency")
            or ""
        ).strip().upper()

        member = str(
            evento.get("member")
            or ""
        ).strip()

        statement = str(
            evento.get("statement")
            or ""
        ).strip()

        if (
            not currency
            or not member
            or not statement
        ):
            continue

        texto_id = (
            f"{currency}|"
            f"{member.lower()}|"
            f"{statement.lower()}"
        )

        event_id = hashlib.sha256(
            texto_id.encode("utf-8")
        ).hexdigest()[:24]

        filas.append({
            "EventID": event_id,
            "DateTime": evento.get(
                "datetime"
            ),
            "Currency": currency,
            "Member": member,
            "CentralBank": str(
                evento.get("central_bank")
                or ""
            ).strip(),
            "Statement": statement,
            "Context": str(
                evento.get("context")
                or ""
            ).strip(),
            "Bias": str(
                evento.get("bias")
                or ""
            ).strip(),
            "Importance": str(
                evento.get("importance")
                or ""
            ).strip(),
            "Source": str(
                evento.get("source")
                or ""
            ).strip(),
            "SourceURL": str(
                evento.get("source_url")
                or ""
            ).strip(),
            "DetectedAt": detected_at,
            "EventDate": evento.get(
                "event_date"
            ),
        })

    return filas


# ===================================================
# GUARDAR EN GOOGLE SHEETS
# ===================================================

def guardar_central_bank_drivers(filas):

    if not filas:
        return {
            "ok": True,
            "received": 0,
            "inserted": 0,
            "duplicates": 0,
        }

    if not CENTRAL_BANK_DRIVERS_WEBAPP_URL:
        raise ValueError(
            "Falta CENTRAL_BANK_DRIVERS_WEBAPP_URL."
        )

    payload = {
        "action": "save_central_bank_drivers",
        "events": filas,
    }

    response = requests.post(
        CENTRAL_BANK_DRIVERS_WEBAPP_URL,
        json=payload,
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("ok"):
        raise ValueError(
            "Apps Script devolvió error: "
            + str(data.get("error"))
        )

    return data


# ===================================================
# ACTUALIZAR UNA DIVISA
# ===================================================

def actualizar_central_bank_currency(currency):

    currency = str(
        currency
    ).strip().upper()

    resultado_ia = buscar_bancos_centrales_ia(
        currency
    )

    eventos = preparar_central_bank_drivers(
        resultado_ia
    )

    resultado_guardado = guardar_central_bank_drivers(
        eventos
    )

    return {
        "currency": currency,
        "events_found": len(eventos),
        "save_result": resultado_guardado,
    }


# ===================================================
# ACTUALIZAR LAS 8 DIVISAS
# ===================================================

def actualizar_todos_central_bank_drivers():

    divisas = [
        "USD",
        "EUR",
        "GBP",
        "JPY",
        "CHF",
        "AUD",
        "NZD",
        "CAD",
    ]

    resultados = []

    for indice, currency in enumerate(
        divisas
    ):

        if indice > 0:
            time.sleep(15)

        max_intentos = 2

        for intento in range(
            max_intentos
        ):

            try:

                print(
                    f"[{currency}] Iniciando búsqueda..."
                )

                resultado = actualizar_central_bank_currency(
                    currency
                )

                resultados.append({
                    "currency": currency,
                    "ok": True,
                    "events_found": resultado[
                        "events_found"
                    ],
                    "save_result": resultado[
                        "save_result"
                    ],
                    "error": None,
                })

                save_result = (
                    resultado[
                        "save_result"
                    ]
                    or {}
                )

                print(
                    f"[{currency}] OK · "
                    f"{resultado['events_found']} encontrados · "
                    f"{save_result.get('inserted', 0)} nuevos · "
                    f"{save_result.get('duplicates', 0)} duplicados"
                )

                break

            except RateLimitError as error:

                if intento < max_intentos - 1:

                    espera = (
                        20
                        + random.uniform(
                            0,
                            5,
                        )
                    )

                    print(
                        f"[{currency}] Rate limit · "
                        f"reintento en {espera:.1f}s"
                    )

                    time.sleep(
                        espera
                    )

                    continue

                resultados.append({
                    "currency": currency,
                    "ok": False,
                    "events_found": 0,
                    "save_result": None,
                    "error": (
                        f"Rate limit: "
                        f"{str(error)}"
                    ),
                })

                print(
                    f"[{currency}] ERROR · Rate limit"
                )

                break

            except Exception as error:

                resultados.append({
                    "currency": currency,
                    "ok": False,
                    "events_found": 0,
                    "save_result": None,
                    "error": str(error),
                })

                print(
                    f"[{currency}] ERROR · "
                    f"{str(error)}"
                )

                break

    return resultados


# ===================================================
# EJECUCIÓN DIRECTA
# ===================================================

if __name__ == "__main__":

    print(
        "=== CENTRAL BANK DRIVERS UPDATE ==="
    )

    resultados = actualizar_todos_central_bank_drivers()

    errores = [
        resultado
        for resultado in resultados
        if not resultado["ok"]
    ]

    print()
    print(
        "=== RESUMEN ==="
    )

    for resultado in resultados:

        if resultado["ok"]:

            save_result = (
                resultado["save_result"]
                or {}
            )

            print(
                f"{resultado['currency']} · OK · "
                f"{resultado['events_found']} encontrados · "
                f"{save_result.get('inserted', 0)} nuevos · "
                f"{save_result.get('duplicates', 0)} duplicados"
            )

        else:

            print(
                f"{resultado['currency']} · ERROR · "
                f"{resultado['error']}"
            )

    if errores:
        raise SystemExit(1)
