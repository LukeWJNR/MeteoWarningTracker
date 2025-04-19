"""
Severe Weather Forecast Application

This application provides comprehensive weather forecasting with a focus on severe weather events.
It uses reliable data sources and advanced meteorological calculations to provide accurate forecasts.
"""
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import folium_static
import json
import os
import logging
import time
import pytz
from datetime import datetime, timedelta
import requests
from meteostat import Point, Daily, Hourly
from utils.visual_crossing import VisualCrossingAPI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize API client
weather_api = VisualCrossingAPI()

# Page config
st.set_page_config(
    page_title="Severe Weather Forecast",
    page_icon="🌩️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state variables if they don't exist
if 'lat' not in st.session_state:
    st.session_state.lat = 40.7128  # Default to NYC
if 'lon' not in st.session_state:
    st.session_state.lon = -74.0060
if 'location' not in st.session_state:
    st.session_state.location = "New York, NY"
if 'forecast_data' not in st.session_state:
    st.session_state.forecast_data = None
if 'current_weather' not in st.session_state:
    st.session_state.current_weather = None
if 'hourly_forecast' not in st.session_state:
    st.session_state.hourly_forecast = None
if 'alert_check_time' not in st.session_state:
    st.session_state.alert_check_time = None
if 'active_alerts' not in st.session_state:
    st.session_state.active_alerts = []
if 'units' not in st.session_state:
    st.session_state.units = "metric"  # Default to metric units

# Title and introduction
st.title("🌩️ Severe Weather Forecast")
st.markdown("""
This application provides detailed weather forecasts with a focus on severe weather events. 
It uses reliable data sources and advanced meteorological calculations to help you stay informed about potential weather hazards.
""")

# Sidebar for location input and settings
st.sidebar.title("Settings")

# Location input
st.sidebar.header("Location")
location_input = st.sidebar.text_input("Enter location:", value=st.session_state.location)
search_button = st.sidebar.button("Search")

if search_button and location_input:
    try:
        # Use Visual Crossing API to search for location
        location = weather_api.search_location(location_input)
        
        if location and location.get('latitude') and location.get('longitude'):
            st.session_state.lat = location['latitude']
            st.session_state.lon = location['longitude']
            st.session_state.location = location['name']
            
            # Clear cached data when location changes
            st.session_state.forecast_data = None
            st.session_state.current_weather = None
            st.session_state.hourly_forecast = None
            st.session_state.active_alerts = []
            
            st.sidebar.success(f"Location updated to {location['name']}")
            # Rerun to update all components with new location
            st.rerun()
        else:
            st.sidebar.error("Location not found. Please try a different search term.")
    except Exception as e:
        st.sidebar.error(f"Error finding location: {str(e)}")
        logger.error(f"Error in location search: {str(e)}")

# Display current coordinates
st.sidebar.write(f"Latitude: {st.session_state.lat:.4f}, Longitude: {st.session_state.lon:.4f}")

# Forecast settings
st.sidebar.header("Forecast Settings")
forecast_days = st.sidebar.slider("Forecast Days", min_value=1, max_value=10, value=7)
forecast_elements = st.sidebar.multiselect(
    "Forecast Elements",
    ["Temperature", "Precipitation", "Wind", "Humidity", "Pressure", "UV Index", "Cloud Cover"],
    default=["Temperature", "Precipitation", "Wind"]
)

# Unit settings
unit_system = st.sidebar.radio("Units", ["Metric (°C, mm, km/h)", "Imperial (°F, in, mph)"])
st.session_state.units = "metric" if "Metric" in unit_system else "imperial"

# Fetch weather data using Visual Crossing API if not already loaded
with st.spinner("Loading weather data..."):
    # Fetch current weather if not already loaded
    if not st.session_state.current_weather:
        try:
            # Get current conditions from Visual Crossing API
            current_data = weather_api.get_current_conditions(st.session_state.lat, st.session_state.lon)
            
            if current_data:
                st.session_state.current_weather = current_data
                
                # Also check for alerts at the same time
                full_data = weather_api.get_forecast(st.session_state.lat, st.session_state.lon, days=1)
                if full_data and 'alerts' in full_data:
                    st.session_state.active_alerts = full_data['alerts']
                    st.session_state.alert_check_time = datetime.now()
            else:
                st.error("Could not fetch current weather data. Please check your API key or try again later.")
        except Exception as e:
            logger.error(f"Error fetching current weather: {str(e)}")
            st.error("Could not fetch current weather data. Please check your API key or try again later.")
    
    # Fetch forecast data if not already loaded
    if not st.session_state.forecast_data:
        try:
            # Get daily forecast data
            forecast_df = weather_api.get_forecast_df(
                st.session_state.lat, 
                st.session_state.lon, 
                days=forecast_days
            )
            
            if not forecast_df.empty:
                st.session_state.forecast_data = forecast_df
                
                # Also get hourly forecast for the next 2 days
                hourly_df = weather_api.get_hourly_forecast_df(
                    st.session_state.lat,
                    st.session_state.lon,
                    days=2
                )
                
                if not hourly_df.empty:
                    st.session_state.hourly_forecast = hourly_df
            else:
                st.error("Could not fetch forecast data. Please check your API key or try again later.")
        except Exception as e:
            logger.error(f"Error fetching forecast data: {str(e)}")
            st.error("Could not fetch forecast data. Please check your API key or try again later.")

# Display any active weather alerts
if st.session_state.active_alerts:
    st.subheader("⚠️ Active Weather Alerts")
    
    for i, alert in enumerate(st.session_state.active_alerts):
        with st.expander(f"{alert.get('event', 'Weather Alert')} - {alert.get('headline', 'Details')}"):
            st.markdown(f"""
            - **Type:** {alert.get('event', 'Unknown')}
            - **Severity:** {alert.get('severity', 'Unknown')}
            - **Time:** {alert.get('onset', 'Unknown')} to {alert.get('ends', 'Unknown')}
            
            **Description:**  
            {alert.get('description', 'No description available')}
            """)

# Display current weather if available
if st.session_state.current_weather:
    st.subheader("Current Conditions")
    
    # Create current conditions display
    current = st.session_state.current_weather
    
    # Create metrics in columns
    curr_col1, curr_col2, curr_col3, curr_col4 = st.columns(4)
    
    with curr_col1:
        if 'temp' in current:
            st.metric("Temperature", f"{current['temp']:.1f}°C")
        if 'feelslike' in current:
            st.metric("Feels Like", f"{current['feelslike']:.1f}°C")
            
    with curr_col2:
        if 'humidity' in current:
            st.metric("Humidity", f"{current['humidity']:.0f}%")
        if 'dew' in current:
            st.metric("Dew Point", f"{current['dew']:.1f}°C")
            
    with curr_col3:
        if 'windspeed' in current:
            st.metric("Wind Speed", f"{current['windspeed']:.1f} km/h")
        if 'winddir' in current:
            st.metric("Wind Direction", f"{current['winddir']:.0f}°")
            
    with curr_col4:
        if 'precip' in current:
            st.metric("Precipitation", f"{current['precip']:.2f} mm")
        if 'pressure' in current:
            st.metric("Pressure", f"{current['pressure']:.0f} hPa")
    
    # Additional metrics in columns
    curr_col1, curr_col2, curr_col3, curr_col4 = st.columns(4)
    
    with curr_col1:
        if 'cloudcover' in current:
            st.metric("Cloud Cover", f"{current['cloudcover']:.0f}%")
            
    with curr_col2:
        if 'uvindex' in current:
            st.metric("UV Index", f"{current['uvindex']}")
            
    with curr_col3:
        if 'visibility' in current:
            st.metric("Visibility", f"{current['visibility']:.1f} km")
            
    with curr_col4:
        if 'conditions' in current:
            st.metric("Conditions", f"{current['conditions']}")
    
    # Format datetime
    if 'datetime' in current and 'datetimeEpoch' in current:
        time_str = datetime.fromtimestamp(current['datetimeEpoch']).strftime("%Y-%m-%d %H:%M")
        st.caption(f"Last updated: {time_str}")

# Display hourly forecast for next 24 hours if available
if st.session_state.hourly_forecast is not None and not st.session_state.hourly_forecast.empty:
    st.subheader("Hourly Forecast (Next 24 Hours)")
    
    # Get first 24 hours
    hourly_df = st.session_state.hourly_forecast.iloc[:24]
    
    # Create temperature chart
    fig = go.Figure()
    
    # Add temperature trace
    fig.add_trace(go.Scatter(
        x=hourly_df.index,
        y=hourly_df['temp'],
        mode='lines+markers',
        name='Temperature',
        line=dict(color='red', width=2)
    ))
    
    # Add feels like
    if 'feelslike' in hourly_df.columns:
        fig.add_trace(go.Scatter(
            x=hourly_df.index,
            y=hourly_df['feelslike'],
            mode='lines',
            name='Feels Like',
            line=dict(color='orange', width=2, dash='dash')
        ))
    
    # Add precipitation probability if available
    if 'precipprob' in hourly_df.columns:
        fig.add_trace(go.Bar(
            x=hourly_df.index,
            y=hourly_df['precipprob'],
            name='Precip. Probability (%)',
            marker_color='blue',
            opacity=0.3,
            yaxis='y2'
        ))
    
    # Layout with dual y-axis
    fig.update_layout(
        title='Hourly Temperature and Precipitation Probability',
        xaxis_title='Time',
        yaxis_title='Temperature (°C)',
        yaxis2=dict(
            title='Precipitation Probability (%)',
            titlefont=dict(color='blue'),
            tickfont=dict(color='blue'),
            anchor='x',
            overlaying='y',
            side='right',
            range=[0, 100]
        ),
        hovermode='x unified',
        height=400,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=1.02,
            xanchor='center',
            x=0.5
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)

# Display daily forecast data if available
if st.session_state.forecast_data is not None and not st.session_state.forecast_data.empty:
    st.subheader("Daily Weather Forecast")
    
    df = st.session_state.forecast_data
    
    # Temperature forecast plot if selected
    if "Temperature" in forecast_elements and all(col in df.columns for col in ['tempmin', 'tempmax']):
        # Create temperature plot with Plotly for interactivity
        fig = go.Figure()
        
        # Create temperature range area
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['tempmax'],
            fill=None,
            mode='lines+markers',
            line_color='rgba(255,0,0,0.7)',
            name='Max Temp'
        ))
        
        fig.add_trace(go.Scatter(
            x=df.index,
            y=df['tempmin'],
            fill='tonexty',
            mode='lines+markers',
            line_color='rgba(0,0,255,0.7)',
            name='Min Temp'
        ))
        
        if 'temp' in df.columns:
            fig.add_trace(go.Scatter(
                x=df.index,
                y=df['temp'],
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
    if "Precipitation" in forecast_elements and 'precip' in df.columns:
        # Create precipitation bar chart
        precip_fig = go.Figure()
        
        # Add precipitation bars
        precip_fig.add_trace(go.Bar(
            x=df.index,
            y=df['precip'],
            name='Precipitation',
            marker_color='blue'
        ))
        
        # Add precipitation probability line if available
        if 'precipprob' in df.columns:
            precip_fig.add_trace(go.Scatter(
                x=df.index,
                y=df['precipprob'],
                mode='lines+markers',
                name='Probability (%)',
                line=dict(color='navy', width=2),
                yaxis='y2'
            ))
        
        # Layout with dual y-axis
        precip_fig.update_layout(
            title='Precipitation Forecast',
            xaxis_title='Date',
            yaxis_title='Precipitation (mm)',
            yaxis2=dict(
                title='Probability (%)',
                titlefont=dict(color='navy'),
                tickfont=dict(color='navy'),
                anchor='x',
                overlaying='y',
                side='right',
                range=[0, 100]
            ),
            hovermode='x unified',
            height=400
        )
        
        # Add horizontal line for moderate rain threshold (10mm)
        precip_fig.add_shape(
            type="line",
            x0=df.index.min(),
            y0=10,
            x1=df.index.max(),
            y1=10,
            line=dict(color="orange", width=2, dash="dash"),
        )
        
        # Add annotation for the line
        precip_fig.add_annotation(
            x=df.index.max(),
            y=10,
            text="Moderate Rain",
            showarrow=False,
            yshift=10
        )
        
        st.plotly_chart(precip_fig, use_container_width=True)
    
    # Wind forecast if selected
    if "Wind" in forecast_elements and 'windspeed' in df.columns:
        # Create wind speed line chart
        wind_fig = go.Figure()
        
        # Add wind speed line
        wind_fig.add_trace(go.Scatter(
            x=df.index,
            y=df['windspeed'],
            mode='lines+markers',
            name='Wind Speed',
            line=dict(color='green', width=2)
        ))
        
        # Add wind gust line if available
        if 'windgust' in df.columns:
            wind_fig.add_trace(go.Scatter(
                x=df.index,
                y=df['windgust'],
                mode='lines',
                name='Wind Gust',
                line=dict(color='darkgreen', width=2, dash='dash')
            ))
        
        # Layout
        wind_fig.update_layout(
            title='Wind Forecast',
            xaxis_title='Date',
            yaxis_title='Wind Speed (km/h)',
            hovermode='x unified',
            height=400
        )
        
        # Add threshold lines for wind categories
        wind_fig.add_shape(
            type="line",
            x0=df.index.min(),
            y0=20,
            x1=df.index.max(),
            y1=20,
            line=dict(color="yellow", width=2, dash="dash"),
        )
        
        wind_fig.add_shape(
            type="line",
            x0=df.index.min(),
            y0=40,
            x1=df.index.max(),
            y1=40,
            line=dict(color="orange", width=2, dash="dash"),
        )
        
        wind_fig.add_shape(
            type="line",
            x0=df.index.min(),
            y0=60,
            x1=df.index.max(),
            y1=60,
            line=dict(color="red", width=2, dash="dash"),
        )
        
        # Add annotations
        wind_fig.add_annotation(x=df.index.max(), y=20, text="Breezy", showarrow=False, yshift=10)
        wind_fig.add_annotation(x=df.index.max(), y=40, text="Strong Wind", showarrow=False, yshift=10)
        wind_fig.add_annotation(x=df.index.max(), y=60, text="Gale", showarrow=False, yshift=10)
        
        st.plotly_chart(wind_fig, use_container_width=True)
    
    # Humidity forecast if selected
    if "Humidity" in forecast_elements and 'humidity' in df.columns:
        # Create humidity line chart
        fig = px.line(
            df,
            x=df.index,
            y='humidity',
            labels={'humidity': 'Relative Humidity (%)', 'x': 'Date'},
            title='Humidity Forecast',
            markers=True
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Pressure forecast if selected
    if "Pressure" in forecast_elements and 'pressure' in df.columns:
        # Create pressure line chart
        fig = px.line(
            df,
            x=df.index,
            y='pressure',
            labels={'pressure': 'Pressure (hPa)', 'x': 'Date'},
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
    
    # UV Index forecast if selected
    if "UV Index" in forecast_elements and 'uvindex' in df.columns:
        # Create UV index bar chart
        uv_colors = ["green", "green", "yellow", "yellow", "orange", "orange", "red", "red", "purple", "purple", "purple"]
        
        fig = px.bar(
            df,
            x=df.index,
            y='uvindex',
            labels={'uvindex': 'UV Index', 'x': 'Date'},
            title='UV Index Forecast',
            color='uvindex',
            color_continuous_scale=uv_colors,
            range_color=[0, 10]
        )
        
        # Add reference lines for UV categories
        fig.add_shape(
            type="line",
            x0=df.index.min(),
            y0=3,
            x1=df.index.max(),
            y1=3,
            line=dict(color="yellow", width=2, dash="dash"),
        )
        
        fig.add_shape(
            type="line",
            x0=df.index.min(),
            y0=6,
            x1=df.index.max(),
            y1=6,
            line=dict(color="orange", width=2, dash="dash"),
        )
        
        fig.add_shape(
            type="line",
            x0=df.index.min(),
            y0=8,
            x1=df.index.max(),
            y1=8,
            line=dict(color="red", width=2, dash="dash"),
        )
        
        # Add annotations
        fig.add_annotation(x=df.index.max(), y=3, text="Moderate", showarrow=False, yshift=10)
        fig.add_annotation(x=df.index.max(), y=6, text="High", showarrow=False, yshift=10)
        fig.add_annotation(x=df.index.max(), y=8, text="Very High", showarrow=False, yshift=10)
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Cloud Cover forecast if selected
    if "Cloud Cover" in forecast_elements and 'cloudcover' in df.columns:
        # Create cloud cover line chart
        fig = px.line(
            df,
            x=df.index,
            y='cloudcover',
            labels={'cloudcover': 'Cloud Cover (%)', 'x': 'Date'},
            title='Cloud Cover Forecast',
            markers=True
        )
        
        # Add reference lines for cloud cover categories
        fig.add_shape(
            type="line",
            x0=df.index.min(),
            y0=25,
            x1=df.index.max(),
            y1=25,
            line=dict(color="lightblue", width=2, dash="dash"),
        )
        
        fig.add_shape(
            type="line",
            x0=df.index.min(),
            y0=50,
            x1=df.index.max(),
            y1=50,
            line=dict(color="skyblue", width=2, dash="dash"),
        )
        
        fig.add_shape(
            type="line",
            x0=df.index.min(),
            y0=75,
            x1=df.index.max(),
            y1=75,
            line=dict(color="royalblue", width=2, dash="dash"),
        )
        
        # Add annotations
        fig.add_annotation(x=df.index.max(), y=25, text="Mostly Clear", showarrow=False, yshift=10)
        fig.add_annotation(x=df.index.max(), y=50, text="Partly Cloudy", showarrow=False, yshift=10)
        fig.add_annotation(x=df.index.max(), y=75, text="Mostly Cloudy", showarrow=False, yshift=10)
        
        st.plotly_chart(fig, use_container_width=True)

# Create a map with the location
st.subheader("Location Map")
m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=10)

# Add marker for the location
folium.Marker(
    [st.session_state.lat, st.session_state.lon],
    popup=st.session_state.location,
    icon=folium.Icon(color="blue", icon="info-sign")
).add_to(m)

# Display the map
folium_static(m)

# Fire Weather Index calculation
st.subheader("Fire Weather Index")

# Check if we have the necessary data to calculate FWI
if st.session_state.current_weather:
    current = st.session_state.current_weather
    
    # Calculate FWI using the VisualCrossingAPI method
    fwi = weather_api.calculate_fire_weather_index(current)
    
    # Display FWI
    fwi_col1, fwi_col2 = st.columns([1, 3])
    
    with fwi_col1:
        st.markdown(f"""
        <div style="background-color: {fwi['color']}30; padding: 20px; border-radius: 5px; text-align: center;">
            <h1 style="color: {fwi['color']};">{fwi['value']}</h1>
            <h3>{fwi['category']}</h3>
            <p>Fire Weather Index</p>
        </div>
        """, unsafe_allow_html=True)
    
    with fwi_col2:
        st.markdown("""
        The Fire Weather Index (FWI) estimates the potential intensity of wildfire based on weather conditions.
        
        **Key Factors:**
        - Temperature: Higher temperatures increase fire risk
        - Humidity: Lower humidity increases fire risk
        - Wind Speed: Stronger winds increase fire spread potential
        - Recent Rainfall: Recent precipitation reduces fire risk
        
        **FWI Categories:**
        - **Low (0-20)**: Fire ignition unlikely, slow spread if ignited
        - **Moderate (20-40)**: Fires may start and spread moderately
        - **High (40-60)**: Fire ignition likely with rapid spread
        - **Very High (60-80)**: Fires start easily and spread rapidly
        - **Extreme (80-100)**: Extremely dangerous fire conditions
        """)
else:
    st.warning("Current weather data not available for Fire Weather Index calculation")