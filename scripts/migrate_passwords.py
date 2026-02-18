import mysql.connector
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash

load_dotenv()

dbconfig = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'database': os.getenv('DB_NAME', 'attendance_system'),
}

def migrate_passwords():
    try:
        conn = mysql.connector.connect(**dbconfig)
        cursor = conn.cursor()
        
        tables = [
            {'name': 'students', 'id': 'roll_number'},
            {'name': 'faculty', 'id': 'faculty_id'},
            {'name': 'admin', 'id': 'admin_id'}
        ]
        
        for table in tables:
            table_name = table['name']
            id_col = table['id']
            print(f"Migrating passwords for {table_name}...")
            
            cursor.execute(f"SELECT {id_col}, password_hash FROM {table_name}")
            users = cursor.fetchall()
            
            for user in users:
                user_id = user[0]
                current_password = user[1]
                
                # Simple check: if it looks like a hash (starts with method$), skip
                # Werkzeug default hash starts with scrypt: or pbkdf2:
                if current_password.startswith('scrypt:') or current_password.startswith('pbkdf2:'):
                    print(f"  Skipping {user_id} (already hashed)")
                    continue
                    
                new_hash = generate_password_hash(current_password)
                cursor.execute(f"UPDATE {table_name} SET password_hash = %s WHERE {id_col} = %s", (new_hash, user_id))
                print(f"  Hashed password for {user_id}")
                
        conn.commit()
        print("Password migration completed successfully.")
        
    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
    finally:
        if 'cursor' in locals() and cursor:
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == "__main__":
    migrate_passwords()
