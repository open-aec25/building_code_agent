"""Tests for report formatting of raw wind-load engine results."""

from backend.report_formatter import format_results_as_markdown, format_results_for_display
from backend.wind_load_engine import (
    BuildingInputs,
    AnalysisType,
    DesignStandard,
    ExposureCategory,
    RidgeOrientation,
    RoofType,
    TopoFeatureType,
    TopographicInputs,
    run_wind_load_calculation,
)


def _inputs(**overrides):
    defaults = {
        "risk_category": "II",
        "basic_wind_speed_V": 115.0,
        "exposure_category": ExposureCategory.C,
        "mean_roof_height_h": 40.0,
        "building_length_L": 100.0,
        "building_width_B": 50.0,
        "roof_type": RoofType.FLAT,
        "analysis_type": AnalysisType.MWFRS,
        "design_standard": DesignStandard.LRFD,
    }
    defaults.update(overrides)
    return BuildingInputs(**defaults)


def test_flat_roof_display_has_expected_top_level_sections():
    results = run_wind_load_calculation(_inputs())

    display = format_results_for_display(results)

    assert set(display) >= {
        "project_summary",
        "user_inputs",
        "derived_ratios",
        "assumptions_defaults",
        "topographic_result",
        "velocity_pressure",
        "cp_values",
        "wall_pressures",
        "roof_pressures",
        "minimum_pressure_checks",
        "wind_direction_cases",
        "warnings_limitations",
        "references",
    }
    assert display["project_summary"]["qh_psf"] == results["summary"]["qh_psf"]
    assert display["cp_values"]["roof"]
    assert display["wall_pressures"]
    assert display["roof_pressures"]
    assert display["wind_direction_cases"]


def test_gable_roof_formatting_surfaces_roof_slope_pressures():
    results = run_wind_load_calculation(
        _inputs(
            roof_type=RoofType.GABLE,
            roof_slope_deg=20.0,
            ridge_orientation=RidgeOrientation.NORMAL,
        )
    )

    display = format_results_for_display(results)
    markdown = format_results_as_markdown(results)

    roof_rows = display["roof_pressures"]
    assert any(row[0] == "windward_slope" for row in roof_rows)
    assert any(row[0] == "leeward_slope" for row in roof_rows)
    assert "## Final Roof Pressures" in markdown
    assert "windward_slope" in markdown


def test_topographic_result_formatting_includes_kzt_source_and_inputs():
    topo = TopographicInputs(
        feature_type=TopoFeatureType.HILL,
        H=100,
        Lh=200,
        x=50,
        wind_direction="upwind",
    )
    results = run_wind_load_calculation(_inputs(topo_inputs=topo))

    display = format_results_for_display(results)

    assert display["topographic_result"]["Kzt"] > 1.0
    assert "Figure 26.8-1" in display["topographic_result"]["source"]
    assert display["topographic_result"]["inputs"]["feature_type"] == "3D_hill"


def test_assumptions_defaults_and_references_are_present():
    results = run_wind_load_calculation(_inputs())

    display = format_results_for_display(results)
    markdown = format_results_as_markdown(results)

    assumption_names = {item["parameter"] for item in display["assumptions_defaults"]}
    assert {"G", "Kd", "Ke", "GCpi"} <= assumption_names
    assert "ASCE 7-16 Table 26.6-1" in markdown
    assert "ASCE 7-16 Eq. 26.10-1" in markdown
    assert "ASCE 7-16 §27.1.5" in markdown


def test_minimum_pressure_checks_are_surfaced_for_low_wind_speed():
    results = run_wind_load_calculation(_inputs(basic_wind_speed_V=75.0))

    display = format_results_for_display(results)
    markdown = format_results_as_markdown(results)

    checks = display["minimum_pressure_checks"]
    assert checks
    assert any(row[4] is True for row in checks)
    assert "## Minimum Pressure Checks" in markdown
    assert "True" in markdown


def test_markdown_contains_readable_report_sections_and_key_values():
    results = run_wind_load_calculation(_inputs())

    markdown = format_results_as_markdown(results)

    assert markdown.startswith("# ASCE 7-16 Wind Load Calculation Summary")
    assert "## Project Summary" in markdown
    assert "## Assumptions and Defaults" in markdown
    assert "## Final Wall Pressures" in markdown
    assert "## Final Roof Pressures" in markdown
    assert "## Wind Direction Cases" in markdown
    assert f"**qh_psf**: {results['summary']['qh_psf']}" in markdown
    assert "Kh" in markdown
    assert "Kzt" in markdown


def test_formatter_preserves_raw_and_design_pressure_columns():
    results = run_wind_load_calculation(
        _inputs(
            basic_wind_speed_V=120.0,
            exposure_category=ExposureCategory.C,
            mean_roof_height_h=15.0,
            building_length_L=30.0,
            building_width_B=30.0,
        )
    )

    markdown = format_results_as_markdown(results)

    assert "+GCpi calculated psf" in markdown
    assert "-GCpi calculated psf" in markdown
    assert "13.317" in markdown
    assert "13.244" in markdown
