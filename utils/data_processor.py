import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WeatherDataProcessor:
    """
    Process weather data from MeteoCenter GDPS for display and analysis
    """

    def __init__(self):
        pass

    @staticmethod
    def cache_data(ttl=3600):
        def decorator(func):
            from joblib import Memory
            cachedir = 'cachedir'  # Adjust cache directory as needed
            memory = Memory(cachedir, verbose=0)
            return memory.cache(func)
        return decorator


    @cache_data(ttl=3600)
    def process_temperature_data(self, df):
        """
        Process temperature data, including unit conversion if needed
        Uses vectorized operations for better performance
        """
        if df is None or df.empty:
            return None

        try:
            # Use vectorized operations instead of loops
            if 'value' in df.columns and df['value'].mean() > 100:
                df['value'] = df['value'].sub(273.15)

            if 'value' in df.columns:
                df['value'] = df['value'].round(1)

            if 'time' in df.columns:
                df['date'] = pd.to_datetime(df['time']).dt.date
                daily_stats = df.groupby('date').agg({
                    'value': ['min', 'max', 'mean']
                }).round(1)
                daily_stats.columns = ['min_temp', 'max_temp', 'avg_temp']

            return df

        except Exception as e:
            logger.error(f"Error processing temperature data: {e}")
            return df

    def process_precipitation_data(self, df):
        """
        Process precipitation data, calculate accumulations

        Args:
            df (pd.DataFrame): Raw precipitation data

        Returns:
            pd.DataFrame: Processed precipitation data with accumulations
        """
        if df is None:
            return None

        try:
            if 'value' in df.columns:
                # Calculate cumulative precipitation
                df['cumulative'] = df['value'].cumsum()

                # Check for daily accumulations
                if 'time' in df.columns:
                    df['date'] = pd.to_datetime(df['time']).dt.date
                    daily_total = df.groupby('date')['value'].sum().reset_index()
                    daily_total.columns = ['date', 'daily_total']

                    # Determine precipitation type based on temperature if available
                    # This would require temperature data in a real implementation

            return df

        except Exception as e:
            logger.error(f"Error processing precipitation data: {e}")
            return df

    def process_wind_data(self, wind_speed_df, wind_dir_df=None):
        """
        Process wind data, combining speed and direction if available

        Args:
            wind_speed_df (pd.DataFrame): Wind speed data
            wind_dir_df (pd.DataFrame): Wind direction data (optional)

        Returns:
            pd.DataFrame: Processed wind data
        """
        if wind_speed_df is None:
            return None

        try:
            # Process wind speed
            if 'value' in wind_speed_df.columns:
                # Convert to km/h if needed
                pass

            # Combine with direction if available
            if wind_dir_df is not None and 'value' in wind_dir_df.columns:
                # Make sure timestamps align
                if 'time' in wind_speed_df.columns and 'time' in wind_dir_df.columns:
                    wind_speed_df['time'] = pd.to_datetime(wind_speed_df['time'])
                    wind_dir_df['time'] = pd.to_datetime(wind_dir_df['time'])

                    # Merge the datasets
                    merged_df = pd.merge(
                        wind_speed_df, 
                        wind_dir_df, 
                        on='time', 
                        suffixes=('_speed', '_direction')
                    )

                    # Calculate U and V components for vector plotting
                    merged_df['u'] = -merged_df['value_speed'] * np.sin(np.radians(merged_df['value_direction']))
                    merged_df['v'] = -merged_df['value_speed'] * np.cos(np.radians(merged_df['value_direction']))

                    return merged_df

            return wind_speed_df

        except Exception as e:
            logger.error(f"Error processing wind data: {e}")
            return wind_speed_df

    def identify_severe_weather(self, data_dict):
        """
        Identify potential severe weather conditions from forecast data

        Args:
            data_dict (dict): Dictionary containing different weather parameter dataframes

        Returns:
            list: List of potential severe weather events with timestamps
        """
        severe_events = []

        try:
            # Check for high temperatures
            if 'TMP_TGL_2' in data_dict and data_dict['TMP_TGL_2'] is not None:
                temp_df = data_dict['TMP_TGL_2']
                if 'value' in temp_df.columns:
                    high_temp_times = temp_df[temp_df['value'] > 30]['time'].tolist()
                    if high_temp_times:
                        severe_events.append({
                            'type': 'Extreme Heat',
                            'threshold': '30°C',
                            'times': high_temp_times,
                            'description': 'Temperature exceeding 30°C may cause heat stress.'
                        })

                    low_temp_times = temp_df[temp_df['value'] < -20]['time'].tolist()
                    if low_temp_times:
                        severe_events.append({
                            'type': 'Extreme Cold',
                            'threshold': '-20°C',
                            'times': low_temp_times,
                            'description': 'Temperature below -20°C may cause frostbite and hypothermia.'
                        })

            # Check for heavy precipitation
            if 'APCP_SFC' in data_dict and data_dict['APCP_SFC'] is not None:
                precip_df = data_dict['APCP_SFC']
                if 'value' in precip_df.columns:
                    heavy_rain_times = precip_df[precip_df['value'] > 10]['time'].tolist()
                    if heavy_rain_times:
                        severe_events.append({
                            'type': 'Heavy Precipitation',
                            'threshold': '10mm/hr',
                            'times': heavy_rain_times,
                            'description': 'Heavy rainfall may cause localized flooding.'
                        })

            # Check for strong winds
            if 'WIND_TGL_10' in data_dict and data_dict['WIND_TGL_10'] is not None:
                wind_df = data_dict['WIND_TGL_10']
                if 'value' in wind_df.columns:
                    strong_wind_times = wind_df[wind_df['value'] > 50]['time'].tolist()
                    if strong_wind_times:
                        severe_events.append({
                            'type': 'Strong Winds',
                            'threshold': '50 km/h',
                            'times': strong_wind_times,
                            'description': 'Strong winds may cause power outages and property damage.'
                        })

            return severe_events

        except Exception as e:
            logger.error(f"Error identifying severe weather: {e}")
            return severe_events

    def calculate_wind_chill(self, temp_df, wind_df):
        """
        Calculate wind chill using temperature and wind speed

        Args:
            temp_df (pd.DataFrame): Temperature data
            wind_df (pd.DataFrame): Wind speed data

        Returns:
            pd.DataFrame: Wind chill data
        """
        if temp_df is None or wind_df is None:
            return None

        try:
            # Ensure common time index
            temp_df['time'] = pd.to_datetime(temp_df['time'])
            wind_df['time'] = pd.to_datetime(wind_df['time'])

            # Merge dataframes
            merged = pd.merge(temp_df, wind_df, on='time', suffixes=('_temp', '_wind'))

            # Calculate wind chill
            # Wind chill formula valid for T <= 10°C and V >= 5 km/h
            mask = (merged['value_temp'] <= 10) & (merged['value_wind'] >= 5)
            merged['wind_chill'] = np.nan

            # Wind chill formula: 13.12 + 0.6215*T - 11.37*V^0.16 + 0.3965*T*V^0.16
            # Where T is temperature in °C and V is wind speed in km/h
            merged.loc[mask, 'wind_chill'] = (
                13.12 + 
                0.6215 * merged.loc[mask, 'value_temp'] - 
                11.37 * merged.loc[mask, 'value_wind'] ** 0.16 + 
                0.3965 * merged.loc[mask, 'value_temp'] * merged.loc[mask, 'value_wind'] ** 0.16
            )

            return merged

        except Exception as e:
            logger.error(f"Error calculating wind chill: {e}")
            return None

    def calculate_heat_index(self, temp_df, rh_df):
        """
        Calculate heat index using temperature and relative humidity

        Args:
            temp_df (pd.DataFrame): Temperature data in Celsius
            rh_df (pd.DataFrame): Relative humidity data

        Returns:
            pd.DataFrame: Heat index data
        """
        if temp_df is None or rh_df is None:
            return None

        try:
            # Ensure common time index
            temp_df['time'] = pd.to_datetime(temp_df['time'])
            rh_df['time'] = pd.to_datetime(rh_df['time'])

            # Merge dataframes
            merged = pd.merge(temp_df, rh_df, on='time', suffixes=('_temp', '_rh'))

            # Calculate heat index
            # Heat index formula valid for T >= 27°C
            mask = (merged['value_temp'] >= 27)
            merged['heat_index'] = merged['value_temp']  # Default to temperature

            # Convert to Fahrenheit for the formula
            T = merged.loc[mask, 'value_temp'] * 9/5 + 32
            RH = merged.loc[mask, 'value_rh']

            # Heat index formula
            merged.loc[mask, 'heat_index'] = (
                -42.379 + 
                2.04901523 * T + 
                10.14333127 * RH - 
                0.22475541 * T * RH - 
                0.00683783 * T**2 - 
                0.05481717 * RH**2 + 
                0.00122874 * T**2 * RH + 
                0.00085282 * T * RH**2 - 
                0.00000199 * T**2 * RH**2
            )

            # Convert back to Celsius
            merged.loc[mask, 'heat_index'] = (merged.loc[mask, 'heat_index'] - 32) * 5/9

            return merged

        except Exception as e:
            logger.error(f"Error calculating heat index: {e}")
            return None

    def get_forecast_summary(self, data_dict):
        """
        Create a summary of the forecast for quick overview

        Args:
            data_dict (dict): Dictionary of processed weather dataframes

        Returns:
            dict: Summary of forecast conditions
        """
        summary = {
            'daily': [],
            'overall': {}
        }

        try:
            # Check if temperature data is available
            if 'TMP_TGL_2' in data_dict and data_dict['TMP_TGL_2'] is not None:
                temp_df = data_dict['TMP_TGL_2']

                if 'time' in temp_df.columns:
                    temp_df['date'] = pd.to_datetime(temp_df['time']).dt.date

                    # Get summary by day
                    daily_temp = temp_df.groupby('date').agg({
                        'value': ['min', 'max', 'mean']
                    })
                    daily_temp.columns = ['min_temp', 'max_temp', 'avg_temp']

                    # Overall temperature range
                    summary['overall']['temp_min'] = temp_df['value'].min()
                    summary['overall']['temp_max'] = temp_df['value'].max()

                    # Get precipitation data if available
                    precip_data = None
                    if 'APCP_SFC' in data_dict and data_dict['APCP_SFC'] is not None:
                        precip_df = data_dict['APCP_SFC']
                        if 'time' in precip_df.columns:
                            precip_df['date'] = pd.to_datetime(precip_df['time']).dt.date
                            precip_data = precip_df.groupby('date')['value'].sum()

                    # Get wind data if available
                    wind_data = None
                    if 'WIND_TGL_10' in data_dict and data_dict['WIND_TGL_10'] is not None:
                        wind_df = data_dict['WIND_TGL_10']
                        if 'time' in wind_df.columns:
                            wind_df['date'] = pd.to_datetime(wind_df['time']).dt.date
                            wind_data = wind_df.groupby('date')['value'].max()

                    # Build daily summaries
                    for date, row in daily_temp.iterrows():
                        day_summary = {
                            'date': date.strftime('%Y-%m-%d'),
                            'min_temp': round(row['min_temp'], 1),
                            'max_temp': round(row['max_temp'], 1),
                            'avg_temp': round(row['avg_temp'], 1)
                        }

                        # Add precipitation if available
                        if precip_data is not None and date in precip_data.index:
                            day_summary['precipitation'] = round(precip_data[date], 1)

                        # Add wind if available
                        if wind_data is not None and date in wind_data.index:
                            day_summary['max_wind'] = round(wind_data[date], 1)

                        summary['daily'].append(day_summary)

            return summary

        except Exception as e:
            logger.error(f"Error creating forecast summary: {e}")
            return summary