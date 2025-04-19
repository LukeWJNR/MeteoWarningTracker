"""
Utility for tropical storm tracking and analysis using the Tropycal package
"""
import os
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import io
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, timedelta
import folium
from tropycal.tracks import TrackDataset
from tropycal.recon import ReconDataset
# tropycal.current module might not be available in the current version
# We'll implement a fallback mechanism

logger = logging.getLogger(__name__)

class TropicalStormTracker:
    """
    Class for tracking and analyzing tropical storms using Tropycal
    """
    
    def __init__(self):
        """Initialize the tropical storm tracker"""
        self.tracks_data = None
        self.recon_data = None
        self.current_data = None
        self.latest_update = None
    
    def init_data(self, force_refresh=False):
        """
        Initialize the track dataset
        
        Args:
            force_refresh (bool): Force refresh of data even if already loaded
            
        Returns:
            bool: Success status
        """
        try:
            if self.tracks_data is None or force_refresh:
                # Initialize track dataset for recent Atlantic basin storms
                self.tracks_data = TrackDataset(basin='north_atlantic')
                
                # Initialize reconnaissance data
                self.recon_data = ReconDataset()
                
                # Initialize current storm data
                try:
                    # Try to import the Current module dynamically since it might not be available
                    from importlib import import_module
                    current_module = import_module('tropycal.current')
                    Current = getattr(current_module, 'Current')
                    self.current_data = Current(jtwc=True)
                except (ImportError, AttributeError) as e:
                    logger.warning(f"Tropycal Current module not available: {e}")
                    self.current_data = None
                
                self.latest_update = datetime.now()
                
                logger.info("Tropical storm data initialized successfully")
                return True
            
            return True
            
        except Exception as e:
            logger.error(f"Error initializing tropical storm data: {e}")
            return False
    
    def get_active_storms(self):
        """
        Get currently active tropical storms
        
        Returns:
            list: List of active storms with details
        """
        try:
            if not self.init_data():
                return []
            
            # Check if current_data module is available
            if self.current_data is None:
                logger.warning("Current storm data module not available")
                return []
            
            # Fetch current storms
            storms = self.current_data.list_current_storms()
            
            # Process storm data
            active_storms = []
            for storm in storms:
                storm_data = {
                    "name": storm["name"],
                    "id": storm["id"],
                    "type": storm["type"],
                    "basin": storm["basin"],
                    "current_status": {
                        "lat": storm["lat"],
                        "lon": storm["lon"],
                        "wind": storm["vmax"],
                        "pressure": storm["mslp"],
                        "category": self._get_storm_category(storm["vmax"])
                    }
                }
                
                active_storms.append(storm_data)
            
            return active_storms
            
        except Exception as e:
            logger.error(f"Error fetching active storms: {e}")
            return []
    
    def _get_storm_category(self, wind_speed):
        """Helper function to determine storm category"""
        if wind_speed < 35:
            return "Tropical Depression"
        elif wind_speed < 64:
            return "Tropical Storm"
        elif wind_speed < 83:
            return "Category 1 Hurricane"
        elif wind_speed < 96:
            return "Category 2 Hurricane"
        elif wind_speed < 113:
            return "Category 3 Hurricane"
        elif wind_speed < 137:
            return "Category 4 Hurricane"
        else:
            return "Category 5 Hurricane"
    
    def plot_active_storm(self, storm_id):
        """
        Create a plot of an active storm's track and forecast
        
        Args:
            storm_id (str): Storm ID
            
        Returns:
            BytesIO: Image of storm plot or None if failed
        """
        try:
            if not self.init_data():
                return None
                
            # Check if current_data module is available
            if self.current_data is None:
                logger.warning("Current storm data module not available")
                return None
            
            # Fetch current storm object
            storm = self.current_data.get_storm(storm_id)
            
            # Create figure
            fig = plt.figure(figsize=(10, 8), dpi=100)
            ax = plt.axes(projection=storm.map_projection)
            
            # Plot storm track and forecast cone
            storm.plot(ax=ax, return_ax=True, prop={'color':'white'})
            
            # Save plot to bytes buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)
            
            return buf
            
        except Exception as e:
            logger.error(f"Error plotting active storm {storm_id}: {e}")
            return None
    
    def create_storm_map(self, storm_id=None, zoom=5):
        """
        Create an interactive Folium map of tropical storm track
        
        Args:
            storm_id (str): Storm ID or None for all active storms
            zoom (int): Initial zoom level
            
        Returns:
            folium.Map: Folium map with storm track
        """
        try:
            if not self.init_data():
                return None
            
            active_storms = self.get_active_storms()
            
            if not active_storms:
                logger.info("No active storms to display")
                # Create a default map centered on Atlantic basin
                m = folium.Map(
                    location=[20.0, -60.0],
                    zoom_start=4,
                    tiles='CartoDB positron'
                )
                return m
            
            # If no specific storm ID provided, use the first active storm
            target_storm = None
            if storm_id:
                target_storm = next((s for s in active_storms if s["id"] == storm_id), None)
            
            if not target_storm and active_storms:
                target_storm = active_storms[0]
            
            if not target_storm:
                return None
            
            # Center map on the storm's current position
            m = folium.Map(
                location=[target_storm["current_status"]["lat"], target_storm["current_status"]["lon"]],
                zoom_start=zoom,
                tiles='CartoDB positron'
            )
            
            # Check if current_data module is available
            if self.current_data is None:
                logger.warning("Current storm data module not available")
                return m  # Return the basic map without detailed tracks
                
            # Get detailed storm data from the current module
            storm_obj = self.current_data.get_storm(target_storm["id"])
            
            # Add forecasted track points
            forecast_points = []
            for i, row in enumerate(storm_obj.forecast.iterrows()):
                point = row[1]
                forecast_points.append([point['lat'], point['lon']])
                
                # Add marker for each forecast point
                forecast_time = point.name
                folium.CircleMarker(
                    location=[point['lat'], point['lon']],
                    radius=4,
                    color='orange',
                    fill=True,
                    fill_color='orange',
                    tooltip=f"Forecast: {forecast_time.strftime('%Y-%m-%d %H:%M')} - Wind: {point['vmax']} kt"
                ).add_to(m)
            
            # Add historical track points
            track_points = []
            for i, row in enumerate(storm_obj.obs.iterrows()):
                point = row[1]
                track_points.append([point['lat'], point['lon']])
                
                # Add marker for historical points
                marker_color = 'blue'
                if point['type'] == 'HU':
                    marker_color = 'red'
                elif point['type'] == 'TS':
                    marker_color = 'orange'
                
                obs_time = point.name
                folium.CircleMarker(
                    location=[point['lat'], point['lon']],
                    radius=5,
                    color=marker_color,
                    fill=True,
                    fill_color=marker_color,
                    tooltip=f"{obs_time.strftime('%Y-%m-%d %H:%M')} - Wind: {point['vmax']} kt"
                ).add_to(m)
            
            # Add lines connecting the track points
            folium.PolyLine(
                track_points,
                color='blue',
                weight=3,
                opacity=0.8,
                tooltip=f"{target_storm['name']} Track"
            ).add_to(m)
            
            # Add lines connecting the forecast points
            folium.PolyLine(
                forecast_points,
                color='orange',
                weight=3,
                opacity=0.8,
                dash_array='5,8',
                tooltip=f"{target_storm['name']} Forecast"
            ).add_to(m)
            
            # Add marker for current position
            folium.Marker(
                location=[target_storm["current_status"]["lat"], target_storm["current_status"]["lon"]],
                tooltip=f"{target_storm['name']} - {target_storm['current_status']['category']}",
                icon=folium.Icon(color='red', icon='circle', prefix='fa')
            ).add_to(m)
            
            return m
            
        except Exception as e:
            logger.error(f"Error creating storm map for {storm_id}: {e}")
            # Return a default map on error
            m = folium.Map(
                location=[20.0, -60.0],
                zoom_start=4,
                tiles='CartoDB positron'
            )
            return m
    
    def get_historical_storms(self, year=None, season=None):
        """
        Get historical storm data
        
        Args:
            year (int): Specific year to fetch or None for recent
            season (str): Season to fetch (e.g., "2022")
            
        Returns:
            pd.DataFrame: Dataframe with historical storm data
        """
        try:
            if not self.init_data():
                return None
            
            if year:
                storms = self.tracks_data.get_season(year)
            elif season:
                storms = self.tracks_data.get_season(season)
            else:
                # Get the most recent complete season
                current_year = datetime.now().year
                season_year = current_year - 1 if datetime.now().month < 6 else current_year
                storms = self.tracks_data.get_season(season_year)
            
            # Process storm data into dataframe
            storm_list = []
            for storm_id, storm_data in storms.items():
                max_wind = storm_data.dict["vmax"].max()
                min_pressure = storm_data.dict["mslp"].min()
                
                storm_list.append({
                    "id": storm_id,
                    "name": storm_data.name,
                    "year": storm_data.season,
                    "max_wind": max_wind,
                    "min_pressure": min_pressure,
                    "category": self._get_storm_category(max_wind),
                    "ace": storm_data.ace,
                    "track_distance": storm_data.track_distance,
                    "start_date": storm_data.dict.index[0],
                    "end_date": storm_data.dict.index[-1]
                })
            
            return pd.DataFrame(storm_list)
            
        except Exception as e:
            logger.error(f"Error fetching historical storms: {e}")
            return None
    
    def plot_historical_season(self, year=None):
        """
        Plot all storm tracks for a given season
        
        Args:
            year (int): Year to plot or None for most recent
            
        Returns:
            BytesIO: Image of season plot or None if failed
        """
        try:
            if not self.init_data():
                return None
            
            # If no year specified, use most recent complete season
            if not year:
                current_year = datetime.now().year
                year = current_year - 1 if datetime.now().month < 6 else current_year
            
            # Create figure
            fig = plt.figure(figsize=(12, 8), dpi=100)
            
            # Plot the season tracks
            self.tracks_data.plot_season(year)
            
            # Save plot to bytes buffer
            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)
            
            return buf
            
        except Exception as e:
            logger.error(f"Error plotting historical season {year}: {e}")
            return None
    
    def get_storm_summary(self, storm_id, current=True):
        """
        Get a comprehensive summary of a storm
        
        Args:
            storm_id (str): Storm ID
            current (bool): Whether to look in current storms or historical
            
        Returns:
            dict: Storm summary information
        """
        try:
            if not self.init_data():
                return {}
            
            if current:
                # Check if current_data module is available
                if self.current_data is None:
                    logger.warning("Current storm data module not available")
                    return {}
                
                # Get active storm from current module
                storm = self.current_data.get_storm(storm_id)
                
                # Extract storm data
                summary = {
                    "id": storm_id,
                    "name": storm.name,
                    "type": storm.type,
                    "basin": storm.basin,
                    "current_position": {
                        "lat": storm.lat[-1],
                        "lon": storm.lon[-1],
                        "time": storm.time[-1]
                    },
                    "current_intensity": {
                        "wind": storm.vmax[-1],
                        "pressure": storm.mslp[-1],
                        "category": self._get_storm_category(storm.vmax[-1])
                    },
                    "movement": {
                        "heading": storm.heading[-1],
                        "speed": storm.speed[-1]
                    },
                    "forecast": []
                }
                
                # Add forecast information
                for i, row in enumerate(storm.forecast.iterrows()):
                    point = row[1]
                    forecast_time = point.name
                    
                    summary["forecast"].append({
                        "time": forecast_time,
                        "lat": point['lat'],
                        "lon": point['lon'],
                        "wind": point['vmax'],
                        "pressure": point['mslp'],
                        "category": self._get_storm_category(point['vmax'])
                    })
                
                return summary
            else:
                # Look for historical storm
                season = None
                
                # Try to determine season from storm ID (e.g., "AL012022")
                if len(storm_id) >= 8:
                    try:
                        season = int(storm_id[-4:])
                    except ValueError:
                        pass
                
                if not season:
                    # Use most recent season as fallback
                    current_year = datetime.now().year
                    season = current_year - 1 if datetime.now().month < 6 else current_year
                
                # Get the storm data
                season_data = self.tracks_data.get_season(season)
                
                if storm_id not in season_data:
                    return {}
                
                storm = season_data[storm_id]
                
                # Extract storm data
                summary = {
                    "id": storm_id,
                    "name": storm.name,
                    "season": storm.season,
                    "type": storm.type,
                    "basin": storm.basin,
                    "track": [],
                    "intensity": {
                        "max_wind": storm.dict["vmax"].max(),
                        "min_pressure": storm.dict["mslp"].min(),
                        "max_category": self._get_storm_category(storm.dict["vmax"].max())
                    },
                    "stats": {
                        "ace": storm.ace,
                        "track_distance": storm.track_distance,
                        "start_date": storm.dict.index[0],
                        "end_date": storm.dict.index[-1],
                        "duration_hours": (storm.dict.index[-1] - storm.dict.index[0]).total_seconds() / 3600
                    }
                }
                
                # Add track information
                for i, row in enumerate(storm.dict.iterrows()):
                    time = row[0]
                    point = row[1]
                    
                    summary["track"].append({
                        "time": time,
                        "lat": point['lat'],
                        "lon": point['lon'],
                        "wind": point['vmax'],
                        "pressure": point['mslp'],
                        "type": point['type'],
                        "category": self._get_storm_category(point['vmax'])
                    })
                
                return summary
                
        except Exception as e:
            logger.error(f"Error getting storm summary for {storm_id}: {e}")
            return {}

# Initialize as a singleton
tropical_tracker = TropicalStormTracker()