from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from models.forms import FormFactory
from flask_login import current_user, login_required, LoginManager, login_user, logout_user, UserMixin
from datetime import datetime
from pytz import timezone, utc
from flask_migrate import Migrate
from openai import OpenAI
import logging
from functools import wraps

# Configuração básica de logging
logging.basicConfig(level=logging.DEBUG)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///storage.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'nunca-saberá'
db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Configuração da API do OpenAI
client = OpenAI(api_key="chave")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String, unique=True)
    password = db.Column(db.String)
    name = db.Column(db.String)
    email = db.Column(db.String, unique=True)

    def __init__(self, username, password, name, email):
        self.username = username
        self.password = password
        self.name = name
        self.email = email

    def __repr__(self):
        return "<User %r>" % self.username

class Post(db.Model):
    __tablename__ = "posts"
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    user = db.relationship('User', foreign_keys=[user_id])

    def __init__(self, content, user_id):
        self.content = content
        self.user_id = user_id

    def __repr__(self):
        return "<Post %r>" % self.id

# Observer
class Subject:
    def __init__(self):
        self._observers = []

    def attach(self, observer):
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer):
        try:
            self._observers.remove(observer)
        except ValueError:
            pass

    def notify(self, message):
        for observer in self._observers:
            observer.update(message)

class Observer:
    def update(self, message):
        raise NotImplementedError

class AdminObserver(Observer):
    def update(self, message):
        print(f"Admin Notification: {message}")

post_notifier = Subject()
admin_observer = AdminObserver()
post_notifier.attach(admin_observer)

# Decorator
def log_login_attempts(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' in request.form:
            username = request.form['username']
            logging.info(f"Tentativa de login para o usuário: {username}")
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    form = FormFactory.create_form('post')
    posts = Post.query.order_by(Post.created_at.desc()).all()

    def get_local_time(utc_time):
        local_timezone = timezone('America/Sao_Paulo')
        local_time = utc_time.replace(tzinfo=utc).astimezone(local_timezone)
        return local_time

    return render_template('index.html', form=form, posts=posts, current_user=current_user, get_local_time=get_local_time)

@app.route('/auth', methods=["GET", "POST"])
@log_login_attempts
def auth():
    login_form = FormFactory.create_form('login')
    register_form = FormFactory.create_form('register')
    active_form = 'login'

    if 'login' in request.form:
        active_form = 'login'
        if login_form.validate_on_submit():
            username = login_form.username.data
            password = login_form.password.data
            user = User.query.filter_by(username=username, password=password).first()
            if user:
                login_user(user)
                session['username'] = username
                session['user_id'] = user.id
                return redirect(url_for('index'))
            else:
                flash('Credenciais inválidas. Tente novamente.', 'danger')
        else:
                for field, errors in login_form.errors.items():
                    for error in errors:
                        flash(f'Erro no campo "{field}": {error}', 'danger')
    elif 'register' in request.form:
        active_form = 'register'
        if register_form.validate_on_submit():
            username = register_form.username.data
            password = register_form.password.data
            email = register_form.email.data
            name = register_form.name.data
            if User.query.filter_by(username=username).first() is not None:
                flash('Esse Username já existe. Escolha outro.', 'danger')
            elif User.query.filter_by(email=email).first() is not None:
                flash('Esse Email já foi cadastrado. Use outro email.', 'danger')
            else:
                new_user = User(username, password, name, email)
                db.session.add(new_user)
                db.session.commit()
                flash('Cadastro realizado com sucesso! Você já pode fazer login.', 'success')
                return redirect(url_for('auth'))
        else:
                for field, errors in register_form.errors.items():
                    for error in errors:
                        flash(f'Erro no campo "{field}": {error}', 'danger',)

    return render_template('auth.html', login_form=login_form, register_form=register_form, active_form=active_form)

@app.route('/logout')
def logout():
    logout_user()
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/create_post', methods=['POST'])
def create_post():
    form = FormFactory.create_form('post')
    if form.validate_on_submit():
        if 'username' in session:
            user = User.query.filter_by(username=session['username']).first()
            new_post = Post(content=form.content.data, user_id=user.id)
            db.session.add(new_post)
            db.session.commit()
            post_notifier.notify(f"Novo post criado pelo usuário {user.username}")
            flash('Post criado com sucesso!', 'success')
        else:
            flash('Você precisa estar logado para criar um post.', 'danger')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Erro no campo "{getattr(form, field).label.text}": {error}', 'danger')
    return redirect(url_for('index'))

@app.route('/edit_post/<int:post_id>', methods=["POST"])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        flash('Você não tem permissão para editar este post.')
        return redirect(url_for('index'))

    content = request.form.get('content')
    if content:
        post.content = content
        db.session.commit()
        flash('Post atualizado com sucesso!')
    else:
        flash('Erro ao atualizar o post.')

    return redirect(url_for('index'))

@app.route('/delete_post/<int:post_id>', methods=["POST"])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.user_id != current_user.id:
        flash('Você não tem permissão para excluir este post.')
        return redirect(url_for('index'))

    db.session.delete(post)
    db.session.commit()
    flash('Post excluído com sucesso!')
    return redirect(url_for('index'))

def perguntar(prompt):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "Você é influenciador de sucesso, com muito conhecimento em criar conteúdo de qualidade,que ajuda a criar posts completos sobre determinado assunto. Exclua o Claro do começo das respostas e apenas apresente a sugestão direto ao ponto"},
            {"role": "user", "content": prompt}
        ],
        max_tokens=400
    )
    return response.choices[0].message.content

@app.route('/chat', methods=["GET", "POST"])
def chat():
    chat_form = FormFactory.create_form('chat')
    response = None

    if request.method == 'POST' and chat_form.validate_on_submit():
        prompt = chat_form.prompt.data
        try:
            response = perguntar(prompt)
        except Exception as e:
            logging.error(f"Erro ao obter resposta do ChatGPT: {e}")
            flash(f"Erro ao obter resposta do ChatGPT: {e}", "error")

    return render_template('chat.html', chat_form=chat_form, response=response)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
