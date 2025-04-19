"""
Utility for fetching weather data from Visual Crossing Weather API
"""
import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VisualCrossingAPI:
    """
    Class for fetching weather data from Visual Crossing Weather API
    """
    BASE_URL = "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
    
    def __init__(self):
        """Initialize the API client with API key from environment variables"""
        self.api_key = os.environ.get('VISUAL_CROSSING_API_KEY')
        if not self.api_key:
            logger.warning("Visual Crossing API key not found in environment variables")
        
    def get_forecast(self, lat, lon, days=7, include_current=True):
        """
        Get weather forecast for a location
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            days (int): Number of days to forecast
            include_current (bool): Include current conditions
            
        Returns:
            dict: Weather forecast data
        """
        try:
            location = f"{lat},{lon}"
            url = f"{self.BASE_URL}/{location}"
            
            params = {
                'unitGroup': 'metric',
                'key': self.api_key,
                'include': 'days,hours,current,alerts',
                'contentType': 'json',
                'elements': 'datetime,datetimeEpoch,temp,feelslike,dew,humidity,precip,precipprob,preciptype,snow,windspeed,winddir,pressure,cloudcover,visibility,uvindex,conditions,description,icon,sunrise,sunset,moonphase,precipcover,windgust,severerisk'
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()  # Raise exception for HTTP errors
            
            data = response.json()
            return data
            
        except Exception as e:
            logger.error(f"Error fetching forecast data: {str(e)}")
            return None
    
    def get_historical_data(self, lat, lon, start_date, end_date=None):
        """
        Get historical weather data for a location
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            start_date (str): Start date in format YYYY-MM-DD
            end_date (str, optional): End date in format YYYY-MM-DD. Defaults to start_date.
            
        Returns:
            dict: Historical weather data
        """
        try:
            location = f"{lat},{lon}"
            
            # If end_date not provided, use start_date (single day)
            if not end_date:
                end_date = start_date
                
            date_range = f"{start_date}/{end_date}"
            url = f"{self.BASE_URL}/{location}/{date_range}"
            
            params = {
                'unitGroup': 'metric',
                'key': self.api_key,
                'include': 'days,hours',
                'contentType': 'json'
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            return data
            
        except Exception as e:
            logger.error(f"Error fetching historical data: {str(e)}")
            return None
    
    def get_severe_alerts(self, lat, lon):
        """
        Get severe weather alerts for a location
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            
        Returns:
            list: List of active severe weather alerts
        """
        try:
            # Get forecast data which includes alerts
            data = self.get_forecast(lat, lon, days=1)
            
            if data and 'alerts' in data:
                return data['alerts']
            return []
            
        except Exception as e:
            logger.error(f"Error fetching severe alerts: {str(e)}")
            return []
    
    def get_current_conditions(self, lat, lon):
        """
        Get current weather conditions for a location
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            
        Returns:
            dict: Current weather conditions
        """
        try:
            # Get forecast data which includes current conditions
            data = self.get_forecast(lat, lon, days=1)
            
            if data and 'currentConditions' in data:
                return data['currentConditions']
            return None
            
        except Exception as e:
            logger.error(f"Error fetching current conditions: {str(e)}")
            return None
    
    def get_forecast_df(self, lat, lon, days=7):
        """
        Get weather forecast as a pandas DataFrame
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            days (int): Number of days to forecast
            
        Returns:
            pd.DataFrame: Forecast data with date index
        """
        try:
            # Get forecast data
            data = self.get_forecast(lat, lon, days=days)
            
            if not data or 'days' not in data:
                return pd.DataFrame()
            
            # Extract daily forecast data
            daily_data = data['days']
            
            # Convert to DataFrame
            df = pd.DataFrame(daily_data)
            
            # Convert datetime to datetime objects and set as index
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime')
            
            return df
            
        except Exception as e:
            logger.error(f"Error creating forecast DataFrame: {str(e)}")
            return pd.DataFrame()
    
    def get_hourly_forecast_df(self, lat, lon, days=3):
        """
        Get hourly weather forecast as a pandas DataFrame
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            days (int): Number of days to forecast hourly data for
            
        Returns:
            pd.DataFrame: Hourly forecast data with datetime index
        """
        try:
            # Get forecast data
            data = self.get_forecast(lat, lon, days=days)
            
            if not data or 'days' not in data:
                return pd.DataFrame()
            
            # Extract hourly forecast data from all days
            hourly_data = []
            for day in data['days']:
                if 'hours' in day:
                    # Add date to each hour
                    date = day['datetime']
                    for hour in day['hours']:
                        # Create full datetime string
                        hour['datetime'] = f"{date}T{hour['datetime']}"
                    hourly_data.extend(day['hours'])
            
            # Convert to DataFrame
            df = pd.DataFrame(hourly_data)
            
            # Convert datetime to datetime objects and set as index
            df['datetime'] = pd.to_datetime(df['datetime'])
            df = df.set_index('datetime')
            
            return df
            
        except Exception as e:
            logger.error(f"Error creating hourly forecast DataFrame: {str(e)}")
            return pd.DataFrame()
    
    def calculate_fire_weather_index(self, data):
        """
        Calculate a simplified Fire Weather Index from weather data
        
        Args:
            data (dict): Weather data dictionary with temperature, humidity, wind speed, and precipitation
            
        Returns:
            dict: Fire Weather Index and category
        """
        try:
            # Extract required parameters
            temp = data.get('temp', 0)  # Temperature in Celsius
            humidity = data.get('humidity', 50)  # Relative humidity in percent
            wind_speed = data.get('windspeed', 0)  # Wind speed in km/h
            precip = data.get('precip', 0)  # Precipitation in mm
            
            # Simple FWI calculation (simplified version of Canadian FWI system)
            # Temperature component (higher temp = higher risk)
            temp_factor = max(0, (temp - 10) / 30)
            
            # Humidity component (lower humidity = higher risk)
            humidity_factor = max(0, (100 - humidity) / 100)
            
            # Wind component (higher wind = higher risk)
            wind_factor = min(1, wind_speed / 40)
            
            # Precipitation component (recent rain reduces risk)
            precip_factor = max(0, 1 - (precip / 5))
            
            # Calculate FWI (0-100 scale)
            fwi = 100 * (0.3 * temp_factor + 0.3 * humidity_factor + 0.2 * wind_factor + 0.2 * precip_factor)
            fwi = max(0, min(100, fwi))  # Clamp between 0-100
            
            # Determine FWI category
            if fwi < 20:
                category = "Low"
                color = "green"
            elif fwi < 40:
                category = "Moderate"
                color = "blue"
            elif fwi < 60:
                category = "High"
                color = "yellow"
            elif fwi < 80:
                category = "Very High"
                color = "orange"
            else:
                category = "Extreme"
                color = "red"
            
            return {
                "value": round(fwi, 1),
                "category": category,
                "color": color
            }
            
        except Exception as e:
            logger.error(f"Error calculating Fire Weather Index: {str(e)}")
            return {"value": 0, "category": "Unknown", "color": "gray"}
    
    def search_location(self, query):
        """
        Search for a location using Visual Crossing location services
        
        Args:
            query (str): Location search query
            
        Returns:
            dict: Location information including coordinates
        """
        try:
            url = f"{self.BASE_URL}/{query}"
            
            params = {
                'unitGroup': 'metric',
                'key': self.api_key,
                'include': 'days',
                'contentType': 'json',
                'elements': 'datetime'  # Minimal data to just get location info
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract location information
            location = {
                'name': data.get('resolvedAddress', query),
                'latitude': data.get('latitude'),
                'longitude': data.get('longitude'),
                'timezone': data.get('timezone')
            }
            
            return location
            
        except Exception as e:
            logger.error(f"Error searching location: {str(e)}")
            return None