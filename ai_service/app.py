"""Top-level app entry that composes the modular UI.
This file is intentionally small and import-safe: it defines run_app() and only
runs it when executed as a script (streamlit run app.py will execute it).
"""
from __future__ import annotations


def run_app():
    import streamlit as st
    from ui.utils.state import init_session_state
    from ui.components import apply_global_styles, apply_light_mode, render_header
    from ui.sidebar import render_sidebar
    from ui.workflow import prepare_workspace
    from ui.tabs.viewer import render_viewer_tab

    st.set_page_config(
        page_title="AI-Powered Cephalometric Landmark Detection",
        page_icon=":tooth:",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session_state()
    apply_global_styles()

    use_demo = render_sidebar()
    apply_light_mode()
    render_header()

    display_image = prepare_workspace(use_demo)

    tabs = st.tabs(["Workspace", "Analysis", "Data Management"])
    with tabs[0]:
        render_viewer_tab(display_image, st.session_state.landmarks)
    with tabs[1]:
        from ui.tabs.analysis import render_analysis_tab
        render_analysis_tab(st.session_state.landmarks)
    with tabs[2]:
        from ui.tabs.data_management import render_data_management_tab
        render_data_management_tab(st.session_state.landmarks)

    st.markdown(
        '<div style="margin-top:2rem;padding:.75rem 0;border-top:1px solid rgba(255,255,255,.07);'
        'text-align:center;font-size:.7rem;color:#64748b">AI-Powered Cephalometric Landmark Detection v5.0 - Hospital Edition - Clinical Research Use Only</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    run_app()
