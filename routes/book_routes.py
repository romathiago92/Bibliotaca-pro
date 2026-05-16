from datetime import date, timedelta
from flask import Blueprint, render_template, redirect, request, url_for, session, flash, abort, current_app

from decorators import login_required
from helpers import get_book_details, user_has_favorite, get_book_reviews
from db_utils import execute_db

# ==================== BLUEPRINT ====================
book_bp = Blueprint('book', __name__)

@book_bp.route('/return/<int:reservation_id>')
@login_required
def return_book(reservation_id):
    # Solo admins pueden devolver
    if session.get('role') != 'admin':
        flash("Acción restringida a administradores.", "error")
        return redirect(url_for('user.my_reservations'))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Marcar la reserva como devuelta
    cursor.execute(
        "UPDATE reservations SET status = 'returned', return_date = CURRENT_TIMESTAMP WHERE id = ?",
        (reservation_id,)
    )

    # Actualizar disponibilidad del libro
    cursor.execute(
        """
        UPDATE books 
        SET available = available + 1 
        WHERE id = (SELECT book_id FROM reservations WHERE id = ?)
        """,
        (reservation_id,)
    )

    conn.commit()
    conn.close()

    flash("Libro devuelto correctamente.", "success")
    return redirect(url_for('user.my_reservations'))


@book_bp.route('/book/<int:book_id>')
@login_required
def book_detail(book_id):
    current_app.logger.info(f"Accessing book_detail for book_id: {book_id}")
    
    book = get_book_details(book_id)
    current_app.logger.info(f"Book: {book}")
    
    if not book:
        abort(404)
    
    linked = user_has_favorite(session['user_id'], book_id)
    reviews = get_book_reviews(book_id)
    current_app.logger.info(f"Reviews: {reviews}")
    
    return render_template('book_detail.html', book=book, favorited=linked, reviews=reviews)


@book_bp.route('/book/<int:book_id>/review', methods=['POST'])
@login_required
def submit_book_review(book_id):
    book = get_book_details(book_id)
    if not book:
        abort(404)

    rating = request.form.get('rating', type=int)
    comment = request.form.get('comment', '').strip()
    
    if not rating or rating < 1 or rating > 5:
        flash('Selecciona una calificación de 1 a 5 estrellas.', 'warning')
        return redirect(url_for('book.book_detail', book_id=book_id))

    execute_db(
        'INSERT INTO comments (user_id, book_id, rating, comment) VALUES (?, ?, ?, ?)',
        (session['user_id'], book_id, rating, comment),
    )
    execute_db(
        'INSERT INTO ratings (user_id, book_id, rating) VALUES (?, ?, ?)',
        (session['user_id'], book_id, rating),
    )
    flash('Gracias por dejar tu reseña.', 'success')
    return redirect(url_for('book.book_detail', book_id=book_id))


@book_bp.route('/favorite/<int:book_id>')
@login_required
def toggle_favorite(book_id):
    if user_has_favorite(session['user_id'], book_id):
        execute_db('DELETE FROM favorites WHERE user_id = ? AND book_id = ?', (session['user_id'], book_id))
        flash('Libro eliminado de favoritos.', 'info')
    else:
        execute_db('INSERT OR IGNORE INTO favorites (user_id, book_id) VALUES (?, ?)', (session['user_id'], book_id))
        flash('Libro agregado a favoritos.', 'success')

    return redirect(request.referrer or url_for('catalog.catalog'))


@book_bp.route('/reserve/<int:book_id>')
@login_required
def reserve_book(book_id):
    book = get_book_details(book_id)
    if not book:
        abort(404)

    if book['available'] <= 0:
        flash('No hay copias disponibles para reservar.', 'warning')
        return redirect(url_for('catalog.catalog'))

    today = date.today().isoformat()
    days = current_app.config.get('RESERVATION_PERIOD_DAYS', 14)
    due_date = (date.today() + timedelta(days=days)).isoformat()

    execute_db(
        'INSERT INTO reservations (user_id, book_id, status, loan_date, due_date) VALUES (?, ?, ?, ?, ?)',
        (session['user_id'], book_id, 'reserved', today, due_date),
    )
    execute_db('UPDATE books SET available = available - 1 WHERE id = ?', (book_id,))
    flash('Reserva registrada correctamente.', 'success')
    return redirect(url_for('user.my_reservations'))
