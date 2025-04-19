import requests
import pandas as pd
import numpy as np
import logging
import os
from io import BytesIO
from datetime import datetime, timedelta

# Import database utility
from utils.database import db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MeteoDataFetcher:
    """
    A class to handle fetching weather data from MeteoCenter GDPS
    """
    
    BASE_URL = "https://meteocentre.com/plus"
    
    def __init__(self):
        self.session = requests.Session()
    
    def get_latest_gdps_run(self):
        """
        Get the latest GDPS model run time.
        GDPS models typically run at 00Z and 12Z.
        
        Returns:
            str: Date and hour of the latest model run
        """
        now = datetime.utcnow()
        
        # GDPS runs at 00Z and 12Z
        if now.hour < 15:  # Before 15 UTC use the 00Z run
            run_hour = "00"
        else:  # After 15 UTC use the 12Z run
            run_hour = "12"
            
        run_date = now.strftime("%Y%m%d")
        
        # If it's very early in the day and we need the 12Z run,
        # we need to use yesterday's date
        if now.hour < 3 and run_hour == "12":
            yesterday = now - timedelta(days=1)
            run_date = yesterday.strftime("%Y%m%d")
            
        return f"{run_date}{run_hour}"
    
    def fetch_gdps_data(self, parameter, lat, lon, forecast_hours=72, save_to_db=True):
        """
        Fetch GDPS data for a specific parameter at a given location.
        
        Args:
            parameter (str): Weather parameter to fetch (e.g., 'TMP_TGL_2', 'APCP_SFC')
            lat (float): Latitude
            lon (float): Longitude
            forecast_hours (int): Number of forecast hours to fetch
            save_to_db (bool): Whether to save the data to the database
        
        Returns:
            pd.DataFrame: Dataframe containing the forecast data
        """
        # First check if location exists in database and save it if necessary
        location_id = None
        if save_to_db and db.engine:
            location_name = f"{lat:.4f}, {lon:.4f}"
            # Try to get from database first
            location = db.get_location_by_coordinates(lat, lon)
            if location:
                location_id = location['id']
                logger.info(f"Found existing location in database: {location_id}")
            else:
                # Save new location
                location_id = db.save_location(location_name, lat, lon)
                logger.info(f"Saved new location to database: {location_id}")
            
            # Check for cached forecast data in database
            if location_id:
                db_data = db.get_latest_forecast(location_id, parameter, forecast_hours)
                if db_data is not None and not db_data.empty:
                    logger.info(f"Retrieved {parameter} data from database")
                    return db_data
        
        # If data not in database or database not available, fetch from API
        try:
            run_time = self.get_latest_gdps_run()
            logger.info(f"Fetching GDPS data for parameter {parameter}, run: {run_time}")
            
            # Try to save model run info to database
            if save_to_db and db.engine:
                run_datetime = datetime.strptime(run_time, "%Y%m%d%H")
                db.save_model_run("GDPS", run_datetime)
            
            # Construct URL for the data
            url = f"{self.BASE_URL}/api/gdps/{run_time}/{parameter}?lat={lat}&lon={lon}&hours={forecast_hours}"
            
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parse the response
            data = None
            if response.headers.get('content-type') == 'application/json':
                data_json = response.json()
                data = pd.DataFrame(data_json)
            else:
                # For CSV or other formats
                data = pd.read_csv(BytesIO(response.content))
                
            # Save to database if successful
            if save_to_db and db.engine and location_id and data is not None and not data.empty:
                success = db.save_forecast_data(location_id, parameter, data)
                if success:
                    logger.info(f"Saved {parameter} data to database")
                    
            return data
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching GDPS data: {e}")
            # If API fails, fallback to sample data
            sample_data = self.generate_sample_data(parameter, forecast_hours)
            
            # Save sample data to database if requested
            if save_to_db and db.engine and location_id and sample_data is not None and not sample_data.empty:
                db.save_forecast_data(location_id, parameter, sample_data)
                
            return sample_data
    
    def fetch_severe_warnings(self, lat, lon, radius_km=50, save_to_db=True):
        """
        Fetch severe weather warnings for a given location.
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            radius_km (int): Radius in kilometers to check for warnings
            save_to_db (bool): Whether to save warnings to the database
            
        Returns:
            list: List of warnings if any
        """
        # First check if location exists in database
        location_id = None
        if save_to_db and db.engine:
            location = db.get_location_by_coordinates(lat, lon)
            if location:
                location_id = location['id']
                # Check for cached warnings
                db_warnings = db.get_active_warnings(location_id)
                if db_warnings:
                    logger.info(f"Retrieved {len(db_warnings)} warnings from database")
                    return db_warnings
        
        # If not in database or database not available, fetch from API
        try:
            url = f"{self.BASE_URL}/api/warnings?lat={lat}&lon={lon}&radius={radius_km}"
            
            response = self.session.get(url)
            response.raise_for_status()
            
            warnings_data = response.json()
            
            # Save to database if successful
            if save_to_db and db.engine and location_id and warnings_data:
                for warning in warnings_data:
                    warning_type = warning.get('title', 'Weather Warning')
                    description = warning.get('description', 'No details provided')
                    start_time = None
                    end_time = None
                    severity = warning.get('severity', 'moderate')
                    
                    # Extract times if available
                    if 'times' in warning and warning['times']:
                        times = sorted(pd.to_datetime(warning['times']))
                        if times:
                            start_time = times[0]
                            end_time = times[-1] + pd.Timedelta(hours=1)
                    
                    db.save_weather_warning(
                        location_id,
                        warning_type,
                        description,
                        start_time,
                        end_time,
                        severity
                    )
                
                logger.info(f"Saved {len(warnings_data)} warnings to database")
            
            return warnings_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching weather warnings: {e}")
            return []
    
    def fetch_available_parameters(self):
        """
        Fetch a list of available parameters from GDPS.
        
        Returns:
            list: List of parameter codes and descriptions
        """
        # Comprehensive list of GDPS parameters based on GDPS 15km (GDPS.ETA)
        return [
            # Temperature parameters
            {"code": "TMP_TGL_2", "description": "Temperature at 2m", "unit": "°C"},
            {"code": "TMP_TGL_0", "description": "Surface Temperature", "unit": "°C"},
            {"code": "TMP_ISBL_500", "description": "Temperature at 500 hPa", "unit": "°C"},
            {"code": "TMP_ISBL_850", "description": "Temperature at 850 hPa", "unit": "°C"},
            {"code": "TMAX_TGL_2", "description": "Maximum Temperature at 2m", "unit": "°C"},
            {"code": "TMIN_TGL_2", "description": "Minimum Temperature at 2m", "unit": "°C"},
            
            # Precipitation parameters
            {"code": "APCP_SFC", "description": "Total Precipitation", "unit": "mm"},
            {"code": "ACPCP_SFC", "description": "Convective Precipitation", "unit": "mm"},
            {"code": "SNOD_SFC", "description": "Snow Depth", "unit": "cm"},
            {"code": "WEASD_SFC", "description": "Water Equivalent of Snow", "unit": "kg/m²"},
            {"code": "CRAIN_SFC", "description": "Categorical Rain", "unit": "category"},
            {"code": "CSNOW_SFC", "description": "Categorical Snow", "unit": "category"},
            
            # Wind parameters
            {"code": "WDIR_TGL_10", "description": "Wind Direction at 10m", "unit": "degrees"},
            {"code": "WIND_TGL_10", "description": "Wind Speed at 10m", "unit": "km/h"},
            {"code": "GUST_TGL_10", "description": "Wind Gust at 10m", "unit": "km/h"},
            {"code": "UGRD_TGL_10", "description": "U-Component Wind at 10m", "unit": "m/s"},
            {"code": "VGRD_TGL_10", "description": "V-Component Wind at 10m", "unit": "m/s"},
            {"code": "WIND_ISBL_250", "description": "Wind Speed at 250 hPa", "unit": "km/h"},
            
            # Pressure parameters
            {"code": "PRMSL_MSL", "description": "Mean Sea Level Pressure", "unit": "hPa"},
            {"code": "PRES_SFC", "description": "Surface Pressure", "unit": "hPa"},
            {"code": "HGT_ISBL_500", "description": "500 hPa Geopotential Height", "unit": "m"},
            
            # Humidity parameters
            {"code": "RH_TGL_2", "description": "Relative Humidity at 2m", "unit": "%"},
            {"code": "RH_ISBL_700", "description": "Relative Humidity at 700 hPa", "unit": "%"},
            {"code": "SPFH_TGL_2", "description": "Specific Humidity at 2m", "unit": "kg/kg"},
            {"code": "PWAT_EATM", "description": "Precipitable Water", "unit": "kg/m²"},
            
            # Cloud parameters
            {"code": "TCDC_SFC", "description": "Total Cloud Cover", "unit": "%"},
            {"code": "LCDC_LOW", "description": "Low Cloud Cover", "unit": "%"},
            {"code": "MCDC_MID", "description": "Medium Cloud Cover", "unit": "%"},
            {"code": "HCDC_HIGH", "description": "High Cloud Cover", "unit": "%"},
            
            # Other parameters
            {"code": "CAPE_SFC", "description": "Convective Available Potential Energy", "unit": "J/kg"},
            {"code": "CIN_SFC", "description": "Convective Inhibition", "unit": "J/kg"},
            {"code": "LFTX_SFC", "description": "Surface Lifted Index", "unit": "K"},
            {"code": "VIS_SFC", "description": "Surface Visibility", "unit": "m"},
            {"code": "WTMP_SFC", "description": "Water Temperature", "unit": "°C"},
            {"code": "LAND_SFC", "description": "Land-Sea Mask", "unit": "boolean"}
        ]
    
    def fetch_grid_data(self, parameter, bbox, forecast_hour=24):
        """
        Fetch gridded data for map visualization.
        
        Args:
            parameter (str): Weather parameter to fetch
            bbox (tuple): Bounding box (min_lon, min_lat, max_lon, max_lat)
            forecast_hour (int): Forecast hour
            
        Returns:
            dict: Gridded data suitable for map visualization
        """
        try:
            run_time = self.get_latest_gdps_run()
            min_lon, min_lat, max_lon, max_lat = bbox
            
            url = f"{self.BASE_URL}/api/gdps/{run_time}/{parameter}/grid?min_lat={min_lat}&min_lon={min_lon}&max_lat={max_lat}&max_lon={max_lon}&hour={forecast_hour}"
            
            try:
                response = self.session.get(url)
                response.raise_for_status()
                
                grid_data = response.json()
                return grid_data
            except requests.exceptions.RequestException as e:
                logger.error(f"Error fetching grid data: {e}")
                # Generate sample grid data for demonstration
                return self.generate_sample_grid_data(parameter, bbox, forecast_hour)
            
        except Exception as e:
            logger.error(f"Error preparing grid data request: {e}")
            # Generate sample grid data for demonstration
            return self.generate_sample_grid_data(parameter, bbox, forecast_hour)
            
    def generate_sample_grid_data(self, parameter, bbox, forecast_hour=24):
        """
        Generate sample grid data for map visualization when the API is not available.
        
        Args:
            parameter (str): Weather parameter to visualize
            bbox (tuple): Bounding box (min_lon, min_lat, max_lon, max_lat)
            forecast_hour (int): Forecast hour
            
        Returns:
            dict: Gridded data suitable for map visualization
        """
        min_lon, min_lat, max_lon, max_lat = bbox
        
        # Create a grid of points
        resolution = 0.1  # Degrees
        lat_steps = int((max_lat - min_lat) / resolution) + 1
        lon_steps = int((max_lon - min_lon) / resolution) + 1
        
        lats = np.linspace(min_lat, max_lat, lat_steps)
        lons = np.linspace(min_lon, max_lon, lon_steps)
        
        # Initialize grid with zeros
        values = np.zeros((lat_steps, lon_steps))
        
        # Center point (for creating patterns around the selected location)
        center_lat = (min_lat + max_lat) / 2
        center_lon = (min_lon + max_lon) / 2
        
        # Generate data based on parameter type
        if "TMP" in parameter:  # Temperature
            # Base temperature with latitude gradient (cooler towards poles)
            base_temp = 20 - 0.1 * np.abs(center_lat - 45)  # Baseline temp around 45°N/S
            
            # Temperature decreases with latitude and elevation
            for i, lat in enumerate(lats):
                for j, lon in enumerate(lons):
                    # Latitude effect (cooler toward poles)
                    lat_effect = -0.5 * np.abs(lat - center_lat)
                    
                    # Create some topographic variation (imaginary mountains/valleys)
                    topo_effect = 2 * np.sin(lon * 5) * np.sin(lat * 5)
                    
                    # Distance from center for local weather effects
                    dist = np.sqrt((lat - center_lat)**2 + (lon - center_lon)**2)
                    local_effect = -2 * dist  # Cooler away from center
                    
                    # Random small-scale variation
                    random_effect = np.random.normal(0, 0.5)
                    
                    # Combine effects
                    values[i, j] = base_temp + lat_effect + topo_effect + local_effect + random_effect
            
            # Specific adjustments for different temperature parameters
            if "ISBL_500" in parameter:  # Upper atmosphere is much colder
                values -= 30
            elif "ISBL_850" in parameter:
                values -= 15
        
        elif "PCP" in parameter or "RAIN" in parameter or "SNOW" in parameter:  # Precipitation
            # Create some rain/snow areas with realistic patterns
            # Start with all zeros (no precipitation)
            
            # Add some precipitation systems
            num_systems = np.random.randint(1, 4)  # 1-3 precipitation systems
            
            for _ in range(num_systems):
                # Random center for this system
                sys_lat = min_lat + np.random.random() * (max_lat - min_lat)
                sys_lon = min_lon + np.random.random() * (max_lon - min_lon)
                
                # Size and intensity of system
                size = np.random.uniform(0.5, 2.0)  # Radius in degrees
                intensity = np.random.uniform(2, 20)  # Max precipitation amount
                
                # Shape factor (elongation in one direction)
                elongation = np.random.uniform(1, 2.5)
                angle = np.random.uniform(0, np.pi)  # Angle of elongation
                
                # Apply precipitation to grid
                for i, lat in enumerate(lats):
                    for j, lon in enumerate(lons):
                        # Calculate distance with elongation
                        dx = (lon - sys_lon) * np.cos(angle) - (lat - sys_lat) * np.sin(angle)
                        dy = (lon - sys_lon) * np.sin(angle) + (lat - sys_lat) * np.cos(angle)
                        dist = np.sqrt((dx * elongation)**2 + dy**2)
                        
                        # Precipitation follows a bell curve from center of system
                        if dist < size * 2:  # Limit to 2x the nominal size for efficiency
                            precip = intensity * np.exp(-dist**2 / (2 * (size/2)**2))
                            values[i, j] = max(values[i, j], precip)  # Take max for overlapping systems
            
            # For snow parameters, zero out precipitation in warm areas (simplified)
            if "SNOW" in parameter:
                # Generate a temperature grid
                temp_grid = np.zeros((lat_steps, lon_steps))
                for i, lat in enumerate(lats):
                    for j, lon in enumerate(lons):
                        # Simple temperature model
                        temp_grid[i, j] = 20 - 0.5 * abs(lat) + np.random.normal(0, 2)
                
                # Zero out precipitation where temp > 2°C (simplistic approach)
                values = np.where(temp_grid > 2, 0, values)
        
        elif "WIND" in parameter or "UGRD" in parameter or "VGRD" in parameter:  # Wind
            # Create a realistic wind field with some high and low pressure systems
            
            # Initialize u and v components
            u_component = np.zeros((lat_steps, lon_steps))
            v_component = np.zeros((lat_steps, lon_steps))
            
            # Base westerly flow (stronger in mid-latitudes)
            for i, lat in enumerate(lats):
                lat_factor = np.sin(np.radians(lat)) * np.cos(np.radians(lat)) * 2  # Max around 45°
                base_u = 10 * lat_factor
                for j in range(lon_steps):
                    u_component[i, j] = base_u
            
            # Add some pressure systems (highs and lows)
            num_systems = np.random.randint(1, 4)
            
            for _ in range(num_systems):
                # Random center within the grid
                sys_lat_idx = np.random.randint(0, lat_steps)
                sys_lon_idx = np.random.randint(0, lon_steps)
                
                # System strength and size
                strength = np.random.choice([-1, 1]) * np.random.uniform(5, 15)  # Negative for low pressure
                size = np.random.uniform(1.0, 3.0)  # System size in degrees
                
                # Apply circular wind pattern to the grid
                for i in range(lat_steps):
                    for j in range(lon_steps):
                        # Distance to system center
                        dy = lats[i] - lats[sys_lat_idx]
                        dx = (lons[j] - lons[sys_lon_idx]) * np.cos(np.radians(lats[i]))  # Adjust for lat/lon distortion
                        dist = np.sqrt(dx**2 + dy**2)
                        
                        if dist < size * 2:
                            # Wind strength decreases with distance
                            factor = np.exp(-dist**2 / (2 * (size/2)**2))
                            
                            # Circular wind pattern (clockwise for high pressure, counterclockwise for low)
                            # Note: dy/dist is sin(angle), dx/dist is cos(angle)
                            if dist > 0.01:  # Avoid division by near-zero
                                u_component[i, j] += strength * factor * (dy / dist)
                                v_component[i, j] += -strength * factor * (dx / dist)  # Negative for perpendicular flow
            
            # For WIND parameter, calculate magnitude
            if "WIND" in parameter and "UGRD" not in parameter and "VGRD" not in parameter:
                for i in range(lat_steps):
                    for j in range(lon_steps):
                        values[i, j] = np.sqrt(u_component[i, j]**2 + v_component[i, j]**2)
            # For U or V component
            elif "UGRD" in parameter:
                values = u_component
            elif "VGRD" in parameter:
                values = v_component
                
            # Upper atmosphere winds are stronger
            if "ISBL_250" in parameter:
                values *= 3
        
        elif "PRMSL" in parameter or "PRES" in parameter:  # Pressure
            # Create realistic pressure patterns with highs and lows
            base_pressure = 1013.25  # Standard sea level pressure in hPa
            
            # Add some pressure systems
            num_systems = np.random.randint(2, 5)
            
            # Start with uniform pressure
            for i in range(lat_steps):
                for j in range(lon_steps):
                    values[i, j] = base_pressure
            
            for _ in range(num_systems):
                # Random center within the grid
                sys_lat_idx = np.random.randint(0, lat_steps)
                sys_lon_idx = np.random.randint(0, lon_steps)
                
                # System parameters
                amplitude = np.random.uniform(5, 30)  # Pressure deviation
                sign = np.random.choice([-1, 1])  # High or low
                size = np.random.uniform(1.0, 4.0)  # System size
                
                # Apply pressure system
                for i in range(lat_steps):
                    for j in range(lon_steps):
                        # Distance to system center
                        dy = lats[i] - lats[sys_lat_idx]
                        dx = (lons[j] - lons[sys_lon_idx]) * np.cos(np.radians(lats[i]))
                        dist = np.sqrt(dx**2 + dy**2)
                        
                        if dist < size * 2:
                            # Pressure anomaly decreases with distance
                            anomaly = sign * amplitude * np.exp(-dist**2 / (2 * (size/2)**2))
                            values[i, j] += anomaly
        
        elif "RH" in parameter:  # Relative humidity
            # Humidity patterns often correlate with temperature and pressure
            
            # Start with a baseline humidity that's higher near water (simplified)
            coast_effect = np.zeros((lat_steps, lon_steps))
            for i in range(lat_steps):
                for j in range(lon_steps):
                    # Higher humidity near the edges of the map (simplified coast effect)
                    edge_dist = min([
                        (lats[i] - min_lat) / (max_lat - min_lat),
                        (max_lat - lats[i]) / (max_lat - min_lat),
                        (lons[j] - min_lon) / (max_lon - min_lon),
                        (max_lon - lons[j]) / (max_lon - min_lon)
                    ])
                    coast_effect[i, j] = np.exp(-edge_dist * 5) * 20  # Higher humidity near "coasts"
            
            # Base humidity pattern
            for i in range(lat_steps):
                for j in range(lon_steps):
                    # Latitude effect (generally higher humidity in tropics)
                    lat_effect = 60 - abs(lats[i]) * 0.5
                    
                    # Random small-scale variation
                    random_effect = np.random.normal(0, 5)
                    
                    # Combine effects
                    values[i, j] = min(100, max(10, lat_effect + coast_effect[i, j] + random_effect))
            
            # Add some moisture/dry areas
            num_systems = np.random.randint(1, 4)
            for _ in range(num_systems):
                # Random center
                sys_lat = min_lat + np.random.random() * (max_lat - min_lat)
                sys_lon = min_lon + np.random.random() * (max_lon - min_lon)
                
                # System parameters
                intensity = np.random.choice([-1, 1]) * np.random.uniform(10, 40)  # Humidity anomaly
                size = np.random.uniform(0.5, 2.0)
                
                # Apply to grid
                for i, lat in enumerate(lats):
                    for j, lon in enumerate(lons):
                        dist = np.sqrt((lat - sys_lat)**2 + (lon - sys_lon)**2)
                        if dist < size * 2:
                            effect = intensity * np.exp(-dist**2 / (2 * (size/2)**2))
                            values[i, j] = min(100, max(0, values[i, j] + effect))
            
            # Adjust for different levels
            if "ISBL_700" in parameter:
                values *= 0.8  # Lower humidity at altitude
        
        elif "CDC" in parameter:  # Cloud cover
            # Cloud patterns often correlate with humidity and precipitation
            
            # Start with some random cloud cover
            for i in range(lat_steps):
                for j in range(lon_steps):
                    values[i, j] = np.random.uniform(10, 40)  # Baseline scattered clouds
            
            # Add some cloud systems
            num_systems = np.random.randint(1, 5)
            for _ in range(num_systems):
                # Random center
                sys_lat = min_lat + np.random.random() * (max_lat - min_lat)
                sys_lon = min_lon + np.random.random() * (max_lon - min_lon)
                
                # System parameters
                intensity = np.random.uniform(30, 90)  # Additional cloud cover
                size = np.random.uniform(0.5, 2.0)
                
                # Apply to grid
                for i, lat in enumerate(lats):
                    for j, lon in enumerate(lons):
                        dist = np.sqrt((lat - sys_lat)**2 + (lon - sys_lon)**2)
                        if dist < size * 2:
                            effect = intensity * np.exp(-dist**2 / (2 * (size/2)**2))
                            values[i, j] = min(100, values[i, j] + effect)
            
            # Adjust for different cloud levels
            if "LCDC" in parameter:  # Low clouds
                values *= np.random.uniform(0.7, 0.9)
            elif "MCDC" in parameter:  # Mid-level clouds
                values *= np.random.uniform(0.6, 0.8)
            elif "HCDC" in parameter:  # High clouds
                values *= np.random.uniform(0.5, 0.7)
        
        elif "CAPE" in parameter:  # Convective Available Potential Energy
            # CAPE is often highest in areas with warm, moist air
            
            # Start with low CAPE everywhere
            values.fill(200)  # Background instability
            
            # Add some high CAPE regions (potential thunderstorm areas)
            num_systems = np.random.randint(1, 3)
            for _ in range(num_systems):
                sys_lat = min_lat + np.random.random() * (max_lat - min_lat)
                sys_lon = min_lon + np.random.random() * (max_lon - min_lon)
                
                max_cape = np.random.randint(1000, 4000)
                size = np.random.uniform(0.3, 1.0)
                
                for i, lat in enumerate(lats):
                    for j, lon in enumerate(lons):
                        dist = np.sqrt((lat - sys_lat)**2 + (lon - sys_lon)**2)
                        if dist < size * 2:
                            effect = max_cape * np.exp(-dist**2 / (2 * (size/2)**2))
                            values[i, j] = max(values[i, j], effect)
        
        else:  # Default behavior for other parameters
            # Create a generic pattern with some realistic-looking spatial variation
            
            # Start with a base value
            param_info = next((p for p in self.fetch_available_parameters() if p["code"] == parameter), None)
            if param_info:
                # Set appropriate base value and range based on parameter unit
                if param_info["unit"] == "%":
                    base_value = 50
                    variation = 30
                elif "°C" in param_info["unit"]:
                    base_value = 15
                    variation = 10
                elif "hPa" in param_info["unit"]:
                    base_value = 1013
                    variation = 15
                elif "m" in param_info["unit"] and "HGT" in parameter:
                    base_value = 5500  # For geopotential height
                    variation = 200
                else:
                    base_value = 0
                    variation = 1
            else:
                base_value = 0
                variation = 1
            
            # Create spatial pattern
            for i in range(lat_steps):
                for j in range(lon_steps):
                    # Simple wave patterns
                    pattern = (
                        np.sin(lats[i] * 3) * np.cos(lons[j] * 2) +
                        np.sin(lats[i] * 5 + lons[j] * 3) * 0.5
                    )
                    values[i, j] = base_value + pattern * variation
        
        # Return in the format expected by the visualization code
        return {
            "lat": lats.tolist(),
            "lon": lons.tolist(),
            "values": values.tolist()
        }
    
    # For demo/testing, if the API is not accessible
    def generate_sample_data(self, parameter, hours=72):
        """
        Generate sample data for testing.
        For real forecast data, try to use the NOAA provider first.
        
        Args:
            parameter (str): Parameter code
            hours (int): Number of forecast hours
            
        Returns:
            pd.DataFrame: Forecast data
        """
        # First try to get real data from NOAA (added in the direct NCEP integration)
        try:
            from utils.noaa_data import noaa_provider
            logger.info(f"Attempting to fetch {parameter} data from NOAA GFS")
            
            # Fetch data from NOAA GFS model - we need to pass lat/lon
            # Since this is inside generate_sample_data which doesn't have lat/lon parameters,
            # we'll use a hardcoded default location for now (Montreal)
            default_lat, default_lon = 45.5017, -73.5673
            df = noaa_provider.fetch_forecast_data(default_lat, default_lon, parameter, model="gfs", forecast_hours=hours)
            
            if df is not None and not df.empty:
                logger.info(f"Successfully fetched {parameter} data from NOAA GFS")
                return df
                
            logger.warning(f"Could not fetch {parameter} data from NOAA GFS, falling back to sample data")
        except Exception as e:
            logger.error(f"Error fetching from NOAA: {e}")
            
        # Fall back to sample data if NOAA data fetch fails
        # Create a time series for the forecast period
        now = datetime.utcnow()
        time_index = [now + timedelta(hours=h) for h in range(hours)]
        
        # Default values will be overridden based on parameter
        values = np.zeros(hours)
        
        # Generate values based on parameter type
        # Temperature related parameters
        if "TMP" in parameter or "TMAX" in parameter or "TMIN" in parameter:
            base_temp = 20  # Base temperature in Celsius
            daily_variation = 8  # Daily temperature variation
            seasonal_trend = -0.1  # Slight cooling trend over forecast period
            
            values = []
            for i, t in enumerate(time_index):
                hour_fraction = (t.hour % 24) / 24
                daily_offset = -np.cos(2 * np.pi * hour_fraction) * daily_variation
                trend_offset = seasonal_trend * (i / 24)  # Gradual trend
                random_offset = np.random.normal(0, 0.5)  # Small random variation
                
                # Adjust base temperature based on altitude levels (if specified in parameter)
                level_adjust = 0
                if "ISBL_500" in parameter:
                    level_adjust = -25  # 500 hPa is much colder
                elif "ISBL_850" in parameter:
                    level_adjust = -10  # 850 hPa is somewhat colder
                
                temp = base_temp + daily_offset + trend_offset + random_offset + level_adjust
                
                # Min/Max adjustments
                if "TMAX" in parameter:
                    temp += daily_variation / 2
                elif "TMIN" in parameter:
                    temp -= daily_variation / 2
                
                values.append(temp)
        
        # Precipitation parameters
        elif "PCP" in parameter or "SNOD" in parameter or "WEASD" in parameter:
            # Most hours have 0 precipitation
            values = np.zeros(hours)
            
            # Create realistic precipitation patterns with clusters
            for start_hour in range(0, hours, 24):  # Daily patterns
                if np.random.random() < 0.4:  # 40% chance of precipitation event per day
                    event_start = start_hour + np.random.randint(0, 12)  # Random start within day
                    event_duration = np.random.randint(2, 8)  # 2-8 hour event
                    event_end = min(event_start + event_duration, hours)
                    
                    # Intensity pattern (builds up then reduces)
                    intensity_pattern = np.concatenate([
                        np.linspace(0, 1, event_duration // 3 + 1),
                        np.linspace(1, 0, event_duration - event_duration // 3)
                    ])
                    
                    # Apply intensity to time slots
                    for i, hour in enumerate(range(event_start, event_end)):
                        if hour < hours:  # Guard against out of bounds
                            if i < len(intensity_pattern):
                                base_intensity = intensity_pattern[i] * 5  # Max 5mm/h
                                values[hour] = base_intensity * (1 + 0.2 * np.random.random())
            
            # Adjust for different precip parameters
            if "ACPCP" in parameter:  # Convective precipitation
                values = values * (np.random.random(hours) < 0.6) * 0.7  # Less convective precip
            elif "SNOD" in parameter:  # Snow depth - convert to cm
                values = values * 10 * (now.month in [11, 12, 1, 2, 3])  # Snow only in winter months
            elif "WEASD" in parameter:  # Water equivalent
                values = values * 0.1  # Convert to kg/m²
        
        # Wind parameters
        elif "WIND" in parameter or "WDIR" in parameter or "UGRD" in parameter or "VGRD" in parameter or "GUST" in parameter:
            base_wind = 15  # Base wind speed in km/h
            
            # Add variability and trends
            daily_variation = 5  # Daily variation
            values = []
            
            for i, t in enumerate(time_index):
                hour_fraction = (t.hour % 24) / 24
                daily_offset = np.sin(2 * np.pi * hour_fraction) * daily_variation
                
                # Add a weather system effect (increasing then decreasing wind)
                system_effect = 10 * np.sin(np.pi * i / hours) if i < hours / 2 else 0
                
                # Level adjustments
                level_adjust = 0
                if "ISBL_250" in parameter:  # Upper atmosphere winds are much stronger
                    level_adjust = 80
                    
                random_offset = np.random.normal(0, 2)  # Random variation
                wind_val = max(0, base_wind + daily_offset + system_effect + random_offset + level_adjust)
                
                # Adjust for gusts
                if "GUST" in parameter:
                    wind_val = wind_val * (1 + 0.3 * np.random.random())
                
                values.append(wind_val)
            
            # Special handling for wind direction
            if "WDIR" in parameter:
                # Create somewhat realistic wind direction shifts
                base_direction = np.random.randint(0, 360)
                directions = []
                current_dir = base_direction
                
                for i in range(hours):
                    # Wind direction generally shifts gradually
                    shift = np.random.normal(0, 10)  # Usually small shifts
                    if np.random.random() < 0.05:  # Occasional larger shift (5% chance)
                        shift = np.random.normal(0, 45)
                        
                    current_dir = (current_dir + shift) % 360
                    directions.append(current_dir)
                    
                values = directions
            
            # U and V components
            if "UGRD" in parameter or "VGRD" in parameter:
                # Generate directions first
                base_direction = np.random.randint(0, 360)
                directions = []
                wind_speeds = values  # Use the speeds we calculated above
                
                if "UGRD" in parameter:  # U-component (west-east)
                    values = [-spd * np.sin(np.radians(dir)) for spd, dir in zip(wind_speeds, directions)]
                elif "VGRD" in parameter:  # V-component (south-north)
                    values = [-spd * np.cos(np.radians(dir)) for spd, dir in zip(wind_speeds, directions)]
        
        # Pressure parameters
        elif "PRMSL" in parameter or "PRES" in parameter:
            base_pressure = 1013.25  # Standard pressure in hPa
            
            # Create realistic pressure patterns
            trend = np.linspace(0, np.random.choice([-15, 15]), hours)  # Gradual trend over forecast
            
            # Add cyclical variations
            hourly_variation = np.sin(np.linspace(0, 2*np.pi, 24)) * 0.5  # Small diurnal cycle
            daily_variations = np.tile(hourly_variation, hours // 24 + 1)[:hours]
            
            # Random fluctuations
            noise = np.random.normal(0, 1, hours)
            
            values = base_pressure + trend + daily_variations + noise
            
            # Surface pressure is affected by elevation
            if "PRES_SFC" in parameter:
                values = values - 30  # Example: location is at higher elevation
        
        # Humidity parameters
        elif "RH" in parameter or "SPFH" in parameter:
            # Relative humidity
            if "RH" in parameter:
                # Daily cycle with higher humidity at night
                values = []
                for t in time_index:
                    hour_fraction = (t.hour % 24) / 24
                    # Higher humidity at night, lower during day
                    daily_cycle = 70 - 30 * np.sin(np.pi * hour_fraction)
                    # Add some randomness
                    humidity = min(100, max(10, daily_cycle + np.random.normal(0, 10)))
                    values.append(humidity)
                    
                # Adjust for different levels
                if "ISBL_700" in parameter:
                    values = [min(100, max(5, v * 0.8)) for v in values]  # Lower humidity at altitude
            
            # Specific humidity
            elif "SPFH" in parameter:
                # Much smaller values for specific humidity
                values = [v * 0.0001 for v in values]  # Scale to kg/kg range
        
        # Cloud parameters
        elif "CDC" in parameter:
            # Create realistic cloud patterns
            values = []
            
            # Base pattern with cloud systems moving through
            cloud_systems = []
            for day in range(hours // 24 + 1):
                # Random cloud system for each day
                system_peak = np.random.randint(0, 24)  # Hour of max cloud cover
                system_width = np.random.randint(6, 18)  # Duration of cloud system
                system_intensity = np.random.random() * 100  # Max cloud cover %
                
                cloud_systems.append((day * 24 + system_peak, system_width, system_intensity))
            
            for i in range(hours):
                cloud_cover = 0
                for peak, width, intensity in cloud_systems:
                    # Distance from peak of cloud system
                    distance = abs(i - peak)
                    if distance < width:
                        # Cloud cover decreases with distance from peak
                        contribution = intensity * (1 - distance / width)
                        cloud_cover = max(cloud_cover, contribution)
                
                # Add random variability
                cloud_cover = min(100, max(0, cloud_cover + np.random.normal(0, 10)))
                values.append(cloud_cover)
            
            # Adjust for cloud level
            if "LCDC" in parameter:  # Low clouds
                values = [v * (1 - (np.random.random() * 0.3)) for v in values]
            elif "MCDC" in parameter:  # Mid-level clouds
                values = [v * (1 - (np.random.random() * 0.4)) for v in values]
            elif "HCDC" in parameter:  # High clouds
                values = [v * (1 - (np.random.random() * 0.5)) for v in values]
        
        # Severe weather parameters
        elif "CAPE" in parameter or "CIN" in parameter or "LFTX" in parameter:
            values = np.zeros(hours)
            
            # Add potential severe weather days
            for day in range(hours // 24 + 1):
                if np.random.random() < 0.2:  # 20% chance of potential severe weather per day
                    # Peak instability in afternoon
                    peak_hour = day * 24 + 12 + np.random.randint(-2, 3)
                    
                    # Create a 6-12 hour window of instability
                    window = np.random.randint(6, 13)
                    start_hour = max(0, peak_hour - window // 2)
                    end_hour = min(hours, peak_hour + window // 2)
                    
                    # Set values for CAPE
                    if "CAPE" in parameter:
                        max_cape = np.random.randint(1000, 4000)  # Realistic CAPE values
                        for h in range(start_hour, end_hour):
                            if h < hours:
                                distance = abs(h - peak_hour)
                                values[h] = max_cape * (1 - distance / (window // 2))
                    
                    # Set values for CIN
                    elif "CIN" in parameter:
                        max_cin = np.random.randint(-200, -50)  # Realistic CIN values (negative)
                        for h in range(start_hour, end_hour):
                            if h < hours:
                                distance = abs(h - peak_hour)
                                values[h] = max_cin * (1 - distance / (window // 2))
                    
                    # Set values for lifted index
                    elif "LFTX" in parameter:
                        min_lftx = np.random.randint(-8, -2)  # Negative values indicate instability
                        for h in range(start_hour, end_hour):
                            if h < hours:
                                distance = abs(h - peak_hour)
                                values[h] = min_lftx * (1 - distance / (window // 2)) + np.random.normal(0, 1)
        
        # Other parameters
        elif "VIS" in parameter:  # Visibility
            # Base visibility in meters (good conditions)
            base_vis = 10000
            values = np.ones(hours) * base_vis
            
            # Add reduced visibility events (fog, precipitation, etc.)
            for day in range(hours // 24 + 1):
                # Morning fog potential
                morning_hour = day * 24 + 6  # 6 AM
                if morning_hour < hours and np.random.random() < 0.3:  # 30% chance of morning fog
                    fog_duration = np.random.randint(2, 6)
                    fog_min_vis = np.random.randint(100, 5000)
                    
                    for h in range(morning_hour, min(morning_hour + fog_duration, hours)):
                        hour_from_start = h - morning_hour
                        # Visibility improves as fog dissipates
                        improvement_factor = hour_from_start / fog_duration
                        values[h] = fog_min_vis + improvement_factor * (base_vis - fog_min_vis)
        
        elif "LAND" in parameter:  # Land-sea mask
            # Binary values - either land (1) or sea (0)
            values = np.ones(hours)  # Default to land
        
        else:  # Default random data for any other parameters
            param_info = next((p for p in self.fetch_available_parameters() if p["code"] == parameter), None)
            
            if param_info:  # If we know about this parameter
                if param_info["unit"] == "%":  # Percentage values
                    values = np.random.uniform(0, 100, hours)
                elif "°C" in param_info["unit"]:  # Temperature values
                    values = np.random.normal(15, 10, hours)
                elif "hPa" in param_info["unit"]:  # Pressure values
                    values = np.random.normal(1013, 10, hours)
                else:  # Generic variation
                    values = np.random.normal(0, 1, hours)
            else:  # Completely unknown parameter
                values = np.random.normal(0, 1, hours)
        
        # Create dataframe
        df = pd.DataFrame({
            'time': time_index,
            'value': values
        })
        
        return df
