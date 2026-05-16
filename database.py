"""
database.py
Módulo de inicialización y conexión a SQLite para la aplicación.
"""

import os
import sqlite3
from werkzeug.security import generate_password_hash

DEFAULT_DB_PATH = os.environ.get('DATABASE', 'library.db')

GENRES = [
    'Fantasía', 'Ciencia Ficción', 'Romance', 'Terror', 'Misterio',
    'Juvenil', 'Clásico', 'Infantil', 'Historia', 'Poesía',
    'Ficción', 'No Ficción', 'Aventura', 'Detective', 'Thriller',
    'Drama', 'Comedia', 'Biografía', 'Memorias', 'Ensayo',
    'Filosofía', 'Psicología', 'Autoayuda', 'Cocina', 'Viajes',
    'Arte', 'Fotografía', 'Música', 'Teatro', 'Crimen',
    'Policial', 'Histórica', 'Distopía', 'Utopía', 'Magia Realista',
    'Gótico', 'Paranormal', 'Western', 'Piratas', 'Espías',
    'Deportes', 'Negocios', 'Ciencia', 'Matemáticas', 'Tecnología',
    'Mitología', 'Cuentos de Hadas', 'Leyendas', 'Folclore', 'Épica',
]

# Lista de admins iniciales
ADMIN_USERS = [
    {
        'username': 'alfbiblio',
        'email': 'alfbiblio@gmail.com',
        'password': 'alfredo123',
        'role': 'admin'
    },
    {
        'username': 'Thiago_TheZ',
        'email': 'romathiago92@gmail.com',
        'password': '47882877',
        'role': 'admin'
    }
]


def get_db_connection(db_path=None):
    db_path = db_path or DEFAULT_DB_PATH
    connection = sqlite3.connect(db_path, timeout=10, detect_types=sqlite3.PARSE_DECLTYPES)
    connection.row_factory = sqlite3.Row
    connection.execute('PRAGMA foreign_keys = ON')
    return connection


def init_db(db_path=None):
    db_path = db_path or DEFAULT_DB_PATH
    if os.path.exists(db_path):
        print('Base de datos ya existe. Bórrala si deseas recrearla.')
        return

    directory = os.path.dirname(db_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()

        cursor.execute(
            '''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                email TEXT UNIQUE,
                password TEXT,
                role TEXT DEFAULT 'user',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )

        cursor.execute('CREATE TABLE genres (id INTEGER PRIMARY KEY, name TEXT UNIQUE)')

        cursor.execute(
            '''
            CREATE TABLE books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT NOT NULL,
                copies INTEGER DEFAULT 1,
                available INTEGER DEFAULT 1
            )
            '''
        )

        cursor.execute('CREATE TABLE book_genres (book_id INTEGER, genre_id INTEGER)')
        cursor.execute('CREATE TABLE favorites (user_id INTEGER, book_id INTEGER)')
        cursor.execute(
            '''
            CREATE TABLE reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                book_id INTEGER,
                status TEXT DEFAULT 'reserved',
                loan_date TEXT,
                due_date TEXT,
                return_date TEXT
            )
            '''
        )

        for index, genre in enumerate(GENRES, start=1):
            cursor.execute('INSERT INTO genres (id, name) VALUES (?, ?)', (index, genre))

        # Insertar todos los admins definidos
        for admin in ADMIN_USERS:
            cursor.execute(
                'INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)',
                (
                    admin['username'],
                    admin['email'],
                    generate_password_hash(admin['password']),
                    admin['role'],
                ),
            )

        conn.commit()

    print('Base de datos creada correctamente.')
    for admin in ADMIN_USERS:
        print(f"Admin creado: {admin['email']} (contraseña: {admin['password']})")


def ensure_optional_tables(db_path=None):
    db_path = db_path or DEFAULT_DB_PATH
    with sqlite3.connect(db_path) as conn:
        conn.execute('PRAGMA foreign_keys = ON')
        cursor = conn.cursor()

        existing_user_columns = [row[1] for row in cursor.execute("PRAGMA table_info(users)").fetchall()]
        if 'created_at' not in existing_user_columns:
            cursor.execute(
                'ALTER TABLE users ADD COLUMN created_at DATETIME'
            )
            cursor.execute(
                'UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL'
            )

        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                book_id INTEGER,
                rating INTEGER CHECK(rating BETWEEN 1 AND 5),
                comment TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )

        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                book_id INTEGER,
                rating INTEGER CHECK(rating BETWEEN 1 AND 5),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )

        cursor.execute('CREATE INDEX IF NOT EXISTS idx_book_genres_book_genre ON book_genres(book_id, genre_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_favorites_user_book ON favorites(user_id, book_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_reservations_user_id ON reservations(user_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_comments_book_id ON comments(book_id)')

        conn.commit()
