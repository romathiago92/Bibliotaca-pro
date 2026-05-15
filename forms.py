from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectMultipleField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, Optional, NumberRange


class RegisterForm(FlaskForm):
    username = StringField('Usuario', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    confirm_password = PasswordField(
        'Confirmar', validators=[DataRequired(), EqualTo('password')]
    )
    submit = SubmitField('Registrarse')


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Contraseña', validators=[DataRequired()])
    submit = SubmitField('Iniciar Sesión')


class BookForm(FlaskForm):
    title = StringField('Título', validators=[DataRequired()])
    author = StringField('Autor', validators=[DataRequired()])
    isbn = StringField('ISBN (Opcional)', validators=[Optional()])
    copies = IntegerField(
        'Copias', validators=[DataRequired(), NumberRange(min=1)], default=1
    )
    genres = SelectMultipleField('Géneros', coerce=int, validators=[DataRequired()], choices=[])
    submit = SubmitField('Guardar Libro')
