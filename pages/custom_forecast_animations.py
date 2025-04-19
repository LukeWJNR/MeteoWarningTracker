"""
Custom Forecast Animations - Generate and view forecast animations created directly from forecast data
"""
import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime, timedelta
import folium
from streamlit_folium import folium_static
import os
import io
from PIL import Image

# Import utility modules
from utils.forecast_generator import forecast_generator

st.set_page_config(page_title="Custom Forecast Animations", page_icon="🌀", layout="wide")

# Main content
st.title("🌀 Custom Forecast Animations")
st.markdown("""
Generate custom forecast animations directly from NOAA/NWS forecast data.
These animations are created from raw gridded forecast data rather than pre-rendered images.
""")

# Sidebar for parameter selection
st.sidebar.header("Parameter Selection")

# Get available parameters from the data fetcher
parameters = forecast_generator.data_fetcher.fetch_available_parameters()

# Group parameters by category
parameter_groups = {
    "Temperature": [p for p in parameters if p["code"].startswith("T") and not p["code"].startswith("TCDC")],
    "Precipitation": [p for p in parameters if p["code"].startswith("A") or p["code"].startswith("SNO")],
    "Wind": [p for p in parameters if "WIND" in p["code"] or "GUST" in p["code"]],
    "Pressure": [p for p in parameters if "PRES" in p["code"] or "PRMSL" in p["code"] or p["code"].startswith("HGT")],
    "Humidity": [p for p in parameters if "RH" in p["code"] or "SPFH" in p["code"] or "PWAT" in p["code"]],
    "Severe Weather": [p for p in parameters if "CAPE" in p["code"] or "CIN" in p["code"] or "LFT" in p["code"]],
    "Other": [p for p in parameters if not any(p["code"].startswith(prefix) for prefix in 
                                              ["T", "A", "SNO", "WIND", "GUST", "PRES", "PRMSL", "HGT", "RH", "SPFH", "PWAT", "CAPE", "CIN", "LFT"])]
}

# Sidebar for parameter category selection
selected_category = st.sidebar.selectbox("Parameter Category", list(parameter_groups.keys()))

# Display parameters in the selected category
selected_param_info = st.sidebar.selectbox(
    "Parameter",
    parameter_groups[selected_category],
    format_func=lambda x: f"{x['description']} ({x['unit']})"
)

selected_param = selected_param_info["code"]

# Region selection
st.sidebar.header("Region Selection")
regions = {
    "na": "North America",
    "us": "United States",
    "eu": "Europe",
    "global": "Global View",
    "atl": "Atlantic Ocean",
    "pac": "Pacific Ocean",
    "asia": "Asia",
    "aus": "Australia",
    "sa": "South America",
    "af": "Africa"
}

selected_region = st.sidebar.selectbox(
    "Region",
    list(regions.keys()),
    format_func=lambda x: regions[x]
)

# Advanced options
st.sidebar.header("Advanced Options")
forecast_mode = st.sidebar.radio(
    "Forecast Mode",
    ["Animation", "Interactive Map"]
)

# Forecast hour selection (for interactive map)
if forecast_mode == "Interactive Map":
    forecast_hour = st.sidebar.slider("Forecast Hour", 0, 72, 24, 6)

# Main content based on selections
st.markdown(f"## {selected_param_info['description']} - {regions[selected_region]}")

# Button to generate the forecast
if st.button(f"Generate {forecast_mode}"):
    with st.spinner(f"Generating {forecast_mode.lower()}, please wait..."):
        if forecast_mode == "Animation":
            # Generate animation
            st.info(f"Fetching {selected_param_info['description']} data for {regions[selected_region]}...")
            animation_data = forecast_generator.generate_forecast_animation(selected_param, selected_region)
            
            if animation_data:
                # Display animation
                st.success("Animation generated successfully!")
                
                # Display metadata
                run_time = forecast_generator.data_fetcher.get_latest_gdps_run()
                run_datetime = datetime.strptime(run_time, "%Y%m%d%H")
                
                with st.expander("Forecast Information", expanded=True):
                    st.markdown(f"**Parameter**: {selected_param_info['description']} ({selected_param_info['unit']})")
                    st.markdown(f"**Region**: {regions[selected_region]}")
                    st.markdown(f"**Model Run**: {run_datetime.strftime('%Y-%m-%d %H:00Z')}")
                    
                # Display the animation
                st.image(animation_data, caption=f"{selected_param_info['description']} forecast animation")
                
                # Offer download option
                st.download_button(
                    label="Download Animation",
                    data=animation_data,
                    file_name=f"{selected_param}_{selected_region}_{run_time}.gif",
                    mime="image/gif"
                )
            else:
                st.error("Could not generate animation. There may be issues with data availability.")
                st.info("Please try a different parameter, region, or check again later.")
        else:
            # Generate interactive map
            st.info(f"Creating interactive map for {selected_param_info['description']} at forecast hour +{forecast_hour}h...")
            
            map_object = forecast_generator.create_interactive_forecast_map(
                selected_param, 
                selected_region,
                forecast_hour
            )
            
            if map_object:
                # Display the map
                st.success("Interactive map created successfully!")
                folium_static(map_object, width=800, height=600)
                
                # Display metadata in an expander
                run_time = forecast_generator.data_fetcher.get_latest_gdps_run()
                run_datetime = datetime.strptime(run_time, "%Y%m%d%H")
                valid_time = run_datetime + timedelta(hours=forecast_hour)
                
                with st.expander("Forecast Information", expanded=True):
                    st.markdown(f"**Parameter**: {selected_param_info['description']} ({selected_param_info['unit']})")
                    st.markdown(f"**Region**: {regions[selected_region]}")
                    st.markdown(f"**Model Run**: {run_datetime.strftime('%Y-%m-%d %H:00Z')}")
                    st.markdown(f"**Valid Time**: {valid_time.strftime('%Y-%m-%d %H:00Z')} (+{forecast_hour}h)")
            else:
                st.error("Could not create interactive map. There may be issues with data availability.")
                st.info("Please try a different parameter, region, or check again later.")

# Show helpful information on predefined animations
st.markdown("---")
st.markdown("## Tips for Custom Forecast Animations")
st.markdown("""
- **Temperature Parameters** are useful for identifying warm and cold fronts
- **Precipitation Parameters** show rainfall and snowfall forecasts
- **CAPE** (Convective Available Potential Energy) indicates thunderstorm potential
- **500 hPa Geopotential Height** shows the large-scale atmospheric pattern
- **Mean Sea Level Pressure** helps identify high and low pressure systems
""")

st.markdown("---")
st.caption("Data provided by NOAA/NWS. Animations and maps are generated directly from forecast data, not from pre-rendered images.")