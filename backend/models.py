"""Pydantic models for the Phase 2 FastAPI backend skeleton."""

from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.wind_load_engine import (
    AnalysisType,
    BuildingInputs,
    DesignStandard,
    ExposureCategory,
    RidgeOrientation,
    RoofType,
    TopoFeatureType,
    TopographicInputs,
)


class SessionResponse(BaseModel):
    session_id: str = Field(description="Unique server-side session identifier.")
    session_state: dict[str, Any] = Field(description="Current in-memory session state.")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, description="User message for the session.")


class ChatResponse(BaseModel):
    response: str = Field(description="Backend response text.")
    session_state: dict[str, Any] = Field(description="Updated in-memory session state.")


class TopographicInputsRequest(BaseModel):
    feature_type: TopoFeatureType = Field(description="Topographic feature type.")
    H: float = Field(gt=0, description="Height of the topographic feature in feet.")
    Lh: float = Field(gt=0, description="Horizontal distance to the half-height point in feet.")
    x: float = Field(ge=0, description="Horizontal distance from crest to building in feet.")
    wind_direction: Literal["upwind", "downwind"] = Field(
        default="upwind",
        description="Building location relative to the crest and wind direction.",
    )

    def to_engine_input(self) -> TopographicInputs:
        return TopographicInputs(
            feature_type=self.feature_type,
            H=self.H,
            Lh=self.Lh,
            x=self.x,
            wind_direction=self.wind_direction,
        )


class CalculationRequest(BaseModel):
    risk_category: Literal["I", "II", "III", "IV"] = Field(
        description="ASCE 7 risk category."
    )
    basic_wind_speed_V: float = Field(
        gt=0,
        description="Basic wind speed in miles per hour.",
    )
    exposure_category: ExposureCategory = Field(description="Exposure category B, C, or D.")
    mean_roof_height_h: float = Field(gt=0, description="Mean roof height in feet.")
    building_length_L: float = Field(gt=0, description="Building length parallel to wind in feet.")
    building_width_B: float = Field(gt=0, description="Building width perpendicular to wind in feet.")
    roof_type: RoofType = Field(description="Roof type used by the calculation engine.")
    roof_slope_deg: float = Field(default=0.0, ge=0, description="Roof slope in degrees.")
    ridge_orientation: RidgeOrientation | None = Field(
        default=None,
        description="Ridge orientation for gable and hip roofs.",
    )
    topo_inputs: TopographicInputsRequest | None = Field(
        default=None,
        description="Optional topographic inputs when a qualifying feature is present.",
    )
    analysis_type: AnalysisType = Field(
        default=AnalysisType.MWFRS,
        description="Requested analysis type.",
    )
    design_standard: DesignStandard = Field(
        default=DesignStandard.LRFD,
        description="Design standard basis.",
    )

    def to_engine_input(self) -> BuildingInputs:
        return BuildingInputs(
            risk_category=self.risk_category,
            basic_wind_speed_V=self.basic_wind_speed_V,
            exposure_category=self.exposure_category,
            mean_roof_height_h=self.mean_roof_height_h,
            building_length_L=self.building_length_L,
            building_width_B=self.building_width_B,
            roof_type=self.roof_type,
            roof_slope_deg=self.roof_slope_deg,
            ridge_orientation=self.ridge_orientation,
            topo_inputs=self.topo_inputs.to_engine_input() if self.topo_inputs else None,
            analysis_type=self.analysis_type,
            design_standard=self.design_standard,
        )


class CalculationResponse(BaseModel):
    session_id: str = Field(description="Session that owns this calculation.")
    results: dict[str, Any] = Field(description="Full calculation result from the engine.")
    session_state: dict[str, Any] = Field(description="Updated in-memory session state.")

