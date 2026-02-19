from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required
from app.db import get_db_connection
from app.decorators import student_required
import cv2
import numpy as np
import base64
import pickle
import face_recognition
from app.services.recognition import clear_cache

student = Blueprint('student', __name__)

@student.route('/student-dashboard')
@login_required
@student_required
@student_required
def student_dashboard():
    # Enforce facial registration
    if session.get('require_face_registration'):
        return redirect(url_for('student.register_facial_data'))

    student_id = session.get('id')
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch student's classes and attendance
        cursor.execute("""
                       SELECT s.subject_id,
                              s.subject_name,
                              COUNT(a.attendance_id)AS total_classes,
                              SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_classes FROM attendance a JOIN subjects s ON a.subject_id = s.subject_id JOIN students st ON a.roll_number = st.roll_number -- Join with students table
                       WHERE a.roll_number = %s -- Filter by roll number
                       GROUP BY s.subject_id, s.subject_name;
                       """, (student_id,))
        classes = cursor.fetchall()
        print(classes)

        # Calculate attendance percentage for each class
        for class_info in classes:
            if class_info['total_classes'] > 0:
                class_info['attendance_percentage'] = round((class_info['present_classes'] / class_info['total_classes']) * 100, 2)
            else:
                class_info['attendance_percentage'] = 0

        # Fetch detailed attendance records for each class
        for class_info in classes:
            cursor.execute("""
                SELECT date, status
                FROM attendance
                WHERE roll_number = %s AND subject_id = %s
                ORDER BY date DESC
            """, (student_id, class_info['subject_id']))
            class_info['attendance_records'] = cursor.fetchall()

        # Calculate overall attendance percentage
        total_classes = sum(class_info['total_classes'] for class_info in classes)
        present_classes = sum(class_info['present_classes'] for class_info in classes)
        if total_classes > 0:
            overall_attendance_percentage = round((present_classes / total_classes) * 100, 2)
        else:
            overall_attendance_percentage = 0

    finally:
        cursor.close()
        conn.close()

    return render_template('student_dashboard.html',
                          user_name=session.get('name'),
                          classes=classes,
                          present_percentage=overall_attendance_percentage,
                          absent_percentage=100 - overall_attendance_percentage)


@student.route('/register-facial-data', methods=['GET', 'POST'])
@login_required
def register_facial_data():
    if request.method == 'GET':
        return render_template('register_facial_data.html')

    # Handle facial data registration
    data = request.get_json()
    image_data = data.get('image')  # Base64-encoded image

    # Decode the image and extract facial encoding
    try:
        image_data = image_data.split(",")[1]
        image = base64.b64decode(image_data)
        np_image = np.frombuffer(image, dtype=np.uint8)
        img = cv2.imdecode(np_image, cv2.IMREAD_COLOR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) # Convert to RGB for face_recognition

        # Extract facial encoding
        face_encodings = face_recognition.face_encodings(img)
        if not face_encodings:
            return jsonify({'success': False, 'message': 'No face detected in the image.'}), 400

        facial_encoding = face_encodings[0].tolist()
        encoding_blob = pickle.dumps(facial_encoding)

        # Update the user's facial encoding in the database
        user_id = session.get('id')
        user_role = session.get('role')

        conn = get_db_connection()
        cursor = conn.cursor()

        if user_role == 'student':
            cursor.execute("UPDATE students SET facial_embedding = %s WHERE roll_number = %s", (encoding_blob, user_id))
        elif user_role == 'faculty':
            cursor.execute("UPDATE faculty SET facial_embedding = %s WHERE faculty_id = %s", (encoding_blob, user_id))

        conn.commit()
        cursor.close()
        conn.close()

        # Invalidate all cache since we don't know the section easily
        clear_cache()

        # Update session to indicate registration is complete
        session['require_face_registration'] = False

        return jsonify({'success': True, 'message': 'Facial data registered successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing facial data: {e}'}), 500
