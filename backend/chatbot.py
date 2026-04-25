"""Deterministic conversation controller for ASCE 7-16 wind inputs.

This module owns conversation flow and validation. It does not call any LLM and
does not perform wind-load arithmetic itself; confirmed inputs are delegated to
the calculation engine.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.models import CalculationRequest
from backend.session import get_session, store_calculation_result, update_session
from backend.wind_load_engine import run_wind_load_calculation


DATA_DIR = Path(__file__).resolve().parent.parent / "data"

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


class ChatbotError(ValueError):
    """Raised when a user answer cannot be parsed for the current question."""


def start_prompt() -> str:
    return QUESTIONS["Q1"]


def process_user_message(session_id: str, message: str) -> tuple[str, dict[str, Any]]:
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
        try:
            response, next_question_id = _handle_answer(current_question_id, message, collected, branch_flags)
        except ChatbotError as exc:
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
    return response, updated


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
