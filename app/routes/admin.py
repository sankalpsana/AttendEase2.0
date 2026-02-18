from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from flask_login import login_required, current_user
from app.db import get_db_connection
from app.forms import CreateSectionForm
from werkzeug.security import generate_password_hash
import re
import os
import cv2
import base64
import pickle
import numpy as np
import face_recognition
from PIL import Image
from io import BytesIO
from app.services.recognition import clear_cache

admin = Blueprint('admin', __name__)
UPLOAD_FOLDER = 'Faces' # Should be in config or consistent path. Ideally app/static/Faces? or just Faces in root. 
# Current app uses 'Faces' in root. We should probably keep it there for now or fix path.
# Assuming root run context, 'Faces' is fine.

@admin.route('/manage-faculty', methods=['GET', 'POST'])
def manage_faculty():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT faculty_id, name, email FROM faculty")
        faculty_data = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    faculty_list = []
    for faculty in faculty_data:
        faculty_list.append({
            'faculty_id': faculty['faculty_id'],
            'name': faculty['name'],
            'email': faculty['email']
        })

    return render_template('faculty_management.html', faculty_list=faculty_list, user_name=session.get('name'))


@admin.route('/fetch-faculty', methods=['GET'])
def fetch_faculty():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT faculty_id, name, email FROM faculty")
        faculty_data = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    faculty_list = []
    for faculty in faculty_data:
        faculty_list.append({
            'faculty_id': faculty['faculty_id'],
            'name': faculty['name'],
            'email': faculty['email']
        })

    return jsonify({'success': True, 'faculty': faculty_list})


@admin.route('/add-faculty', methods=['POST'])
def add_faculty():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403
    data = request.get_json()
    faculty_id = data.get('faculty_id')
    full_name = data.get('fullName')
    email = data.get('email')
    password = data.get('password')

    if not faculty_id or not full_name or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required'})

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return jsonify({'success': False, 'message': 'Invalid email address'})

    hashed_password = generate_password_hash(password)

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO faculty (faculty_id, name, email, password_hash) VALUES (%s, %s, %s, %s)",
                       (faculty_id, full_name, email, hashed_password))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


@admin.route('/delete-faculty/<faculty_id>', methods=['DELETE'])
def delete_faculty(faculty_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM faculty WHERE faculty_id = %s", [faculty_id])
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})
    finally:
        cursor.close()
        conn.close()


@admin.route('/update-faculty', methods=['POST'])
@login_required
def update_faculty():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

    try:
        data = request.json
        original_faculty_id = data.get('originalFacultyId')
        full_name = data.get('fullName')
        email = data.get('email')
        
        # Not updating ID or password here for simplicity
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE faculty 
                SET name = %s, email = %s
                WHERE faculty_id = %s
            """, (full_name, email, original_faculty_id))
            conn.commit()
            
            return jsonify({'success': True, 'message': 'Faculty updated successfully!'})
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin.route('/manage-subjects')
@login_required
def manage_subjects():
    if session.get('role') != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('auth.dashboard')) # Updated to blueprint

    return render_template('manage_subjects.html', user_name=session.get('name'))


@admin.route('/add-subject', methods=['POST'])
@login_required
def add_subject():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

    try:
        data = request.get_json()
        subject_name = data.get('subject_name')

        if not subject_name:
            return jsonify({'success': False, 'message': 'Subject name is required!'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT subject_name FROM subjects WHERE subject_name = %s", (subject_name,))
            existing_subject = cursor.fetchone()
            if existing_subject:
                return jsonify({'success': False, 'message': 'Subject already exists!'}), 400

            cursor.execute("INSERT INTO subjects (subject_name) VALUES (%s)", (subject_name,))
            conn.commit()

            return jsonify({'success': True, 'message': 'Subject added successfully!'})

        finally:
            cursor.close()
            conn.close()

    except Exception as err:
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500


@admin.route('/fetch-subjects', methods=['GET'])
@login_required
def fetch_subjects():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT subject_id, subject_name FROM subjects")
            subjects = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

        return jsonify({'success': True, 'subjects': subjects})

    except Exception as err:
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500


@admin.route('/delete-subject/<int:subject_id>', methods=['DELETE'])
@login_required
def delete_subject(subject_id):
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM subjects WHERE subject_id = %s", (subject_id,))
            conn.commit()
            return jsonify({'success': True, 'message': 'Subject deleted successfully!'})
        finally:
            cursor.close()
            conn.close()
    
    except Exception as err:
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500


@admin.route('/manage-sections', methods=['GET', 'POST'])
@login_required
def manage_sections():
    if session.get('role') != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('auth.dashboard'))

    form = CreateSectionForm()
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT section_name FROM sections")
        sections = cursor.fetchall()

        if form.validate_on_submit():
            section_name = form.section_name.data

            cursor.execute("SELECT section_name FROM sections WHERE section_name = %s", (section_name,))
            existing_section = cursor.fetchone()
            if existing_section:
                flash('Section already exists!', 'danger')
            else:
                cursor.execute("INSERT INTO sections (section_name) VALUES (%s)", (section_name,))
                conn.commit()
                flash('Section created successfully!', 'success')
                return redirect(url_for('admin.manage_sections'))
    finally:
        cursor.close()
        conn.close()
    return render_template('manage_sections.html', form=form, sections=sections)


@admin.route('/add-section', methods=['POST'])
@login_required
def add_section():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

    try:
        data = request.get_json()
        section_name = data.get('section_name')

        if not section_name:
            return jsonify({'success': False, 'message': 'Section name is required!'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT section_name FROM sections WHERE section_name = %s", (section_name,))
            existing_section = cursor.fetchone()
            if existing_section:
                return jsonify({'success': False, 'message': 'Section already exists!'}), 400

            cursor.execute("INSERT INTO sections (section_name) VALUES (%s)", (section_name,))
            conn.commit()
            return jsonify({'success': True, 'message': 'Section added successfully!'})
        finally:
            cursor.close()
            conn.close()

    except Exception as err:
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500


@admin.route('/delete-section/<section_name>', methods=['POST'])
@login_required
def delete_section(section_name):
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM sections WHERE section_name = %s", (section_name,))
            conn.commit()
            flash('Section deleted successfully!', 'success')
            return redirect(url_for('admin.manage_sections'))
        finally:
            cursor.close()
            conn.close()

    except Exception as err:
        flash(f'Error deleting section: {err}', 'danger')
        return redirect(url_for('admin.manage_sections'))


@admin.route('/manage-students')
@login_required
def manage_students():
    if session.get('role') != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('auth.dashboard'))

    return render_template('manage_students.html', user_name=session.get('name'))


@admin.route('/fetch-students', methods=['GET'])
def fetch_students():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name, roll_number, email, section_name FROM students")
            students = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

        return jsonify({"success": True, "students": students})

    except Exception as e:
        print("Error:", e)
        return jsonify({"success": False, "message": str(e)}), 500


@admin.route('/delete-student/<roll_number>', methods=['DELETE'])
def delete_student(roll_number):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM students WHERE roll_number = %s", (roll_number,))
            conn.commit()
            
            # Invalidate all cache for simplicity
            clear_cache()

            return jsonify({"success": True, "message": "Student deleted successfully"})
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@admin.route('/update-student', methods=['POST'])
@login_required
def update_student():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

    try:
        data = request.json
        original_roll_number = data.get('originalRollNumber')
        full_name = data.get('fullName')
        email = data.get('email')
        section_name = data.get('sectionName')
        
        # We are not updating roll number or photo for now as per request/complexity
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE students 
                SET name = %s, email = %s, section_name = %s
                WHERE roll_number = %s
            """, (full_name, email, section_name, original_roll_number))
            conn.commit()
            
            # Invalidate cache
            clear_cache(section_name)
            
            return jsonify({'success': True, 'message': 'Student updated successfully!'})
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@admin.route('/add-student', methods=['POST'])
@login_required
def add_student():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

    try:
        data = request.json
        full_name = data['fullName']
        roll_number = data['rollNumber']
        email = data['email']
        password = data['password']
        hashed_password = generate_password_hash(password)
        section_name = data['sectionName']
        photo_base64 = data['photo']

        # Sanitize roll number for filename usage
        safe_roll_number = "".join([c for c in roll_number if c.isalnum() or c in ('-', '_')])
        if not safe_roll_number:
            safe_roll_number = "unknown_student"

        photo_base64 = photo_base64.split(",")[1]
        photo_bytes = base64.b64decode(photo_base64)  # Decode only once

        image_path = None
        cropped_image_path = None
        
        # Ensure UPLOAD_FOLDER exists
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)

        try:  # Image processing try block
            image = Image.open(BytesIO(photo_bytes))
            image = np.array(image)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) # Convert RGB (PIL) to BGR (OpenCV)

            image_filename = f"{safe_roll_number}.jpg"
            image_path = os.path.join(UPLOAD_FOLDER, image_filename)
            cv2.imwrite(image_path, image)  # Save the original image

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)  # Use gray for face detection
            faces = face_recognition.face_locations(gray)  

            if len(faces) > 0:
                (top, right, bottom, left) = faces[0]  # Get face coordinates
                face_image = image[top:bottom, left:right]  # Correct slicing order

                crop_file_name = f"{safe_roll_number}_face.jpg"
                cropped_image_path = os.path.join(UPLOAD_FOLDER, crop_file_name)
                cv2.imwrite(cropped_image_path, face_image)

                # Use the in-memory face_image directly
                img_rgb = cv2.cvtColor(face_image, cv2.COLOR_BGR2RGB)

                try:
                    encodings = face_recognition.face_encodings(img_rgb)
                    encodings = np.array(encodings, dtype=np.float64)
                    if len(encodings) > 0:
                        encode = encodings[0]
                        encoding_blob = pickle.dumps(encode)
                    else:
                        if image_path and os.path.exists(image_path): os.remove(image_path)
                        if cropped_image_path and os.path.exists(cropped_image_path): os.remove(cropped_image_path)
                        return jsonify({"success": False, "message": "No face detected in cropped image."}), 400
                except Exception as e:
                    print(f"Encoding Error: {e}")
                    if image_path and os.path.exists(image_path): os.remove(image_path)
                    if cropped_image_path and os.path.exists(cropped_image_path): os.remove(cropped_image_path)
                    return jsonify({"success": False, "message": "Error encoding face."}), 500

                if image_path and os.path.exists(image_path): os.remove(image_path) 

            else:
                if image_path and os.path.exists(image_path): os.remove(image_path)
                return jsonify({"success": False, "message": "No face detected in the uploaded image."}), 400

        except (FileNotFoundError, OSError, IOError, Exception) as e: 
            print(f"Image Error: {e}")
            try:
                if image_path and os.path.exists(image_path): os.remove(image_path)
            except:
                pass
            return jsonify({"success": False, "message": f"Error processing image: {str(e)}"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            query = """
                    INSERT INTO students (name, roll_number, email, password_hash, section_name, facial_embedding)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """
            cursor.execute(query, (full_name, roll_number, email, hashed_password, section_name, encoding_blob))
            conn.commit()
            
            # Invalidate cache for this section
            clear_cache(section_name)

            return jsonify({"success": True, "message": "Student added successfully!"})
        finally:
            cursor.close()
            conn.close()

    except Exception as e: 
        print(f"General Error: {e}")
        return jsonify({"success": False, "message": f"Failed to add student: {str(e)}"}), 500

@admin.route('/fetch-sections', methods=['GET'])
@login_required
def fetch_sections():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT section_name FROM sections")
        sections = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'sections': sections})

    except Exception as err:
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500

@admin.route('/fetch-section-details', methods=['GET'])
@login_required
def fetch_section_details():
    section_name = request.args.get('section_name')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch subjects and faculty for the section
        cursor.execute("""
                       SELECT s.subject_id, s.subject_name, f.name AS faculty_name
                       FROM faculty_subjects fs
                                JOIN subjects s ON fs.subject_id = s.subject_id
                                JOIN faculty f ON fs.faculty_id = f.faculty_id
                       WHERE fs.section_name = %s
                       """, (section_name,))
        subjects = cursor.fetchall()

        # Fetch available subjects
        cursor.execute("SELECT subject_id, subject_name FROM subjects")
        available_subjects = cursor.fetchall()

        # Fetch available faculty
        cursor.execute("SELECT faculty_id, name FROM faculty")
        available_faculty = cursor.fetchall()

    finally:
        cursor.close()
        conn.close()

    return jsonify({
        'success': True,
        'subjects': subjects,
        'available_subjects': available_subjects,
        'available_faculty': available_faculty,
    })

@admin.route('/assign-subject', methods=['POST'])
@login_required
def assign_subject():
    data = request.get_json()
    section_name = data.get('section_name')
    subject_id = data.get('subject_id')
    faculty_id = data.get('faculty_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
                       INSERT INTO faculty_subjects (faculty_id, subject_id, section_name)
                       VALUES (%s, %s, %s)
                       """, (faculty_id, subject_id, section_name))
        conn.commit()
        return jsonify({'success': True})
    except Exception as err:
        return jsonify({'success': False, 'message': str(err)})
    finally:
        cursor.close()
        conn.close()

@admin.route('/remove-subject', methods=['POST'])
@login_required
def remove_subject():
    data = request.get_json()
    section_name = data.get('section_name')
    subject_id = data.get('subject_id')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
                       DELETE
                       FROM faculty_subjects
                       WHERE section_name = %s
                         AND subject_id = %s
                       """, (section_name, subject_id))
        conn.commit()
        return jsonify({'success': True})
    except Exception as err:
        return jsonify({'success': False, 'message': str(err)})
    finally:
        cursor.close()
        conn.close()

@admin.route('/admin-analytics')
def analytics_page():
    username = session.get('name')
    user_role = session.get('role')
    user_id = session.get('id')
    return render_template('admin_analytics.html', username=username, user_role=user_role, user_id=user_id)

@admin.route('/api/subject-attendance', methods=['GET'])
def get_subject_attendance():
    section_name = request.args.get('section')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch subject-wise average attendance for the given section
        cursor.execute("""
            SELECT s.subject_name, AVG(CASE WHEN a.status = 'Present' THEN 100 ELSE 0 END) AS attendance_percentage
            FROM attendance a
            JOIN subjects s ON a.subject_id = s.subject_id
            JOIN students st ON a.roll_number = st.roll_number
            WHERE st.section_name = %s
            GROUP BY s.subject_name
        """, (section_name,))
        subject_attendance = cursor.fetchall()

        # Prepare data for the chart
        return jsonify(subject_attendance)
    except Exception as err:
        return jsonify({
            'success': False,
            'message': f'Database error: {err}'
        })
    finally:
        cursor.close()
        conn.close()


@admin.route('/api/analytics')
def analytics():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch attendance overview data (monthly attendance percentages)
        cursor.execute("""
            SELECT TO_CHAR(date, 'YYYY-MM') AS month, AVG(CASE WHEN status = 'Present' THEN 100 ELSE 0 END) AS attendance_percentage
            FROM attendance
            GROUP BY TO_CHAR(date, 'YYYY-MM')
            ORDER BY month
        """)
        attendance_overview = cursor.fetchall()

        # Fetch section-wise attendance data
        cursor.execute("""
            SELECT s.section_name, AVG(CASE WHEN a.status = 'Present' THEN 100 ELSE 0 END) AS attendance_percentage
            FROM attendance a
            JOIN students s ON a.roll_number = s.roll_number
            GROUP BY s.section_name
        """)
        section_attendance = cursor.fetchall()

    finally:
        cursor.close()
        conn.close()

    # Format data for the frontend
    data = {
        'attendance_overview': {
            'labels': [row['month'] for row in attendance_overview],
            'data': [row['attendance_percentage'] for row in attendance_overview],
        },
        'section_attendance': {
            'labels': [row['section_name'] for row in section_attendance],
            'data': [row['attendance_percentage'] for row in section_attendance],
        }
    }

    return jsonify(data)
