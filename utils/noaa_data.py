"""
Utility for accessing NCEP/NWS data directly using Siphon and MetPy
"""
import os
import datetime
import logging
import numpy as np
import pandas as pd
import xarray as xr
from siphon.catalog import TDSCatalog
from siphon.ncss import NCSS
import metpy.calc as mpcalc
from metpy.units import units

logger = logging.getLogger(__name__)

class NOAADataProvider:
    """
    Class for accessing NOAA/NCEP/NWS data directly
    """
    
    # NCEP/THREDDS Data Server URLs
    GFS_CATALOG_URL = "https://thredds.ucar.edu/thredds/catalog/grib/NCEP/GFS/Global_0p25deg/catalog.xml"
    NAM_CATALOG_URL = "https://thredds.ucar.edu/thredds/catalog/grib/NCEP/NAM/CONUS_12km/catalog.xml"
    HRRR_CATALOG_URL = "https://thredds.ucar.edu/thredds/catalog/grib/NCEP/HRRR/CONUS_2p5km/catalog.xml"
    
    # NWS API endpoint
    NWS_API_URL = "https://api.weather.gov"
    
    # Parameter mappings between our app and NCEP parameters
    PARAMETER_MAPPING = {
        # Temperature parameters
        "TMP_TGL_2": {"ncep": "Temperature_surface", "level": "2 m above ground", "units": "K"},
        "TMP_TGL_0": {"ncep": "Temperature_surface", "level": "surface", "units": "K"},
        "TMP_ISBL_500": {"ncep": "Temperature_isobaric", "level": "500 mb", "units": "K"},
        "TMP_ISBL_850": {"ncep": "Temperature_isobaric", "level": "850 mb", "units": "K"},
        
        # Precipitation parameters
        "APCP_SFC": {"ncep": "Total_precipitation_surface", "level": "surface", "units": "kg/m^2"},
        "ACPCP_SFC": {"ncep": "Convective_precipitation_surface", "level": "surface", "units": "kg/m^2"},
        
        # Wind parameters
        "WIND_TGL_10": {"ncep": ["u-component_of_wind_height_above_ground", "v-component_of_wind_height_above_ground"], 
                        "level": "10 m above ground", "units": "m/s", "derived": True},
        "WDIR_TGL_10": {"ncep": ["u-component_of_wind_height_above_ground", "v-component_of_wind_height_above_ground"], 
                        "level": "10 m above ground", "units": "degrees", "derived": True},
        
        # Pressure parameters
        "PRMSL_MSL": {"ncep": "Pressure_reduced_to_MSL_msl", "level": "mean sea level", "units": "Pa"},
        
        # Severe weather parameters
        "CAPE_SFC": {"ncep": "Convective_available_potential_energy_surface", "level": "surface", "units": "J/kg"},
        "CIN_SFC": {"ncep": "Convective_inhibition_surface", "level": "surface", "units": "J/kg"},
    }
    
    def __init__(self):
        """Initialize the NOAA data provider"""
        self.session = None
        self.latest_dataset = None
        self.model_run_date = None
    
    def get_latest_model_run(self, model="gfs"):
        """
        Get the latest available model run
        
        Args:
            model (str): Model name (gfs, nam, hrrr)
            
        Returns:
            str: URL to the latest dataset
        """
        try:
            if model.lower() == "gfs":
                catalog_url = self.GFS_CATALOG_URL
            elif model.lower() == "nam":
                catalog_url = self.NAM_CATALOG_URL
            elif model.lower() == "hrrr":
                catalog_url = self.HRRR_CATALOG_URL
            else:
                raise ValueError(f"Unsupported model: {model}")
            
            # Access the THREDDS catalog
            catalog = TDSCatalog(catalog_url)
            
            # Get the latest dataset
            latest_dataset = list(catalog.datasets.values())[-1]
            
            # Store model run date from the dataset name
            # Format depends on the model, but generally contains a timestamp
            if model.lower() == "gfs":
                # GFS filenames are like: gfs_0p25_YYYYMMDD_HHz_fNNN.grib2
                parts = latest_dataset.name.split('_')
                if len(parts) >= 3:
                    date_str = parts[2]
                    hour_str = parts[3].replace('z', '')
                    self.model_run_date = datetime.datetime.strptime(f"{date_str}_{hour_str}", "%Y%m%d_%H")
            
            logger.info(f"Found latest {model.upper()} run: {latest_dataset.name}")
            return latest_dataset.access_urls['NCSS']
            
        except Exception as e:
            logger.error(f"Error getting latest {model.upper()} model run: {e}")
            return None
    
    def fetch_forecast_data(self, lat, lon, parameter, model="gfs", forecast_hours=72):
        """
        Fetch forecast data for a specific parameter at a given location
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            parameter (str): Parameter code (e.g., "TMP_TGL_2", "APCP_SFC")
            model (str): Model name (gfs, nam, hrrr)
            forecast_hours (int): Number of forecast hours to fetch
            
        Returns:
            pd.DataFrame: Dataframe with forecast data
        """
        try:
            # Get parameter mapping
            if parameter not in self.PARAMETER_MAPPING:
                logger.error(f"Unsupported parameter: {parameter}")
                return None
            
            param_info = self.PARAMETER_MAPPING[parameter]
            
            # Get the latest dataset URL
            dataset_url = self.get_latest_model_run(model)
            if not dataset_url:
                return None
            
            # Create NCSS connection
            ncss = NCSS(dataset_url)
            
            # Determine time range
            now = datetime.datetime.utcnow()
            end_time = now + datetime.timedelta(hours=forecast_hours)
            
            # Build the query
            query = ncss.query()
            query.lonlat_point(lon, lat)
            query.time_range(now, end_time)
            
            # Add variables to the query
            if isinstance(param_info["ncep"], list):
                # For derived parameters that need multiple variables
                for var in param_info["ncep"]:
                    query.variables(var).add_query_parameter("VertCoord", param_info["level"])
            else:
                # Single variable parameters
                query.variables(param_info["ncep"]).add_query_parameter("VertCoord", param_info["level"])
            
            # Get the data
            data = ncss.get_data(query)
            
            # Extract and process the data based on parameter type
            if parameter == "WIND_TGL_10":
                # Extract u and v components
                u_data = data.variables["u-component_of_wind_height_above_ground"][:]
                v_data = data.variables["v-component_of_wind_height_above_ground"][:]
                
                # Calculate wind speed
                wind_speed = np.sqrt(u_data**2 + v_data**2)
                
                # Create dataframe
                times = data.variables["time"][:]
                timestamps = pd.DatetimeIndex([datetime.datetime.utcfromtimestamp(t) for t in times])
                
                df = pd.DataFrame({
                    "time": timestamps,
                    "value": wind_speed
                })
                
                return df
                
            elif parameter == "WDIR_TGL_10":
                # Extract u and v components
                u_data = data.variables["u-component_of_wind_height_above_ground"][:]
                v_data = data.variables["v-component_of_wind_height_above_ground"][:]
                
                # Calculate wind direction
                wind_dir = (270 - np.arctan2(v_data, u_data) * 180 / np.pi) % 360
                
                # Create dataframe
                times = data.variables["time"][:]
                timestamps = pd.DatetimeIndex([datetime.datetime.utcfromtimestamp(t) for t in times])
                
                df = pd.DataFrame({
                    "time": timestamps,
                    "value": wind_dir
                })
                
                return df
                
            else:
                # Process regular parameters
                var_data = data.variables[param_info["ncep"]][:]
                
                # Convert units if needed
                if param_info.get("units") == "K" and parameter.startswith("TMP"):
                    # Convert Kelvin to Celsius
                    var_data = var_data - 273.15
                
                # Create dataframe
                times = data.variables["time"][:]
                timestamps = pd.DatetimeIndex([datetime.datetime.utcfromtimestamp(t) for t in times])
                
                df = pd.DataFrame({
                    "time": timestamps,
                    "value": var_data
                })
                
                return df
                
        except Exception as e:
            logger.error(f"Error fetching {parameter} from {model.upper()}: {e}")
            return None
    
    def fetch_grid_data(self, parameter, bbox, model="gfs", forecast_hour=24):
        """
        Fetch gridded data for map visualization
        
        Args:
            parameter (str): Parameter code (e.g., "TMP_TGL_2", "CAPE_SFC")
            bbox (tuple): Bounding box (min_lon, min_lat, max_lon, max_lat)
            model (str): Model name (gfs, nam, hrrr)
            forecast_hour (int): Forecast hour
            
        Returns:
            dict: Gridded data suitable for map visualization
        """
        try:
            # Get parameter mapping
            if parameter not in self.PARAMETER_MAPPING:
                logger.error(f"Unsupported parameter: {parameter}")
                return None
            
            param_info = self.PARAMETER_MAPPING[parameter]
            
            # Get the latest dataset URL
            dataset_url = self.get_latest_model_run(model)
            if not dataset_url:
                return None
            
            # Create NCSS connection
            ncss = NCSS(dataset_url)
            
            # Determine time
            now = datetime.datetime.utcnow()
            forecast_time = now + datetime.timedelta(hours=forecast_hour)
            
            # Build the query
            query = ncss.query()
            query.lonlat_box(north=bbox[3], south=bbox[1], east=bbox[2], west=bbox[0])
            query.time(forecast_time)
            
            # Add variables to the query
            if isinstance(param_info["ncep"], list):
                # For derived parameters that need multiple variables
                for var in param_info["ncep"]:
                    query.variables(var).add_query_parameter("VertCoord", param_info["level"])
            else:
                # Single variable parameters
                query.variables(param_info["ncep"]).add_query_parameter("VertCoord", param_info["level"])
            
            # Get the data
            data = ncss.get_data(query)
            
            # Extract and process the data based on parameter type
            if parameter == "WIND_TGL_10":
                # Extract u and v components
                u_data = data.variables["u-component_of_wind_height_above_ground"][0, :, :]
                v_data = data.variables["v-component_of_wind_height_above_ground"][0, :, :]
                
                # Calculate wind speed
                wind_speed = np.sqrt(u_data**2 + v_data**2)
                
                # Get the lat/lon grid
                lats = data.variables["lat"][:]
                lons = data.variables["lon"][:]
                
                # Create grid data
                grid_data = {
                    "parameter": parameter,
                    "display_name": "Wind Speed (10m)",
                    "unit": "m/s",
                    "values": wind_speed.flatten(),
                    "lats": lats.flatten(),
                    "lons": lons.flatten(),
                    "min_value": np.min(wind_speed),
                    "max_value": np.max(wind_speed)
                }
                
                return grid_data
                
            else:
                # Process regular parameters
                var_data = data.variables[param_info["ncep"]][0, :, :]
                
                # Convert units if needed
                if param_info.get("units") == "K" and parameter.startswith("TMP"):
                    # Convert Kelvin to Celsius
                    var_data = var_data - 273.15
                
                # Get the lat/lon grid
                lats = data.variables["lat"][:]
                lons = data.variables["lon"][:]
                
                # Create grid data
                # Use parameter as display name without mapping lookup
                display_name = parameter
                if parameter.startswith("TMP"):
                    display_name = "Temperature"
                elif parameter.startswith("APCP"):
                    display_name = "Precipitation"
                elif parameter.startswith("WIND"):
                    display_name = "Wind Speed"
                elif parameter.startswith("CAPE"):
                    display_name = "CAPE"
                
                grid_data = {
                    "parameter": parameter,
                    "display_name": display_name,
                    "unit": param_info.get("units"),
                    "values": var_data.flatten(),
                    "lats": lats.flatten(),
                    "lons": lons.flatten(),
                    "min_value": np.min(var_data),
                    "max_value": np.max(var_data)
                }
                
                return grid_data
                
        except Exception as e:
            logger.error(f"Error fetching grid data for {parameter} from {model.upper()}: {e}")
            return None
    
    def fetch_severe_warnings(self, lat, lon, radius_km=50):
        """
        Fetch severe weather warnings from NWS API
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            radius_km (int): Radius in kilometers to check for warnings
            
        Returns:
            list: List of warnings with details
        """
        try:
            import requests
            
            # Get NWS grid point information for the location
            headers = {
                'User-Agent': 'Weather Forecast App (contact: example@example.com)',
                'Accept': 'application/geo+json'
            }
            
            # First get the grid point
            response = requests.get(
                f"{self.NWS_API_URL}/points/{lat},{lon}",
                headers=headers
            )
            response.raise_for_status()
            grid_data = response.json()
            
            # Extract grid details
            grid_id = grid_data["properties"]["gridId"]
            grid_x = grid_data["properties"]["gridX"]
            grid_y = grid_data["properties"]["gridY"]
            
            # Fetch alerts for this area
            alerts_response = requests.get(
                f"{self.NWS_API_URL}/alerts/active?point={lat},{lon}",
                headers=headers
            )
            alerts_response.raise_for_status()
            alerts_data = alerts_response.json()
            
            # Process alerts data
            warnings = []
            if "features" in alerts_data and alerts_data["features"]:
                for alert in alerts_data["features"]:
                    props = alert["properties"]
                    
                    warning = {
                        "id": props.get("id"),
                        "title": props.get("event"),
                        "description": props.get("headline"),
                        "severity": props.get("severity"),
                        "certainty": props.get("certainty"),
                        "urgency": props.get("urgency"),
                        "start": props.get("effective"),
                        "end": props.get("expires"),
                        "instruction": props.get("instruction"),
                        "source": "National Weather Service"
                    }
                    
                    warnings.append(warning)
            
            return warnings
            
        except Exception as e:
            logger.error(f"Error fetching severe warnings from NWS API: {e}")
            return []

# Initialize as a singleton
noaa_provider = NOAADataProvider()