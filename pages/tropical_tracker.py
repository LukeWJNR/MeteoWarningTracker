"""
Tropical Storm Tracker - Track and analyze tropical cyclones
"""
import streamlit as st
import pandas as pd
import folium
from streamlit_folium import folium_static
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np
from utils.tropical import tropical_tracker

# Page configuration
st.set_page_config(
    page_title="Tropical Storm Tracker",
    page_icon="🌀",
    layout="wide"
)

# Title and introduction
st.title("🌀 Tropical Storm Tracker")
st.markdown("""
This page provides real-time tracking and analysis of tropical cyclones using NOAA data.
Monitor active storms, view forecasts, and explore historical storm data.
""")

# Initialize data
with st.spinner("Loading tropical storm data..."):
    tropical_tracker.init_data()

# Main tabs
tab1, tab2, tab3 = st.tabs(["Active Storms", "Historical Storms", "Storm Analysis"])

with tab1:
    st.markdown("### Currently Active Tropical Cyclones")
    
    # Get active storms
    active_storms = tropical_tracker.get_active_storms()
    
    if not active_storms:
        st.info("There are currently no active tropical cyclones in the tracked basins.")
    else:
        # Display active storms as cards
        st.markdown(f"**{len(active_storms)} active storms found**")
        
        # Create columns for storm cards
        cols = st.columns(min(3, len(active_storms)))
        
        for i, storm in enumerate(active_storms):
            with cols[i % len(cols)]:
                # Create a card-like display
                st.markdown(f"""
                <div style="padding: 10px; border: 1px solid #ddd; border-radius: 5px; margin-bottom: 10px;">
                    <h3 style="margin-top:0">{storm['name']}</h3>
                    <p><strong>Status:</strong> {storm['current_status']['category']}</p>
                    <p><strong>Wind:</strong> {storm['current_status']['wind']} kt</p>
                    <p><strong>Pressure:</strong> {storm['current_status']['pressure']} mb</p>
                    <p><strong>Location:</strong> {storm['current_status']['lat']:.1f}°N, {storm['current_status']['lon']:.1f}°W</p>
                </div>
                """, unsafe_allow_html=True)
        
        # Storm selector for detailed view
        selected_storm = st.selectbox(
            "Select a storm for detailed tracking",
            options=[storm["id"] for storm in active_storms],
            format_func=lambda x: next((storm["name"] for storm in active_storms if storm["id"] == x), x)
        )
        
        # Detailed view of selected storm
        if selected_storm:
            st.markdown("### Storm Track and Forecast")
            
            # Get storm details
            storm_details = next((storm for storm in active_storms if storm["id"] == selected_storm), None)
            
            if storm_details:
                # Display basic information
                col1, col2 = st.columns([2, 1])
                
                with col1:
                    # Create interactive map
                    storm_map = tropical_tracker.create_storm_map(selected_storm)
                    folium_static(storm_map, width=700)
                
                with col2:
                    # Display detailed storm information
                    st.markdown(f"### {storm_details['name']} ({storm_details['id']})")
                    
                    # Get comprehensive storm summary
                    summary = tropical_tracker.get_storm_summary(selected_storm)
                    
                    if summary:
                        st.markdown(f"**Current Status:** {summary['current_intensity']['category']}")
                        st.markdown(f"**Wind Speed:** {summary['current_intensity']['wind']} kt")
                        st.markdown(f"**Pressure:** {summary['current_intensity']['pressure']} mb")
                        
                        if 'movement' in summary:
                            st.markdown(f"**Movement:** {summary['movement']['heading']}° at {summary['movement']['speed']} kt")
                        
                        # Display forecast in a table
                        if 'forecast' in summary and summary['forecast']:
                            st.markdown("#### Forecast")
                            
                            forecast_data = []
                            for point in summary['forecast']:
                                forecast_data.append({
                                    "Time": point['time'].strftime("%Y-%m-%d %H:%M"),
                                    "Wind (kt)": point['wind'],
                                    "Category": point['category'],
                                    "Lat": f"{point['lat']:.1f}°N",
                                    "Lon": f"{point['lon']:.1f}°W"
                                })
                            
                            st.dataframe(pd.DataFrame(forecast_data), hide_index=True)
                
                # Generate a static image of the storm
                st.markdown("### Detailed Track Image")
                track_image = tropical_tracker.plot_active_storm(selected_storm)
                
                if track_image:
                    st.image(track_image, caption=f"{storm_details['name']} Track and Forecast")
                else:
                    st.warning("Could not generate detailed track image.")

with tab2:
    st.markdown("### Historical Tropical Cyclone Data")
    
    # Season selector
    current_year = datetime.now().year
    selected_year = st.slider(
        "Select Season",
        min_value=current_year - 10,
        max_value=current_year,
        value=current_year - 1 if datetime.now().month < 6 else current_year
    )
    
    # Get historical storm data
    with st.spinner(f"Loading {selected_year} storm data..."):
        historical_storms = tropical_tracker.get_historical_storms(year=selected_year)
    
    if historical_storms is not None and not historical_storms.empty:
        # Display season summary
        st.markdown(f"#### {selected_year} Atlantic Hurricane Season Summary")
        
        # Display stats
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Storms", len(historical_storms))
        
        with col2:
            hurricanes = len(historical_storms[historical_storms['max_wind'] >= 64])
            st.metric("Hurricanes", hurricanes)
        
        with col3:
            major_hurricanes = len(historical_storms[historical_storms['max_wind'] >= 96])
            st.metric("Major Hurricanes", major_hurricanes)
        
        # Display ACE index
        total_ace = historical_storms['ace'].sum()
        st.metric("Accumulated Cyclone Energy (ACE)", f"{total_ace:.1f}")
        
        # Display storms in a table
        st.markdown("#### Storm List")
        
        # Format the dataframe for display
        display_df = historical_storms.copy()
        display_df['Duration (days)'] = (display_df['end_date'] - display_df['start_date']).dt.total_seconds() / (24 * 3600)
        display_df['Duration (days)'] = display_df['Duration (days)'].round(1)
        display_df['Start Date'] = display_df['start_date'].dt.strftime('%Y-%m-%d')
        display_df['End Date'] = display_df['end_date'].dt.strftime('%Y-%m-%d')
        
        # Reorder and select columns for display
        display_df = display_df[['name', 'category', 'max_wind', 'min_pressure', 'Start Date', 'End Date', 'Duration (days)', 'ace']]
        display_df.columns = ['Name', 'Maximum Category', 'Max Wind (kt)', 'Min Pressure (mb)', 'Start Date', 'End Date', 'Duration (days)', 'ACE']
        
        st.dataframe(display_df, hide_index=True)
        
        # Generate and display a season map
        st.markdown("#### Season Track Map")
        season_image = tropical_tracker.plot_historical_season(selected_year)
        
        if season_image:
            st.image(season_image, caption=f"{selected_year} Atlantic Hurricane Season Tracks")
        else:
            st.warning("Could not generate season track map.")
        
    else:
        st.info(f"No historical storm data available for {selected_year}.")

with tab3:
    st.markdown("### Detailed Storm Analysis")
    st.markdown("""
    Select a historical storm to analyze its track, intensity, and other characteristics.
    """)
    
    # Create two columns for input
    col1, col2 = st.columns(2)
    
    with col1:
        # Year selector
        analysis_year = st.selectbox(
            "Select Year",
            options=list(range(current_year, current_year - 11, -1)),
            index=0
        )
    
    # Get storms for the selected year
    with st.spinner(f"Loading {analysis_year} storm data..."):
        year_storms = tropical_tracker.get_historical_storms(year=analysis_year)
    
    if year_storms is not None and not year_storms.empty:
        with col2:
            # Storm selector
            storm_id = st.selectbox(
                "Select Storm",
                options=year_storms['id'].tolist(),
                format_func=lambda x: next((f"{row['name']} ({row['category']})" for _, row in year_storms.iterrows() if row['id'] == x), x)
            )
        
        if storm_id:
            # Get detailed storm summary
            with st.spinner("Loading detailed storm data..."):
                storm_summary = tropical_tracker.get_storm_summary(storm_id, current=False)
            
            if storm_summary:
                # Display storm details
                st.markdown(f"### {storm_summary['name']} ({storm_summary['id']})")
                
                # Create tabs for different analysis views
                analysis_tabs = st.tabs(["Overview", "Track Map", "Intensity", "Comparison"])
                
                with analysis_tabs[0]:
                    # Basic overview
                    st.markdown("#### Storm Overview")
                    
                    # Create metrics in columns
                    metric_col1, metric_col2, metric_col3 = st.columns(3)
                    
                    with metric_col1:
                        st.metric("Maximum Category", storm_summary['intensity']['max_category'])
                        st.metric("Maximum Wind", f"{storm_summary['intensity']['max_wind']} kt")
                    
                    with metric_col2:
                        st.metric("Minimum Pressure", f"{storm_summary['intensity']['min_pressure']} mb")
                        st.metric("ACE Index", f"{storm_summary['stats']['ace']:.1f}")
                    
                    with metric_col3:
                        duration_days = storm_summary['stats']['duration_hours'] / 24
                        st.metric("Duration", f"{duration_days:.1f} days")
                        st.metric("Track Distance", f"{storm_summary['stats']['track_distance']:.0f} km")
                    
                    # Create timeline
                    start_date = storm_summary['stats']['start_date']
                    end_date = storm_summary['stats']['end_date']
                    
                    st.markdown(f"**Active Period:** {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}")
                
                with analysis_tabs[1]:
                    # Track map visualization
                    st.markdown("#### Storm Track Map")
                    
                    # Extract track data
                    track_data = pd.DataFrame(storm_summary['track'])
                    
                    # Create Folium map
                    if not track_data.empty:
                        # Calculate center point
                        center_lat = track_data['lat'].mean()
                        center_lon = track_data['lon'].mean()
                        
                        m = folium.Map(
                            location=[center_lat, center_lon],
                            zoom_start=5,
                            tiles='CartoDB positron'
                        )
                        
                        # Add track points
                        points = []
                        for _, point in track_data.iterrows():
                            points.append([point['lat'], point['lon']])
                            
                            # Determine marker color based on storm category
                            if point['type'] == 'HU':
                                if point['wind'] >= 137:
                                    color = 'darkred'  # Cat 5
                                elif point['wind'] >= 113:
                                    color = 'red'  # Cat 4
                                elif point['wind'] >= 96:
                                    color = 'orange'  # Cat 3
                                elif point['wind'] >= 83:
                                    color = 'lightred'  # Cat 2
                                else:
                                    color = 'beige'  # Cat 1
                            elif point['type'] == 'TS':
                                color = 'blue'
                            else:
                                color = 'lightblue'
                            
                            # Add marker
                            folium.CircleMarker(
                                location=[point['lat'], point['lon']],
                                radius=5,
                                color=color,
                                fill=True,
                                fill_color=color,
                                tooltip=f"{point['time'].strftime('%Y-%m-%d %H:%M')} - {point['category']} ({point['wind']} kt)"
                            ).add_to(m)
                        
                        # Add track line
                        folium.PolyLine(
                            points,
                            color='blue',
                            weight=2,
                            opacity=0.7
                        ).add_to(m)
                        
                        # Display map
                        folium_static(m, width=700)
                    else:
                        st.warning("No track data available for mapping.")
                
                with analysis_tabs[2]:
                    # Intensity analysis
                    st.markdown("#### Storm Intensity Evolution")
                    
                    # Extract track data for plotting
                    track_data = pd.DataFrame(storm_summary['track'])
                    
                    if not track_data.empty:
                        # Create plotly figure for intensity
                        fig = go.Figure()
                        
                        # Add wind trace
                        fig.add_trace(go.Scatter(
                            x=track_data['time'],
                            y=track_data['wind'],
                            mode='lines+markers',
                            name='Wind Speed (kt)',
                            line=dict(color='blue', width=2)
                        ))
                        
                        # Add category thresholds
                        fig.add_shape(
                            type='line',
                            x0=track_data['time'].min(),
                            x1=track_data['time'].max(),
                            y0=34,
                            y1=34,
                            line=dict(color='green', dash='dash'),
                            name='Tropical Storm'
                        )
                        
                        fig.add_shape(
                            type='line',
                            x0=track_data['time'].min(),
                            x1=track_data['time'].max(),
                            y0=64,
                            y1=64,
                            line=dict(color='orange', dash='dash'),
                            name='Hurricane'
                        )
                        
                        fig.add_shape(
                            type='line',
                            x0=track_data['time'].min(),
                            x1=track_data['time'].max(),
                            y0=96,
                            y1=96,
                            line=dict(color='red', dash='dash'),
                            name='Major Hurricane'
                        )
                        
                        # Update layout
                        fig.update_layout(
                            title=f"{storm_summary['name']} Wind Intensity",
                            xaxis_title="Date",
                            yaxis_title="Wind Speed (kt)",
                            height=400,
                            margin=dict(l=20, r=20, t=50, b=20)
                        )
                        
                        # Display plot
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Create pressure plot
                        fig2 = go.Figure()
                        
                        fig2.add_trace(go.Scatter(
                            x=track_data['time'],
                            y=track_data['pressure'],
                            mode='lines+markers',
                            name='Pressure (mb)',
                            line=dict(color='red', width=2)
                        ))
                        
                        # Update layout
                        fig2.update_layout(
                            title=f"{storm_summary['name']} Pressure Evolution",
                            xaxis_title="Date",
                            yaxis_title="Pressure (mb)",
                            height=350,
                            margin=dict(l=20, r=20, t=50, b=20),
                            yaxis=dict(autorange="reversed")  # Lower pressure at the top
                        )
                        
                        # Display plot
                        st.plotly_chart(fig2, use_container_width=True)
                    else:
                        st.warning("No intensity data available for plotting.")
                
                with analysis_tabs[3]:
                    # Comparison with other storms
                    st.markdown("#### Compare with Other Storms")
                    
                    # Get all storms for comparison
                    if year_storms is not None and not year_storms.empty:
                        # Create comparison chart
                        fig = px.bar(
                            year_storms,
                            x='name',
                            y='max_wind',
                            color='category',
                            title=f"Maximum Wind Speed Comparison - {analysis_year}",
                            labels={'name': 'Storm Name', 'max_wind': 'Maximum Wind Speed (kt)'},
                            height=400
                        )
                        
                        # Highlight the selected storm
                        selected_storm_name = storm_summary['name']
                        fig.add_shape(
                            type='rect',
                            x0=year_storms[year_storms['name'] == selected_storm_name].index[0] - 0.4,
                            x1=year_storms[year_storms['name'] == selected_storm_name].index[0] + 0.4,
                            y0=0,
                            y1=year_storms[year_storms['name'] == selected_storm_name]['max_wind'].values[0],
                            line=dict(color='black', width=2),
                            fillcolor='rgba(0,0,0,0)'
                        )
                        
                        # Display plot
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # ACE comparison
                        fig2 = px.bar(
                            year_storms,
                            x='name',
                            y='ace',
                            title=f"Accumulated Cyclone Energy (ACE) Comparison - {analysis_year}",
                            labels={'name': 'Storm Name', 'ace': 'ACE Index'},
                            height=400
                        )
                        
                        # Highlight the selected storm
                        fig2.add_shape(
                            type='rect',
                            x0=year_storms[year_storms['name'] == selected_storm_name].index[0] - 0.4,
                            x1=year_storms[year_storms['name'] == selected_storm_name].index[0] + 0.4,
                            y0=0,
                            y1=year_storms[year_storms['name'] == selected_storm_name]['ace'].values[0],
                            line=dict(color='black', width=2),
                            fillcolor='rgba(0,0,0,0)'
                        )
                        
                        # Display plot
                        st.plotly_chart(fig2, use_container_width=True)
                    else:
                        st.warning("No comparison data available.")
            else:
                st.warning("Could not load detailed storm data. Please try another selection.")
    else:
        st.info(f"No storm data available for {analysis_year}.")

# Footer
st.markdown("---")
st.markdown("""
Tropical Storm Tracker | Powered by Tropycal package and NOAA NHC data
* Data sourced from the National Hurricane Center (NHC) and processed using Tropycal
* Last updated: {}
""".format(datetime.now().strftime("%Y-%m-%d %H:%M")))

# Add information about the data
with st.expander("About Tropical Storm Data"):
    st.markdown("""
    ### Data Sources
    
    This tracker uses data from the following sources:
    
    * **National Hurricane Center (NHC)**: Official tropical cyclone forecasts, tracks, and advisories
    * **HURDAT2**: Historical hurricane database with best track data
    * **Tropycal Package**: Python package for tropical cyclone analysis
    
    ### Storm Categories
    
    Tropical cyclones are classified by their maximum sustained wind speeds:
    
    * **Tropical Depression**: < 34 knots (< 39 mph)
    * **Tropical Storm**: 34-63 knots (39-73 mph)
    * **Category 1 Hurricane**: 64-82 knots (74-95 mph)
    * **Category 2 Hurricane**: 83-95 knots (96-110 mph)
    * **Category 3 Hurricane**: 96-112 knots (111-129 mph)
    * **Category 4 Hurricane**: 113-136 knots (130-156 mph)
    * **Category 5 Hurricane**: > 136 knots (> 156 mph)
    
    ### Accumulated Cyclone Energy (ACE)
    
    ACE is a measure of hurricane activity based on wind speed over the lifecycle of a storm. It is calculated by summing the squares of the 6-hourly maximum sustained wind speeds (in knots) for all named systems while they are at least tropical storm strength.
    """)