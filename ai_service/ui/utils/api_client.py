import requests
import base64
import streamlit as st
import uuid
from PIL import Image
from io import BytesIO

API_BASE_URL = "http://127.0.0.1:8000"

def check_api_health():
    """Check if the FastAPI server is running."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        if response.status_code != 200:
            return False

        data = response.json()
        return data.get("model_loaded", True) is True
    except requests.RequestException:
        return False

def get_demo_image() -> bytes:
    """Return bytes of a demo image from the dataset if available."""
    try:
        with open("dataset/demo.jpg", "rb") as f:
            return f.read()
    except FileNotFoundError:
        # Fallback to an empty image just to avoid crashing if no demo image exists
        img = Image.new("RGB", (800, 800), color=(200, 200, 200))
        buf = BytesIO()
        img.save(buf, format="JPEG")
        return buf.getvalue()

def _landmarks_dict_to_list(landmarks: dict) -> list:
    return [
        {
            "name": name,
            "x": item.get("x", 0.0),
            "y": item.get("y", 0.0),
            "score": item.get("confidence", item.get("score")),
            "confidence": item.get("confidence", item.get("score")),
            "provenance": item.get("provenance", "ai"),
            "expected_error_mm": item.get("expected_error_mm"),
        }
        for name, item in landmarks.items()
    ]


def _landmarks_list_to_dict(landmarks: list) -> dict:
    return {
        str(item.get("name") or item.get("id")): {
            "x": item.get("x", 0.0),
            "y": item.get("y", 0.0),
            "provenance": item.get("provenance"),
        }
        for item in landmarks
        if item.get("name") or item.get("id")
    }


def _measurement_values(analysis: dict) -> dict:
    return {
        row.get("measurement"): row.get("value", 0.0)
        for row in analysis.get("measurements", [])
        if row.get("measurement")
    }


def _normalize_diagnosis(raw: dict) -> dict:
    return {
        **raw,
        "confidence": raw.get("confidence_score", raw.get("confidence", 0.0)),
        "professional_summary": raw.get("summary", raw.get("professional_summary", "")),
        "recommendations": raw.get("warnings", raw.get("recommendations", [])),
        "findings": [
            {
                "measurement": note,
                "interpretation": note,
                "is_outlier": False,
            }
            for note in raw.get("clinical_notes", [])
        ],
    }


def _normalize_treatment_plan(raw: dict) -> dict:
    treatments = raw.get("treatments", [])
    primary = next((item for item in treatments if item.get("is_primary")), treatments[0] if treatments else None)
    alternatives = [item for item in treatments if item is not primary]

    def to_card(item: dict) -> dict:
        return {
            "title": item.get("treatment_name", "Treatment option"),
            "alternative": item.get("description", ""),
            "rationale": item.get("rationale", ""),
            "timeline_months": item.get("estimated_duration_months"),
            "evidence_level": item.get("evidence_level", ""),
            "evidence_refs": [item.get("evidence_reference")] if item.get("evidence_reference") else [],
        }

    success = None
    if primary:
        outcomes = primary.get("predicted_outcomes") or {}
        success = outcomes.get("success_probability") or outcomes.get("estimated_success_rate")

    return {
        "primary_recommendation": to_card(primary) if primary else None,
        "alternative_recommendations": [to_card(item) for item in alternatives],
        "success_prediction": {
            "estimated_success_rate": success if success is not None else "Unknown",
            "predictive_factors": [],
        },
        "risk_assessment": {
            "overall_risk_level": "See treatment details",
            "specific_risks": [],
        },
        "raw_treatments": treatments,
    }


def _calculate_measurements(session_id: str, landmarks: dict, px_to_mm: float, ethnic_profile: str, protocol_id: str):
    payload = {
        "session_id": session_id,
        "landmarks": landmarks,
        "pixel_spacing_mm": px_to_mm,
        "is_cbct_derived": False,
        "population": ethnic_profile,
        "protocol_id": protocol_id,
    }
    response = requests.post(f"{API_BASE_URL}/ai/calculate-measurements", json=payload)
    response.raise_for_status()
    return response.json()


def predict_landmarks(image_bytes: bytes, px_to_mm: float = 1.0, ethnic_profile: str = "Caucasian", protocol_id: str = "core_lateral"):
    """Detect landmarks and calculate measurements through active staged AI endpoints."""
    session_id = str(uuid.uuid4())
    payload = {
        "session_id": session_id,
        "image_base64": base64.b64encode(image_bytes).decode("ascii"),
        "pixel_spacing_mm": px_to_mm,
    }
    try:
        response = requests.post(f"{API_BASE_URL}/ai/detect-landmarks", json=payload)
        response.raise_for_status()
        landmarks_dict = response.json().get("landmarks", {})
        analysis = _calculate_measurements(session_id, landmarks_dict, px_to_mm, ethnic_profile, protocol_id)
        return {
            "landmarks": _landmarks_dict_to_list(landmarks_dict),
            "analysis": analysis,
        }
    except requests.RequestException as e:
        st.error(f"Error connecting to AI Engine: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            st.error(e.response.text)
        return None

def get_diagnosis(landmarks: list, px_to_mm: float = 1.0, ethnic_profile: str = "Caucasian", protocol_id: str = "core_lateral", patient_age: int = 25, patient_sex: str = "Male"):
    """Calculate measurements, classify diagnosis, and request treatment suggestions."""
    session_id = str(uuid.uuid4())
    try:
        landmark_dict = _landmarks_list_to_dict(landmarks)
        analysis = _calculate_measurements(session_id, landmark_dict, px_to_mm, ethnic_profile, protocol_id)
        measurements = _measurement_values(analysis)

        diagnosis_payload = {
            "session_id": session_id,
            "measurements": measurements,
            "protocol_id": protocol_id,
            "population": ethnic_profile,
        }
        diagnosis_response = requests.post(f"{API_BASE_URL}/ai/classify-diagnosis", json=diagnosis_payload)
        diagnosis_response.raise_for_status()
        diagnosis = diagnosis_response.json()

        treatment_payload = {
            "session_id": session_id,
            "skeletal_class": diagnosis.get("skeletal_class", "Class I"),
            "vertical_pattern": diagnosis.get("vertical_pattern", "Normodivergent"),
            "measurements": measurements,
            "patient_age": patient_age,
            "severity": diagnosis.get("severity"),
        }
        treatment_response = requests.post(f"{API_BASE_URL}/ai/suggest-treatment", json=treatment_payload)
        treatment_response.raise_for_status()

        return {
            "analysis": analysis,
            "diagnosis": _normalize_diagnosis(diagnosis),
            "treatment_plan": _normalize_treatment_plan(treatment_response.json()),
        }
    except requests.RequestException as e:
        st.error(f"Error generating diagnosis: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            st.error(e.response.text)
        return None

def get_xai_explanation(payload: dict):
    """Call the /ai/explain-decision endpoint."""
    url = f"{API_BASE_URL}/ai/explain-decision"
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Error generating XAI explanation: {str(e)}")
        return None
