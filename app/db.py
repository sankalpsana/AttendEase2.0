import os
import mysql.connector
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from urllib.parse import urlparse

load_dotenv()

# Global variable to hold the connection for reuse (if needed, though frameworks usually handle this)
# For this simple app, we'll create a new connection per request or let the driver handle pooling if configured.

def get_db_connection():
    """
    Establishes a connection to the database based on the DATABASE_URL environment variable.
    Supports both MySQL (legacy) and PostgreSQL (new).
    """
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        # Fallback to legacy MySQL config if no DATABASE_URL is present
        return get_mysql_connection()

    # Parse the URL to determine the database type
    parsed_url = urlparse(database_url)
    scheme = parsed_url.scheme

    if 'postgres' in scheme:
        return get_postgres_connection(database_url)
    elif 'mysql' in scheme:
        # If we eventually switch to a mysql:// URL, we can parse it here.
        # For now, we assume standard host/user/pass env vars for MySQL if not Postgres.
        return get_mysql_connection()
    else:
        raise ValueError(f"Unsupported database scheme: {scheme}")

def get_mysql_connection():
    """Legacy MySQL connection using individual env vars."""
    try:
        conn = mysql.connector.connect(
            host=os.getenv('DB_HOST', 'localhost'),
            user=os.getenv('DB_USER', 'root'),
            password=os.getenv('DB_PASSWORD', 'password'),
            database=os.getenv('DB_NAME', 'attendance_system')
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL: {err}")
        raise

def get_postgres_connection(database_url):
    """PostgreSQL connection using psycopg2."""
    try:
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        return conn
    except psycopg2.Error as err:
        print(f"Error connecting to PostgreSQL: {err}")
        raise
