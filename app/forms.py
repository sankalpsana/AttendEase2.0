from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectField
from wtforms.validators import DataRequired

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    role = SelectField('Role', choices=[('admin', 'Admin'), ('faculty', 'Faculty'), ('student', 'Student')],
                       validators=[DataRequired()])
    submit = SubmitField('Login')

class CreateSectionForm(FlaskForm):
    section_name = StringField('Section Name', validators=[DataRequired()])
    submit = SubmitField('Create Section')
