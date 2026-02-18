import re
import pickle
from io import BytesIO
from PIL import Image
from flask import Flask, render_template, redirect, url_for, flash, session, request, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired
# import mysql.connector
# from mysql.connector import pooling
import db  # Use our new DB abstraction
import base64
import face_recognition
import numpy as np
import os
import subprocess
import cv2
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import SocketIO, emit

load_dotenv()
# from pyngrok import ngrok
# import pyqrcode
# import png
# from pyqrcode import QRCode

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*")

# Global cache for known faces: { section_name: (encodings, ids) }
known_faces_cache = {}

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Helper function to get DB connection
def get_db_connection():
    return db.get_db_connection()



# Reset the connection pool
# Get a connection from the pool


# User Model (for Flask-Login)
class User(UserMixin):
    def __init__(self, id, role, name):
        self.id = id  # Roll number or ID number
        self.role = role  # 'student', 'faculty', or 'admin'
        self.name = name  # User's name


class CreateSectionForm(FlaskForm):
    section_name = StringField('Section Name', validators=[DataRequired()])
    submit = SubmitField('Create Section')


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


@socketio.on('process_frame')
def handle_frame(data):
    image_data = data.get('image')  # Base64-encoded image
    section_name = data.get('section_name')

    # Load known students for the current section
    known_face_encodings, known_face_ids = load_known_students(section_name)

    known_face_encodings = [np.array(encoding, dtype=np.float64) for encoding in known_face_encodings]

    try:
        # Decode the image
        image_data = image_data.split(",")[1]
        image = base64.b64decode(image_data)
        np_image = np.frombuffer(image, dtype=np.uint8)
        img = cv2.imdecode(np_image, cv2.IMREAD_COLOR)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) # Convert to RGB for face_recognition
    except Exception as e:
        emit('frame_processed', {'success': False, 'message': f'Error decoding image: {e}'})
        return

    # If no known face encodings are found, return an empty response
    if not known_face_encodings:
        emit('frame_processed', {
            'success': True,
            'faces': [],
            'message': 'No known students found for this section.'
        })
        return

    # Perform facial recognition
    face_locations = face_recognition.face_locations(img)
    face_encodings = face_recognition.face_encodings(img, face_locations)

    faces_info = []

    for face_encoding, face_location in zip(face_encodings, face_locations):
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding)
        face_distances = face_recognition.face_distance(known_face_encodings, face_encoding)

        student_id = "Unknown"

        # If a match is found, get the student ID
        if True in matches:
            best_match_index = np.argmin(face_distances)
            if matches[best_match_index]:
                student_id = known_face_ids[best_match_index]
            print(f'{student_id} found')

        # Append face location and student ID to results
        faces_info.append({
            "location": face_location,  # [top, right, bottom, left]
            "student_id": student_id
        })
        
    emit('frame_processed', {'success': True, 'faces': faces_info})


@app.route('/', methods=['GET', 'POST'])
def landing():
    return render_template('landing.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        role = form.role.data

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            user = None
    
            # Check if user is a student
            if role == 'student':
                cursor.execute("SELECT roll_number, name, password_hash FROM students WHERE roll_number = %s", (username,))
                student = cursor.fetchone()
                if student and check_password_hash(student['password_hash'], password):
                    user = User(student['roll_number'], 'student', student['name'])
    
            # Check if user is faculty
            elif role == 'faculty':
                cursor.execute("SELECT faculty_id, name, password_hash FROM faculty WHERE faculty_id = %s", (username,))
                faculty = cursor.fetchone()
                if faculty and check_password_hash(faculty['password_hash'], password):
                    user = User(faculty['faculty_id'], 'faculty', faculty['name'])
    
            # Check if user is admin
            elif role == 'admin':
                cursor.execute("SELECT admin_id, username, password_hash FROM admin WHERE admin_id = %s", (username,))
                admin = cursor.fetchone()
                if admin and check_password_hash(admin['password_hash'], password):
                    user = User(admin['admin_id'], 'admin', admin['username'])

        except Exception as e:
            print(f"Login error: {e}")
            flash('An error occurred during login.', 'danger')
            return render_template('login.html', form=form)
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()
            if 'conn' in locals() and conn:
                conn.close()

        if user:
            login_user(user)
            # Store user details in session
            session['id'] = user.id
            session['role'] = user.role
            session['name'] = user.name
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username, password, or role!', 'danger')
    
    return render_template('login.html', form=form)



@app.route('/dev-login')
def dev_login():
    """Temporary route to bypass login for testing mark_attendance."""
    # Set up a dummy session for faculty 'f001'
    user = User('f001', 'faculty', 'Dev Faculty')
    login_user(user)
    session['id'] = 'f001'
    session['role'] = 'faculty'
    session['name'] = 'Dev Faculty'
    
    # Redirect to mark_attendance with default test parameters
    return redirect(url_for('mark_attendance', faculty_id='f001', subject_id='1', section_name='A'))


@app.route('/manage-faculty', methods=['GET', 'POST'])
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


@app.route('/fetch-faculty', methods=['GET'])
def fetch_faculty():
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT faculty_id, name, email FROM faculty")
        faculty_data = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    # Debugging: Print the fetched data
    print(faculty_data)

    faculty_list = []
    for faculty in faculty_data:
        faculty_list.append({
            'faculty_id': faculty['faculty_id'],
            'name': faculty['name'],
            'email': faculty['email']
        })

    return jsonify({'success': True, 'faculty': faculty_list})


# Route to add a new faculty member
@app.route('/add-faculty', methods=['POST'])
def add_faculty():
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403
    data = request.get_json()
    faculty_id = data.get('faculty_id')
    full_name = data.get('fullName')
    email = data.get('email')
    password = data.get('password')

    # Validate input data
    if not faculty_id or not full_name or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required'})

    # Check if the email is valid
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


# Route to delete a faculty member by faculty_id
@app.route('/delete-faculty/<faculty_id>', methods=['DELETE'])
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


# User Loader
@login_manager.user_loader
def load_user(id):
    if session.get('id') == id and session.get('role'):
        return User(session.get('id'), session.get('role'), session.get('name'))
    return None


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    role = SelectField('Role', choices=[('admin', 'Admin'), ('faculty', 'Faculty'), ('student', 'Student')],
                       validators=[DataRequired()])
    submit = SubmitField('Login')


def get_face_encoding(image_base64):
    try:
        image_data = base64.b64decode(image_base64.split(",")[1])
        image = Image.open(BytesIO(image_data))
        image = np.array(image)

        face_encodings = face_recognition.face_encodings(image)
        if face_encodings:
            return face_encodings[0].tolist()
        else:
            return None
    except Exception as e:
        print(f"Error processing image: {e}")
        return None


UPLOAD_FOLDER = 'Faces'


@app.route('/add-student', methods=['POST'])
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

        try:  # Image processing try block
            image = Image.open(BytesIO(photo_bytes))
            image = np.array(image)
            image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) # Convert RGB (PIL) to BGR (OpenCV)

            image_filename = f"{safe_roll_number}.jpg"
            image_path = os.path.join(UPLOAD_FOLDER, image_filename)
            cv2.imwrite(image_path, image)  # Save the original image

            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)  # Use gray for face detection
            faces = face_recognition.face_locations(gray)  # No need for extra parameters unless necessary

            if len(faces) > 0:
                (top, right, bottom, left) = faces[0]  # Get face coordinates
                face_image = image[top:bottom, left:right]  # Correct slicing order

                crop_file_name = f"{safe_roll_number}_face.jpg"
                cropped_image_path = os.path.join(UPLOAD_FOLDER, crop_file_name)
                cv2.imwrite(cropped_image_path, face_image)

                # Use the in-memory face_image directly
                # face_image is BGR (from 'image'), need RGB for face_encodings
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

                # Remove the original image after cropping and encoding? 
                # Keeping it might be useful, but the logic previously deleted it.
                if image_path and os.path.exists(image_path): os.remove(image_path) 

            else:
                if image_path and os.path.exists(image_path): os.remove(image_path)
                return jsonify({"success": False, "message": "No face detected in the uploaded image."}), 400

        except (FileNotFoundError, OSError, IOError, Exception) as e:  # Catch potential image processing errors
            print(f"Image Error: {e}")
            try:
                if image_path and os.path.exists(image_path): os.remove(image_path)
            except:
                pass
            return jsonify({"success": False, "message": f"Error processing image: {str(e)}"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()  # No need for dictionary=True if not fetching data
        try:
            query = """
                    INSERT INTO students (name, roll_number, email, password_hash, section_name, facial_embedding)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """
            cursor.execute(query, (full_name, roll_number, email, hashed_password, section_name, encoding_blob))
            conn.commit()
            
            # Invalidate cache for this section
            if section_name in known_faces_cache:
                del known_faces_cache[section_name]

            return jsonify({"success": True, "message": "Student added successfully!"})
        finally:
            cursor.close()
            conn.close()

    except Exception as e:  # Catch database or other errors
        print(f"General Error: {e}")
        return jsonify({"success": False, "message": f"Failed to add student: {str(e)}"}), 500


@app.route('/register-facial-data', methods=['GET', 'POST'])
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
        known_faces_cache.clear()

        return jsonify({'success': True, 'message': 'Facial data registered successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing facial data: {e}'}), 500

'''@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        role = form.role.data

        conn = db_pool.get_connection()
        cursor = conn.cursor(dictionary=True)
        user = None

        # Check if user is a student
        if role == 'student':
            cursor.execute("SELECT roll_number, name, password_hash, facial_embedding FROM students WHERE roll_number = %s", (username,))
            student = cursor.fetchone()
            if student and student['password_hash'] == password:  # Compare plain-text passwords
                user = User(student['roll_number'], 'student', student['name'])
                session['facial_embedding'] = student['facial_embedding']

        # Check if user is faculty
        elif role == 'faculty':
            cursor.execute("SELECT faculty_id, name, password_hash, facial_embedding FROM faculty WHERE faculty_id = %s", (username,))
            faculty = cursor.fetchone()
            if faculty and faculty['password_hash'] == password:  # Compare plain-text passwords
                user = User(faculty['faculty_id'], 'faculty', faculty['name'])
                session['facial_embedding'] = faculty['facial_embedding']

        # Check if user is admin
        elif role == 'admin':
            cursor.execute("SELECT admin_id, username, password_hash FROM admin WHERE admin_id = %s", (username,))
            admin = cursor.fetchone()
            if admin and admin['password_hash'] == password:  # Compare plain-text passwords
                user = User(admin['admin_id'], 'admin', admin['username'])

        cursor.close()
        conn.close()

        if user:
            # If user is admin, skip facial verification
            if user.role == 'admin':
                login_user(user)
                session['id'] = user.id
                session['role'] = user.role
                session['name'] = user.name
                return redirect(url_for('dashboard'))

            # For non-admin users, check if facial data is registered
            if not session.get('facial_embedding'):
                # Redirect to facial data registration page
                login_user(user)
                session['id'] = user.id
                session['role'] = user.role
                session['name'] = user.name
                return redirect(url_for('register_facial_data'))

            # If facial data is registered, proceed to facial verification
            return render_template('facial_verification.html', username=username, role=role)
        else:
            flash('Invalid username, password, or role!', 'danger')

    return render_template('login.html', form=form)'''

'''@app.route('/verify-facial-data', methods=['POST'])
def verify_facial_data():
    data = request.get_json()
    image_data = data.get('image')  # Base64-encoded image
    username = data.get('username')
    role = data.get('role')

    # Fetch the stored facial encoding for the user
    conn = get_db_connection()
    cursor = conn.cursor()

    if role == 'student':
        cursor.execute("SELECT facial_embedding FROM students WHERE roll_number = %s", (username,))
    elif role == 'faculty':
        cursor.execute("SELECT facial_embedding FROM faculty WHERE faculty_id = %s", (username,))

    user = cursor.fetchone()
    cursor.close()
    conn.close()

    if not user or not user['facial_embedding']:
        return jsonify({'success': False, 'message': 'Facial data not found for the user.'}), 404

    stored_encoding = [float(x) for x in user['facial_embedding'].split(',')]

    # Decode the image and extract facial encoding
    try:
        image_data = image_data.split(",")[1]
        image = base64.b64decode(image_data)
        np_image = np.frombuffer(image, dtype=np.uint8)
        img = cv2.imdecode(np_image, cv2.IMREAD_COLOR)

        # Extract facial encoding from the uploaded image
        face_encodings = face_recognition.face_encodings(img)
        if not face_encodings:
            return jsonify({'success': False, 'message': 'No face detected in the image.'}), 400

        uploaded_encoding = face_encodings[0]

        # Compare the uploaded encoding with the stored encoding
        match = face_recognition.compare_faces([stored_encoding], uploaded_encoding)
        if match[0]:
            return jsonify({'success': True, 'message': 'Facial verification successful!'})
        else:
            return jsonify({'success': False, 'message': 'Facial verification failed.'}), 401
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing facial data: {e}'}), 500
'''

@app.route('/fetch-sections', methods=['GET'])
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


@app.route('/fetch-section-details', methods=['GET'])
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


@app.route('/assign-subject', methods=['POST'])
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


@app.route('/remove-subject', methods=['POST'])
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


@app.route('/dashboard')
@login_required
def dashboard():
    user_role = session.get('role')
    user_name = session.get('name')
    user_id = session.get('id')
    if user_role == 'student':
        return redirect('/student-dashboard')
    return render_template(f'{user_role}_dashboard.html', user_name=user_name, user_id=user_id)


@app.route('/manage-subjects')
@login_required
def manage_subjects():
    if session.get('role') != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('dashboard'))

    return render_template('manage_subjects.html', user_name=session.get('name'))


@app.route('/add-subject', methods=['POST'])
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
            # Check if the subject already exists
            cursor.execute("SELECT subject_name FROM subjects WHERE subject_name = %s", (subject_name,))
            existing_subject = cursor.fetchone()
            if existing_subject:
                return jsonify({'success': False, 'message': 'Subject already exists!'}), 400

            # Insert the new subject into the database
            cursor.execute("INSERT INTO subjects (subject_name) VALUES (%s)", (subject_name,))
            conn.commit()

            return jsonify({'success': True, 'message': 'Subject added successfully!'})

        finally:
            cursor.close()
            conn.close()

    except Exception as err:
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500


@app.route('/fetch-subjects', methods=['GET'])
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


@app.route('/delete-subject/<int:subject_id>', methods=['DELETE'])
@login_required
def delete_subject(subject_id):
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Delete the subject from the database
            cursor.execute("DELETE FROM subjects WHERE subject_id = %s", (subject_id,))
            conn.commit()
            return jsonify({'success': True, 'message': 'Subject deleted successfully!'})
        finally:
            cursor.close()
            conn.close()
    
    except Exception as err:
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500


@app.route('/manage-sections', methods=['GET', 'POST'])
@login_required
def manage_sections():
    if session.get('role') != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('dashboard'))

    form = CreateSectionForm()
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch all sections from the database
        cursor.execute("SELECT section_name FROM sections")
        sections = cursor.fetchall()

        if form.validate_on_submit():
            section_name = form.section_name.data

            # Check if the section already exists
            cursor.execute("SELECT section_name FROM sections WHERE section_name = %s", (section_name,))
            existing_section = cursor.fetchone()
            if existing_section:
                flash('Section already exists!', 'danger')
            else:
                # Insert the new section into the database
                cursor.execute("INSERT INTO sections (section_name) VALUES (%s)", (section_name,))
                conn.commit()
                flash('Section created successfully!', 'success')
                return redirect(url_for('manage_sections'))
    finally:
        cursor.close()
        conn.close()
    return render_template('manage_sections.html', form=form, sections=sections)


@app.route('/add-section', methods=['POST'])
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
            # Check if the section already exists
            cursor.execute("SELECT section_name FROM sections WHERE section_name = %s", (section_name,))
            existing_section = cursor.fetchone()
            if existing_section:
                return jsonify({'success': False, 'message': 'Section already exists!'}), 400

            # Insert the new section into the database
            cursor.execute("INSERT INTO sections (section_name) VALUES (%s)", (section_name,))
            conn.commit()
            return jsonify({'success': True, 'message': 'Section added successfully!'})
        finally:
            cursor.close()
            conn.close()

    except Exception as err:
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500


@app.route('/delete-section/<section_name>', methods=['POST'])
@login_required
def delete_section(section_name):
    if session.get('role') != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Delete the section from the database
            cursor.execute("DELETE FROM sections WHERE section_name = %s", (section_name,))
            conn.commit()
            flash('Section deleted successfully!', 'success')
            return redirect(url_for('manage_sections'))
        finally:
            cursor.close()
            conn.close()

    except Exception as err:
        flash(f'Error deleting section: {err}', 'danger')
        return redirect(url_for('manage_sections'))


@app.route('/manage-students')
@login_required
def manage_students():
    if session.get('role') != 'admin':
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('dashboard'))

    return render_template('manage_students.html', user_name=session.get('name'))


@app.route('/fetch-students', methods=['GET'])
def fetch_students():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT name, roll_number, email FROM students")
            students = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

        return jsonify({"success": True, "students": students})

    except Exception as e:
        print("Error:", e)
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/delete-student/<roll_number>', methods=['DELETE'])
def delete_student(roll_number):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM students WHERE roll_number = %s", (roll_number,))
            conn.commit()
            
            # Invalidate all cache for simplicity
            known_faces_cache.clear()

            return jsonify({"success": True, "message": "Student deleted successfully"})
        finally:
            cursor.close()
            conn.close()

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route('/fetch-faculty-classes', methods=['GET'])
@login_required
def fetch_faculty_classes():
    faculty_id = session.get('id')  # Get the logged-in faculty's ID from the session

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch the faculty's assigned classes (subject-section combinations)
        cursor.execute("""
                       SELECT s.subject_id, s.subject_name, fs.section_name
                       FROM faculty_subjects fs
                                JOIN subjects s ON fs.subject_id = s.subject_id
                       WHERE fs.faculty_id = %s
                       """, (faculty_id,))
        classes = cursor.fetchall()

        return jsonify({
            'success': True,
            'classes': classes,
        })
    except Exception as err:
        return jsonify({
            'success': False,
            'message': f'Database error: {err}',
        })
    finally:
        cursor.close()
        conn.close()


@app.route('/mark-attendance', methods=['GET'])
@login_required
def mark_attendance():
    faculty_id = request.args.get('faculty_id')
    subject_id = request.args.get('subject_id')
    section_name = request.args.get('section_name')

    print('for mark-attendance', faculty_id, subject_id, section_name)

    # Fetch students enrolled in the current class
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
                       SELECT s.roll_number, s.name, s.facial_embedding
                       FROM students s
                       WHERE section_name = %s
                       """, (section_name,))
        students = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template('mark_attendance.html', username=session.get('name'), students=students, faculty_id=faculty_id, subject_id=subject_id,
                           section_name=section_name)


'''@app.route('/submit-attendance', methods=['POST'])
def submit_attendance():
    data = request.get_json()
    faculty_id = data.get('faculty_id')
    subject_id = data.get('subject_id')
    section_name = data.get('section_name')
    present_students = data.get('present_students')
    absent_students = data.get('absent_students')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Insert attendance records into the database
        for student_id in present_students:
            print("present",student_id, subject_id, faculty_id)
            cursor.execute("""
                           INSERT INTO attendance (roll_number, subject_id, date, status, faculty_id)
                           VALUES (%s, %s, CURDATE(), 'Present', %s)
                           """, (student_id, subject_id, faculty_id))
            for student_id in absent_students:
                print("Absent", student_id, subject_id, faculty_id)
                cursor.execute("""
                               INSERT INTO attendance (roll_number, subject_id, date, status, faculty_id)
                               VALUES (%s, %s, CURDATE(), 'Absent', %s)
                               """, (student_id, subject_id, faculty_id))

        conn.commit()
        return jsonify({'success': True})
    except Exception as err:
        return jsonify({'success': False, 'message': str(err)})
    finally:
        cursor.close()
        conn.close()'''
@app.route('/submit-attendance', methods=['POST'])
def submit_attendance():
    data = request.get_json()
    faculty_id = data.get('faculty_id')
    subject_id = data.get('subject_id')
    section_name = data.get('section_name')
    present_students = data.get('present_students')
    absent_students = data.get('absent_students')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Insert attendance records into the database
        for student_id in present_students:
            cursor.execute("""
                INSERT INTO attendance (roll_number, subject_id, date, status, faculty_id)
                VALUES (%s, %s, CURRENT_DATE, 'Present', %s)
            """, (student_id, subject_id, faculty_id))

        for student_id in absent_students:
            cursor.execute("""
                INSERT INTO attendance (roll_number, subject_id, date, status, faculty_id)
                VALUES (%s, %s, CURRENT_DATE, 'Absent', %s)
            """, (student_id, subject_id, faculty_id))

        # Remove the substitute assignment after attendance is marked
        cursor.execute("""
            DELETE FROM substitute_assignments
            WHERE substitute_faculty_id = %s AND subject_id = %s AND section_name = %s
        """, (faculty_id, subject_id, section_name))

        conn.commit()
        return jsonify({'success': True})
    except Exception as err:
        return jsonify({'success': False, 'message': str(err)})
    finally:
        cursor.close()
        conn.close()

@app.route('/student-dashboard')
@login_required
def student_dashboard():
    if session.get('role') != 'student':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

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

@app.route('/faculty-attendance')
@login_required
def faculty_attendance():
    if session.get('role') != 'faculty':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

    faculty_id = session.get('id')
    subject_id = request.args.get('subject_id')
    section_name = request.args.get('section_name')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch subject name
        cursor.execute("SELECT subject_name FROM subjects WHERE subject_id = %s", (subject_id,))
        subject = cursor.fetchone()
        subject_name = subject['subject_name']

        # Fetch all students in the section
        cursor.execute("""
            SELECT s.roll_number, s.name
            FROM students s
            WHERE s.section_name = %s
        """, (section_name,))
        students = cursor.fetchall()

        # Fetch attendance data for each student
        for student in students:
            cursor.execute("""
                SELECT COUNT(a.attendance_id) AS total_classes,
                       SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_classes
                FROM attendance a
                WHERE a.roll_number = %s AND a.subject_id = %s
            """, (student['roll_number'], subject_id))
            attendance_data = cursor.fetchone()
            if attendance_data['total_classes'] > 0:
                student['attendance_percentage'] = round((attendance_data['present_classes'] / attendance_data['total_classes']) * 100, 2)
            else:
                student['attendance_percentage'] = 0

            # Fetch detailed attendance records
            cursor.execute("""
                SELECT date, status
                FROM attendance
                WHERE roll_number = %s AND subject_id = %s
                ORDER BY date DESC
            """, (student['roll_number'], subject_id))
            student['attendance_records'] = cursor.fetchall()

        # Calculate overall attendance percentage
        total_classes = sum(student.get('total_classes', 0) for student in students)
        present_classes = sum(student.get('present_classes', 0) for student in students)
        if total_classes > 0:
            overall_attendance_percentage = round((present_classes / total_classes) * 100, 2)
        else:
            overall_attendance_percentage = 0

    finally:
        cursor.close()
        conn.close()

    return render_template('faculty_attendance.html',
                          user_name=session.get('name'),
                          subject_name=subject_name,
                          section_name=section_name,
                          students=students,
                          present_percentage=overall_attendance_percentage,
                          absent_percentage=100 - overall_attendance_percentage)
@app.route('/admin-analytics')
def analytics_page():
    username = session.get('name')
    user_role = session.get('role')
    user_id = session.get('id')
    return render_template('admin_analytics.html', username=username, user_role=user_role, user_id=user_id)

@app.route('/api/subject-attendance', methods=['GET'])
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


@app.route('/api/analytics')
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

@app.route('/assign-substitute', methods=['POST'])
@login_required
def assign_substitute():
    if session.get('role') != 'faculty':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

    data = request.get_json()
    substitute_faculty_id = data.get('substitute_faculty_id')
    subject_id = data.get('subject_id')
    section_name = data.get('section_name')
    date = data.get('date')  # Date for which the substitute is assigned

    original_faculty_id = session.get('id')  # Logged-in faculty is the original faculty

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Insert the substitute assignment into the database
        cursor.execute("""
            INSERT INTO substitute_assignments (original_faculty_id, substitute_faculty_id, subject_id, section_name, date)
            VALUES (%s, %s, %s, %s, %s)
        """, (original_faculty_id, substitute_faculty_id, subject_id, section_name, date))
        conn.commit()

        return jsonify({'success': True, 'message': 'Substitute assigned successfully!'})
    except Exception as err:
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/fetch-substitute-classes', methods=['GET'])
@login_required
def fetch_substitute_classes():
    if session.get('role') != 'faculty':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

    substitute_faculty_id = session.get('id')  # Logged-in faculty is the substitute

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch substitute assignments for the logged-in faculty
        cursor.execute("""
            SELECT sa.id, sa.subject_id, sa.section_name, sa.date, s.subject_name, f.name AS original_faculty_name
            FROM substitute_assignments sa
            JOIN subjects s ON sa.subject_id = s.subject_id
            JOIN faculty f ON sa.original_faculty_id = f.faculty_id
            WHERE sa.substitute_faculty_id = %s
        """, (substitute_faculty_id,))
        substitute_classes = cursor.fetchall()

        return jsonify({'success': True, 'substitute_classes': substitute_classes})
    except Exception as err:
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/fetch-substitute-assignments', methods=['GET'])
@login_required
def fetch_substitute_assignments():
    if session.get('role') != 'faculty':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

    original_faculty_id = session.get('id')  # Logged-in faculty is the original faculty

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch substitute assignments for the logged-in faculty
        cursor.execute("""
            SELECT sa.id, sa.subject_id, sa.section_name, sa.date, s.subject_name, f.name AS substitute_faculty_name
            FROM substitute_assignments sa
            JOIN subjects s ON sa.subject_id = s.subject_id
            JOIN faculty f ON sa.substitute_faculty_id = f.faculty_id
            WHERE sa.original_faculty_id = %s
        """, (original_faculty_id,))
        substitute_assignments = cursor.fetchall()

        return jsonify({'success': True, 'substitute_assignments': substitute_assignments})
    except Exception as err:
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()

@app.route('/fetch-substitute-classes-for-substitute', methods=['GET'])
@login_required
def fetch_substitute_classes_for_substitute():
    if session.get('role') != 'faculty':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403

    substitute_faculty_id = session.get('id')  # Logged-in faculty is the substitute

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Fetch substitute assignments for the logged-in substitute faculty
        cursor.execute("""
            SELECT sa.id, sa.subject_id, sa.section_name, sa.date, s.subject_name, f.name AS original_faculty_name
            FROM substitute_assignments sa
            JOIN subjects s ON sa.subject_id = s.subject_id
            JOIN faculty f ON sa.original_faculty_id = f.faculty_id
            WHERE sa.substitute_faculty_id = %s
        """, (substitute_faculty_id,))
        substitute_classes = cursor.fetchall()

        return jsonify({'success': True, 'substitute_classes': substitute_classes})
    except Exception as err:
        return jsonify({'success': False, 'message': f'Database error: {err}'}), 500
    finally:
        cursor.close()
        conn.close()



@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('login'))

# public_url = ngrok.connect(addr=5000, proto='http').public_url
# 
# url = pyqrcode.create(public_url)
# qr_filename = "myqr.png"
# url.png(qr_filename, scale=6)
# img = Image.open(qr_filename)
# img.show()
# print(" * ngrok URL: " + public_url + " *")

def kill_port(port):
    try:
        # Find the process ID (PID) using the port
        # output format: TCP    0.0.0.0:5000           0.0.0.0:0              LISTENING       1234
        result = subprocess.run(f"netstat -ano | findstr :{port}", shell=True, capture_output=True, text=True)
        if result.stdout:
            lines = result.stdout.strip().split('\n')
            for line in lines:
                parts = line.split()
                if len(parts) >= 5:
                    local_addr = parts[1]
                    pid = parts[-1]
                    # Check if the address actually ends with :port to avoid matching 50000, 15000 etc.
                    if local_addr.endswith(f":{port}") and pid != "0":
                        print(f"Killing process {pid} on port {port}...")
                        subprocess.run(f"taskkill /PID {pid} /F", shell=True)
    except Exception as e:
        print(f"Error killing port {port}: {e}")

if __name__ == '__main__':
    # Kill any process using port 5000 before starting, but only in the main process not the reloader
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        kill_port(5000)
    socketio.run(app, debug=True)
