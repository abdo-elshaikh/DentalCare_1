"""Pydantic request/response schemas for API endpoints."""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

MAX_IMAGE_BASE64_LENGTH = 22 * 1024 * 1024


class LandmarkPointRequest(BaseModel):
    """A single landmark point with coordinates."""
    x: float
    y: float
    provenance: Optional[str] = None


class LandmarkResponsePoint(BaseModel):
    """A detected landmark with confidence and metadata."""
    x: float
    y: float
    confidence: float
    provenance: Optional[str] = "ai"
    derived_from: Optional[List[str]] = None
    expected_error_mm: Optional[float] = None


class LandmarkDetectionRequest(BaseModel):
    """Request for landmark detection from image."""
    session_id: str
    image_base64: str = Field(..., max_length=MAX_IMAGE_BASE64_LENGTH)
    pixel_spacing_mm: Optional[float] = None


class LandmarkDetectionResponse(BaseModel):
    """Response with detected landmarks."""
    landmarks: Dict[str, LandmarkResponsePoint]


class AiCalculateMeasurementsRequest(BaseModel):
    """Request to calculate measurements from landmarks."""
    session_id: str
    landmarks: Dict[str, LandmarkPointRequest]
    pixel_spacing_mm: float
    is_cbct_derived: bool = False
    population: Optional[str] = None
    protocol_id: str = "core_lateral"


class AiDiagnosisClassificationRequest(BaseModel):
    """Request for diagnostic classification."""
    session_id: str
    measurements: Dict[str, float]
    protocol_id: str = "core_lateral"
    population: Optional[str] = "Caucasian"


class DiagnosisResponseModel(BaseModel):
    """Complete diagnostic classification response."""
    skeletal_class: str
    skeletal_type: str
    corrected_anb: float
    apdi_classification: Optional[str] = "Normal"
    odi_classification: Optional[str] = "Normal"
    vertical_pattern: str
    maxillary_position: str
    mandibular_position: str
    upper_incisor_inclination: Optional[str] = None
    lower_incisor_inclination: Optional[str] = None
    soft_tissue_profile: Optional[str] = None
    overjet_mm: Optional[float] = None
    overjet_classification: Optional[str] = None
    overbite_mm: Optional[float] = None
    overbite_classification: Optional[str] = None
    confidence_score: float
    severity: Optional[str] = None
    summary: str
    warnings: List[str] = Field(default_factory=list)
    clinical_notes: List[str] = Field(default_factory=list)
    skeletal_differential: Optional[Dict[str, float]] = None


class AiTreatmentSuggestionRequest(BaseModel):
    """Request for treatment suggestions."""
    session_id: str
    skeletal_class: str
    vertical_pattern: str
    measurements: Dict[str, float]
    patient_age: float
    severity: Optional[str] = None
    image_base64: Optional[str] = Field(default=None, max_length=MAX_IMAGE_BASE64_LENGTH)


class TreatmentDto(BaseModel):
    """A single treatment option."""
    plan_index: int
    treatment_type: str
    treatment_name: str
    description: str
    rationale: Optional[str] = None
    risks: Optional[str] = None
    estimated_duration_months: Optional[int] = None
    confidence_score: float
    source: str
    is_primary: bool
    evidence_reference: Optional[str] = None
    evidence_level: Optional[str] = None
    retention_recommendation: Optional[str] = None
    predicted_outcomes: Optional[Dict[str, float]] = None


class AiTreatmentSuggestionResponse(BaseModel):
    """Response with treatment options."""
    treatments: List[TreatmentDto]


class XAIDecisionStep(BaseModel):
    """A single step in explainable AI decision chain."""
    step: int
    factor: str
    evidence: str
    impact: str


class AiXaiRequestPayload(BaseModel):
    """Request for explainable AI analysis."""
    session_id: str
    skeletal_class: str
    skeletal_probabilities: Dict[str, float]
    vertical_pattern: str
    measurements: Dict[str, float]
    treatment_name: str
    predicted_outcomes: Dict[str, float]
    uncertainty_landmarks: Optional[List[str]] = None


class AiXaiResponsePayload(BaseModel):
    """Response with explainable AI decision chain."""
    decision_chain: List[XAIDecisionStep]
    key_drivers: List[str]
    uncertainty_factors: List[str]
    clinical_confidence: str
    alternative_interpretation: str


class AiOverlayMeasurementPayload(BaseModel):
    """A single measurement for overlay generation."""
    code: str
    name: str
    value: float
    unit: str
    normal_value: float
    std_deviation: float
    difference: float
    group_name: str
    status: str


class AiOverlayImagePayload(BaseModel):
    """A single generated overlay image."""
    key: str
    label: str
    image_base64: str
    width: int
    height: int


class AiOverlayRequestPayload(BaseModel):
    """Request for overlay image generation."""
    session_id: str
    image_base64: str = Field(..., max_length=MAX_IMAGE_BASE64_LENGTH)
    landmarks: Dict[str, LandmarkPointRequest]
    measurements: List[AiOverlayMeasurementPayload]
    patient_label: Optional[str] = None
    date_label: Optional[str] = None
    pixel_spacing_mm: Optional[float] = None
    outputs: List[str]


class AiOverlayResponsePayload(BaseModel):
    """Response with generated overlay images."""
    session_id: Optional[str] = None
    images: List[AiOverlayImagePayload] = Field(default_factory=list)
    render_ms: int


class Point(BaseModel):
    """Point representation used by calibration and protocol validation."""
    id: Optional[int] = None
    x: float
    y: float
    name: Optional[str] = None
    score: Optional[float] = None


class CalibrateRequest(BaseModel):
    """Request to calibrate pixel-to-mm scale."""
    point_a: Point
    point_b: Point
    real_distance_mm: float


class ProtocolValidateRequest(BaseModel):
    """Request to validate landmarks against protocol."""
    landmarks: List[Point]


class InterpretRequest(BaseModel):
    """Request for patient-facing diagnostic explanation."""
    diagnostic_report: Optional[Dict[str, Any]] = None
    landmarks: Optional[List[Point]] = None
    px_to_mm: float = 1.0
    ethnic_profile: str = "Caucasian"
    protocol_id: str = "steiner"
    patient_age: Optional[int] = None
    patient_sex: Optional[str] = None
    provider: str = "auto"
