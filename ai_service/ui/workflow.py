import streamlit as st
from PIL import Image
import io
from .utils.api_client import get_demo_image, predict_landmarks, get_diagnosis

def prepare_workspace(use_demo: bool):
    """
    Handle the image upload or demo loading, call the AI engine if not yet done,
    and return the image to be displayed.
    """
    display_image = None
    
    # 1. File Upload Area
    if not use_demo:
        st.markdown(
            """
            <style>
                .css-1v0mbdj.e115fcil1 { 
                    border: 2px dashed rgba(99, 102, 241, 0.5); 
                    border-radius: 12px;
                    background: rgba(99, 102, 241, 0.05);
                }
            </style>
            """, unsafe_allow_html=True
        )
        uploaded_file = st.file_uploader("Drop Cephalometric X-Ray here", type=["jpg", "jpeg", "png"])
        if uploaded_file is not None:
            # Check if it's a new file
            if st.session_state.uploaded_file != uploaded_file:
                st.session_state.uploaded_file = uploaded_file
                st.session_state.display_image = uploaded_file.getvalue()
                # Clear previous results
                st.session_state.landmarks = None
                st.session_state.analysis_results = None
                st.session_state.diagnosis_results = None
    else:
        # Load demo image
        if st.session_state.uploaded_file != "demo":
            st.session_state.uploaded_file = "demo"
            st.session_state.display_image = get_demo_image()
            st.session_state.landmarks = None
            st.session_state.analysis_results = None
            st.session_state.diagnosis_results = None

    # 2. Trigger AI Analysis
    if st.session_state.display_image is not None and st.session_state.landmarks is None:
        if st.button("🚀 Analyze with AI", use_container_width=True):
            with st.spinner("Analyzing Cephalometric Image..."):
                # Call Predict
                predict_res = predict_landmarks(
                    st.session_state.display_image,
                    px_to_mm=st.session_state.px_to_mm,
                    ethnic_profile=st.session_state.ethnic_profile,
                    protocol_id=st.session_state.protocol_id
                )
                
                if predict_res and "landmarks" in predict_res:
                    st.session_state.landmarks = predict_res["landmarks"]
                    st.session_state.analysis_results = predict_res.get("analysis")
                    
                    # Call Diagnosis
                    diag_res = get_diagnosis(
                        st.session_state.landmarks,
                        px_to_mm=st.session_state.px_to_mm,
                        ethnic_profile=st.session_state.ethnic_profile,
                        protocol_id=st.session_state.protocol_id,
                        patient_age=st.session_state.patient_age,
                        patient_sex=st.session_state.patient_sex
                    )
                    
                    if diag_res:
                        st.session_state.diagnosis_results = diag_res.get("diagnosis")
                        st.session_state.treatment_plan = diag_res.get("treatment_plan")
                    
                    st.rerun()

    if st.session_state.display_image:
        display_image = Image.open(io.BytesIO(st.session_state.display_image))
        
    return display_image
