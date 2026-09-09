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


COMMITTEE_CONFIG = {
    "USD": {
        "banco": "Federal Reserve",
        "comite": "FOMC",
        "fallback_voters": [
            "Kevin Warsh",
            "John Williams",
            "Michael Barr",
            "Michelle Bowman",
            "Lisa Cook",
            "Beth Hammack",
            "Philip Jefferson",
            "Neel Kashkari",
            "Lorie Logan",
            "Anna Paulson",
            "Jerome Powell",
            "Christopher Waller",
        ],
    },
    "EUR": {
        "banco": "European Central Bank / Eurosystem",
        "comite": "Governing Council",
        "fallback_voters": [
            "Christine Lagarde",
            "Boris Vujcic",
            "Piero Cipollone",
            "Frank Elderson",
            "Philip Lane",
            "Isabel Schnabel",
            "Emmanuel Moulin",
            "Fabio Panetta",
            "Olaf Sleijpen",
            "Joachim Nagel",
            "Pierre Wunsch",
            "Dimitar Radev",
            "Ülo Kaasik",
            "Gabriel Makhlouf",
            "Gaston Reinesch",
            "Alexander Demarco",
            "Martin Kocher",
            "Álvaro Santos Pereira",
            "Primož Dolenc",
            "Peter Kažimír",
            "Olli Rehn",
        ],
    },
    "GBP": {
        "banco": "Bank of England",
        "comite": "MPC",
        "fallback_voters": [
            "Andrew Bailey",
            "Sarah Breeden",
            "Swati Dhingra",
            "Megan Greene",
            "Clare Lombardelli",
            "Catherine Mann",
            "Huw Pill",
            "Dave Ramsden",
            "Alan Taylor",
        ],
    },
    "JPY": {
        "banco": "Bank of Japan",
        "comite": "Policy Board",
        "fallback_voters": [
            "Kazuo Ueda",
            "Shinichi Uchida",
            "Ryozo Himino",
            "Hajime Takata",
            "Naoki Tamura",
            "Junko Koeda",
            "Kazuyuki Masu",
            "Toichiro Asada",
            "Ayano Sato",
        ],
    },
    "CHF": {
        "banco": "Swiss National Bank",
        "comite": "Governing Board",
        "fallback_voters": [
            "Martin Schlegel",
            "Antoine Martin",
            "Petra Tschudin",
        ],
    },
    "AUD": {
        "banco": "Reserve Bank of Australia",
        "comite": "Monetary Policy Board",
        "fallback_voters": [
            "Michele Bullock",
            "Andrew Hauser",
            "Marnie Baker",
            "Melinda Cilento",
            "Renee Fry-McKibbin",
            "Carolyn Hewson",
            "Bruce Preston",
            "Iain Ross",
            "Jenny Wilkinson",
        ],
    },
    "NZD": {
        "banco": "Reserve Bank of New Zealand",
        "comite": "MPC",
        "fallback_voters": [
            "Anna Breman",
            "Karen Silk",
            "Paul Conway",
            "Carl Hansen",
            "Prasanna Gai",
            "Hayley Gourley",
        ],
    },
    "CAD": {
        "banco": "Bank of Canada",
        "comite": "Governing Council",
        "fallback_voters": [
            "Tiff Macklem",
            "Carolyn Rogers",
            "Toni Gravelle",
            "Marc-Andre Gosselin",
            "Nicolas Vincent",
            "Michelle Alexopoulos",
        ],
    },
}


VALID_BIASES = [
    "Hawkish",
    "Lean Hawkish",
    "Neutral",
    "Lean Dovish",
    "Dovish",
]

BIAS_SCORE = {
    "Dovish": -2,
    "Lean Dovish": -1,
    "Neutral": 0,
    "Lean Hawkish": 1,
    "Hawkish": 2,
}


# ===================================================
# WEB APP — ESTADO PREVIO
# ===================================================

def _webapp_post(payload, timeout=30):
    if not CENTRAL_BANK_DRIVERS_WEBAPP_URL:
        raise ValueError(
            "Falta CENTRAL_BANK_DRIVERS_WEBAPP_URL."
        )

    response = requests.post(
        CENTRAL_BANK_DRIVERS_WEBAPP_URL,
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()

    try:
        data = response.json()
    except Exception:
        raise ValueError(
            "Apps Script no devolvió JSON válido: "
            + response.text[:500]
        )

    if not data.get("ok"):
        raise ValueError(
            "Apps Script devolvió error: "
            + str(data.get("error"))
        )

    return data


def cargar_estado_previo_miembros(currency):
    """
    Lee CentralBank_Members a través del mismo Web App.
    Si todavía no existe la hoja/acción, devuelve vacío para permitir
    la primera ejecución.
    """
    try:
        data = _webapp_post(
            {
                "action": "get_central_bank_members",
                "currency": currency,
            },
            timeout=30,
        )
        members = data.get("members", [])
        if isinstance(members, list):
            return members
    except Exception as error:
        print(
            f"[{currency}] Aviso: no se pudo cargar estado previo "
            f"de miembros: {error}"
        )

    return []


# ===================================================
# OPENAI — DECLARACIONES + COMITÉ EN UNA SOLA BÚSQUEDA
# ===================================================

def buscar_bancos_centrales_ia(divisa, previous_members):

    divisa = str(divisa).strip().upper()

    if divisa not in COMMITTEE_CONFIG:
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

    datos = COMMITTEE_CONFIG[divisa]

    prev_json = json.dumps(
        previous_members,
        ensure_ascii=False,
        indent=2,
    )

    fallback = "\n".join(
        f"- {name}"
        for name in datos["fallback_voters"]
    )

    prompt = f"""
You maintain two connected datasets for an institutional FX dashboard:

A) recent central-bank statements
B) the CURRENT rate-setting voting committee and each voter's structural policy bias

CENTRAL BANK: {datos["banco"]}
COMMITTEE: {datos["comite"]}
CURRENCY: {divisa}

===================================================
PART A — RECENT STATEMENTS
===================================================

Search the web for RECENT statements, interviews, speeches,
testimony, minutes-related comments or direct remarks made during
approximately the last 48 hours by relevant officials of this central bank.

Only include comments that matter for monetary policy or FX.

Do NOT include:
- analyst forecasts
- market expectations without a direct central-bank statement
- generic articles merely mentioning the bank

For each event return:
event_date, datetime, currency, member, central_bank, statement,
context, bias (Hawkish/Dovish/Neutral), importance, source, source_url.

===================================================
PART B — CURRENT VOTERS
===================================================

First verify who CURRENTLY HAS A VOTE on the interest-rate decision
for the NEXT scheduled policy meeting.

Use OFFICIAL central-bank sources as the primary authority.

Rules:
- Exclude observers, alternates and non-voting participants.
- Federal Reserve: only current FOMC voters.
- ECB: apply the official rotation of NCB governors for the NEXT
  monetary-policy decision; Executive Board members retain voting rights.
- Other banks: include only formal members who vote on policy.
- If there has been an appointment, departure, replacement, expiry
  or rotation, use the new CURRENT voting list.

Fallback voter list from the dashboard; correct it if official sources
show a change:
{fallback}

Previous saved state from CentralBank_Members:
{prev_json}

For EVERY current voter return:

proposed_bias:
Hawkish / Lean Hawkish / Neutral / Lean Dovish / Dovish

latest_signal:
Hawkish / Lean Hawkish / Neutral / Lean Dovish / Dovish

expected_vote:
Hike / Hold / Cut / Hike or Hold / Hold or Cut / Unclear

confidence:
High / Medium / Low

evidence_type:
Official vote / Explicit stance change / Multiple consistent statements /
Single statement / No new evidence

reason:
Spanish, factual, max 28 words.

evidence_date:
YYYY-MM-DD or null

source:
publisher/source name only

source_url:
one raw https URL or empty string

IMPORTANT STRUCTURAL-BIAS RULE:
Structural bias is persistent. Do NOT move a member merely because one
isolated sentence sounds different.

A structural-bias change should be supported by:
- an official vote clearly inconsistent with the previous stance, OR
- an explicit stance change, OR
- multiple consistent recent statements indicating a durable shift.

A single statement can change latest_signal without changing structural bias.

Also return:
membership_as_of
next_meeting_date
membership_source
membership_source_url
summary (Spanish, max 35 words)

Prioritize completeness over speed.
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
                "name": "central_bank_update",
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
                                        "type": ["string", "null"]
                                    },
                                    "datetime": {
                                        "type": ["string", "null"]
                                    },
                                    "currency": {"type": "string"},
                                    "member": {"type": "string"},
                                    "central_bank": {"type": "string"},
                                    "statement": {"type": "string"},
                                    "context": {"type": "string"},
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
                                    "source": {"type": "string"},
                                    "source_url": {"type": "string"},
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
                        },
                        "committee": {
                            "type": "object",
                            "properties": {
                                "membership_as_of": {
                                    "type": ["string", "null"]
                                },
                                "next_meeting_date": {
                                    "type": ["string", "null"]
                                },
                                "membership_source": {
                                    "type": "string"
                                },
                                "membership_source_url": {
                                    "type": "string"
                                },
                                "summary": {
                                    "type": "string"
                                },
                                "members": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {
                                                "type": "string"
                                            },
                                            "proposed_bias": {
                                                "type": "string",
                                                "enum": VALID_BIASES,
                                            },
                                            "latest_signal": {
                                                "type": "string",
                                                "enum": VALID_BIASES,
                                            },
                                            "expected_vote": {
                                                "type": "string",
                                                "enum": [
                                                    "Hike",
                                                    "Hold",
                                                    "Cut",
                                                    "Hike or Hold",
                                                    "Hold or Cut",
                                                    "Unclear",
                                                ],
                                            },
                                            "confidence": {
                                                "type": "string",
                                                "enum": [
                                                    "High",
                                                    "Medium",
                                                    "Low",
                                                ],
                                            },
                                            "evidence_type": {
                                                "type": "string",
                                                "enum": [
                                                    "Official vote",
                                                    "Explicit stance change",
                                                    "Multiple consistent statements",
                                                    "Single statement",
                                                    "No new evidence",
                                                ],
                                            },
                                            "reason": {
                                                "type": "string"
                                            },
                                            "evidence_date": {
                                                "type": ["string", "null"]
                                            },
                                            "source": {
                                                "type": "string"
                                            },
                                            "source_url": {
                                                "type": "string"
                                            },
                                        },
                                        "required": [
                                            "name",
                                            "proposed_bias",
                                            "latest_signal",
                                            "expected_vote",
                                            "confidence",
                                            "evidence_type",
                                            "reason",
                                            "evidence_date",
                                            "source",
                                            "source_url",
                                        ],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": [
                                "membership_as_of",
                                "next_meeting_date",
                                "membership_source",
                                "membership_source_url",
                                "summary",
                                "members",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "required": [
                        "events",
                        "committee",
                    ],
                    "additionalProperties": False,
                },
            }
        },
    )

    return response.output_text


# ===================================================
# PREPARAR DECLARACIONES
# ===================================================

def preparar_central_bank_drivers(data):

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
# PREPARAR MAPA DEL COMITÉ
# ===================================================

def _normalizar_nombre(nombre):
    return " ".join(
        str(nombre or "")
        .strip()
        .lower()
        .split()
    )


def _indice_previos(previous_members):
    salida = {}

    for item in previous_members:
        name = str(
            item.get("Member")
            or item.get("name")
            or ""
        ).strip()

        if not name:
            continue

        salida[
            _normalizar_nombre(name)
        ] = item

    return salida


def _resolver_bias(
    previous_bias,
    proposed_bias,
    confidence,
    evidence_type,
):
    """
    Regla conservadora:
    - Primera observación: acepta proposed_bias.
    - Sin cambio propuesto: conserva.
    - Cambio estructural: solo con High + evidencia fuerte.
    """
    previous_bias = str(
        previous_bias or ""
    ).strip()

    proposed_bias = str(
        proposed_bias or "Neutral"
    ).strip()

    if proposed_bias not in VALID_BIASES:
        proposed_bias = "Neutral"

    if previous_bias not in VALID_BIASES:
        return proposed_bias

    if proposed_bias == previous_bias:
        return previous_bias

    evidencia_fuerte = evidence_type in {
        "Official vote",
        "Explicit stance change",
        "Multiple consistent statements",
    }

    if (
        confidence == "High"
        and evidencia_fuerte
    ):
        return proposed_bias

    return previous_bias


def _bias_change(previous_bias, new_bias):
    if (
        previous_bias not in BIAS_SCORE
        or new_bias not in BIAS_SCORE
    ):
        return "Initial"

    delta = (
        BIAS_SCORE[new_bias]
        - BIAS_SCORE[previous_bias]
    )

    if delta > 0:
        return "More Hawkish"

    if delta < 0:
        return "More Dovish"

    return "No Change"


def preparar_central_bank_members(
    currency,
    data,
    previous_members,
):
    committee = data.get(
        "committee",
        {},
    )

    ai_members = committee.get(
        "members",
        [],
    )

    if not isinstance(ai_members, list):
        ai_members = []

    previous_index = _indice_previos(
        previous_members
    )

    updated_at = datetime.now(
        timezone.utc
    ).isoformat()

    current_rows = []
    current_keys = set()
    changes = []

    for item in ai_members:

        name = str(
            item.get("name")
            or ""
        ).strip()

        if not name:
            continue

        key = _normalizar_nombre(
            name
        )

        if key in current_keys:
            continue

        current_keys.add(key)

        previous = previous_index.get(
            key,
            {},
        )

        previous_bias = str(
            previous.get("StructuralBias")
            or previous.get("structural_bias")
            or ""
        ).strip()

        proposed_bias = str(
            item.get("proposed_bias")
            or "Neutral"
        ).strip()

        confidence = str(
            item.get("confidence")
            or "Low"
        ).strip()

        evidence_type = str(
            item.get("evidence_type")
            or "No new evidence"
        ).strip()

        structural_bias = _resolver_bias(
            previous_bias,
            proposed_bias,
            confidence,
            evidence_type,
        )

        bias_change = _bias_change(
            previous_bias,
            structural_bias,
        )

        row = {
            "Currency": currency,
            "Member": name,
            "Voting": True,
            "StructuralBias": structural_bias,
            "PreviousBias": (
                previous_bias
                if previous_bias in VALID_BIASES
                else ""
            ),
            "BiasChange": bias_change,
            "LatestSignal": str(
                item.get("latest_signal")
                or structural_bias
            ).strip(),
            "ExpectedVote": str(
                item.get("expected_vote")
                or "Unclear"
            ).strip(),
            "Confidence": confidence,
            "EvidenceType": evidence_type,
            "Evidence": str(
                item.get("reason")
                or ""
            ).strip(),
            "EvidenceDate": item.get(
                "evidence_date"
            ),
            "Source": str(
                item.get("source")
                or ""
            ).strip(),
            "SourceURL": str(
                item.get("source_url")
                or ""
            ).strip(),
            "UpdatedAt": updated_at,
            "MembershipAsOf": committee.get(
                "membership_as_of"
            ),
            "NextMeetingDate": committee.get(
                "next_meeting_date"
            ),
            "MembershipSource": str(
                committee.get(
                    "membership_source"
                )
                or ""
            ).strip(),
            "MembershipSourceURL": str(
                committee.get(
                    "membership_source_url"
                )
                or ""
            ).strip(),
            "CommitteeSummary": str(
                committee.get(
                    "summary"
                )
                or ""
            ).strip(),
        }

        current_rows.append(
            row
        )

        if (
            bias_change
            in {
                "More Hawkish",
                "More Dovish",
            }
        ):
            changes.append({
                "Currency": currency,
                "Member": name,
                "ChangeType": "Bias",
                "PreviousValue": previous_bias,
                "NewValue": structural_bias,
                "DetectedAt": updated_at,
                "Evidence": row["Evidence"],
                "Source": row["Source"],
                "SourceURL": row["SourceURL"],
            })

        if key not in previous_index:
            changes.append({
                "Currency": currency,
                "Member": name,
                "ChangeType": "VotingMemberAdded",
                "PreviousValue": "",
                "NewValue": "Voting",
                "DetectedAt": updated_at,
                "Evidence": (
                    "Nuevo miembro con derecho de voto "
                    "detectado en la composición actual."
                ),
                "Source": row["MembershipSource"],
                "SourceURL": row[
                    "MembershipSourceURL"
                ],
            })

    # Miembros que estaban guardados y ya no aparecen entre los votantes
    for key, previous in previous_index.items():
        if key in current_keys:
            continue

        old_name = str(
            previous.get("Member")
            or previous.get("name")
            or ""
        ).strip()

        changes.append({
            "Currency": currency,
            "Member": old_name,
            "ChangeType": "VotingMemberRemoved",
            "PreviousValue": "Voting",
            "NewValue": "Not Voting",
            "DetectedAt": updated_at,
            "Evidence": (
                "Ya no aparece entre los votantes "
                "actuales verificados."
            ),
            "Source": str(
                committee.get(
                    "membership_source"
                )
                or ""
            ).strip(),
            "SourceURL": str(
                committee.get(
                    "membership_source_url"
                )
                or ""
            ).strip(),
        })

    return current_rows, changes


# ===================================================
# GUARDAR
# ===================================================

def guardar_central_bank_drivers(filas):

    if not filas:
        return {
            "ok": True,
            "received": 0,
            "inserted": 0,
            "duplicates": 0,
        }

    return _webapp_post({
        "action": "save_central_bank_drivers",
        "events": filas,
    })


def guardar_central_bank_members(
    currency,
    members,
    changes,
):
    return _webapp_post({
        "action": "save_central_bank_members",
        "currency": currency,
        "members": members,
        "changes": changes,
    })


# ===================================================
# ACTUALIZAR UNA DIVISA
# ===================================================

def actualizar_central_bank_currency(currency):

    currency = str(
        currency
    ).strip().upper()

    previous_members = (
        cargar_estado_previo_miembros(
            currency
        )
    )

    resultado_texto = (
        buscar_bancos_centrales_ia(
            currency,
            previous_members,
        )
    )

    try:
        data = json.loads(
            resultado_texto
        )
    except Exception as error:
        print("DEBUG JSON INVALIDO:")
        print(repr(resultado_texto))
        raise ValueError(
            "No se pudo interpretar "
            f"la respuesta de OpenAI: {error}"
        )

    eventos = (
        preparar_central_bank_drivers(
            data
        )
    )

    members, changes = (
        preparar_central_bank_members(
            currency,
            data,
            previous_members,
        )
    )

    resultado_drivers = (
        guardar_central_bank_drivers(
            eventos
        )
    )

    resultado_members = (
        guardar_central_bank_members(
            currency,
            members,
            changes,
        )
    )

    return {
        "currency": currency,
        "events_found": len(eventos),
        "members_found": len(members),
        "changes_found": len(changes),
        "drivers_save_result": (
            resultado_drivers
        ),
        "members_save_result": (
            resultado_members
        ),
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
                    f"[{currency}] Iniciando búsqueda "
                    "de declaraciones + comité..."
                )

                resultado = (
                    actualizar_central_bank_currency(
                        currency
                    )
                )

                resultados.append({
                    "currency": currency,
                    "ok": True,
                    **resultado,
                    "error": None,
                })

                print(
                    f"[{currency}] OK · "
                    f"{resultado['events_found']} declaraciones · "
                    f"{resultado['members_found']} votantes · "
                    f"{resultado['changes_found']} cambios"
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
                    "error": (
                        "Rate limit: "
                        + str(error)
                    ),
                })

                break

            except Exception as error:

                resultados.append({
                    "currency": currency,
                    "ok": False,
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
        "=== CENTRAL BANK DRIVERS + MEMBERS UPDATE ==="
    )

    resultados = (
        actualizar_todos_central_bank_drivers()
    )

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
            print(
                f"{resultado['currency']} · OK · "
                f"{resultado['events_found']} declaraciones · "
                f"{resultado['members_found']} votantes · "
                f"{resultado['changes_found']} cambios"
            )

        else:
            print(
                f"{resultado['currency']} · ERROR · "
                f"{resultado['error']}"
            )

    if errores:
        raise SystemExit(1)
