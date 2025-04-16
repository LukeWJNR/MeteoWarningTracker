"""
Module for integrating with Lightning Wizard (lightningwizard.com) to get severe weather forecast maps
"""
import requests
import logging
import pandas as pd
import numpy as np
import datetime
import re
from bs4 import BeautifulSoup
import trafilatura
from io import BytesIO
from PIL import Image
import folium
import base64
import streamlit as st

logger = logging.getLogger(__name__)

class LightningWizardService:
    """
    A class to handle fetching severe weather map data from Lightning Wizard
    """
    BASE_URL = "https://www.lightningwizard.com"
    MAPS_URL = "https://www.lightningwizard.com/maps"
    
    # Known map URLs that can be directly accessed (based on website structure)
    FORECAST_MAP_URLS = {
        "lightning": [
            "https://www.lightningwizard.com/maps/usltg.png",
            "https://www.lightningwizard.com/maps/ltgna.png"
        ],
        "radar": [
            "https://www.lightningwizard.com/maps/usrad.png",
            "https://www.lightningwizard.com/maps/narad.png"
        ],
        "satellite": [
            "https://www.lightningwizard.com/maps/ussat.png",
            "https://www.lightningwizard.com/maps/nasat.png"
        ],
        "severe_weather": [
            "https://www.lightningwizard.com/maps/ussevere.png",
            "https://www.lightningwizard.com/maps/nasevere.png"
        ]
    }
    
    def __init__(self):
        """Initialize the Lightning Wizard service"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        # Cache for downloaded maps
        self.map_cache = {}
    
    def get_forecast_maps(self, map_type=None):
        """
        Get forecast maps from Lightning Wizard
        
        Args:
            map_type (str, optional): Type of map to retrieve (e.g., "lightning", "radar", "satellite", "severe_weather")
            
        Returns:
            list: List of maps with their URLs and metadata
        """
        maps_list = []
        
        # If a specific map type is requested, return only those maps
        if map_type and map_type in self.FORECAST_MAP_URLS:
            for url in self.FORECAST_MAP_URLS[map_type]:
                map_name = url.split('/')[-1].split('.')[0]
                region = "US" if "us" in map_name.lower() else "North America"
                maps_list.append({
                    'url': url,
                    'title': f"{map_type.replace('_', ' ').title()} - {region}",
                    'type': map_type,
                    'region': region
                })
            return maps_list
        
        # Otherwise, return all maps
        for map_type, urls in self.FORECAST_MAP_URLS.items():
            for url in urls:
                map_name = url.split('/')[-1].split('.')[0]
                region = "US" if "us" in map_name.lower() else "North America"
                maps_list.append({
                    'url': url,
                    'title': f"{map_type.replace('_', ' ').title()} - {region}",
                    'type': map_type,
                    'region': region
                })
        
        return maps_list
    
    def discover_available_maps(self):
        """
        Attempt to discover all available maps from the website
        
        Returns:
            dict: Dictionary of discovered maps by type
        """
        try:
            # Get the maps page to see what's available
            response = self.session.get(self.MAPS_URL)
            response.raise_for_status()
            
            # Parse the page to extract map links
            soup = BeautifulSoup(response.text, 'html.parser')
            discovered_maps = {}
            
            # Find image links
            img_tags = soup.find_all('img', src=True)
            for img in img_tags:
                src = img['src']
                
                # Only consider image files
                if not src.endswith(('.png', '.jpg', '.gif')):
                    continue
                
                # Make sure URL is absolute
                img_url = src if src.startswith('http') else f"{self.BASE_URL}/{src.lstrip('/')}"
                
                # Try to determine map type from URL or alt text
                detected_type = 'other'
                alt_text = img.get('alt', '').lower()
                
                for keyword, map_type in [
                    ('lightning', 'lightning'),
                    ('ltg', 'lightning'),
                    ('radar', 'radar'),
                    ('sat', 'satellite'),
                    ('satellite', 'satellite'),
                    ('severe', 'severe_weather'),
                    ('precip', 'precipitation'),
                    ('precipitation', 'precipitation'),
                    ('temp', 'temperature'),
                    ('temperature', 'temperature')
                ]:
                    if keyword in img_url.lower() or keyword in alt_text:
                        detected_type = map_type
                        break
                
                # Also check parent elements for context
                parent = img.parent
                if parent and parent.name == 'a':
                    parent_text = parent.get_text().lower()
                    for keyword, map_type in [
                        ('lightning', 'lightning'),
                        ('radar', 'radar'),
                        ('satellite', 'satellite'),
                        ('severe', 'severe_weather')
                    ]:
                        if keyword in parent_text:
                            detected_type = map_type
                            break
                
                # Add to our maps dictionary
                if detected_type not in discovered_maps:
                    discovered_maps[detected_type] = []
                
                # Create a title based on what we know
                map_name = img_url.split('/')[-1].split('.')[0]
                region = "US" if "us" in map_name.lower() else "North America" if "na" in map_name.lower() else "Unknown"
                
                discovered_maps[detected_type].append({
                    'url': img_url,
                    'title': img.get('alt') or f"{detected_type.replace('_', ' ').title()} - {region}",
                    'type': detected_type,
                    'region': region
                })
            
            # Also check direct anchor links to images
            a_tags = soup.find_all('a', href=True)
            for a in a_tags:
                href = a['href']
                
                # Only consider image files
                if not href.endswith(('.png', '.jpg', '.gif')):
                    continue
                
                # Make sure URL is absolute
                img_url = href if href.startswith('http') else f"{self.BASE_URL}/{href.lstrip('/')}"
                
                # Skip if we already found this URL in img tags
                already_found = False
                for map_list in discovered_maps.values():
                    if any(m['url'] == img_url for m in map_list):
                        already_found = True
                        break
                
                if already_found:
                    continue
                
                # Try to determine map type from URL or link text
                detected_type = 'other'
                link_text = a.get_text().lower()
                
                for keyword, map_type in [
                    ('lightning', 'lightning'),
                    ('ltg', 'lightning'),
                    ('radar', 'radar'),
                    ('sat', 'satellite'),
                    ('satellite', 'satellite'),
                    ('severe', 'severe_weather'),
                    ('precip', 'precipitation'),
                    ('precipitation', 'precipitation'),
                    ('temp', 'temperature'),
                    ('temperature', 'temperature')
                ]:
                    if keyword in img_url.lower() or keyword in link_text:
                        detected_type = map_type
                        break
                
                # Add to our maps dictionary
                if detected_type not in discovered_maps:
                    discovered_maps[detected_type] = []
                
                # Create a title based on what we know
                map_name = img_url.split('/')[-1].split('.')[0]
                region = "US" if "us" in map_name.lower() else "North America" if "na" in map_name.lower() else "Unknown"
                
                discovered_maps[detected_type].append({
                    'url': img_url,
                    'title': a.get_text().strip() or f"{detected_type.replace('_', ' ').title()} - {region}",
                    'type': detected_type,
                    'region': region
                })
            
            # Update our known map URLs with any new discoveries
            for map_type, maps in discovered_maps.items():
                if map_type not in self.FORECAST_MAP_URLS:
                    self.FORECAST_MAP_URLS[map_type] = []
                
                for map_info in maps:
                    if map_info['url'] not in self.FORECAST_MAP_URLS[map_type]:
                        self.FORECAST_MAP_URLS[map_type].append(map_info['url'])
            
            logger.info(f"Discovered {sum(len(maps) for maps in discovered_maps.values())} maps from Lightning Wizard")
            return discovered_maps
            
        except requests.RequestException as e:
            logger.error(f"Error discovering maps from Lightning Wizard: {e}")
            return {}
    
    def download_map_image(self, url):
        """
        Download a map image from a URL
        
        Args:
            url (str): URL of the image to download
            
        Returns:
            BytesIO: Binary image data or None if failed
        """
        # Check cache first
        if url in self.map_cache:
            cached_time, cached_data = self.map_cache[url]
            # If cache is less than 10 minutes old, use it
            if (datetime.datetime.now() - cached_time).total_seconds() < 600:
                # Make a copy of the BytesIO object to reset position
                copy_data = BytesIO(cached_data.getvalue())
                return copy_data
        
        try:
            response = self.session.get(url, stream=True)
            response.raise_for_status()
            
            # Create BytesIO object from image data
            img_data = BytesIO(response.content)
            
            # Verify it's a valid image
            try:
                Image.open(img_data).verify()
                img_data.seek(0)  # Reset file pointer after verification
                
                # Update cache
                self.map_cache[url] = (datetime.datetime.now(), img_data)
                
                # Return a copy so the position is at 0
                return BytesIO(img_data.getvalue())
            except Exception as e:
                logger.error(f"Invalid image data from {url}: {e}")
                return None
            
        except requests.RequestException as e:
            logger.error(f"Error downloading map image from {url}: {e}")
            return None
    
    def get_severe_weather_map(self, region="US"):
        """
        Get the severe weather map for a specific region
        
        Args:
            region (str): Region to get map for ("US" or "NA" for North America)
            
        Returns:
            BytesIO: Binary image data or None if failed
        """
        if region.upper() == "US":
            url = self.FORECAST_MAP_URLS.get("severe_weather", [])[0] if self.FORECAST_MAP_URLS.get("severe_weather") else None
        else:  # North America
            url = self.FORECAST_MAP_URLS.get("severe_weather", [])[1] if len(self.FORECAST_MAP_URLS.get("severe_weather", [])) > 1 else None
        
        if not url:
            logger.error(f"No severe weather map URL found for region {region}")
            return None
        
        return self.download_map_image(url)
    
    def get_lightning_map(self, region="US"):
        """
        Get the lightning map for a specific region
        
        Args:
            region (str): Region to get map for ("US" or "NA" for North America)
            
        Returns:
            BytesIO: Binary image data or None if failed
        """
        if region.upper() == "US":
            url = self.FORECAST_MAP_URLS.get("lightning", [])[0] if self.FORECAST_MAP_URLS.get("lightning") else None
        else:  # North America
            url = self.FORECAST_MAP_URLS.get("lightning", [])[1] if len(self.FORECAST_MAP_URLS.get("lightning", [])) > 1 else None
        
        if not url:
            logger.error(f"No lightning map URL found for region {region}")
            return None
        
        return self.download_map_image(url)
    
    def display_map_in_streamlit(self, map_type, region="US", width=800):
        """
        Display a map directly in Streamlit
        
        Args:
            map_type (str): Type of map to display (e.g., "lightning", "radar", "satellite", "severe_weather")
            region (str): Region to display ("US" or "NA" for North America)
            width (int): Width of the displayed image
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Find the correct URL for the requested map
        url = None
        for map_info in self.get_forecast_maps(map_type):
            if region.upper() in map_info['region'].upper():
                url = map_info['url']
                break
        
        if not url:
            st.error(f"No {map_type} map available for {region}")
            return False
        
        try:
            # Download the image
            img_data = self.download_map_image(url)
            if img_data:
                # Display the image
                st.image(img_data, caption=f"{map_type.replace('_', ' ').title()} - {region}", width=width)
                st.caption(f"Source: Lightning Wizard - Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
                return True
            else:
                st.error(f"Could not load {map_type} map for {region}")
                return False
                
        except Exception as e:
            st.error(f"Error displaying {map_type} map: {e}")
            return False
    
    def create_folium_overlay(self, map_type, folium_map, region="US", opacity=0.7):
        """
        Add a map overlay to a Folium map
        
        Args:
            map_type (str): Type of map to overlay (e.g., "lightning", "radar", "satellite", "severe_weather")
            folium_map (folium.Map): Folium map object to add the overlay to
            region (str): Region to display ("US" or "NA" for North America)
            opacity (float): Opacity of the overlay (0-1)
            
        Returns:
            folium.Map: The updated map object
        """
        # Find the correct URL for the requested map
        url = None
        for map_info in self.get_forecast_maps(map_type):
            if region.upper() in map_info['region'].upper():
                url = map_info['url']
                break
        
        if not url:
            logger.error(f"No {map_type} map available for {region}")
            return folium_map
        
        try:
            # Download the image
            img_data = self.download_map_image(url)
            if not img_data:
                logger.error(f"Could not load {map_type} map for {region}")
                return folium_map
            
            # Define map bounds
            if region.upper() == "US":
                bounds = [[24.396308, -125.000000], [49.384358, -66.934570]]  # Continental US bounds
            else:  # North America
                bounds = [[15.000000, -169.000000], [72.000000, -52.000000]]  # North America bounds
            
            # Convert to base64 to avoid JSON serialization issues
            img_base64 = base64.b64encode(img_data.getvalue()).decode("utf-8")
            
            # Add the overlay
            from folium.raster_layers import ImageOverlay
            overlay = ImageOverlay(
                f"data:image/png;base64,{img_base64}",
                bounds=bounds,
                opacity=opacity,
                name=f"{map_type.replace('_', ' ').title()} Overlay"
            )
            overlay.add_to(folium_map)
            
            # Add layer control if it doesn't exist yet
            if not any(isinstance(child, folium.LayerControl) for child in folium_map._children.values()):
                folium.LayerControl().add_to(folium_map)
            
            return folium_map
            
        except Exception as e:
            logger.error(f"Error adding {map_type} overlay to map: {e}")
            return folium_map

# Initialize as a singleton for reuse
lightning_wizard = LightningWizardService()