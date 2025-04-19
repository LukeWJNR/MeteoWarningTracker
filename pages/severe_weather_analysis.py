"""
Severe Weather Analysis - Advanced meteorological parameters using SHARPpy
"""
import streamlit as st

# Page configuration must be first Streamlit command
st.set_page_config(
    page_title="Severe Weather Analysis",
    page_icon="⚡",
    layout="wide"
)

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from utils.sharppy_analysis import severe_weather_analyzer
import folium
from streamlit_folium import folium_static
import io
import matplotlib.pyplot as plt
from utils.data_fetcher import MeteoDataFetcher
import requests

# Title and introduction
st.title("⚡ Severe Weather Analysis")
st.markdown("""
This page provides advanced meteorological analysis using SHARPpy, a professional-grade 
sounding and profile analysis toolkit used by meteorologists and severe weather forecasters.
""")

# Check if SHARPpy is available
if not severe_weather_analyzer.check_availability():
    st.warning("SHARPpy is not fully available. Some functionality may be limited.")

# Location selection
st.sidebar.header("Location Settings")

# Get location from session state or use default
if 'location' in st.session_state:
    default_lat = st.session_state.location["lat"]
    default_lon = st.session_state.location["lon"]
    default_location_name = st.session_state.location["display_name"]
else:
    # Default to Montreal
    default_lat = 45.5017
    default_lon = -73.5673
    default_location_name = "Montreal, Quebec, Canada"

# Import geocode function from app.py
import sys
sys.path.append('./')  # Add root directory to path
try:
    from app import geocode_location
except ImportError:
    # If import fails, define a basic geocode function
    def geocode_location(location_name):
        import requests
        try:
            url = f"https://nominatim.openstreetmap.org/search?q={location_name}&format=json&limit=1"
            response = requests.get(url, headers={"User-Agent": "Weather App"})
            data = response.json()
            if data:
                return {
                    "lat": float(data[0]["lat"]),
                    "lon": float(data[0]["lon"]),
                    "display_name": data[0]["display_name"]
                }
            return None
        except Exception as e:
            st.error(f"Error geocoding location: {e}")
            return None

# Location search interface
location_input = st.sidebar.text_input("Search Location", value=default_location_name)
search_button = st.sidebar.button("Search Location")

if search_button and location_input:
    with st.sidebar.spinner("Searching location..."):
        geocoded = geocode_location(location_input)
        if geocoded:
            st.session_state.location = geocoded
            st.sidebar.success(f"Found: {geocoded['display_name']}")
            st.rerun()  # Rerun the app with the new location
        else:
            st.sidebar.error("Location not found. Please try a different search term.")

# Display current coordinates (but don't allow direct editing)
st.sidebar.markdown(f"**Current Coordinates:** {default_lat:.4f}, {default_lon:.4f}")

# Store the coordinates in variables for use in the analysis
lat = default_lat
lon = default_lon
location_name = default_location_name

# Model selection
model_options = ["GFS", "NAM", "HRRR", "RAP"]
selected_model = st.sidebar.selectbox("Forecast Model", options=model_options)

# Profile time selection - create options for forecast hours
current_time = datetime.utcnow()
forecast_hours = list(range(0, 121, 3))  # 0 to 120 hours, every 3 hours
forecast_times = [current_time + timedelta(hours=h) for h in forecast_hours]
time_options = [f"+{h}h ({t.strftime('%Y-%m-%d %HZ')})" for h, t in zip(forecast_hours, forecast_times)]

selected_time_idx = st.sidebar.selectbox("Forecast Time", options=range(len(time_options)), format_func=lambda x: time_options[x])
selected_hour = forecast_hours[selected_time_idx]

# Load button
load_button = st.sidebar.button("Load Data", type="primary")

# Containers for the analysis sections
profile_container = st.container()
parameters_container = st.container()
threat_container = st.container()
map_container = st.container()

# Load and analyze data when requested
if load_button:
    with st.spinner(f"Loading {selected_model} data for {lat:.4f}, {lon:.4f}..."):
        # Load data from NCEP
        success = severe_weather_analyzer.load_model_data_from_ncep(lat, lon, model=selected_model)
        
        if success:
            st.success(f"Data loaded for {location_name} ({selected_model}, +{selected_hour}h forecast)")
            
            # Get the analysis results
            analysis = severe_weather_analyzer.latest_analysis
            summary = severe_weather_analyzer.extract_severe_weather_summary()
            threat = severe_weather_analyzer.get_severe_weather_threat()
            
            # Display the results
            with profile_container:
                st.header("Atmospheric Profile")
                
                col1, col2 = st.columns([3, 2])
                
                with col1:
                    # Generate and display SkewT plot
                    skewt_plot = severe_weather_analyzer.generate_skewt_plot()
                    if skewt_plot:
                        st.image(skewt_plot, caption="SkewT-LogP Diagram", use_column_width=True)
                    else:
                        st.warning("Could not generate SkewT plot")
                
                with col2:
                    # Show basic thermodynamic info
                    st.subheader("Basic Thermodynamic Parameters")
                    
                    # Create a clean table for thermodynamic parameters
                    thermo_data = {
                        "Parameter": ["Surface CAPE", "ML CAPE (0-1km)", "MU CAPE", "Surface CIN", "ML CIN", "MU CIN"],
                        "Value": [
                            f"{summary['cape']['surface']} J/kg",
                            f"{summary['cape']['mixed_layer']} J/kg",
                            f"{summary['cape']['most_unstable']} J/kg",
                            f"{summary['cin']['surface']} J/kg",
                            f"{summary['cin']['mixed_layer']} J/kg",
                            f"{summary['cin']['most_unstable']} J/kg"
                        ]
                    }
                    st.table(pd.DataFrame(thermo_data))
                    
                    st.subheader("Height Parameters")
                    height_data = {
                        "Parameter": ["Surface LCL", "ML LCL", "MU LCL", "0-6km Shear", "0-1km Shear"],
                        "Value": [
                            f"{summary['lcl_height']['surface']} m",
                            f"{summary['lcl_height']['mixed_layer']} m",
                            f"{summary['lcl_height']['most_unstable']} m",
                            f"{summary['shear']['0_6km']} kts",
                            f"{summary['shear']['0_1km']} kts"
                        ]
                    }
                    st.table(pd.DataFrame(height_data))
            
            with parameters_container:
                st.header("Advanced Parameters")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.subheader("Severe Weather Indices")
                    indices_data = {
                        "Parameter": ["STP", "SCP", "LI", "K-Index", "Total Totals"],
                        "Value": [
                            f"{summary['indices']['stp']:.2f}",
                            f"{summary['indices']['scp']:.2f}",
                            f"{summary['indices']['li']:.1f}",
                            f"{summary['indices']['k_index']:.1f}",
                            f"{summary['indices']['totals']:.1f}"
                        ]
                    }
                    st.table(pd.DataFrame(indices_data))
                
                with col2:
                    st.subheader("Wind/Shear Parameters")
                    wind_data = {
                        "Parameter": ["0-1km SRH", "0-3km SRH", "0-3km Shear", "Effective Shear"],
                        "Value": [
                            f"{summary['helicity']['0_1km']} m²/s²",
                            f"{summary['helicity']['0_3km']} m²/s²",
                            f"{summary['shear']['0_3km']} kts",
                            f"{summary['shear']['0_6km']} kts"
                        ]
                    }
                    st.table(pd.DataFrame(wind_data))
                
                with col3:
                    st.subheader("Thermodynamic Environment")
                    env_data = {
                        "Parameter": ["PWAT", "0-3km Lapse Rate", "700-500mb Lapse Rate"],
                        "Value": [
                            f"{summary['moisture']['pwat']:.2f} mm",
                            f"{summary['lapse_rates']['0_3km']:.1f} °C/km",
                            f"{summary['lapse_rates']['700_500mb']:.1f} °C/km"
                        ]
                    }
                    st.table(pd.DataFrame(env_data))
            
            with threat_container:
                st.header("Severe Weather Threats")
                
                # Create color-coded threat levels
                def get_threat_color(level):
                    if level == "high":
                        return "#ff4b4b"
                    elif level == "moderate":
                        return "#ffa500"
                    elif level == "slight":
                        return "#ffff00"
                    else:
                        return "#00ff00"
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    tornado_level = threat['tornado']['level']
                    st.markdown(f"""
                    <div style="background-color: {get_threat_color(tornado_level)}; padding: 10px; border-radius: 5px;">
                        <h3 style="margin-top: 0;">Tornado Threat</h3>
                        <p><strong>Level:</strong> {tornado_level.upper()}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if threat['tornado']['factors']:
                        st.markdown("**Key Factors:**")
                        for factor in threat['tornado']['factors']:
                            st.markdown(f"- {factor}")
                
                with col2:
                    hail_level = threat['hail']['level']
                    st.markdown(f"""
                    <div style="background-color: {get_threat_color(hail_level)}; padding: 10px; border-radius: 5px;">
                        <h3 style="margin-top: 0;">Hail Threat</h3>
                        <p><strong>Level:</strong> {hail_level.upper()}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if threat['hail']['factors']:
                        st.markdown("**Key Factors:**")
                        for factor in threat['hail']['factors']:
                            st.markdown(f"- {factor}")
                
                with col3:
                    wind_level = threat['wind']['level']
                    st.markdown(f"""
                    <div style="background-color: {get_threat_color(wind_level)}; padding: 10px; border-radius: 5px;">
                        <h3 style="margin-top: 0;">Wind Threat</h3>
                        <p><strong>Level:</strong> {wind_level.upper()}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if threat['wind']['factors']:
                        st.markdown("**Key Factors:**")
                        for factor in threat['wind']['factors']:
                            st.markdown(f"- {factor}")
                
                with col4:
                    flood_level = threat['flash_flood']['level']
                    st.markdown(f"""
                    <div style="background-color: {get_threat_color(flood_level)}; padding: 10px; border-radius: 5px;">
                        <h3 style="margin-top: 0;">Flash Flood Threat</h3>
                        <p><strong>Level:</strong> {flood_level.upper()}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    if threat['flash_flood']['factors']:
                        st.markdown("**Key Factors:**")
                        for factor in threat['flash_flood']['factors']:
                            st.markdown(f"- {factor}")
            
            with map_container:
                st.header("Regional Parameter Maps")
                
                # Map parameter selection
                map_params = [
                    {"name": "CAPE (Surface-Based)", "value": "sfcape"},
                    {"name": "CAPE (Most Unstable)", "value": "mucape"},
                    {"name": "CIN (Surface-Based)", "value": "sfcin"},
                    {"name": "0-6km Shear", "value": "sfc_6km_shear"},
                    {"name": "Significant Tornado Parameter", "value": "stp"},
                    {"name": "Supercell Composite Parameter", "value": "scp"},
                    {"name": "0-3km Storm Relative Helicity", "value": "srh3km"},
                    {"name": "Lifted Index", "value": "li"},
                    {"name": "K-Index", "value": "k_index"},
                    {"name": "Precipitable Water", "value": "pwat"}
                ]
                
                selected_param = st.selectbox(
                    "Select Parameter for Map",
                    options=[p["value"] for p in map_params],
                    format_func=lambda x: next((p["name"] for p in map_params if p["value"] == x), x)
                )
                
                # Here we would normally fetch a grid of the selected parameter
                # Since we don't have that functionality yet, we'll show a placeholder map
                
                st.info("These maps would normally show regional parameter grids from model data. This is a placeholder for future implementation.")
                
                # Create a basic folium map centered on the selected location
                m = folium.Map(location=[lat, lon], zoom_start=6, tiles='CartoDB positron')
                
                # Add a marker for the analysis point
                folium.Marker(
                    location=[lat, lon],
                    popup=f"Analysis Point: {location_name}",
                    icon=folium.Icon(color='red', icon='info-sign')
                ).add_to(m)
                
                # Display the map
                folium_static(m, width=1000)
                
                # Note about grid data
                st.markdown("""
                **Note:** In a complete implementation, this section would display parameter 
                grids and contours for the selected parameter across a region. This would 
                require accessing model grid data from NCEP or similar sources.
                """)
        else:
            st.error("Failed to load or analyze data. Please try again with a different location or model.")

# Footer with help information
st.markdown("---")
with st.expander("About SHARPpy Analysis"):
    st.markdown("""
    ### SHARPpy (Sounding and Hodograph Analysis and Research Program in Python)
    
    SHARPpy is a collection of open-source meteorological analysis tools originally 
    developed at the NOAA Storm Prediction Center (SPC) and the University of Oklahoma. 
    It provides a robust framework for analyzing atmospheric soundings, calculating severe 
    weather parameters, and visualizing meteorological data.
    
    ### Parameter Glossary
    
    - **CAPE (Convective Available Potential Energy)**: Measures the amount of energy available for convection, with higher values indicating stronger updraft potential.
      - Surface-based (SBCAPE): CAPE using a parcel from the surface
      - Mixed-layer (MLCAPE): CAPE using a parcel averaged over the lowest 1km
      - Most-unstable (MUCAPE): CAPE using the most unstable parcel in the lowest 300mb
      
    - **CIN (Convective Inhibition)**: Negative energy that must be overcome for thunderstorm initiation.
    
    - **LCL (Lifting Condensation Level)**: Height at which a rising air parcel becomes saturated.
    
    - **LFC (Level of Free Convection)**: Height at which a rising air parcel becomes positively buoyant.
    
    - **EL (Equilibrium Level)**: Height at which a rising air parcel becomes neutrally buoyant, approximating thunderstorm tops.
    
    - **Wind Shear**: Change in wind speed and/or direction with height.
      - 0-1km shear: Important for tornado potential
      - 0-6km shear: Important for supercell organization
      
    - **Storm-Relative Helicity (SRH)**: Measure of the streamwise vorticity, important for assessing tornado potential.
    
    - **Significant Tornado Parameter (STP)**: Composite parameter indicating the potential for significant tornadoes.
    
    - **Supercell Composite Parameter (SCP)**: Composite parameter indicating the potential for supercell thunderstorms.
    
    - **Lifted Index (LI)**: Stability index where negative values indicate instability.
    
    - **K-Index**: Measures thunderstorm potential based on temperature lapse rate, moisture content, and depth.
    
    - **Precipitable Water (PWAT)**: Total atmospheric water vapor in a column, related to heavy rainfall potential.
    """)

# Add information about meteorologist-grade analysis
with st.expander("Advanced Meteorological Parameters"):
    st.markdown("""
    ### Advanced Meteorological Parameters
    
    This page can be expanded to include more complex meteorological parameters as listed below:
    
    - **MSL Pressure, 500 hPa Height**: Base state of the atmosphere and large-scale features
    - **Mixed-Layer CAPE (lowest 1000m parcel)**: Convective energy using a well-mixed parcel
    - **Most Unstable CAPE (500m AGL to 700 hPa Parcel)**: Convective energy for elevated instability
    - **Parcel to -10°C Level Bulk Shear**: Relevant for hail and severe potential
    - **Advection of Geostrophic Vorticity by the Thermal Wind**: Vertical motion at 600 hPa
    - **PVU Level Potential Temperature (Dynamic Tropopause)**: Tropopause dynamics and folds
    - **Differential Theta-W advection**: Warm/cold air advection patterns
    - **500-300 hPa Divergence**: Upper-level support for vertical motion
    - **Equilibrium Level Convective Cloud Top Temperature**: Potential cloud top heights
    - **Thompson Index**: Combined instability and moisture parameter
    - **Convective Precipitation**: Model-predicted convective rainfall
    - **0-2 km Low Level CAPE**: Lower tropospheric instability important for severe weather
    - **Surface-500 meter AGL Temperature Lapse Rate**: Near-surface instability
    - **Wetbulb Potential Temperature / Equivalent Potential Temperature**: Conserved thermodynamic properties
    - **0-6 km Deep Layer Shear, 0-1 km Low Level Shear**: Important for storm organization and tornadoes
    - **Significant Tornado Parameter**: Composite index for significant tornado potential
    - **Storm-Relative Helicity (SRH)**: Rotational potential in storm environments
    - **Cold cloud (-10°C to -30°C) - Warm cloud Buoyancy Difference**: Large hail parameter
    - **Effective Precipitable Water, MCS Propagation Vectors**: Heavy rainfall and MCS forecasting
    - **Moisture Transport Vectors, Orographic Lifting**: Moisture advection and terrain interactions
    """)