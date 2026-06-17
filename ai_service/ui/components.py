import streamlit as st

def apply_global_styles():
    """Inject premium, modern CSS using glassmorphism and rich aesthetics."""
    custom_css = """
    <style>
        /* Import Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        /* Global Font and Background styling */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif !important;
        }
        
        .stApp {
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            color: #f8fafc;
        }

        /* Top Header Styling */
        header[data-testid="stHeader"] {
            background-color: transparent !important;
            box-shadow: none !important;
        }
        
        /* Glassmorphism Sidebar */
        section[data-testid="stSidebar"] {
            background-color: rgba(15, 23, 42, 0.6) !important;
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border-right: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        /* Metric Cards */
        div[data-testid="stMetric"] {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 1rem;
            backdrop-filter: blur(10px);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        div[data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2), 0 4px 6px -2px rgba(0, 0, 0, 0.1);
            border-color: rgba(99, 102, 241, 0.5); /* Indigo hover */
        }
        
        /* Tabs styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 12px;
            background-color: transparent;
        }
        .stTabs [data-baseweb="tab"] {
            background-color: rgba(255, 255, 255, 0.05);
            border-radius: 8px 8px 0 0;
            padding: 10px 20px;
            border: none !important;
            color: #cbd5e1;
            font-weight: 500;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(180deg, rgba(99, 102, 241, 0.2) 0%, rgba(99, 102, 241, 0) 100%);
            color: #fff !important;
            border-bottom: 2px solid #6366f1 !important;
        }
        
        /* Buttons */
        .stButton>button {
            background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            color: white;
            border: none;
            border-radius: 8px;
            padding: 0.5rem 1rem;
            font-weight: 600;
            transition: all 0.3s ease;
            box-shadow: 0 4px 14px 0 rgba(99, 102, 241, 0.39);
        }
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(99, 102, 241, 0.23);
            background: linear-gradient(135deg, #4f46e5 0%, #4338ca 100%);
            color: white;
        }
        
        /* Dataframes */
        .stDataFrame {
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            overflow: hidden;
        }
        
        /* Title Gradients */
        h1, h2, h3 {
            background: -webkit-linear-gradient(45deg, #818cf8, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        h1 {
            font-weight: 700 !important;
            letter-spacing: -0.02em;
        }
        
        /* Hide streamlit watermark */
        footer {visibility: hidden;}
    </style>
    """
    st.markdown(custom_css, unsafe_allow_html=True)

def apply_light_mode():
    """Optional override for light mode (Not used by default since dark is premium)."""
    # Placeholder in case we want a toggle later
    pass

def render_header():
    """Render the main application header."""
    st.markdown(
        """
        <div style="margin-bottom: 2rem;">
            <h1 style="font-size: 2.5rem; margin-bottom: 0.5rem;">🦷 CephAI Diagnostic Studio</h1>
            <p style="color: #94a3b8; font-size: 1.1rem; max-width: 600px;">
                Advanced AI-powered cephalometric landmark detection and orthodontic analysis. 
                Upload an X-ray to generate precision measurements, diagnostics, and treatment plans.
            </p>
        </div>
        """, 
        unsafe_allow_html=True
    )
