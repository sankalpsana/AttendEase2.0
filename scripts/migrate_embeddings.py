import mysql.connector
import pickle
import numpy as np

dbconfig = {
    'host': 'localhost',
    'user': 'root',
    'password': 'password',
    'database': 'attendance_system'
}

def migrate_table(cursor, table_name, id_column):
    print(f"Migrating {table_name}...")
    
    # 1. Add temporary BLOB column
    try:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN facial_embedding_blob BLOB")
        print("  Added temporary column facial_embedding_blob")
    except mysql.connector.Error as err:
        if err.errno == 1060: # Time for Duplicate column name
             print("  Column facial_embedding_blob already exists, proceeding...")
        else:
             raise err

    # 2. Fetch all records
    cursor.execute(f"SELECT {id_column}, facial_embedding FROM {table_name}")
    rows = cursor.fetchall()

    for row in rows:
        record_id = row[0]
        embedding_text = row[1]
        
        if embedding_text:
            try:
                # Convert TEXT (0.1,0.2,...) to numpy array
                if isinstance(embedding_text, bytes):
                    embedding_text = embedding_text.decode('utf-8')
                
                # Check if it's already pickled (unlikely, but safe)
                # But currently it's TEXT, so it's a string.
                
                # Parse the string
                encoding_list = [float(x) for x in embedding_text.split(',')]
                encoding_array = np.array(encoding_list, dtype=np.float64)
                
                # Pickle it
                embedding_blob = pickle.dumps(encoding_array)
                
                # Update the temporary column
                query = f"UPDATE {table_name} SET facial_embedding_blob = %s WHERE {id_column} = %s"
                cursor.execute(query, (embedding_blob, record_id))
                print(f"  Converted embedding for {record_id}")
                
            except Exception as e:
                print(f"  Failed to convert {record_id}: {e}")
    
    # 3. Drop old column and rename new one
    try:
        cursor.execute(f"ALTER TABLE {table_name} DROP COLUMN facial_embedding")
        print("  Dropped old facial_embedding column")
        
        cursor.execute(f"ALTER TABLE {table_name} CHANGE COLUMN facial_embedding_blob facial_embedding BLOB")
        print("  Renamed facial_embedding_blob to facial_embedding")
        
    except mysql.connector.Error as err:
        print(f"  Error modifying schema for {table_name}: {err}")

def migrate():
    try:
        conn = mysql.connector.connect(**dbconfig)
        cursor = conn.cursor()
        
        migrate_table(cursor, 'students', 'roll_number')
        migrate_table(cursor, 'faculty', 'faculty_id')
        
        conn.commit()
        conn.close()
        print("Migration completed successfully.")
        
    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    migrate()
