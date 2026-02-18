from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required
from app.db import get_db_connection

faculty = Blueprint('faculty', __name__)

@faculty.route('/fetch-faculty-classes', methods=['GET'])
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


@faculty.route('/analytics-dashboard')
@login_required
def analytics_dashboard():
    if session.get('role') != 'faculty':
        return jsonify({'success': False, 'message': 'Unauthorized access!'}), 403
    return render_template('faculty_analytics_dashboard.html', user_name=session.get('name'))



@faculty.route('/mark-attendance', methods=['GET'])
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


@faculty.route('/submit-attendance', methods=['POST'])
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


@faculty.route('/faculty-attendance')
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


@faculty.route('/assign-substitute', methods=['POST'])
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

@faculty.route('/fetch-substitute-classes', methods=['GET'])
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

@faculty.route('/fetch-substitute-assignments', methods=['GET'])
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

@faculty.route('/fetch-substitute-classes-for-substitute', methods=['GET'])
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
