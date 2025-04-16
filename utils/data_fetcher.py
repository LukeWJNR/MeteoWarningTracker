import requests
import pandas as pd
import numpy as np
import logging
from io import BytesIO
from datetime import datetime, timedelta

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
    
    def fetch_gdps_data(self, parameter, lat, lon, forecast_hours=72):
        """
        Fetch GDPS data for a specific parameter at a given location.
        
        Args:
            parameter (str): Weather parameter to fetch (e.g., 'TMP_TGL_2', 'APCP_SFC')
            lat (float): Latitude
            lon (float): Longitude
            forecast_hours (int): Number of forecast hours to fetch
        
        Returns:
            pd.DataFrame: Dataframe containing the forecast data
        """
        try:
            run_time = self.get_latest_gdps_run()
            logger.info(f"Fetching GDPS data for parameter {parameter}, run: {run_time}")
            
            # Construct URL for the data - exact URL pattern may need adjustment
            url = f"{self.BASE_URL}/api/gdps/{run_time}/{parameter}?lat={lat}&lon={lon}&hours={forecast_hours}"
            
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parse the response - format will depend on the API's actual response
            if response.headers.get('content-type') == 'application/json':
                data = response.json()
                return pd.DataFrame(data)
            else:
                # For CSV or other formats
                data = pd.read_csv(BytesIO(response.content))
                return data
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching GDPS data: {e}")
            return None
    
    def fetch_severe_warnings(self, lat, lon, radius_km=50):
        """
        Fetch severe weather warnings for a given location.
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            radius_km (int): Radius in kilometers to check for warnings
            
        Returns:
            list: List of warnings if any
        """
        try:
            url = f"{self.BASE_URL}/api/warnings?lat={lat}&lon={lon}&radius={radius_km}"
            
            response = self.session.get(url)
            response.raise_for_status()
            
            warnings_data = response.json()
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
        # This would need to be adjusted based on actual API
        # For now, return a hardcoded list of common parameters
        return [
            {"code": "TMP_TGL_2", "description": "Temperature at 2m", "unit": "°C"},
            {"code": "APCP_SFC", "description": "Precipitation", "unit": "mm"},
            {"code": "WDIR_TGL_10", "description": "Wind Direction at 10m", "unit": "degrees"},
            {"code": "WIND_TGL_10", "description": "Wind Speed at 10m", "unit": "km/h"},
            {"code": "PRMSL_MSL", "description": "Mean Sea Level Pressure", "unit": "hPa"},
            {"code": "RH_TGL_2", "description": "Relative Humidity at 2m", "unit": "%"},
            {"code": "TCDC_SFC", "description": "Total Cloud Cover", "unit": "%"}
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
            
            response = self.session.get(url)
            response.raise_for_status()
            
            grid_data = response.json()
            return grid_data
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching grid data: {e}")
            return None
    
    # For demo/testing, if the API is not accessible
    def generate_sample_data(self, parameter, hours=72):
        """
        Generate sample data for testing.
        Should only be used if the actual API is unavailable.
        
        Args:
            parameter (str): Parameter code
            hours (int): Number of forecast hours
            
        Returns:
            pd.DataFrame: Sample data
        """
        # Create a time series for the forecast period
        now = datetime.utcnow()
        time_index = [now + timedelta(hours=h) for h in range(hours)]
        
        # Generate values based on parameter
        if parameter == "TMP_TGL_2":  # Temperature
            base_temp = 20  # Base temperature in Celsius
            daily_variation = 8  # Daily temperature variation
            
            values = []
            for t in time_index:
                hour_fraction = (t.hour % 24) / 24
                daily_offset = -np.cos(2 * np.pi * hour_fraction) * daily_variation
                random_offset = np.random.normal(0, 0.5)  # Small random variation
                temp = base_temp + daily_offset + random_offset
                values.append(temp)
        
        elif parameter == "APCP_SFC":  # Precipitation
            # Most hours have 0 precipitation
            values = np.zeros(hours)
            # Add some random precipitation events
            rain_hours = np.random.choice(range(hours), size=int(hours * 0.2), replace=False)
            values[rain_hours] = np.random.exponential(2, size=len(rain_hours))
            
        elif parameter in ["WIND_TGL_10"]:  # Wind speed
            base_wind = 15  # Base wind speed in km/h
            values = np.random.normal(base_wind, 5, size=hours)
            values = np.maximum(0, values)  # No negative wind speeds
            
        else:  # Default random data
            values = np.random.normal(0, 1, size=hours)
        
        # Create dataframe
        df = pd.DataFrame({
            'time': time_index,
            'value': values
        })
        
        return df
