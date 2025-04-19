"""
Utility for generating custom weather forecast animations and visualizations
based on gridded forecast data fetched directly from NCEP/NWS.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
from matplotlib.animation import FuncAnimation
import io
import base64
import folium
import logging
from datetime import datetime, timedelta
from .data_fetcher import MeteoDataFetcher

# Configure logging
logger = logging.getLogger(__name__)

class ForecastGenerator:
    """
    Class for generating custom forecast animations and visualizations
    directly from gridded weather data
    """
    
    def __init__(self):
        """Initialize the forecast generator"""
        self.data_fetcher = MeteoDataFetcher()
        self.colormap_by_parameter = {
            # Temperature colormaps
            "TMP_TGL_2": "RdYlBu_r",  # Reversed RdYlBu for temperature (red=hot, blue=cold)
            "TMP_TGL_0": "RdYlBu_r",
            "TMP_ISBL_500": "RdYlBu_r",
            "TMP_ISBL_850": "RdYlBu_r",
            
            # Precipitation colormaps
            "APCP_SFC": "Blues",       # Blues for precipitation (darker blue = more precipitation)
            "ACPCP_SFC": "Blues",
            "SNOD_SFC": "Blues",
            
            # Wind colormaps
            "WIND_TGL_10": "YlOrRd",   # Yellow-Orange-Red for wind (red = strongest)
            "GUST_TGL_10": "YlOrRd",
            
            # Pressure colormaps
            "PRMSL_MSL": "viridis",    # viridis for pressure
            "HGT_ISBL_500": "viridis",
            
            # CAPE colormap
            "CAPE_SFC": "Reds",        # Reds for CAPE (darker red = higher CAPE)
            
            # Default colormap for other parameters
            "default": "viridis"
        }
        
        self.parameter_ranges = {
            # Temperature ranges in Celsius
            "TMP_TGL_2": (-40, 40),
            "TMP_TGL_0": (-40, 40),
            "TMP_ISBL_500": (-60, 10),
            "TMP_ISBL_850": (-40, 30),
            
            # Precipitation ranges in mm
            "APCP_SFC": (0, 50),
            "ACPCP_SFC": (0, 30),
            
            # Snow depth in cm
            "SNOD_SFC": (0, 50),
            
            # Wind speeds in km/h
            "WIND_TGL_10": (0, 100),
            "GUST_TGL_10": (0, 120),
            
            # Pressure in hPa
            "PRMSL_MSL": (980, 1040),
            
            # Geopotential height in m
            "HGT_ISBL_500": (5400, 5900),
            
            # CAPE in J/kg
            "CAPE_SFC": (0, 4000)
        }
    
    def get_parameter_info(self, parameter_code):
        """
        Get display information for a parameter
        
        Args:
            parameter_code (str): Parameter code (e.g., "TMP_TGL_2")
            
        Returns:
            dict: Parameter information including description and unit
        """
        parameters = self.data_fetcher.fetch_available_parameters()
        for param in parameters:
            if param['code'] == parameter_code:
                return param
        
        # Default information if parameter not found
        return {
            "code": parameter_code,
            "description": parameter_code,
            "unit": ""
        }
    
    def generate_forecast_animation(self, parameter, region, forecast_hours=None):
        """
        Generate a forecast animation for a specified parameter and region
        
        Args:
            parameter (str): Parameter code (e.g., "TMP_TGL_2", "APCP_SFC")
            region (str): Region identifier (predefined regions like "na", "us", "eu")
            forecast_hours (list, optional): List of forecast hours to include
                
        Returns:
            BytesIO: Animation as GIF in BytesIO object
        """
        try:
            # Define region bounding boxes (min_lon, min_lat, max_lon, max_lat)
            region_bounds = {
                "na": (-130, 25, -60, 60),     # North America
                "us": (-125, 24, -66, 50),     # United States
                "eu": (-10, 35, 30, 65),       # Europe
                "global": (-180, -60, 180, 80), # Global view
                "atl": (-90, 5, -30, 45),      # Atlantic Ocean
                "pac": (140, 5, -120, 60),     # Pacific Ocean
                "asia": (60, 0, 140, 60),      # Asia
                "aus": (110, -45, 155, -10),   # Australia
                "sa": (-85, -60, -30, 15),     # South America
                "af": (-20, -35, 55, 35)       # Africa
            }
            
            if region.lower() not in region_bounds:
                logger.error(f"Unknown region: {region}")
                return None
                
            bbox = region_bounds[region.lower()]
            
            # Determine forecast hours
            if forecast_hours is None:
                if parameter.startswith("APCP") or parameter.startswith("SNOD"):
                    # Use 6-hour intervals for precipitation and snow
                    forecast_hours = list(range(0, 73, 6))
                else:
                    # Use 12-hour intervals for other parameters
                    forecast_hours = list(range(0, 73, 12))
            
            # Fetch gridded data for each forecast hour
            grid_data_frames = []
            for hour in forecast_hours:
                try:
                    grid_data = self.data_fetcher.fetch_grid_data(parameter, bbox, hour)
                    if grid_data and "data" in grid_data and "lats" in grid_data and "lons" in grid_data:
                        grid_data["forecast_hour"] = hour
                        grid_data_frames.append(grid_data)
                except Exception as e:
                    logger.error(f"Error fetching grid data for hour {hour}: {e}")
            
            if not grid_data_frames:
                logger.error(f"Could not fetch any valid grid data for {parameter}")
                return None
            
            # Get parameter information
            param_info = self.get_parameter_info(parameter)
            
            # Generate animation frames
            fig, ax = plt.figure(figsize=(10, 8), dpi=100, facecolor='white'), plt.axes(projection='rectilinear')
            
            # Get parameter-specific colormap and data range
            cmap_name = self.colormap_by_parameter.get(parameter, self.colormap_by_parameter["default"])
            cmap = plt.get_cmap(cmap_name)
            
            vmin, vmax = self.parameter_ranges.get(parameter, (None, None))
            
            # Draw the frames
            frames = []
            for grid_data in grid_data_frames:
                data = np.array(grid_data["data"])
                lats = np.array(grid_data["lats"])
                lons = np.array(grid_data["lons"])
                hour = grid_data["forecast_hour"]
                
                # Clear the plot for the new frame
                ax.clear()
                
                # Mesh grid creation for contour plot
                lon_mesh, lat_mesh = np.meshgrid(lons, lats)
                
                # Create filled contour plot
                contour = ax.contourf(lon_mesh, lat_mesh, data, levels=20, cmap=cmap, vmin=vmin, vmax=vmax)
                
                # Add coastlines and borders
                ax.grid(True, linestyle='--', alpha=0.5)
                
                # Add colorbar
                cbar = plt.colorbar(contour, ax=ax, orientation='vertical', pad=0.01)
                cbar.set_label(f"{param_info['description']} ({param_info['unit']})")
                
                # Set title with forecast information
                run_time = self.data_fetcher.get_latest_gdps_run()
                run_datetime = datetime.strptime(run_time, "%Y%m%d%H")
                valid_time = run_datetime + timedelta(hours=hour)
                
                ax.set_title(f"{param_info['description']} - {region.upper()}\nModel Run: {run_datetime.strftime('%Y-%m-%d %H:00Z')}\nValid: {valid_time.strftime('%Y-%m-%d %H:00Z')} (+{hour}h)")
                
                # Set axis labels
                ax.set_xlabel('Longitude')
                ax.set_ylabel('Latitude')
                
                # Set plot limits based on region
                ax.set_xlim(bbox[0], bbox[2])
                ax.set_ylim(bbox[1], bbox[3])
                
                # Capture frame
                frame_buffer = io.BytesIO()
                plt.savefig(frame_buffer, format='png', bbox_inches='tight')
                frame_buffer.seek(0)
                frames.append(frame_buffer.getvalue())
            
            # Close the figure to free up resources
            plt.close(fig)
            
            # Generate GIF animation from frames
            from PIL import Image
            gif_buffer = io.BytesIO()
            
            # Open frames as PIL images
            pil_frames = [Image.open(io.BytesIO(frame)) for frame in frames]
            
            # Save as animated GIF
            if pil_frames:
                pil_frames[0].save(
                    gif_buffer, 
                    format='GIF',
                    save_all=True,
                    append_images=pil_frames[1:],
                    duration=500,  # Display each frame for 500ms
                    loop=0         # Loop forever
                )
                
                # Reset buffer position
                gif_buffer.seek(0)
                return gif_buffer
            
            return None
        
        except Exception as e:
            logger.error(f"Error generating forecast animation: {e}")
            return None
    
    def create_interactive_forecast_map(self, parameter, region, forecast_hour=24):
        """
        Create an interactive folium map with forecast data
        
        Args:
            parameter (str): Parameter code (e.g., "TMP_TGL_2")
            region (str): Region identifier (e.g., "na", "us", "eu")
            forecast_hour (int): Forecast hour
            
        Returns:
            folium.Map: Interactive map with forecast data
        """
        try:
            # Define region bounding boxes and center points
            region_centers = {
                "na": (40, -95),      # North America
                "us": (38, -98),      # United States
                "eu": (50, 10),       # Europe
                "global": (20, 0),    # Global view
                "atl": (25, -60),     # Atlantic Ocean
                "pac": (30, -170),    # Pacific Ocean
                "asia": (35, 100),    # Asia
                "aus": (-25, 135),    # Australia
                "sa": (-20, -60),     # South America
                "af": (5, 20)         # Africa
            }
            
            region_bounds = {
                "na": (-130, 25, -60, 60),     # North America
                "us": (-125, 24, -66, 50),     # United States
                "eu": (-10, 35, 30, 65),       # Europe
                "global": (-180, -60, 180, 80), # Global view
                "atl": (-90, 5, -30, 45),      # Atlantic Ocean
                "pac": (140, 5, -120, 60),     # Pacific Ocean
                "asia": (60, 0, 140, 60),      # Asia
                "aus": (110, -45, 155, -10),   # Australia
                "sa": (-85, -60, -30, 15),     # South America
                "af": (-20, -35, 55, 35)       # Africa
            }
            
            if region.lower() not in region_bounds:
                logger.error(f"Unknown region: {region}")
                # Default to North America if region not recognized
                region = "na"
                
            bbox = region_bounds[region.lower()]
            center = region_centers[region.lower()]
            
            # Fetch grid data
            grid_data = self.data_fetcher.fetch_grid_data(parameter, bbox, forecast_hour)
            
            if not grid_data or "data" not in grid_data:
                logger.error(f"Could not fetch valid grid data for {parameter}")
                # Return an empty map centered on the region
                m = folium.Map(location=center, zoom_start=4)
                return m
            
            # Get parameter information
            param_info = self.get_parameter_info(parameter)
            
            # Create base map
            m = folium.Map(location=center, zoom_start=4)
            
            # Extract data
            data = np.array(grid_data["data"])
            lats = np.array(grid_data["lats"])
            lons = np.array(grid_data["lons"])
            
            # Determine appropriate zoom level based on region
            if region.lower() in ["global", "pac"]:
                zoom_start = 2
            elif region.lower() in ["na", "eu", "asia", "sa", "af"]:
                zoom_start = 3
            else:
                zoom_start = 4
                
            m = folium.Map(location=center, zoom_start=zoom_start)
            
            # Get parameter-specific colormap and data range
            cmap_name = self.colormap_by_parameter.get(parameter, self.colormap_by_parameter["default"])
            cmap = plt.get_cmap(cmap_name)
            
            vmin, vmax = self.parameter_ranges.get(parameter, (None, None))
            if vmin is None:
                vmin = np.nanmin(data)
            if vmax is None:
                vmax = np.nanmax(data)
            
            # Create a heatmap layer from the data
            # We'll need to reformat the data for folium
            heat_data = []
            for i in range(len(lats)):
                for j in range(len(lons)):
                    if not np.isnan(data[i, j]):
                        # Normalize the value between 0 and 1 for color intensity
                        norm_value = (data[i, j] - vmin) / (vmax - vmin) if vmax > vmin else 0.5
                        heat_data.append([lats[i], lons[j], norm_value])
            
            # Add the heatmap to the map
            folium.plugins.HeatMap(
                heat_data,
                radius=10,
                gradient={0.4: 'blue', 0.65: 'lime', 0.8: 'yellow', 1: 'red'},
                min_opacity=0.5,
                blur=15,
                max_zoom=10,
            ).add_to(m)
            
            # Add a title
            run_time = self.data_fetcher.get_latest_gdps_run()
            run_datetime = datetime.strptime(run_time, "%Y%m%d%H")
            valid_time = run_datetime + timedelta(hours=forecast_hour)
            
            title_html = f'''
                <h3 align="center" style="font-size:16px">
                    <b>{param_info['description']} ({param_info['unit']}) - {region.upper()}</b>
                    <br>
                    <span style="font-size:14px">
                        Model Run: {run_datetime.strftime('%Y-%m-%d %H:00Z')}
                        <br>
                        Valid: {valid_time.strftime('%Y-%m-%d %H:00Z')} (+{forecast_hour}h)
                    </span>
                </h3>
            '''
            m.get_root().html.add_child(folium.Element(title_html))
            
            return m
        
        except Exception as e:
            logger.error(f"Error creating interactive forecast map: {e}")
            # Return a basic map if there's an error
            m = folium.Map(location=[40, -95], zoom_start=4)
            return m

# Initialize a singleton for easy access
forecast_generator = ForecastGenerator()