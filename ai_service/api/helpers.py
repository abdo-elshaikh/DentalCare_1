"""Utility helpers for API endpoints."""

import re
from io import BytesIO
from PIL import Image
from typing import List, Dict, Any, Optional, Tuple
from shared.landmarks import LANDMARK_SHORTS


def parse_treatment_timeline_months(timeline_str: str) -> int:
    """Extract average duration in months from timeline string."""
    nums = [int(s) for s in re.findall(r"\d+", timeline_str)]
    if not nums:
        return 18
    return int(sum(nums) / len(nums))


def build_diagnostic_context(
    landmarks: Optional[List[Dict[str, Any]]] = None,
    diagnostic_report: Optional[Dict[str, Any]] = None,
    px_to_mm: float = 1.0,
    ethnic_profile: str = "Caucasian",
    protocol_id: str = "steiner",
    patient_age: Optional[int] = None,
    patient_sex: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Build diagnostic context with report and treatment plan."""
    from .diagnostic_engine import build_diagnostic_report
    from .treatment_engine import build_treatment_plan
    
    if diagnostic_report is not None:
        report = diagnostic_report
    else:
        report = build_diagnostic_report(
            landmarks,
            px_to_mm=px_to_mm,
            ethnic_profile=ethnic_profile,
            protocol_id=protocol_id,
            age=patient_age,
            sex=patient_sex,
        )
    treatment_plan = build_treatment_plan(report, age=patient_age, sex=patient_sex)
    return report, treatment_plan


def classify_maxillary_position(sna: float) -> str:
    """Classify maxillary position from SNA angle."""
    if sna > 84:
        return "Prognathic"
    elif sna < 80:
        return "Retrognathic"
    return "Normal"


def classify_mandibular_position(snb: float) -> str:
    """Classify mandibular position from SNB angle."""
    if snb > 82:
        return "Prognathic"
    elif snb < 78:
        return "Retrognathic"
    return "Normal"


def classify_lower_incisor_inclination(impa: float) -> str:
    """Classify lower incisor inclination from IMPA angle."""
    if impa > 95:
        return "Proclined"
    elif impa < 85:
        return "Retroclined"
    return "Normal"


def classify_skeletal_differential(skeletal_class: str) -> Dict[str, float]:
    """Create probabilistic differential for skeletal class."""
    base = {"CI": 0.05, "CII": 0.05, "CIII": 0.05}
    
    if skeletal_class == "Class I":
        base["CI"] = 0.90
    elif skeletal_class == "Class II":
        base["CII"] = 0.90
    elif skeletal_class == "Class III":
        base["CIII"] = 0.90
    else:
        base["CI"] = 0.80
    
    return base


def image_to_bytes(img: Image.Image) -> bytes:
    """Convert PIL image to bytes."""
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return buffered.getvalue()


def landmark_names_to_ids(landmarks_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convert landmark names to ID list format."""
    landmark_shorts_reverse = {v: k for k, v in LANDMARK_SHORTS.items()}
    lm_list = []
    for name, pt in landmarks_dict.items():
        landmark_id = landmark_shorts_reverse.get(name)
        if landmark_id is not None:
            lm_list.append({
                "id": landmark_id,
                "x": pt.x,
                "y": pt.y,
                "score": 1.0,
                "name": name
            })
    return lm_list


def landmark_ids_to_response_dict(landmarks_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert landmarks from ID list to response dictionary format."""
    
    mapped = {}
    for lm in landmarks_list:
        lm_id = int(lm["id"])
        short_name = LANDMARK_SHORTS.get(lm_id)
        if short_name:
            mapped[short_name] = {
                "x": lm["x"],
                "y": lm["y"],
                "confidence": lm.get("score", 1.0),
                "provenance": "ai",
                "derived_from": [],
                "expected_error_mm": 0.5
            }
    return mapped
