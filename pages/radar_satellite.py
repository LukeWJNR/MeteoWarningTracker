"""
Radar & Satellite - View real-time weather radar and satellite imagery
"""
import streamlit as st
import folium
from streamlit_folium import folium_static
import requests
import json
from datetime import datetime, timedelta
import time
from PIL import Image
import io
import base64

# Configure page
st.set_page_config(page_title="Radar & Satellite Imagery", page_icon="🛰️", layout="wide")

# Title and description
st.title("🛰️ Radar & Satellite Imagery")
st.markdown("""
View the latest weather radar and satellite imagery to track storms, precipitation, 
cloud cover, and other meteorological conditions in real-time.
""")

# Access session state from main app
if 'lat' not in st.session_state:
    st.session_state.lat = 40.7128  # New York City
if 'lon' not in st.session_state:
    st.session_state.lon = -74.0060
if 'location' not in st.session_state:
    st.session_state.location = "New York, NY"

# Sidebar options
st.sidebar.header("Map Options")

# Imagery type selection
imagery_type = st.sidebar.selectbox(
    "Imagery Type",
    ["Radar", "Satellite (Visible)", "Satellite (Infrared)", "Satellite (Water Vapor)", "Temperature", "Precipitation"]
)

# Region selection
region_options = {
    "Current Location": "Center on location set in the main dashboard",
    "US - National": {"lat": 39.8, "lon": -98.5, "zoom": 4},
    "US - Northeast": {"lat": 42.5, "lon": -72.0, "zoom": 6},
    "US - Southeast": {"lat": 33.0, "lon": -84.0, "zoom": 6},
    "US - Midwest": {"lat": 41.0, "lon": -89.0, "zoom": 6},
    "US - Southwest": {"lat": 33.0, "lon": -112.0, "zoom": 6},
    "US - West Coast": {"lat": 37.0, "lon": -122.0, "zoom": 6},
    "US - Great Plains": {"lat": 40.0, "lon": -100.0, "zoom": 6},
    "North America": {"lat": 45.0, "lon": -100.0, "zoom": 3},
    "Europe": {"lat": 48.0, "lon": 10.0, "zoom": 4},
    "Asia": {"lat": 35.0, "lon": 105.0, "zoom": 3},
    "Australia": {"lat": -25.0, "lon": 135.0, "zoom": 4}
}

selected_region = st.sidebar.selectbox("Select Region", list(region_options.keys()))

# Set coordinates and zoom based on selection
if selected_region != "Current Location":
    center_lat = region_options[selected_region]["lat"]
    center_lon = region_options[selected_region]["lon"]
    zoom_level = region_options[selected_region]["zoom"]
    region_name = selected_region
else:
    center_lat = st.session_state.lat
    center_lon = st.session_state.lon
    zoom_level = 8
    region_name = st.session_state.location

# Animation options
st.sidebar.header("Animation Options")
show_animation = st.sidebar.checkbox("Show Animation", value=True)
animation_frames = st.sidebar.slider("Animation Frames", 5, 20, 10)
animation_interval = st.sidebar.slider("Frame Interval (ms)", 200, 1000, 500, 100)

# Function to get appropriate weather layer URL based on selection
def get_weather_layer_url(imagery_type, region):
    # These URLs would typically point to real weather service APIs
    # For this example, we'll use placeholder URLs that would be replaced with actual endpoints
    
    base_url = "https://api.weather.gov/radar/"
    
    # In a production app, you would use actual API endpoints from weather services
    layer_urls = {
        "Radar": f"{base_url}ridge/radar/{get_radar_station(center_lat, center_lon)}/standard",
        "Satellite (Visible)": "https://cdn.star.nesdis.noaa.gov/GOES16/ABI/CONUS/GEOCOLOR/latest.jpg",
        "Satellite (Infrared)": "https://cdn.star.nesdis.noaa.gov/GOES16/ABI/CONUS/13/latest.jpg",
        "Satellite (Water Vapor)": "https://cdn.star.nesdis.noaa.gov/GOES16/ABI/CONUS/09/latest.jpg",
        "Temperature": "https://cdn.star.nesdis.noaa.gov/GOES16/ABI/CONUS/11/latest.jpg",
        "Precipitation": f"{base_url}ridge/radar/{get_radar_station(center_lat, center_lon)}/precip"
    }
    
    return layer_urls.get(imagery_type, "")

# Function to determine the closest radar station based on coordinates
def get_radar_station(lat, lon):
    # This would typically query a database of radar stations to find the closest one
    # For this example, we'll use a simple approximation
    
    # Check if the location is in the US (approximately)
    is_us_location = (24 <= lat <= 50) and (-125 <= lon <= -66)
    
    if is_us_location:
        # Northeast
        if lon > -85 and lat > 37:
            return "BOX"  # Boston
        # Southeast
        elif lon > -85 and lat <= 37:
            return "ATL"  # Atlanta
        # Midwest
        elif -85 >= lon > -100 and lat > 37:
            return "LOT"  # Chicago
        # South Central
        elif -85 >= lon > -100 and lat <= 37:
            return "FWS"  # Dallas/Fort Worth
        # Northwest
        elif lon <= -100 and lat > 37:
            return "SEA"  # Seattle
        # Southwest
        else:
            return "PSR"  # Phoenix
    else:
        # Default to a central US station if outside the US
        return "OAX"  # Omaha

# Main content
col1, col2 = st.columns([3, 1])

with col1:
    st.subheader(f"{imagery_type} Imagery - {region_name}")
    
    # Create a base map
    m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_level, tiles="CartoDB positron")
    
    # Add marker for the center point if using current location
    if selected_region == "Current Location":
        folium.Marker(
            [center_lat, center_lon],
            popup=f"Center: {region_name}",
            icon=folium.Icon(color="blue", icon="info-sign")
        ).add_to(m)
    
    # Add weather overlay based on selection
    if imagery_type == "Radar":
        # Add radar overlay - in a real app, this would use actual radar tiles
        folium.TileLayer(
            name="Weather Radar",
            tiles="https://{s}.tile.openweathermap.org/map/precipitation_new/{z}/{x}/{y}.png?appid=your_api_key_here",
            attr="OpenWeatherMap",
            overlay=True,
            opacity=0.6
        ).add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Display the map
    folium_static(m, width=800, height=500)
    
    # Display static or animated imagery
    st.subheader(f"{imagery_type} Image")
    
    # In a real application, this would fetch actual imagery from weather services
    # For now, we'll display a message about imagery availability
    st.info(f"Imagery service integration is pending API key configuration.")
    
    # Placeholder for animation frames
    if show_animation:
        st.subheader("Animated Imagery")
        st.warning("Animation requires a weather data provider API key. Please configure it in the settings.")
        
        # Here we would typically create an animated GIF from a sequence of images
        # For now, we'll just display a placeholder
        st.markdown("""
        The animation would show:
        - Movement of weather systems
        - Precipitation intensity changes
        - Cloud formation and dissipation
        """)
    
    # Additional information about the imagery
    st.subheader("Imagery Information")
    st.markdown(f"""
    **Type:** {imagery_type}  
    **Region:** {region_name}  
    **Center Coordinates:** {center_lat:.4f}, {center_lon:.4f}  
    **Last Updated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    
    *Note: For real-time weather radar and satellite imagery, this application would integrate with:*
    - NOAA/NWS Weather Radar (NEXRAD)
    - GOES-16/17 Satellite Imagery
    - Various international weather services
    """)

with col2:
    # Legend explanation
    st.subheader("Imagery Guide")
    
    if imagery_type == "Radar":
        st.markdown("""
        ### Weather Radar
        
        Weather radar shows precipitation intensity:
        
        🟦 **Light Blue**: Light precipitation  
        🟩 **Green**: Moderate rain  
        🟨 **Yellow**: Heavy rain  
        🟧 **Orange**: Very heavy rain  
        🟥 **Red**: Extreme precipitation/possible hail
        
        Radar operates by sending out radio waves that bounce off precipitation particles in the atmosphere. The returned signal indicates the size and density of the particles.
        """)
    
    elif "Satellite" in imagery_type:
        if "Visible" in imagery_type:
            st.markdown("""
            ### Visible Satellite
            
            Visible satellite imagery shows reflected sunlight:
            
            ⚪ **White**: Thick clouds  
            🔘 **Gray**: Thin clouds  
            ⚫ **Black**: No clouds (clear sky)
            
            *Note: Visible satellite only works during daylight hours.*
            """)
        
        elif "Infrared" in imagery_type:
            st.markdown("""
            ### Infrared Satellite
            
            Infrared imagery shows cloud temperature:
            
            🟥 **Red/White**: Very cold/high clouds (severe storms)  
            🟧 **Orange/Yellow**: Cold/high clouds  
            🟩 **Green**: Mid-level clouds  
            🟦 **Blue**: Warm/low clouds or fog  
            ⚫ **Black/Gray**: No clouds (warm ground)
            
            Infrared imagery works 24 hours a day since it detects heat radiation.
            """)
        
        elif "Water Vapor" in imagery_type:
            st.markdown("""
            ### Water Vapor Satellite
            
            Water vapor imagery shows moisture in the mid to upper atmosphere:
            
            ⚪ **White**: High moisture content  
            🔘 **Gray**: Moderate moisture  
            ⚫ **Black**: Dry air
            
            This helps track atmospheric rivers, jet streams, and areas of potential storm development.
            """)
    
    elif imagery_type == "Temperature":
        st.markdown("""
        ### Temperature Map
        
        Temperature imagery shows surface temperatures:
        
        🟥 **Red/Purple**: Very hot  
        🟧 **Orange/Yellow**: Hot  
        🟩 **Green**: Moderate temperatures  
        🟦 **Light Blue**: Cool  
        🟪 **Dark Blue/Purple**: Cold
        """)
    
    elif imagery_type == "Precipitation":
        st.markdown("""
        ### Precipitation Map
        
        Precipitation maps show accumulated or forecast precipitation:
        
        🟦 **Light Blue**: Light precipitation (0-2.5mm)  
        🟩 **Green**: Moderate rain (2.5-10mm)  
        🟨 **Yellow**: Heavy rain (10-25mm)  
        🟧 **Orange**: Very heavy rain (25-50mm)  
        🟥 **Red**: Extreme precipitation (>50mm)
        """)
    
    # How to interpret
    st.subheader("How to Interpret")
    st.markdown("""
    ### Reading Weather Imagery
    
    - **Storm Structure**: Look for organized patterns that may indicate severe weather
    - **Movement**: Note the direction weather systems are moving
    - **Intensity Changes**: Watch for strengthening or weakening patterns
    - **Convergence Lines**: Where air masses meet (potential storm development)
    - **Rotation**: Hook-shaped radar returns may indicate rotation (possible tornado)
    
    ### Limitations
    
    - Radar can't see very light precipitation or very high clouds
    - Ground clutter and mountains can create false echoes
    - Satellite imagery has resolution limitations
    - Some imagery types have time delays before publishing
    """)
    
    # Resources for more information
    st.subheader("Additional Resources")
    st.markdown("""
    - [National Weather Service Radar](https://radar.weather.gov/)
    - [NOAA Satellite Images](https://www.star.nesdis.noaa.gov/GOES/index.php)
    - [College of DuPage NEXLAB](https://weather.cod.edu/satrad/)
    - [NWS Jetstream Weather School](https://www.weather.gov/jetstream/)
    """)
    
    # Disclaimer
    st.caption("""
    **Disclaimer**: This imagery is provided for informational purposes only.
    For critical weather decisions, always refer to official government weather service products and warnings.
    """)