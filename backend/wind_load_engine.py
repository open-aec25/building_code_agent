"""
ASCE 7-16 Wind Load Calculation Engine
Directional Procedure — Chapter 27 (MWFRS, All Heights)

Assumptions (hardcoded):
    - Rigid structure: G = 0.85
    - Fully enclosed building: GCpi = ±0.18
    - Ground elevation factor: Ke = 1.0
    - Wind directionality factor: Kd = 0.85

References:
    - ASCE 7-16 §26 (General Wind Load Provisions)
    - ASCE 7-16 §27 (Directional Procedure, All Heights)
"""

import math
import json
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


# ---------------------------------------------------------------------------
# ENUMS
# ---------------------------------------------------------------------------

class ExposureCategory(str, Enum):
    B = "B"
    C = "C"
    D = "D"


class RoofType(str, Enum):
    FLAT       = "flat"
    GABLE      = "gable"
    HIP        = "hip"
    MONOSLOPE  = "monoslope"


class RidgeOrientation(str, Enum):
    NORMAL   = "normal"    # wind perpendicular to ridge
    PARALLEL = "parallel"  # wind along the ridge


class AnalysisType(str, Enum):
    MWFRS = "MWFRS"
    CC    = "C&C"
    BOTH  = "both"


class DesignStandard(str, Enum):
    LRFD = "LRFD"
    ASD  = "ASD"


class TopoFeatureType(str, Enum):
    RIDGE       = "2D_ridge"
    ESCARPMENT  = "2D_escarpment"
    HILL        = "3D_hill"


# ---------------------------------------------------------------------------
# INPUT DATACLASSES
# ---------------------------------------------------------------------------

@dataclass
class TopographicInputs:
    """
    Inputs for Kzt calculation per ASCE 7-16 §26.8 / Figure 26.8-1.
    Only required if topographic feature is present.
    """
    feature_type: TopoFeatureType
    H: float            # Height of feature from base to crest (ft)
    Lh: float           # Horizontal distance from crest to H/2 point upwind (ft)
    x: float            # Horizontal distance from crest to building (ft)
    wind_direction: str = "upwind"   # "upwind" or "downwind"


@dataclass
class BuildingInputs:
    """
    Complete set of user-provided inputs collected by the chatbot.
    """
    # Classification
    risk_category: str                          # "I", "II", "III", "IV"

    # Site
    basic_wind_speed_V: float                   # mph — from wind speed map lookup
    exposure_category: ExposureCategory

    # Geometry
    mean_roof_height_h: float                   # ft
    building_length_L: float                    # ft — parallel to wind
    building_width_B: float                     # ft — perpendicular to wind
    roof_type: RoofType
    roof_slope_deg: float = 0.0                 # degrees (0 for flat)
    ridge_orientation: Optional[RidgeOrientation] = None

    # Topographic (optional)
    topo_inputs: Optional[TopographicInputs] = None

    # Design intent
    analysis_type: AnalysisType = AnalysisType.MWFRS
    design_standard: DesignStandard = DesignStandard.LRFD

    def __post_init__(self):
        self._validate()

    def _validate(self):
        if self.mean_roof_height_h <= 0:
            raise ValueError("Mean roof height must be greater than 0.")
        if self.building_length_L <= 0 or self.building_width_B <= 0:
            raise ValueError("Building dimensions must be greater than 0.")
        if self.basic_wind_speed_V <= 0:
            raise ValueError("Basic wind speed must be greater than 0.")
        if self.roof_type != RoofType.FLAT and self.roof_slope_deg == 0.0:
            raise ValueError(f"Roof slope is required for roof type '{self.roof_type}'.")
        if self.roof_type in (RoofType.GABLE, RoofType.HIP) and self.ridge_orientation is None:
            raise ValueError(f"Ridge orientation is required for roof type '{self.roof_type}'.")


# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

# ASCE 7-16 Table 26.6-1
Kd = 0.85

# ASCE 7-16 §26.9 — conservative default
Ke = 1.0

# ASCE 7-16 §26.11.1 — rigid structure assumption
G = 0.85

# ASCE 7-16 Table 26.13-1 — enclosed building
GCpi_positive =  0.18
GCpi_negative = -0.18

# ASCE 7-16 Eq. 26.10-1
VELOCITY_PRESSURE_COEFF = 0.00256

# ASCE 7-16 §27.1.5 — minimum design pressures
MIN_WALL_PRESSURE_PSF = 16.0
MIN_ROOF_PRESSURE_PSF =  8.0

# Kz table parameters per exposure — ASCE 7-16 Table 26.10-1
KZ_PARAMS = {
    ExposureCategory.B: {"alpha": 7.0,  "zg": 1200},
    ExposureCategory.C: {"alpha": 9.5,  "zg": 900},
    ExposureCategory.D: {"alpha": 11.5, "zg": 700},
}

# Tabulated Kz values (height ft → Kz) per ASCE 7-16 Table 26.10-1
KZ_TABLE = {
    ExposureCategory.B: {
        15: 0.57, 20: 0.62, 25: 0.66, 30: 0.70, 40: 0.76,
        50: 0.81, 60: 0.85, 70: 0.89, 80: 0.93, 90: 0.96,
        100: 0.99, 120: 1.04, 140: 1.09, 160: 1.13, 180: 1.17,
        200: 1.20, 250: 1.28, 300: 1.35, 350: 1.41, 400: 1.47,
        450: 1.52, 500: 1.56
    },
    ExposureCategory.C: {
        15: 0.85, 20: 0.90, 25: 0.94, 30: 0.98, 40: 1.04,
        50: 1.09, 60: 1.13, 70: 1.17, 80: 1.21, 90: 1.24,
        100: 1.26, 120: 1.31, 140: 1.36, 160: 1.39, 180: 1.43,
        200: 1.46, 250: 1.52, 300: 1.58, 350: 1.63, 400: 1.67,
        450: 1.71, 500: 1.75
    },
    ExposureCategory.D: {
        15: 1.03, 20: 1.08, 25: 1.12, 30: 1.16, 40: 1.22,
        50: 1.27, 60: 1.31, 70: 1.34, 80: 1.38, 90: 1.40,
        100: 1.43, 120: 1.48, 140: 1.52, 160: 1.55, 180: 1.58,
        200: 1.61, 250: 1.68, 300: 1.73, 350: 1.78, 400: 1.82,
        450: 1.86, 500: 1.89
    }
}

# K1 values for Kzt — ASCE 7-16 Figure 26.8-1
# Keyed by feature type, then H/Lh ratio
K1_TABLE = {
    TopoFeatureType.RIDGE: {
        0.20: 0.29, 0.25: 0.36, 0.30: 0.43,
        0.35: 0.51, 0.40: 0.58, 0.45: 0.65, 0.50: 0.72
    },
    TopoFeatureType.ESCARPMENT: {
        0.20: 0.17, 0.25: 0.21, 0.30: 0.26,
        0.35: 0.30, 0.40: 0.34, 0.45: 0.38, 0.50: 0.43
    },
    TopoFeatureType.HILL: {
        0.20: 0.21, 0.25: 0.26, 0.30: 0.32,
        0.35: 0.37, 0.40: 0.42, 0.45: 0.47, 0.50: 0.53
    }
}

# mu values for K2 — ASCE 7-16 Figure 26.8-1
MU_TABLE = {
    TopoFeatureType.RIDGE:      {"upwind": 1.5, "downwind": 1.5},
    TopoFeatureType.HILL:       {"upwind": 1.5, "downwind": 1.5},
    TopoFeatureType.ESCARPMENT: {"upwind": 2.5, "downwind": 4.0},
}

# gamma values for K3 — ASCE 7-16 Figure 26.8-1
GAMMA_TABLE = {
    TopoFeatureType.RIDGE:      3.0,
    TopoFeatureType.ESCARPMENT: 2.5,
    TopoFeatureType.HILL:       4.0,
}


# ---------------------------------------------------------------------------
# STEP 1 — Kz (Velocity Pressure Exposure Coefficient)
# ASCE 7-16 Table 26.10-1 / §26.10
# ---------------------------------------------------------------------------

def calc_kz(z: float, exposure: ExposureCategory) -> float:
    """
    Calculate velocity pressure exposure coefficient Kz at height z.

    Uses table lookup with linear interpolation for heights between
    tabulated values. For z < 15 ft, uses z = 15 ft per ASCE 7-16.
    For z > 500 ft, uses the analytical formula.

    Args:
        z:        Height above ground (ft)
        exposure: Exposure category (B, C, or D)

    Returns:
        Kz (dimensionless)

    Reference:
        ASCE 7-16 Table 26.10-1
    """
    z = max(z, 15.0)  # minimum height per ASCE 7-16

    table = KZ_TABLE[exposure]
    heights = sorted(table.keys())

    # Exact match
    if z in table:
        return table[z]

    # Below table minimum — use 15 ft value
    if z < heights[0]:
        return table[heights[0]]

    # Above table maximum — use analytical formula
    params = KZ_PARAMS[exposure]
    if z > heights[-1]:
        return 2.01 * (z / params["zg"]) ** (2.0 / params["alpha"])

    # Linear interpolation between table entries
    for i in range(len(heights) - 1):
        z_low  = heights[i]
        z_high = heights[i + 1]
        if z_low <= z <= z_high:
            kz_low  = table[z_low]
            kz_high = table[z_high]
            t = (z - z_low) / (z_high - z_low)
            return round(kz_low + t * (kz_high - kz_low), 4)

    raise ValueError(f"Could not compute Kz for z={z}, exposure={exposure}")


# ---------------------------------------------------------------------------
# STEP 2 — Kzt (Topographic Factor)
# ASCE 7-16 §26.8 / Figure 26.8-1
# ---------------------------------------------------------------------------

def _interp_k1(feature_type: TopoFeatureType, H_over_Lh: float) -> float:
    """Linear interpolation of K1 from Figure 26.8-1 table."""
    H_over_Lh = min(H_over_Lh, 0.50)  # capped at 0.50 per ASCE 7-16
    table = K1_TABLE[feature_type]
    ratios = sorted(table.keys())

    if H_over_Lh in table:
        return table[H_over_Lh]
    if H_over_Lh < ratios[0]:
        return table[ratios[0]]
    if H_over_Lh > ratios[-1]:
        return table[ratios[-1]]

    for i in range(len(ratios) - 1):
        r_low  = ratios[i]
        r_high = ratios[i + 1]
        if r_low <= H_over_Lh <= r_high:
            t = (H_over_Lh - r_low) / (r_high - r_low)
            return table[r_low] + t * (table[r_high] - table[r_low])

    raise ValueError(f"K1 interpolation failed for H/Lh={H_over_Lh}")


def calc_kzt(topo: TopographicInputs, z: float) -> float:
    """
    Calculate topographic factor Kzt at height z.

    Args:
        topo: TopographicInputs dataclass
        z:    Height above ground at building location (ft)

    Returns:
        Kzt (dimensionless, >= 1.0)

    Reference:
        ASCE 7-16 §26.8, Figure 26.8-1
        Formula: Kzt = (1 + K1 * K2 * K3)^2
    """
    H, Lh, x = topo.H, topo.Lh, topo.x
    feature  = topo.feature_type
    wind_dir = topo.wind_direction

    H_over_Lh = min(H / Lh, 0.50)

    # K1 — feature shape and height ratio
    K1 = _interp_k1(feature, H_over_Lh)

    # K2 — horizontal distance from crest
    mu = MU_TABLE[feature][wind_dir]
    K2 = max(0.0, 1.0 - (x / (mu * Lh)))

    # K3 — height above ground
    gamma = GAMMA_TABLE[feature]
    K3 = math.exp(-gamma * z / Lh)

    Kzt = (1.0 + K1 * K2 * K3) ** 2
    return round(Kzt, 4)


# ---------------------------------------------------------------------------
# STEP 3 — Velocity Pressure (qz and qh)
# ASCE 7-16 §26.10 / Eq. 26.10-1
# ---------------------------------------------------------------------------

def calc_velocity_pressure(Kz: float, Kzt: float, V: float) -> float:
    """
    Calculate velocity pressure qz at a given height.

    Formula: qz = 0.00256 * Kz * Kzt * Kd * V^2
    (Ke = 1.0 assumed — drops out of equation)

    Args:
        Kz:  Velocity pressure exposure coefficient at height z
        Kzt: Topographic factor
        V:   Basic wind speed (mph)

    Returns:
        qz (psf)

    Reference:
        ASCE 7-16 Eq. 26.10-1
    """
    qz = VELOCITY_PRESSURE_COEFF * Kz * Kzt * Kd * (V ** 2)
    return round(qz, 3)


# ---------------------------------------------------------------------------
# STEP 4 — External Pressure Coefficients (Cp)
# ASCE 7-16 §27.3, Figures 27.3-1 and 27.3-2
# ---------------------------------------------------------------------------

def get_cp_leeward_wall(L_over_B: float) -> float:
    """
    Leeward wall Cp from Figure 27.3-1.
    Linearly interpolated based on L/B ratio.

    Reference: ASCE 7-16 Figure 27.3-1
    """
    # Tabulated values: L/B ratio → Cp
    leeward_table = {0.25: -0.5, 0.5: -0.5, 1.0: -0.5, 2.0: -0.3, 4.0: -0.2}
    ratios = sorted(leeward_table.keys())

    if L_over_B <= ratios[0]:
        return leeward_table[ratios[0]]
    if L_over_B >= ratios[-1]:
        return leeward_table[ratios[-1]]
    if L_over_B in leeward_table:
        return leeward_table[L_over_B]

    for i in range(len(ratios) - 1):
        r_low  = ratios[i]
        r_high = ratios[i + 1]
        if r_low <= L_over_B <= r_high:
            t = (L_over_B - r_low) / (r_high - r_low)
            return round(
                leeward_table[r_low] + t * (leeward_table[r_high] - leeward_table[r_low]), 3
            )

    raise ValueError(f"Leeward Cp interpolation failed for L/B={L_over_B}")


def get_cp_roof_flat(h_over_L: float) -> list[dict]:
    """
    Flat roof Cp zones per ASCE 7-16 Figure 27.3-2.
    Returns list of zone dicts with Cp and zone description.

    Reference: ASCE 7-16 Figure 27.3-2
    """
    if h_over_L <= 0.5:
        return [
            {"zone": "0 to h",   "Cp": -0.9},
            {"zone": "h to 2h",  "Cp": -0.5},
            {"zone": "beyond 2h","Cp": -0.3},
        ]
    else:  # h/L > 0.5
        return [
            {"zone": "0 to h",   "Cp": -1.3},
            {"zone": "beyond h", "Cp": -0.7},
        ]


def get_cp_roof_gable(
    slope_deg: float,
    h_over_L: float,
    orientation: RidgeOrientation
) -> dict:
    """
    Gable roof Cp per ASCE 7-16 Figure 27.3-2.
    Returns dict with windward and leeward slope Cp values.

    Reference: ASCE 7-16 Figure 27.3-2
    """
    if orientation == RidgeOrientation.PARALLEL:
        # Both slopes treated as leeward — similar to flat roof zones
        return {
            "wind_direction": "parallel to ridge",
            "note": "Both slopes treated as leeward — suction governs",
            "zones": [
                {"zone": "0 to h/2",    "Cp": -1.3},
                {"zone": "h/2 to h",    "Cp": -0.7},
                {"zone": "beyond h",    "Cp": -0.7},
            ]
        }

    # Wind normal to ridge
    # Windward slope Cp — interpolate on slope and h/L
    # Tabulated breakpoints from Figure 27.3-2
    windward_slope_table = {
        # slope_deg: {h/L_breakpoint: Cp}
        0:  {0.25: -0.7, 0.5: -0.9, 1.0: -1.3},
        5:  {0.25: -0.7, 0.5: -0.9, 1.0: -1.3},
        10: {0.25: -0.7, 0.5: -0.9, 1.0: -1.3},
        15: {0.25: -0.5, 0.5: -0.7, 1.0: -1.0},
        20: {0.25:  0.2, 0.5: -0.3, 1.0: -0.6},
        25: {0.25:  0.3, 0.5:  0.2, 1.0: -0.2},
        30: {0.25:  0.4, 0.5:  0.4, 1.0:  0.3},
        35: {0.25:  0.4, 0.5:  0.4, 1.0:  0.3},
        45: {0.25:  0.4, 0.5:  0.4, 1.0:  0.3},
    }

    # Leeward slope Cp — function of slope only
    leeward_slope_table = {
        0: -0.3, 5: -0.3, 10: -0.3, 15: -0.4,
        20: -0.3, 25: -0.2, 30: -0.2, 35: -0.2, 45: -0.2
    }

    def interp_slope(table: dict, slope: float) -> dict | float:
        slopes = sorted(table.keys())
        if slope <= slopes[0]:
            return table[slopes[0]]
        if slope >= slopes[-1]:
            return table[slopes[-1]]
        for i in range(len(slopes) - 1):
            s_low  = slopes[i]
            s_high = slopes[i + 1]
            if s_low <= slope <= s_high:
                t = (slope - s_low) / (s_high - s_low)
                lo = table[s_low]
                hi = table[s_high]
                if isinstance(lo, dict):
                    # interpolate inner h/L dict
                    result = {}
                    for k in lo:
                        result[k] = lo[k] + t * (hi[k] - lo[k])
                    return result
                return lo + t * (hi - lo)
        raise ValueError(f"Slope interpolation failed for slope={slope}")

    ww_by_hL  = interp_slope(windward_slope_table, slope_deg)
    lw_cp_raw = interp_slope(leeward_slope_table,  slope_deg)

    # Now interpolate windward Cp on h/L
    def interp_hL(hL_table: dict, h_over_L_val: float) -> float:
        ratios = sorted(hL_table.keys())
        if h_over_L_val <= ratios[0]:
            return hL_table[ratios[0]]
        if h_over_L_val >= ratios[-1]:
            return hL_table[ratios[-1]]
        for i in range(len(ratios) - 1):
            r_low  = ratios[i]
            r_high = ratios[i + 1]
            if r_low <= h_over_L_val <= r_high:
                t = (h_over_L_val - r_low) / (r_high - r_low)
                return hL_table[r_low] + t * (hL_table[r_high] - hL_table[r_low])
        raise ValueError(f"h/L interpolation failed")

    ww_cp = round(interp_hL(ww_by_hL, h_over_L), 3) if isinstance(ww_by_hL, dict) else round(ww_by_hL, 3)
    lw_cp = round(lw_cp_raw, 3) if isinstance(lw_cp_raw, (int, float)) else lw_cp_raw

    return {
        "wind_direction": "normal to ridge",
        "windward_slope": {"Cp": ww_cp},
        "leeward_slope":  {"Cp": lw_cp},
    }


# ---------------------------------------------------------------------------
# STEP 5 — Design Wind Pressure (p)
# ASCE 7-16 §27.3.1 / Eq. 27.3-1
# ---------------------------------------------------------------------------

def calc_design_pressure(
    q: float,
    Cp: float,
    qi: float,
    gcpi: float
) -> float:
    """
    Calculate design wind pressure for a single surface.

    Formula: p = q * G * Cp - qi * GCpi

    Args:
        q:    Velocity pressure at relevant height (psf)
              — qz (varies) for windward wall
              — qh (constant) for leeward wall, side walls, roof
        Cp:   External pressure coefficient for the surface
        qi:   Internal velocity pressure = qh for enclosed buildings (psf)
        gcpi: Internal pressure coefficient (+0.18 or -0.18)

    Returns:
        p (psf) — positive = pressure toward surface, negative = suction

    Reference:
        ASCE 7-16 Eq. 27.3-1
    """
    p = q * G * Cp - qi * gcpi
    return round(p, 3)


def apply_minimum_pressure(p: float, surface: str) -> tuple[float, bool]:
    """
    Check calculated pressure against ASCE 7-16 minimum requirements.

    Args:
        p:       Calculated design pressure (psf)
        surface: "wall" or "roof"

    Returns:
        (governing_pressure, minimum_governed: bool)

    Reference:
        ASCE 7-16 §27.1.5
    """
    minimum = MIN_WALL_PRESSURE_PSF if surface == "wall" else MIN_ROOF_PRESSURE_PSF
    abs_p   = abs(p)
    if abs_p < minimum:
        governing = minimum if p >= 0 else -minimum
        return governing, True
    return p, False


def _pressure_result(raw_pressure: float, surface: str) -> dict:
    """Return calculated pressure data while flagging minimum-check thresholds."""
    _, below_minimum = apply_minimum_pressure(raw_pressure, surface)
    return {
        "raw_psf": raw_pressure,
        "design_psf": raw_pressure,
        "minimum_governed": False,
        "below_minimum": below_minimum,
    }


def _roof_zone_extents(zone_name: str, h: float, along_wind_depth: float) -> tuple[float, float]:
    """Return start/end roof-zone extents measured from the windward edge."""
    if zone_name == "0 to h":
        start, end = 0.0, h
    elif zone_name == "h to 2h":
        start, end = h, 2.0 * h
    elif zone_name == "beyond 2h":
        start, end = 2.0 * h, along_wind_depth
    elif zone_name == "beyond h":
        start, end = h, along_wind_depth
    elif zone_name == "0 to h/2":
        start, end = 0.0, h / 2.0
    elif zone_name == "h/2 to h":
        start, end = h / 2.0, h
    else:
        start, end = 0.0, along_wind_depth
    return start, min(end, along_wind_depth)


def _roof_zone_geometry(zone_name: str, h: float, along_wind_depth: float, transverse_width: float) -> dict | None:
    start, end = _roof_zone_extents(zone_name, h, along_wind_depth)
    width = round(max(0.0, end - start), 3)
    if width <= 0:
        return None
    return {
        "distance_from_windward_edge_ft": [round(start, 3), round(end, 3)],
        "zone_width_ft": width,
        "transverse_width_ft": transverse_width,
        "area_ft2": round(width * transverse_width, 3),
    }


def _force_kips(pressure_psf: float, area_ft2: float) -> float:
    return round(pressure_psf * area_ft2 / 1000.0, 3)


def _surface_governing_case(pos_raw: float, neg_raw: float) -> str:
    return "+GCpi" if abs(pos_raw) >= abs(neg_raw) else "-GCpi"


def _direction_case_summary(
    wind_direction: str,
    along_wind_depth: float,
    transverse_width: float,
    h: float,
    qh: float,
    roof_type: RoofType,
    roof_slope_deg: float,
    ridge_orientation: Optional[RidgeOrientation],
) -> dict:
    """Summarize direction-specific Cp, roof zones, and MWFRS force checks."""
    h_over_L = round(h / along_wind_depth, 4)
    L_over_B = round(along_wind_depth / transverse_width, 4)
    wall_area = round(transverse_width * h, 3)
    cp_windward = 0.8
    cp_leeward = get_cp_leeward_wall(L_over_B)
    cp_side = -0.7

    wall_rows = {}
    for name, cp in [
        ("windward_wall", cp_windward),
        ("leeward_wall", cp_leeward),
        ("side_walls", cp_side),
    ]:
        pos_raw = calc_design_pressure(qh, cp, qh, GCpi_positive)
        neg_raw = calc_design_pressure(qh, cp, qh, GCpi_negative)
        area = wall_area if name in ("windward_wall", "leeward_wall") else None
        wall_rows[name] = {
            "Cp": cp,
            "p_GCpi_pos_raw_psf": pos_raw,
            "p_GCpi_neg_raw_psf": neg_raw,
            "governing_gcpi": _surface_governing_case(pos_raw, neg_raw),
            "area_ft2": area,
            "force_GCpi_pos_kips": _force_kips(pos_raw, area) if area else None,
            "force_GCpi_neg_kips": _force_kips(neg_raw, area) if area else None,
        }

    roof_rows = {}
    roof_vertical_area = 0.0
    if roof_type == RoofType.FLAT:
        for zone in get_cp_roof_flat(h_over_L):
            geometry = _roof_zone_geometry(zone["zone"], h, along_wind_depth, transverse_width)
            if geometry is None:
                continue
            cp = zone["Cp"]
            pos_raw = calc_design_pressure(qh, cp, qh, GCpi_positive)
            neg_raw = calc_design_pressure(qh, cp, qh, GCpi_negative)
            roof_rows[zone["zone"]] = {
                "Cp": cp,
                "geometry": geometry,
                "p_GCpi_pos_raw_psf": pos_raw,
                "p_GCpi_neg_raw_psf": neg_raw,
                "governing_gcpi": _surface_governing_case(pos_raw, neg_raw),
                "force_GCpi_pos_kips": _force_kips(pos_raw, geometry["area_ft2"]),
                "force_GCpi_neg_kips": _force_kips(neg_raw, geometry["area_ft2"]),
            }
    elif roof_type in (RoofType.GABLE, RoofType.HIP):
        roof_rows["note"] = "Direction-specific roof zone geometry is not yet expanded for sloped roofs."
    elif roof_type == RoofType.MONOSLOPE:
        roof_rows["note"] = "Monoslope roof Cp requires manual lookup."

    calculated_pos_force = round(
        abs(wall_rows["windward_wall"]["force_GCpi_pos_kips"] or 0.0)
        + abs(wall_rows["leeward_wall"]["force_GCpi_pos_kips"] or 0.0),
        3,
    )
    calculated_neg_force = round(
        abs(wall_rows["windward_wall"]["force_GCpi_neg_kips"] or 0.0)
        + abs(wall_rows["leeward_wall"]["force_GCpi_neg_kips"] or 0.0),
        3,
    )
    minimum_horizontal_force = round(
        (MIN_WALL_PRESSURE_PSF * wall_area + MIN_ROOF_PRESSURE_PSF * roof_vertical_area) / 1000.0,
        3,
    )
    governing_calculated_force = max(calculated_pos_force, calculated_neg_force)

    return {
        "wind_direction": wind_direction,
        "along_wind_depth_ft": along_wind_depth,
        "transverse_width_ft": transverse_width,
        "h_over_L": h_over_L,
        "L_over_B": L_over_B,
        "wall_area_ft2": wall_area,
        "roof_vertical_area_ft2": roof_vertical_area,
        "walls": wall_rows,
        "roof": roof_rows,
        "overall_horizontal_loading": {
            "load_cases": {
                "+GCpi": {
                    "calculated_force_kips": calculated_pos_force,
                    "governing_force_kips": max(calculated_pos_force, minimum_horizontal_force),
                    "minimum_controls": minimum_horizontal_force > calculated_pos_force,
                },
                "-GCpi": {
                    "calculated_force_kips": calculated_neg_force,
                    "governing_force_kips": max(calculated_neg_force, minimum_horizontal_force),
                    "minimum_controls": minimum_horizontal_force > calculated_neg_force,
                },
            },
            "calculated_force_kips": governing_calculated_force,
            "minimum_force_kips": minimum_horizontal_force,
            "governing_force_kips": max(governing_calculated_force, minimum_horizontal_force),
            "minimum_controls": minimum_horizontal_force > governing_calculated_force,
        },
    }


# ---------------------------------------------------------------------------
# MAIN ENGINE — run_wind_load_calculation()
# ---------------------------------------------------------------------------

def run_wind_load_calculation(inputs: BuildingInputs) -> dict:
    """
    Run the full ASCE 7-16 wind load calculation — Directional Procedure.
    Chapter 27, all heights.

    Args:
        inputs: BuildingInputs dataclass with all user-provided values

    Returns:
        dict with all intermediate and final results, organized by calculation step
    """
    results = {}

    # --------------------------------------------------
    # Derived ratios
    # --------------------------------------------------
    h = inputs.mean_roof_height_h
    L = inputs.building_length_L
    B = inputs.building_width_B
    V = inputs.basic_wind_speed_V
    exp = inputs.exposure_category

    h_over_L = round(h / L, 4)
    L_over_B = round(L / B, 4)

    results["inputs"] = {
        "risk_category":       inputs.risk_category,
        "basic_wind_speed_V":  V,
        "exposure_category":   exp.value,
        "mean_roof_height_h":  h,
        "building_length_L":   L,
        "building_width_B":    B,
        "h_over_L":            h_over_L,
        "L_over_B":            L_over_B,
        "roof_type":           inputs.roof_type.value,
        "roof_slope_deg":      inputs.roof_slope_deg,
        "ridge_orientation":   inputs.ridge_orientation.value if inputs.ridge_orientation else None,
        "analysis_type":       inputs.analysis_type.value,
        "design_standard":     inputs.design_standard.value,
    }

    # --------------------------------------------------
    # Step 1: Hardcoded constants
    # --------------------------------------------------
    results["constants"] = {
        "Kd":             Kd,
        "Ke":             Ke,
        "G":              G,
        "GCpi_positive":  GCpi_positive,
        "GCpi_negative":  GCpi_negative,
        "note":           "G=0.85 rigid structure assumed; Ke=1.0 conservative default; Kd=0.85 per Table 26.6-1; GCpi=±0.18 enclosed building per Table 26.13-1"
    }

    # --------------------------------------------------
    # Step 2: Kzt
    # --------------------------------------------------
    if inputs.topo_inputs:
        Kzt = calc_kzt(inputs.topo_inputs, h)
        results["Kzt"] = {
            "value": Kzt,
            "source": "Calculated per ASCE 7-16 Figure 26.8-1",
            "inputs": {
                "feature_type": inputs.topo_inputs.feature_type.value,
                "H":  inputs.topo_inputs.H,
                "Lh": inputs.topo_inputs.Lh,
                "x":  inputs.topo_inputs.x,
            }
        }
    else:
        Kzt = 1.0
        results["Kzt"] = {
            "value": 1.0,
            "source": "Default — no topographic feature present (ASCE 7-16 §26.8)"
        }

    # --------------------------------------------------
    # Step 3: Kh and qh (at mean roof height)
    # --------------------------------------------------
    Kh = calc_kz(h, exp)
    qh = calc_velocity_pressure(Kh, Kzt, V)

    results["velocity_pressure"] = {
        "Kh": {
            "value":     Kh,
            "at_height": h,
            "reference": "ASCE 7-16 Table 26.10-1"
        },
        "qh": {
            "value":     qh,
            "units":     "psf",
            "formula":   f"0.00256 * {Kh} * {Kzt} * {Kd} * {V}² = {qh} psf",
            "reference": "ASCE 7-16 Eq. 26.10-1",
            "note":      "qh used for leeward wall, side walls, and roof"
        }
    }

    # --------------------------------------------------
    # Step 4: Windward wall — qz profile (varies with height)
    # --------------------------------------------------
    # Build height profile in 10 ft increments up to h, then at h
    heights_to_check = list(range(0, int(h), 10)) + [h]
    heights_to_check = sorted(set(max(z, 15) for z in heights_to_check))

    qz_profile = []
    for z in heights_to_check:
        kz = calc_kz(z, exp)
        qz = calc_velocity_pressure(kz, Kzt, V)
        qz_profile.append({"height_ft": z, "Kz": kz, "qz_psf": qz})

    results["windward_wall_profile"] = {
        "note": "qz varies with height for windward wall only",
        "profile": qz_profile
    }

    # --------------------------------------------------
    # Step 5: External Pressure Coefficients (Cp)
    # --------------------------------------------------
    Cp_windward_wall = 0.8
    Cp_side_wall     = -0.7
    Cp_leeward_wall  = get_cp_leeward_wall(L_over_B)

    results["Cp_values"] = {
        "reference": "ASCE 7-16 Figures 27.3-1 and 27.3-2",
        "walls": {
            "windward": {"Cp": Cp_windward_wall, "note": "Constant per Figure 27.3-1"},
            "leeward":  {"Cp": Cp_leeward_wall,  "L_over_B": L_over_B, "note": "Interpolated from Figure 27.3-1"},
            "side":     {"Cp": Cp_side_wall,      "note": "Constant per Figure 27.3-1"},
        }
    }

    # Roof Cp
    if inputs.roof_type == RoofType.FLAT:
        roof_cp = get_cp_roof_flat(h_over_L)
        results["Cp_values"]["roof"] = {
            "type": "flat",
            "h_over_L": h_over_L,
            "zones": roof_cp
        }
    elif inputs.roof_type in (RoofType.GABLE, RoofType.HIP):
        roof_cp = get_cp_roof_gable(inputs.roof_slope_deg, h_over_L, inputs.ridge_orientation)
        results["Cp_values"]["roof"] = {
            "type": inputs.roof_type.value,
            "slope_deg": inputs.roof_slope_deg,
            "h_over_L":  h_over_L,
            "result":    roof_cp
        }
    elif inputs.roof_type == RoofType.MONOSLOPE:
        results["Cp_values"]["roof"] = {
            "type": "monoslope",
            "flag": "REQUIRES_MANUAL_LOOKUP",
            "note": "Monoslope roof Cp must be read from ASCE 7-16 Figure 27.3-3 — not computed here"
        }

    # --------------------------------------------------
    # Step 6: Design Wind Pressures — Walls
    # ASCE 7-16 Eq. 27.3-1: p = q * G * Cp - qi * GCpi
    # --------------------------------------------------
    wall_pressures = {}

    # Windward wall — two GCpi cases, pressure varies with height
    ww_pressures = []
    for row in qz_profile:
        z   = row["height_ft"]
        qz  = row["qz_psf"]
        p_pos_gcpi = calc_design_pressure(qz, Cp_windward_wall, qh, GCpi_positive)
        p_neg_gcpi = calc_design_pressure(qz, Cp_windward_wall, qh, GCpi_negative)
        pos_result = _pressure_result(p_pos_gcpi, "wall")
        neg_result = _pressure_result(p_neg_gcpi, "wall")
        ww_pressures.append({
            "height_ft":         z,
            "qz_psf":            qz,
            "p_GCpi_pos_raw_psf": p_pos_gcpi,
            "p_GCpi_neg_raw_psf": p_neg_gcpi,
            "p_GCpi_pos_psf":    pos_result["design_psf"],
            "p_GCpi_neg_psf":    neg_result["design_psf"],
            "min_governed_pos":  pos_result["minimum_governed"],
            "min_governed_neg":  neg_result["minimum_governed"],
            "governing_gcpi":    _surface_governing_case(p_pos_gcpi, p_neg_gcpi),
        })

    wall_pressures["windward_wall"] = {
        "Cp": Cp_windward_wall,
        "note": "Pressure varies with height — use qz at each level",
        "pressures": ww_pressures
    }

    # Leeward wall — constant pressure (uses qh)
    lw_pos = calc_design_pressure(qh, Cp_leeward_wall, qh, GCpi_positive)
    lw_neg = calc_design_pressure(qh, Cp_leeward_wall, qh, GCpi_negative)
    lw_pos_result = _pressure_result(lw_pos, "wall")
    lw_neg_result = _pressure_result(lw_neg, "wall")

    wall_pressures["leeward_wall"] = {
        "Cp":             Cp_leeward_wall,
        "L_over_B":       L_over_B,
        "p_GCpi_pos_raw_psf": lw_pos,
        "p_GCpi_neg_raw_psf": lw_neg,
        "p_GCpi_pos_psf": lw_pos_result["design_psf"],
        "p_GCpi_neg_psf": lw_neg_result["design_psf"],
        "min_governed_pos": lw_pos_result["minimum_governed"],
        "min_governed_neg": lw_neg_result["minimum_governed"],
        "governing_gcpi": _surface_governing_case(lw_pos, lw_neg),
        "note": "Constant pressure — uses qh"
    }

    # Side walls — constant pressure (uses qh)
    sw_pos = calc_design_pressure(qh, Cp_side_wall, qh, GCpi_positive)
    sw_neg = calc_design_pressure(qh, Cp_side_wall, qh, GCpi_negative)
    sw_pos_result = _pressure_result(sw_pos, "wall")
    sw_neg_result = _pressure_result(sw_neg, "wall")

    wall_pressures["side_walls"] = {
        "Cp":             Cp_side_wall,
        "p_GCpi_pos_raw_psf": sw_pos,
        "p_GCpi_neg_raw_psf": sw_neg,
        "p_GCpi_pos_psf": sw_pos_result["design_psf"],
        "p_GCpi_neg_psf": sw_neg_result["design_psf"],
        "min_governed_pos": sw_pos_result["minimum_governed"],
        "min_governed_neg": sw_neg_result["minimum_governed"],
        "governing_gcpi": _surface_governing_case(sw_pos, sw_neg),
        "note": "Constant pressure — uses qh"
    }

    results["wall_pressures"] = {
        "reference": "ASCE 7-16 Eq. 27.3-1: p = q * G * Cp - qi * GCpi",
        "surfaces":  wall_pressures
    }

    # --------------------------------------------------
    # Step 7: Design Wind Pressures — Roof
    # --------------------------------------------------
    roof_pressures = {}

    if inputs.roof_type == RoofType.FLAT:
        for zone in get_cp_roof_flat(h_over_L):
            cp_val = zone["Cp"]
            geometry = _roof_zone_geometry(zone["zone"], h, L, B)
            if geometry is None:
                continue
            p_pos = calc_design_pressure(qh, cp_val, qh, GCpi_positive)
            p_neg = calc_design_pressure(qh, cp_val, qh, GCpi_negative)
            pos_result = _pressure_result(p_pos, "roof")
            neg_result = _pressure_result(p_neg, "roof")
            roof_pressures[zone["zone"]] = {
                "Cp": cp_val,
                "geometry": geometry,
                "p_GCpi_pos_raw_psf": p_pos,
                "p_GCpi_neg_raw_psf": p_neg,
                "p_GCpi_pos_psf": pos_result["design_psf"],
                "p_GCpi_neg_psf": neg_result["design_psf"],
                "min_governed_pos": pos_result["minimum_governed"],
                "min_governed_neg": neg_result["minimum_governed"],
                "governing_gcpi": _surface_governing_case(p_pos, p_neg),
            }

    elif inputs.roof_type in (RoofType.GABLE, RoofType.HIP):
        roof_cp_result = get_cp_roof_gable(
            inputs.roof_slope_deg, h_over_L, inputs.ridge_orientation
        )
        if inputs.ridge_orientation == RidgeOrientation.NORMAL:
            for slope_label in ["windward_slope", "leeward_slope"]:
                cp_val = roof_cp_result[slope_label]["Cp"]
                p_pos  = calc_design_pressure(qh, cp_val, qh, GCpi_positive)
                p_neg  = calc_design_pressure(qh, cp_val, qh, GCpi_negative)
                pos_result = _pressure_result(p_pos, "roof")
                neg_result = _pressure_result(p_neg, "roof")
                roof_pressures[slope_label] = {
                    "Cp":             cp_val,
                    "p_GCpi_pos_raw_psf": p_pos,
                    "p_GCpi_neg_raw_psf": p_neg,
                    "p_GCpi_pos_psf": pos_result["design_psf"],
                    "p_GCpi_neg_psf": neg_result["design_psf"],
                    "min_governed_pos": pos_result["minimum_governed"],
                    "min_governed_neg": neg_result["minimum_governed"],
                    "governing_gcpi": _surface_governing_case(p_pos, p_neg),
                }
        else:
            for zone in roof_cp_result["zones"]:
                cp_val = zone["Cp"]
                p_pos  = calc_design_pressure(qh, cp_val, qh, GCpi_positive)
                p_neg  = calc_design_pressure(qh, cp_val, qh, GCpi_negative)
                geometry = _roof_zone_geometry(zone["zone"], h, L, B)
                if geometry is None:
                    continue
                pos_result = _pressure_result(p_pos, "roof")
                neg_result = _pressure_result(p_neg, "roof")
                roof_pressures[zone["zone"]] = {
                    "Cp":             cp_val,
                    "geometry": geometry,
                    "p_GCpi_pos_raw_psf": p_pos,
                    "p_GCpi_neg_raw_psf": p_neg,
                    "p_GCpi_pos_psf": pos_result["design_psf"],
                    "p_GCpi_neg_psf": neg_result["design_psf"],
                    "min_governed_pos": pos_result["minimum_governed"],
                    "min_governed_neg": neg_result["minimum_governed"],
                    "governing_gcpi": _surface_governing_case(p_pos, p_neg),
                }

    elif inputs.roof_type == RoofType.MONOSLOPE:
        roof_pressures["note"] = (
            "Monoslope roof requires manual Cp lookup from ASCE 7-16 Figure 27.3-3. "
            "Run calc_design_pressure() once Cp is determined."
        )

    results["roof_pressures"] = {
        "reference": "ASCE 7-16 Eq. 27.3-1 applied to roof surfaces",
        "qh_used_psf": qh,
        "surfaces": roof_pressures
    }

    # --------------------------------------------------
    # Step 8: Direction checks and MWFRS force summaries
    # --------------------------------------------------
    results["wind_direction_cases"] = {
        "reference": "ASCE 7-16 Chapter 27 MWFRS checks for orthogonal wind directions",
        "note": (
            "Wind 0 uses building_length_L as along-wind depth. "
            "Wind 90 swaps length and width for direction-specific L/B, h/L, roof zones, and force checks."
        ),
        "cases": [
            _direction_case_summary(
                "0",
                L,
                B,
                h,
                qh,
                inputs.roof_type,
                inputs.roof_slope_deg,
                inputs.ridge_orientation,
            ),
            _direction_case_summary(
                "90",
                B,
                L,
                h,
                qh,
                inputs.roof_type,
                inputs.roof_slope_deg,
                inputs.ridge_orientation,
            ),
        ],
    }

    # --------------------------------------------------
    # Step 9: Summary of governing pressures
    # --------------------------------------------------
    results["summary"] = {
        "reference":       "ASCE 7-16 Chapter 27 — Directional Procedure",
        "design_standard": inputs.design_standard.value,
        "qh_psf":          qh,
        "Kzt":             Kzt,
        "Kh":              Kh,
        "note": (
            "All pressures in psf. Positive = pressure toward surface. "
            "Negative = suction away from surface. "
            "Both GCpi cases (+0.18 and -0.18) must be checked simultaneously — "
            "do not mix signs between surfaces in a single load case."
        ),
        "minimum_load_check": {
            "wall_minimum_psf": MIN_WALL_PRESSURE_PSF,
            "roof_minimum_psf": MIN_ROOF_PRESSURE_PSF,
            "reference":        "ASCE 7-16 §27.1.5"
        }
    }

    return results


# ---------------------------------------------------------------------------
# EXAMPLE USAGE
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Example: 4-story office building, Boston MA
    example_inputs = BuildingInputs(
        risk_category          = "II",
        basic_wind_speed_V     = 115.0,          # mph — Risk Cat II, Boston area
        exposure_category      = ExposureCategory.B,
        mean_roof_height_h     = 50.0,           # ft
        building_length_L      = 120.0,          # ft — parallel to wind
        building_width_B       = 60.0,           # ft — perpendicular to wind
        roof_type              = RoofType.GABLE,
        roof_slope_deg         = 18.4,           # 4:12 pitch
        ridge_orientation      = RidgeOrientation.NORMAL,
        topo_inputs            = None,           # no topographic feature
        analysis_type          = AnalysisType.MWFRS,
        design_standard        = DesignStandard.LRFD,
    )

    output = run_wind_load_calculation(example_inputs)
    print(json.dumps(output, indent=2))
