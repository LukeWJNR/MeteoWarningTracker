import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import folium_static
import requests
import json
from datetime import datetime, timedelta
import time
import io
from PIL import Image
import logging
from meteostat import Point, Daily, Hourly

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="Severe Weather Forecast",
    page_icon="🌩️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title and description
st.title("🌩️ Severe Weather Forecast")
st.markdown("""
This application provides accurate severe weather forecasts using reliable data sources.
Enter a location to view current conditions, forecasts, and potential severe weather alerts.
""")

# Initialize session state for persistence
if 'location' not in st.session_state:
    st.session_state.location = "New York, NY"
if 'lat' not in st.session_state:
    st.session_state.lat = 40.7128
if 'lon' not in st.session_state:
    st.session_state.lon = -74.0060
if 'forecast_data' not in st.session_state:
    st.session_state.forecast_data = {}
if 'current_weather' not in st.session_state:
    st.session_state.current_weather = None
if 'alerts' not in st.session_state:
    st.session_state.alerts = []

# Sidebar for location input
st.sidebar.header("Location")
location_input = st.sidebar.text_input("Enter Location", value=st.session_state.location)

# Search button
if st.sidebar.button("Search Location"):
    try:
        # Geocode the location using Nominatim (OpenStreetMap)
        geocode_url = f"https://nominatim.openstreetmap.org/search?q={location_input}&format=json&limit=1"
        headers = {'User-Agent': 'SevereWeatherForecast/1.0'}
        response = requests.get(geocode_url, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                st.session_state.lat = float(data[0]['lat'])
                st.session_state.lon = float(data[0]['lon'])
                st.session_state.location = location_input
                
                # Clear cached data to force refresh
                st.session_state.forecast_data = {}
                st.session_state.current_weather = None
                st.session_state.alerts = []
                
                st.sidebar.success(f"Location set to: {location_input}")
            else:
                st.sidebar.error("Location not found. Please try another search term.")
        else:
            st.sidebar.error(f"Error geocoding location: {response.status_code}")
    except Exception as e:
        st.sidebar.error(f"Error: {str(e)}")

# Display current coordinates
st.sidebar.write(f"**Coordinates:** {st.session_state.lat:.4f}, {st.session_state.lon:.4f}")

# Forecast options
st.sidebar.header("Forecast Options")
forecast_days = st.sidebar.slider("Forecast Days", min_value=1, max_value=10, value=5)
forecast_elements = st.sidebar.multiselect(
    "Forecast Elements",
    ["Temperature", "Precipitation", "Wind", "Humidity", "Pressure", "Severe Weather"],
    default=["Temperature", "Precipitation", "Severe Weather"]
)

# Main content - two columns
col1, col2 = st.columns([2, 1])

with col1:
    st.header(f"Weather Forecast for {st.session_state.location}")
    
    # Get current weather data using Meteostat if not already loaded
    if not st.session_state.current_weather:
        with st.spinner("Loading current weather..."):
            try:
                # Create Point for the location
                location = Point(st.session_state.lat, st.session_state.lon)
                
                # Get hourly data for today
                time_now = datetime.now()
                start = time_now - timedelta(hours=24)  # Get last 24 hours to ensure we have data
                end = time_now
                
                # Fetch hourly data
                data = Hourly(location, start, end)
                df = data.fetch()
                
                if not df.empty:
                    # Get the latest hour's data
                    latest = df.iloc[-1]
                    st.session_state.current_weather = {
                        'temp': latest.get('temp'),
                        'dwpt': latest.get('dwpt'),
                        'rhum': latest.get('rhum'),
                        'prcp': latest.get('prcp'),
                        'wdir': latest.get('wdir'),
                        'wspd': latest.get('wspd'),
                        'pres': latest.get('pres'),
                        'time': latest.name,
                    }
                else:
                    # If hourly data is not available, try daily data
                    daily_data = Daily(location, time_now.date() - timedelta(days=1), time_now.date())
                    daily_df = daily_data.fetch()
                    
                    if not daily_df.empty:
                        latest = daily_df.iloc[-1]
                        st.session_state.current_weather = {
                            'temp': latest.get('tavg'),
                            'tmin': latest.get('tmin'),
                            'tmax': latest.get('tmax'),
                            'prcp': latest.get('prcp'),
                            'wspd': latest.get('wspd'),
                            'pres': latest.get('pres'),
                            'time': latest.name,
                        }
            except Exception as e:
                logger.error(f"Error fetching current weather: {e}")
                st.error("Could not fetch current weather data. Using forecast data instead.")
    
    # Display current weather if available
    if st.session_state.current_weather:
        st.subheader("Current Conditions")
        
        # Create current conditions display
        current = st.session_state.current_weather
        
        # Format time
        if isinstance(current.get('time'), pd.Timestamp):
            time_str = current['time'].strftime("%Y-%m-%d %H:%M")
        else:
            time_str = "Unknown"
        
        # Create metrics in columns
        curr_col1, curr_col2, curr_col3, curr_col4 = st.columns(4)
        
        with curr_col1:
            if 'temp' in current and current['temp'] is not None:
                st.metric("Temperature", f"{current['temp']:.1f}°C")
            if 'tmin' in current and current['tmin'] is not None and 'tmax' in current and current['tmax'] is not None:
                st.metric("Min/Max", f"{current['tmin']:.1f}°C / {current['tmax']:.1f}°C")
                
        with curr_col2:
            if 'rhum' in current and current['rhum'] is not None:
                st.metric("Humidity", f"{current['rhum']:.0f}%")
            if 'dwpt' in current and current['dwpt'] is not None:
                st.metric("Dew Point", f"{current['dwpt']:.1f}°C")
                
        with curr_col3:
            if 'wspd' in current and current['wspd'] is not None:
                st.metric("Wind Speed", f"{current['wspd']:.1f} km/h")
            if 'wdir' in current and current['wdir'] is not None:
                st.metric("Wind Direction", f"{current['wdir']:.0f}°")
                
        with curr_col4:
            if 'prcp' in current and current['prcp'] is not None:
                st.metric("Precipitation", f"{current['prcp']:.1f} mm")
            if 'pres' in current and current['pres'] is not None:
                st.metric("Pressure", f"{current['pres']:.0f} hPa")
                
        st.caption(f"Last updated: {time_str}")
    
    # Fetch forecast data using Meteostat if not already loaded
    if not st.session_state.forecast_data:
        with st.spinner("Loading forecast data..."):
            try:
                # Create Point for the location
                location = Point(st.session_state.lat, st.session_state.lon)
                
                # Set time period
                start_date = datetime.now().date()
                end_date = start_date + timedelta(days=forecast_days)
                
                # Fetch daily data (more reliable for forecasts)
                data = Daily(location, start_date, end_date)
                df = data.fetch()
                
                if not df.empty:
                    st.session_state.forecast_data = df
            except Exception as e:
                logger.error(f"Error fetching forecast data: {e}")
                st.error("Could not fetch forecast data. Please try again later.")
    
    # Display forecast data if available
    if isinstance(st.session_state.forecast_data, pd.DataFrame) and not st.session_state.forecast_data.empty:
        st.subheader("Weather Forecast")
        
        df = st.session_state.forecast_data
        
        # Temperature forecast plot if selected
        if "Temperature" in forecast_elements and any(col in df.columns for col in ['tmin', 'tmax', 'tavg']):
            # Create temperature plot with Plotly for interactivity
            fig = go.Figure()
            
            # Add temperature traces
            if all(col in df.columns for col in ['tmin', 'tmax']):
                # Create temperature range area
                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df['tmax'],
                    fill=None,
                    mode='lines',
                    line_color='rgba(255,0,0,0.5)',
                    name='Max Temp'
                ))
                
                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df['tmin'],
                    fill='tonexty',
                    mode='lines',
                    line_color='rgba(0,0,255,0.5)',
                    name='Min Temp'
                ))
                
                if 'tavg' in df.columns:
                    fig.add_trace(go.Scatter(
                        x=df.index,
                        y=df['tavg'],
                        mode='lines+markers',
                        line=dict(color='black', width=2),
                        name='Avg Temp'
                    ))
            elif 'tavg' in df.columns:
                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df['tavg'],
                    mode='lines+markers',
                    line=dict(color='black', width=2),
                    name='Avg Temp'
                ))
            
            # Layout
            fig.update_layout(
                title='Temperature Forecast',
                xaxis_title='Date',
                yaxis_title='Temperature (°C)',
                hovermode='x unified',
                height=400
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Precipitation forecast if selected
        if "Precipitation" in forecast_elements and 'prcp' in df.columns:
            # Create precipitation bar chart
            fig = px.bar(
                df,
                x=df.index,
                y='prcp',
                labels={'prcp': 'Precipitation (mm)', 'x': 'Date'},
                title='Precipitation Forecast',
                color_discrete_sequence=['blue']
            )
            
            # Add horizontal line for moderate rain threshold (10mm)
            fig.add_shape(
                type="line",
                x0=df.index.min(),
                y0=10,
                x1=df.index.max(),
                y1=10,
                line=dict(color="orange", width=2, dash="dash"),
            )
            
            # Add annotation for the line
            fig.add_annotation(
                x=df.index.max(),
                y=10,
                text="Moderate Rain",
                showarrow=False,
                yshift=10
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Wind forecast if selected
        if "Wind" in forecast_elements and 'wspd' in df.columns:
            # Create wind speed line chart
            fig = px.line(
                df,
                x=df.index,
                y='wspd',
                labels={'wspd': 'Wind Speed (km/h)', 'x': 'Date'},
                title='Wind Speed Forecast',
                markers=True
            )
            
            # Add threshold lines for wind categories
            fig.add_shape(
                type="line",
                x0=df.index.min(),
                y0=20,
                x1=df.index.max(),
                y1=20,
                line=dict(color="yellow", width=2, dash="dash"),
            )
            
            fig.add_shape(
                type="line",
                x0=df.index.min(),
                y0=40,
                x1=df.index.max(),
                y1=40,
                line=dict(color="orange", width=2, dash="dash"),
            )
            
            fig.add_shape(
                type="line",
                x0=df.index.min(),
                y0=60,
                x1=df.index.max(),
                y1=60,
                line=dict(color="red", width=2, dash="dash"),
            )
            
            # Add annotations
            fig.add_annotation(x=df.index.max(), y=20, text="Breezy", showarrow=False, yshift=10)
            fig.add_annotation(x=df.index.max(), y=40, text="Strong Wind", showarrow=False, yshift=10)
            fig.add_annotation(x=df.index.max(), y=60, text="Gale", showarrow=False, yshift=10)
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Humidity forecast if selected
        if "Humidity" in forecast_elements and 'rhum' in df.columns:
            # Create humidity line chart
            fig = px.line(
                df,
                x=df.index,
                y='rhum',
                labels={'rhum': 'Relative Humidity (%)', 'x': 'Date'},
                title='Humidity Forecast',
                markers=True
            )
            
            st.plotly_chart(fig, use_container_width=True)
        
        # Pressure forecast if selected
        if "Pressure" in forecast_elements and 'pres' in df.columns:
            # Create pressure line chart
            fig = px.line(
                df,
                x=df.index,
                y='pres',
                labels={'pres': 'Pressure (hPa)', 'x': 'Date'},
                title='Atmospheric Pressure Forecast',
                markers=True
            )
            
            # Add reference line for standard pressure
            fig.add_shape(
                type="line",
                x0=df.index.min(),
                y0=1013.25,
                x1=df.index.max(),
                y1=1013.25,
                line=dict(color="gray", width=2, dash="dash"),
            )
            
            # Add annotation for the line
            fig.add_annotation(
                x=df.index.max(),
                y=1013.25,
                text="Standard Pressure",
                showarrow=False,
                yshift=10
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    # Create a map with the location
    st.subheader("Location Map")
    m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=10)
    
    # Add marker for the location
    folium.Marker(
        [st.session_state.lat, st.session_state.lon],
        popup=st.session_state.location,
        icon=folium.Icon(color="red", icon="info-sign")
    ).add_to(m)
    
    # Display the map
    folium_static(m)

with col2:
    # Severe Weather Alerts
    st.header("Severe Weather Alerts")
    
    # Try to fetch alerts from Weather.gov (NWS) API for US locations
    if not st.session_state.alerts:
        with st.spinner("Checking for severe weather alerts..."):
            try:
                # First check if the location is in the US (approximately)
                is_us_location = (24 <= st.session_state.lat <= 50) and (-125 <= st.session_state.lon <= -66)
                
                if is_us_location:
                    alert_data = None
                    # Direct API request to NWS API
                    try:
                        # NWS API endpoint for alerts by point
                        url = f"https://api.weather.gov/alerts/active?point={st.session_state.lat},{st.session_state.lon}"
                        headers = {
                            "User-Agent": "SevereWeatherForecast/1.0",
                            "Accept": "application/geo+json"
                        }
                        
                        response = requests.get(url, headers=headers)
                        
                        if response.status_code == 200:
                            alert_data = response.json()
                            
                            if alert_data and 'features' in alert_data:
                                st.session_state.alerts = alert_data['features']
                    except Exception as e:
                        logger.error(f"Error requesting NWS alerts: {e}")
            except Exception as e:
                logger.error(f"Error fetching weather alerts: {e}")
                st.warning("Could not fetch official weather alerts. Checking for potential severe weather conditions...")
    
    # Display alerts if any
    if st.session_state.alerts and len(st.session_state.alerts) > 0:
        for alert in st.session_state.alerts:
            properties = alert.get('properties', {})
            
            # Alert severity color coding
            severity = properties.get('severity', '').lower()
            if severity == 'extreme':
                box_color = "#FF0000"  # Red
            elif severity == 'severe':
                box_color = "#FFA500"  # Orange
            elif severity == 'moderate':
                box_color = "#FFFF00"  # Yellow
            else:
                box_color = "#00FF00"  # Green
            
            # Create alert box with information
            st.markdown(
                f"""
                <div style="background-color: {box_color}30; padding: 10px; border-left: 5px solid {box_color};">
                    <h3 style="color: {box_color};">{properties.get('event', 'Weather Alert')}</h3>
                    <p><strong>Severity:</strong> {properties.get('severity', 'Unknown').capitalize()}</p>
                    <p><strong>Issued:</strong> {properties.get('sent', 'Unknown')}</p>
                    <p><strong>Expires:</strong> {properties.get('expires', 'Unknown')}</p>
                    <details>
                        <summary>View Details</summary>
                        <p>{properties.get('description', 'No details available')}</p>
                    </details>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        # If no official alerts, check forecast data for potential severe weather
        severe_conditions = []
        
        # Check if we have forecast data
        if isinstance(st.session_state.forecast_data, pd.DataFrame) and not st.session_state.forecast_data.empty:
            df = st.session_state.forecast_data
            
            # Check for heavy precipitation
            if 'prcp' in df.columns and df['prcp'].max() >= 20:
                heavy_rain_days = df[df['prcp'] >= 20].index.tolist()
                if heavy_rain_days:
                    severe_conditions.append({
                        'condition': 'Heavy Precipitation',
                        'description': f"Potential heavy rainfall ({df['prcp'].max():.1f} mm) on {heavy_rain_days[0].strftime('%Y-%m-%d')}",
                        'severity': 'Moderate',
                        'date': heavy_rain_days[0]
                    })
            
            # Check for strong winds
            if 'wspd' in df.columns and df['wspd'].max() >= 40:
                strong_wind_days = df[df['wspd'] >= 40].index.tolist()
                if strong_wind_days:
                    severe_conditions.append({
                        'condition': 'Strong Winds',
                        'description': f"Strong winds ({df['wspd'].max():.1f} km/h) predicted on {strong_wind_days[0].strftime('%Y-%m-%d')}",
                        'severity': 'Moderate',
                        'date': strong_wind_days[0]
                    })
            
            # Check for extreme temperatures
            if 'tmax' in df.columns and df['tmax'].max() >= 35:
                hot_days = df[df['tmax'] >= 35].index.tolist()
                if hot_days:
                    severe_conditions.append({
                        'condition': 'Extreme Heat',
                        'description': f"Very high temperatures ({df['tmax'].max():.1f}°C) expected on {hot_days[0].strftime('%Y-%m-%d')}",
                        'severity': 'Moderate',
                        'date': hot_days[0]
                    })
            
            if 'tmin' in df.columns and df['tmin'].min() <= -10:
                cold_days = df[df['tmin'] <= -10].index.tolist()
                if cold_days:
                    severe_conditions.append({
                        'condition': 'Extreme Cold',
                        'description': f"Very low temperatures ({df['tmin'].min():.1f}°C) expected on {cold_days[0].strftime('%Y-%m-%d')}",
                        'severity': 'Moderate',
                        'date': cold_days[0]
                    })
            
            # Check for rapid pressure changes
            if 'pres' in df.columns and len(df) > 1:
                df['pres_change'] = df['pres'].diff()
                if df['pres_change'].min() <= -5:
                    pressure_drop_days = df[df['pres_change'] <= -5].index.tolist()
                    if pressure_drop_days:
                        severe_conditions.append({
                            'condition': 'Rapid Pressure Drop',
                            'description': f"Significant pressure drop ({df['pres_change'].min():.1f} hPa) on {pressure_drop_days[0].strftime('%Y-%m-%d')}",
                            'severity': 'Moderate',
                            'date': pressure_drop_days[0]
                        })
        
        # Display potential severe weather conditions
        if severe_conditions:
            st.subheader("Potential Severe Weather")
            for condition in severe_conditions:
                severity = condition['severity'].lower()
                if severity == 'high':
                    box_color = "#FFA500"  # Orange
                else:
                    box_color = "#FFFF00"  # Yellow
                
                st.markdown(
                    f"""
                    <div style="background-color: {box_color}30; padding: 10px; border-left: 5px solid {box_color};">
                        <h3 style="color: {box_color};">{condition['condition']}</h3>
                        <p>{condition['description']}</p>
                        <p><small>Potential Impact: {condition['severity']}</small></p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
        else:
            st.info("No severe weather alerts or conditions detected for this location.")
    
    # Weather Forecast Interpretation Guide
    st.header("Interpretation Guide")
    
    with st.expander("Understanding the Forecast"):
        st.markdown("""
        ### How to Read the Forecast

        This forecast uses reliable meteorological data to help you prepare for upcoming weather conditions:

        - **Temperature Range**: The shaded area between minimum and maximum temperatures shows the expected temperature variation for each day.
        
        - **Precipitation**: Values indicate expected rainfall in millimeters (mm).
            - Light rain: 0.5-5 mm
            - Moderate rain: 5-20 mm
            - Heavy rain: >20 mm
        
        - **Wind Speed**:
            - Light: 5-20 km/h
            - Moderate: 20-40 km/h
            - Strong: 40-60 km/h
            - Gale: >60 km/h
        
        - **Pressure Trends**: 
            - Falling pressure often indicates approaching storms
            - Rising pressure typically suggests improving weather
        """)
    
    with st.expander("Severe Weather Indicators"):
        st.markdown("""
        ### Signs of Potential Severe Weather

        Be alert for these indicators in the forecast:

        1. **Rapid pressure drops** (>5 hPa in 24 hours)
        2. **Heavy precipitation** (>20 mm in 24 hours)
        3. **Strong winds** (>40 km/h sustained)
        4. **Extreme temperatures** (varies by region and season)
        5. **Convergence of multiple conditions** (e.g., strong winds with heavy precipitation)

        ### Weather Alert Severity Levels

        - **Minor**: Awareness recommended, minimal impact expected
        - **Moderate**: Increased awareness and some precautions advised
        - **Severe**: Significant impact possible, preventive actions recommended
        - **Extreme**: Life-threatening conditions, immediate action required
        """)
    
    # Data sources
    st.header("Data Sources")
    st.markdown("""
    This application uses data from:
    - **Meteostat**: Historical and forecast weather data
    - **Weather.gov (NWS)**: Official US weather alerts and warnings
    - **OpenStreetMap/Nominatim**: Location geocoding
    
    Last updated: """ + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # Disclaimer
    st.caption("""
    **Disclaimer**: This tool provides weather forecasts for informational purposes only.
    Always consult official government weather services for critical weather decisions and emergencies.
    """)

# Function to calculate the Fire Weather Index (for future use)
def calculate_fire_weather_index(temp, humidity, wind_speed, rainfall):
    """
    Calculate a simple Fire Weather Index (FWI) based on key weather parameters
    
    Args:
        temp (float): Temperature in Celsius
        humidity (float): Relative humidity in percent
        wind_speed (float): Wind speed in km/h
        rainfall (float): Rainfall in mm over the past 24 hours
        
    Returns:
        float: Fire Weather Index value and category
    """
    # Implement logic for fire weather index calculation
    # This is a simplified version for demonstration
    
    # Adjust for recent rainfall
    if rainfall > 10:
        rainfall_factor = 0.2
    elif rainfall > 5:
        rainfall_factor = 0.5
    elif rainfall > 0:
        rainfall_factor = 0.8
    else:
        rainfall_factor = 1.0
    
    # Calculate base FWI
    fwi = ((temp * 1.1) + (wind_speed * 0.7) - (humidity * 0.5)) * rainfall_factor
    
    # Clamp to reasonable range
    fwi = max(0, min(100, fwi))
    
    # Determine category
    if fwi >= 80:
        category = "Extreme"
    elif fwi >= 60:
        category = "Very High"
    elif fwi >= 40:
        category = "High"
    elif fwi >= 20:
        category = "Moderate"
    else:
        category = "Low"
        
    return fwi, category