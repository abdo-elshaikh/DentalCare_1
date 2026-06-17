import streamlit as st
import plotly.graph_objects as go
from PIL import Image


def render_viewer_tab(image: Image.Image, landmarks: list):
    """Render the main image viewer with interactive Plotly landmarks."""
    if image is None:
        st.info("👈 Upload an image or load the demo to begin.")
        return
    col1, col2 = st.columns([3, 1])
    
    with col2:
        st.markdown("### Visualization Controls")
        show_image = st.checkbox("Show X-Ray Image", value=True)
        show_labels = st.checkbox("Show Landmark Labels", value=True)
        show_planes = st.checkbox("Show Anatomical Planes", value=True)
        
        st.markdown("---")
        st.markdown("### Landmarks Detected")
        
        if landmarks:
            # AI Confidence Score
            diagnosis = st.session_state.get('diagnosis_results')
            if diagnosis and 'confidence' in diagnosis:
                conf = diagnosis['confidence'] * 100
                color = "green" if conf > 80 else "orange" if conf > 60 else "red"
                st.markdown(f"**AI Confidence:** <span style='color:{color}'>{conf:.1f}%</span>", unsafe_allow_html=True)
                st.progress(diagnosis['confidence'])
                
            st.markdown(f"**Total:** {len(landmarks)}")
            with st.expander("View Raw Coordinates"):
                import pandas as pd
                
                table_data = []
                for lm in landmarks:
                    # Get accuracy/score if available, otherwise default to N/A
                    acc = lm.get('score', lm.get('confidence'))
                    if acc is not None:
                        acc_str = f"{acc * 100:.1f}%" if acc <= 1.0 else f"{acc:.1f}%"
                    else:
                        acc_str = "N/A"
                        
                    table_data.append({
                        "Landmark": lm.get('name', 'Unknown'),
                        "X": int(lm.get('x', 0)),
                        "Y": int(lm.get('y', 0)),
                        "Accuracy": acc_str
                    })
                    
                df_coords = pd.DataFrame(table_data)
                st.dataframe(df_coords, use_container_width=True, hide_index=True)
        else:
            st.write("No landmarks detected yet.")

    with col1:
        st.markdown(
            "<div style='background: rgba(255,255,255,0.02); padding: 10px; border-radius: 12px;'>",
            unsafe_allow_html=True
        )
        if landmarks:
            # Create Plotly Figure
            fig = go.Figure()
            
            # Add Image
            if show_image:
                fig.add_layout_image(
                    dict(
                        source=image,
                        xref="x",
                        yref="y",
                        x=0,
                        y=image.height,
                        sizex=image.width,
                        sizey=image.height,
                        sizing="stretch",
                        opacity=1,
                        layer="below")
                )
            
            # Draw Anatomical Planes
            if show_planes:
                planes = [
                    ("Sella-Nasion", ["sella", " S", "s", "nasion", " n", "n"]),
                    ("Frankfort Horizontal", ["porion", "po"], ["orbitale", "or"]),
                    ("Mandibular Plane", ["gonion", "go"], ["menton", "me"])
                ]
                
                # Note: Sella-Nasion has 6 names in the target above by accident. Let's write them properly:
                planes = [
                    ("Sella-Nasion", ["sella", "s"], ["nasion", "n"]),
                    ("Frankfort Horizontal", ["porion", "po"], ["orbitale", "or"]),
                    ("Mandibular Plane", ["gonion", "go"], ["menton", "me"])
                ]
                
                for plane_name, p1_names, p2_names in planes:
                    lm1 = _get_landmark_by_name(landmarks, p1_names)
                    lm2 = _get_landmark_by_name(landmarks, p2_names)
                    
                    if lm1 and lm2:
                        fig.add_trace(go.Scatter(
                            x=[lm1['x'], lm2['x']],
                            y=[image.height - lm1['y'], image.height - lm2['y']],
                            mode='lines',
                            line=dict(color='rgba(236, 72, 153, 0.6)', width=2, dash='dash'),
                            hoverinfo="text",
                            hovertext=plane_name,
                            name=plane_name
                        ))
            
            # Add Landmarks
            x_coords = [lm.get('x') for lm in landmarks]
            y_coords = [image.height - lm.get('y') for lm in landmarks]
            names = [lm.get('name') for lm in landmarks]
            
            fig.add_trace(go.Scatter(
                x=x_coords,
                y=y_coords,
                mode='markers+text' if show_labels else 'markers',
                marker=dict(size=8, color='#6366f1', line=dict(width=2, color='white')),
                text=[lm.get('name', 'Unknown') for lm in landmarks],
                textposition="top center",
                textfont=dict(color="white", size=10),
                hoverinfo="text",
                hovertext=names,
                name="Landmarks"
            ))
            
            # Use fixed axis range for consistent sizing whether image is shown or not
            fig.update_layout(
                xaxis=dict(visible=False, range=[0, image.width]),
                yaxis=dict(visible=False, range=[0, image.height], scaleanchor="x", scaleratio=1),
                margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                dragmode="pan",
                showlegend=False
            )
            
            st.plotly_chart(fig, use_container_width=True, config={'scrollZoom': True})
        else:
            # Just display the raw image
            if show_image:
                st.image(image, use_container_width=True)
            
        st.markdown("</div>", unsafe_allow_html=True)

def _get_landmark_by_name(landmarks: list, names: list) -> dict:
    for lm in landmarks:
        for name in names:
            if lm.get("name", "").strip().lower() == name.strip().lower():
                return lm
    return None
