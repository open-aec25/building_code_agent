"""
Unit Tests — ASCE 7-16 Wind Load Calculation Engine
Covers: Kz interpolation, Kzt, qh, Cp lookups, design pressures, min load check
"""

import math
import pytest
from backend.wind_load_engine import (
    BuildingInputs, TopographicInputs,
    ExposureCategory, RoofType, RidgeOrientation, AnalysisType,
    DesignStandard, TopoFeatureType,
    calc_kz, calc_kzt, calc_velocity_pressure,
    get_cp_leeward_wall, get_cp_roof_flat, get_cp_roof_gable,
    calc_design_pressure, apply_minimum_pressure,
    run_wind_load_calculation,
    Kd, G, GCpi_positive, GCpi_negative
)


# ---------------------------------------------------------------------------
# calc_kz — Table 26.10-1
# ---------------------------------------------------------------------------

class TestCalcKz:

    def test_exact_table_value_exposure_B(self):
        assert calc_kz(15, ExposureCategory.B) == 0.57

    def test_exact_table_value_exposure_C(self):
        assert calc_kz(30, ExposureCategory.C) == 0.98

    def test_exact_table_value_exposure_D(self):
        assert calc_kz(50, ExposureCategory.D) == 1.27

    def test_height_below_15_clamps_to_15(self):
        """Heights below 15 ft must use z=15 ft value per ASCE 7-16"""
        assert calc_kz(0,  ExposureCategory.C) == calc_kz(15, ExposureCategory.C)
        assert calc_kz(10, ExposureCategory.B) == calc_kz(15, ExposureCategory.B)

    def test_interpolation_between_table_entries(self):
        """Kz at z=35 ft should interpolate between 30 ft and 40 ft values"""
        kz_30 = calc_kz(30, ExposureCategory.C)  # 0.98
        kz_40 = calc_kz(40, ExposureCategory.C)  # 1.04
        kz_35 = calc_kz(35, ExposureCategory.C)
        assert kz_30 < kz_35 < kz_40
        assert abs(kz_35 - 0.5 * (kz_30 + kz_40)) < 0.001  # midpoint

    def test_height_above_table_uses_analytical_formula(self):
        """Heights above 500 ft fall back to analytical formula"""
        kz_500 = calc_kz(500, ExposureCategory.C)
        kz_600 = calc_kz(600, ExposureCategory.C)
        assert kz_600 > kz_500  # should increase with height

    def test_exposure_D_greater_than_B_at_same_height(self):
        """More exposed sites produce higher Kz values"""
        assert calc_kz(30, ExposureCategory.D) > calc_kz(30, ExposureCategory.C)
        assert calc_kz(30, ExposureCategory.C) > calc_kz(30, ExposureCategory.B)

    def test_kz_increases_with_height(self):
        """Kz should monotonically increase with height"""
        heights = [15, 20, 30, 40, 50, 100, 200]
        for exp in ExposureCategory:
            values = [calc_kz(h, exp) for h in heights]
            for i in range(len(values) - 1):
                assert values[i] <= values[i + 1], \
                    f"Kz not monotonic at height {heights[i+1]} for Exposure {exp}"


# ---------------------------------------------------------------------------
# calc_kzt — Figure 26.8-1
# ---------------------------------------------------------------------------

class TestCalcKzt:

    def _make_topo(self, feature_type=TopoFeatureType.HILL, H=100, Lh=200,
                   x=100, wind_dir="upwind"):
        return TopographicInputs(
            feature_type=feature_type, H=H, Lh=Lh, x=x,
            wind_direction=wind_dir
        )

    def test_kzt_always_gte_1(self):
        """Kzt must always be >= 1.0"""
        topo = self._make_topo()
        assert calc_kzt(topo, z=30) >= 1.0

    def test_kzt_increases_near_crest(self):
        """Building closer to crest (small x) should have higher Kzt"""
        topo_near = self._make_topo(x=10)
        topo_far  = self._make_topo(x=300)
        assert calc_kzt(topo_near, z=30) > calc_kzt(topo_far, z=30)

    def test_kzt_decreases_with_height(self):
        """Kzt should decrease as height above ground increases (K3 decay)"""
        topo = self._make_topo()
        kzt_low  = calc_kzt(topo, z=15)
        kzt_high = calc_kzt(topo, z=100)
        assert kzt_low > kzt_high

    def test_ridge_higher_kzt_than_escarpment(self):
        """2D ridge produces higher K1 than escarpment for same H/Lh"""
        topo_ridge = self._make_topo(feature_type=TopoFeatureType.RIDGE)
        topo_escarp = self._make_topo(feature_type=TopoFeatureType.ESCARPMENT)
        assert calc_kzt(topo_ridge, z=30) > calc_kzt(topo_escarp, z=30)

    def test_k2_zero_far_downwind(self):
        """Very large x should drive K2 to 0, making Kzt approach 1.0"""
        topo = self._make_topo(x=10000)  # very far from crest
        kzt = calc_kzt(topo, z=30)
        assert abs(kzt - 1.0) < 0.05  # should be close to 1.0

    def test_h_over_lh_capped_at_0_5(self):
        """H/Lh > 0.5 should be capped — not raise an error"""
        topo = self._make_topo(H=300, Lh=100)  # H/Lh = 3.0 > 0.5
        kzt = calc_kzt(topo, z=30)
        assert kzt >= 1.0


# ---------------------------------------------------------------------------
# calc_velocity_pressure — Eq. 26.10-1
# ---------------------------------------------------------------------------

class TestCalcVelocityPressure:

    def test_known_value(self):
        """qh = 0.00256 * 0.85 * 1.0 * 0.85 * 115^2 ≈ 27.6 psf (Exposure C)"""
        Kz  = calc_kz(50, ExposureCategory.C)   # 1.09
        qz  = calc_velocity_pressure(Kz, 1.0, 115.0)
        expected = 0.00256 * Kz * 1.0 * Kd * (115.0 ** 2)
        assert abs(qz - expected) < 0.01

    def test_higher_wind_speed_higher_pressure(self):
        assert calc_velocity_pressure(1.0, 1.0, 130) > \
               calc_velocity_pressure(1.0, 1.0, 115)

    def test_kzt_above_1_increases_pressure(self):
        base = calc_velocity_pressure(0.9, 1.0, 115)
        topo = calc_velocity_pressure(0.9, 1.3, 115)
        assert topo > base

    def test_result_is_positive(self):
        qz = calc_velocity_pressure(0.85, 1.0, 115)
        assert qz > 0


# ---------------------------------------------------------------------------
# get_cp_leeward_wall — Figure 27.3-1
# ---------------------------------------------------------------------------

class TestCpLeewardWall:

    def test_L_over_B_lte_1_returns_neg_0_5(self):
        assert get_cp_leeward_wall(0.25) == -0.5
        assert get_cp_leeward_wall(1.0)  == -0.5

    def test_L_over_B_4_returns_neg_0_2(self):
        assert get_cp_leeward_wall(4.0) == -0.2

    def test_interpolation_at_L_over_B_2(self):
        assert get_cp_leeward_wall(2.0) == -0.3

    def test_interpolation_between_2_and_4(self):
        cp = get_cp_leeward_wall(3.0)
        assert -0.3 < cp < -0.2

    def test_cp_is_negative(self):
        """Leeward wall Cp is always negative (suction)"""
        for ratio in [0.5, 1.0, 2.0, 3.0, 4.0]:
            assert get_cp_leeward_wall(ratio) < 0


# ---------------------------------------------------------------------------
# get_cp_roof_flat — Figure 27.3-2
# ---------------------------------------------------------------------------

class TestCpRoofFlat:

    def test_h_over_L_low_returns_3_zones(self):
        zones = get_cp_roof_flat(0.3)
        assert len(zones) == 3

    def test_h_over_L_high_returns_2_zones(self):
        zones = get_cp_roof_flat(0.8)
        assert len(zones) == 2

    def test_first_zone_uses_flat_roof_suction_cp(self):
        zones = get_cp_roof_flat(0.3)
        assert zones[0]["Cp"] == -0.9

    def test_h_over_L_0_5_boundary(self):
        """Boundary at h/L = 0.5 stays in the low h/L flat roof row."""
        zones_below = get_cp_roof_flat(0.49)
        zones_at = get_cp_roof_flat(0.5)
        zones_above = get_cp_roof_flat(0.51)
        assert len(zones_below) == 3
        assert len(zones_at) == 3
        assert zones_at[0]["Cp"] == -0.9
        assert len(zones_above) == 2


# ---------------------------------------------------------------------------
# get_cp_roof_gable — Figure 27.3-2
# ---------------------------------------------------------------------------

class TestCpRoofGable:

    def test_parallel_wind_all_suction(self):
        result = get_cp_roof_gable(15, 0.4, RidgeOrientation.PARALLEL)
        for zone in result["zones"]:
            assert zone["Cp"] < 0, "All zones should be suction for parallel wind"

    def test_low_slope_windward_suction(self):
        """Low slope windward roof should be suction"""
        result = get_cp_roof_gable(5, 0.3, RidgeOrientation.NORMAL)
        assert result["windward_slope"]["Cp"] < 0

    def test_high_slope_windward_positive(self):
        """High slope (>=30 deg) windward roof should be positive Cp"""
        result = get_cp_roof_gable(35, 0.3, RidgeOrientation.NORMAL)
        assert result["windward_slope"]["Cp"] > 0

    def test_leeward_always_suction(self):
        """Leeward slope always has negative Cp"""
        for slope in [5, 15, 25, 35]:
            result = get_cp_roof_gable(slope, 0.4, RidgeOrientation.NORMAL)
            assert result["leeward_slope"]["Cp"] < 0

    def test_slope_interpolation(self):
        """Slope between tabulated values should interpolate"""
        result_20 = get_cp_roof_gable(20, 0.25, RidgeOrientation.NORMAL)
        result_25 = get_cp_roof_gable(25, 0.25, RidgeOrientation.NORMAL)
        result_22 = get_cp_roof_gable(22, 0.25, RidgeOrientation.NORMAL)
        cp_20 = result_20["windward_slope"]["Cp"]
        cp_25 = result_25["windward_slope"]["Cp"]
        cp_22 = result_22["windward_slope"]["Cp"]
        assert min(cp_20, cp_25) <= cp_22 <= max(cp_20, cp_25)


# ---------------------------------------------------------------------------
# calc_design_pressure — Eq. 27.3-1
# ---------------------------------------------------------------------------

class TestCalcDesignPressure:

    def test_windward_wall_positive(self):
        """Windward wall with +GCpi should typically yield positive net pressure"""
        p = calc_design_pressure(q=20, Cp=0.8, qi=20, gcpi=GCpi_positive)
        # p = 20 * 0.85 * 0.8 - 20 * 0.18 = 13.6 - 3.6 = 10.0
        assert abs(p - 10.0) < 0.01

    def test_windward_wall_neg_gcpi_higher(self):
        """Negative GCpi increases windward wall net pressure"""
        p_pos = calc_design_pressure(q=20, Cp=0.8, qi=20, gcpi=GCpi_positive)
        p_neg = calc_design_pressure(q=20, Cp=0.8, qi=20, gcpi=GCpi_negative)
        assert p_neg > p_pos

    def test_leeward_wall_negative(self):
        """Leeward wall net pressure should typically be negative"""
        p = calc_design_pressure(q=20, Cp=-0.5, qi=20, gcpi=GCpi_positive)
        assert p < 0

    def test_formula_manual_verification(self):
        """Verify formula: p = q * G * Cp - qi * GCpi"""
        q, Cp, qi, gcpi = 25.0, 0.8, 25.0, 0.18
        expected = q * G * Cp - qi * gcpi
        result   = calc_design_pressure(q, Cp, qi, gcpi)
        assert abs(result - expected) < 0.001


# ---------------------------------------------------------------------------
# apply_minimum_pressure — §27.1.5
# ---------------------------------------------------------------------------

class TestApplyMinimumPressure:

    def test_wall_minimum_governs(self):
        p_gov, governed = apply_minimum_pressure(10.0, "wall")
        assert governed is True
        assert p_gov == 16.0

    def test_wall_calculated_governs(self):
        p_gov, governed = apply_minimum_pressure(20.0, "wall")
        assert governed is False
        assert p_gov == 20.0

    def test_roof_minimum_governs(self):
        p_gov, governed = apply_minimum_pressure(-5.0, "roof")
        assert governed is True
        assert p_gov == -8.0

    def test_roof_calculated_governs(self):
        p_gov, governed = apply_minimum_pressure(-15.0, "roof")
        assert governed is False
        assert p_gov == -15.0

    def test_negative_wall_minimum(self):
        """Negative wall pressure below minimum magnitude should be raised to -16 psf"""
        p_gov, governed = apply_minimum_pressure(-10.0, "wall")
        assert governed is True
        assert p_gov == -16.0


# ---------------------------------------------------------------------------
# run_wind_load_calculation — Integration Tests
# ---------------------------------------------------------------------------

class TestRunWindLoadCalculation:

    def _base_inputs(self, **kwargs):
        defaults = dict(
            risk_category       = "II",
            basic_wind_speed_V  = 115.0,
            exposure_category   = ExposureCategory.C,
            mean_roof_height_h  = 40.0,
            building_length_L   = 100.0,
            building_width_B    = 50.0,
            roof_type           = RoofType.FLAT,
            analysis_type       = AnalysisType.MWFRS,
            design_standard     = DesignStandard.LRFD,
        )
        defaults.update(kwargs)
        return BuildingInputs(**defaults)

    def test_output_has_required_keys(self):
        result = run_wind_load_calculation(self._base_inputs())
        for key in ["inputs", "constants", "Kzt", "velocity_pressure",
                    "windward_wall_profile", "Cp_values",
                    "wall_pressures", "roof_pressures", "summary"]:
            assert key in result, f"Missing key: {key}"

    def test_flat_roof_produces_zones(self):
        result = run_wind_load_calculation(self._base_inputs())
        assert "surfaces" in result["roof_pressures"]
        assert len(result["roof_pressures"]["surfaces"]) > 0

    def test_gable_roof_produces_windward_leeward_slopes(self):
        inputs = self._base_inputs(
            roof_type         = RoofType.GABLE,
            roof_slope_deg    = 20.0,
            ridge_orientation = RidgeOrientation.NORMAL
        )
        result = run_wind_load_calculation(inputs)
        surfaces = result["roof_pressures"]["surfaces"]
        assert "windward_slope" in surfaces
        assert "leeward_slope"  in surfaces

    def test_topo_feature_raises_kzt(self):
        topo = TopographicInputs(
            feature_type  = TopoFeatureType.HILL,
            H=100, Lh=200, x=50, wind_direction="upwind"
        )
        inputs_no_topo   = self._base_inputs()
        inputs_with_topo = self._base_inputs(topo_inputs=topo)

        result_flat = run_wind_load_calculation(inputs_no_topo)
        result_topo = run_wind_load_calculation(inputs_with_topo)

        assert result_topo["Kzt"]["value"] > result_flat["Kzt"]["value"]
        assert result_topo["velocity_pressure"]["qh"]["value"] > \
               result_flat["velocity_pressure"]["qh"]["value"]

    def test_higher_wind_speed_higher_qh(self):
        low  = run_wind_load_calculation(self._base_inputs(basic_wind_speed_V=90))
        high = run_wind_load_calculation(self._base_inputs(basic_wind_speed_V=150))
        assert high["velocity_pressure"]["qh"]["value"] > \
               low["velocity_pressure"]["qh"]["value"]

    def test_exposure_D_higher_than_B(self):
        exp_B = run_wind_load_calculation(
            self._base_inputs(exposure_category=ExposureCategory.B)
        )
        exp_D = run_wind_load_calculation(
            self._base_inputs(exposure_category=ExposureCategory.D)
        )
        assert exp_D["velocity_pressure"]["qh"]["value"] > \
               exp_B["velocity_pressure"]["qh"]["value"]

    def test_windward_profile_height_count(self):
        """Profile should include heights at 10 ft intervals up to h"""
        result = run_wind_load_calculation(self._base_inputs(mean_roof_height_h=50))
        profile = result["windward_wall_profile"]["profile"]
        assert len(profile) >= 4  # at least 15, 20, 30, 40, 50

    def test_wall_pressures_remain_raw_while_overall_minimum_is_checked(self):
        """Surface pressures stay calculated; the 16 psf minimum is checked at the system level."""
        result = run_wind_load_calculation(self._base_inputs(basic_wind_speed_V=75))
        walls  = result["wall_pressures"]["surfaces"]
        for surface_name, surface_data in walls.items():
            if surface_name == "windward_wall":
                for row in surface_data["pressures"]:
                    assert "p_GCpi_pos_raw_psf" in row
                    assert "p_GCpi_neg_raw_psf" in row
                    assert row["p_GCpi_pos_psf"] == row["p_GCpi_pos_raw_psf"]
                    assert row["p_GCpi_neg_psf"] == row["p_GCpi_neg_raw_psf"]
            else:
                assert "p_GCpi_pos_raw_psf" in surface_data
                assert "p_GCpi_neg_raw_psf" in surface_data
                assert surface_data["p_GCpi_pos_psf"] == surface_data["p_GCpi_pos_raw_psf"]
                assert surface_data["p_GCpi_neg_psf"] == surface_data["p_GCpi_neg_raw_psf"]

        overall = result["wind_direction_cases"]["cases"][0]["overall_horizontal_loading"]
        assert overall["minimum_force_kips"] > 0

    def test_tedds_flat_roof_benchmark_coefficients_and_raw_pressures(self):
        inputs = self._base_inputs(
            basic_wind_speed_V=120.0,
            exposure_category=ExposureCategory.C,
            mean_roof_height_h=15.0,
            building_length_L=30.0,
            building_width_B=30.0,
        )
        result = run_wind_load_calculation(inputs)

        assert result["velocity_pressure"]["qh"]["value"] == 26.634
        roof = result["roof_pressures"]["surfaces"]
        assert roof["0 to h"]["Cp"] == -0.9
        assert roof["h to 2h"]["Cp"] == -0.5
        assert abs(roof["0 to h"]["p_GCpi_pos_raw_psf"] - -25.174) < 0.01
        assert abs(roof["h to 2h"]["p_GCpi_pos_raw_psf"] - -16.114) < 0.01
        assert "beyond 2h" not in roof

        walls = result["wall_pressures"]["surfaces"]
        assert abs(walls["windward_wall"]["pressures"][0]["p_GCpi_pos_raw_psf"] - 13.317) < 0.01
        assert abs(walls["windward_wall"]["pressures"][0]["p_GCpi_neg_raw_psf"] - 22.905) < 0.01
        assert abs(walls["leeward_wall"]["p_GCpi_neg_psf"] - -6.525) < 0.01

        overall = result["wind_direction_cases"]["cases"][0]["overall_horizontal_loading"]
        assert abs(overall["calculated_force_kips"] - 13.244) < 0.01
        assert overall["minimum_force_kips"] == 7.2

    def test_wind_direction_cases_swap_rectangular_dimensions(self):
        result = run_wind_load_calculation(
            self._base_inputs(
                mean_roof_height_h=20.0,
                building_length_L=100.0,
                building_width_B=50.0,
            )
        )
        cases = result["wind_direction_cases"]["cases"]
        assert cases[0]["wind_direction"] == "0"
        assert cases[0]["L_over_B"] == 2.0
        assert cases[1]["wind_direction"] == "90"
        assert cases[1]["L_over_B"] == 0.5
        assert cases[0]["roof"]
        assert cases[1]["roof"]

    def test_invalid_height_raises(self):
        with pytest.raises(ValueError):
            self._base_inputs(mean_roof_height_h=-10)

    def test_missing_slope_raises(self):
        with pytest.raises(ValueError):
            self._base_inputs(roof_type=RoofType.GABLE, roof_slope_deg=0.0)

    def test_missing_ridge_orientation_raises(self):
        with pytest.raises(ValueError):
            self._base_inputs(
                roof_type      = RoofType.GABLE,
                roof_slope_deg = 20.0,
                # ridge_orientation intentionally omitted
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
