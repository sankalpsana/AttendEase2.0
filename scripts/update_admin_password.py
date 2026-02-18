from werkzeug.security import generate_password_hash
from app import get_db_connection
import sys

def update_admin_password():
    print("Updating admin password...")
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Generate hash for 'admin123'
        hashed_password = generate_password_hash('admin123')
        
        # Update the admin user
        cursor.execute("UPDATE admin SET password_hash = %s WHERE admin_id = 'admin'", (hashed_password,))
        conn.commit()
        
        if cursor.rowcount > 0:
            print("Successfully updated admin password to hash.")
        else:
            print("Admin user 'admin' not found.")
            
    except Exception as e:
        print(f"Error updating password: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    update_admin_password()
