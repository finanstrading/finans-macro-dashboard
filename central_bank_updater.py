import os
import json
import time
import random
import hashlib
import requests
import re
import unicodedata

from datetime import datetime, timezone
from openai import OpenAI, RateLimitError


# ===================================================
# CONFIGURACIÓN
# ===================================================

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

CENTRAL_BANK_DRIVERS_WEBAPP_URL = os.environ.get(
    "CENTRAL_BANK_DRIVERS_WEBAPP_URL"
)

# One-time baseline recalibration. Set this GitHub environment variable to
# "true" for ONE run only, then remove/disable it.
RECALIBRATE_BIAS = os.environ.get(
    "CENTRAL_BANK_RECALIBRATE_BIAS",
    "false",
).strip().lower() in {"1", "true", "yes", "on"}

# Automatic structural-bias evolution. A member is allowed to move one step
# when fresh evidence consistently points in the same direction.
AUTO_BIAS_EVOLUTION = True
MAX_AUTO_BIAS_STEP = 1

# V13.2 stability guards. Roster membership is authoritative and independent
# from the AI research result; AI may enrich members, but cannot invent/remove
# voters. Structural bias also gets one-run hysteresis against immediate reversal.
OFFICIAL_ROSTER_GUARD = True
BIAS_HYSTERESIS = True

# V14: OpenAI extracts structured monetary-policy evidence; Python owns the
# structural classification. Scores are intentionally conservative and relative
# to the committee so "supports the bank's current path" is not automatically hawkish.
V14_EVIDENCE_SCORING = True

# V14.2:
# - StructuralScore is 100% evidence-derived and independent from stored bias.
# - Stored StructuralBias only affects persistence/hysteresis AFTER scoring.
# - Committee-relative normalization remains modest.
# - DRY RUN stays ON by default until validation is complete.
V14_RELATIVE_WEIGHT = 0.25
V14_DRY_RUN = os.environ.get(
    "CENTRAL_BANK_V14_DRY_RUN",
    "true",
).strip().lower() in {"1", "true", "yes", "on"}

V14_REQUIRE_CONFIRMATION_FOR_EXTREMES = True

# V14.3: component-level evidence audit.
# OpenAI proposes V/P/R scores, but Python accepts them only when the
# corresponding evidence payload satisfies deterministic validation rules.
V14_COMPONENT_EVIDENCE_AUDIT = True

# V14.3.1: absence of differentiated evidence is not evidence of Neutrality.
V14_EVIDENCE_SUFFICIENCY = True
V14_MIN_ABS_SCORE_FOR_DIRECTIONAL_EVIDENCE = 0.05

# V14.3.2: an existing structural lean cannot decay to Neutral merely because
# the latest EvidenceScore falls inside the Neutral band. Neutralization itself
# must be affirmatively evidenced.
V14_NEUTRALIZATION_GUARD = True
V14_MIN_OPPOSING_SCORE_FOR_NEUTRALIZATION = 0.05


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


# Official committee-roster sources. The exact roster used by the updater is the
# `fallback_voters` list above (plus deterministic ECB rotation below). This
# prevents a web-search hallucination or a retired member from entering Sheets.
OFFICIAL_ROSTER_SOURCES = {
    "USD": ("Federal Reserve — FOMC", "https://www.federalreserve.gov/monetarypolicy/fomc.htm"),
    "GBP": ("Bank of England — Monetary Policy Committee", "https://www.bankofengland.co.uk/about/people/monetary-policy-committee"),
    "JPY": ("Bank of Japan — Policy Board", "https://www.boj.or.jp/en/about/organization/policyboard/index.htm"),
    "CHF": ("Swiss National Bank — Governing Board", "https://www.snb.ch/en/the-snb/organisation/supervisory-management-bodies/board"),
    "AUD": ("Reserve Bank of Australia — Monetary Policy Board", "https://www.rba.gov.au/about-rba/boards/mpb.html"),
    "NZD": ("Reserve Bank of New Zealand — Monetary Policy Committee", "https://www.rbnz.govt.nz/about-us/organisation-and-governance/monetary-policy-committee"),
    "CAD": ("Bank of Canada — Governing Council", "https://www.bankofcanada.ca/about/governing-council/"),
}



# ===================================================
# ECB — ROTACIÓN OFICIAL DETERMINISTA
# ===================================================

ECB_EXECUTIVE_BOARD = [
    "Christine Lagarde",
    "Boris Vujcic",
    "Piero Cipollone",
    "Frank Elderson",
    "Philip Lane",
    "Isabel Schnabel",
]

ECB_NCB_GOVERNORS = {
    "ES": "José Luis Escrivá",
    "FR": "Emmanuel Moulin",
    "IT": "Fabio Panetta",
    "NL": "Olaf Sleijpen",
    "DE": "Joachim Nagel",
    "BE": "Pierre Wunsch",
    "BG": "Dimitar Radev",
    "EE": "Ülo Kaasik",
    "IE": "Gabriel Makhlouf",
    "GR": "Yannis Stournaras",
    "HR": "Ante Žigman",
    "CY": "Christodoulos Patsalides",
    "LV": "Mārtiņš Kazāks",
    "LT": "Gediminas Šimkus",
    "LU": "Gaston Reinesch",
    "MT": "Alexander Demarco",
    "AT": "Martin Kocher",
    "PT": "Álvaro Santos Pereira",
    "SI": "Primož Dolenc",
    "SK": "Peter Kažimír",
    "FI": "Olli Rehn",
}

# Official ECB 2026 rotation table:
# https://www.ecb.europa.eu/ecb/decisions/govc/html/votingrights.en.html
ECB_2026_NCB_VOTERS = {
    1:  ["ES","FR","NL","DE","BG","EE","IE","GR","HR","CY","LV","LT","LU","MT","AT"],
    2:  ["ES","FR","IT","DE","GR","HR","CY","LV","LT","LU","MT","AT","PT","SI","SK"],
    3:  ["ES","FR","IT","NL","BE","BG","LV","LT","LU","MT","AT","PT","SI","SK","FI"],
    4:  ["FR","IT","NL","DE","BE","BG","EE","IE","GR","MT","AT","PT","SI","SK","FI"],
    5:  ["ES","IT","NL","DE","BE","BG","EE","IE","GR","HR","CY","LV","SI","SK","FI"],
    6:  ["ES","FR","NL","DE","BE","BG","EE","IE","GR","HR","CY","LV","LT","LU","MT"],
    7:  ["ES","FR","IT","NL","DE","IE","GR","HR","CY","LT","LU","MT","AT","PT","SI"],
    8:  ["ES","FR","IT","NL","BE","CY","LV","LT","LU","MT","AT","PT","SI","SK","FI"],
    9:  ["FR","IT","NL","DE","BE","BG","EE","IE","LV","LU","MT","PT","SI","SK","FI"],
    10: ["ES","IT","NL","DE","BE","BG","EE","IE","GR","HR","CY","PT","SI","SK","FI"],
    11: ["ES","FR","NL","DE","BE","BG","EE","IE","GR","HR","CY","LV","LT","LU","FI"],
    12: ["ES","FR","IT","DE","EE","IE","GR","HR","CY","LV","LT","LU","MT","AT","PT"],
}

ECB_VOTING_RIGHTS_SOURCE = (
    "https://www.ecb.europa.eu/ecb/decisions/govc/html/votingrights.en.html"
)


def _clean_date(value):
    value = str(value or "").strip()
    return value[:10] if value else ""


def _previous_meeting_date(previous_members):
    for item in previous_members or []:
        value = (
            item.get("NextMeetingDate")
            or item.get("next_meeting_date")
            or ""
        )
        value = _clean_date(value)
        if value:
            return value
    return ""


def _ecb_official_roster_for_date(date_value):
    date_value = _clean_date(date_value)
    if not date_value:
        return None

    try:
        year, month, _ = [int(x) for x in date_value.split("-")]
    except Exception:
        return None

    if year != 2026 or month not in ECB_2026_NCB_VOTERS:
        return None

    ncb_names = [
        ECB_NCB_GOVERNORS[code]
        for code in ECB_2026_NCB_VOTERS[month]
    ]

    roster = list(ECB_EXECUTIVE_BOARD) + ncb_names

    if len(roster) != 21:
        raise ValueError(
            f"ECB official roster inválido para {year}-{month:02d}: "
            f"{len(roster)} miembros, se esperaban 21."
        )

    return roster


def _valid_ecb_roster(ai_members, committee):
    if not isinstance(ai_members, list):
        return False

    names = []
    seen = set()
    for item in ai_members:
        name = str(item.get("name") or "").strip()
        key = _normalizar_nombre(name)
        if name and key not in seen:
            seen.add(key)
            names.append(name)

    if len(names) != 21:
        return False

    keys = {_normalizar_nombre(name) for name in names}
    required = {_normalizar_nombre(name) for name in ECB_EXECUTIVE_BOARD}
    if not required.issubset(keys):
        return False

    source_url = str(
        committee.get("membership_source_url") or ""
    ).strip().lower()

    return "ecb.europa.eu" in source_url


def _previous_as_ai_item(previous, name):
    structural = str(
        previous.get("StructuralBias")
        or previous.get("structural_bias")
        or "Neutral"
    ).strip()

    return {
        "name": name,
        "structural_bias_candidate": structural if structural in VALID_BIASES else "Neutral",
        "latest_signal": str(
            previous.get("LatestSignal")
            or previous.get("latest_signal")
            or structural
            or "Neutral"
        ).strip(),
        "expected_vote": str(
            previous.get("ExpectedVote")
            or previous.get("expected_vote")
            or "Unclear"
        ).strip(),
        "confidence": str(
            previous.get("Confidence")
            or previous.get("confidence")
            or "Low"
        ).strip(),
        "evidence_type": str(
            previous.get("EvidenceType")
            or previous.get("evidence_type")
            or "No new evidence"
        ).strip(),
        "reason": str(
            previous.get("Evidence")
            or previous.get("reason")
            or ""
        ).strip(),
        "evidence_date": (
            previous.get("EvidenceDate")
            or previous.get("evidence_date")
            or None
        ),
        "source": str(
            previous.get("Source")
            or previous.get("source")
            or ""
        ).strip(),
        "source_url": str(
            previous.get("SourceURL")
            or previous.get("source_url")
            or ""
        ).strip(),
    }


def _stabilize_official_roster(currency, ai_members, previous_members, committee):
    """
    Lock non-ECB committees to the verified roster in COMMITTEE_CONFIG.

    AI is allowed to research bias/evidence for those names, but it cannot add a
    retired/non-voting person or silently remove an official voter. Missing AI
    research falls back to the prior snapshot, then to a neutral placeholder.
    """
    if not OFFICIAL_ROSTER_GUARD or currency == "EUR":
        return ai_members

    target_names = list(COMMITTEE_CONFIG[currency]["fallback_voters"])
    previous_index = _indice_previos(previous_members or [])

    ai_index = {}
    for item in ai_members or []:
        name = str(item.get("name") or "").strip()
        key = _normalizar_nombre(name)
        if name and key and key not in ai_index:
            ai_index[key] = item

    source_name, source_url = OFFICIAL_ROSTER_SOURCES.get(
        currency,
        (COMMITTEE_CONFIG[currency]["banco"], ""),
    )
    committee["membership_source"] = source_name
    committee["membership_source_url"] = source_url

    stabilized = []
    for target_name in target_names:
        key = _normalizar_nombre(target_name)

        if key in ai_index:
            item = dict(ai_index[key])
            item["name"] = target_name
            stabilized.append(item)
            continue

        previous = previous_index.get(key)
        if previous:
            stabilized.append(_previous_as_ai_item(previous, target_name))
            continue

        stabilized.append({
            "name": target_name,
            "vote_score": 0,
            "path_score": 0,
            "risk_score": 0,
            "latest_signal": "Neutral",
            "expected_vote": "Unclear",
            "confidence": "Low",
            "evidence_type": "No new evidence",
            "reason": (
                "Votante incluido por el roster oficial protegido; "
                "sin evidencia individual suficiente en esta ejecución."
            ),
            "evidence_date": None,
            "source": source_name,
            "source_url": source_url,
        })

    ignored = []
    allowed = {_normalizar_nombre(x) for x in target_names}
    for item in ai_members or []:
        name = str(item.get("name") or "").strip()
        if name and _normalizar_nombre(name) not in allowed:
            ignored.append(name)

    if ignored:
        print(
            f"[{currency}] ROSTER GUARD · ignored non-roster AI members: "
            + ", ".join(ignored)
        )

    print(
        f"[{currency}] ROSTER GUARD · official voters={len(stabilized)}"
    )
    return stabilized


def _stabilize_ecb_members(ai_members, previous_members, committee):
    previous_members = previous_members or []
    previous_index = _indice_previos(previous_members)

    ai_index = {}
    for item in ai_members or []:
        name = str(item.get("name") or "").strip()
        key = _normalizar_nombre(name)
        if name and key and key not in ai_index:
            ai_index[key] = item

    meeting_date = _clean_date(
        committee.get("next_meeting_date")
    )
    previous_meeting = _previous_meeting_date(
        previous_members
    )

    target_names = _ecb_official_roster_for_date(
        meeting_date
    )

    if target_names:
        mode = "official_2026_rotation"
        committee["membership_source"] = (
            "European Central Bank — Rotation of voting rights"
        )
        committee["membership_source_url"] = ECB_VOTING_RIGHTS_SOURCE

    elif _valid_ecb_roster(ai_members, committee):
        target_names = [
            str(item.get("name") or "").strip()
            for item in ai_members
            if str(item.get("name") or "").strip()
        ]
        mode = "validated_official_fallback"

    elif previous_members and len(previous_index) == 21:
        target_names = [
            str(
                item.get("Member")
                or item.get("name")
                or ""
            ).strip()
            for item in previous_members
            if str(
                item.get("Member")
                or item.get("name")
                or ""
            ).strip()
        ]
        mode = "fallback_previous"

    else:
        raise ValueError(
            "No se pudo determinar de forma segura el roster ECB."
        )

    stabilized = []
    used = set()

    for target_name in target_names:
        key = _normalizar_nombre(target_name)
        if not key or key in used:
            continue
        used.add(key)

        if key in ai_index:
            item = dict(ai_index[key])
            item["name"] = target_name
            stabilized.append(item)
            continue

        previous = previous_index.get(key)
        if previous:
            stabilized.append(
                _previous_as_ai_item(previous, target_name)
            )
            continue

        stabilized.append({
            "name": target_name,
            "vote_score": 0,
            "path_score": 0,
            "risk_score": 0,
            "latest_signal": "Neutral",
            "expected_vote": "Unclear",
            "confidence": "Low",
            "evidence_type": "No new evidence",
            "reason": (
                "Votante determinado por la rotación oficial del BCE; "
                "sin evidencia individual suficiente en esta ejecución."
            ),
            "evidence_date": None,
            "source": "European Central Bank",
            "source_url": ECB_VOTING_RIGHTS_SOURCE,
        })

    if len(stabilized) != 21:
        raise ValueError(
            f"ECB roster final inválido: {len(stabilized)} miembros."
        )

    print(
        f"[EUR] ECB roster mode={mode} · "
        f"meeting={meeting_date or 'unknown'} · "
        f"voters={len(stabilized)}"
    )

    return stabilized, mode, previous_meeting

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
# V14 — DETERMINISTIC EVIDENCE SCORING
# ===================================================

def _clamp(value, low=-2.0, high=2.0):
    return max(low, min(high, float(value)))


def _date_decay(date_value):
    """Structural evidence decays more slowly than a latest-signal headline.
    <30d 1.0, 30-90d .9, 90-180d .7, older .4.
    Missing/invalid dates get a conservative .6."""
    value = _clean_date(date_value)
    if not value:
        return 0.6
    try:
        evidence_dt = datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        days = max(0, (datetime.now(timezone.utc) - evidence_dt).days)
    except Exception:
        return 0.6
    if days < 30:
        return 1.0
    if days < 90:
        return 0.9
    if days < 180:
        return 0.7
    return 0.4


def _evidence_quality_weight(evidence_type, confidence):
    type_weight = {
        "Official vote": 1.00,
        "Explicit stance change": 1.00,
        "Multiple consistent statements": 0.90,
        "Single statement": 0.45,
        "No new evidence": 0.20,
    }.get(str(evidence_type or ""), 0.40)
    conf_weight = {"High": 1.00, "Medium": 0.90, "Low": 0.60}.get(
        str(confidence or ""), 0.60
    )
    return type_weight * conf_weight


def _valid_https_url(value):
    value = str(value or "").strip()
    return value.startswith("https://")


def _valid_iso_date(value):
    value = str(value or "").strip()
    if not value:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except Exception:
        return False


def _component_payload_ok(item, prefix):
    evidence = str(item.get(f"{prefix}_evidence") or "").strip()
    source = str(item.get(f"{prefix}_source") or "").strip()
    source_url = str(item.get(f"{prefix}_source_url") or "").strip()
    date_value = item.get(f"{prefix}_date")
    return (
        bool(evidence)
        and bool(source)
        and _valid_https_url(source_url)
        and _valid_iso_date(date_value)
    )


def _audit_component_scores(item):
    """
    V14.3 deterministic evidence audit.

    OpenAI can propose vote/path/risk scores, but Python is authoritative.
    A component is zeroed when its component-specific evidence is insufficient.

    vote_score:
      - non-zero requires a dated source + explicit formal vote/proposal evidence
        and vote_verified_official=True.
      - |2| additionally requires vote_differentiated=True.

    path_score:
      - non-zero requires a dated source + explicit relative policy-path evidence
        and path_explicit_relative=True.
      - |2| additionally requires High confidence.

    risk_score:
      - non-zero requires a dated source + reaction-function evidence.
      - |2| additionally requires risk_persistent=True and High confidence.
    """
    if not V14_COMPONENT_EVIDENCE_AUDIT:
        return {
            "vote_score": _clamp(item.get("vote_score", 0)),
            "path_score": _clamp(item.get("path_score", 0)),
            "risk_score": _clamp(item.get("risk_score", 0)),
            "vote_audit": "audit_disabled",
            "path_audit": "audit_disabled",
            "risk_audit": "audit_disabled",
        }

    def proposed(key):
        try:
            return _clamp(item.get(key, 0))
        except Exception:
            return 0.0

    confidence = str(item.get("confidence") or "Low").strip()

    vote = proposed("vote_score")
    path = proposed("path_score")
    risk = proposed("risk_score")

    vote_audit = "accepted_zero"
    path_audit = "accepted_zero"
    risk_audit = "accepted_zero"

    # ---- Vote ----
    if vote != 0:
        if not _component_payload_ok(item, "vote"):
            vote = 0.0
            vote_audit = "zeroed_missing_component_evidence"
        elif item.get("vote_verified_official") is not True:
            vote = 0.0
            vote_audit = "zeroed_not_verified_official"
        elif abs(vote) >= 1.5 and item.get("vote_differentiated") is not True:
            vote = 0.0
            vote_audit = "zeroed_extreme_not_differentiated"
        else:
            vote_audit = "accepted"

    # ---- Path ----
    if path != 0:
        if not _component_payload_ok(item, "path"):
            path = 0.0
            path_audit = "zeroed_missing_component_evidence"
        elif item.get("path_explicit_relative") is not True:
            path = 0.0
            path_audit = "zeroed_not_explicit_relative"
        elif abs(path) >= 1.5 and confidence != "High":
            # Preserve direction but cap an insufficiently confirmed extreme at ±1.
            path = 1.0 if path > 0 else -1.0
            path_audit = "capped_extreme_without_high_confidence"
        else:
            path_audit = "accepted"

    # ---- Risk ----
    if risk != 0:
        if not _component_payload_ok(item, "risk"):
            risk = 0.0
            risk_audit = "zeroed_missing_component_evidence"
        elif abs(risk) >= 1.5 and not (
            item.get("risk_persistent") is True and confidence == "High"
        ):
            risk = 1.0 if risk > 0 else -1.0
            risk_audit = "capped_extreme_without_persistence"
        else:
            risk_audit = "accepted"

    return {
        "vote_score": float(vote),
        "path_score": float(path),
        "risk_score": float(risk),
        "vote_audit": vote_audit,
        "path_audit": path_audit,
        "risk_audit": risk_audit,
    }


def _raw_evidence_score(item):
    """
    OpenAI supplies evidence dimensions only. Python combines them.
    Each dimension is bounded to [-2,+2]:
      vote_score: dissent/official voting evidence
      path_score: explicit preferred rate path / speed
      risk_score: durable inflation-vs-activity reaction-function emphasis
    """
    audited = _audit_component_scores(item)
    vote = audited["vote_score"]
    path = audited["path_score"]
    risk = audited["risk_score"]

    # Votes and explicit policy-path preferences dominate rhetoric.
    # V14.2 gives slightly more weight to explicit path guidance.
    base = 0.48 * vote + 0.38 * path + 0.14 * risk
    quality = _evidence_quality_weight(
        item.get("evidence_type"), item.get("confidence")
    )
    decay = _date_decay(item.get("evidence_date"))
    return _clamp(base * quality * decay)


def _score_to_bias(score):
    """V14.1 calibrated five-band mapping.

    The Neutral zone is deliberately narrower. A persistent, differentiated tilt
    should show as Lean Hawkish/Dovish, while full Hawkish/Dovish requires a
    clearly strong relative reaction function.
    """
    score = float(score)
    if score >= 0.80:
        return "Hawkish"
    if score >= 0.30:
        return "Lean Hawkish"
    if score > -0.30:
        return "Neutral"
    if score > -0.80:
        return "Lean Dovish"
    return "Dovish"


def _has_differentiated_relative_evidence(item, direction):
    """Require something stronger than generic committee-consensus language.

    This does NOT choose the bias. It only checks whether extracted evidence
    contains a genuinely differentiated relative stance.
    """
    try:
        vote = float(item.get("vote_score", 0) or 0)
        path = float(item.get("path_score", 0) or 0)
        risk = float(item.get("risk_score", 0) or 0)
    except Exception:
        return False

    evidence_type = str(item.get("evidence_type") or "")
    confidence = str(item.get("confidence") or "Low")

    signed_vote = vote * direction
    signed_path = path * direction
    signed_risk = risk * direction

    if signed_vote >= 1.0:
        return True
    if signed_path >= 0.75:
        return True
    if (
        signed_risk >= 1.5
        and evidence_type in {"Explicit stance change", "Multiple consistent statements"}
        and confidence == "High"
    ):
        return True
    return False


def _v14_evidence_sufficiency(item, audited, structural_score):
    """Classify evidence availability separately from policy direction."""
    if not V14_EVIDENCE_SUFFICIENCY:
        return "directional_evidence"

    vote = float(audited.get("vote_score", 0) or 0)
    path = float(audited.get("path_score", 0) or 0)
    risk = float(audited.get("risk_score", 0) or 0)
    has_component = any(abs(x) > 0 for x in (vote, path, risk))

    evidence_type = str(item.get("evidence_type") or "").strip()
    confidence = str(item.get("confidence") or "Low").strip()
    latest_signal = str(item.get("latest_signal") or "").strip()

    # Neutrality must itself be evidenced. Zero components alone do not prove it.
    affirmative_neutral = (
        not has_component
        and latest_signal == "Neutral"
        and evidence_type in {
            "Official vote",
            "Explicit stance change",
            "Multiple consistent statements",
        }
        and confidence in {"Medium", "High"}
        and bool(str(item.get("reason") or "").strip())
        and _valid_https_url(item.get("source_url"))
    )
    if affirmative_neutral:
        return "neutral_evidence"

    if has_component and abs(float(structural_score)) >= V14_MIN_ABS_SCORE_FOR_DIRECTIONAL_EVIDENCE:
        return "directional_evidence"

    return "insufficient_evidence"


def _v14_neutralization_allowed(previous_bias, candidate, sufficiency, structural_score, item):
    """
    V14.3.2 persistent-state guard.

    Existing directional structural bias may move to Neutral only when:
      1) there is affirmative neutral evidence, OR
      2) audited directional evidence clearly points AGAINST the previous bias.

    Weak evidence that still points in the SAME direction as the stored bias
    must never erase that bias simply because its score lands in the Neutral band.
    """
    if not V14_NEUTRALIZATION_GUARD:
        return True, "guard_disabled"

    previous_bias = str(previous_bias or "").strip()
    candidate = str(candidate or "").strip()
    sufficiency = str(sufficiency or "").strip()

    if candidate != "Neutral":
        return True, "not_neutral_candidate"

    if previous_bias not in {"Hawkish", "Lean Hawkish", "Lean Dovish", "Dovish"}:
        return True, "no_directional_prior"

    if sufficiency == "neutral_evidence":
        return True, "affirmative_neutral_evidence"

    if sufficiency != "directional_evidence":
        return False, "no_affirmative_neutralization"

    try:
        score = float(structural_score)
    except Exception:
        score = 0.0

    previous_sign = 1 if previous_bias in {"Hawkish", "Lean Hawkish"} else -1
    opposing = score * previous_sign < -V14_MIN_OPPOSING_SCORE_FOR_NEUTRALIZATION

    confidence = str(item.get("confidence") or "Low").strip()
    evidence_type = str(item.get("evidence_type") or "").strip()

    if (
        opposing
        and confidence in {"Medium", "High"}
        and evidence_type in {
            "Official vote",
            "Explicit stance change",
            "Multiple consistent statements",
            "Single statement",
        }
    ):
        return True, "opposing_directional_evidence"

    return False, "same_direction_or_too_weak"


def _prepare_v14_scores(ai_members, previous_members):
    """
    V14.3:
    StructuralScore is evidence-only. Before scoring, each V/P/R component is
    audited deterministically against its own evidence payload.
    """
    previous_index = _indice_previos(previous_members or [])

    raw = {}
    item_index = {}
    audit_index = {}

    for item in ai_members or []:
        name = str(item.get("name") or "").strip()
        key = _normalizar_nombre(name)
        if not key:
            continue

        audited = _audit_component_scores(item)
        audited_item = dict(item)
        audited_item["vote_score"] = audited["vote_score"]
        audited_item["path_score"] = audited["path_score"]
        audited_item["risk_score"] = audited["risk_score"]

        item_index[key] = audited_item
        audit_index[key] = audited
        raw[key] = _raw_evidence_score(audited_item)

    values = sorted(raw.values())
    if values:
        n = len(values)
        committee_center = (
            values[n // 2]
            if n % 2
            else (values[n // 2 - 1] + values[n // 2]) / 2.0
        )
    else:
        committee_center = 0.0

    scored = {}
    for key, absolute_score in raw.items():
        relative_score = _clamp(
            absolute_score - V14_RELATIVE_WEIGHT * committee_center
        )
        candidate = _score_to_bias(relative_score)

        item = item_index.get(key, {})
        audited = audit_index.get(key, {})
        prev = previous_index.get(key, {})
        prev_bias = str(
            prev.get("StructuralBias") or prev.get("structural_bias") or ""
        ).strip()

        sufficiency = _v14_evidence_sufficiency(item, audited, relative_score)
        guard_status = "not_needed"

        if sufficiency == "insufficient_evidence":
            candidate = "INSUFFICIENT_EVIDENCE"

        elif candidate in {"Lean Hawkish", "Lean Dovish"} and prev_bias in {"", "Neutral"}:
            direction = 1 if candidate == "Lean Hawkish" else -1
            if not _has_differentiated_relative_evidence(item, direction):
                candidate = "Neutral"
                guard_status = "blocked_generic_consensus"
            else:
                guard_status = "passed"

        scored[key] = {
            "absolute_score": round(absolute_score, 3),
            "committee_center": round(committee_center, 3),
            "structural_score": round(relative_score, 3),
            "candidate": candidate,
            "guard": guard_status,
            "sufficiency": sufficiency,
            "vote_score": audited.get("vote_score", 0),
            "path_score": audited.get("path_score", 0),
            "risk_score": audited.get("risk_score", 0),
            "vote_audit": audited.get("vote_audit", ""),
            "path_audit": audited.get("path_audit", ""),
            "risk_audit": audited.get("risk_audit", ""),
            "audited_item": item,
        }

    return scored

def _webapp_post(payload, timeout=90, max_retries=3):
    """POST robusto a Apps Script con reintentos para fallos transitorios."""
    if not CENTRAL_BANK_DRIVERS_WEBAPP_URL:
        raise ValueError("Falta CENTRAL_BANK_DRIVERS_WEBAPP_URL.")

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                CENTRAL_BANK_DRIVERS_WEBAPP_URL,
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()

            try:
                data = response.json()
            except Exception:
                raise requests.exceptions.RequestException(
                    "Apps Script no devolvió JSON válido: "
                    + response.text[:500]
                )

            if not data.get("ok"):
                raise ValueError(
                    "Apps Script devolvió error: "
                    + str(data.get("error"))
                )

            return data

        except ValueError:
            raise

        except (
            requests.exceptions.Timeout,
            requests.exceptions.ConnectionError,
            requests.exceptions.RequestException,
        ) as error:
            last_error = error

            if attempt >= max_retries:
                break

            wait_seconds = 5 * attempt + random.uniform(0, 2)
            action = str(payload.get("action") or "unknown")
            print(
                f"[WebApp:{action}] Error transitorio "
                f"(intento {attempt}/{max_retries}): {error}. "
                f"Reintento en {wait_seconds:.1f}s..."
            )
            time.sleep(wait_seconds)

    raise RuntimeError(
        f"Apps Script no respondió correctamente tras "
        f"{max_retries} intentos: {last_error}"
    )


def cargar_estado_previo_miembros(currency):
    """
    Lee CentralBank_Members a través del Web App y distingue dos estados:

    - (members, True): la lectura del backend fue válida. `members` puede ser []
      en una inicialización real.
    - ([], False): el backend falló. Este caso NUNCA debe interpretarse como
      una primera ejecución, porque podría sobrescribir el snapshot histórico.
    """
    try:
        data = _webapp_post(
            {
                "action": "get_central_bank_members",
                "currency": currency,
            }
        )
        members = data.get("members", [])
        if isinstance(members, list):
            return members, True

        raise ValueError(
            "get_central_bank_members devolvió un campo members no válido."
        )

    except Exception as error:
        print(
            f"[{currency}] FAILSAFE · no se pudo cargar el snapshot previo: "
            f"{error}"
        )
        print(
            f"[{currency}] FAILSAFE · se conservará CentralBank_Members sin cambios "
            "para evitar una falsa inicialización."
        )
        return [], False


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

    # Give the model the previous roster for identity/membership continuity,
    # but deliberately REMOVE prior bias/signal fields. The model must build an
    # independent StructuralBiasCandidate from current/recent evidence rather
    # than echoing the stored classification. Python compares the candidate
    # with the real previous StructuralBias afterwards.
    previous_members_for_model = []
    for previous in previous_members or []:
        previous_members_for_model.append({
            "Member": previous.get("Member") or previous.get("name") or "",
            "Voting": previous.get("Voting", True),
            "MembershipAsOf": previous.get("MembershipAsOf"),
            "NextMeetingDate": previous.get("NextMeetingDate"),
        })

    prev_json = json.dumps(
        previous_members_for_model,
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
approximately the last 72 hours by relevant officials of this central bank.

MANDATORY COVERAGE PROCEDURE:
- Search EACH current/fallback voter's full name together with the central-bank
  name or acronym; do not rely only on a general central-bank news search.
- For Part A, search both official sources and reputable financial-news/wire
  sources, including Reuters, Bloomberg, MNI/Market News, Newsquawk and other
  outlets that report direct central-bank remarks.
- An interview or direct quotation remains eligible when the original article
  is paywalled, provided an accessible reputable result accurately reports the
  remark. Use the best accessible reporting URL as source_url.
- If recent evidence found while researching Part B contains a direct,
  monetary-policy-relevant statement by a voter, it MUST also be returned in
  Part A as an event. Do not leave it only inside that member's reason field.
- Before returning an empty events array, explicitly verify every listed
  current/fallback voter for the search window.

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

Use OFFICIAL central-bank sources as the primary authority for committee
membership. This official-source preference does NOT restrict Part A:
reputable interviews, wires and financial-news reports are valid statement
sources.

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

Previous saved ROSTER from CentralBank_Members (bias fields intentionally omitted):
{prev_json}

CRITICAL — V14.3 AUDITABLE EVIDENCE EXTRACTION:
For EVERY current voter, extract objective monetary-policy evidence. Python,
not you, owns the final StructuralBias classification. You are intentionally
NOT shown the stored StructuralBias.

Assess a meaningful recent policy window and distinguish a member's stance
RELATIVE TO THEIR COMMITTEE from merely supporting the institution's current
policy path. Do not infer "hawkish" just because a member supports a hike that
is already the committee consensus.

Use Neutral only when the evidence is genuinely balanced/unclear. A consistent
moderate tilt should be Lean Hawkish or Lean Dovish.

RECALIBRATION MODE FOR THIS RUN: {RECALIBRATE_BIAS}
When True, Python may accept the independent candidate directly. When False,
Python applies controlled one-step evolution rules after receiving the candidate.

For EVERY current voter return:

vote_score:
number from -2 to +2. Use +2 for a clearly hawkish dissent/proposal relative
to the majority, -2 for a clearly dovish dissent/proposal, and 0 when voting
with the committee provides no relative information.

vote_evidence / vote_date / vote_source / vote_source_url:
component-specific evidence supporting vote_score. If vote_score is 0, use an
empty evidence/source/url and null date when no useful voting evidence exists.
vote_verified_official:
true ONLY when the score is grounded in a formal central-bank vote, minutes,
decision record, or clearly documented formal policy proposal.
vote_differentiated:
true ONLY when that vote/proposal differs materially from the committee
majority/baseline. A routine vote with consensus is false.

path_score:
number from -2 to +2 measuring explicit preference for a tighter/faster (+)
or easier/slower (-) policy path RELATIVE TO the committee baseline.

path_evidence / path_date / path_source / path_source_url:
component-specific evidence supporting path_score.
path_explicit_relative:
true ONLY when the source explicitly shows a tighter/faster or easier/slower
preference relative to the committee baseline. Generic support for the current
institutional path is false. For |path_score|=2, the evidence must be unusually
clear and differentiated.

risk_score:
number from -2 to +2 for a durable reaction-function emphasis: upside
inflation/tightening risks (+), downside activity/employment/easing risks (-).
Do not use generic inflation concern as +1 if it simply repeats consensus.

risk_evidence / risk_date / risk_source / risk_source_url:
component-specific evidence supporting risk_score.
risk_persistent:
true ONLY when the directional reaction-function emphasis is repeated,
persistent, or especially explicit. One generic remark is false.

CRITICAL V14.3 AUDIT RULE:
Do not invent a component score merely to make the final stance look plausible.
Each non-zero component must stand on its OWN cited evidence. Python will zero
or cap unsupported components automatically.

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
Structural bias is a persistent policy orientation. It is NOT the expected
vote at the next meeting and it is NOT a synonym for Hike / Hold / Cut.

Interpret the five categories as follows:
- Hawkish: clear, persistent preference for tighter policy / stronger
  inflation vigilance relative to the committee.
- Lean Hawkish: discernible hawkish inclination, but less strong or less
  persistent than Hawkish.
- Neutral: NO CLEAR STRUCTURAL HAWKISH OR DOVISH BIAS. 
    Use Lean Hawkish or Lean Dovish whenever there is a consistent but moderate
    directional inclination, even if the evidence is not strong enough to justify
    a full Hawkish or Dovish classification.

    Do not overuse Neutral. If the balance of recent votes, speeches and reaction
    function consistently tilts in one direction, prefer the corresponding Lean
    category over Neutral.
The member can lean
  toward either camp depending on incoming data and circumstances.
  IMPORTANT: Neutral does NOT mean the member favors unchanged rates,
  does NOT mean "Hold", and does NOT mean centrist voting at the next meeting.
- Lean Dovish: discernible dovish inclination, but less strong or less
  persistent than Dovish.
- Dovish: clear, persistent preference for easier policy / greater concern
  about activity or employment relative to the committee.

Classify structural bias using the best available evidence over a meaningful
recent policy window, not merely the last 48 hours. Consider, in order of
importance:
1) official policy votes and dissents,
2) explicit statements about the appropriate policy path,
3) repeated speeches/interviews showing a consistent reaction function,
4) minutes and other official evidence,
5) older evidence only when no newer evidence supersedes it.

Do NOT assign Neutral merely because there is no new statement in the last
48 hours. Lack of fresh evidence is not evidence of neutrality.

Your StructuralBiasCandidate must be based on the member's evidence, not on
database inertia. Python — not you — will compare it with the stored bias.

Evidence strong enough to support a structural candidate should preferably be:
- official policy votes/dissents, OR
- an explicit policy-path/stance statement, OR
- multiple consistent recent statements showing a durable reaction function.

IMPORTANT: do not label evidence_type as "Single statement" merely because only
one new article appeared in the last 72 hours. If that fresh statement confirms
older votes/speeches that establish the same structural direction, classify the
combined evidence as "Multiple consistent statements" and propose the bias that
best represents the member TODAY. This is especially important when an old
Neutral classification has become stale.

A genuinely isolated statement can make latest_signal directional while the
StructuralBiasCandidate remains Neutral or less directional. "No new evidence"
refers to the evidence update, not to a requirement that the candidate be Neutral.

Keep expected_vote independent from StructuralBias. A Neutral member may
currently be expected to Hike, Hold or Cut; likewise a Hawkish member can
vote Hold when the current policy setting already matches their reaction
function.

For committee composition, Lean Hawkish belongs to the HAWK camp and
Lean Dovish belongs to the DOVE camp. Keep the five-category value for each
individual member; the frontend will aggregate the camps.

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
                                            "vote_score": {
                                                "type": "number",
                                                "minimum": -2,
                                                "maximum": 2,
                                            },
                                            "vote_evidence": {
                                                "type": "string"
                                            },
                                            "vote_date": {
                                                "type": ["string", "null"]
                                            },
                                            "vote_source": {
                                                "type": "string"
                                            },
                                            "vote_source_url": {
                                                "type": "string"
                                            },
                                            "vote_verified_official": {
                                                "type": "boolean"
                                            },
                                            "vote_differentiated": {
                                                "type": "boolean"
                                            },
                                            "path_score": {
                                                "type": "number",
                                                "minimum": -2,
                                                "maximum": 2,
                                            },
                                            "path_evidence": {
                                                "type": "string"
                                            },
                                            "path_date": {
                                                "type": ["string", "null"]
                                            },
                                            "path_source": {
                                                "type": "string"
                                            },
                                            "path_source_url": {
                                                "type": "string"
                                            },
                                            "path_explicit_relative": {
                                                "type": "boolean"
                                            },
                                            "risk_score": {
                                                "type": "number",
                                                "minimum": -2,
                                                "maximum": 2,
                                            },
                                            "risk_evidence": {
                                                "type": "string"
                                            },
                                            "risk_date": {
                                                "type": ["string", "null"]
                                            },
                                            "risk_source": {
                                                "type": "string"
                                            },
                                            "risk_source_url": {
                                                "type": "string"
                                            },
                                            "risk_persistent": {
                                                "type": "boolean"
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
                                            "vote_score",
                                            "vote_evidence",
                                            "vote_date",
                                            "vote_source",
                                            "vote_source_url",
                                            "vote_verified_official",
                                            "vote_differentiated",
                                            "path_score",
                                            "path_evidence",
                                            "path_date",
                                            "path_source",
                                            "path_source_url",
                                            "path_explicit_relative",
                                            "risk_score",
                                            "risk_evidence",
                                            "risk_date",
                                            "risk_source",
                                            "risk_source_url",
                                            "risk_persistent",
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
    seen_event_keys = set()

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

        event_date = str(
            evento.get("event_date")
            or ""
        ).strip()

        source_url = str(
            evento.get("source_url")
            or ""
        ).strip()

        # Same member + day + source URL is treated as one event. This avoids
        # two paraphrases of the same speech becoming separate driver cards.
        if source_url:
            event_key = (
                currency,
                _normalizar_nombre(member),
                event_date,
                source_url.split("#", 1)[0].rstrip("/"),
            )
        else:
            # Without a URL, use normalized statement as conservative fallback.
            statement_key = re.sub(
                r"[^a-z0-9]+",
                " ",
                unicodedata.normalize("NFKD", statement.lower())
                .encode("ascii", "ignore")
                .decode("ascii"),
            ).strip()
            event_key = (
                currency,
                _normalizar_nombre(member),
                event_date,
                statement_key,
            )

        if event_key in seen_event_keys:
            continue

        seen_event_keys.add(event_key)

        texto_id = "|".join(str(x) for x in event_key)

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
            "SourceURL": source_url,
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
    """
    Clave estable de identidad para miembros del comité.

    Normaliza:
    - mayúsculas/minúsculas
    - acentos
    - guiones y puntuación
    - iniciales intermedias de una sola letra

    Ejemplos:
    John C. Williams -> john williams
    John Williams    -> john williams
    Marc-André Gosselin -> marc andre gosselin
    """
    value = str(nombre or "").strip().lower()

    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        ch for ch in value
        if not unicodedata.combining(ch)
    )

    value = re.sub(r"[^a-z0-9]+", " ", value)
    tokens = [token for token in value.split() if token]

    if len(tokens) >= 3:
        tokens = [
            token
            for i, token in enumerate(tokens)
            if not (
                0 < i < len(tokens) - 1
                and len(token) == 1
            )
        ]

    return " ".join(tokens)



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


def _hysteresis_blocks_reversal(
    previous_bias,
    previous_previous_bias,
    previous_change,
    structural_bias_candidate,
    confidence,
    evidence_type,
    recalibrate=False,
):
    """Block an immediate reversal on the run right after a structural change.

    The saved row already contains StructuralBias, PreviousBias and BiasChange.
    If the last run moved the member and today's candidate points back in the
    opposite direction, require a second confirming run. Only an explicit,
    high-confidence stance change can override the cooldown immediately.
    """
    if recalibrate or not BIAS_HYSTERESIS:
        return False
    if previous_bias not in BIAS_SCORE or previous_previous_bias not in BIAS_SCORE:
        return False
    if structural_bias_candidate not in BIAS_SCORE:
        return False
    if previous_change not in {"More Hawkish", "More Dovish"}:
        return False

    last_delta = BIAS_SCORE[previous_bias] - BIAS_SCORE[previous_previous_bias]
    new_delta = BIAS_SCORE[structural_bias_candidate] - BIAS_SCORE[previous_bias]
    if last_delta == 0 or new_delta == 0:
        return False

    is_reversal = (last_delta > 0 and new_delta < 0) or (last_delta < 0 and new_delta > 0)
    if not is_reversal:
        return False

    exceptional_override = (
        evidence_type == "Explicit stance change"
        and confidence == "High"
    )
    return not exceptional_override


def _v14_transition_guard(
    previous_bias,
    candidate_bias,
    evidence_type,
    confidence,
    item,
    recalibrate=False,
):
    """
    State-transition safety only. It does NOT alter EvidenceScore.
    """
    if recalibrate or not V14_REQUIRE_CONFIRMATION_FOR_EXTREMES:
        return False, ""

    previous_bias = str(previous_bias or "").strip()
    candidate_bias = str(candidate_bias or "").strip()
    evidence_type = str(evidence_type or "").strip()
    confidence = str(confidence or "Low").strip()

    if previous_bias not in BIAS_SCORE or candidate_bias not in BIAS_SCORE:
        return False, ""

    prev_score = BIAS_SCORE[previous_bias]
    cand_score = BIAS_SCORE[candidate_bias]
    delta = cand_score - prev_score

    # Persistent state never jumps more than one category per normal run.
    if abs(delta) > 1:
        return True, "block_multi_rung"

    # Entering a full extreme requires High-confidence differentiated evidence.
    if candidate_bias in {"Hawkish", "Dovish"} and previous_bias not in {"Hawkish", "Dovish"}:
        direction = 1 if candidate_bias == "Hawkish" else -1
        strong_relative = _has_differentiated_relative_evidence(item, direction)
        strong_type = evidence_type in {
            "Official vote",
            "Explicit stance change",
            "Multiple consistent statements",
        }
        if not (strong_relative and strong_type and confidence == "High"):
            return True, "block_extreme_without_high_confirmation"

    return False, ""


def _resolver_bias(
    previous_bias,
    structural_bias_candidate,
    latest_signal,
    confidence,
    evidence_type,
    previous_previous_bias="",
    previous_change="",
    recalibrate=False,
):
    """
    Structural bias is stable, while an independent candidate prevents stale anchoring.

    Normal runs:
    - preserve on no evidence / weak contradictory evidence;
    - accept an adjacent one-step move with strong evidence and Medium/High confidence;
    - accept an adjacent one-step move with a fresh Single statement only when
      structural_bias_candidate and latest_signal agree and confidence is High;
    - never jump more than one category automatically. Large reclassifications
      require a later confirming run or explicit one-time recalibration.
    """
    previous_bias = str(previous_bias or "").strip()
    structural_bias_candidate = str(structural_bias_candidate or "Neutral").strip()
    latest_signal = str(latest_signal or structural_bias_candidate or "Neutral").strip()
    confidence = str(confidence or "Low").strip()
    evidence_type = str(evidence_type or "No new evidence").strip()

    if structural_bias_candidate not in VALID_BIASES:
        structural_bias_candidate = "Neutral"
    if latest_signal not in VALID_BIASES:
        latest_signal = structural_bias_candidate

    if previous_bias not in VALID_BIASES:
        return structural_bias_candidate
    if recalibrate:
        return structural_bias_candidate
    if structural_bias_candidate == previous_bias:
        return previous_bias
    if evidence_type == "No new evidence":
        return previous_bias

    if _hysteresis_blocks_reversal(
        previous_bias,
        previous_previous_bias,
        previous_change,
        structural_bias_candidate,
        confidence,
        evidence_type,
        recalibrate=recalibrate,
    ):
        return previous_bias

    prev_score = BIAS_SCORE[previous_bias]
    prop_score = BIAS_SCORE[structural_bias_candidate]
    delta = prop_score - prev_score
    direction = 1 if delta > 0 else -1

    strong_evidence = evidence_type in {
        "Official vote",
        "Explicit stance change",
        "Multiple consistent statements",
    }
    strong_enough = strong_evidence and confidence in {"Medium", "High"}

    # A high-confidence fresh statement may establish a moderate lean when the
    # model's independent structural candidate and latest signal point the same way.
    signal_confirms = (
        evidence_type == "Single statement"
        and confidence == "High"
        and BIAS_SCORE[latest_signal] * direction > BIAS_SCORE[previous_bias] * direction
        and BIAS_SCORE[structural_bias_candidate] * direction > BIAS_SCORE[previous_bias] * direction
    )

    if not AUTO_BIAS_EVOLUTION or not (strong_enough or signal_confirms):
        return previous_bias

    # Move only one rung per run. This fixes stale Neutral classifications while
    # preventing one search result from flipping Neutral straight to Hawkish/Dovish.
    target_score = prev_score + direction * min(abs(delta), MAX_AUTO_BIAS_STEP)
    return next(bias for bias, score in BIAS_SCORE.items() if score == target_score)

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

    ecb_roster_mode = ""
    previous_meeting = _previous_meeting_date(
        previous_members
    )

    if currency == "EUR":
        ai_members, ecb_roster_mode, previous_meeting = (
            _stabilize_ecb_members(
                ai_members,
                previous_members,
                committee,
            )
        )
    else:
        ai_members = _stabilize_official_roster(
            currency,
            ai_members,
            previous_members,
            committee,
        )

    previous_index = _indice_previos(
        previous_members
    )

    updated_at = datetime.now(
        timezone.utc
    ).isoformat()

    current_rows = []
    current_keys = set()
    changes = []

    v14_scores = _prepare_v14_scores(ai_members, previous_members)

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

        previous_name = str(
            previous.get("Member")
            or previous.get("name")
            or ""
        ).strip()

        if previous_name:
            name = previous_name

        previous_bias = str(
            previous.get("StructuralBias")
            or previous.get("structural_bias")
            or ""
        ).strip()

        previous_previous_bias = str(
            previous.get("PreviousBias")
            or previous.get("previous_bias")
            or ""
        ).strip()
        previous_change = str(
            previous.get("BiasChange")
            or previous.get("bias_change")
            or ""
        ).strip()

        v14_score = v14_scores.get(key, {
            "absolute_score": 0.0,
            "committee_center": 0.0,
            "structural_score": 0.0,
            "candidate": "Neutral",
        })
        structural_bias_candidate = v14_score["candidate"]
        evidence_insufficient = structural_bias_candidate == "INSUFFICIENT_EVIDENCE"
        candidate_for_resolution = (
            previous_bias
            if evidence_insufficient and previous_bias in VALID_BIASES
            else ("Neutral" if evidence_insufficient else structural_bias_candidate)
        )

        neutralization_allowed, neutralization_reason = _v14_neutralization_allowed(
            previous_bias,
            candidate_for_resolution,
            v14_score.get("sufficiency", ""),
            v14_score.get("structural_score", 0.0),
            v14_score.get("audited_item", item),
        )

        neutralization_blocked = (
            candidate_for_resolution == "Neutral"
            and previous_bias in VALID_BIASES
            and previous_bias != "Neutral"
            and not neutralization_allowed
        )

        if neutralization_blocked:
            candidate_for_resolution = previous_bias

        confidence = str(
            item.get("confidence")
            or "Low"
        ).strip()

        evidence_type = str(
            item.get("evidence_type")
            or "No new evidence"
        ).strip()

        latest_signal = str(
            item.get("latest_signal")
            or structural_bias_candidate
        ).strip()

        hysteresis_blocked = _hysteresis_blocks_reversal(
            previous_bias,
            previous_previous_bias,
            previous_change,
            candidate_for_resolution,
            confidence,
            evidence_type,
            recalibrate=RECALIBRATE_BIAS,
        )

        audited_item = v14_score.get("audited_item", item)

        transition_blocked, transition_reason = _v14_transition_guard(
            previous_bias,
            candidate_for_resolution,
            evidence_type,
            confidence,
            audited_item,
            recalibrate=RECALIBRATE_BIAS,
        )

        candidate_for_state = (
            previous_bias
            if transition_blocked and previous_bias in VALID_BIASES
            else candidate_for_resolution
        )

        structural_bias = _resolver_bias(
            previous_bias,
            candidate_for_state,
            latest_signal,
            confidence,
            evidence_type,
            previous_previous_bias=previous_previous_bias,
            previous_change=previous_change,
            recalibrate=RECALIBRATE_BIAS,
        )

        bias_change = _bias_change(
            previous_bias,
            structural_bias,
        )

        # Transparent audit trail: every voter shows stored bias, independent
        # candidate, latest signal, evidence strength and the Python decision.
        if previous_bias in VALID_BIASES:
            if structural_bias != previous_bias:
                decision = f"CHANGE -> {structural_bias}"
            elif evidence_insufficient:
                decision = f"INSUFFICIENT EVIDENCE · KEEP {structural_bias}"
            elif neutralization_blocked:
                decision = (
                    f"NEUTRALIZATION HOLD {structural_bias} "
                    f"({neutralization_reason})"
                )
            elif transition_blocked:
                decision = (
                    f"TRANSITION HOLD {structural_bias} "
                    f"({transition_reason})"
                )
            elif hysteresis_blocked:
                decision = f"HYSTERESIS HOLD {structural_bias}"
            else:
                decision = f"KEEP {structural_bias}"
        else:
            decision = f"INITIAL -> {structural_bias}"

        print(
            f"[{currency}][BIAS] {name} | "
            f"current={previous_bias or 'None'} | "
            f"evidence_score={v14_score['structural_score']:+.3f} "
            f"(raw={v14_score['absolute_score']:+.3f}, center={v14_score['committee_center']:+.3f}) | "
            f"components=V{v14_score.get('vote_score', 0)}/P{v14_score.get('path_score', 0)}/R{v14_score.get('risk_score', 0)} | "
            f"audit=V[{v14_score.get('vote_audit', '')}]"
            f"/P[{v14_score.get('path_audit', '')}]"
            f"/R[{v14_score.get('risk_audit', '')}] | "
            f"sufficiency={v14_score.get('sufficiency', 'n/a')} | "
            f"neutralization={neutralization_reason} | "
            f"guard={v14_score.get('guard', 'n/a')} | "
            f"candidate={structural_bias_candidate} | "
            f"latest={latest_signal} | "
            f"evidence={evidence_type} | "
            f"confidence={confidence} | "
            f"decision={decision}"
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
            "LatestSignal": latest_signal,
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

        if previous_index and key not in previous_index:
            if currency == "EUR":
                current_meeting = _clean_date(
                    committee.get("next_meeting_date")
                )
                if (
                    previous_meeting
                    and current_meeting
                    and previous_meeting != current_meeting
                ):
                    change_type = "VotingRotationAdded"
                else:
                    change_type = "VotingRosterCorrectionAdded"
            else:
                change_type = "VotingMemberAdded"

            changes.append({
                "Currency": currency,
                "Member": name,
                "ChangeType": change_type,
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

    # Miembros que estaban guardados y ya no aparecen entre los votantes.
    # Si no existe snapshot previo, esta ejecución se considera inicialización
    # y no se generan falsos cambios de composición.
    for key, previous in previous_index.items():
        if key in current_keys:
            continue

        old_name = str(
            previous.get("Member")
            or previous.get("name")
            or ""
        ).strip()

        if currency == "EUR":
            current_meeting = _clean_date(
                committee.get("next_meeting_date")
            )
            if (
                previous_meeting
                and current_meeting
                and previous_meeting != current_meeting
            ):
                change_type = "VotingRotationRemoved"
            else:
                change_type = "VotingRosterCorrectionRemoved"
        else:
            change_type = "VotingMemberRemoved"

        changes.append({
            "Currency": currency,
            "Member": old_name,
            "ChangeType": change_type,
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

    previous_members, previous_state_ok = (
        cargar_estado_previo_miembros(
            currency
        )
    )

    # La búsqueda de declaraciones puede seguir ejecutándose aunque falle la
    # lectura del snapshot. Sin embargo, la composición/bias NO se persistirá
    # en ese caso: el estado histórico existente en Sheets es más seguro.
    resultado_texto = (
        buscar_bancos_centrales_ia(
            currency,
            previous_members if previous_state_ok else [],
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

    resultado_drivers = (
        guardar_central_bank_drivers(
            eventos
        )
    )

    committee_skipped = not previous_state_ok

    if committee_skipped:
        # CRITICAL FAILSAFE:
        # Si no conocemos el estado anterior, no calculamos ni guardamos un nuevo
        # snapshot. Así `current=None` nunca puede convertirse en INITIAL por un
        # fallo temporal de Apps Script.
        members = []
        changes = []
        resultado_members = {
            "ok": True,
            "skipped": True,
            "reason": "previous_snapshot_unavailable",
        }
        print(
            f"[{currency}] COMMITTEE SKIPPED · snapshot previo no disponible; "
            "se conserva el estado existente en Sheets."
        )
    else:
        members, changes = (
            preparar_central_bank_members(
                currency,
                data,
                previous_members,
            )
        )

        try:
            if V14_DRY_RUN:
                resultado_members = {
                    "ok": True,
                    "skipped": True,
                    "reason": "v14_3_2_neutralization_guard_dry_run",
                }
                print(
                    f"[{currency}] V14.3.2 DRY RUN · committee NOT saved to Sheets · "
                    f"{len(members)} voters · {len(changes)} proposed changes"
                )
            else:
                resultado_members = (
                    guardar_central_bank_members(
                        currency,
                        members,
                        changes,
                    )
                )
        except Exception as error:
            # Guardar el comité es una sustitución del snapshot. Si falla, el
            # snapshot anterior permanece intacto. Registramos el fallo como skip
            # seguro para no convertir un problema transitorio en corrupción de datos.
            committee_skipped = True
            print(
                f"[{currency}] COMMITTEE SAVE FAILED · {error}"
            )
            print(
                f"[{currency}] FAILSAFE · se conserva el snapshot anterior en Sheets."
            )
            resultado_members = {
                "ok": False,
                "skipped": True,
                "reason": "committee_save_failed",
                "error": str(error),
            }

    return {
        "currency": currency,
        "events_found": len(eventos),
        "members_found": len(members),
        "changes_found": len(changes),
        "committee_skipped": committee_skipped,
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
                    + (" · COMMITTEE SKIPPED" if resultado.get("committee_skipped") else "")
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
        "=== CENTRAL BANK DRIVERS + MEMBERS UPDATE · V14.3.2 NEUTRALIZATION GUARD ==="
    )
    print(
        f"RECALIBRATE_BIAS={RECALIBRATE_BIAS}"
    )
    print(
        f"V14_DRY_RUN={V14_DRY_RUN}"
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
