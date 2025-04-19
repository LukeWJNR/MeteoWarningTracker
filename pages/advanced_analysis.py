"""
Advanced Meteorological Analysis - Calculate and visualize important severe weather parameters
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import folium_static
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import io
from metpy.calc import cape_cin, lcl, dewpoint_from_relative_humidity
from metpy.units import units
from meteostat import Point, Hourly

# Configure page
st.set_page_config(page_title="Advanced Meteorological Analysis", page_icon="🔬", layout="wide")

# Title and description
st.title("🔬 Advanced Meteorological Analysis")
st.markdown("""
This page provides advanced meteorological calculations and analysis that are critical 
for understanding severe weather potential. Calculate parameters like CAPE, CIN, and LCL
to assess thunderstorm and severe weather risk.
""")

# Access session state from main app
if 'lat' not in st.session_state:
    st.session_state.lat = 40.7128  # New York City
if 'lon' not in st.session_state:
    st.session_state.lon = -74.0060
if 'location' not in st.session_state:
    st.session_state.location = "New York, NY"

# Sidebar options
st.sidebar.header("Location")
st.sidebar.write(f"**Current Location:** {st.session_state.location}")
st.sidebar.write(f"**Coordinates:** {st.session_state.lat:.4f}, {st.session_state.lon:.4f}")

use_custom_sounding = st.sidebar.checkbox("Use Custom Sounding Data", value=False)

# Analysis options
st.sidebar.header("Analysis Options")
analysis_type = st.sidebar.selectbox(
    "Analysis Type",
    ["Thermodynamic", "Convective Parameters", "Wind Shear", "Atmospheric Moisture"]
)

if use_custom_sounding:
    st.sidebar.subheader("Custom Sounding Data")
    st.sidebar.markdown("Enter atmospheric profile data (pressure, temperature, dewpoint)")
    
    # Allow custom input of sounding data (simplified for user interface)
    pressure_input = st.sidebar.text_area(
        "Pressure Levels (hPa)",
        "1000\n925\n850\n700\n500\n300"
    )
    
    temperature_input = st.sidebar.text_area(
        "Temperature (°C)",
        "25\n20\n15\n5\n-15\n-40"
    )
    
    dewpoint_input = st.sidebar.text_area(
        "Dewpoint (°C)",
        "20\n15\n10\n0\n-20\n-50"
    )

# Main content
col1, col2 = st.columns([3, 2])

with col1:
    # Fetch real atmospheric data from Meteostat
    @st.cache_data(ttl=3600)  # Cache for 1 hour
    def fetch_atmospheric_data(lat, lon):
        try:
            # Create Point for the location
            location = Point(lat, lon)
            
            # Get recent hourly data
            now = datetime.now()
            start = now - timedelta(hours=24)
            end = now
            
            # Fetch data
            data = Hourly(location, start, end)
            df = data.fetch()
            
            if not df.empty:
                # Get the most recent data point with complete information
                df = df.dropna(subset=['temp', 'rhum', 'pres'])
                if not df.empty:
                    return df.iloc[-1]
            
            return None
        except Exception as e:
            st.error(f"Error fetching atmospheric data: {str(e)}")
            return None
    
    # Function to get simplified atmospheric profile based on surface conditions
    def generate_profile_from_surface(surface_data):
        """
        Generate a simplified atmospheric profile based on surface measurements
        and standard atmospheric lapse rates.
        
        Args:
            surface_data: Pandas Series with surface measurements
            
        Returns:
            dict: Dictionary with pressure, temperature, and dewpoint profiles
        """
        # Standard pressure levels
        pressure_levels = np.array([1000, 925, 850, 700, 500, 300]) * units.hPa
        
        # Get surface values (or use defaults if not available)
        surface_temp = surface_data.get('temp', 20) * units.degC
        surface_rh = surface_data.get('rhum', 50) / 100
        surface_pressure = surface_data.get('pres', 1013.25) * units.hPa
        
        # Calculate surface dewpoint
        surface_dewpoint = dewpoint_from_relative_humidity(surface_temp, surface_rh)
        
        # Use simple lapse rates to estimate values at standard levels
        # Standard temperature lapse rate: ~6.5 °C/km
        # Standard dewpoint lapse rate: ~2 °C/km
        temperature_profile = []
        dewpoint_profile = []
        
        for p in pressure_levels:
            # Estimate height difference from surface using hypsometric equation (simplified)
            if p.magnitude >= surface_pressure.magnitude:
                # If the standard level is higher pressure than surface (below surface)
                height_diff = 0  # Just use surface values
            else:
                # Estimate height difference in meters
                height_diff = -8000 * np.log(p / surface_pressure)  # Simplified height calculation
            
            # Calculate temperature and dewpoint at this level
            # Note: Using magnitude values to avoid units complications
            temp_lapse = 6.5 * (height_diff / 1000)
            dewpoint_lapse = 2.0 * (height_diff / 1000)
            
            temp_at_level = surface_temp - temp_lapse * units.delta_degC
            dewpoint_at_level = surface_dewpoint - dewpoint_lapse * units.delta_degC
            
            temperature_profile.append(temp_at_level)
            dewpoint_profile.append(dewpoint_at_level)
        
        # Create profile dictionary with separate lists
        return {
            'pressure': pressure_levels,
            'temperature': temperature_profile,
            'dewpoint': dewpoint_profile
        }
    
    # Parse custom sounding data if provided
    def parse_custom_sounding():
        try:
            pressure = np.array([float(p) for p in pressure_input.strip().split('\n')]) * units.hPa
            temperature = np.array([float(t) for t in temperature_input.strip().split('\n')]) * units.degC
            dewpoint = np.array([float(d) for d in dewpoint_input.strip().split('\n')]) * units.degC
            
            # Check if all arrays have the same length
            if len(pressure) != len(temperature) or len(pressure) != len(dewpoint):
                st.error("All input arrays must have the same length. Please check your input data.")
                return None
            
            return {
                'pressure': pressure,
                'temperature': temperature,
                'dewpoint': dewpoint
            }
        except Exception as e:
            st.error(f"Error parsing sounding data: {str(e)}")
            return None
    
    # Get atmospheric data
    current_data = fetch_atmospheric_data(st.session_state.lat, st.session_state.lon)
    
    # Get sounding data
    if use_custom_sounding:
        sounding_data = parse_custom_sounding()
    else:
        if current_data is not None:
            sounding_data = generate_profile_from_surface(current_data)
            st.info("Using generated atmospheric profile based on current surface conditions")
        else:
            st.warning("Could not get current atmospheric data. Using sample profile.")
            # Sample profile as fallback
            sounding_data = {
                'pressure': np.array([1000, 925, 850, 700, 500, 300]) * units.hPa,
                'temperature': np.array([25, 20, 15, 5, -15, -40]) * units.degC,
                'dewpoint': np.array([20, 15, 10, 0, -20, -50]) * units.degC
            }
    
    # Display the analysis based on selection
    if analysis_type == "Thermodynamic":
        st.subheader("Thermodynamic Analysis")
        
        # Calculate LCL
        try:
            lcl_pressure, lcl_temperature = lcl(
                sounding_data['pressure'][0],
                sounding_data['temperature'][0],
                sounding_data['dewpoint'][0]
            )
            
            # Display LCL information
            st.markdown(f"""
            ### Lifted Condensation Level (LCL)
            - **Pressure:** {lcl_pressure.magnitude:.1f} hPa
            - **Temperature:** {lcl_temperature.to('degC').magnitude:.1f} °C
            - **Height (approx):** {((sounding_data['pressure'][0] - lcl_pressure) / units.hPa * 8).magnitude:.0f} meters
            """)
            
            st.markdown("""
            The Lifted Condensation Level (LCL) is the height at which a parcel of air becomes saturated when lifted adiabatically.
            It represents the approximate height of cloud base for surface-based convection.
            
            - **Lower LCL** (< 1000m): Higher relative humidity, more favorable for tornadoes
            - **Higher LCL** (> 2000m): Drier conditions, more favorable for dry microbursts
            """)
        except Exception as e:
            st.error(f"Error calculating LCL: {str(e)}")
        
        # Create Skew-T plot or simplified Temperature-Height plot
        try:
            # Create simplified temperature-pressure plot
            fig = go.Figure()
            
            # Convert to lists for plotting
            p_list = [p.magnitude for p in sounding_data['pressure']]
            t_list = [t.to('degC').magnitude for t in sounding_data['temperature']]
            td_list = [td.to('degC').magnitude for td in sounding_data['dewpoint']]
            
            # Temperature profile
            fig.add_trace(go.Scatter(
                x=t_list,
                y=p_list,
                mode='lines+markers',
                name='Temperature',
                line=dict(color='red', width=2)
            ))
            
            # Dewpoint profile
            fig.add_trace(go.Scatter(
                x=td_list,
                y=p_list,
                mode='lines+markers',
                name='Dewpoint',
                line=dict(color='blue', width=2)
            ))
            
            # Add LCL point
            fig.add_trace(go.Scatter(
                x=[lcl_temperature.to('degC').magnitude],
                y=[lcl_pressure.magnitude],
                mode='markers',
                marker=dict(size=10, color='purple'),
                name='LCL'
            ))
            
            # Update layout
            fig.update_layout(
                title='Temperature-Pressure Profile',
                xaxis_title='Temperature (°C)',
                yaxis_title='Pressure (hPa)',
                yaxis=dict(
                    autorange='reversed',  # Reverse y-axis to have pressure decrease upward
                ),
                height=600,
                hovermode='closest'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error creating plot: {str(e)}")
    
    elif analysis_type == "Convective Parameters":
        st.subheader("Convective Parameters Analysis")
        
        # Calculate CAPE/CIN
        try:
            # For a simple parcel profile, we'll use a simple lifted parcel
            # In a real application, you would compute a proper parcel profile
            parcel_profile = sounding_data['temperature']  # This is a simplification
            
            cape, cin = cape_cin(
                sounding_data['pressure'],
                sounding_data['temperature'],
                sounding_data['dewpoint'],
                parcel_profile
            )
            
            # Display CAPE/CIN information
            st.markdown(f"""
            ### Convective Available Potential Energy (CAPE)
            - **CAPE Value:** {cape.magnitude:.0f} J/kg
            - **Convective Inhibition (CIN):** {cin.magnitude:.0f} J/kg
            """)
            
            # CAPE interpretation
            if cape.magnitude < 300:
                cape_text = "Minimal convective potential"
                cape_color = "green"
            elif cape.magnitude < 1000:
                cape_text = "Marginal convective potential"
                cape_color = "blue"
            elif cape.magnitude < 2000:
                cape_text = "Moderate convective potential"
                cape_color = "orange"
            else:
                cape_text = "Strong convective potential"
                cape_color = "red"
            
            # CIN interpretation
            if abs(cin.magnitude) < 50:
                cin_text = "Minimal inhibition, convection easily triggered"
                cin_color = "green"
            elif abs(cin.magnitude) < 100:
                cin_text = "Moderate inhibition, triggers needed for convection"
                cin_color = "orange"
            else:
                cin_text = "Strong inhibition, significant trigger needed"
                cin_color = "red"
            
            # Display interpretation
            st.markdown(f"""
            <div style="background-color: {cape_color}10; padding: 10px; margin: 10px 0; border-left: 5px solid {cape_color};">
                <p>CAPE Interpretation: <strong>{cape_text}</strong></p>
                <ul>
                    <li>CAPE < 300 J/kg: Insufficient for significant thunderstorms</li>
                    <li>300-1000 J/kg: Marginally unstable; weak thunderstorms possible</li>
                    <li>1000-2000 J/kg: Moderately unstable; thunderstorms likely</li>
                    <li>> 2000 J/kg: Very unstable; strong to severe thunderstorms possible</li>
                </ul>
            </div>
            
            <div style="background-color: {cin_color}10; padding: 10px; margin: 10px 0; border-left: 5px solid {cin_color};">
                <p>CIN Interpretation: <strong>{cin_text}</strong></p>
                <ul>
                    <li>CIN > -50 J/kg: Weak cap; convection easily initiated</li>
                    <li>-50 to -100 J/kg: Moderate cap; convection needs forcing</li>
                    <li>< -100 J/kg: Strong cap; significant forcing needed</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
            # Severe weather potential assessment
            if cape.magnitude > 1000 and abs(cin.magnitude) < 100:
                st.markdown("""
                <div style="background-color: #ff000010; padding: 10px; margin: 10px 0; border-left: 5px solid red;">
                    <h3 style="color: red;">⚠️ Severe Weather Potential</h3>
                    <p>Atmospheric conditions indicate potential for thunderstorm development if triggering mechanisms are present.</p>
                    <p>Monitor for additional factors like:</p>
                    <ul>
                        <li>Wind shear (for storm organization)</li>
                        <li>Lifting mechanisms (fronts, outflow boundaries)</li>
                        <li>Moisture convergence</li>
                    </ul>
                </div>
                """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Error calculating CAPE/CIN: {str(e)}")
    
    elif analysis_type == "Wind Shear":
        st.subheader("Wind Shear Analysis")
        
        st.info("Wind shear analysis requires wind data (speed and direction) at multiple levels. This simplified version uses estimated values.")
        
        # In a real application, you would use actual wind data
        # Here, we'll use sample wind data for demonstration
        wind_levels = [1000, 925, 850, 700, 500, 300]  # hPa
        wind_speeds = [10, 15, 25, 35, 50, 70]  # knots
        wind_dirs = [150, 170, 190, 210, 230, 250]  # degrees
        
        # Create wind profile dataframe
        wind_df = pd.DataFrame({
            'Pressure (hPa)': wind_levels,
            'Speed (knots)': wind_speeds,
            'Direction (°)': wind_dirs
        })
        
        # Display wind profile table
        st.write("**Wind Profile**")
        st.dataframe(wind_df)
        
        # Calculate bulk shear
        sfc_500mb_shear = 45  # knots, sample value
        sfc_6km_shear = 40  # knots, sample value
        
        # Display bulk shear information
        st.markdown(f"""
        ### Bulk Wind Shear
        - **Surface to 500mb Shear:** {sfc_500mb_shear} knots
        - **Surface to 6km Shear:** {sfc_6km_shear} knots
        """)
        
        # Storm type interpretation based on shear
        if sfc_6km_shear < 20:
            shear_text = "Single-cell thunderstorms or pulse storms"
            shear_color = "green"
        elif sfc_6km_shear < 40:
            shear_text = "Multi-cell thunderstorms and squall lines"
            shear_color = "orange"
        else:
            shear_text = "Supercell thunderstorms possible"
            shear_color = "red"
        
        st.markdown(f"""
        <div style="background-color: {shear_color}10; padding: 10px; margin: 10px 0; border-left: 5px solid {shear_color};">
            <p>Shear Interpretation: <strong>{shear_text}</strong></p>
            <ul>
                <li>0-20 knots: Minimal shear; short-lived, pulse storms</li>
                <li>20-40 knots: Moderate shear; organized multi-cell storms</li>
                <li>> 40 knots: Strong shear; supercell potential</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        # Create hodograph (wind direction/speed with height)
        try:
            # Calculate u and v components
            u = [-speed * np.sin(np.radians(direction)) for speed, direction in zip(wind_speeds, wind_dirs)]
            v = [-speed * np.cos(np.radians(direction)) for speed, direction in zip(wind_speeds, wind_dirs)]
            
            # Create hodograph
            fig = go.Figure()
            
            # Add hodograph trace
            fig.add_trace(go.Scatter(
                x=u,
                y=v,
                mode='lines+markers+text',
                marker=dict(
                    size=10,
                    color=wind_levels,
                    colorscale='Jet',
                    colorbar=dict(title='Pressure (hPa)'),
                    cmin=300,
                    cmax=1000
                ),
                text=[f"{p} hPa" for p in wind_levels],
                textposition="top center",
                line=dict(width=2)
            ))
            
            # Add origin
            fig.add_trace(go.Scatter(
                x=[0],
                y=[0],
                mode='markers',
                marker=dict(size=10, color='black'),
                showlegend=False
            ))
            
            # Update layout
            fig.update_layout(
                title='Hodograph',
                xaxis_title='U-Component (knots)',
                yaxis_title='V-Component (knots)',
                xaxis=dict(
                    range=[-80, 80],
                    zeroline=True,
                    zerolinewidth=1,
                    zerolinecolor='black'
                ),
                yaxis=dict(
                    range=[-80, 80],
                    zeroline=True,
                    zerolinewidth=1,
                    zerolinecolor='black',
                    scaleanchor="x",
                    scaleratio=1
                ),
                height=600,
                hovermode='closest'
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error creating hodograph: {str(e)}")
    
    elif analysis_type == "Atmospheric Moisture":
        st.subheader("Atmospheric Moisture Analysis")
        
        # Calculate precipitable water
        try:
            # In a real application, you would integrate the moisture through the column
            # Here we'll use a simplified approach
            pw = 1.25  # inches, sample value
            
            # Display precipitable water information
            st.markdown(f"""
            ### Precipitable Water
            - **Precipitable Water Value:** {pw:.2f} inches
            - **Climatological Normal:** 1.00 inches
            - **Percent of Normal:** {(pw / 1.0 * 100):.0f}%
            """)
            
            # PW interpretation
            if pw < 1.0:
                pw_text = "Below normal atmospheric moisture"
                pw_color = "blue"
            elif pw < 1.5:
                pw_text = "Near normal atmospheric moisture"
                pw_color = "green"
            elif pw < 2.0:
                pw_text = "Above normal atmospheric moisture"
                pw_color = "orange"
            else:
                pw_text = "Significantly elevated atmospheric moisture"
                pw_color = "red"
            
            st.markdown(f"""
            <div style="background-color: {pw_color}10; padding: 10px; margin: 10px 0; border-left: 5px solid {pw_color};">
                <p>Precipitable Water Interpretation: <strong>{pw_text}</strong></p>
                <ul>
                    <li>< 1.0 inch: Dry air mass, limited precipitation potential</li>
                    <li>1.0-1.5 inches: Moderate moisture, normal precipitation potential</li>
                    <li>1.5-2.0 inches: High moisture, enhanced precipitation potential</li>
                    <li>> 2.0 inches: Very high moisture, heavy precipitation potential</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
            # Calculate relative humidity profile
            rh_profile = []
            for temp, dewpoint in zip(sounding_data['temperature'], sounding_data['dewpoint']):
                # Convert to celsius for calculation
                t_c = temp.to('degC').magnitude
                td_c = dewpoint.to('degC').magnitude
                
                # Simple RH calculation
                rh = 100 - 5 * (t_c - td_c)  # Simplified approximation
                rh = max(0, min(100, rh))  # Clamp between 0-100%
                rh_profile.append(rh)
            
            # Create relative humidity profile plot
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=rh_profile,
                y=[p.magnitude for p in sounding_data['pressure']],
                mode='lines+markers',
                line=dict(color='blue', width=2),
                name='Relative Humidity'
            ))
            
            # Update layout
            fig.update_layout(
                title='Relative Humidity Profile',
                xaxis_title='Relative Humidity (%)',
                yaxis_title='Pressure (hPa)',
                yaxis=dict(
                    autorange='reversed'  # Reverse y-axis to have pressure decrease upward
                ),
                height=600,
                hovermode='closest'
            )
            
            # Add reference lines
            fig.add_shape(
                type="line",
                x0=70, y0=200,
                x1=70, y1=1050,
                line=dict(color="red", width=2, dash="dash"),
            )
            
            # Add annotation
            fig.add_annotation(
                x=70, y=200,
                text="70% RH (Cloudy)",
                showarrow=True,
                arrowhead=1
            )
            
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Error analyzing atmospheric moisture: {str(e)}")

with col2:
    st.subheader("Meteorological Parameters")
    
    # Display current surface conditions if available
    if current_data is not None:
        st.markdown("### Current Surface Conditions")
        
        # Create metrics in a grid
        metric_col1, metric_col2 = st.columns(2)
        
        with metric_col1:
            if 'temp' in current_data:
                st.metric("Temperature", f"{current_data['temp']:.1f}°C")
            if 'rhum' in current_data:
                st.metric("Relative Humidity", f"{current_data['rhum']:.0f}%")
            if 'pres' in current_data:
                st.metric("Pressure", f"{current_data['pres']:.1f} hPa")
        
        with metric_col2:
            if 'temp' in current_data and 'rhum' in current_data:
                # Calculate dewpoint from temperature and RH
                t = current_data['temp'] * units.degC
                rh = current_data['rhum'] / 100
                td = dewpoint_from_relative_humidity(t, rh)
                st.metric("Dewpoint", f"{td.magnitude:.1f}°C")
            
            if 'wspd' in current_data:
                st.metric("Wind Speed", f"{current_data['wspd']:.1f} km/h")
            if 'wdir' in current_data:
                st.metric("Wind Direction", f"{current_data['wdir']:.0f}°")
    
    # Display sounding data table
    st.markdown("### Atmospheric Profile")
    
    # Create and display table
    profile_df = pd.DataFrame({
        'Pressure (hPa)': [p.magnitude for p in sounding_data['pressure']],
        'Temperature (°C)': [t.to('degC').magnitude for t in sounding_data['temperature']],
        'Dewpoint (°C)': [d.to('degC').magnitude for d in sounding_data['dewpoint']]
    })
    
    st.dataframe(profile_df)
    
    # Interpretation guide
    st.markdown("### Parameter Interpretation Guide")
    
    with st.expander("CAPE (Convective Available Potential Energy)"):
        st.markdown("""
        CAPE measures the amount of energy available for convection. It represents the positive buoyancy of an air parcel and is an indicator of atmospheric instability.
        
        - **< 300 J/kg**: Marginally unstable, weak updrafts
        - **300-1000 J/kg**: Moderately unstable, strong thunderstorms possible
        - **1000-2500 J/kg**: Very unstable, severe thunderstorms likely
        - **> 2500 J/kg**: Extremely unstable, violent thunderstorms possible
        """)
    
    with st.expander("CIN (Convective Inhibition)"):
        st.markdown("""
        CIN represents the amount of energy needed to overcome the negatively buoyant layer before free convection can occur.
        
        - **> -50 J/kg**: Minimal inhibition, convection easily initiated
        - **-50 to -200 J/kg**: Moderate inhibition, convection needs forcing mechanism
        - **< -200 J/kg**: Strong inhibition, significant forcing needed
        """)
    
    with st.expander("LCL (Lifted Condensation Level)"):
        st.markdown("""
        The LCL is the height at which a parcel of air becomes saturated when lifted adiabatically. It approximately represents the cloud base height.
        
        - **< 1000m**: Low cloud bases, higher humidity, more favorable for tornadoes
        - **1000-2000m**: Moderate cloud bases
        - **> 2000m**: High cloud bases, commonly seen with drier air masses
        """)
    
    with st.expander("Wind Shear"):
        st.markdown("""
        Wind shear is the change in wind speed and/or direction with height. It's crucial for thunderstorm organization and longevity.
        
        - **0-20 knots**: Minimal shear, pulse-type thunderstorms
        - **20-40 knots**: Moderate shear, organized multicell storms
        - **> 40 knots**: Strong shear, supercell potential
        """)
    
    # Disclaimer
    st.markdown("""
    ---
    **Disclaimer**: This tool provides meteorological analysis for educational and information purposes. For official forecasts and warnings, always consult your local weather service.
    """)