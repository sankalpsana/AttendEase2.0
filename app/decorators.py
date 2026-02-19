from functools import wraps
from flask import session, abort, redirect, url_for, flash


def role_required(*roles):
    """
    Decorator that restricts access to users with the specified role(s).
    Usage: @role_required('admin') or @role_required('admin', 'faculty')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_role = session.get('role')
            if user_role not in roles:
                flash('You do not have permission to access this page.', 'danger')
                return redirect(url_for('auth.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def admin_required(f):
    """Restricts access to admin users only."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def faculty_required(f):
    """Restricts access to faculty users only."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'faculty':
            flash('Faculty access required.', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return decorated_function


def student_required(f):
    """Restricts access to student users only."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'student':
            flash('Student access required.', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return decorated_function
