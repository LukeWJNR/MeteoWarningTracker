import streamlit as st
import pandas as pd
import numpy as np
import folium
from streamlit_folium import folium_static
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import time
from utils.data_fetcher import MeteoDataFetcher
from utils.data_processor import WeatherDataProcessor
from utils.visualizations import WeatherVisualizer
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
st.title("Weather Forecast")
st.markdown("### MeteoCenter GDPS Data Visualization")

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
        {"code": "TMP_TGL_2", "name": "Temperature (2m)"},
        {"code": "APCP_SFC", "name": "Precipitation"},
        {"code": "WIND_TGL_10", "name": "Wind Speed (10m)"},
        {"code": "PRMSL_MSL", "name": "Sea Level Pressure"},
        {"code": "RH_TGL_2", "name": "Relative Humidity (2m)"},
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
    
    # About section
    st.header("About")
    st.markdown("""
    This application visualizes weather forecast data from the MeteoCenter Global Deterministic Prediction System (GDPS).
    
    Data is updated twice daily with forecasts up to 168 hours ahead.
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
    st.markdown("### Weather Parameters")
    st.markdown("""
    - **Temperature**: Air temperature at 2 meters above ground
    - **Precipitation**: Accumulated precipitation (rain, snow, etc.)
    - **Wind**: Wind speed at 10 meters above ground
    - **Humidity**: Relative humidity at 2 meters above ground
    - **Pressure**: Sea-level atmospheric pressure
    """)
    
    # Data source information
    st.markdown("### Data Source")
    st.markdown("""
    Weather forecast data is provided by MeteoCenter Global Deterministic Prediction System (GDPS).
    
    The GDPS model is run twice daily at 00Z and 12Z, providing forecast data up to 168 hours ahead.
    """)
    
    # Last updated information
    st.markdown(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

# Footer
st.markdown("---")
st.markdown("Weather Forecast Application | Using MeteoCenter GDPS Data")
