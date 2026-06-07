"""Format raw ASCE 7-16 engine results for UI display and reports."""

from __future__ import annotations

from typing import Any


ASCE_SCOPE_NOTE = (
    "Preliminary ASCE 7-16 Chapter 27 MWFRS wind pressure summary. "
    "Positive pressures act toward the surface; negative pressures are suction away from the surface."
)


def format_results_for_display(results: dict[str, Any]) -> dict[str, Any]:
    """Return a stable, UI-friendly structure derived from raw engine output."""
    inputs = results.get("inputs", {})
    summary = results.get("summary", {})
    velocity = results.get("velocity_pressure", {})
    constants = results.get("constants", {})
    cp_values = results.get("Cp_values", {})

    display = {
        "project_summary": _project_summary(inputs, summary),
        "user_inputs": _user_inputs(inputs),
        "derived_ratios": _derived_ratios(inputs),
        "assumptions_defaults": _assumptions_defaults(constants),
        "topographic_result": _topographic_result(results.get("Kzt", {})),
        "velocity_pressure": _velocity_pressure(velocity),
        "cp_values": _cp_values(cp_values),
        "wall_pressures": _wall_pressures(results.get("wall_pressures", {})),
        "roof_pressures": _roof_pressures(results.get("roof_pressures", {})),
        "minimum_pressure_checks": _minimum_pressure_checks(results),
        "wind_direction_cases": _wind_direction_cases(results.get("wind_direction_cases", {})),
        "warnings_limitations": _warnings_limitations(results),
        "references": _references(results),
    }
    return display


def format_results_as_markdown(results: dict[str, Any], inputs: dict[str, Any] | None = None) -> str:
    """Return a readable markdown engineering summary from raw engine output."""
    display = format_results_for_display(results)
    report_inputs = inputs or results.get("inputs", {})
    lines = [
        "# ASCE 7-16 Wind Load Calculation Summary",
        "",
        "## Project Summary",
        ASCE_SCOPE_NOTE,
        "",
        _kv_lines(display["project_summary"]),
        "",
        "## User Inputs",
        _kv_lines(report_inputs),
        "",
        "## Derived Ratios",
        _kv_lines(display["derived_ratios"]),
        "",
        "## Assumptions and Defaults",
        _table(
            ["Parameter", "Value", "Reference", "Note"],
            [
                [item["parameter"], item["value"], item["reference"], item["note"]]
                for item in display["assumptions_defaults"]
            ],
        ),
        "",
        "## Topographic Result",
        _kv_lines(display["topographic_result"]),
        "",
        "## Velocity Pressure",
        _kv_lines(display["velocity_pressure"]),
        "",
        "## Wall Cp Values",
        _table(["Surface", "Cp", "Reference", "Note"], display["cp_values"]["walls"]),
        "",
        "## Roof Cp Values",
        _table(["Zone/Surface", "Cp", "Reference", "Note"], display["cp_values"]["roof"]),
        "",
        "## Final Wall Pressures",
        _table(
            [
                "Surface",
                "Height",
                "Cp",
                "+GCpi calculated psf",
                "-GCpi calculated psf",
                "Minimum controlled",
            ],
            display["wall_pressures"],
        ),
        "",
        "## Final Roof Pressures",
        _table(
            [
                "Zone/Surface",
                "Cp",
                "Area ft2",
                "+GCpi calculated psf",
                "-GCpi calculated psf",
                "Minimum controlled",
            ],
            display["roof_pressures"],
        ),
        "",
        "## Wind Direction Cases",
        _table(
            [
                "Wind",
                "Along Depth ft",
                "Transverse Width ft",
                "h/L",
                "L/B",
                "+GCpi Horizontal kips",
                "-GCpi Horizontal kips",
                "Max Calculated Horizontal kips",
                "Minimum Horizontal kips",
                "Governing Horizontal kips",
            ],
            display["wind_direction_cases"],
        ),
        "",
        "## Minimum Pressure Checks",
        _table(
            ["Surface", "Case", "Value psf", "Minimum psf", "Controlled", "Reference"],
            display["minimum_pressure_checks"],
        ),
        "",
        "## Warnings and Limitations",
    ]
    lines.extend(f"- {warning}" for warning in display["warnings_limitations"])
    lines.extend(
        [
            "",
            "## References",
        ]
    )
    lines.extend(f"- {reference}" for reference in display["references"])
    return "\n".join(lines)


def _project_summary(inputs: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "design_standard": summary.get("design_standard") or inputs.get("design_standard"),
        "risk_category": inputs.get("risk_category"),
        "analysis_type": inputs.get("analysis_type"),
        "roof_type": inputs.get("roof_type"),
        "exposure_category": inputs.get("exposure_category"),
        "basic_wind_speed_mph": inputs.get("basic_wind_speed_V"),
        "qh_psf": summary.get("qh_psf"),
        "Kh": summary.get("Kh"),
        "Kzt": summary.get("Kzt"),
        "reference": summary.get("reference", "ASCE 7-16 Chapter 27 - Directional Procedure"),
    }


def _user_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "risk_category",
        "basic_wind_speed_V",
        "exposure_category",
        "mean_roof_height_h",
        "building_length_L",
        "building_width_B",
        "roof_type",
        "roof_slope_deg",
        "ridge_orientation",
        "analysis_type",
        "design_standard",
    ]
    return {field: inputs.get(field) for field in fields if field in inputs}


def _derived_ratios(inputs: dict[str, Any]) -> dict[str, Any]:
    return {
        "h_over_L": inputs.get("h_over_L"),
        "L_over_B": inputs.get("L_over_B"),
    }


def _assumptions_defaults(constants: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "parameter": "Kd",
            "value": constants.get("Kd"),
            "reference": "ASCE 7-16 Table 26.6-1",
            "note": "Wind directionality factor.",
        },
        {
            "parameter": "Ke",
            "value": constants.get("Ke"),
            "reference": "ASCE 7-16 Section 26.9",
            "note": "Ground elevation factor; conservative default in engine.",
        },
        {
            "parameter": "G",
            "value": constants.get("G"),
            "reference": "ASCE 7-16 Section 26.11.1",
            "note": "Rigid-structure gust effect factor assumed.",
        },
        {
            "parameter": "GCpi",
            "value": f"{constants.get('GCpi_positive')} / {constants.get('GCpi_negative')}",
            "reference": "ASCE 7-16 Table 26.13-1",
            "note": "Enclosed-building internal pressure cases.",
        },
    ]


def _topographic_result(kzt: dict[str, Any]) -> dict[str, Any]:
    return {
        "Kzt": kzt.get("value"),
        "source": kzt.get("source"),
        "inputs": kzt.get("inputs"),
    }


def _velocity_pressure(velocity: dict[str, Any]) -> dict[str, Any]:
    kh = velocity.get("Kh", {})
    qh = velocity.get("qh", {})
    return {
        "Kh": kh.get("value"),
        "Kh_reference": kh.get("reference"),
        "Kh_at_height_ft": kh.get("at_height"),
        "qh_psf": qh.get("value"),
        "qh_formula": qh.get("formula"),
        "qh_reference": qh.get("reference"),
        "note": qh.get("note"),
    }


def _cp_values(cp_values: dict[str, Any]) -> dict[str, list[list[Any]]]:
    reference = cp_values.get("reference", "ASCE 7-16 Figures 27.3-1 and 27.3-2")
    walls = []
    for surface, data in cp_values.get("walls", {}).items():
        walls.append([surface, data.get("Cp"), reference, data.get("note", "")])

    roof = []
    roof_data = cp_values.get("roof", {})
    if "zones" in roof_data:
        for zone in roof_data.get("zones", []):
            roof.append([zone.get("zone"), zone.get("Cp"), reference, zone.get("note", "")])
    elif "result" in roof_data:
        result = roof_data["result"]
        if "windward_slope" in result:
            roof.append(["windward_slope", result["windward_slope"].get("Cp"), reference, ""])
        if "leeward_slope" in result:
            roof.append(["leeward_slope", result["leeward_slope"].get("Cp"), reference, ""])
        for zone in result.get("zones", []):
            roof.append([zone.get("zone"), zone.get("Cp"), reference, result.get("note", "")])
    else:
        roof.append([roof_data.get("type"), roof_data.get("flag"), "ASCE 7-16 Figure 27.3-3", roof_data.get("note", "")])

    return {"walls": walls, "roof": roof}


def _wall_pressures(wall_pressures: dict[str, Any]) -> list[list[Any]]:
    rows = []
    surfaces = wall_pressures.get("surfaces", {})
    for surface, data in surfaces.items():
        if surface == "windward_wall":
            for pressure in data.get("pressures", []):
                rows.append(
                    [
                        surface,
                        pressure.get("height_ft"),
                        data.get("Cp"),
                        pressure.get("p_GCpi_pos_raw_psf"),
                        pressure.get("p_GCpi_neg_raw_psf"),
                        _controlled_text(pressure.get("min_governed_pos"), pressure.get("min_governed_neg")),
                    ]
                )
        else:
            rows.append(
                [
                    surface,
                    "qh",
                    data.get("Cp"),
                    data.get("p_GCpi_pos_raw_psf"),
                    data.get("p_GCpi_neg_raw_psf"),
                    _controlled_text(data.get("min_governed_pos"), data.get("min_governed_neg")),
                ]
            )
    return rows


def _roof_pressures(roof_pressures: dict[str, Any]) -> list[list[Any]]:
    rows = []
    roof_min = 8.0
    for surface, data in roof_pressures.get("surfaces", {}).items():
        if isinstance(data, dict) and "cases" in data:
            for case in data["cases"]:
                rows.append(
                    [
                        surface,
                        case.get("Cp"),
                        _area(case),
                        case.get("p_GCpi_pos_raw_psf"),
                        case.get("p_GCpi_neg_raw_psf"),
                        _controlled_text(case.get("min_governed_pos"), case.get("min_governed_neg")),
                    ]
                )
        elif isinstance(data, dict):
            rows.append(
                [
                    surface,
                    data.get("Cp"),
                    _area(data),
                    data.get("p_GCpi_pos_raw_psf"),
                    data.get("p_GCpi_neg_raw_psf"),
                    _controlled_text(data.get("min_governed_pos"), data.get("min_governed_neg")),
                ]
            )
        else:
            rows.append([surface, "", "", "", data])
    return rows


def _minimum_pressure_checks(results: dict[str, Any]) -> list[list[Any]]:
    summary = results.get("summary", {})
    min_check = summary.get("minimum_load_check", {})
    wall_min = min_check.get("wall_minimum_psf", 16.0)
    roof_min = min_check.get("roof_minimum_psf", 8.0)
    reference = min_check.get("reference", "ASCE 7-16 Section 27.1.5")
    rows = []

    for surface, data in results.get("wall_pressures", {}).get("surfaces", {}).items():
        if surface == "windward_wall":
            for pressure in data.get("pressures", []):
                rows.extend(_min_rows(surface, pressure, wall_min, reference, height=pressure.get("height_ft")))
        else:
            rows.extend(_min_rows(surface, data, wall_min, reference))

    for surface, data in results.get("roof_pressures", {}).get("surfaces", {}).items():
        if isinstance(data, dict) and "cases" in data:
            for case in data["cases"]:
                rows.extend(_min_rows(surface, case, roof_min, reference, infer=True))
        elif isinstance(data, dict):
            rows.extend(_min_rows(surface, data, roof_min, reference, infer=True))

    for case in results.get("wind_direction_cases", {}).get("cases", []):
        overall = case.get("overall_horizontal_loading", {})
        for label, load_case in overall.get("load_cases", {}).items():
            rows.append(
                [
                    f"wind {case.get('wind_direction')} overall horizontal",
                    label,
                    load_case.get("calculated_force_kips"),
                    overall.get("minimum_force_kips"),
                    bool(load_case.get("minimum_controls")),
                    reference,
                ]
            )

    if not rows:
        rows.append(["all", "minimum load", "", f"wall {wall_min} / roof {roof_min}", "not indicated", reference])
    return rows


def _wind_direction_cases(wind_direction_cases: dict[str, Any]) -> list[list[Any]]:
    rows = []
    for case in wind_direction_cases.get("cases", []):
        overall = case.get("overall_horizontal_loading", {})
        load_cases = overall.get("load_cases", {})
        rows.append(
            [
                case.get("wind_direction"),
                case.get("along_wind_depth_ft"),
                case.get("transverse_width_ft"),
                case.get("h_over_L"),
                case.get("L_over_B"),
                load_cases.get("+GCpi", {}).get("calculated_force_kips"),
                load_cases.get("-GCpi", {}).get("calculated_force_kips"),
                overall.get("calculated_force_kips"),
                overall.get("minimum_force_kips"),
                overall.get("governing_force_kips"),
            ]
        )
    return rows


def _min_rows(
    surface: str,
    data: dict[str, Any],
    minimum: float,
    reference: str,
    *,
    height: Any = None,
    infer: bool = False,
) -> list[list[Any]]:
    rows = []
    label = f"{surface} at {height} ft" if height is not None else surface
    for case_key, flag_key, case_label in [
        ("p_GCpi_pos_psf", "min_governed_pos", "+GCpi"),
        ("p_GCpi_neg_psf", "min_governed_neg", "-GCpi"),
    ]:
        value = data.get(case_key)
        if value is None:
            continue
        raw_key = case_key.replace("_psf", "_raw_psf")
        reported_value = data.get(raw_key, value)
        controlled = data.get(flag_key)
        if controlled is None and infer:
            controlled = abs(value) == minimum
        rows.append([label, case_label, reported_value, minimum, bool(controlled), reference])
    return rows


def _area(data: dict[str, Any]) -> Any:
    geometry = data.get("geometry")
    if isinstance(geometry, dict):
        return geometry.get("area_ft2")
    return data.get("area_ft2")


def _warnings_limitations(results: dict[str, Any]) -> list[str]:
    warnings = [
        "Formatter preserves raw engine assumptions; it does not independently verify site-specific code requirements.",
        "Enclosed building, rigid structure, Ke = 1.0, Kd = 0.85, G = 0.85, and GCpi = +/-0.18 are carried from the deterministic engine.",
        "Both GCpi cases must be checked consistently; do not mix signs between surfaces in one load case.",
    ]
    roof = results.get("Cp_values", {}).get("roof", {})
    if roof.get("flag") == "REQUIRES_MANUAL_LOOKUP":
        warnings.append(roof.get("note", "Manual roof Cp lookup is required."))
    return warnings


def _references(results: dict[str, Any]) -> list[str]:
    refs = [
        results.get("summary", {}).get("reference"),
        results.get("velocity_pressure", {}).get("Kh", {}).get("reference"),
        results.get("velocity_pressure", {}).get("qh", {}).get("reference"),
        results.get("Cp_values", {}).get("reference"),
        results.get("wall_pressures", {}).get("reference"),
        results.get("roof_pressures", {}).get("reference"),
        results.get("wind_direction_cases", {}).get("reference"),
        results.get("summary", {}).get("minimum_load_check", {}).get("reference"),
        results.get("Kzt", {}).get("source"),
    ]
    return [ref for ref in refs if ref]


def _controlled_text(pos: Any, neg: Any) -> str:
    controlled = []
    if pos:
        controlled.append("+GCpi")
    if neg:
        controlled.append("-GCpi")
    return ", ".join(controlled) if controlled else "No"


def _inferred_roof_min_text(data: dict[str, Any], roof_min: float) -> str:
    controlled = []
    if abs(data.get("p_GCpi_pos_psf", 9999)) == roof_min:
        controlled.append("+GCpi")
    if abs(data.get("p_GCpi_neg_psf", 9999)) == roof_min:
        controlled.append("-GCpi")
    return ", ".join(controlled) if controlled else "No"


def _kv_lines(values: dict[str, Any]) -> str:
    return "\n".join(f"- **{key}**: {value}" for key, value in values.items())


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    header = "| " + " | ".join(headers) + " |"
    divider = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(_cell(value) for value in row) + " |" for row in rows]
    return "\n".join([header, divider, *body])


def _cell(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ")
