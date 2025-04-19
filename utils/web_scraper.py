"""
Utility for scraping web content, particularly weather forecast maps and animations.
"""
import requests
import trafilatura
import re
import logging
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

logger = logging.getLogger(__name__)

def get_website_text_content(url: str) -> str:
    """
    This function takes a url and returns the main text content of the website.
    The text content is extracted using trafilatura and easier to understand.
    
    Args:
        url (str): URL of the website to scrape
        
    Returns:
        str: Extracted text content
    """
    try:
        # Send a request to the website
        downloaded = trafilatura.fetch_url(url)
        text = trafilatura.extract(downloaded)
        return text
    except Exception as e:
        logger.error(f"Error extracting text content from {url}: {e}")
        return ""

def extract_animation_frames(animation_url: str) -> dict:
    """
    Extract animation frame information from a Lightning Wizard animation URL.
    
    Args:
        animation_url (str): URL of the animation page
        
    Returns:
        dict: Information about the animation including model, parameter, region, and frames
    """
    try:
        # Parse the URL
        parsed_url = urlparse(animation_url)
        
        # Extract base parts from the path
        path_parts = parsed_url.path.strip('/').split('/')
        if len(path_parts) >= 2:
            region = path_parts[-2]  # e.g., "Europe"
        else:
            region = "Unknown"
            
        # Parse query parameters
        query_parts = parsed_url.query.split(',')
        if len(query_parts) >= 3:
            time_index = int(query_parts[0])
            model_param = query_parts[1]  # e.g., "gfs_mucape_eur"
            extension = query_parts[2]  # e.g., ".png"
            
            # Extract forecast hours
            forecast_hours = []
            for part in query_parts[3:]:
                try:
                    forecast_hours.append(int(part))
                except ValueError:
                    continue
                    
            # Try to determine model and parameter from model_param string
            model_parts = model_param.split('_')
            if len(model_parts) >= 2:
                model = model_parts[0].upper()  # e.g., "GFS"
                parameter = '_'.join(model_parts[1:-1]) if len(model_parts) > 2 else model_parts[1]  # e.g., "mucape"
            else:
                model = model_param
                parameter = ""
                
            # Create base URL for image frames
            base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"
            path_prefix = '/'.join(path_parts[:-1])  # Path excluding filename
            
            # Create frame URLs
            frame_urls = []
            for hour in forecast_hours:
                frame_url = f"{base_domain}/{path_prefix}/{model.lower()}_{parameter}_{hour:03d}{extension}"
                frame_urls.append({"hour": hour, "url": frame_url})
                
            return {
                "region": region,
                "model": model,
                "parameter": parameter,
                "extension": extension,
                "forecast_hours": forecast_hours,
                "frames": frame_urls,
                "base_url": base_domain
            }
        else:
            logger.error(f"Could not parse animation URL format: {animation_url}")
            return {}
            
    except Exception as e:
        logger.error(f"Error extracting animation frames from {animation_url}: {e}")
        return {}

def get_available_animation_pages(base_url: str = "https://www.lightningwizard.com") -> list:
    """
    Get a list of available animation pages from Lightning Wizard.
    
    Args:
        base_url (str): Base URL of the website
        
    Returns:
        list: List of animation page URLs and their descriptions
    """
    try:
        # Potential paths to check
        paths_to_check = [
            "/maps",
            "/maps/usa",
            "/maps/Europe",
            "/maps/Australia",
            "/maps/Canada",
            "/maps/Asia"
        ]
        
        animation_pages = []
        
        for path in paths_to_check:
            url = f"{base_url}{path}"
            response = requests.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Look for links to animation pages
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if 'ani.html' in href or 'animation' in href.lower() or 'anim' in href.lower():
                        full_url = urljoin(url, href)
                        animation_pages.append({
                            "url": full_url,
                            "text": link.get_text().strip() or "Animation",
                            "region": path.split('/')[-1] if path != "/maps" else "Global"
                        })
        
        return animation_pages
    
    except Exception as e:
        logger.error(f"Error getting available animation pages: {e}")
        return []

def generate_meteocenter_url(model: str, date: str, parameter: str, hour: str = "12Z", region: str = None) -> str:
    """
    Generate a URL for a MeteoCenter forecast image.
    
    Args:
        model (str): Model name (e.g., "GDPS", "GFS")
        date (str): Date in format YYYYMMDD
        parameter (str): Parameter code (e.g., "CAPE", "T850")
        hour (str): Model run hour (e.g., "00Z", "12Z")
        region (str, optional): Region code (e.g., "na" for North America, 
                               "us" for United States, "eu" for Europe)
        
    Returns:
        str: URL to the forecast image
    """
    try:
        # Define region-specific path component if provided
        region_path = ""
        if region:
            region = region.lower()
            # Map region codes to URL path components
            region_map = {
                "na": "north_america",
                "us": "usa",
                "eu": "europe",
                "global": "global",
                "atl": "atlantic",
                "pac": "pacific",
                "asia": "asia",
                "aus": "australia",
                "sa": "south_america",
                "af": "africa"
            }
            # Get the region path if it's in our map
            if region in region_map:
                region_path = f"/{region_map[region]}"
        
        # Standard path format with optional region component
        url = f"https://meteocentre.com/plus/{model.lower()}{region_path}/{date}/{parameter}/{hour}.png"
        
        # Alternative paths to try based on common patterns
        alternative_urls = []
        
        # Try alternative dates (yesterday and tomorrow)
        from datetime import datetime, timedelta
        
        # Convert string date to datetime for manipulation
        try:
            date_obj = datetime.strptime(date, "%Y%m%d")
            yesterday = (date_obj - timedelta(days=1)).strftime("%Y%m%d")
            tomorrow = (date_obj + timedelta(days=1)).strftime("%Y%m%d")
            
            # Add alternative dates with the region path if specified
            alternative_urls.extend([
                f"https://meteocentre.com/plus/{model.lower()}{region_path}/{yesterday}/{parameter}/{hour}.png",
                f"https://meteocentre.com/plus/{model.lower()}{region_path}/{tomorrow}/{parameter}/{hour}.png"
            ])
        except ValueError:
            pass  # Invalid date format, skip alternatives
        
        # Try alternative parameter formats
        if parameter.isupper():
            alternative_urls.append(f"https://meteocentre.com/plus/{model.lower()}{region_path}/{date}/{parameter.lower()}/{hour}.png")
        else:
            alternative_urls.append(f"https://meteocentre.com/plus/{model.lower()}{region_path}/{date}/{parameter.upper()}/{hour}.png")
        
        # Try alternative model run hours
        for alt_hour in ["00Z", "06Z", "12Z", "18Z"]:
            if alt_hour != hour:
                alternative_urls.append(f"https://meteocentre.com/plus/{model.lower()}{region_path}/{date}/{parameter}/{alt_hour}.png")
        
        # Return the primary URL
        return url
    except Exception as e:
        logger.error(f"Error generating MeteoCenter URL: {e}")
        return ""

def get_meteocenter_alternative_urls(model: str, date: str, parameter: str, region: str = None) -> list:
    """
    Generate a list of alternative URLs for MeteoCenter forecast images.
    This is useful when the primary URL fails to load.
    
    Args:
        model (str): Model name (e.g., "GDPS", "GFS")
        date (str): Date in format YYYYMMDD
        parameter (str): Parameter code (e.g., "CAPE", "T850")
        region (str, optional): Region code (e.g., "na" for North America,
                               "us" for United States, "eu" for Europe)
        
    Returns:
        list: List of alternative URLs to try
    """
    try:
        alternative_urls = []
        
        # Convert string date to datetime for manipulation
        from datetime import datetime, timedelta
        
        try:
            date_obj = datetime.strptime(date, "%Y%m%d")
            yesterday = (date_obj - timedelta(days=1)).strftime("%Y%m%d")
            tomorrow = (date_obj + timedelta(days=1)).strftime("%Y%m%d")
            
            # Add all possible combinations of dates, hours, and parameter cases
            hours = ["00Z", "06Z", "12Z", "18Z"]
            dates = [yesterday, date, tomorrow]
            
            param_variants = [parameter]
            if parameter.isupper():
                param_variants.append(parameter.lower())
            else:
                param_variants.append(parameter.upper())
                
            # Generate all combinations
            for d in dates:
                for h in hours:
                    for p in param_variants:
                        url = f"https://meteocentre.com/plus/{model.lower()}/{d}/{p}/{h}.png"
                        alternative_urls.append(url)
        except ValueError:
            # If date parsing fails, just try the basic alternatives
            for hour in ["00Z", "06Z", "12Z", "18Z"]:
                alternative_urls.append(f"https://meteocentre.com/plus/{model.lower()}/{date}/{parameter}/{hour}.png")
        
        # Add alternate domains/paths
        base_url = f"https://meteocentre.com/plus/{model.lower()}/latest/{parameter}.png"
        alternative_urls.append(base_url)
        
        return alternative_urls
    except Exception as e:
        logger.error(f"Error generating alternative MeteoCenter URLs: {e}")
        return []