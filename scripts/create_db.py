import mysql.connector
import os
from dotenv import load_dotenv

load_dotenv()

dbconfig = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'password'),
}

def create_database():
    try:
        conn = mysql.connector.connect(**dbconfig)
        cursor = conn.cursor()
        
        # Create database
        cursor.execute("CREATE DATABASE IF NOT EXISTS attendance_system")
        print("Database 'attendance_system' created or already exists.")
        
        cursor.execute("USE attendance_system")
        
        # Create tables
        tables = {}
        
        tables['admin'] = (
            "CREATE TABLE IF NOT EXISTS admin ("
            "  admin_id VARCHAR(20) NOT NULL,"
            "  username VARCHAR(50) NOT NULL,"
            "  email VARCHAR(100) NOT NULL,"
            "  password_hash VARCHAR(255) NOT NULL,"
            "  PRIMARY KEY (admin_id)"
            ") ENGINE=InnoDB")
            
        tables['sections'] = (
            "CREATE TABLE IF NOT EXISTS sections ("
            "  section_name VARCHAR(10) NOT NULL,"
            "  PRIMARY KEY (section_name)"
            ") ENGINE=InnoDB")
            
        tables['subjects'] = (
            "CREATE TABLE IF NOT EXISTS subjects ("
            "  subject_id INT AUTO_INCREMENT NOT NULL,"
            "  subject_name VARCHAR(100) NOT NULL,"
            "  PRIMARY KEY (subject_id)"
            ") ENGINE=InnoDB")

        tables['faculty'] = (
            "CREATE TABLE IF NOT EXISTS faculty ("
            "  faculty_id VARCHAR(20) NOT NULL,"
            "  name VARCHAR(100) NOT NULL,"
            "  email VARCHAR(100) NOT NULL,"
            "  password_hash VARCHAR(255) NOT NULL,"
            "  facial_embedding BLOB,"
            "  PRIMARY KEY (faculty_id)"
            ") ENGINE=InnoDB")

        tables['students'] = (
            "CREATE TABLE IF NOT EXISTS students ("
            "  roll_number VARCHAR(20) NOT NULL,"
            "  name VARCHAR(100) NOT NULL,"
            "  email VARCHAR(100) NOT NULL,"
            "  password_hash VARCHAR(255) NOT NULL,"
            "  section_name VARCHAR(10),"
            "  facial_embedding BLOB,"
            "  PRIMARY KEY (roll_number),"
            "  FOREIGN KEY (section_name) REFERENCES sections(section_name) ON DELETE SET NULL"
            ") ENGINE=InnoDB")
            
        tables['faculty_subjects'] = (
            "CREATE TABLE IF NOT EXISTS faculty_subjects ("
            "  id INT AUTO_INCREMENT NOT NULL,"
            "  subject_id INT NOT NULL,"
            "  faculty_id VARCHAR(20) NOT NULL,"
            "  section_name VARCHAR(10) NOT NULL,"
            "  PRIMARY KEY (id),"
            "  FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE,"
            "  FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE CASCADE,"
            "  FOREIGN KEY (section_name) REFERENCES sections(section_name) ON DELETE CASCADE"
            ") ENGINE=InnoDB")
            
        tables['attendance'] = (
            "CREATE TABLE IF NOT EXISTS attendance ("
            "  attendance_id INT AUTO_INCREMENT NOT NULL,"
            "  roll_number VARCHAR(20) NOT NULL,"
            "  subject_id INT NOT NULL,"
            "  date DATE NOT NULL,"
            "  status VARCHAR(20) NOT NULL,"
            "  faculty_id VARCHAR(20) NOT NULL,"
            "  PRIMARY KEY (attendance_id),"
            "  FOREIGN KEY (roll_number) REFERENCES students(roll_number) ON DELETE CASCADE,"
            "  FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE,"
            "  FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE CASCADE"
            ") ENGINE=InnoDB")
            
        tables['substitute_assignments'] = (
            "CREATE TABLE IF NOT EXISTS substitute_assignments ("
            "  id INT AUTO_INCREMENT NOT NULL,"
            "  original_faculty_id VARCHAR(20) NOT NULL,"
            "  substitute_faculty_id VARCHAR(20) NOT NULL,"
            "  subject_id INT NOT NULL,"
            "  section_name VARCHAR(10) NOT NULL,"
            "  date DATE NOT NULL,"
            "  PRIMARY KEY (id),"
            "  FOREIGN KEY (original_faculty_id) REFERENCES faculty(faculty_id) ON DELETE CASCADE,"
            "  FOREIGN KEY (substitute_faculty_id) REFERENCES faculty(faculty_id) ON DELETE CASCADE,"
            "  FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE,"
            "  FOREIGN KEY (section_name) REFERENCES sections(section_name) ON DELETE CASCADE"
            ") ENGINE=InnoDB")

        for name, ddl in tables.items():
            try:
                print(f"Creating table {name}: ", end='')
                cursor.execute(ddl)
                print("OK")
            except mysql.connector.Error as err:
                print(f"Error: {err.msg}")
        
        # Create default admin user
        # Check if admin exists first
        cursor.execute("SELECT * FROM admin WHERE admin_id = 'admin'")
        if not cursor.fetchone():
            print("Creating default admin user...")
            cursor.execute("INSERT INTO admin (admin_id, username, email, password_hash) VALUES (%s, %s, %s, %s)",
                           ('admin', 'admin', 'admin@example.com', 'admin123'))
            conn.commit()
            print("Default admin user created: ID 'admin', Password 'admin123'")
        else:
            print("Default admin user already exists.")

        cursor.close()
        conn.close()

    except mysql.connector.Error as err:
        print(f"Error connecting to MySQL: {err}")

if __name__ == "__main__":
    create_database()
