import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import folium
from folium.plugins import HeatMap, MarkerCluster
from branca.colormap import linear
import streamlit as st
import matplotlib.pyplot as plt

class WeatherVisualizer:
    """
    Class for creating visualizations of weather data
    """
    
    def __init__(self):
        self.color_scales = {
            'temperature': px.colors.diverging.RdBu_r,
            'precipitation': px.colors.sequential.Blues,
            'wind': px.colors.sequential.Viridis,
            'pressure': px.colors.sequential.matter,
            'humidity': px.colors.sequential.Blues,
            'cloud': px.colors.sequential.gray
        }
    
    def plot_time_series(self, df, parameter_name, units="", height=400):
        """
        Create a time series plot for a weather parameter
        
        Args:
            df (pd.DataFrame): Dataframe with time and value columns
            parameter_name (str): Name of the parameter being plotted
            units (str): Units for the y-axis
            height (int): Height of the plot in pixels
            
        Returns:
            plotly.graph_objects.Figure: Plotly figure object
        """
        if df is None or df.empty or 'time' not in df.columns or 'value' not in df.columns:
            return go.Figure()
        
        try:
            # Determine appropriate color scale
            color_scale = self.color_scales.get('temperature', px.colors.sequential.Viridis)
            if 'precipitation' in parameter_name.lower():
                color_scale = self.color_scales['precipitation']
            elif 'wind' in parameter_name.lower():
                color_scale = self.color_scales['wind']
            elif 'humidity' in parameter_name.lower():
                color_scale = self.color_scales['humidity']
            
            # Create figure
            fig = px.line(
                df, 
                x='time', 
                y='value',
                title=f"{parameter_name} Forecast",
                labels={"value": f"{parameter_name} ({units})", "time": "Time"},
                height=height
            )
            
            # Customize appearance
            fig.update_traces(line=dict(color="#1E88E5", width=2))
            fig.update_layout(
                margin=dict(l=20, r=20, t=40, b=20),
                plot_bgcolor="white",
                hovermode="x unified"
            )
            
            # Add daily min/max if available
            if 'min_value' in df.columns and 'max_value' in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df['time'],
                        y=df['min_value'],
                        mode='lines',
                        line=dict(width=0),
                        showlegend=False
                    )
                )
                fig.add_trace(
                    go.Scatter(
                        x=df['time'],
                        y=df['max_value'],
                        mode='lines',
                        line=dict(width=0),
                        fill='tonexty',
                        fillcolor='rgba(30, 136, 229, 0.2)',
                        showlegend=False
                    )
                )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating time series plot: {e}")
            return go.Figure()
    
    def plot_wind_barbs(self, wind_df, height=400):
        """
        Create a wind barb plot showing wind speed and direction
        
        Args:
            wind_df (pd.DataFrame): Dataframe with time, speed, and direction
            height (int): Height of the plot in pixels
            
        Returns:
            plotly.graph_objects.Figure: Plotly figure object
        """
        if wind_df is None or wind_df.empty:
            return go.Figure()
        
        try:
            # Check if we have U and V components
            if 'u' in wind_df.columns and 'v' in wind_df.columns:
                # Create figure
                fig = go.Figure()
                
                # Add wind barbs
                fig.add_trace(
                    go.Scatter(
                        x=wind_df['time'],
                        y=wind_df['value_speed'],
                        mode='lines+markers',
                        name='Wind Speed',
                        line=dict(color="#1E88E5", width=2)
                    )
                )
                
                # Add quiver plot for direction
                arrow_time = wind_df['time'][::3]  # Every 3rd point to avoid overcrowding
                arrow_speed = wind_df['value_speed'][::3]
                arrow_u = wind_df['u'][::3]
                arrow_v = wind_df['v'][::3]
                
                scale = 0.1 * np.max(arrow_speed)
                
                for i in range(len(arrow_time)):
                    fig.add_annotation(
                        x=arrow_time.iloc[i],
                        y=arrow_speed.iloc[i],
                        ax=arrow_time.iloc[i] + arrow_u.iloc[i] / scale,
                        ay=arrow_speed.iloc[i] + arrow_v.iloc[i] / scale,
                        axref="x", ayref="y",
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1,
                        arrowwidth=1,
                        arrowcolor="#546E7A"
                    )
                
                fig.update_layout(
                    title="Wind Speed and Direction",
                    xaxis_title="Time",
                    yaxis_title="Wind Speed (km/h)",
                    height=height,
                    margin=dict(l=20, r=20, t=40, b=20),
                    plot_bgcolor="white",
                    hovermode="x unified"
                )
                
                return fig
            
            # Fallback to basic line chart if we don't have direction
            return self.plot_time_series(
                wind_df, 
                "Wind Speed", 
                "km/h", 
                height
            )
            
        except Exception as e:
            st.error(f"Error creating wind barb plot: {e}")
            return go.Figure()
    
    def create_weather_map(self, grid_data, lat, lon, parameter, zoom=8):
        """
        Create a Folium map with weather data overlay
        
        Args:
            grid_data (dict): Gridded weather data
            lat (float): Center latitude
            lon (float): Center longitude
            parameter (str): Weather parameter being plotted
            zoom (int): Initial zoom level
            
        Returns:
            folium.Map: Folium map object
        """
        try:
            # Create base map
            m = folium.Map(
                location=[lat, lon],
                zoom_start=zoom,
                tiles='CartoDB positron'
            )
            
            # Add marker for selected location
            folium.Marker(
                [lat, lon],
                popup="Selected Location",
                icon=folium.Icon(color="red", icon="info-sign")
            ).add_to(m)
            
            # If grid data is available, add it to map
            if grid_data and 'lat' in grid_data and 'lon' in grid_data and 'values' in grid_data:
                lats = grid_data['lat']
                lons = grid_data['lon']
                values = grid_data['values']
                
                # Flatten values for min/max calculation if nested list
                flat_values = []
                for row in values:
                    if isinstance(row, list):
                        flat_values.extend(row)
                    else:
                        flat_values.append(row)
                
                # Determine color scale and range based on parameter
                if 'temperature' in parameter.lower():
                    colormap = linear.RdBu_11.scale(
                        min(flat_values),
                        max(flat_values)
                    )
                    colormap_name = 'Temperature (°C)'
                elif 'precipitation' in parameter.lower():
                    colormap = linear.Blues_09.scale(0, max(max(flat_values), 0.1))
                    colormap_name = 'Precipitation (mm)'
                elif 'wind' in parameter.lower():
                    colormap = linear.YlOrRd_09.scale(0, max(max(flat_values), 1))
                    colormap_name = 'Wind Speed (km/h)'
                else:
                    colormap = linear.viridis.scale(
                        min(flat_values),
                        max(flat_values)
                    )
                    colormap_name = parameter
                
                # Add the color map to the main map
                colormap.caption = colormap_name
                colormap.add_to(m)
                
                # Add data as a heatmap layer
                heat_data = []
                for i in range(len(lats)):
                    for j in range(len(lons)):
                        heat_data.append([lats[i], lons[j], values[i][j]])
                
                HeatMap(
                    heat_data,
                    radius=15,
                    gradient={0.0: 'blue', 0.5: 'lime', 1.0: 'red'},
                    min_opacity=0.5,
                    blur=10
                ).add_to(m)
            
            return m
            
        except Exception as e:
            st.error(f"Error creating weather map: {e}")
            # Return a basic map without the data layer
            m = folium.Map(
                location=[lat, lon],
                zoom_start=zoom,
                tiles='CartoDB positron'
            )
            return m
    
    def plot_precipitation_bars(self, precip_df, height=400):
        """
        Create a bar chart for precipitation forecast
        
        Args:
            precip_df (pd.DataFrame): Precipitation data with time and value
            height (int): Height of the plot in pixels
            
        Returns:
            plotly.graph_objects.Figure: Plotly figure object
        """
        if precip_df is None or precip_df.empty:
            return go.Figure()
        
        try:
            # Create figure
            fig = px.bar(
                precip_df,
                x='time',
                y='value',
                title="Precipitation Forecast",
                labels={"value": "Precipitation (mm)", "time": "Time"},
                height=height,
                color_discrete_sequence=["#1E88E5"]
            )
            
            # Add cumulative line if available
            if 'cumulative' in precip_df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=precip_df['time'],
                        y=precip_df['cumulative'],
                        mode='lines',
                        name='Cumulative',
                        line=dict(color="#FF6F00", width=2),
                        yaxis='y2'
                    )
                )
                
                # Update layout for secondary y-axis
                fig.update_layout(
                    yaxis2=dict(
                        title="Cumulative Precipitation (mm)",
                        overlaying="y",
                        side="right"
                    )
                )
            
            # Customize appearance
            fig.update_layout(
                margin=dict(l=20, r=20, t=40, b=20),
                plot_bgcolor="white",
                hovermode="x unified"
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating precipitation chart: {e}")
            return go.Figure()
    
    def create_severe_warning_visual(self, warnings):
        """
        Create visual representation of severe weather warnings
        
        Args:
            warnings (list): List of warning dictionaries
            
        Returns:
            plotly.graph_objects.Figure: Plotly figure or None
        """
        if not warnings:
            return None
        
        try:
            # Create a timeline visualization of warnings
            warning_types = []
            start_times = []
            end_times = []
            descriptions = []
            colors = []
            
            color_map = {
                'Extreme Heat': '#FF3D00',
                'Extreme Cold': '#2979FF',
                'Heavy Precipitation': '#0277BD',
                'Strong Winds': '#FFC107',
                'Thunderstorm': '#7B1FA2',
                'Tornado': '#D32F2F',
                'Flash Flood': '#0288D1',
                'Winter Storm': '#0D47A1',
                'Hurricane': '#6A1B9A'
            }
            
            # Process each warning
            for warning in warnings:
                if 'times' in warning and warning['times']:
                    # Sort times to find start and end
                    times = sorted(pd.to_datetime(warning['times']))
                    if len(times) > 0:
                        # If times are discrete points, create ranges by assuming each lasts 1 hour
                        current_start = times[0]
                        current_end = current_start + pd.Timedelta(hours=1)
                        
                        for i in range(1, len(times)):
                            time = times[i]
                            # If the next time is within 1 hour of current end, extend the range
                            if time <= current_end + pd.Timedelta(hours=1):
                                current_end = time + pd.Timedelta(hours=1)
                            else:
                                # Add the current range and start a new one
                                warning_types.append(warning['type'])
                                start_times.append(current_start)
                                end_times.append(current_end)
                                descriptions.append(warning['description'])
                                colors.append(color_map.get(warning['type'], '#757575'))
                                
                                current_start = time
                                current_end = time + pd.Timedelta(hours=1)
                        
                        # Add the last range
                        warning_types.append(warning['type'])
                        start_times.append(current_start)
                        end_times.append(current_end)
                        descriptions.append(warning['description'])
                        colors.append(color_map.get(warning['type'], '#757575'))
            
            if not warning_types:
                return None
                
            # Create a DataFrame for the chart
            df = pd.DataFrame({
                'Warning': warning_types,
                'Start': start_times,
                'End': end_times,
                'Description': descriptions,
                'Color': colors
            })
            
            # Create Gantt chart
            fig = px.timeline(
                df,
                x_start='Start',
                x_end='End',
                y='Warning',
                color='Warning',
                hover_data=['Description'],
                color_discrete_map={wt: color for wt, color in zip(df['Warning'], df['Color'])},
                title="Severe Weather Warnings Timeline"
            )
            
            # Update layout
            fig.update_layout(
                height=300,
                margin=dict(l=20, r=20, t=40, b=20),
                hovermode="closest",
                xaxis=dict(
                    title="Time",
                    tickangle=-45
                ),
                yaxis=dict(
                    title=None
                )
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating warning visualization: {e}")
            return None
    
    def create_forecast_summary_table(self, summary):
        """
        Create a visual summary table of forecast data
        
        Args:
            summary (dict): Forecast summary data
            
        Returns:
            plotly.graph_objects.Figure: Plotly figure with table
        """
        if not summary or 'daily' not in summary or not summary['daily']:
            return None
        
        try:
            daily = summary['daily']
            
            # Extract data
            dates = [day['date'] for day in daily]
            min_temps = [day.get('min_temp', '-') for day in daily]
            max_temps = [day.get('max_temp', '-') for day in daily]
            precip = [day.get('precipitation', 0) for day in daily]
            wind = [day.get('max_wind', '-') for day in daily]
            
            # Create color scales
            temp_scale = px.colors.diverging.RdBu_r
            precip_scale = px.colors.sequential.Blues
            
            # Format dates to be more readable
            formatted_dates = []
            for date_str in dates:
                try:
                    date_obj = pd.to_datetime(date_str)
                    formatted_dates.append(date_obj.strftime('%a<br>%b %d'))
                except:
                    formatted_dates.append(date_str)
            
            # Create table
            fig = go.Figure(data=[
                go.Table(
                    header=dict(
                        values=['Date', 'Min (°C)', 'Max (°C)', 'Precip (mm)', 'Wind (km/h)'],
                        fill_color='#1E88E5',
                        align='center',
                        font=dict(color='white', size=12)
                    ),
                    cells=dict(
                        values=[formatted_dates, min_temps, max_temps, precip, wind],
                        align='center',
                        height=30
                    )
                )
            ])
            
            fig.update_layout(
                margin=dict(l=10, r=10, t=10, b=10),
                height=len(daily) * 40 + 40  # Adjust height based on number of rows
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating forecast summary table: {e}")
            return None
