"""
Utility for creating and displaying weather forecast animations.
"""
import streamlit as st
import numpy as np
import requests
import time
import datetime
from io import BytesIO
from PIL import Image
import base64
import logging
from .web_scraper import extract_animation_frames, generate_meteocenter_url

logger = logging.getLogger(__name__)

class ForecastAnimation:
    """
    Class for handling weather forecast animations
    """
    
    def __init__(self):
        """Initialize the forecast animation handler"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.frame_cache = {}
    
    def _download_image(self, url):
        """
        Download an image from a URL
        
        Args:
            url (str): URL of the image
            
        Returns:
            BytesIO: Image data or None if failed
        """
        # Check cache first
        if url in self.frame_cache:
            cached_time, cached_data = self.frame_cache[url]
            # If cache is less than 10 minutes old, use it
            if (datetime.datetime.now() - cached_time).total_seconds() < 600:
                return BytesIO(cached_data.getvalue())
        
        try:
            response = self.session.get(url, stream=True)
            response.raise_for_status()
            
            img_data = BytesIO(response.content)
            
            # Verify it's a valid image
            try:
                Image.open(img_data).verify()
                img_data.seek(0)
                
                # Update cache
                self.frame_cache[url] = (datetime.datetime.now(), img_data)
                
                return BytesIO(img_data.getvalue())
            except Exception as e:
                logger.error(f"Invalid image data from {url}: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error downloading image from {url}: {e}")
            return None
    
    def create_lightning_wizard_animation(self, animation_url, width=800):
        """
        Create an animation from a Lightning Wizard animation URL
        
        Args:
            animation_url (str): URL of the Lightning Wizard animation page
            width (int): Width of the animation in pixels
            
        Returns:
            bool: Success status
        """
        try:
            # Extract animation frames
            animation_info = extract_animation_frames(animation_url)
            
            if not animation_info or not animation_info.get("frames"):
                st.error(f"Could not extract animation information from URL: {animation_url}")
                return False
            
            # Display animation info
            st.markdown(f"### {animation_info['model']} {animation_info['parameter'].upper()} - {animation_info['region']}")
            
            # Download frames
            frames = []
            progress_bar = st.progress(0)
            
            for i, frame in enumerate(animation_info["frames"]):
                progress_bar.progress((i + 1) / len(animation_info["frames"]))
                
                img_data = self._download_image(frame["url"])
                if img_data:
                    try:
                        frames.append({
                            "data": img_data,
                            "hour": frame["hour"]
                        })
                    except Exception as e:
                        logger.error(f"Error processing frame {i}: {e}")
            
            progress_bar.empty()
            
            if not frames:
                st.error("Could not download any animation frames.")
                return False
            
            # Create animation controls
            st.markdown("### Animation Controls")
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                play_button = st.button("▶ Play")
                
            with col2:
                frame_slider = st.slider("Frame", 0, len(frames) - 1, 0)
                
            with col3:
                speed = st.selectbox("Speed", [0.5, 1, 2, 3], index=1)
            
            # Display the current frame
            current_frame = frames[frame_slider]
            st.image(current_frame["data"], caption=f"Forecast Hour: +{current_frame['hour']}h", width=width)
            
            # Auto-play functionality
            if play_button:
                animation_placeholder = st.empty()
                for i in range(frame_slider, len(frames)):
                    if st.session_state.get("stop_animation", False):
                        break
                    
                    with animation_placeholder.container():
                        st.image(frames[i]["data"], caption=f"Forecast Hour: +{frames[i]['hour']}h", width=width)
                    
                    time.sleep(1 / speed)
            
            return True
            
        except Exception as e:
            st.error(f"Error creating Lightning Wizard animation: {e}")
            logger.error(f"Error creating Lightning Wizard animation: {e}")
            return False
    
    def create_meteocenter_animation(self, model, parameter, width=800):
        """
        Create an animation from MeteoCenter forecast images
        
        Args:
            model (str): Model name (e.g., "GDPS", "GFS")
            parameter (str): Parameter code (e.g., "CAPE", "T850")
            width (int): Width of the animation in pixels
            
        Returns:
            bool: Success status
        """
        try:
            # Get today's date
            today = datetime.datetime.now().strftime("%Y%m%d")
            
            # Define forecast hours
            if model.upper() in ["GDPS", "GFS"]:
                forecast_hours = list(range(0, 85, 6))  # 0h to 84h by 6-hour intervals
            else:
                forecast_hours = list(range(0, 49, 3))  # 0h to 48h by 3-hour intervals
            
            # Display animation info
            st.markdown(f"### {model.upper()} {parameter.upper()} Forecast")
            
            # Generate URLs for each frame
            frames = []
            progress_bar = st.progress(0)
            
            for i, hour in enumerate(forecast_hours):
                progress_bar.progress((i + 1) / len(forecast_hours))
                
                # For MeteoCenter, we need to handle the display of forecast hours differently
                # They typically show forecast hour as part of the filename or on the image itself
                url = generate_meteocenter_url(model, today, parameter, "12Z")
                
                # If specific hour formats are available, use them
                if url:
                    img_data = self._download_image(url)
                    if img_data:
                        frames.append({
                            "data": img_data,
                            "hour": hour
                        })
            
            progress_bar.empty()
            
            if not frames:
                st.error(f"Could not download any {model} {parameter} forecast images.")
                return False
            
            # Create animation controls
            st.markdown("### Animation Controls")
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col1:
                play_button = st.button("▶ Play")
                
            with col2:
                frame_slider = st.slider("Frame", 0, len(frames) - 1, 0)
                
            with col3:
                speed = st.selectbox("Speed", [0.5, 1, 2, 3], index=1)
            
            # Display the current frame
            current_frame = frames[frame_slider]
            st.image(current_frame["data"], caption=f"Forecast Hour: +{current_frame['hour']}h", width=width)
            
            # Auto-play functionality
            if play_button:
                animation_placeholder = st.empty()
                for i in range(frame_slider, len(frames)):
                    if st.session_state.get("stop_animation", False):
                        break
                    
                    with animation_placeholder.container():
                        st.image(frames[i]["data"], caption=f"Forecast Hour: +{frames[i]['hour']}h", width=width)
                    
                    time.sleep(1 / speed)
            
            return True
            
        except Exception as e:
            st.error(f"Error creating MeteoCenter animation: {e}")
            logger.error(f"Error creating MeteoCenter animation: {e}")
            return False