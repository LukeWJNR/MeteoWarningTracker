"""
Utility for advanced meteorological analysis using SHARPpy
This module provides comprehensive severe weather parameter calculations
"""
import os
import logging
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import json
from datetime import datetime, timedelta

# Import SHARPpy components
try:
    import sharppy
    import sharppy.sharptab as tab
    from sharppy.sharptab import profile, params, thermo, winds, utils, interp
    SHARPPY_AVAILABLE = True
except ImportError as e:
    logging.warning(f"SHARPpy not fully available: {e}")
    SHARPPY_AVAILABLE = False

logger = logging.getLogger(__name__)

class SevereWeatherAnalyzer:
    """
    Class for analyzing severe weather parameters using SHARPpy
    """
    
    def __init__(self):
        """Initialize the severe weather analyzer"""
        self.latest_profile = None
        self.latest_analysis = None
        self.check_availability()
    
    def check_availability(self):
        """Check if SHARPpy is fully available"""
        if not SHARPPY_AVAILABLE:
            logger.warning("SHARPpy is not fully available. Some functionality will be limited.")
            return False
        return True
    
    def create_profile_from_model_data(self, pres, hght, tmpc, dwpc, wspd, wdir, lat, lon, date=None):
        """
        Create a SHARPpy profile from model data
        
        Args:
            pres (list): Pressure levels in hPa
            hght (list): Heights in meters
            tmpc (list): Temperature in Celsius
            dwpc (list): Dew point in Celsius
            wspd (list): Wind speed in knots
            wdir (list): Wind direction in degrees
            lat (float): Latitude
            lon (float): Longitude
            date (datetime): Date/time of the profile
            
        Returns:
            profile.Profile: SHARPpy profile object or None if failed
        """
        if not SHARPPY_AVAILABLE:
            logger.error("SHARPpy is not available")
            return None
        
        try:
            if date is None:
                date = datetime.utcnow()
                
            # Create the profile object
            prof = profile.create_profile(
                profile='default',
                pres=pres,
                hght=hght,
                tmpc=tmpc,
                dwpc=dwpc,
                wspd=wspd,
                wdir=wdir,
                missing=-9999,
                date=date,
                latitude=lat,
                longitude=lon
            )
            
            self.latest_profile = prof
            return prof
            
        except Exception as e:
            logger.error(f"Error creating SHARPpy profile: {e}")
            return None
    
    def create_profile_from_sounding(self, sounding_file):
        """
        Create a SHARPpy profile from a sounding file
        
        Args:
            sounding_file (str): Path to the sounding file
            
        Returns:
            profile.Profile: SHARPpy profile object or None if failed
        """
        if not SHARPPY_AVAILABLE:
            logger.error("SHARPpy is not available")
            return None
        
        try:
            # Parse the sounding file and create a profile
            prof = profile.read_sounding(sounding_file)
            self.latest_profile = prof
            return prof
            
        except Exception as e:
            logger.error(f"Error reading sounding file: {e}")
            return None
    
    def calculate_parameters(self, prof=None):
        """
        Calculate severe weather parameters using a SHARPpy profile
        
        Args:
            prof (profile.Profile): SHARPpy profile object or None to use latest
            
        Returns:
            dict: Dictionary of calculated parameters
        """
        if not SHARPPY_AVAILABLE:
            logger.error("SHARPpy is not available")
            return {}
        
        try:
            if prof is None:
                prof = self.latest_profile
                
            if prof is None:
                logger.error("No profile available for parameter calculation")
                return {}
            
            # Initialize the output dictionary
            param_dict = {}
            
            # CAPE parameters
            param_dict['sfcpcl'] = params.parcelx(prof, flag=1)  # Surface parcel
            param_dict['fcstpcl'] = params.parcelx(prof, flag=2)  # Forecast parcel
            param_dict['mupcl'] = params.parcelx(prof, flag=3)  # Most unstable parcel
            param_dict['mlpcl'] = params.parcelx(prof, flag=4)  # Mixed layer parcel
            
            # Extract CAPE/CIN values
            param_dict['sfcape'] = param_dict['sfcpcl'].bplus  # Surface-based CAPE
            param_dict['sfcin'] = param_dict['sfcpcl'].bminus  # Surface-based CIN
            param_dict['mucape'] = param_dict['mupcl'].bplus  # Most unstable CAPE
            param_dict['mucin'] = param_dict['mupcl'].bminus  # Most unstable CIN
            param_dict['mlcape'] = param_dict['mlpcl'].bplus  # Mixed-layer CAPE
            param_dict['mlcin'] = param_dict['mlpcl'].bminus  # Mixed-layer CIN
            
            # LCL and LFC heights
            param_dict['sfclcl'] = param_dict['sfcpcl'].lclhght  # Surface LCL height
            param_dict['sflcl_mb'] = param_dict['sfcpcl'].lclpres  # Surface LCL pressure
            param_dict['mulcl'] = param_dict['mupcl'].lclhght  # Most unstable LCL height
            param_dict['mllcl'] = param_dict['mlpcl'].lclhght  # Mixed-layer LCL height
            
            param_dict['sflfc'] = param_dict['sfcpcl'].lfchght  # Surface LFC height
            param_dict['sflfc_mb'] = param_dict['sfcpcl'].lfcpres  # Surface LFC pressure
            param_dict['mlfcl'] = param_dict['mlpcl'].lfchght  # Mixed-layer LFC height
            param_dict['mulfc'] = param_dict['mupcl'].lfchght  # Most unstable LFC height
            
            # Equilibrium level
            param_dict['sfeql'] = param_dict['sfcpcl'].elhght  # Surface EL height
            param_dict['mueql'] = param_dict['mupcl'].elhght  # Most unstable EL height
            param_dict['mleql'] = param_dict['mlpcl'].elhght  # Mixed-layer EL height
            
            # 0-6 km shear
            param_dict['sfc_6km_shear'] = winds.wind_shear(prof, pbot=prof.pres[prof.sfc], ptop=prof.pres[prof.sfc] - 600.)
            
            # 0-1 km shear
            param_dict['sfc_1km_shear'] = winds.wind_shear(prof, pbot=prof.pres[prof.sfc], ptop=prof.pres[prof.sfc] - 100.)
            
            # 0-3 km shear
            param_dict['sfc_3km_shear'] = winds.wind_shear(prof, pbot=prof.pres[prof.sfc], ptop=prof.pres[prof.sfc] - 300.)
            
            # Storm-relative helicity (SRH)
            param_dict['srh1km'] = winds.helicity(prof, 0, 1000., stu=prof.srwind[0], stv=prof.srwind[1])[0]
            param_dict['srh3km'] = winds.helicity(prof, 0, 3000., stu=prof.srwind[0], stv=prof.srwind[1])[0]
            
            # Bulk Richardson Number (BRN)
            param_dict['brn'] = params.bulk_rich(prof)
            
            # Significant tornado parameter (STP) and supercell composite parameter (SCP)
            param_dict['stp'] = params.stp_cin(prof)
            param_dict['scp'] = params.scp(prof)
            
            # Lifted index
            param_dict['li'] = params.li(prof, pbot=prof.pres[prof.sfc])
            
            # K-index 
            param_dict['k_index'] = params.k_index(prof)
            
            # Total totals
            param_dict['totals'] = params.t_totals(prof)
            
            # Precipitable water
            param_dict['pwat'] = params.precip_water(prof)
            
            # Lapse rates
            param_dict['lr_0_3km'] = params.lapse_rate(prof, 0, 3000.)
            param_dict['lr_700_500'] = params.lapse_rate_700_500(prof)
            
            # PVU levels (if data is available)
            # Note: PVU level calculation is more complex and may require additional data
            
            # Store the latest analysis
            self.latest_analysis = param_dict
            
            return param_dict
            
        except Exception as e:
            logger.error(f"Error calculating parameters: {e}")
            return {}
    
    def generate_skewt_plot(self, prof=None, width=800, height=600):
        """
        Generate a SkewT plot using SHARPpy
        
        Args:
            prof (profile.Profile): SHARPpy profile object or None to use latest
            width (int): Width of the plot in pixels
            height (int): Height of the plot in pixels
            
        Returns:
            BytesIO: Image data buffer or None if failed
        """
        if not SHARPPY_AVAILABLE:
            logger.error("SHARPpy is not available")
            return None
        
        try:
            if prof is None:
                prof = self.latest_profile
                
            if prof is None:
                logger.error("No profile available for SkewT plot")
                return None
            
            # Create a figure
            fig = plt.figure(figsize=(width/100, height/100), dpi=100)
            
            # Create SkewT diagram
            skew = tab.SkewT(fig, rotation=45)
            
            # Plot temperature and dew point profiles
            skew.plot_profile(prof)
            
            # Plot wind barbs
            skew.plot_wind(prof)
            
            # Plot parcel trace
            skew.plot_parcel(prof, 'surface')
            
            # Add title
            plt.title(f"SkewT Plot - {prof.date.strftime('%Y-%m-%d %H:%M UTC')}")
            
            # Save plot to bytes buffer
            buf = BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight')
            buf.seek(0)
            plt.close(fig)
            
            return buf
            
        except Exception as e:
            logger.error(f"Error generating SkewT plot: {e}")
            return None
    
    def convert_profile_to_json(self, prof=None):
        """
        Convert a SHARPpy profile to JSON format
        
        Args:
            prof (profile.Profile): SHARPpy profile object or None to use latest
            
        Returns:
            str: JSON string or None if failed
        """
        if not SHARPPY_AVAILABLE:
            logger.error("SHARPpy is not available")
            return None
        
        try:
            if prof is None:
                prof = self.latest_profile
                
            if prof is None:
                logger.error("No profile available for JSON conversion")
                return None
            
            # Create profile data dictionary
            profile_data = {
                "pres": prof.pres.tolist(),
                "hght": prof.hght.tolist(),
                "tmpc": prof.tmpc.tolist(),
                "dwpc": prof.dwpc.tolist(),
                "wspd": prof.wspd.tolist(),
                "wdir": prof.wdir.tolist(),
                "metadata": {
                    "latitude": prof.latitude,
                    "longitude": prof.longitude,
                    "date": prof.date.strftime("%Y-%m-%d %H:%M:%S"),
                }
            }
            
            # Convert to JSON string
            return json.dumps(profile_data)
            
        except Exception as e:
            logger.error(f"Error converting profile to JSON: {e}")
            return None
    
    def extract_severe_weather_summary(self, analysis=None):
        """
        Extract a summary of severe weather parameters for display
        
        Args:
            analysis (dict): Analysis dictionary or None to use latest
            
        Returns:
            dict: Summary dictionary with human-readable values
        """
        try:
            if analysis is None:
                analysis = self.latest_analysis
                
            if analysis is None or not analysis:
                logger.error("No analysis available for summary extraction")
                return {}
            
            # Create summary dictionary
            summary = {
                "cape": {
                    "surface": int(analysis.get('sfcape', 0)),
                    "mixed_layer": int(analysis.get('mlcape', 0)),
                    "most_unstable": int(analysis.get('mucape', 0))
                },
                "cin": {
                    "surface": int(analysis.get('sfcin', 0)),
                    "mixed_layer": int(analysis.get('mlcin', 0)),
                    "most_unstable": int(analysis.get('mucin', 0))
                },
                "lcl_height": {
                    "surface": int(analysis.get('sfclcl', 0)),
                    "mixed_layer": int(analysis.get('mllcl', 0)),
                    "most_unstable": int(analysis.get('mulcl', 0))
                },
                "shear": {
                    "0_1km": round(analysis.get('sfc_1km_shear', 0), 1),
                    "0_3km": round(analysis.get('sfc_3km_shear', 0), 1),
                    "0_6km": round(analysis.get('sfc_6km_shear', 0), 1)
                },
                "helicity": {
                    "0_1km": int(analysis.get('srh1km', 0)),
                    "0_3km": int(analysis.get('srh3km', 0))
                },
                "indices": {
                    "stp": round(analysis.get('stp', 0), 2),
                    "scp": round(analysis.get('scp', 0), 2),
                    "li": round(analysis.get('li', 0), 1),
                    "k_index": round(analysis.get('k_index', 0), 1),
                    "totals": round(analysis.get('totals', 0), 1)
                },
                "moisture": {
                    "pwat": round(analysis.get('pwat', 0), 2)
                },
                "lapse_rates": {
                    "0_3km": round(analysis.get('lr_0_3km', 0), 1),
                    "700_500mb": round(analysis.get('lr_700_500', 0), 1)
                }
            }
            
            return summary
            
        except Exception as e:
            logger.error(f"Error extracting severe weather summary: {e}")
            return {}
    
    def get_severe_weather_threat(self, analysis=None):
        """
        Assess the severe weather threat based on parameters
        
        Args:
            analysis (dict): Analysis dictionary or None to use latest
            
        Returns:
            dict: Threat assessment with likelihood for different hazards
        """
        try:
            if analysis is None:
                analysis = self.latest_analysis
                
            if analysis is None or not analysis:
                logger.error("No analysis available for threat assessment")
                return {}
            
            # Initialize threat dictionary
            threat = {
                "tornado": {
                    "level": "none",
                    "factors": []
                },
                "hail": {
                    "level": "none",
                    "factors": []
                },
                "wind": {
                    "level": "none",
                    "factors": []
                },
                "flash_flood": {
                    "level": "none",
                    "factors": []
                }
            }
            
            # Assess tornado threat
            stp = analysis.get('stp', 0)
            srh3km = analysis.get('srh3km', 0)
            mlcape = analysis.get('mlcape', 0)
            lr_0_3km = analysis.get('lr_0_3km', 0)
            sfc_6km_shear = analysis.get('sfc_6km_shear', 0)
            
            if stp >= 1:
                threat["tornado"]["level"] = "high"
                threat["tornado"]["factors"].append(f"STP: {stp:.2f}")
            elif stp >= 0.5:
                threat["tornado"]["level"] = "moderate"
                threat["tornado"]["factors"].append(f"STP: {stp:.2f}")
            elif srh3km > 150 and mlcape > 1000:
                threat["tornado"]["level"] = "slight"
                threat["tornado"]["factors"].append(f"SRH: {srh3km} m²/s²")
                threat["tornado"]["factors"].append(f"MLCAPE: {mlcape} J/kg")
            
            # Assess hail threat
            mucape = analysis.get('mucape', 0)
            pwat = analysis.get('pwat', 0)
            
            if mucape > 2500 and sfc_6km_shear > 40:
                threat["hail"]["level"] = "high"
                threat["hail"]["factors"].append(f"MUCAPE: {mucape} J/kg")
                threat["hail"]["factors"].append(f"Deep shear: {sfc_6km_shear} kt")
            elif mucape > 1500 and sfc_6km_shear > 30:
                threat["hail"]["level"] = "moderate"
                threat["hail"]["factors"].append(f"MUCAPE: {mucape} J/kg")
                threat["hail"]["factors"].append(f"Deep shear: {sfc_6km_shear} kt")
            elif mucape > 1000:
                threat["hail"]["level"] = "slight"
                threat["hail"]["factors"].append(f"MUCAPE: {mucape} J/kg")
            
            # Assess wind threat
            scp = analysis.get('scp', 0)
            mucin = analysis.get('mucin', 0)
            
            if mucape > 2000 and mucin > -50:
                threat["wind"]["level"] = "high"
                threat["wind"]["factors"].append(f"MUCAPE: {mucape} J/kg")
                threat["wind"]["factors"].append(f"MUCIN: {mucin} J/kg")
            elif mucape > 1000 and sfc_6km_shear > 30:
                threat["wind"]["level"] = "moderate"
                threat["wind"]["factors"].append(f"MUCAPE: {mucape} J/kg")
                threat["wind"]["factors"].append(f"Deep shear: {sfc_6km_shear} kt")
            elif mucape > 500:
                threat["wind"]["level"] = "slight"
                threat["wind"]["factors"].append(f"MUCAPE: {mucape} J/kg")
            
            # Assess flash flood threat
            if pwat > 50 and mucape > 1000:
                threat["flash_flood"]["level"] = "high"
                threat["flash_flood"]["factors"].append(f"PWAT: {pwat} mm")
                threat["flash_flood"]["factors"].append(f"MUCAPE: {mucape} J/kg")
            elif pwat > 35:
                threat["flash_flood"]["level"] = "moderate"
                threat["flash_flood"]["factors"].append(f"PWAT: {pwat} mm")
            elif pwat > 25:
                threat["flash_flood"]["level"] = "slight"
                threat["flash_flood"]["factors"].append(f"PWAT: {pwat} mm")
            
            return threat
            
        except Exception as e:
            logger.error(f"Error assessing severe weather threat: {e}")
            return {}
    
    def load_model_data_from_ncep(self, lat, lon, model="GFS"):
        """
        Load model data from NCEP for a specific location
        This is a placeholder - actual implementation would use API or direct data access
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            model (str): Model name (GFS, NAM, etc.)
            
        Returns:
            bool: Success status
        """
        try:
            # In a real implementation, this would connect to NCEP data
            # For now, we'll create a sample profile
            
            logger.info(f"Loading model data from NCEP {model} for {lat}, {lon}")
            
            # Create sample pressure levels and data
            pres = np.array([1000, 925, 850, 700, 500, 300, 250, 200, 150, 100, 50])
            hght = np.array([111, 789, 1500, 3000, 5600, 9300, 10500, 12000, 13500, 16000, 20000])
            tmpc = np.array([25, 20, 15, 5, -15, -40, -50, -55, -60, -70, -65])
            dwpc = np.array([18, 15, 10, 0, -20, -45, -55, -60, -65, -75, -80])
            wspd = np.array([5, 7, 10, 15, 25, 35, 45, 40, 30, 25, 15])
            wdir = np.array([180, 190, 210, 230, 250, 270, 280, 290, 300, 320, 340])
            
            # Create a profile
            prof = self.create_profile_from_model_data(
                pres=pres,
                hght=hght,
                tmpc=tmpc,
                dwpc=dwpc,
                wspd=wspd,
                wdir=wdir,
                lat=lat,
                lon=lon,
                date=datetime.utcnow()
            )
            
            if prof:
                # Calculate parameters
                self.calculate_parameters(prof)
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error loading model data from NCEP: {e}")
            return False

# Initialize as a singleton
severe_weather_analyzer = SevereWeatherAnalyzer()