"""
app.py
Aplicación principal de la biblioteca.
"""

import logging
import os
from datetime import timedelta
from flask import Flask, redirect, url_for

from database import init_db, ensure_optional_tables
from db_utils import close_db

# ====================== CONFIGURACIÓN ======================
app = Flask(
    __name__,
    static_folder='static',
    template_folder='templates'
)

app.config.from_mapping(
    SECRET_KEY=os.environ.get('SECRET_KEY', os.urandom(32).hex()),
    DATABASE=os.environ.get('DATABASE', 'library.db'),
    RESERVATION_PERIOD_DAYS=14,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=False,
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    GOOGLE_BOOKS_ENDPOINT='https://www.googleapis.com/books/v1/volumes?q=isbn:{}',
    TEMPLATES_AUTO_RELOAD=True,
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
app.logger.setLevel(logging.INFO)

# ====================== BASE DE DATOS ======================
try:
    init_db(app.config['DATABASE'])
    ensure_optional_tables(app.config['DATABASE'])
except Exception as exc:
    app.logger.warning('No se pudo inicializar la base de datos: %s', exc)

@app.teardown_appcontext
def teardown_db(exception=None):
    close_db(exception)

# ====================== BLUEPRINTS ======================
from routes import auth_routes, catalog_routes, admin_routes, book_routes, user_routes

app.register_blueprint(auth_routes.auth_bp)
app.register_blueprint(catalog_routes.catalog_bp)
app.register_blueprint(admin_routes.admin_bp)
app.register_blueprint(book_routes.book_bp)
app.register_blueprint(user_routes.user_bp)
# =======================================================

@app.route('/')
def home():
    # Redirige a la ruta inicial del Blueprint auth
    return redirect(url_for('auth.index'))

if __name__ == '__main__':
    print("🚀 Servidor Flask iniciado en http://127.0.0.1:5001")
    app.run(host='0.0.0.0', port=5001, debug=True)
