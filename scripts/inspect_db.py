import mysql.connector

dbconfig = {
    'host': 'localhost',
    'user': 'root',
    'password': 'password',
    'database': 'attendance_system'
}

def check_columns():
    try:
        conn = mysql.connector.connect(**dbconfig)
        cursor = conn.cursor()
        
        tables = ['students', 'faculty']
        for table in tables:
            cursor.execute(f"DESCRIBE {table}")
            columns = cursor.fetchall()
            for col in columns:
                if col[0] == 'facial_embedding':
                    print(f"Table {table}, Column facial_embedding Type: {col[1]}")
                    
        conn.close()
    except mysql.connector.Error as err:
        print(f"Error: {err}")

if __name__ == "__main__":
    check_columns()
