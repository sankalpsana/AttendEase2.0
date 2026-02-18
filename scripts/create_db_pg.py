import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def create_database():
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("DATABASE_URL not found in .env")
        return

    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        
        # Create tables
        tables = {}
        
        # Admin table
        tables['admin'] = (
            "CREATE TABLE IF NOT EXISTS admin ("
            "  admin_id VARCHAR(20) PRIMARY KEY,"
            "  username VARCHAR(50) NOT NULL,"
            "  email VARCHAR(100) NOT NULL,"
            "  password_hash VARCHAR(255) NOT NULL"
            ")")
            
        # Sections table
        tables['sections'] = (
            "CREATE TABLE IF NOT EXISTS sections ("
            "  section_name VARCHAR(10) PRIMARY KEY"
            ")")
            
        # Subjects table
        tables['subjects'] = (
            "CREATE TABLE IF NOT EXISTS subjects ("
            "  subject_id SERIAL PRIMARY KEY,"
            "  subject_name VARCHAR(100) NOT NULL"
            ")")

        # Faculty table
        tables['faculty'] = (
            "CREATE TABLE IF NOT EXISTS faculty ("
            "  faculty_id VARCHAR(20) PRIMARY KEY,"
            "  name VARCHAR(100) NOT NULL,"
            "  email VARCHAR(100) NOT NULL,"
            "  password_hash VARCHAR(255) NOT NULL,"
            "  facial_embedding BYTEA"  # BLOB in MySQL -> BYTEA in Postgres
            ")")

        # Students table
        tables['students'] = (
            "CREATE TABLE IF NOT EXISTS students ("
            "  roll_number VARCHAR(20) PRIMARY KEY,"
            "  name VARCHAR(100) NOT NULL,"
            "  email VARCHAR(100) NOT NULL,"
            "  password_hash VARCHAR(255) NOT NULL,"
            "  section_name VARCHAR(10),"
            "  facial_embedding BYTEA,"
            "  FOREIGN KEY (section_name) REFERENCES sections(section_name) ON DELETE SET NULL"
            ")")
            
        # Faculty Subjects table
        tables['faculty_subjects'] = (
            "CREATE TABLE IF NOT EXISTS faculty_subjects ("
            "  id SERIAL PRIMARY KEY,"
            "  subject_id INT NOT NULL,"
            "  faculty_id VARCHAR(20) NOT NULL,"
            "  section_name VARCHAR(10) NOT NULL,"
            "  FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE,"
            "  FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE CASCADE,"
            "  FOREIGN KEY (section_name) REFERENCES sections(section_name) ON DELETE CASCADE"
            ")")
            
        # Attendance table
        tables['attendance'] = (
            "CREATE TABLE IF NOT EXISTS attendance ("
            "  attendance_id SERIAL PRIMARY KEY,"
            "  roll_number VARCHAR(20) NOT NULL,"
            "  subject_id INT NOT NULL,"
            "  date DATE NOT NULL,"
            "  status VARCHAR(20) NOT NULL,"
            "  faculty_id VARCHAR(20) NOT NULL,"
            "  FOREIGN KEY (roll_number) REFERENCES students(roll_number) ON DELETE CASCADE,"
            "  FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE,"
            "  FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE CASCADE"
            ")")
            
        # Substitute Assignments table
        tables['substitute_assignments'] = (
            "CREATE TABLE IF NOT EXISTS substitute_assignments ("
            "  id SERIAL PRIMARY KEY,"
            "  original_faculty_id VARCHAR(20) NOT NULL,"
            "  substitute_faculty_id VARCHAR(20) NOT NULL,"
            "  subject_id INT NOT NULL,"
            "  section_name VARCHAR(10) NOT NULL,"
            "  date DATE NOT NULL,"
            "  FOREIGN KEY (original_faculty_id) REFERENCES faculty(faculty_id) ON DELETE CASCADE,"
            "  FOREIGN KEY (substitute_faculty_id) REFERENCES faculty(faculty_id) ON DELETE CASCADE,"
            "  FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE,"
            "  FOREIGN KEY (section_name) REFERENCES sections(section_name) ON DELETE CASCADE"
            ")")

        for name, ddl in tables.items():
            try:
                print(f"Creating table {name}: ", end='')
                cursor.execute(ddl)
                print("OK")
            except psycopg2.Error as err:
                print(f"Error: {err}")
        
        # Create default admin user if not exists
        cursor.execute("SELECT * FROM admin WHERE admin_id = %s", ('admin',))
        if not cursor.fetchone():
            print("Creating default admin user...")
            # Hash: 'admin123'
            hashed_pw = 'scrypt:32768:8:1$W0sylJ7M$f676239169450372df03da9e2003c03527e02df35c24941913349603204968ed983c25227181c96937e2e2830206143c7063ff8684218ea9153a795328990159'
            cursor.execute("INSERT INTO admin (admin_id, username, email, password_hash) VALUES (%s, %s, %s, %s)",
                           ('admin', 'admin', 'admin@example.com', hashed_pw))
            print("Default admin user created.")
        else:
            print("Default admin user already exists.")

        conn.commit()
        cursor.close()
        conn.close()

    except psycopg2.Error as err:
        print(f"Error connecting to PostgreSQL: {err}")

if __name__ == "__main__":
    create_database()
