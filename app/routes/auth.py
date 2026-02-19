from flask import Blueprint, render_template, redirect, url_for, flash, session, request
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
from app.db import get_db_connection
from app.models import User
from app.forms import LoginForm

auth = Blueprint('auth', __name__)

@auth.route('/', methods=['GET', 'POST'])
def landing():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    return render_template('landing.html')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        role = form.role.data

        conn = get_db_connection()
        cursor = conn.cursor()
        user = None

        try:
            # Check if user is a student
            if role == 'student':
                cursor.execute("SELECT roll_number, name, password_hash, facial_embedding FROM students WHERE roll_number = %s", (username,))
                student = cursor.fetchone()
                if student and check_password_hash(student['password_hash'], password):
                    user = User(student['roll_number'], 'student', student['name'])
                    # Check if facial embedding exists
                    if student.get('facial_embedding') is None:
                        session['require_face_registration'] = True
                    else:
                        session['require_face_registration'] = False

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
            if cursor:
                cursor.close()
            if conn:
                conn.close()

        if user:
            login_user(user)
            # Store user details in session
            session['id'] = user.id
            session['role'] = user.role
            session['name'] = user.name
            
            # Use dot notation for blueprints if dashboard is in a blueprint? 
            # Ideally 'dashboard' shouldn't be in auth, but if we have a main blueprint...
            # For now, let's assume 'main.dashboard' or just 'dashboard' if we define it at app level or auth level.
            # I will put dashboard in auth for now as a generic router.
            if session.get('require_face_registration'):
                flash('Please register your facial data to continue.', 'warning')
                return redirect(url_for('student.register_facial_data'))

            return redirect(url_for('auth.dashboard')) 
        else:
            flash('Invalid username, password, or role!', 'danger')
    
    return render_template('login.html', form=form)

@auth.route('/dashboard')
@login_required
def dashboard():
    user_role = session.get('role')
    user_name = session.get('name')
    user_id = session.get('id')
    
    if session.get('require_face_registration'):
        flash('Please register your facial data to continue.', 'warning')
        return redirect(url_for('student.register_facial_data'))

    if user_role == 'student':
        # This needs to be updated to check for facial data
        return redirect(url_for('student.student_dashboard'))
    elif user_role == 'faculty':
         # Assuming faculty dashboard is a template, not a route, but the code says 'faculty_dashboard.html'
         # But wait, app.py had: return render_template(f'{user_role}_dashboard.html', ...)
         # So safe to render here.
         pass
    
    return render_template(f'{user_role}_dashboard.html', user_name=user_name, user_id=user_id)

@auth.route('/test-camera')
def test_camera():
    return render_template('test_camera.html')


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('auth.login'))

@auth.route('/dev-login')
def dev_login():
    """Temporary route to bypass login for testing mark_attendance."""
    user = User('f001', 'faculty', 'Dev Faculty')
    login_user(user)
    session['id'] = 'f001'
    session['role'] = 'faculty'
    session['name'] = 'Dev Faculty'
    # 'faculty.mark_attendance' needs to be defined
    return redirect(url_for('faculty.mark_attendance', faculty_id='f001', subject_id='1', section_name='A'))
