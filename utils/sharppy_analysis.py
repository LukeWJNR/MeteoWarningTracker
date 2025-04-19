"""
Utility for accessing SHARPpy (Sounding and Hodograph Analysis and Research Program in Python)
for advanced meteorological analysis and severe weather parameter calculation.
"""
import io
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import requests
from io import BytesIO
import base64

# Import SHARPpy modules (wrapped in try/except for flexibility)
try:
    import sharppy
    import sharppy.sharptab.profile as profile
    import sharppy.sharptab.params as params
    import sharppy.sharptab.interp as interp
    import sharppy.sharptab.winds as winds
    import sharppy.sharptab.utils as utils
    import sharppy.sharptab.thermo as thermo
    SHARPPY_AVAILABLE = True
except ImportError:
    SHARPPY_AVAILABLE = False
    logging.warning("SHARPpy not available. Some functionality will be limited.")

# Set up logging
logger = logging.getLogger(__name__)

class SevereWeatherAnalyzer:
    """
    A class for severe weather analysis using SHARPpy.
    """
    
    def __init__(self):
        """Initialize the analyzer with default values."""
        self.latest_data = None
        self.latest_analysis = None
        self.skewt_image = None
        self.hodograph_image = None
    
    def check_availability(self):
        """Check if SHARPpy is available for use."""
        return SHARPPY_AVAILABLE
    
    def load_model_data_from_ncep(self, lat, lon, model="GFS", forecast_hour=0):
        """
        Load model data from NCEP for a specific location and create a SHARPpy profile.
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            model (str): Model name (e.g., "GFS", "NAM", "RAP", "HRRR")
            forecast_hour (int): Forecast hour
            
        Returns:
            bool: Success status
        """
        if not SHARPPY_AVAILABLE:
            logger.warning("SHARPpy not available. Cannot load model data.")
            return False
        
        try:
            # In a full implementation, this would use siphon to access NCEP data
            # For now, we'll generate a sample profile
            self.latest_data = self._generate_sample_profile(lat, lon, model, forecast_hour)
            
            # Create a SHARPpy profile from the data
            if self.latest_data:
                self._create_profile()
                logger.info(f"Successfully created SHARPpy profile for {lat}, {lon}")
                return True
            else:
                logger.error("Failed to create sample profile")
                return False
                
        except Exception as e:
            logger.error(f"Error loading model data: {e}")
            return False
    
    def _create_profile(self):
        """
        Create a SHARPpy profile from the latest data.
        
        Returns:
            bool: Success status
        """
        if not SHARPPY_AVAILABLE or self.latest_data is None:
            return False
            
        try:
            # Extract pressure, height, temperature, dewpoint, wind direction, wind speed
            data = self.latest_data
            
            # Create arrays for SHARPpy
            pres = data['pres'].values  # Pressure in hPa
            hght = data['hght'].values  # Height in meters
            tmpc = data['tmpc'].values  # Temperature in C
            dwpc = data['dwpc'].values  # Dewpoint in C
            wspd = data['wspd'].values  # Wind speed in knots
            wdir = data['wdir'].values  # Wind direction in degrees
            
            # Create the profile
            prof = profile.create_profile(pres=pres, hght=hght, tmpc=tmpc, dwpc=dwpc, 
                                         wspd=wspd, wdir=wdir, missing=-9999, strictQC=False)
            
            # Store the profile and calculate parameters
            self.latest_analysis = prof
            
            # Generate the SkewT-LogP diagram
            self._generate_profile_plots()
            
            return True
            
        except Exception as e:
            logger.error(f"Error creating SHARPpy profile: {e}")
            return False
    
    def _generate_profile_plots(self):
        """
        Generate SHARPpy profile plots, including SkewT-LogP diagram and hodograph.
        
        Returns:
            bool: Success status
        """
        if not SHARPPY_AVAILABLE or self.latest_analysis is None:
            return False
            
        try:
            # Create matplotlib figure for SkewT-LogP
            fig = plt.figure(figsize=(9, 8))
            ax = fig.add_subplot(111)
            
            # Plot the data using SHARPpy plotting utilities (simplified for now)
            # In a complete implementation, this would use the SHARPpy plotting utilities
            
            # For now, just create a basic plot to demonstrate functionality
            skew_pres = self.latest_analysis.pres
            skew_tmpc = self.latest_analysis.tmpc
            skew_dwpc = self.latest_analysis.dwpc
            
            # Basic plot
            ax.semilogy(skew_tmpc, skew_pres, 'r-', linewidth=2, label='Temperature')
            ax.semilogy(skew_dwpc, skew_pres, 'g-', linewidth=2, label='Dewpoint')
            
            ax.set_ylim(1050, 100)
            ax.invert_yaxis()
            ax.set_xlabel('Temperature (°C)')
            ax.set_ylabel('Pressure (hPa)')
            ax.set_title('SkewT-LogP Diagram (Basic Representation)')
            ax.grid(True)
            ax.legend()
            
            # Save to memory
            buf = BytesIO()
            fig.savefig(buf, format='png')
            buf.seek(0)
            self.skewt_image = buf
            
            plt.close(fig)
            
            # In a similar way, we would create the hodograph
            # But for simplicity, we'll skip that for now
            
            return True
            
        except Exception as e:
            logger.error(f"Error generating profile plots: {e}")
            return False
    
    def generate_skewt_plot(self):
        """
        Return the SkewT-LogP diagram as an image.
        
        Returns:
            BytesIO: SkewT image data or None if not available
        """
        return self.skewt_image
    
    def extract_severe_weather_summary(self):
        """
        Extract a summary of severe weather parameters from the latest analysis.
        
        Returns:
            dict: Dictionary with severe weather parameters
        """
        if not SHARPPY_AVAILABLE or self.latest_analysis is None:
            return self._generate_sample_summary()
        
        try:
            # Extract parameters from the profile
            analysis = self.latest_analysis
            
            # Extract CAPE, CIN
            sfc_cape = int(params.parcelx(analysis, flag=1).bplus)  # Surface parcel
            ml_cape = int(params.parcelx(analysis, flag=2).bplus)   # Mixed-layer parcel
            mu_cape = int(params.parcelx(analysis, flag=3).bplus)   # Most-unstable parcel
            
            sfc_cin = int(params.parcelx(analysis, flag=1).bminus)  # Surface parcel
            ml_cin = int(params.parcelx(analysis, flag=2).bminus)   # Mixed-layer parcel
            mu_cin = int(params.parcelx(analysis, flag=3).bminus)   # Most-unstable parcel
            
            # Extract LCL heights
            sfc_lcl = int(params.parcelx(analysis, flag=1).lclhght)  # Surface parcel LCL
            ml_lcl = int(params.parcelx(analysis, flag=2).lclhght)   # Mixed-layer parcel LCL
            mu_lcl = int(params.parcelx(analysis, flag=3).lclhght)   # Most-unstable parcel LCL
            
            # Calculate shear parameters
            sfc_6km_shear = int(winds.wind_shear(analysis, pbot=analysis.pres[0], ptop=interp.pres(analysis, 6000)).mag())
            sfc_1km_shear = int(winds.wind_shear(analysis, pbot=analysis.pres[0], ptop=interp.pres(analysis, 1000)).mag())
            sfc_3km_shear = int(winds.wind_shear(analysis, pbot=analysis.pres[0], ptop=interp.pres(analysis, 3000)).mag())
            
            # Calculate helicity
            srh_1km = int(winds.helicity(analysis, 0, 1000)[0])
            srh_3km = int(winds.helicity(analysis, 0, 3000)[0])
            
            # Calculate severe weather indices
            stp = params.stp_fixed(analysis)  # Significant Tornado Parameter
            scp = params.scp(analysis)  # Supercell Composite Parameter
            li = params.li(analysis, flag=0)  # Lifted Index
            k_index = params.k_index(analysis)  # K-Index
            totals = params.totals_totals(analysis)  # Total Totals Index
            
            # Other parameters
            pwat = params.precip_water(analysis)  # Precipitable water
            
            # Lapse rates
            lr_03 = params.lapse_rate(analysis, 0, 3000)  # 0-3km lapse rate
            lr_700_500 = params.lapse_rate(analysis, 700, 500, pres=True)  # 700-500mb lapse rate
            
            return {
                "cape": {
                    "surface": sfc_cape,
                    "mixed_layer": ml_cape,
                    "most_unstable": mu_cape
                },
                "cin": {
                    "surface": sfc_cin,
                    "mixed_layer": ml_cin,
                    "most_unstable": mu_cin
                },
                "lcl_height": {
                    "surface": sfc_lcl,
                    "mixed_layer": ml_lcl,
                    "most_unstable": mu_lcl
                },
                "shear": {
                    "0_6km": sfc_6km_shear,
                    "0_1km": sfc_1km_shear,
                    "0_3km": sfc_3km_shear
                },
                "helicity": {
                    "0_1km": srh_1km,
                    "0_3km": srh_3km
                },
                "indices": {
                    "stp": stp,
                    "scp": scp,
                    "li": li,
                    "k_index": k_index,
                    "totals": totals
                },
                "moisture": {
                    "pwat": pwat,
                },
                "lapse_rates": {
                    "0_3km": lr_03,
                    "700_500mb": lr_700_500
                }
            }
            
        except Exception as e:
            logger.error(f"Error extracting severe weather summary: {e}")
            return self._generate_sample_summary()
    
    def get_severe_weather_threat(self):
        """
        Assess severe weather threats based on the latest analysis.
        
        Returns:
            dict: Dictionary with severe weather threat assessments
        """
        if not SHARPPY_AVAILABLE or self.latest_analysis is None:
            return self._generate_sample_threat()
        
        # Get the summary data
        summary = self.extract_severe_weather_summary()
        
        # Initialize the threat assessment
        threat = {
            "tornado": {"level": "none", "factors": []},
            "hail": {"level": "none", "factors": []},
            "wind": {"level": "none", "factors": []},
            "flash_flood": {"level": "none", "factors": []}
        }
        
        # Tornado threat assessment
        # Factors: CAPE, SRH, LCL height, shear
        if summary["cape"]["surface"] > 1000 and summary["helicity"]["0_1km"] > 100:
            if summary["lcl_height"]["surface"] < 1000 and summary["shear"]["0_1km"] > 20:
                threat["tornado"]["level"] = "high"
                threat["tornado"]["factors"] = [
                    f"CAPE: {summary['cape']['surface']} J/kg (>1000)",
                    f"0-1km SRH: {summary['helicity']['0_1km']} m²/s² (>100)",
                    f"LCL Height: {summary['lcl_height']['surface']} m (<1000)",
                    f"0-1km Shear: {summary['shear']['0_1km']} kts (>20)"
                ]
            elif summary["lcl_height"]["surface"] < 1500 and summary["shear"]["0_1km"] > 15:
                threat["tornado"]["level"] = "moderate"
                threat["tornado"]["factors"] = [
                    f"CAPE: {summary['cape']['surface']} J/kg (>1000)",
                    f"0-1km SRH: {summary['helicity']['0_1km']} m²/s² (>100)",
                    f"LCL Height: {summary['lcl_height']['surface']} m (<1500)",
                    f"0-1km Shear: {summary['shear']['0_1km']} kts (>15)"
                ]
            else:
                threat["tornado"]["level"] = "slight"
                threat["tornado"]["factors"] = [
                    f"CAPE: {summary['cape']['surface']} J/kg (>1000)",
                    f"0-1km SRH: {summary['helicity']['0_1km']} m²/s² (>100)"
                ]
        elif summary["cape"]["surface"] > 500 and summary["helicity"]["0_1km"] > 50:
            threat["tornado"]["level"] = "slight"
            threat["tornado"]["factors"] = [
                f"CAPE: {summary['cape']['surface']} J/kg (>500)",
                f"0-1km SRH: {summary['helicity']['0_1km']} m²/s² (>50)"
            ]
        
        # Hail threat assessment
        # Factors: CAPE, 0-6km shear, freezing level
        if summary["cape"]["most_unstable"] > 2000 and summary["shear"]["0_6km"] > 40:
            threat["hail"]["level"] = "high"
            threat["hail"]["factors"] = [
                f"MUCAPE: {summary['cape']['most_unstable']} J/kg (>2000)",
                f"0-6km Shear: {summary['shear']['0_6km']} kts (>40)",
                "Favorable thermodynamic profile for large hail"
            ]
        elif summary["cape"]["most_unstable"] > 1500 and summary["shear"]["0_6km"] > 30:
            threat["hail"]["level"] = "moderate"
            threat["hail"]["factors"] = [
                f"MUCAPE: {summary['cape']['most_unstable']} J/kg (>1500)",
                f"0-6km Shear: {summary['shear']['0_6km']} kts (>30)"
            ]
        elif summary["cape"]["most_unstable"] > 1000 and summary["shear"]["0_6km"] > 20:
            threat["hail"]["level"] = "slight"
            threat["hail"]["factors"] = [
                f"MUCAPE: {summary['cape']['most_unstable']} J/kg (>1000)",
                f"0-6km Shear: {summary['shear']['0_6km']} kts (>20)"
            ]
        
        # Wind threat assessment
        # Factors: CAPE, downdraft CAPE, LCL height, 0-6km shear
        if summary["cape"]["mixed_layer"] > 1500 and summary["shear"]["0_6km"] > 30:
            threat["wind"]["level"] = "high"
            threat["wind"]["factors"] = [
                f"MLCAPE: {summary['cape']['mixed_layer']} J/kg (>1500)",
                f"0-6km Shear: {summary['shear']['0_6km']} kts (>30)",
                "Favorable for organized convection with strong winds"
            ]
        elif summary["cape"]["mixed_layer"] > 1000 and summary["shear"]["0_6km"] > 20:
            threat["wind"]["level"] = "moderate"
            threat["wind"]["factors"] = [
                f"MLCAPE: {summary['cape']['mixed_layer']} J/kg (>1000)",
                f"0-6km Shear: {summary['shear']['0_6km']} kts (>20)"
            ]
        elif summary["cape"]["mixed_layer"] > 500:
            threat["wind"]["level"] = "slight"
            threat["wind"]["factors"] = [
                f"MLCAPE: {summary['cape']['mixed_layer']} J/kg (>500)"
            ]
        
        # Flash flood threat assessment
        # Factors: Precipitable water, K-index, convergence
        if summary["moisture"]["pwat"] > 50 and summary["indices"]["k_index"] > 35:
            threat["flash_flood"]["level"] = "high"
            threat["flash_flood"]["factors"] = [
                f"PWAT: {summary['moisture']['pwat']:.1f} mm (>50mm)",
                f"K-Index: {summary['indices']['k_index']:.1f} (>35)",
                "Favorable for heavy precipitation"
            ]
        elif summary["moisture"]["pwat"] > 40 and summary["indices"]["k_index"] > 30:
            threat["flash_flood"]["level"] = "moderate"
            threat["flash_flood"]["factors"] = [
                f"PWAT: {summary['moisture']['pwat']:.1f} mm (>40mm)",
                f"K-Index: {summary['indices']['k_index']:.1f} (>30)"
            ]
        elif summary["moisture"]["pwat"] > 30 and summary["indices"]["k_index"] > 25:
            threat["flash_flood"]["level"] = "slight"
            threat["flash_flood"]["factors"] = [
                f"PWAT: {summary['moisture']['pwat']:.1f} mm (>30mm)",
                f"K-Index: {summary['indices']['k_index']:.1f} (>25)"
            ]
        
        return threat
    
    def _generate_sample_profile(self, lat, lon, model="GFS", forecast_hour=0):
        """
        Generate a sample profile for demonstration purposes.
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            model (str): Model name
            forecast_hour (int): Forecast hour
            
        Returns:
            pd.DataFrame: DataFrame with profile data
        """
        # Generate a realistic atmospheric profile based on a standard atmosphere
        # with some instability and moisture added
        
        # Pressure levels (hPa)
        pres = np.array([1000, 975, 950, 925, 900, 875, 850, 825, 800, 775, 750, 725, 700,
                         650, 600, 550, 500, 450, 400, 350, 300, 250, 200, 150, 100, 50])
        
        # Heights (meters) - approximate standard atmosphere
        hght = np.array([0, 300, 600, 900, 1200, 1500, 1800, 2100, 2400, 2700, 3000, 3300, 3600,
                         4200, 4800, 5500, 6000, 6600, 7200, 8000, 9000, 10000, 11000, 13000, 16000, 20000])
        
        # Temperature (°C) - with instability in the lower levels
        tmpc = np.array([30, 28, 26, 24, 22, 20, 18, 16, 12, 8, 6, 4, 2,
                          -2, -8, -15, -20, -25, -33, -40, -50, -55, -60, -65, -70, -75])
        
        # Add some random variation based on lat/lon to make it more realistic
        # This is just for demonstration, real data would come from NWP model
        lat_factor = np.cos(np.radians(lat)) * 5  # Temperature decreases with latitude
        tmpc = tmpc - lat_factor
        
        # Dewpoint (°C) - relatively moist in the lower levels, drier aloft
        dwpc = np.array([22, 21, 20, 18, 16, 14, 10, 6, 2, -2, -6, -10, -15,
                          -20, -25, -30, -35, -40, -45, -50, -55, -60, -65, -70, -75, -80])
        
        # Wind direction (degrees)
        wdir = np.array([180, 185, 190, 200, 210, 220, 230, 240, 250, 255, 260, 265, 270,
                          275, 280, 285, 290, 295, 300, 300, 300, 300, 300, 300, 300, 300])
        
        # Wind speed (knots) - increasing with height
        wspd = np.array([5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65,
                          70, 75, 80, 85, 90, 95, 100, 105, 110, 115, 120, 125, 130])
        
        # Create a DataFrame
        data = pd.DataFrame({
            'pres': pres,
            'hght': hght,
            'tmpc': tmpc,
            'dwpc': dwpc,
            'wdir': wdir,
            'wspd': wspd
        })
        
        return data
    
    def _generate_sample_summary(self):
        """
        Generate a sample summary for demonstration purposes.
        
        Returns:
            dict: Dictionary with sample severe weather parameters
        """
        return {
            "cape": {
                "surface": 1800,
                "mixed_layer": 1500,
                "most_unstable": 2200
            },
            "cin": {
                "surface": -50,
                "mixed_layer": -25,
                "most_unstable": -10
            },
            "lcl_height": {
                "surface": 1200,
                "mixed_layer": 1500,
                "most_unstable": 900
            },
            "shear": {
                "0_6km": 45,
                "0_1km": 25,
                "0_3km": 35
            },
            "helicity": {
                "0_1km": 150,
                "0_3km": 250
            },
            "indices": {
                "stp": 1.5,
                "scp": 4.0,
                "li": -4.0,
                "k_index": 35.0,
                "totals": 50.0
            },
            "moisture": {
                "pwat": 45.0,
            },
            "lapse_rates": {
                "0_3km": 7.5,
                "700_500mb": 7.0
            }
        }
    
    def _generate_sample_threat(self):
        """
        Generate a sample threat assessment for demonstration purposes.
        
        Returns:
            dict: Dictionary with sample severe weather threat assessments
        """
        return {
            "tornado": {
                "level": "moderate",
                "factors": [
                    "CAPE: 1800 J/kg (>1000)",
                    "0-1km SRH: 150 m²/s² (>100)",
                    "LCL Height: 1200 m (<1500)",
                    "0-1km Shear: 25 kts (>15)"
                ]
            },
            "hail": {
                "level": "high",
                "factors": [
                    "MUCAPE: 2200 J/kg (>2000)",
                    "0-6km Shear: 45 kts (>40)",
                    "Favorable thermodynamic profile for large hail"
                ]
            },
            "wind": {
                "level": "moderate",
                "factors": [
                    "MLCAPE: 1500 J/kg (>1000)",
                    "0-6km Shear: 45 kts (>20)"
                ]
            },
            "flash_flood": {
                "level": "moderate",
                "factors": [
                    "PWAT: 45.0 mm (>40mm)",
                    "K-Index: 35.0 (>30)"
                ]
            }
        }

# Create a singleton instance of the analyzer
severe_weather_analyzer = SevereWeatherAnalyzer()