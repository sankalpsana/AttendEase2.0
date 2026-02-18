import pickle
import numpy as np
import cv2
import face_recognition
from app.db import get_db_connection

# Global cache for known faces: { section_name: (encodings, ids) }
known_faces_cache = {}

def load_known_students(section_name):
    global known_faces_cache
    if section_name in known_faces_cache:
        return known_faces_cache[section_name]

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch students in the specified section
        cursor.execute("""
                       SELECT roll_number, facial_embedding
                       FROM students
                       WHERE section_name = %s
                       """, (section_name,))
        students = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    known_face_encodings = []
    known_face_ids = []

    for student in students:
        if student['facial_embedding']:
            try:
                # Decode the facial embedding bytes
                known_face_encodings.append(pickle.loads(student['facial_embedding']))
                known_face_ids.append(student['roll_number'])
            except (ValueError, pickle.PickleError) as e:
                print(f"Error decoding facial embedding for student {student['roll_number']}: {e}")
            except AttributeError as e:
                print(f"Error processing facial embedding for student {student['roll_number']}: {e}")

    # Cache the results
    known_faces_cache[section_name] = (known_face_encodings, known_face_ids)
    return known_face_encodings, known_face_ids

def clear_cache(section_name=None):
    global known_faces_cache
    if section_name:
        if section_name in known_faces_cache:
            del known_faces_cache[section_name]
    else:
        known_faces_cache.clear()
