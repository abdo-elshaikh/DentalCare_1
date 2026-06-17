import requests
import base64
import json
import streamlit as st
from PIL import Image
from io import BytesIO

API_BASE_URL = "http://127.0.0.1:8000"

def check_api_health():
    """Check if the FastAPI server is running."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=2)
        return response.status_code == 200
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

def predict_landmarks(image_bytes: bytes, px_to_mm: float = 1.0, ethnic_profile: str = "Caucasian", protocol_id: str = "core_lateral"):
    """Call the /predict endpoint to get landmarks and basic analysis."""
    url = f"{API_BASE_URL}/predict"
    files = {"file": ("image.jpg", image_bytes, "image/jpeg")}
    data = {
        "px_to_mm": px_to_mm,
        "ethnic_profile": ethnic_profile,
        "protocol_id": protocol_id
    }
    try:
        response = requests.post(url, files=files, data=data)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Error connecting to AI Engine: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            st.error(e.response.text)
        return None

def get_diagnosis(landmarks: list, px_to_mm: float = 1.0, ethnic_profile: str = "Caucasian", protocol_id: str = "core_lateral", patient_age: int = 25, patient_sex: str = "Male"):
    """Call the /diagnose endpoint to get full diagnosis and treatment plan."""
    url = f"{API_BASE_URL}/diagnose"
    payload = {
        "landmarks": landmarks,
        "px_to_mm": px_to_mm,
        "ethnic_profile": ethnic_profile,
        "protocol_id": protocol_id,
        "patient_age": patient_age,
        "patient_sex": patient_sex,
        "provider": "Dr. Smith" # Default provider for narrative
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
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

def get_growth_assessment(payload: dict):
    """Call the /growth-assessment endpoint."""
    url = f"{API_BASE_URL}/growth-assessment"
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Error generating growth assessment: {str(e)}")
        return None

def create_case(payload: dict):
    """Call the /cases endpoint to save the analysis locally."""
    url = f"{API_BASE_URL}/cases"
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        st.error(f"Error saving case: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            st.error(e.response.text)
        return None
