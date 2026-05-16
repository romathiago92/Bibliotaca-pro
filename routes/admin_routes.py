import requests
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app

from decorators import login_required, admin_required
from forms import BookForm
from db_utils import query_db, execute_db
from helpers import get_dashboard_stats, generate_activity_graph, get_book_details, get_user_reviews, auto_detect_genres, normalize_text

# ==================== BLUEPRINT ====================
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/dashboard')
@login_required
@admin_required
def admin_dashboard():
    stats = get_dashboard_stats()
    graph_path = generate_activity_graph()
    return render_template('admin_dashboard.html', stats=stats, graph_path=graph_path)


@admin_bp.route('/users')
@login_required
@admin_required
def admin_users():
    users = query_db(
        """
        SELECT u.id, u.username, u.email,
               COALESCE((SELECT COUNT(*) FROM reservations r WHERE r.user_id = u.id AND r.status = 'returned'), 0) AS returned,
               COALESCE((SELECT COUNT(*) FROM reservations r WHERE r.user_id = u.id AND r.status = 'reserved'), 0) AS reserved,
               COALESCE((SELECT COUNT(*) FROM reservations r WHERE r.user_id = u.id AND r.status = 'pending'), 0) AS pending,
               COALESCE((SELECT AVG(CASE WHEN r.status = 'returned' AND r.due_date IS NOT NULL AND r.return_date IS NOT NULL 
                    THEN (julianday(r.return_date) - julianday(r.due_date)) * -1 ELSE 0 END) 
                    FROM reservations r WHERE r.user_id = u.id), 0) AS responsibility_score
        FROM users u
        ORDER BY u.username
        """
    )
    return render_template('admin_users.html', users=users)


@admin_bp.route('/books', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_books():
    form = BookForm()
    genres = query_db('SELECT id, name FROM genres ORDER BY name')
    form.genres.choices = [(genre['id'], genre['name']) for genre in genres]

    if request.form.get('action') == 'delete_selected':
        selected_ids = [value for value in request.form.getlist('selected_books') if value.isdigit()]
        if selected_ids:
            placeholders = ','.join('?' for _ in selected_ids)
            execute_db(f'DELETE FROM favorites WHERE book_id IN ({placeholders})', tuple(selected_ids))
            execute_db(f'DELETE FROM reservations WHERE book_id IN ({placeholders})', tuple(selected_ids))
            execute_db(f'DELETE FROM book_genres WHERE book_id IN ({placeholders})', tuple(selected_ids))
            execute_db(f'DELETE FROM books WHERE id IN ({placeholders})', tuple(selected_ids))
            flash(f'{len(selected_ids)} libro(s) eliminado(s).', 'success')
            return redirect(url_for('admin.admin_books'))

    if form.validate_on_submit():
        title = normalize_text(form.title.data)
        author = normalize_text(form.author.data)
        isbn = normalize_text(form.isbn.data).replace('-', '')
        copies = max(1, form.copies.data or 1)
        genre_ids = form.genres.data or []

        if isbn:
            try:
                url = current_app.config['GOOGLE_BOOKS_ENDPOINT'].format(isbn)
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                result = response.json()
                if result.get('items'):
                    item = result['items'][0]['volumeInfo']
                    title = item.get('title', title)
                    author = ', '.join(item.get('authors', [author]))
                    if not genre_ids:
                        genre_ids = auto_detect_genres(title, author, item.get('description', ''))
                    flash(f'ISBN encontrado: {title}. Se han completado los datos automáticamente.', 'info')
            except requests.RequestException as exc:
                current_app.logger.warning('Error al buscar ISBN en Google Books: %s', exc)
                flash('No se pudo obtener información del ISBN. Verifica tu conexión.', 'warning')

        execute_db(
            'INSERT INTO books (title, author, copies, available) VALUES (?, ?, ?, ?)',
            (title, author, copies, copies),
        )
        book_id = query_db('SELECT last_insert_rowid() AS id', one=True)['id']

        for genre_id in genre_ids:
            execute_db('INSERT INTO book_genres (book_id, genre_id) VALUES (?, ?)', (book_id, genre_id))

        flash(f'Libro "{title}" agregado con éxito.', 'success')
        return redirect(url_for('admin.admin_books'))

    books = query_db(
        """
        SELECT b.id, b.title, b.author, b.copies AS total_copies, b.available AS available_copies,
               GROUP_CONCAT(DISTINCT g.name) AS genre_names
        FROM books b
        LEFT JOIN book_genres bg ON b.id = bg.book_id
        LEFT JOIN genres g ON bg.genre_id = g.id
        GROUP BY b.id
        ORDER BY b.title
        """
    )
    return render_template('admin_books.html', form=form, books=books, genres=genres)


@admin_bp.route('/book/<int:book_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_edit_book(book_id):
    form = BookForm()
    book = get_book_details(book_id)
    if not book:
        abort(404)

    genres = query_db('SELECT id, name FROM genres ORDER BY name')
    form.genres.choices = [(genre['id'], genre['name']) for genre in genres]

    if request.method == 'GET':
        form.title.data = book['title']
        form.author.data = book['author']
        form.copies.data = book['copies']
        form.genres.data = [row['genre_id'] for row in query_db('SELECT genre_id FROM book_genres WHERE book_id = ?', (book_id,))]

    if form.validate_on_submit():
        title = normalize_text(form.title.data)
        author = normalize_text(form.author.data)
        copies = max(1, form.copies.data or 1)
        active_reserved = query_db(
            'SELECT COUNT(*) AS count FROM reservations WHERE book_id = ? AND status = ?',
            (book_id, 'reserved'), one=True
        )['count']
        available = max(0, copies - active_reserved)

        execute_db(
            'UPDATE books SET title = ?, author = ?, copies = ?, available = ? WHERE id = ?',
            (title, author, copies, available, book_id)
        )
        execute_db('DELETE FROM book_genres WHERE book_id = ?', (book_id,))
        for genre_id in form.genres.data:
            execute_db('INSERT INTO book_genres (book_id, genre_id) VALUES (?, ?)', (book_id, genre_id))

        flash('Libro actualizado correctamente.', 'success')
        return redirect(url_for('admin.admin_books'))

    return render_template('admin_edit_book.html', form=form, book=book)


@admin_bp.route('/book/<int:book_id>/delete', methods=['POST'])
@login_required
@admin_required
def admin_delete_book(book_id):
    execute_db('DELETE FROM favorites WHERE book_id = ?', (book_id,))
    execute_db('DELETE FROM reservations WHERE book_id = ?', (book_id,))
    execute_db('DELETE FROM book_genres WHERE book_id = ?', (book_id,))
    execute_db('DELETE FROM books WHERE id = ?', (book_id,))
    flash('Libro eliminado correctamente.', 'success')
    return redirect(url_for('admin.admin_books'))


@admin_bp.route('/scan_isbn')
@login_required
@admin_required
def scan_isbn():
    return render_template('admin_scan_isbn.html')


@admin_bp.route('/process_isbn', methods=['POST'])
@login_required
@admin_required
def process_isbn():
    isbn = normalize_text(request.form.get('isbn', '')).replace('-', '').upper()
    if len(isbn) < 10:
        flash('ISBN inválido. Debe tener al menos 10 caracteres.', 'error')
        return redirect(url_for('admin.scan_isbn'))

    try:
        url = current_app.config['GOOGLE_BOOKS_ENDPOINT'].format(isbn)
        response = requests.get(url, timeout=12)
        response.raise_for_status()
        payload = response.json()

        if payload.get('items'):
            item = payload['items'][0]['volumeInfo']
            title = item.get('title', 'Sin título')
            author = ', '.join(item.get('authors', ['Sin autor']))
            desc = item.get('description', '')[:500]
            genres = auto_detect_genres(title, author, desc)

            return render_template(
                'admin_add_isbn.html',
                isbn=isbn,
                book_info={'title': title, 'author': author, 'description': desc, 'genres': genres},
                genre_map={genre['id']: genre['name'] for genre in query_db('SELECT id, name FROM genres ORDER BY name')}
            )
    except requests.RequestException as exc:
        current_app.logger.warning('Error buscando ISBN: %s', exc)
        flash('Error al conectar con Google Books. Intenta nuevamente.', 'danger')
        return redirect(url_for('admin.scan_isbn'))

    flash('No se encontró el libro con ese ISBN.', 'warning')
    return redirect(url_for('admin.scan_isbn'))


@admin_bp.route('/add_from_scan', methods=['POST'])
@login_required
@admin_required
def add_from_scan():
    title = normalize_text(request.form.get('title', ''))
    author = normalize_text(request.form.get('author', ''))
    genre_ids = [int(value) for value in request.form.getlist('genres') if value.isdigit()]

    if not title or not author:
        flash('Faltan datos del libro detectado.', 'error')
        return redirect(url_for('admin.admin_books'))

    if not genre_ids:
        flash('Debe seleccionar al menos un género.', 'error')
        return redirect(url_for('admin.admin_books'))

    execute_db(
        'INSERT INTO books (title, author, copies, available) VALUES (?, ?, ?, ?)',
        (title, author, 1, 1)
    )
    book_id = query_db('SELECT last_insert_rowid() AS id', one=True)['id']
    for genre_id in genre_ids:
        execute_db('INSERT INTO book_genres (book_id, genre_id) VALUES (?, ?)', (book_id, genre_id))

    flash(f'Libro "{title}" agregado desde el escáner.', 'success')
    return redirect(url_for('admin.admin_books'))


@admin_bp.route('/generate_test_data', methods=['POST'])
@login_required
@admin_required
def generate_test_data():
    import random
    import sqlite3
    from werkzeug.security import generate_password_hash
    from datetime import datetime, timedelta

    # Generar usuarios
    max_user = query_db("SELECT MAX(CAST(SUBSTR(username, 5) AS INTEGER)) AS max_idx FROM users WHERE username LIKE 'user%';", one=True)
    start_index = (max_user['max_idx'] or 0) + 1
    inserted_users = 0

    for i in range(start_index, start_index + 100):
        username = f'user{i:03d}'
        email = f'user{i:03d}@example.com'
        password = generate_password_hash('password123')
        try:
            execute_db('INSERT INTO users (username, email, password) VALUES (?, ?, ?)', (username, email, password))
            inserted_users += 1
        except sqlite3.IntegrityError:
            continue

    # Generar libros y géneros (el resto de tu código original)
    genres = [row['id'] for row in query_db('SELECT id FROM genres')]
    for i in range(100):
        title = f'Libro de Prueba {i+1}'
        author = f'Autor {i+1}'
        copies = random.randint(1, 5)
        execute_db('INSERT INTO books (title, author, copies, available) VALUES (?, ?, ?, ?)', (title, author, copies, copies))
        book_id = query_db('SELECT last_insert_rowid() AS id', one=True)['id']
        selected_genres = random.sample(genres, min(len(genres), random.randint(1, 3)))
        for genre_id in selected_genres:
            execute_db('INSERT INTO book_genres (book_id, genre_id) VALUES (?, ?)', (book_id, genre_id))

    flash(f'Datos de prueba generados: {inserted_users} usuarios, 100 libros, etc.', 'success')
    return redirect(url_for('admin.admin_dashboard'))


# Rutas restantes
@admin_bp.route('/user/<int:user_id>')
@login_required
@admin_required
def admin_user_profile(user_id):
    user = query_db('SELECT * FROM users WHERE id = ?', (user_id,), one=True)
    if not user:
        abort(404)

    total_borrowed = query_db('SELECT COUNT(*) AS count FROM reservations WHERE user_id = ?', (user_id,), one=True)['count']
    total_returned = query_db('SELECT COUNT(*) AS count FROM reservations WHERE user_id = ? AND status = ?', (user_id, 'returned'), one=True)['count']

    pending_books = query_db(
        "SELECT r.id, b.title, r.loan_date, r.due_date FROM reservations r JOIN books b ON r.book_id = b.id WHERE r.user_id = ? AND r.status = ?",
        (user_id, 'pending')
    )
    reserved_books = query_db(
        "SELECT r.id, b.title, r.loan_date FROM reservations r JOIN books b ON r.book_id = b.id WHERE r.user_id = ? AND r.status = ?",
        (user_id, 'reserved')
    )

    user_reviews = get_user_reviews(user_id)

    return render_template(
        'admin_user_profile.html',
        user=user,
        total_borrowed=total_borrowed,
        total_returned=total_returned,
        pending_books=pending_books,
        reserved_books=reserved_books,
        user_reviews=user_reviews,
    )


@admin_bp.route('/reservation/<int:reservation_id>/deliver', methods=['POST'])
@login_required
@admin_required
def deliver_reservation(reservation_id):
    reservation = query_db('SELECT * FROM reservations WHERE id = ?', (reservation_id,), one=True)
    if not reservation:
        abort(404)

    from datetime import datetime, timedelta
    loan_date = datetime.now().isoformat()
    due_date = (datetime.now() + timedelta(days=14)).isoformat()

    execute_db(
        'UPDATE reservations SET status = ?, loan_date = ?, due_date = ? WHERE id = ?',
        ('pending', loan_date, due_date, reservation_id)
    )
    execute_db('UPDATE books SET available = available - 1 WHERE id = ?', (reservation['book_id'],))

    flash('Libro entregado al usuario.', 'success')
    return redirect(url_for('admin.admin_user_profile', user_id=reservation['user_id']))


@admin_bp.route('/reservation/<int:reservation_id>/deny', methods=['POST'])
@login_required
@admin_required
def deny_reservation(reservation_id):
    reservation = query_db('SELECT * FROM reservations WHERE id = ?', (reservation_id,), one=True)
    if not reservation:
        abort(404)

    execute_db('DELETE FROM reservations WHERE id = ?', (reservation_id,))

    flash('Reserva denegada.', 'success')
    return redirect(url_for('admin.admin_user_profile', user_id=reservation['user_id']))