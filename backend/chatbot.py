"""Deterministic conversation controller for ASCE 7-16 wind inputs.

This module owns conversation flow and validation. It does not call any LLM and
does not perform wind-load arithmetic itself; confirmed inputs are delegated to
the calculation engine.
"""

from __future__ import annotations

import json
import os
import re
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.config import load_dotenv_if_present
from backend.models import CalculationRequest, LLMIntentResponse, LLMStructuredResponse
from backend.session import get_session, store_calculation_result, update_session
from backend.wind_load_engine import run_wind_load_calculation


load_dotenv_if_present()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
LAST_LLM_FAILURE_REASON: str | None = None
REQUEST_LLM_ENABLED: ContextVar[bool | None] = ContextVar("REQUEST_LLM_ENABLED", default=None)

with (DATA_DIR / "conversation_flow.json").open(encoding="utf-8") as flow_file:
    CONVERSATION_FLOW = json.load(flow_file)

with (DATA_DIR / "risk_category.json").open(encoding="utf-8") as risk_file:
    RISK_CATEGORY_DATA = json.load(risk_file)

with (DATA_DIR / "ma_780_cmr_table_1604_11.json").open(encoding="utf-8") as ma_wind_file:
    MA_WIND_DATA = json.load(ma_wind_file)


QUESTION_PHASES = {
    "Q1": 1,
    "Q2": 1,
    "Q3": 1,
    "Q4": 1,
    "Q5": 2,
    "MANUAL_WIND_SPEED": 2,
    "Q6": 3,
    "Q7": 4,
    "Q7a": 4,
    "Q7b": 4,
    "Q7c": 4,
    "Q7d": 4,
    "Q8": 5,
    "Q9": 5,
    "Q10": 5,
    "Q11": 5,
    "Q12": 5,
    "Q13": 5,
    "Q14": 6,
    "Q15": 6,
    "CONFIRM": 7,
    "COMPLETE": 7,
}

WIND_SPEED_LOOKUP_AVAILABLE = False
MA_WIND_SPEED_LOOKUP_AVAILABLE = True

RISK_CATEGORY_WIND_KEYS = {
    "I": "risk_category_i",
    "II": "risk_category_ii",
    "III": "risk_category_iii",
    "IV": "risk_category_iv",
}

STATE_NAMES_BY_ABBR = {
    "AL": "alabama",
    "AK": "alaska",
    "AZ": "arizona",
    "AR": "arkansas",
    "CA": "california",
    "CO": "colorado",
    "CT": "connecticut",
    "DE": "delaware",
    "FL": "florida",
    "GA": "georgia",
    "HI": "hawaii",
    "ID": "idaho",
    "IL": "illinois",
    "IA": "iowa",
    "KS": "kansas",
    "KY": "kentucky",
    "LA": "louisiana",
    "ME": "maine",
    "MD": "maryland",
    "MA": "massachusetts",
    "MI": "michigan",
    "MN": "minnesota",
    "MS": "mississippi",
    "MO": "missouri",
    "MT": "montana",
    "NE": "nebraska",
    "NV": "nevada",
    "NH": "new hampshire",
    "NJ": "new jersey",
    "NM": "new mexico",
    "NY": "new york",
    "NC": "north carolina",
    "ND": "north dakota",
    "OH": "ohio",
    "OK": "oklahoma",
    "PA": "pennsylvania",
    "RI": "rhode island",
    "SC": "south carolina",
    "SD": "south dakota",
    "TN": "tennessee",
    "TX": "texas",
    "UT": "utah",
    "VT": "vermont",
    "VA": "virginia",
    "WA": "washington",
    "WV": "west virginia",
    "WI": "wisconsin",
    "WY": "wyoming",
    "DC": "district of columbia",
}


def _normalize_location_token(text: str) -> str:
    normalized = text.lower().replace("&", " and ")
    normalized = re.sub(r"\bmt\b\.?", "mount", normalized)
    normalized = re.sub(r"\bw\b\.?", "west", normalized)
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)
    return " ".join(normalized.split())


MA_WIND_RECORDS_BY_KEY: dict[str, dict[str, Any]] = {}
for record in MA_WIND_DATA["records"]:
    city_town = record["city_town"]
    aliases = {city_town}
    if "(" in city_town and ")" in city_town:
        aliases.add(re.sub(r"\s*\([^)]*\)", "", city_town))
        aliases.update(re.findall(r"\(([^)]*)\)", city_town))
    if city_town.startswith("W. "):
        aliases.add("West " + city_town[3:])
    if city_town.startswith("Mount "):
        aliases.add("Mt " + city_town[6:])
    for alias in aliases:
        MA_WIND_RECORDS_BY_KEY[_normalize_location_token(alias)] = record


QUESTIONS = {
    "Q1": "What is the primary use of this building? For example: office, warehouse, retail, school, hospital, or residential.",
    "Q2": "Approximately how many people occupy the building at peak times?",
    "Q3": "Is this building designated as essential for post-disaster response, such as a hospital, fire station, or emergency operations center?",
    "Q4": "Does the building store or handle hazardous materials that could pose a public risk if released?",
    "Q5": "What city and state is the project located in? A zip code also works.",
    "MANUAL_WIND_SPEED": "I cannot automatically determine wind speed yet because the lookup table is not ready. Please enter the ASCE 7-16 basic wind speed in mph for this site.",
    "Q6": "How would you describe the terrain? Choose B for dense urban, suburban, wooded, or closely spaced obstructions; C for open terrain with scattered obstructions; or D for flat unobstructed terrain near a large body of water.",
    "Q7": "Is the building located on or near a hill, ridge, or escarpment?",
    "Q7a": "What type of topographic feature is it: 2D ridge, 2D escarpment, or 3D hill?",
    "Q7b": "What is the height H of the topographic feature in feet?",
    "Q7c": "What is Lh in feet, the horizontal distance from the crest to the upwind half-height point?",
    "Q7d": "What is x in feet, the horizontal distance from the crest to the building site?",
    "Q8": "What is the mean roof height h of the building in feet?",
    "Q9": "What is the building length L in feet, parallel to the wind direction being analyzed?",
    "Q10": "What is the building width B in feet, perpendicular to the wind direction?",
    "Q11": "What type of roof does the building have: flat, gable, hip, or monoslope?",
    "Q12": "What is the roof slope in degrees?",
    "Q13": "Relative to the wind direction, is the wind normal to the ridge or parallel to the ridge?",
    "Q14": "What are you designing for: MWFRS, C&C, or both?",
    "Q15": "Which design standard are you using: LRFD or ASD?",
}

FIELD_LABELS = {
    "risk_category": "Risk Category",
    "basic_wind_speed_V": "Basic Wind Speed (V)",
    "exposure_category": "Exposure Category",
    "Kzt": "Topographic Factor Kzt",
    "mean_roof_height_h": "Mean Roof Height (h)",
    "building_length_L": "Building Length (L)",
    "building_width_B": "Building Width (B)",
    "h_over_L": "h/L ratio",
    "L_over_B": "L/B ratio",
    "roof_type": "Roof Type",
    "roof_slope_deg": "Roof Slope",
    "ridge_orientation": "Ridge Orientation",
    "analysis_type": "Analysis Type",
    "design_standard": "Design Standard",
}

QUESTION_GUIDANCE = {
    "Q1": {
        "field": "occupancy_description",
        "help": "I need the primary occupancy so the backend can derive the ASCE 7 Risk Category. A short description like office, warehouse, school, hospital, retail, or residential is enough.",
    },
    "Q2": {
        "field": "occupant_load",
        "help": "I need an approximate peak occupant count because some occupancies move into a higher Risk Category above ASCE occupant thresholds. A best estimate is fine for this preliminary workflow.",
    },
    "Q3": {
        "field": "essential_post_disaster",
        "help": "Answer yes only if the facility is intended to remain operational after a disaster, such as a hospital, fire station, police station, or emergency operations center.",
    },
    "Q4": {
        "field": "hazardous_materials",
        "help": "Answer yes if the building stores or handles hazardous materials where release could pose a substantial public risk. Ordinary cleaning supplies or small incidental quantities usually do not count.",
    },
    "Q5": {
        "field": "location",
        "help": "I need the project city and state so the backend can look up or request the correct ASCE basic wind speed. For Massachusetts, a city or town name like Boston, MA is enough.",
    },
    "MANUAL_WIND_SPEED": {
        "field": "basic_wind_speed_V",
        "help": "The automatic lookup did not resolve this location, so I need the ASCE 7-16 basic wind speed in mph from the applicable wind speed figure.",
    },
    "Q6": {
        "field": "exposure_category",
        "help": "Exposure is based on surrounding surface roughness. B is dense urban, suburban, wooded, or closely obstructed terrain. C is open terrain with scattered obstructions. D is flat unobstructed terrain exposed to wind over a large body of water.",
    },
    "Q7": {
        "field": "topographic_feature_present",
        "help": "This is separate from exposure category. I am checking whether a hill, ridge, or escarpment could accelerate wind over the site. Most flat city parcels can answer no.",
    },
    "Q7a": {
        "field": "topo_feature_type",
        "help": "Choose the closest ASCE topographic feature: 2D ridge, 2D escarpment, or 3D hill.",
    },
    "Q7b": {
        "field": "topo_H",
        "help": "H is the vertical height of the hill, ridge, or escarpment in feet.",
    },
    "Q7c": {
        "field": "topo_Lh",
        "help": "Lh is the horizontal distance from the crest to the upwind half-height point, in feet.",
    },
    "Q7d": {
        "field": "topo_x",
        "help": "x is the horizontal distance from the crest to the building site, in feet.",
    },
    "Q8": {
        "field": "mean_roof_height_h",
        "help": "Mean roof height is the average roof height above grade in feet. For a flat roof, use the roof height.",
    },
    "Q9": {
        "field": "building_length_L",
        "help": "Length L is the plan dimension parallel to the wind direction being analyzed, in feet.",
    },
    "Q10": {
        "field": "building_width_B",
        "help": "Width B is the plan dimension perpendicular to the wind direction being analyzed, in feet.",
    },
    "Q11": {
        "field": "roof_type",
        "help": "Choose the roof form used by the ASCE MWFRS coefficient tables: flat, gable, hip, or monoslope.",
    },
    "Q12": {
        "field": "roof_slope_deg",
        "help": "Roof slope should be entered in degrees. If you have rise over run, convert it to degrees before entering it.",
    },
    "Q13": {
        "field": "ridge_orientation",
        "help": "For gable and hip roofs, say whether the wind is normal to the ridge or parallel to the ridge.",
    },
    "Q14": {
        "field": "analysis_type",
        "help": "MWFRS is for the main wind-force resisting system. C&C is components and cladding. This demo primarily supports MWFRS.",
    },
    "Q15": {
        "field": "design_standard",
        "help": "Choose LRFD or ASD, matching the design basis you want reported.",
    },
}


class ChatbotError(ValueError):
    """Raised when a user answer cannot be parsed for the current question."""


class ChatbotReply(dict):
    """Dictionary reply that compares equal to its display text for legacy tests."""

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return self["display_text"] == other
        return super().__eq__(other)

    def __contains__(self, item: object) -> bool:
        if isinstance(item, str):
            return item in self["display_text"]
        return super().__contains__(item)


def start_prompt() -> str:
    return QUESTIONS["Q1"]


def _build_reply(
    deterministic_response: str,
    *,
    user_message: str,
    session_before: dict[str, Any],
    session_after: dict[str, Any],
    next_question_id: str,
) -> ChatbotReply:
    llm_response = _try_llm_response_generation(
        deterministic_response,
        user_message=user_message,
        session_before=session_before,
        session_after=session_after,
        next_question_id=next_question_id,
    )
    if llm_response is None:
        return ChatbotReply(
            response=deterministic_response,
            display_text=deterministic_response,
            spoken_text=_to_spoken_text(deterministic_response),
            llm_used=False,
            llm_fallback_reason=_llm_unavailable_reason(),
        )

    return ChatbotReply(
        response=llm_response.display_text,
        display_text=llm_response.display_text,
        spoken_text=llm_response.spoken_text,
        llm_used=True,
        llm_fallback_reason=None,
    )


def process_user_message(
    session_id: str,
    message: str,
    *,
    llm_enabled: bool | None = None,
) -> tuple[ChatbotReply, dict[str, Any]]:
    token = REQUEST_LLM_ENABLED.set(llm_enabled)
    try:
        return _process_user_message(session_id, message)
    finally:
        REQUEST_LLM_ENABLED.reset(token)


def _process_user_message(session_id: str, message: str) -> tuple[ChatbotReply, dict[str, Any]]:
    session = get_session(session_id)
    if session is None:
        raise KeyError(session_id)

    current_question_id = session.get("current_question_id") or "Q1"
    collected = dict(session.get("collected_inputs", {}))
    branch_flags = dict(session.get("branch_flags", {}))

    if current_question_id == "CONFIRM":
        response, next_question_id = _handle_confirmation(session_id, message, collected, branch_flags)
    elif current_question_id == "COMPLETE":
        response = "This session already has a completed calculation. Start a new session to run another building."
        next_question_id = "COMPLETE"
    else:
        pending = _handle_pending_or_intent(current_question_id, message, collected, branch_flags)
        if pending is not None:
            response, next_question_id = pending
        else:
            try:
                response, next_question_id = _handle_answer(current_question_id, message, collected, branch_flags)
            except ChatbotError as exc:
                interpreted = _try_llm_interpretation(current_question_id, message, collected, branch_flags, str(exc))
                if interpreted is not None:
                    response, next_question_id = interpreted
                else:
                    response = f"{exc} {QUESTIONS[current_question_id]}"
                    next_question_id = current_question_id

    updated = update_session(
        session_id,
        {
            "current_phase": QUESTION_PHASES[next_question_id],
            "current_question_id": next_question_id,
            "collected_inputs": collected,
            "branch_flags": branch_flags,
            "ready_to_calculate": next_question_id in {"CONFIRM", "COMPLETE"},
        },
    )
    if updated is None:
        raise KeyError(session_id)
    reply = _build_reply(
        response,
        user_message=message,
        session_before=session,
        session_after=updated,
        next_question_id=next_question_id,
    )
    return reply, updated


def _handle_answer(
    question_id: str,
    message: str,
    collected: dict[str, Any],
    branch_flags: dict[str, Any],
) -> tuple[str, str]:
    normalized = message.strip()

    if question_id == "Q1":
        collected["occupancy_description"] = normalized
        collected["occupancy_type"] = _map_occupancy(normalized)
        return _next_response("Q2"), "Q2"

    if question_id == "Q2":
        collected["occupant_load"] = _parse_int(normalized)
        return _next_response("Q3"), "Q3"

    if question_id == "Q3":
        collected["essential_post_disaster"] = _parse_bool(normalized)
        return _next_response("Q4"), "Q4"

    if question_id == "Q4":
        collected["hazardous_materials"] = _parse_bool(normalized)
        risk_category, figure = derive_risk_category(collected)
        collected["risk_category"] = risk_category
        collected["wind_speed_figure"] = figure
        lead = (
            f"Based on your answers, this building is Risk Category {risk_category} "
            f"per ASCE 7-16 Table 1.5-1, using wind speed Figure {figure}."
        )
        return f"{lead}\n\n{QUESTIONS['Q5']}", "Q5"

    if question_id == "Q5":
        collected["location"] = normalized
        lookup_result = _lookup_ma_wind_speed(normalized, collected)
        if lookup_result is not None:
            collected["basic_wind_speed_V"] = lookup_result["basic_wind_speed_V"]
            collected["basic_wind_speed_source"] = "780 CMR Table 1604.11"
            collected["resolved_municipality"] = lookup_result["municipality"]
            branch_flags["wind_speed_lookup_available"] = True
            branch_flags["wind_speed_lookup_failed"] = False
            branch_flags["wind_speed_lookup_source"] = "780 CMR Table 1604.11"
            response = _ma_wind_speed_confirmation(lookup_result)
            return f"{response}\n\n{QUESTIONS['Q6']}", "Q6"

        branch_flags["wind_speed_lookup_available"] = WIND_SPEED_LOOKUP_AVAILABLE
        branch_flags["wind_speed_lookup_failed"] = True
        branch_flags["wind_speed_lookup_source"] = None
        return _manual_wind_speed_prompt(collected), "MANUAL_WIND_SPEED"

    if question_id == "MANUAL_WIND_SPEED":
        collected["basic_wind_speed_V"] = _parse_positive_float(normalized)
        collected["basic_wind_speed_source"] = "manual_user_entry"
        return _next_response("Q6"), "Q6"

    if question_id == "Q6":
        collected["exposure_category"] = _parse_exposure(normalized)
        return _next_response("Q7"), "Q7"

    if question_id == "Q7":
        present = _parse_bool(normalized)
        branch_flags["topographic_feature_present"] = present
        collected["topographic_feature_present"] = present
        if not present:
            collected["Kzt"] = 1.0
            return "No topographic feature noted, so Kzt defaults to 1.0.\n\n" + QUESTIONS["Q8"], "Q8"
        return _next_response("Q7a"), "Q7a"

    if question_id == "Q7a":
        collected["topo_feature_type"] = _parse_topo_feature(normalized)
        return _next_response("Q7b"), "Q7b"

    if question_id == "Q7b":
        collected["topo_H"] = _parse_positive_float(normalized)
        return _next_response("Q7c"), "Q7c"

    if question_id == "Q7c":
        collected["topo_Lh"] = _parse_positive_float(normalized)
        return _next_response("Q7d"), "Q7d"

    if question_id == "Q7d":
        collected["topo_x"] = _parse_float(normalized)
        collected["Kzt"] = "calculated by engine from topographic inputs"
        return _next_response("Q8"), "Q8"

    if question_id == "Q8":
        collected["mean_roof_height_h"] = _parse_positive_float(normalized)
        _update_geometry_ratios(collected)
        return _next_response("Q9"), "Q9"

    if question_id == "Q9":
        collected["building_length_L"] = _parse_positive_float(normalized)
        _update_geometry_ratios(collected)
        return _next_response("Q10"), "Q10"

    if question_id == "Q10":
        collected["building_width_B"] = _parse_positive_float(normalized)
        _update_geometry_ratios(collected)
        return _next_response("Q11"), "Q11"

    if question_id == "Q11":
        roof_type = _parse_roof_type(normalized)
        collected["roof_type"] = roof_type
        if roof_type == "flat":
            collected["roof_slope_deg"] = 0.0
            collected["ridge_orientation"] = None
            return _next_response("Q14"), "Q14"
        return _next_response("Q12"), "Q12"

    if question_id == "Q12":
        collected["roof_slope_deg"] = _parse_float(normalized)
        if collected.get("roof_type") == "monoslope":
            collected["ridge_orientation"] = None
            return _next_response("Q14"), "Q14"
        return _next_response("Q13"), "Q13"

    if question_id == "Q13":
        collected["ridge_orientation"] = _parse_ridge_orientation(normalized)
        return _next_response("Q14"), "Q14"

    if question_id == "Q14":
        collected["analysis_type"] = _parse_analysis_type(normalized)
        return _next_response("Q15"), "Q15"

    if question_id == "Q15":
        collected["design_standard"] = _parse_design_standard(normalized)
        return _summary_response(collected), "CONFIRM"

    raise ChatbotError("I do not know which question to ask next.")


def _handle_confirmation(
    session_id: str,
    message: str,
    collected: dict[str, Any],
    branch_flags: dict[str, Any],
) -> tuple[str, str]:
    if _is_confirm(message):
        request = CalculationRequest(**_engine_payload(collected))
        results = run_wind_load_calculation(request.to_engine_input())
        store_calculation_result(session_id, request.model_dump(mode="json"), results)
        collected.update(request.model_dump(mode="json"))
        return _calculation_response(results), "COMPLETE"

    if _apply_correction(message, collected, branch_flags):
        return _summary_response(collected), "CONFIRM"

    return (
        "I did not catch whether you want to confirm or correct an input. "
        "Reply yes to calculate, or say something like 'change roof slope to 25 degrees'.",
        "CONFIRM",
    )


def _handle_pending_or_intent(
    question_id: str,
    message: str,
    collected: dict[str, Any],
    branch_flags: dict[str, Any],
) -> tuple[str, str] | None:
    normalized = message.strip()
    pending = branch_flags.get("pending_answer")
    if isinstance(pending, dict) and pending.get("question_id") == question_id:
        if _is_confirm(normalized):
            candidate = str(pending.get("candidate_answer", ""))
            branch_flags.pop("pending_answer", None)
            return _handle_answer(question_id, candidate, collected, branch_flags)
        if _is_reject(normalized):
            branch_flags.pop("pending_answer", None)
            return f"No problem. {QUESTIONS[question_id]}", question_id

    if not _looks_like_non_answer(normalized):
        return None

    intent = _try_llm_intent_classification(question_id, normalized, collected, branch_flags)
    if intent is not None:
        handled = _handle_intent_response(question_id, intent, collected, branch_flags)
        if handled is not None:
            return handled

    return _deterministic_help_response(question_id, normalized, branch_flags), question_id


def _looks_like_non_answer(text: str) -> bool:
    lowered = text.lower().strip()
    if not lowered:
        return False
    if "?" in lowered and len(lowered) > 2:
        return True
    return lowered.startswith(
        (
            "help",
            "why",
            "what would",
            "what should",
            "which",
            "should i",
            "would you",
            "how do",
            "how would",
            "can you",
            "do you",
            "i don't know",
            "i dont know",
            "not sure",
            "unsure",
            "i am not sure",
            "i'm not sure",
            "i thought",
        )
    )


def _try_llm_intent_classification(
    question_id: str,
    message: str,
    collected: dict[str, Any],
    branch_flags: dict[str, Any],
) -> LLMIntentResponse | None:
    if not _llm_enabled():
        return None

    guidance = QUESTION_GUIDANCE.get(question_id, {})
    prompt = {
        "task": "classify_user_intent_for_active_question",
        "hard_rules": [
            "Do not perform wind load calculations.",
            "Do not choose ASCE coefficients or compute pressures.",
            "Classify whether the user is answering, asking for help, asking for a recommendation, asking a clarification, correcting a previous value, or off topic.",
            "Set should_advance true only when the user clearly intended to answer the active question.",
            "For recommendation_request or uncertainty, provide candidate_answer when reasonable but set should_advance false so the backend can ask for confirmation.",
            "Return only valid JSON matching the requested shape.",
        ],
        "current_question_id": question_id,
        "question_text": QUESTIONS.get(question_id),
        "expected_field": guidance.get("field"),
        "field_guidance": guidance.get("help"),
        "user_message": message,
        "collected_inputs": collected,
        "branch_flags": branch_flags,
        "required_json_shape": {
            "intent": "direct_answer | help_request | recommendation_request | clarification_question | correction | off_topic",
            "candidate_answer": "string or null",
            "should_advance": False,
            "confidence": 0.0,
            "display_text": "string",
            "spoken_text": "string",
        },
    }
    try:
        raw = _call_anthropic_json(prompt)
        return LLMIntentResponse.model_validate(raw)
    except Exception as exc:
        global LAST_LLM_FAILURE_REASON
        LAST_LLM_FAILURE_REASON = f"{type(exc).__name__}: " + _safe_error_text(exc)
        return None


def _handle_intent_response(
    question_id: str,
    intent: LLMIntentResponse,
    collected: dict[str, Any],
    branch_flags: dict[str, Any],
) -> tuple[str, str] | None:
    if intent.intent == "direct_answer" and intent.should_advance and intent.candidate_answer:
        try:
            return _handle_answer(question_id, intent.candidate_answer, collected, branch_flags)
        except ChatbotError:
            return None

    if intent.intent in {"help_request", "recommendation_request", "clarification_question", "off_topic"}:
        response = intent.display_text.strip() or _deterministic_help_response(question_id, "", branch_flags)
        if (
            intent.intent == "recommendation_request"
            and intent.candidate_answer
            and intent.confidence >= 0.5
            and _candidate_valid_for_question(question_id, intent.candidate_answer, collected, branch_flags)
        ):
            branch_flags["pending_answer"] = {
                "question_id": question_id,
                "field": QUESTION_GUIDANCE.get(question_id, {}).get("field"),
                "candidate_answer": str(intent.candidate_answer),
            }
            if not _asks_for_confirmation(response):
                response = f"{response}\n\nShould I use {intent.candidate_answer} for this field?"
        return response, question_id

    return None


def _candidate_valid_for_question(
    question_id: str,
    candidate_answer: str,
    collected: dict[str, Any],
    branch_flags: dict[str, Any],
) -> bool:
    collected_copy = dict(collected)
    branch_copy = dict(branch_flags)
    try:
        _handle_answer(question_id, str(candidate_answer), collected_copy, branch_copy)
    except ChatbotError:
        return False
    return True


def _deterministic_help_response(
    question_id: str,
    message: str,
    branch_flags: dict[str, Any],
) -> str:
    if question_id == "Q6" and _mentions_city_or_urban(message):
        branch_flags["pending_answer"] = {
            "question_id": "Q6",
            "field": "exposure_category",
            "candidate_answer": "B",
        }
        return (
            "For a typical dense city site, Exposure B is usually the right starting point because it covers urban, suburban, wooded, or closely obstructed terrain.\n\n"
            "If the site is unusually open, Exposure C may be more appropriate. Exposure D is for flat, unobstructed terrain exposed to wind over a large body of water.\n\n"
            "Should I use Exposure B for this site?"
        )

    guidance = QUESTION_GUIDANCE.get(question_id, {})
    help_text = guidance.get("help", "I can help clarify this input before storing it.")
    return f"{help_text}\n\n{QUESTIONS[question_id]}"


def _mentions_city_or_urban(text: str) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in ("city", "urban", "downtown", "boston"))


def _asks_for_confirmation(text: str) -> bool:
    lowered = text.lower()
    return "should i use" in lowered or "do you want me to use" in lowered or "confirm" in lowered


def _is_reject(text: str) -> bool:
    lowered = text.lower().strip()
    return lowered in {"no", "n", "nope", "not quite", "incorrect", "don't use that", "dont use that"}


def _try_llm_interpretation(
    question_id: str,
    message: str,
    collected: dict[str, Any],
    branch_flags: dict[str, Any],
    parse_error: str,
) -> tuple[str, str] | None:
    if not _llm_enabled():
        return None

    expected_field = _expected_field_for_question(question_id)
    prompt = {
        "task": "interpret_user_answer",
        "hard_rules": [
            "Do not perform wind load calculations.",
            "Do not select ASCE coefficients or engineering values.",
            "Return only a candidate field_update for the current expected field.",
            "The backend will validate any candidate before use.",
        ],
        "current_question_id": question_id,
        "expected_field": expected_field,
        "question_text": QUESTIONS.get(question_id),
        "user_message": message,
        "parse_error": parse_error,
        "collected_inputs": collected,
        "required_json_shape": {
            "display_text": "string",
            "spoken_text": "string",
            "field_update": {expected_field or "field_name": "candidate value"},
            "needs_clarification": False,
            "clarification_text": None,
        },
    }
    llm_response = _call_llm_for_structured_response(prompt)
    if llm_response is None:
        return None

    if expected_field and expected_field in llm_response.field_update:
        candidate = llm_response.field_update[expected_field]
        try:
            return _handle_answer(question_id, str(candidate), collected, branch_flags)
        except ChatbotError:
            return None

    if llm_response.needs_clarification and llm_response.clarification_text:
        return llm_response.clarification_text, question_id

    return None


def _try_llm_response_generation(
    deterministic_response: str,
    *,
    user_message: str,
    session_before: dict[str, Any],
    session_after: dict[str, Any],
    next_question_id: str,
) -> LLMStructuredResponse | None:
    if not _llm_enabled():
        return None

    prompt = {
        "task": "polish_deterministic_chatbot_response",
        "hard_rules": [
            "Do not perform wind load calculations.",
            "Do not select ASCE coefficients or engineering values.",
            "Do not change phase progression or ask a different next question.",
            "Preserve any code, table, ASCE, 780 CMR, value, warning, or fallback content from deterministic_response.",
            "Return field_update as an empty object for this task.",
        ],
        "user_message": user_message,
        "previous_question_id": session_before.get("current_question_id"),
        "next_question_id": next_question_id,
        "current_phase": session_after.get("current_phase"),
        "deterministic_response": deterministic_response,
        "collected_inputs": session_after.get("collected_inputs", {}),
        "required_json_shape": {
            "display_text": "string",
            "spoken_text": "string",
            "field_update": {},
            "needs_clarification": False,
            "clarification_text": None,
        },
    }
    llm_response = _call_llm_for_structured_response(prompt)
    if llm_response is None:
        return None
    if not llm_response.display_text.strip() or not llm_response.spoken_text.strip():
        return None
    if llm_response.needs_clarification:
        return None
    return llm_response


def _call_llm_for_structured_response(payload: dict[str, Any]) -> LLMStructuredResponse | None:
    global LAST_LLM_FAILURE_REASON
    LAST_LLM_FAILURE_REASON = None
    try:
        raw = _call_anthropic_json(payload)
        return LLMStructuredResponse.model_validate(raw)
    except ValidationError as exc:
        LAST_LLM_FAILURE_REASON = "invalid_llm_response_schema: " + _safe_error_text(exc)
    except json.JSONDecodeError as exc:
        LAST_LLM_FAILURE_REASON = "invalid_llm_json: " + _safe_error_text(exc)
    except Exception as exc:
        LAST_LLM_FAILURE_REASON = f"{type(exc).__name__}: " + _safe_error_text(exc)
    return None


def _safe_error_text(exc: Exception) -> str:
    text = str(exc).replace("\n", " ")
    text = re.sub(r"sk-ant-[A-Za-z0-9_-]+", "[redacted-anthropic-key]", text)
    text = re.sub(r"sk-proj-[A-Za-z0-9_-]+", "[redacted-openai-key]", text)
    text = re.sub(r"sk-[A-Za-z0-9_-]+", "[redacted-key]", text)
    return text[:240]


def _call_anthropic_json(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        from anthropic import Anthropic
    except ImportError as exc:
        raise ImportError("anthropic package is not installed") from exc

    timeout = float(os.getenv("ANTHROPIC_TIMEOUT_SECONDS", "10"))
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], timeout=timeout)
    message = client.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        max_tokens=800,
        temperature=0,
        system=(
            "You are a controlled assistant layer for an ASCE 7-16 wind-load chatbot. "
            "The deterministic backend owns all flow control, validation, lookups, and calculations. "
            "Return only valid JSON matching the requested shape. Never calculate wind loads, never choose ASCE coefficients, "
            "and never invent engineering values."
        ),
        messages=[
            {
                "role": "user",
                "content": json.dumps(payload, sort_keys=True),
            }
        ],
    )
    text = _anthropic_message_text(message)
    return json.loads(_extract_json_object(text))


def _anthropic_message_text(message: Any) -> str:
    parts: list[str] = []
    for block in getattr(message, "content", []):
        text = getattr(block, "text", None)
        if text is None and isinstance(block, dict):
            text = block.get("text")
        if text:
            parts.append(text)
    if parts:
        return "\n".join(parts)
    text = getattr(message, "text", None)
    if isinstance(text, str):
        return text
    raise ValueError("Anthropic response did not contain text content.")


def _extract_json_object(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    if stripped.startswith("{") and stripped.endswith("}"):
        return stripped
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM response did not contain a JSON object.")
    return stripped[start : end + 1]


def _llm_enabled() -> bool:
    request_override = REQUEST_LLM_ENABLED.get()
    if request_override is not None:
        return request_override and bool(os.getenv("ANTHROPIC_API_KEY"))
    enabled = os.getenv("LLM_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
    return enabled and bool(os.getenv("ANTHROPIC_API_KEY"))


def llm_status() -> dict[str, Any]:
    enabled_value = os.getenv("LLM_ENABLED", "false")
    key_present = bool(os.getenv("ANTHROPIC_API_KEY"))
    env_enabled = enabled_value.lower() in {"1", "true", "yes", "on"}
    return {
        "enabled": env_enabled,
        "api_key_present": key_present,
        "request_toggle_available": key_present,
        "configured": _llm_enabled(),
        "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        "timeout_seconds": float(os.getenv("ANTHROPIC_TIMEOUT_SECONDS", "10")),
    }


def _llm_unavailable_reason() -> str | None:
    request_override = REQUEST_LLM_ENABLED.get()
    if request_override is False:
        return "disabled_by_request"
    if request_override is True and not os.getenv("ANTHROPIC_API_KEY"):
        return "missing_api_key"
    if request_override is True:
        return LAST_LLM_FAILURE_REASON or "invalid_or_failed_response"
    if os.getenv("LLM_ENABLED", "false").lower() not in {"1", "true", "yes", "on"}:
        return "disabled"
    if not os.getenv("ANTHROPIC_API_KEY"):
        return "missing_api_key"
    return LAST_LLM_FAILURE_REASON or "invalid_or_failed_response"


def _expected_field_for_question(question_id: str) -> str | None:
    return {
        "Q1": "occupancy_description",
        "Q2": "occupant_load",
        "Q3": "essential_post_disaster",
        "Q4": "hazardous_materials",
        "Q5": "location",
        "MANUAL_WIND_SPEED": "basic_wind_speed_V",
        "Q6": "exposure_category",
        "Q7": "topographic_feature_present",
        "Q7a": "topo_feature_type",
        "Q7b": "topo_H",
        "Q7c": "topo_Lh",
        "Q7d": "topo_x",
        "Q8": "mean_roof_height_h",
        "Q9": "building_length_L",
        "Q10": "building_width_B",
        "Q11": "roof_type",
        "Q12": "roof_slope_deg",
        "Q13": "ridge_orientation",
        "Q14": "analysis_type",
        "Q15": "design_standard",
    }.get(question_id)


def _to_spoken_text(display_text: str) -> str:
    spoken = re.sub(r"`([^`]*)`", r"\1", display_text)
    spoken = re.sub(r"[*_#>-]", "", spoken)
    spoken = re.sub(r"\n+", " ", spoken)
    return " ".join(spoken.split())


def _next_response(next_question_id: str) -> str:
    return QUESTIONS[next_question_id]


def _lookup_ma_wind_speed(location_text: str, collected: dict[str, Any]) -> dict[str, Any] | None:
    if not MA_WIND_SPEED_LOOKUP_AVAILABLE or _has_non_ma_state_hint(location_text):
        return None

    municipality_key = _extract_ma_municipality_key(location_text)
    if municipality_key is None:
        return None

    record = MA_WIND_RECORDS_BY_KEY.get(municipality_key)
    if record is None:
        return None

    risk_category = collected.get("risk_category")
    wind_key = RISK_CATEGORY_WIND_KEYS.get(risk_category)
    if wind_key is None:
        return None

    wind_speed = record.get("basic_wind_speed_v_mph", {}).get(wind_key)
    if wind_speed is None:
        return None

    return {
        "municipality": record["city_town"],
        "risk_category": risk_category,
        "basic_wind_speed_V": float(wind_speed),
        "note_refs": record.get("note_refs", []),
    }


def _extract_ma_municipality_key(location_text: str) -> str | None:
    text_without_zip = re.sub(r"\b\d{5}(?:-\d{4})?\b", " ", location_text)
    normalized = _normalize_location_token(text_without_zip)
    if not normalized:
        return None

    state_tokens = {"ma", "mass", "massachusetts"}
    tokens = [token for token in normalized.split() if token not in state_tokens]
    if not tokens:
        return None

    candidates = {
        " ".join(tokens),
        _normalize_location_token(re.split(r",", text_without_zip, maxsplit=1)[0]),
    }
    candidates.discard("")
    matches = [candidate for candidate in candidates if candidate in MA_WIND_RECORDS_BY_KEY]
    if len(matches) == 1:
        return matches[0]
    return None


def _has_non_ma_state_hint(location_text: str) -> bool:
    lowered = location_text.lower()
    for abbr, name in STATE_NAMES_BY_ABBR.items():
        if abbr == "MA":
            continue
        if name in lowered:
            return True
        # Keep abbreviation matching conservative so ordinary words like "in" or "or"
        # are not mistaken for state hints.
        if re.search(rf"(?:,\s*|\s+){re.escape(abbr.lower())}\.?\s*$", lowered):
            return True
    return False


def _ma_wind_speed_confirmation(lookup_result: dict[str, Any]) -> str:
    municipality = lookup_result["municipality"]
    wind_speed = lookup_result["basic_wind_speed_V"]
    risk_category = lookup_result["risk_category"]
    lines = [
        f"I found {municipality}, Massachusetts in 780 CMR Table 1604.11.",
        f"For Risk Category {risk_category}, the basic wind speed V is {wind_speed:g} mph per 780 CMR Table 1604.11.",
    ]
    if 2 in lookup_result.get("note_refs", []):
        lines.append(
            "Note: this municipality has table note ref 2, so Special Wind Region or local-condition review may apply; the AHJ or ASCE hazard data may require a higher value."
        )
    return "\n".join(lines)


def _manual_wind_speed_prompt(collected: dict[str, Any]) -> str:
    figure = collected.get("wind_speed_figure", "the applicable ASCE 7-16 wind speed figure")
    return (
        "I was not able to automatically determine the wind speed for this location. "
        "Massachusetts municipalities can be looked up from 780 CMR Table 1604.11, but this input did not resolve to a supported Massachusetts city or town. "
        "Please look up the basic wind speed "
        f"using ASCE 7-16 Figure {figure} and enter the value in mph."
    )


def _summary_response(collected: dict[str, Any]) -> str:
    lines = [
        "Before I run the calculations, please review the collected inputs.",
        "",
    ]
    for field, label in FIELD_LABELS.items():
        if field in {"h_over_L", "L_over_B"}:
            _update_geometry_ratios(collected)
        if field not in collected:
            continue
        value = collected[field]
        if value is None and field == "ridge_orientation":
            continue
        lines.append(f"- {label}: {value}")
    lines.extend(
        [
            "- Ke (default): 1.0",
            "- Kd (hardcoded): 0.85",
            "- G (rigid, hardcoded): 0.85",
            "- GCpi (enclosed): +/-0.18",
            "",
            "Does everything look correct? Reply yes to run the calculation, or tell me what to correct.",
        ]
    )
    return "\n".join(lines)


def _calculation_response(results: dict[str, Any]) -> str:
    summary = results["summary"]
    return (
        "Calculation complete using the deterministic ASCE 7-16 engine.\n\n"
        f"- qh: {summary['qh_psf']} psf\n"
        f"- Kh: {summary['Kh']}\n"
        f"- Kzt: {summary['Kzt']}\n\n"
        "Full wall and roof pressure results are stored in this session's last_calculation field."
    )


def _engine_payload(collected: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "risk_category": collected["risk_category"],
        "basic_wind_speed_V": collected["basic_wind_speed_V"],
        "exposure_category": collected["exposure_category"],
        "mean_roof_height_h": collected["mean_roof_height_h"],
        "building_length_L": collected["building_length_L"],
        "building_width_B": collected["building_width_B"],
        "roof_type": collected["roof_type"],
        "roof_slope_deg": collected.get("roof_slope_deg", 0.0),
        "ridge_orientation": collected.get("ridge_orientation"),
        "analysis_type": collected.get("analysis_type", "MWFRS"),
        "design_standard": collected.get("design_standard", "LRFD"),
    }
    if collected.get("topographic_feature_present"):
        payload["topo_inputs"] = {
            "feature_type": collected["topo_feature_type"],
            "H": collected["topo_H"],
            "Lh": collected["topo_Lh"],
            "x": collected["topo_x"],
            "wind_direction": "upwind",
        }
    return payload


def _parse_bool(text: str) -> bool:
    lowered = text.lower().strip()
    if lowered in {"yes", "y", "true", "1", "correct", "yeah", "yep"}:
        return True
    if lowered in {"no", "n", "false", "0", "nope"}:
        return False
    raise ChatbotError("Please answer yes or no.")


def _parse_int(text: str) -> int:
    match = re.search(r"-?\d+", text.replace(",", ""))
    if not match:
        raise ChatbotError("Please provide a whole number.")
    value = int(match.group())
    if value < 0:
        raise ChatbotError("Please provide a nonnegative number.")
    return value


def _parse_float(text: str) -> float:
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        raise ChatbotError("Please provide a numeric value.")
    value = float(match.group())
    if value < 0:
        raise ChatbotError("Please provide a nonnegative number.")
    return value


def _parse_positive_float(text: str) -> float:
    value = _parse_float(text)
    if value <= 0:
        raise ChatbotError("Please provide a number greater than 0.")
    return value


def _parse_exposure(text: str) -> str:
    lowered = text.lower()
    if re.search(r"\bb\b", lowered) or "urban" in lowered or "wood" in lowered:
        return "B"
    if re.search(r"\bc\b", lowered) or "open" in lowered or "field" in lowered:
        return "C"
    if re.search(r"\bd\b", lowered) or "water" in lowered or "ocean" in lowered:
        return "D"
    raise ChatbotError("Please choose Exposure B, C, or D.")


def _parse_roof_type(text: str) -> str:
    lowered = text.lower()
    for roof_type in ["flat", "gable", "hip", "monoslope"]:
        if roof_type in lowered:
            return roof_type
    raise ChatbotError("Please choose flat, gable, hip, or monoslope.")


def _parse_ridge_orientation(text: str) -> str:
    lowered = text.lower()
    if "parallel" in lowered or "along" in lowered:
        return "parallel"
    if "normal" in lowered or "perpendicular" in lowered:
        return "normal"
    raise ChatbotError("Please choose normal to ridge or parallel to ridge.")


def _parse_analysis_type(text: str) -> str:
    lowered = text.lower()
    if "both" in lowered:
        return "both"
    if "c&c" in lowered or "cladding" in lowered or "component" in lowered:
        return "C&C"
    if "mwfrs" in lowered or "main" in lowered:
        return "MWFRS"
    raise ChatbotError("Please choose MWFRS, C&C, or both.")


def _parse_design_standard(text: str) -> str:
    lowered = text.lower()
    if "lrfd" in lowered:
        return "LRFD"
    if "asd" in lowered:
        return "ASD"
    raise ChatbotError("Please choose LRFD or ASD.")


def _parse_topo_feature(text: str) -> str:
    lowered = text.lower()
    if "escarp" in lowered or "cliff" in lowered:
        return "2D_escarpment"
    if "ridge" in lowered:
        return "2D_ridge"
    if "hill" in lowered:
        return "3D_hill"
    raise ChatbotError("Please choose 2D ridge, 2D escarpment, or 3D hill.")


def _map_occupancy(text: str) -> str:
    lowered = text.lower()
    occupancy_map = RISK_CATEGORY_DATA["occupancy_type_map"]
    aliases = {
        "single_family_residential": ["single family", "house", "home"],
        "multifamily_residential": ["multifamily", "apartment", "condo", "residential"],
        "college_university": ["college", "university"],
        "jail_detention": ["jail", "detention", "correctional"],
        "fire_station": ["fire station"],
        "police_station": ["police station"],
        "emergency_operations_center": ["emergency operations"],
        "water_treatment_facility": ["water treatment"],
        "power_generating_station": ["power generating", "power plant"],
        "aviation_control_tower": ["aviation", "control tower"],
        "agricultural_facility": ["agricultural", "farm"],
        "temporary_facility": ["temporary"],
        "minor_storage": ["minor storage", "small storage"],
    }
    for occupancy_type in occupancy_map:
        tokens = [occupancy_type.replace("_", " "), occupancy_type]
        tokens.extend(aliases.get(occupancy_type, []))
        if any(token in lowered for token in tokens):
            return occupancy_type
    return "office"


def derive_risk_category(collected: dict[str, Any]) -> tuple[str, str]:
    """Derive ASCE 7 risk category and wind-speed figure from collected answers."""
    occupancy_type = collected.get("occupancy_type", "office")
    occupancy_description = collected.get("occupancy_description", "")
    occupant_load = collected.get("occupant_load", 0)
    essential = collected.get("essential_post_disaster", False)
    hazardous = collected.get("hazardous_materials", False)
    occupancy_map = RISK_CATEGORY_DATA["occupancy_type_map"]
    mapped_rule = occupancy_map.get(occupancy_type, "risk_category_II")
    category_rules = RISK_CATEGORY_DATA["derivation_rules"]

    essential_keywords = {
        "hospital",
        "fire_station",
        "police_station",
        "emergency_operations_center",
        "water_treatment_facility",
        "aviation_control_tower",
    }
    if essential and (
        occupancy_type in essential_keywords
        or mapped_rule == "risk_category_IV"
        or _contains_any(
            occupancy_description,
            ["hospital", "fire station", "police station", "emergency", "water treatment", "control tower"],
        )
    ):
        rule = category_rules["risk_category_IV"]
        return rule["category"], rule["wind_speed_figure"]
    if hazardous:
        rule = category_rules["risk_category_III"]
        return rule["category"], rule["wind_speed_figure"]
    if occupancy_type in {"school", "daycare", "college_university"} and occupant_load >= 250:
        rule = category_rules["risk_category_III"]
        return rule["category"], rule["wind_speed_figure"]
    if occupancy_type in {"stadium_arena", "assembly_hall"} and occupant_load >= 300:
        rule = category_rules["risk_category_III"]
        return rule["category"], rule["wind_speed_figure"]
    if occupancy_type in {
        "hospital",
    } and occupant_load >= 50:
        rule = category_rules["risk_category_III"]
        return rule["category"], rule["wind_speed_figure"]
    if occupancy_type in {"jail_detention", "power_generating_station"}:
        rule = category_rules["risk_category_III"]
        return rule["category"], rule["wind_speed_figure"]
    if occupancy_type in {"agricultural_facility", "temporary_facility", "minor_storage"}:
        rule = category_rules["risk_category_I"]
        return rule["category"], rule["wind_speed_figure"]
    if occupant_load <= 5 and occupancy_type in {"agricultural_facility", "minor_storage"}:
        rule = category_rules["risk_category_I"]
        return rule["category"], rule["wind_speed_figure"]
    rule = category_rules["risk_category_II"]
    return rule["category"], rule["wind_speed_figure"]


def _contains_any(text: str, needles: list[str]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def _update_geometry_ratios(collected: dict[str, Any]) -> None:
    h = collected.get("mean_roof_height_h")
    length = collected.get("building_length_L")
    width = collected.get("building_width_B")
    if h and length:
        collected["h_over_L"] = round(h / length, 4)
    if length and width:
        collected["L_over_B"] = round(length / width, 4)


def _is_confirm(text: str) -> bool:
    lowered = text.lower().strip()
    return lowered in {"yes", "y", "confirm", "confirmed", "correct", "looks good", "proceed"}


def _apply_correction(
    message: str,
    collected: dict[str, Any],
    branch_flags: dict[str, Any],
) -> bool:
    lowered = message.lower()
    field_aliases = {
        "basic_wind_speed_V": ["wind speed", "basic wind"],
        "exposure_category": ["exposure"],
        "mean_roof_height_h": ["roof height", "height"],
        "building_length_L": ["length"],
        "building_width_B": ["width"],
        "roof_type": ["roof type", "roof"],
        "roof_slope_deg": ["slope"],
        "ridge_orientation": ["ridge", "orientation"],
        "analysis_type": ["analysis"],
        "design_standard": ["standard", "lrfd", "asd"],
    }
    field = None
    for candidate, aliases in field_aliases.items():
        if any(alias in lowered for alias in aliases):
            field = candidate
            break
    if field is None:
        return False

    value_text = lowered.split(" to ", 1)[-1] if " to " in lowered else lowered
    if field == "basic_wind_speed_V":
        collected[field] = _parse_positive_float(value_text)
    elif field == "exposure_category":
        collected[field] = _parse_exposure(value_text)
    elif field in {"mean_roof_height_h", "building_length_L", "building_width_B", "roof_slope_deg"}:
        collected[field] = _parse_positive_float(value_text)
        _update_geometry_ratios(collected)
    elif field == "roof_type":
        roof_type = _parse_roof_type(value_text)
        collected[field] = roof_type
        if roof_type == "flat":
            collected["roof_slope_deg"] = 0.0
            collected["ridge_orientation"] = None
    elif field == "ridge_orientation":
        collected[field] = _parse_ridge_orientation(value_text)
    elif field == "analysis_type":
        collected[field] = _parse_analysis_type(value_text)
    elif field == "design_standard":
        collected[field] = _parse_design_standard(value_text)
    branch_flags["corrected"] = True
    return True
