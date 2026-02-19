import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    """
    Establishes a connection to the PostgreSQL database using DATABASE_URL.
    """
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set. Please configure it for Supabase/PostgreSQL.")

    try:
        conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        return conn
    except psycopg2.Error as err:
        print(f"Error connecting to PostgreSQL: {err}")
        raise
