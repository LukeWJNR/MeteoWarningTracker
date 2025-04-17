"""
Forecast Animations Page - View and interact with model forecast animations
"""
import streamlit as st
import datetime
import logging
from utils.animation import ForecastAnimation
from utils.web_scraper import get_website_text_content, extract_animation_frames

# Configure logging
logger = logging.getLogger(__name__)

# Initialize animation handler
animation_handler = ForecastAnimation()

# Page configuration
st.set_page_config(
    page_title="Weather Forecast Animations",
    page_icon="🎬",
    layout="wide"
)

# Title and introduction
st.title("🎬 Weather Forecast Animations")
st.markdown("""
This page provides interactive animations of weather forecast model data from various sources.
You can view animations of temperature, precipitation, CAPE, and other parameters from different models.
""")

# Main layout
tab1, tab2 = st.tabs(["MeteoCenter Models", "Lightning Wizard Animations"])

with tab1:
    st.markdown("### MeteoCenter Model Animations")
    st.markdown("Select a model and parameter to view forecast animations.")
    
    # Model and parameter selection
    col1, col2 = st.columns(2)
    
    with col1:
        model = st.selectbox(
            "Select Model",
            ["GDPS", "GFS", "ETA", "HRDPS"],
            index=0
        )
    
    with col2:
        # Different parameter options based on selected model
        if model in ["GDPS", "GFS"]:
            parameter = st.selectbox(
                "Select Parameter",
                ["CAPE", "PCP3", "PCP6", "T850", "SFCT", "MSLP", "Z500", "RH850"],
                index=0
            )
        elif model == "HRDPS":
            parameter = st.selectbox(
                "Select Parameter",
                ["CAPE", "PCP3", "SFCT", "MSLP", "RH850"],
                index=0
            )
        else:  # ETA
            parameter = st.selectbox(
                "Select Parameter",
                ["CAPE", "PCP3", "T850", "SFCT"],
                index=0
            )
    
    # Forecast region
    region = st.selectbox(
        "Select Region",
        ["North America", "Quebec", "Ontario", "Atlantic", "Prairies", "Pacific"],
        index=0
    )
    
    # Generate animation button
    if st.button("Generate MeteoCenter Animation"):
        with st.spinner("Generating animation, please wait..."):
            animation_handler.create_meteocenter_animation(model, parameter)

with tab2:
    st.markdown("### Lightning Wizard Animations")
    st.markdown("""
    This section allows you to view animations from Lightning Wizard.
    You can either enter a Lightning Wizard animation URL or select from predefined animations.
    """)
    
    # Option to input a Lightning Wizard URL
    url_input = st.text_input(
        "Enter Lightning Wizard Animation URL",
        value="https://www.lightningwizard.com/maps/Europe/ani.html?0,gfs_mucape_eur,.png,0,3,6,9,12,15,18,21,24,27,30,33,36,39,42,45,48,51,54,57,60,63,66,69,72",
        help="Example: https://www.lightningwizard.com/maps/Europe/ani.html?0,gfs_mucape_eur,.png,0,3,6,9,12,15,18,21,24,27,30,33,36,39,42,45,48,51,54,57,60,63,66,69,72"
    )
    
    # Option to select predefined animations
    st.markdown("#### Or select a predefined animation:")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("European CAPE"):
            url_input = "https://www.lightningwizard.com/maps/Europe/ani.html?0,gfs_mucape_eur,.png,0,3,6,9,12,15,18,21,24,27,30,33,36,39,42,45,48,51,54,57,60,63,66,69,72"
            st.session_state.animation_url = url_input
    
    with col2:
        if st.button("US Thunderstorm"):
            url_input = "https://www.lightningwizard.com/maps/usa/ani.html?0,gfs_tstm_usa,.png,0,3,6,9,12,15,18,21,24,27,30,33,36,39,42,45,48,51,54,57,60,63,66,69,72"
            st.session_state.animation_url = url_input
    
    with col3:
        if st.button("North America Radar"):
            url_input = "https://www.lightningwizard.com/maps/usa/ani.html?0,gfs_radar_usa,.png,0,3,6,9,12,15,18,21,24,27,30,33,36,39,42,45,48,51,54,57,60,63,66,69,72"
            st.session_state.animation_url = url_input
    
    # URL Analysis Section
    if url_input:
        st.markdown("---")
        st.markdown("### URL Analysis")
        
        # Extract and display parameters from the URL
        animation_info = extract_animation_frames(url_input)
        
        if animation_info:
            # Display animation info as a nice formatted section
            info_col1, info_col2 = st.columns(2)
            
            with info_col1:
                st.markdown(f"**Model:** {animation_info.get('model', 'Unknown')}")
                st.markdown(f"**Parameter:** {animation_info.get('parameter', 'Unknown')}")
                st.markdown(f"**Region:** {animation_info.get('region', 'Unknown')}")
            
            with info_col2:
                st.markdown(f"**Total Frames:** {len(animation_info.get('frames', []))}")
                st.markdown(f"**Forecast Range:** {min(animation_info.get('forecast_hours', [0]))}h to {max(animation_info.get('forecast_hours', [0]))}h")
                st.markdown(f"**Image Format:** {animation_info.get('extension', 'Unknown')}")
        
        # Button to generate the animation
        if st.button("Generate Lightning Wizard Animation"):
            with st.spinner("Generating animation, please wait..."):
                animation_handler.create_lightning_wizard_animation(url_input)
    
    st.markdown("---")
    st.caption("Animation data provided by Lightning Wizard and MeteoCenter. This tool analyzes and displays publicly available forecast images.")

# Footer
st.markdown("---")
st.markdown("Weather Forecast Animation Viewer | Developed for comprehensive severe weather analysis")