import os
import logging
from datetime import datetime, timedelta
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WeatherDatabase:
    """
    A class to handle database operations for storing and retrieving weather forecast data
    """
    
    def __init__(self):
        """Initialize database connection using environment variables"""
        try:
            self.database_url = os.environ.get('DATABASE_URL')
            if not self.database_url:
                raise ValueError("DATABASE_URL environment variable not set")
            
            self.engine = create_engine(self.database_url)
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            self.engine = None
    
    def save_location(self, name, lat, lon):
        """
        Save a location to the database, update if it exists
        
        Args:
            name (str): Location name
            lat (float): Latitude
            lon (float): Longitude
            
        Returns:
            int: Location ID
        """
        if not self.engine:
            logger.error("Database connection not available")
            return None
        
        try:
            # Check if location with these coordinates exists
            query = text("""
                SELECT id FROM locations 
                WHERE lat BETWEEN :lat - 0.01 AND :lat + 0.01
                AND lon BETWEEN :lon - 0.01 AND :lon + 0.01
            """)
            
            with self.engine.connect() as connection:
                result = connection.execute(query, {"lat": lat, "lon": lon})
                location_row = result.fetchone()
                
                if location_row:
                    # Update last accessed time
                    location_id = location_row[0]
                    update_query = text("""
                        UPDATE locations SET 
                        name = :name,
                        last_accessed = NOW()
                        WHERE id = :id
                    """)
                    connection.execute(update_query, {"name": name, "id": location_id})
                    connection.commit()
                    logger.info(f"Updated location {name} ({lat}, {lon})")
                    return location_id
                else:
                    # Insert new location
                    insert_query = text("""
                        INSERT INTO locations (name, lat, lon)
                        VALUES (:name, :lat, :lon)
                        RETURNING id
                    """)
                    result = connection.execute(insert_query, {"name": name, "lat": lat, "lon": lon})
                    connection.commit()
                    location_id = result.fetchone()[0]
                    logger.info(f"Added new location {name} ({lat}, {lon})")
                    return location_id
                    
        except SQLAlchemyError as e:
            logger.error(f"Database error while saving location: {e}")
            return None
    
    def save_forecast_data(self, location_id, parameter_code, forecast_data):
        """
        Save forecast data to the database
        
        Args:
            location_id (int): Location ID
            parameter_code (str): Parameter code (e.g., TMP_TGL_2)
            forecast_data (pd.DataFrame): Dataframe with time and value columns
            
        Returns:
            bool: Success status
        """
        if not self.engine or forecast_data is None or forecast_data.empty:
            logger.error("Database connection not available or empty forecast data")
            return False
        
        try:
            with self.engine.connect() as connection:
                # Insert each forecast time point
                for _, row in forecast_data.iterrows():
                    if 'time' not in row or 'value' not in row:
                        continue
                        
                    query = text("""
                        INSERT INTO forecast_data 
                        (location_id, parameter_code, forecast_time, value)
                        VALUES (:location_id, :parameter_code, :forecast_time, :value)
                        ON CONFLICT (location_id, parameter_code, forecast_time)
                        DO UPDATE SET value = :value, created_at = NOW()
                    """)
                    
                    connection.execute(query, {
                        "location_id": location_id,
                        "parameter_code": parameter_code,
                        "forecast_time": row['time'],
                        "value": float(row['value'])
                    })
                
                connection.commit()
                logger.info(f"Saved {len(forecast_data)} forecast points for {parameter_code}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Database error while saving forecast data: {e}")
            return False
    
    def save_weather_warning(self, location_id, warning_type, description, start_time=None, end_time=None, severity="moderate"):
        """
        Save a severe weather warning to the database
        
        Args:
            location_id (int): Location ID
            warning_type (str): Type of warning (e.g., "Heavy Precipitation")
            description (str): Warning description
            start_time (datetime): Warning start time
            end_time (datetime): Warning end time
            severity (str): Warning severity (low, moderate, high, extreme)
            
        Returns:
            bool: Success status
        """
        if not self.engine:
            logger.error("Database connection not available")
            return False
        
        try:
            with self.engine.connect() as connection:
                query = text("""
                    INSERT INTO weather_warnings 
                    (location_id, warning_type, description, start_time, end_time, severity)
                    VALUES (:location_id, :warning_type, :description, :start_time, :end_time, :severity)
                """)
                
                connection.execute(query, {
                    "location_id": location_id,
                    "warning_type": warning_type,
                    "description": description,
                    "start_time": start_time,
                    "end_time": end_time,
                    "severity": severity
                })
                
                connection.commit()
                logger.info(f"Saved warning: {warning_type} for location {location_id}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Database error while saving warning: {e}")
            return False
    
    def save_model_run(self, model_name, run_time):
        """
        Save information about a model run
        
        Args:
            model_name (str): Name of the model (e.g., "GDPS")
            run_time (datetime): Model run time
            
        Returns:
            bool: Success status
        """
        if not self.engine:
            logger.error("Database connection not available")
            return False
        
        try:
            with self.engine.connect() as connection:
                # Set all existing runs of this model to not latest
                update_query = text("""
                    UPDATE model_runs SET is_latest = FALSE
                    WHERE model_name = :model_name
                """)
                connection.execute(update_query, {"model_name": model_name})
                
                # Insert the new run
                insert_query = text("""
                    INSERT INTO model_runs (model_name, run_time, is_latest)
                    VALUES (:model_name, :run_time, TRUE)
                    ON CONFLICT (model_name, run_time)
                    DO UPDATE SET is_latest = TRUE, available_at = NOW()
                """)
                
                connection.execute(insert_query, {
                    "model_name": model_name,
                    "run_time": run_time
                })
                
                connection.commit()
                logger.info(f"Saved model run: {model_name} at {run_time}")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Database error while saving model run: {e}")
            return False
    
    def get_latest_forecast(self, location_id, parameter_code, hours_limit=168):
        """
        Retrieve the latest forecast data for a parameter at a location
        
        Args:
            location_id (int): Location ID
            parameter_code (str): Parameter code (e.g., TMP_TGL_2)
            hours_limit (int): Maximum forecast hours to retrieve
            
        Returns:
            pd.DataFrame: Dataframe with forecast data or None
        """
        if not self.engine:
            logger.error("Database connection not available")
            return None
        
        try:
            query = text("""
                SELECT forecast_time, value
                FROM forecast_data
                WHERE location_id = :location_id
                AND parameter_code = :parameter_code
                AND forecast_time >= NOW()
                AND forecast_time <= NOW() + (INTERVAL '1 hour' * :hours_limit)
                ORDER BY forecast_time ASC
            """)
            
            with self.engine.connect() as connection:
                result = connection.execute(query, {
                    "location_id": location_id, 
                    "parameter_code": parameter_code,
                    "hours_limit": str(hours_limit)
                })
                
                rows = result.fetchall()
                if not rows:
                    logger.info(f"No forecast data found for {parameter_code} at location {location_id}")
                    return None
                
                df = pd.DataFrame(rows, columns=['time', 'value'])
                logger.info(f"Retrieved {len(df)} forecast points for {parameter_code}")
                return df
                
        except SQLAlchemyError as e:
            logger.error(f"Database error while retrieving forecast: {e}")
            return None
    
    def get_active_warnings(self, location_id):
        """
        Retrieve active weather warnings for a location
        
        Args:
            location_id (int): Location ID
            
        Returns:
            list: List of warning dictionaries
        """
        if not self.engine:
            logger.error("Database connection not available")
            return []
        
        try:
            query = text("""
                SELECT warning_type, description, start_time, end_time, severity
                FROM weather_warnings
                WHERE location_id = :location_id
                AND (end_time IS NULL OR end_time > NOW())
                ORDER BY severity DESC, start_time ASC
            """)
            
            with self.engine.connect() as connection:
                result = connection.execute(query, {"location_id": location_id})
                rows = result.fetchall()
                
                warnings = []
                for row in rows:
                    warnings.append({
                        'title': row[0],
                        'description': row[1],
                        'start_time': row[2],
                        'end_time': row[3],
                        'severity': row[4]
                    })
                
                logger.info(f"Retrieved {len(warnings)} active warnings for location {location_id}")
                return warnings
                
        except SQLAlchemyError as e:
            logger.error(f"Database error while retrieving warnings: {e}")
            return []
    
    def get_location_by_coordinates(self, lat, lon, tolerance=0.01):
        """
        Find a location by approximate coordinates
        
        Args:
            lat (float): Latitude
            lon (float): Longitude
            tolerance (float): Coordinate tolerance
            
        Returns:
            dict: Location information or None
        """
        if not self.engine:
            logger.error("Database connection not available")
            return None
        
        try:
            query = text("""
                SELECT id, name, lat, lon, last_accessed
                FROM locations
                WHERE lat BETWEEN :lat - :tolerance AND :lat + :tolerance
                AND lon BETWEEN :lon - :tolerance AND :lon + :tolerance
                ORDER BY last_accessed DESC
                LIMIT 1
            """)
            
            with self.engine.connect() as connection:
                result = connection.execute(query, {"lat": lat, "lon": lon, "tolerance": tolerance})
                row = result.fetchone()
                
                if row:
                    location = {
                        'id': row[0],
                        'name': row[1],
                        'lat': float(row[2]),
                        'lon': float(row[3]),
                        'last_accessed': row[4]
                    }
                    
                    # Update last accessed time
                    update_query = text("""
                        UPDATE locations SET last_accessed = NOW()
                        WHERE id = :id
                    """)
                    connection.execute(update_query, {"id": location['id']})
                    connection.commit()
                    
                    return location
                else:
                    return None
                    
        except SQLAlchemyError as e:
            logger.error(f"Database error while retrieving location: {e}")
            return None
    
    def get_recent_locations(self, limit=5):
        """
        Get recently accessed locations
        
        Args:
            limit (int): Maximum number of locations to return
            
        Returns:
            list: List of location dictionaries
        """
        if not self.engine:
            logger.error("Database connection not available")
            return []
        
        try:
            query = text("""
                SELECT id, name, lat, lon, last_accessed
                FROM locations
                ORDER BY last_accessed DESC
                LIMIT :limit
            """)
            
            with self.engine.connect() as connection:
                result = connection.execute(query, {"limit": limit})
                rows = result.fetchall()
                
                locations = []
                for row in rows:
                    locations.append({
                        'id': row[0],
                        'name': row[1],
                        'lat': float(row[2]),
                        'lon': float(row[3]),
                        'last_accessed': row[4]
                    })
                
                return locations
                
        except SQLAlchemyError as e:
            logger.error(f"Database error while retrieving recent locations: {e}")
            return []
    
    def get_latest_model_run(self, model_name="GDPS"):
        """
        Get information about the latest model run
        
        Args:
            model_name (str): Name of the model (e.g., "GDPS")
            
        Returns:
            datetime: Latest model run time or None
        """
        if not self.engine:
            logger.error("Database connection not available")
            return None
        
        try:
            query = text("""
                SELECT run_time
                FROM model_runs
                WHERE model_name = :model_name AND is_latest = TRUE
                ORDER BY run_time DESC
                LIMIT 1
            """)
            
            with self.engine.connect() as connection:
                result = connection.execute(query, {"model_name": model_name})
                row = result.fetchone()
                
                if row:
                    return row[0]
                else:
                    return None
                    
        except SQLAlchemyError as e:
            logger.error(f"Database error while retrieving model run: {e}")
            return None
    
    def clear_old_data(self, days_to_keep=7):
        """
        Clear old forecast data and expired warnings
        
        Args:
            days_to_keep (int): Number of days of data to keep
            
        Returns:
            bool: Success status
        """
        if not self.engine:
            logger.error("Database connection not available")
            return False
        
        try:
            with self.engine.connect() as connection:
                # Delete old forecast data
                forecast_query = text("""
                    DELETE FROM forecast_data
                    WHERE created_at < NOW() - INTERVAL :days DAY
                    OR forecast_time < NOW() - INTERVAL '1' DAY
                """)
                connection.execute(forecast_query, {"days": days_to_keep})
                
                # Delete expired warnings
                warnings_query = text("""
                    DELETE FROM weather_warnings
                    WHERE (end_time IS NOT NULL AND end_time < NOW())
                    OR created_at < NOW() - INTERVAL :days DAY
                """)
                connection.execute(warnings_query, {"days": days_to_keep})
                
                # Delete old model runs
                model_runs_query = text("""
                    DELETE FROM model_runs
                    WHERE is_latest = FALSE
                    AND available_at < NOW() - INTERVAL :days DAY
                """)
                connection.execute(model_runs_query, {"days": days_to_keep})
                
                connection.commit()
                logger.info(f"Cleared data older than {days_to_keep} days")
                return True
                
        except SQLAlchemyError as e:
            logger.error(f"Database error while clearing old data: {e}")
            return False


# Initialize the database class as a singleton
db = WeatherDatabase()