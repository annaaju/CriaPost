from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, EqualTo, Email

class LoginForm(FlaskForm):
    username = StringField("username", validators=[DataRequired()])
    password = PasswordField("password", validators=[DataRequired()])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired(), EqualTo('confirm', message='Passwords must match')])
    confirm = PasswordField('Repeat Password')
    email = StringField('Email', validators=[DataRequired(), Email()])
    name = StringField('Name', validators=[DataRequired()])
    submit = SubmitField('Register')

class PostForm(FlaskForm):
    content = TextAreaField('Crie um novo post:', validators=[DataRequired()])
    submit = SubmitField('Publicar')

class ChatForm(FlaskForm):
    prompt = StringField('Assunto', validators=[DataRequired()])
    submit = SubmitField('Obter Dicas')

class FormFactory:
    @staticmethod
    def create_form(form_type):
        if form_type == 'login':
            return LoginForm()
        elif form_type == 'register':
            return RegisterForm()
        elif form_type == 'post':
            return PostForm()
        elif form_type == 'chat':
            return ChatForm()
        else:
            raise ValueError(f"Form type {form_type} is not recognized")
