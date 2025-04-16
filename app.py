import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import folium_static
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
from sqlalchemy import text
from utils.data_fetcher import MeteoDataFetcher
from utils.data_processor import WeatherDataProcessor
from utils.visualizations import WeatherVisualizer
from utils.database import db
import json
import requests
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
data_fetcher = MeteoDataFetcher()
data_processor = WeatherDataProcessor()
visualizer = WeatherVisualizer()

# Page configuration
st.set_page_config(
    page_title="Weather Forecast | MeteoCenter GDPS",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Helper functions for geocoding
def geocode_location(location_name):
    """Convert a location name to lat/lon coordinates"""
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={location_name}&format=json&limit=1"
        response = requests.get(url, headers={"User-Agent": "WeatherForecastApp/1.0"})
        data = response.json()
        if data and len(data) > 0:
            return {
                "lat": float(data[0]["lat"]),
                "lon": float(data[0]["lon"]),
                "display_name": data[0]["display_name"]
            }
        return None
    except Exception as e:
        st.error(f"Error geocoding location: {e}")
        return None

@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_and_process_data(lat, lon, parameter, forecast_hours=72):
    """Fetch and process weather data for a parameter"""
    try:
        df = data_fetcher.fetch_gdps_data(parameter, lat, lon, forecast_hours)
        
        # Process based on parameter type
        if parameter == "TMP_TGL_2":
            return data_processor.process_temperature_data(df)
        elif parameter == "APCP_SFC":
            return data_processor.process_precipitation_data(df)
        elif parameter == "WIND_TGL_10":
            return data_processor.process_wind_data(df)
        else:
            return df
    except Exception as e:
        logger.error(f"Error fetching data for {parameter}: {e}")
        # For demo/testing only - would be removed in production
        return data_fetcher.generate_sample_data(parameter, forecast_hours)

@st.cache_data(ttl=3600)
def fetch_weather_warnings(lat, lon, radius_km=50):
    """Fetch severe weather warnings"""
    try:
        return data_fetcher.fetch_severe_warnings(lat, lon, radius_km)
    except Exception as e:
        logger.error(f"Error fetching weather warnings: {e}")
        return []

@st.cache_data(ttl=3600)
def fetch_grid_data(parameter, lat, lon, forecast_hour=24):
    """Fetch gridded data for map visualization"""
    try:
        # Create a bounding box around the location
        margin = 1.0  # Degrees
        bbox = (lon - margin, lat - margin, lon + margin, lat + margin)
        return data_fetcher.fetch_grid_data(parameter, bbox, forecast_hour)
    except Exception as e:
        logger.error(f"Error fetching grid data: {e}")
        return None

# Define initialization for session state
if 'location' not in st.session_state:
    st.session_state.location = {
        "lat": 45.5017,  # Montreal coordinates as default
        "lon": -73.5673,
        "display_name": "Montreal, Quebec, Canada"
    }

if 'forecast_hours' not in st.session_state:
    st.session_state.forecast_hours = 72

if 'selected_parameter' not in st.session_state:
    st.session_state.selected_parameter = "TMP_TGL_2"

if 'forecast_hour_for_map' not in st.session_state:
    st.session_state.forecast_hour_for_map = 24

# Title and introduction
st.title("GDPS 15km Weather Forecast")
st.markdown("### Global Deterministic Prediction System - Comprehensive Weather Data")
st.markdown("This application provides detailed forecast visualizations from the Global Deterministic Prediction System (GDPS) 15km model, with access to over 30 meteorological parameters at various atmospheric levels.")

# Sidebar for location search and configuration
with st.sidebar:
    st.header("Location Settings")
    
    # Location search
    location_input = st.text_input("Search Location", 
                                  value=st.session_state.location["display_name"] if "display_name" in st.session_state.location else "")
    
    search_button = st.button("Search")
    
    if search_button and location_input:
        with st.spinner("Searching location..."):
            geocoded = geocode_location(location_input)
            if geocoded:
                st.session_state.location = geocoded
                st.success(f"Found: {geocoded['display_name']}")
            else:
                st.error("Location not found. Please try a different search term.")
    
    # Forecast time range
    st.header("Forecast Settings")
    
    forecast_hours = st.select_slider(
        "Forecast Hours",
        options=[24, 48, 72, 96, 120, 144, 168],
        value=st.session_state.forecast_hours
    )
    
    if forecast_hours != st.session_state.forecast_hours:
        st.session_state.forecast_hours = forecast_hours
    
    # Parameter for map visualization
    st.header("Map Settings")
    
    map_params = [
        # Temperature parameters
        {"code": "TMP_TGL_2", "name": "Temperature (2m)"},
        {"code": "TMP_TGL_0", "name": "Surface Temperature"},
        {"code": "TMP_ISBL_500", "name": "Temperature at 500 hPa"},
        {"code": "TMP_ISBL_850", "name": "Temperature at 850 hPa"},
        {"code": "TMAX_TGL_2", "name": "Max Temperature (2m)"},
        {"code": "TMIN_TGL_2", "name": "Min Temperature (2m)"},
        
        # Precipitation parameters
        {"code": "APCP_SFC", "name": "Total Precipitation"},
        {"code": "ACPCP_SFC", "name": "Convective Precipitation"},
        {"code": "SNOD_SFC", "name": "Snow Depth"},
        {"code": "CRAIN_SFC", "name": "Categorical Rain"},
        {"code": "CSNOW_SFC", "name": "Categorical Snow"},
        
        # Wind parameters
        {"code": "WIND_TGL_10", "name": "Wind Speed (10m)"},
        {"code": "WDIR_TGL_10", "name": "Wind Direction (10m)"},
        {"code": "GUST_TGL_10", "name": "Wind Gust (10m)"},
        {"code": "WIND_ISBL_250", "name": "Wind Speed (250 hPa)"},
        
        # Pressure parameters
        {"code": "PRMSL_MSL", "name": "Sea Level Pressure"},
        {"code": "PRES_SFC", "name": "Surface Pressure"},
        {"code": "HGT_ISBL_500", "name": "500 hPa Height"},
        
        # Humidity parameters
        {"code": "RH_TGL_2", "name": "Relative Humidity (2m)"},
        {"code": "RH_ISBL_700", "name": "Relative Humidity (700 hPa)"},
        {"code": "PWAT_EATM", "name": "Precipitable Water"},
        
        # Cloud parameters
        {"code": "TCDC_SFC", "name": "Total Cloud Cover"},
        {"code": "LCDC_LOW", "name": "Low Cloud Cover"},
        {"code": "MCDC_MID", "name": "Medium Cloud Cover"},
        {"code": "HCDC_HIGH", "name": "High Cloud Cover"},
        
        # Severe weather parameters
        {"code": "CAPE_SFC", "name": "CAPE"},
        {"code": "CIN_SFC", "name": "CIN"},
        {"code": "LFTX_SFC", "name": "Lifted Index"},
    ]
    
    selected_param = st.selectbox(
        "Select Parameter for Map",
        options=[p["code"] for p in map_params],
        format_func=lambda x: next((p["name"] for p in map_params if p["code"] == x), x),
        index=0
    )
    
    forecast_hour_for_map = st.slider(
        "Forecast Hour for Map",
        min_value=0,
        max_value=st.session_state.forecast_hours,
        value=min(24, st.session_state.forecast_hours),
        step=6
    )
    
    st.session_state.selected_parameter = selected_param
    st.session_state.forecast_hour_for_map = forecast_hour_for_map
    
    # Additional parameter selection for charts
    st.header("Chart Settings")
    
    # Group parameters by type
    param_groups = {
        "Temperature": [p for p in map_params if any(x in p["code"] for x in ["TMP", "TMAX", "TMIN"])],
        "Precipitation": [p for p in map_params if any(x in p["code"] for x in ["PCP", "SNOW", "RAIN"])],
        "Wind": [p for p in map_params if any(x in p["code"] for x in ["WIND", "WDIR", "GUST", "UGRD", "VGRD"])],
        "Pressure": [p for p in map_params if any(x in p["code"] for x in ["PRMSL", "PRES", "HGT"])],
        "Humidity": [p for p in map_params if any(x in p["code"] for x in ["RH", "SPFH", "PWAT"])],
        "Clouds": [p for p in map_params if "CDC" in p["code"]],
        "Severe Weather": [p for p in map_params if any(x in p["code"] for x in ["CAPE", "CIN", "LFTX"])]
    }
    
    # Create a multi-select for additional parameters
    selected_group = st.selectbox(
        "Parameter Category",
        options=list(param_groups.keys()),
        index=0
    )
    
    if selected_group in param_groups:
        additional_params = st.multiselect(
            "Additional Parameters to Chart",
            options=[p["code"] for p in param_groups[selected_group]],
            default=[],
            format_func=lambda x: next((p["name"] for p in map_params if p["code"] == x), x)
        )
        
        if additional_params:
            st.session_state.additional_params = additional_params
        elif 'additional_params' not in st.session_state:
            st.session_state.additional_params = []
    
    # Database/Cache section
    st.header("Database Cache")
    
    # Get recent locations from database
    recent_locations = db.get_recent_locations(limit=5)
    
    if recent_locations:
        st.markdown("#### Recently Searched Locations")
        for loc in recent_locations:
            if st.button(f"{loc['name']}", key=f"loc_{loc['id']}"):
                st.session_state.location = {
                    "lat": loc['lat'],
                    "lon": loc['lon'],
                    "display_name": loc['name']
                }
                st.rerun()
    
    # Display model run info
    latest_run = db.get_latest_model_run("GDPS")
    if latest_run:
        st.markdown(f"**Latest GDPS Model Run:** {latest_run.strftime('%Y-%m-%d %H:%M UTC')}")
    
    # Database statistics
    with st.expander("Database Statistics"):
        # Get database stats
        try:
            with db.engine.connect() as connection:
                # Count of locations
                location_count = connection.execute(
                    text("SELECT COUNT(*) FROM locations")
                ).scalar()
                
                # Count of forecast data points
                forecast_count = connection.execute(
                    text("SELECT COUNT(*) FROM forecast_data")
                ).scalar()
                
                # Count of warnings
                warning_count = connection.execute(
                    text("SELECT COUNT(*) FROM weather_warnings")
                ).scalar()
                
                # Count of model runs
                model_run_count = connection.execute(
                    text("SELECT COUNT(*) FROM model_runs")
                ).scalar()
                
                # Recent parameter distribution
                parameter_dist = connection.execute(
                    text("""
                        SELECT parameter_code, COUNT(*) as count
                        FROM forecast_data
                        GROUP BY parameter_code
                        ORDER BY count DESC
                        LIMIT 5
                    """)
                ).fetchall()
                
                # Display stats
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Locations Stored", location_count)
                    st.metric("Model Runs Tracked", model_run_count)
                
                with col2:
                    st.metric("Forecast Data Points", forecast_count)
                    st.metric("Weather Warnings", warning_count)
                
                # Parameter distribution
                if parameter_dist:
                    st.markdown("#### Parameters in Database")
                    param_data = pd.DataFrame(parameter_dist, columns=["Parameter", "Count"])
                    st.bar_chart(param_data.set_index("Parameter"))
                
        except Exception as e:
            st.error(f"Error fetching database statistics: {e}")
    
    # Cache clear button
    if st.button("Clear Old Forecast Data (>7 days)"):
        success = db.clear_old_data(days_to_keep=7)
        if success:
            st.success("Successfully cleared old forecast data")
        else:
            st.error("Failed to clear old data")
    
    # About section
    st.header("About")
    st.markdown("""
    This application provides comprehensive access to all parameters from the Global Deterministic Prediction System (GDPS 15km):
    
    - 30+ meteorological parameters at multiple atmospheric levels
    - Global coverage with 15km horizontal resolution
    - Supports forecasts up to 168 hours (7 days) ahead
    - Detailed visualizations of temperature, precipitation, wind, pressure, and more
    - Severe weather warning detection
    - PostgreSQL database caching for improved performance
    """)

# Main content
# Display current location
st.markdown(f"### Forecast for: **{st.session_state.location['display_name']}**")
st.markdown(f"Coordinates: {st.session_state.location['lat']:.4f}, {st.session_state.location['lon']:.4f}")

# Display loading message
with st.spinner("Fetching weather data..."):
    # Fetch data for main parameters
    data = {
        "TMP_TGL_2": fetch_and_process_data(
            st.session_state.location["lat"], 
            st.session_state.location["lon"], 
            "TMP_TGL_2", 
            st.session_state.forecast_hours
        ),
        "APCP_SFC": fetch_and_process_data(
            st.session_state.location["lat"], 
            st.session_state.location["lon"], 
            "APCP_SFC", 
            st.session_state.forecast_hours
        ),
        "WIND_TGL_10": fetch_and_process_data(
            st.session_state.location["lat"], 
            st.session_state.location["lon"], 
            "WIND_TGL_10", 
            st.session_state.forecast_hours
        ),
        "RH_TGL_2": fetch_and_process_data(
            st.session_state.location["lat"], 
            st.session_state.location["lon"], 
            "RH_TGL_2", 
            st.session_state.forecast_hours
        )
    }
    
    # Fetch additional parameters if any are selected
    if 'additional_params' in st.session_state and st.session_state.additional_params:
        for param in st.session_state.additional_params:
            if param not in data:  # Only fetch if not already in data
                data[param] = fetch_and_process_data(
                    st.session_state.location["lat"],
                    st.session_state.location["lon"],
                    param,
                    st.session_state.forecast_hours
                )
    
    # Fetch warnings
    warnings_data = fetch_weather_warnings(
        st.session_state.location["lat"], 
        st.session_state.location["lon"]
    )
    
    # Identify potential severe weather conditions
    severe_events = data_processor.identify_severe_weather(data)
    
    # Fetch grid data for map
    grid_data = fetch_grid_data(
        st.session_state.selected_parameter,
        st.session_state.location["lat"],
        st.session_state.location["lon"],
        st.session_state.forecast_hour_for_map
    )
    
    # Create forecast summary
    forecast_summary = data_processor.get_forecast_summary(data)

# Display severe weather warnings if any
if severe_events or warnings_data:
    st.markdown("## ⚠️ Severe Weather Alerts")
    
    warning_tabs = st.tabs(["Forecast Warnings", "Official Alerts"])
    
    with warning_tabs[0]:
        if severe_events:
            # Display warnings from data analysis
            warning_viz = visualizer.create_severe_warning_visual(severe_events)
            if warning_viz:
                st.plotly_chart(warning_viz, use_container_width=True)
            
            for event in severe_events:
                st.warning(
                    f"**{event['type']}**: {event['description']} "
                    f"(Threshold: {event['threshold']})"
                )
        else:
            st.info("No severe weather conditions detected in the forecast.")
    
    with warning_tabs[1]:
        if warnings_data:
            # Display official warnings
            for warning in warnings_data:
                st.error(
                    f"**{warning.get('title', 'Weather Warning')}**: {warning.get('description', 'No details provided')}"
                )
        else:
            st.info("No official weather alerts in effect for this location.")

# Create layout for main content
col1, col2 = st.columns([3, 1])

# Column 1: Map and main charts
with col1:
    # Map with selected parameter
    st.markdown(f"### Weather Map: {next((p['name'] for p in map_params if p['code'] == st.session_state.selected_parameter), st.session_state.selected_parameter)}")
    st.markdown(f"Forecast hour: +{st.session_state.forecast_hour_for_map}h")
    
    # Create map
    weather_map = visualizer.create_weather_map(
        grid_data,
        st.session_state.location["lat"],
        st.session_state.location["lon"],
        next((p['name'] for p in map_params if p['code'] == st.session_state.selected_parameter), st.session_state.selected_parameter),
        zoom=8
    )
    
    # Display map
    folium_static(weather_map, width=800)
    
    # Add note about sample data
    st.info("Note: This application is showing sample forecast data in demo mode.")
    
    # Temperature chart
    if data["TMP_TGL_2"] is not None:
        temp_fig = visualizer.plot_time_series(
            data["TMP_TGL_2"], 
            "Temperature", 
            "°C"
        )
        st.plotly_chart(temp_fig, use_container_width=True)
    
    # Precipitation chart
    if data["APCP_SFC"] is not None:
        precip_fig = visualizer.plot_precipitation_bars(
            data["APCP_SFC"]
        )
        st.plotly_chart(precip_fig, use_container_width=True)
    
    # Wind chart
    if data["WIND_TGL_10"] is not None:
        wind_fig = visualizer.plot_time_series(
            data["WIND_TGL_10"], 
            "Wind Speed", 
            "km/h"
        )
        st.plotly_chart(wind_fig, use_container_width=True)
        
    # Display additional parameter charts if any are selected
    if 'additional_params' in st.session_state and st.session_state.additional_params:
        st.markdown("### Additional Parameter Charts")
        
        for param in st.session_state.additional_params:
            if param in data and data[param] is not None:
                # Get parameter info for proper labeling
                param_info = next((p for p in map_params if p["code"] == param), None)
                if param_info:
                    param_name = param_info["name"]
                    
                    # Determine appropriate unit based on parameter type
                    unit = ""
                    if "TMP" in param or "TMAX" in param or "TMIN" in param:
                        unit = "°C"
                    elif "PCP" in param or "SNOW" in param or "WEASD" in param:
                        unit = "mm"
                    elif "WIND" in param or "GUST" in param:
                        unit = "km/h"
                    elif "PRMSL" in param or "PRES" in param:
                        unit = "hPa"
                    elif "RH" in param or "CDC" in param:
                        unit = "%"
                    elif "HGT" in param:
                        unit = "m"
                    elif "CAPE" in param or "CIN" in param:
                        unit = "J/kg"
                    
                    # Check if parameter requires special chart type
                    if "APCP" in param or "PCP" in param:
                        fig = visualizer.plot_precipitation_bars(data[param])
                    elif "WDIR" in param:
                        # For direction parameters, use specific visualization if implemented
                        # For now, fallback to regular chart
                        fig = visualizer.plot_time_series(data[param], param_name, unit)
                    else:
                        fig = visualizer.plot_time_series(data[param], param_name, unit)
                    
                    st.plotly_chart(fig, use_container_width=True)

# Column 2: Forecast summary
with col2:
    st.markdown("### Forecast Summary")
    
    # Summary table
    summary_table = visualizer.create_forecast_summary_table(forecast_summary)
    if summary_table:
        st.plotly_chart(summary_table, use_container_width=True)
    
    # Current conditions
    if data["TMP_TGL_2"] is not None and not data["TMP_TGL_2"].empty:
        current_temp = data["TMP_TGL_2"].iloc[0]['value'] if 'value' in data["TMP_TGL_2"].columns else "N/A"
        st.metric("Current Temperature", f"{current_temp:.1f}°C")
    
    if data["RH_TGL_2"] is not None and not data["RH_TGL_2"].empty:
        current_rh = data["RH_TGL_2"].iloc[0]['value'] if 'value' in data["RH_TGL_2"].columns else "N/A"
        st.metric("Current Humidity", f"{current_rh:.0f}%")
    
    if data["WIND_TGL_10"] is not None and not data["WIND_TGL_10"].empty:
        current_wind = data["WIND_TGL_10"].iloc[0]['value'] if 'value' in data["WIND_TGL_10"].columns else "N/A"
        st.metric("Current Wind Speed", f"{current_wind:.1f} km/h")
    
    # Calculate and display feels-like temperature if we have both temp and wind
    if (data["TMP_TGL_2"] is not None and not data["TMP_TGL_2"].empty and
        data["WIND_TGL_10"] is not None and not data["WIND_TGL_10"].empty):
        try:
            wind_chill = data_processor.calculate_wind_chill(
                data["TMP_TGL_2"].head(1), 
                data["WIND_TGL_10"].head(1)
            )
            if wind_chill is not None and 'wind_chill' in wind_chill.columns:
                feels_like = wind_chill.iloc[0]['wind_chill']
                if not np.isnan(feels_like):
                    st.metric("Feels Like", f"{feels_like:.1f}°C")
        except Exception as e:
            logger.error(f"Error calculating feels-like temperature: {e}")
    
    # Weather parameters description
    st.markdown("### GDPS Parameters")
    
    with st.expander("Temperature Parameters"):
        st.markdown("""
        - **TMP_TGL_2**: Air temperature at 2 meters above ground
        - **TMP_TGL_0**: Temperature at surface level
        - **TMP_ISBL_500**: Temperature at 500 hPa pressure level (approx. 5.5 km altitude)
        - **TMP_ISBL_850**: Temperature at 850 hPa pressure level (approx. 1.5 km altitude)
        - **TMAX_TGL_2**: Maximum temperature at 2 meters above ground
        - **TMIN_TGL_2**: Minimum temperature at 2 meters above ground
        """)
    
    with st.expander("Precipitation Parameters"):
        st.markdown("""
        - **APCP_SFC**: Total precipitation accumulation
        - **ACPCP_SFC**: Convective precipitation accumulation (thunderstorms)
        - **SNOD_SFC**: Snow depth on ground
        - **WEASD_SFC**: Water equivalent of accumulated snow depth
        - **CRAIN_SFC**: Categorical rain (yes=1/no=0)
        - **CSNOW_SFC**: Categorical snow (yes=1/no=0)
        """)
    
    with st.expander("Wind Parameters"):
        st.markdown("""
        - **WIND_TGL_10**: Wind speed at 10 meters above ground
        - **WDIR_TGL_10**: Wind direction at 10 meters (degrees, 0=North, 90=East)
        - **GUST_TGL_10**: Wind gust at 10 meters above ground
        - **UGRD_TGL_10**: U-component of wind at 10 meters (east-west)
        - **VGRD_TGL_10**: V-component of wind at 10 meters (north-south)
        - **WIND_ISBL_250**: Wind speed at 250 hPa (approx. 10.5 km, jet stream level)
        """)
    
    with st.expander("Pressure & Height Parameters"):
        st.markdown("""
        - **PRMSL_MSL**: Mean sea level pressure
        - **PRES_SFC**: Surface pressure
        - **HGT_ISBL_500**: 500 hPa geopotential height (altitude of 500 hPa pressure level)
        """)
    
    with st.expander("Humidity & Moisture Parameters"):
        st.markdown("""
        - **RH_TGL_2**: Relative humidity at 2 meters
        - **RH_ISBL_700**: Relative humidity at 700 hPa level (mid-troposphere)
        - **SPFH_TGL_2**: Specific humidity at 2 meters (mass of water vapor per unit mass of air)
        - **PWAT_EATM**: Precipitable water (total column water vapor)
        """)
    
    with st.expander("Cloud Parameters"):
        st.markdown("""
        - **TCDC_SFC**: Total cloud cover (percentage)
        - **LCDC_LOW**: Low cloud cover (below 2 km)
        - **MCDC_MID**: Medium cloud cover (2-6 km)
        - **HCDC_HIGH**: High cloud cover (above 6 km)
        """)
    
    with st.expander("Severe Weather Parameters"):
        st.markdown("""
        - **CAPE_SFC**: Convective Available Potential Energy (thunderstorm potential)
        - **CIN_SFC**: Convective Inhibition (resistance to thunderstorm formation)
        - **LFTX_SFC**: Lifted Index (atmospheric stability measure)
        - **VIS_SFC**: Surface visibility
        """)
    
    
    # Data source information
    st.markdown("### Data Source")
    
    data_source_tab1, data_source_tab2 = st.tabs(["GDPS Information", "Alternative Sources"])
    
    with data_source_tab1:
        st.markdown("""
        ### Global Deterministic Prediction System (GDPS)
        
        The GDPS is Environment Canada's operational global numerical weather prediction system with a horizontal resolution of approximately 15 km.
        
        **Key Features:**
        - Global coverage with 15 km horizontal resolution
        - Runs four times daily at 00Z, 06Z, 12Z, and 18Z
        - Provides forecasts up to 240 hours (10 days) ahead
        - Includes over 30 meteorological parameters at multiple atmospheric levels
        
        **Parameter Naming Convention:**
        - TGL: Values at a specific height above ground level (e.g., TGL_2 = 2 meters)
        - ISBL: Values at a specific pressure level (e.g., ISBL_500 = 500 hPa)
        - SFC: Surface values
        """)
        
    with data_source_tab2:
        st.markdown("""
        ### Alternative Weather Data Sources
        
        For operational use, consider these alternative data sources:
        
        1. **Environment Canada MSC GeoMet API**
           - Official API for Environment Canada data
           - Includes GDPS, RDPS, HRDPS, and other models
           - Website: [MSC GeoMet](https://eccc-msc.github.io/open-data/msc-geomet/readme_en/)
        
        2. **NOAA Global Forecast System (GFS)**
           - Global model with 0.25° resolution
           - Free and open access
           - Website: [NOAA GFS](https://www.ncei.noaa.gov/products/weather-climate-models/global-forecast)
        
        3. **European Centre for Medium-Range Weather Forecasts (ECMWF)**
           - High precision global forecasts
           - Some data available freely, premium data requires subscription
           - Website: [ECMWF](https://www.ecmwf.int/en/forecasts)
        """)
    
    # Last updated information
    st.markdown(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

# Footer
st.markdown("---")
st.markdown("GDPS 15km Weather Forecast Application | Environment Canada Global Deterministic Prediction System")
