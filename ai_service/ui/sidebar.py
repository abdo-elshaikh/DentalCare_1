import streamlit as st
from .utils.api_client import check_api_health

def render_sidebar():
    """Render the sidebar settings and return the boolean use_demo flag."""
    st.sidebar.markdown(
        """
        <div style="margin-bottom: 2rem;">
            <h2 style="font-size: 1.5rem; margin-bottom: 0;">⚙️ Control Panel</h2>
        </div>
        """, 
        unsafe_allow_html=True
    )
    
    # API Health Status
    is_healthy = check_api_health()
    if is_healthy:
        st.sidebar.markdown('🟢 **API Status:** Online')
    else:
        st.sidebar.markdown('🔴 **API Status:** Offline (Please start FastAPI backend)')

    st.sidebar.markdown("---")
    
    # Patient Demographics
    st.sidebar.subheader("Patient Demographics")
    st.session_state.patient_age = st.sidebar.number_input("Age", min_value=1, max_value=100, value=st.session_state.patient_age)
    st.session_state.patient_sex = st.sidebar.selectbox("Sex", ["Male", "Female"], index=0 if st.session_state.patient_sex == "Male" else 1)
    st.session_state.ethnic_profile = st.sidebar.selectbox("Ethnic Profile", ["Caucasian", "Asian", "African", "Hispanic"], index=0)
    
    st.sidebar.markdown("---")
    
    # Image Settings
    st.sidebar.subheader("Image Settings")
    st.session_state.px_to_mm = st.sidebar.number_input("Calibration (px to mm)", value=st.session_state.px_to_mm, format="%.4f")
    
    st.sidebar.markdown("---")
    
    use_demo = st.sidebar.checkbox("Load Demo Image", value=st.session_state.use_demo)
    
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        """
        <div style="margin-top: 2rem; font-size: 0.8rem; color: #64748b;">
            CephAI Diagnostic Studio<br/>
            Version 5.0 Professional
        </div>
        """,
        unsafe_allow_html=True
    )
    
    return use_demo
