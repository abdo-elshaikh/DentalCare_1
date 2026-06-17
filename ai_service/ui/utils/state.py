import streamlit as st

def init_session_state():
    """Initialize Streamlit session state variables."""
    defaults = {
        "uploaded_file": None,
        "display_image": None,
        "landmarks": None,
        "analysis_results": None,
        "diagnosis_results": None,
        "treatment_plan": None,
        "error_message": None,
        "is_loading": False,
        "use_demo": False,
        "px_to_mm": 1.0,
        "ethnic_profile": "Caucasian",
        "protocol_id": "core_lateral",
        "patient_age": 25,
        "patient_sex": "Male"
    }
    
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
