"""Pydantic request/response schemas for API endpoints."""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


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
    image_base64: str
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
    upper_incisor_inclination: str
    lower_incisor_inclination: str
    soft_tissue_profile: str
    overjet_mm: Optional[float] = None
    overjet_classification: Optional[str] = None
    overbite_mm: Optional[float] = None
    overbite_classification: Optional[str] = None
    confidence_score: float
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
    image_base64: Optional[str] = None


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
    image_base64: str
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


class PatientIntegrationRequest(BaseModel):
    """Patient payload sent by the DentalCare ASP.NET application."""
    firstName: str
    lastName: Optional[str] = ""
    dateOfBirth: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    medicalRecordNo: str


class PatientIntegrationResponse(BaseModel):
    """Stored patient identity returned to DentalCare."""
    id: str
    firstName: str
    lastName: Optional[str] = ""
    dateOfBirth: Optional[str] = None
    gender: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    medicalRecordNo: str
    created_at: str
    updated_at: str


# Legacy/compatibility schemas
class Point(BaseModel):
    """Legacy point representation."""
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


class AnalysisRequest(BaseModel):
    """Request for cephalometric analysis."""
    landmarks: List[Point]
    px_to_mm: float = 1.0
    ethnic_profile: str = "Caucasian"
    protocol_id: str = "core_lateral"


class MeasurementsRequest(AnalysisRequest):
    """Request for measurements with uncertainty."""
    samples: int = 200
    base_sigma_px: float = 2.0


class ProtocolValidateRequest(BaseModel):
    """Request to validate landmarks against protocol."""
    landmarks: List[Point]


class DiagnoseRequest(AnalysisRequest):
    """Request for full diagnostic analysis."""
    patient_age: Optional[int] = None
    patient_sex: Optional[str] = None
    provider: str = "auto"


class InterpretRequest(BaseModel):
    """Request for diagnostic interpretation."""
    diagnostic_report: Optional[Dict[str, Any]] = None
    landmarks: Optional[List[Point]] = None
    px_to_mm: float = 1.0
    ethnic_profile: str = "Caucasian"
    protocol_id: str = "steiner"
    patient_age: Optional[int] = None
    patient_sex: Optional[str] = None
    provider: str = "auto"


class ExportRequest(AnalysisRequest):
    """Request to export analysis results."""
    patient_identifier: str = "patient"
    analysis_type: str = "Core lateral cephalometric screening"


class CreateCaseRequest(AnalysisRequest):
    """Request to create a case in repository."""
    patient_identifier: str
    analysis_type: str = "Core lateral cephalometric screening"
    patient_age: Optional[int] = None
    patient_sex: Optional[str] = None
    status: str = "done"
    comment: str = ""
    filename: Optional[str] = None


class UpdateCaseRequest(BaseModel):
    """Request to update a case."""
    status: Optional[str] = None
    comment: Optional[str] = None
    landmarks: Optional[List[Point]] = None
    px_to_mm: Optional[float] = None
    ethnic_profile: Optional[str] = None
    protocol_id: Optional[str] = None


