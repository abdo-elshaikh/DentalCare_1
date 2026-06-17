import streamlit as st
import pandas as pd

def _render_treatment_card(item: dict, is_primary: bool = False):
    """Render a treatment plan dictionary into a beautiful card."""
    bg_color = "rgba(99, 102, 241, 0.1)" if is_primary else "rgba(255, 255, 255, 0.03)"
    border_color = "rgba(99, 102, 241, 0.5)" if is_primary else "rgba(255, 255, 255, 0.1)"
    badge = "🏆 PRIMARY PROTOCOL" if is_primary else "💡 CLINICAL ALTERNATIVE"
    badge_color = "#818cf8" if is_primary else "#94a3b8"
    
    html = f"""
    <div style='background: {bg_color}; border: 1px solid {border_color}; border-radius: 12px; padding: 1.5rem; margin-bottom: 1rem; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);'>
        <div style='display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;'>
            <div style='font-size: 0.75rem; font-weight: 700; letter-spacing: 0.05em; color: {badge_color};'>{badge}</div>
            <div style='font-size: 0.8rem; background: rgba(0,0,0,0.3); padding: 0.2rem 0.6rem; border-radius: 12px; color: #cbd5e1;'>⏱️ {item.get('timeline_months', 'N/A')} mo</div>
        </div>
        <h3 style='margin-top: 0; margin-bottom: 0.5rem; color: #f8fafc; font-size: 1.25rem;'>{item.get('title', 'Unknown')}</h3>
        <p style='color: #94a3b8; font-size: 0.95rem; line-height: 1.5; margin-bottom: 1.2rem;'><strong>Rationale:</strong> {item.get('rationale', '')}</p>
        
        <div style='display: flex; flex-direction: column; gap: 0.5rem;'>
            <div style='display: flex; align-items: flex-start; gap: 0.5rem; font-size: 0.85rem; color: #cbd5e1;'>
                <span style='background: rgba(99,102,241,0.2); padding: 0.2rem 0.5rem; border-radius: 4px; color: #818cf8; white-space: nowrap;'>Strategy</span>
                <span>{item.get('alternative', 'Standard mechanics')}</span>
            </div>
            <div style='display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; color: #cbd5e1;'>
                <span style='background: rgba(99,102,241,0.2); padding: 0.2rem 0.5rem; border-radius: 4px; color: #818cf8; white-space: nowrap;'>Evidence</span>
                <span>{item.get('evidence_level', 'N/A')}</span>
            </div>
    """
    
    if item.get('referrals'):
        refs = ', '.join(item['referrals'])
        html += f"""
            <div style='display: flex; align-items: center; gap: 0.5rem; font-size: 0.85rem; color: #cbd5e1;'>
                <span style='background: rgba(239,68,68,0.2); padding: 0.2rem 0.5rem; border-radius: 4px; color: #f87171; white-space: nowrap;'>Referral</span>
                <span>{refs}</span>
            </div>
        """
        
    html += """
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def render_analysis_tab(landmarks: list):
    """Render the Analysis and Diagnosis metrics in structured sub-tabs."""
    if not landmarks or not st.session_state.get('analysis_results'):
        st.info("Run AI Analysis to view metrics and diagnosis.")
        return

    # Protocol Selection
    protocols_list = {
        "core_lateral": "Steiner (Core Analysis)",
        "steiner": "Steiner Analysis",
        "tweed": "Tweed Analysis",
        "downs": "Downs Analysis",
        "mcnamara": "McNamara Analysis",
        "jarabak": "Jarabak Analysis",
        "ricketts": "Ricketts Analysis"
    }
    
    current_proto = st.session_state.get('protocol_id', 'core_lateral')
    
    col_p1, col_p2 = st.columns([3, 1])
    with col_p2:
        new_proto = st.selectbox(
            "📐 Analysis Protocol", 
            options=list(protocols_list.keys()), 
            format_func=lambda x: protocols_list.get(x, x),
            index=list(protocols_list.keys()).index(current_proto) if current_proto in protocols_list else 0
        )
        
    if new_proto != current_proto:
        st.session_state.protocol_id = new_proto
        with st.spinner(f"Re-analyzing with {protocols_list.get(new_proto, new_proto)}..."):
            from ..utils.api_client import get_diagnosis
            diag_res = get_diagnosis(
                st.session_state.landmarks,
                px_to_mm=st.session_state.px_to_mm,
                ethnic_profile=st.session_state.ethnic_profile,
                protocol_id=new_proto,
                patient_age=st.session_state.patient_age,
                patient_sex=st.session_state.patient_sex
            )
            if diag_res:
                st.session_state.diagnosis_results = diag_res.get("diagnosis")
                st.session_state.analysis_results = diag_res.get("analysis")
                st.session_state.treatment_plan = diag_res.get("treatment_plan")
                st.rerun()

    analysis = st.session_state.analysis_results
    diagnosis = st.session_state.diagnosis_results
    treatment_plan = st.session_state.get('treatment_plan')
    
    if not diagnosis:
        st.warning("Diagnosis data not available.")
        return

    # Sub-tabs
    t1, t2, t3, t4, t5 = st.tabs([
        "📋 Clinical Summary", 
        "📏 Detailed Measurements", 
        "⚕️ Treatment Plan",
        "🧠 Explainable AI",
        "📈 Growth & Dev"
    ])
    
    with t1:
        # Top level metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Skeletal Class", diagnosis.get("skeletal_class", "N/A"))
        with col2:
            st.metric("Vertical Pattern", diagnosis.get("vertical_pattern", "N/A"))
        with col3:
            st.metric("Severity", str(diagnosis.get("severity", "N/A")).title())
        with col4:
            conf = diagnosis.get('confidence', 0) * 100
            st.metric("AI Confidence", f"{conf:.1f}%")

        st.markdown("---")
        
        col_text, col_codes = st.columns([2, 1])
        with col_text:
            st.markdown("#### 📝 AI Professional Narrative")
            st.info(diagnosis.get("professional_summary", "No summary available."))
            
            st.markdown("#### 🦷 Dental Pattern")
            st.write(str(diagnosis.get("dental_pattern", "N/A")).capitalize())
            
        with col_codes:
            st.markdown("#### 🏥 Suggested ICD-10 Codes")
            codes = diagnosis.get("icd10_codes", [])
            if codes:
                for c in codes:
                    st.markdown(f"- **{c.get('code')}**: {c.get('description')}")
            else:
                st.write("No specific ICD-10 codes suggested.")
                
        # Warnings and Recommendations
        recs = diagnosis.get("recommendations", [])
        if recs:
            st.markdown("#### ⚠️ Clinical Recommendations & Alerts")
            for r in recs:
                if "CRITICAL" in r:
                    st.error(r)
                else:
                    st.warning(r)

    with t2:
        st.markdown("### Cephalometric Measurements")
        
        measurements = analysis.get("measurements", [])
        if measurements:
            df = pd.DataFrame(measurements)
            if "measurement" in df.columns:
                # Dynamically select columns
                desired_cols = ["measurement", "value", "norm_mean", "difference", "sd", "status", "label"]
                display_cols = [c for c in desired_cols if c in df.columns]
                
                if len(display_cols) < 2:
                    display_cols = df.columns.tolist()
                    
                display_df = df[display_cols].copy()
                
                for col in ["value", "norm_mean", "difference", "mean", "sd"]:
                    if col in display_df.columns:
                        display_df[col] = pd.to_numeric(display_df[col], errors='ignore')
                        try:
                            display_df[col] = display_df[col].round(2)
                        except:
                            pass
                
                # Highlight Outliers from Findings if any
                findings = diagnosis.get("findings", [])
                outlier_names = [f.get("measurement") for f in findings if f.get("is_outlier")]
                
                def highlight_row(row):
                    if row.name in display_df.index:
                        m_name = display_df.at[row.name, 'measurement']
                        if m_name in outlier_names:
                            return ['background-color: rgba(239, 68, 68, 0.2)'] * len(row)
                    return [''] * len(row)
                
                def color_status(val):
                    color = '#f87171' if str(val).lower() in ['increased', 'decreased', 'abnormal'] else '#4ade80'
                    return f'color: {color}'
                    
                st.markdown("*Rows highlighted in <span style='color:#f87171'>red</span> represent statistical outliers (possible landmark errors).*".replace("'", '"'), unsafe_allow_html=True)
                
                styled_df = display_df.style.apply(highlight_row, axis=1)
                if 'status' in display_df.columns:
                    styled_df = styled_df.map(color_status, subset=['status'])
                    
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
        else:
            st.write("No measurements available.")

    with t3:
        if not treatment_plan:
            st.info("Treatment plan not generated.")
            return
            
        st.markdown("### 🎯 Treatment Strategy")
        
        success = treatment_plan.get("success_prediction", {})
        if success:
            rate = success.get('estimated_success_rate', 'Unknown')
            st.markdown(f"#### Predicted Success Probability: **{rate}**")
            
            # Extract number for progress bar if possible
            try:
                if isinstance(rate, str) and "%" in rate:
                    rate_num = float(rate.replace("%", "")) / 100
                elif isinstance(rate, (int, float)):
                    rate_num = float(rate)
                else:
                    rate_num = 0.85
                st.progress(rate_num)
            except:
                pass
                
            with st.expander("View Predictive Factors", expanded=False):
                for factor in success.get('predictive_factors', []):
                    st.markdown(f"- {factor}")
                
        st.markdown("<br>", unsafe_allow_html=True)
        
        primary = treatment_plan.get("primary_recommendation")
        if primary:
            _render_treatment_card(primary, is_primary=True)
            
        alts = treatment_plan.get("alternative_recommendations", [])
        if alts:
            st.markdown("#### Alternative Approaches")
            for alt in alts:
                with st.expander(f"Option: {alt.get('title', 'Alternative Therapy')}"):
                    _render_treatment_card(alt, is_primary=False)
                
        # Risks
        risks = treatment_plan.get("risk_assessment", {})
        if risks:
            st.markdown("---")
            risk_level = risks.get('overall_risk_level', 'Unknown')
            color = "green" if "low" in risk_level.lower() else "orange" if "moderate" in risk_level.lower() else "red"
            st.markdown(f"#### ⚠️ Risk Profile: <span style='color:{color}'>{risk_level.upper()}</span>", unsafe_allow_html=True)
            
            risk_cols = st.columns(2)
            for i, r in enumerate(risks.get("specific_risks", [])):
                col = risk_cols[i % 2]
                with col:
                    st.error(f"**{r.get('complication')}** ({r.get('probability')})  \n*Mitigation:* {r.get('mitigation')}")

    with t4:
        st.markdown("### 🧠 Explainable AI (XAI) Reasoning")
        st.info("This module explains exactly *why* the AI generated the diagnosis and treatment plan.")
        
        # Build XAI Payload
        if st.button("Generate XAI Report", key="btn_xai"):
            with st.spinner("Generating Explainable AI decision chain..."):
                from ..utils.api_client import get_xai_explanation
                
                # Extract measurements
                meas_dict = {m["measurement"]: m["value"] for m in analysis.get("measurements", [])}
                
                # Get primary treatment name
                prim = treatment_plan.get("primary_recommendation", {})
                t_name = prim.get("title", "Standard Care")
                
                payload = {
                    "session_id": "streamlit_session",
                    "skeletal_class": diagnosis.get("skeletal_class", "Class I"),
                    "skeletal_probabilities": {"Class I": 0.33, "Class II": 0.33, "Class III": 0.33},
                    "vertical_pattern": diagnosis.get("vertical_pattern", "Normodivergent"),
                    "measurements": meas_dict,
                    "treatment_name": t_name,
                    "predicted_outcomes": {"success_rate": 0.85},
                    "uncertainty_landmarks": []
                }
                
                xai_res = get_xai_explanation(payload)
                if xai_res:
                    st.markdown(f"**Clinical Confidence:** {xai_res.get('clinical_confidence')}")
                    
                    st.markdown("#### Decision Chain")
                    for step in xai_res.get("decision_chain", []):
                        with st.expander(f"Step {step.get('step')}: {step.get('factor')}"):
                            st.write(f"**Evidence:** {step.get('evidence')}")
                            st.write(f"**Impact:** {step.get('impact')}")
                            
                    st.markdown("#### Key Drivers")
                    for kd in xai_res.get("key_drivers", []):
                        st.markdown(f"- {kd}")
                        
                    st.markdown("#### Alternative Interpretation")
                    st.write(xai_res.get("alternative_interpretation", ""))

    with t5:
        st.markdown("### 📈 Growth & Development Assessment")
        
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            cvm_stage = st.selectbox("Cervical Vertebral Maturation (CVM) Stage", options=[None, 1, 2, 3, 4, 5, 6], format_func=lambda x: f"CS {x}" if x else "Not Available")
        
        if st.button("Calculate Growth Vector", key="btn_growth"):
            with st.spinner("Assessing growth stages..."):
                from ..utils.api_client import get_growth_assessment
                
                payload = {
                    "patient_age": st.session_state.patient_age,
                    "patient_sex": st.session_state.patient_sex,
                    "landmarks": landmarks,
                    "cvm_stage": cvm_stage,
                    "px_to_mm": st.session_state.px_to_mm
                }
                
                growth_res = get_growth_assessment(payload)
                if growth_res:
                    st.success("Growth Assessment Complete")
                    
                    assessment = growth_res.get("growth_assessment", {})
                    timing = growth_res.get("treatment_timing", {})
                    projection = growth_res.get("growth_projection", {})
                    
                    st.markdown("#### Skeletal Maturity")
                    st.write(assessment.get("maturity_status", "Unknown"))
                    
                    st.markdown("#### Treatment Timing Recommendation")
                    st.info(timing.get("recommendation", "N/A"))
                    st.write(f"**Phase:** {timing.get('phase', 'N/A')}")
                    
                    st.markdown("#### Predicted Growth Vector")
                    st.write(f"**Vector:** {projection.get('vector', 'N/A')}")
                    st.write(f"**Magnitude:** {projection.get('magnitude', 'N/A')}")
                    st.write(f"**Remaining Spurt:** {projection.get('remaining_spurt_potential', 'N/A')}")
