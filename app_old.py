"""
Main Streamlit application for Administration Automation.
Dutch Freelance Companies Receipt Processing and Tax Calculation System.
"""

import streamlit as st
from streamlit_option_menu import option_menu
import logging
from pathlib import Path
import sys

# Add project root to path
sys.path.append(str(Path(__file__).parent))

from config import Config
from pages import (
    dashboard,
    upload_receipts,
    receipt_management,
    analytics,
    export_reports,
    settings
)
from utils.auth import check_authentication, login_page
from utils.session_state import init_session_state

# Configure logging
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title=f"{Config.APP_NAME} - Administratie Automatisering",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': 'https://github.com/yourusername/admin-automation',
        'Report a bug': "https://github.com/yourusername/admin-automation/issues",
        'About': f"""
        ## {Config.APP_NAME}
        Version: {Config.APP_VERSION}

        Intelligent administration automation for Dutch freelancers.
        Automate receipt processing, VAT calculations, and income tax preparation.
        """
    }
)

# Custom CSS for better UI
def load_css():
    """Load custom CSS styles."""
    st.markdown("""
        <style>
        /* Main content area */
        .main {
            padding: 1rem;
        }

        /* Sidebar styling */
        .css-1d391kg {
            padding-top: 1rem;
        }

        /* Headers */
        h1 {
            color: #1f4788;
            font-weight: 600;
        }

        h2 {
            color: #2d5aa0;
            font-weight: 500;
        }

        h3 {
            color: #3a6cb5;
            font-weight: 500;
        }

        /* Metrics styling */
        [data-testid="metric-container"] {
            background-color: #f0f2f6;
            border: 1px solid #d3dae8;
            padding: 1rem;
            border-radius: 0.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }

        /* Success message */
        .success-message {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #d4edda;
            border: 1px solid #c3e6cb;
            color: #155724;
        }

        /* Warning message */
        .warning-message {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #fff3cd;
            border: 1px solid #ffeeba;
            color: #856404;
        }

        /* Error message */
        .error-message {
            padding: 1rem;
            border-radius: 0.5rem;
            background-color: #f8d7da;
            border: 1px solid #f5c6cb;
            color: #721c24;
        }

        /* Upload area */
        [data-testid="stFileUploader"] {
            border: 2px dashed #3a6cb5;
            border-radius: 0.5rem;
            padding: 2rem;
        }

        /* Buttons */
        .stButton > button {
            background-color: #1f4788;
            color: white;
            border-radius: 0.5rem;
            border: none;
            padding: 0.5rem 1rem;
            font-weight: 500;
            transition: all 0.3s;
        }

        .stButton > button:hover {
            background-color: #2d5aa0;
            box-shadow: 0 2px 5px rgba(0,0,0,0.2);
        }

        /* Data tables */
        .dataframe {
            font-size: 0.9rem;
        }

        /* Navigation menu */
        .nav-link {
            color: #1f4788 !important;
        }

        .nav-link-selected {
            background-color: #e3f2fd !important;
        }
        </style>
    """, unsafe_allow_html=True)

def main():
    """Main application entry point."""

    # Initialize session state
    init_session_state()

    # Load custom CSS
    load_css()

    # Check authentication (disabled for initial development)
    # if not check_authentication():
    #     login_page()
    #     return

    # Sidebar with navigation
    with st.sidebar:
        st.title(f"🧾 {Config.APP_NAME}")
        st.markdown("---")

        # User info (placeholder for now)
        st.markdown("👤 **Gebruiker:** Demo User")
        st.markdown("🏢 **Bedrijf:** Demo Company")
        st.markdown("---")

        # Navigation menu
        selected = option_menu(
            menu_title="Navigatie",
            options=[
                "Dashboard",
                "Upload Bonnen",
                "Bonnen Beheer",
                "Analytics",
                "Export/Rapporten",
                "Instellingen"
            ],
            icons=[
                "speedometer2",
                "cloud-upload",
                "file-earmark-text",
                "graph-up",
                "file-earmark-arrow-down",
                "gear"
            ],
            menu_icon="list",
            default_index=0,
            styles={
                "container": {"padding": "5!important", "background-color": "#fafafa"},
                "icon": {"color": "#1f4788", "font-size": "20px"},
                "nav-link": {
                    "font-size": "16px",
                    "text-align": "left",
                    "margin": "0px",
                    "color": "#1f4788",
                },
                "nav-link-selected": {"background-color": "#e3f2fd"},
            }
        )

        # Footer info
        st.markdown("---")
        st.markdown(f"**Versie:** {Config.APP_VERSION}")
        st.markdown("**© 2025** - Alle rechten voorbehouden")

    # Main content area
    if selected == "Dashboard":
        dashboard.show()
    elif selected == "Upload Bonnen":
        upload_receipts.show()
    elif selected == "Bonnen Beheer":
        receipt_management.show()
    elif selected == "Analytics":
        analytics.show()
    elif selected == "Export/Rapporten":
        export_reports.show()
    elif selected == "Instellingen":
        settings.show()

if __name__ == "__main__":
    try:
        # Validate configuration on startup
        # Config.validate()  # Disabled for initial development

        # Initialize database
        from database.connection import init_db
        init_db()

        # Run the app
        main()

    except Exception as e:
        logger.error(f"Application startup error: {e}")
        st.error(f"Er is een fout opgetreden bij het starten van de applicatie: {e}")
        st.stop()