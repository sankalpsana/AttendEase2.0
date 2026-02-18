import mysql.connector
import pickle
import numpy as np

dbconfig = {
    'host': 'localhost',
    'user': 'root',
    'password': 'password',
    'database': 'attendance_system'
}

def verify_blobs():
    try:
        conn = mysql.connector.connect(**dbconfig)
        cursor = conn.cursor(dictionary=True)
        
        # 1. Create dummy data
        test_roll_number = 'TEST_12345'
        original_embedding = np.random.rand(128)
        pickled_data = pickle.dumps(original_embedding)
        
        print(f"Original array shape: {original_embedding.shape}")
        print(f"Pickled data size: {len(pickled_data)} bytes")
        
        # 2. Insert into DB
        # Note: 'students' table has foreign key constraints on 'section_name', but it's NULLable in create_db.py
        # "section_name VARCHAR(10)," in create_db.py
        
        # Check if student already exists and delete
        cursor.execute("DELETE FROM students WHERE roll_number = %s", (test_roll_number,))
        conn.commit()
        
        print("Inserting test student...")
        query = """
            INSERT INTO students (roll_number, name, email, password_hash, facial_embedding)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(query, (test_roll_number, 'Test Student', 'test@example.com', 'hashed_pw', pickled_data))
        conn.commit()
        
        # 3. Retrieve from DB
        print("Retrieving test student...")
        cursor.execute("SELECT facial_embedding FROM students WHERE roll_number = %s", (test_roll_number,))
        result = cursor.fetchone()
        
        if result and result['facial_embedding']:
            retrieved_blob = result['facial_embedding']
            print(f"Retrieved blob size: {len(retrieved_blob)} bytes")
            
            # 4. Unpickle
            restored_embedding = pickle.loads(retrieved_blob)
            print(f"Restored array shape: {restored_embedding.shape}")
            
            # 5. Compare
            if np.array_equal(original_embedding, restored_embedding):
                print("SUCCESS: Retrieved embedding matches original.")
            else:
                print("FAILURE: Retrieved embedding does NOT match original.")
        else:
            print("FAILURE: Could not retrieve student or embedding is NULL.")
            
        # 6. Cleanup
        cursor.execute("DELETE FROM students WHERE roll_number = %s", (test_roll_number,))
        conn.commit()
        print("Test student deleted.")
        
        conn.close()
        
    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error: {e}")

if __name__ == "__main__":
    verify_blobs()
