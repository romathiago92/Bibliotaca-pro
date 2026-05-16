from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from decorators import login_required
from forms import RegisterForm, LoginForm
from db_utils import query_db, execute_db
from werkzeug.security import generate_password_hash, check_password_hash

# ==================== BLUEPRINT ====================
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/')
def index():
    if session.get('user_id'):
        return redirect(url_for('catalog.catalog'))
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        email = form.email.data.strip().lower()
        password = form.password.data

        existing_user = query_db(
            'SELECT 1 FROM users WHERE email = ? OR username = ?',
            (email, username),
            one=True,
        )
        if existing_user:
            flash('El nombre de usuario o el email ya están registrados.', 'error')
            return render_template('register.html', form=form)

        execute_db(
            'INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)',
            (username, email, generate_password_hash(password), 'user'),
        )
        flash('Registro exitoso. Ya puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html', form=form)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        user = query_db('SELECT * FROM users WHERE email = ?', (email,), one=True)

        if user and check_password_hash(user['password'], form.password.data):
            session['user_id'] = user['id']
            session['role'] = user['role']
            flash('Bienvenido de nuevo.', 'success')
            
            if user['role'] == 'admin':
                return redirect(url_for('admin.admin_dashboard'))  # asumiendo que está en admin blueprint
            else:
                return redirect(url_for('catalog.catalog'))

        flash('Credenciales inválidas.', 'error')

    return render_template('login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    session.clear()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('auth.login'))