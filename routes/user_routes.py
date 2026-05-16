from datetime import date
from flask import Blueprint, render_template, redirect, url_for, session, flash

from decorators import login_required
from db_utils import query_db, execute_db
from helpers import get_user_reservations, get_recommendations, get_user_reviews

# ==================== BLUEPRINT ====================
user_bp = Blueprint('user', __name__, url_prefix='/user')

@user_bp.route('/my-reservations')
@login_required
def my_reservations():
    reservations = get_user_reservations(session['user_id'])
    return render_template('my_reservations.html', reservations=reservations)


@user_bp.route('/return/<int:reservation_id>')
@login_required
def return_book(reservation_id):
    query = 'SELECT * FROM reservations WHERE id = ?' if session.get('role') == 'admin' else 'SELECT * FROM reservations WHERE id = ? AND user_id = ?'
    args = (reservation_id,) if session.get('role') == 'admin' else (reservation_id, session['user_id'])
    reservation = query_db(query, args, one=True)

    if not reservation:
        flash('Reserva no encontrada o no autorizada.', 'error')
        return redirect(url_for('user.my_reservations'))

    if reservation['status'] == 'returned':
        flash('La reserva ya fue devuelta.', 'info')
        return redirect(url_for('user.my_reservations'))

    execute_db('UPDATE reservations SET status = ?, return_date = ? WHERE id = ?', 
               ('returned', date.today().isoformat(), reservation_id))
    execute_db('UPDATE books SET available = available + 1 WHERE id = ?', (reservation['book_id'],))
    flash('Libro marcado como devuelto.', 'success')
    return redirect(url_for('user.my_reservations'))


@user_bp.route('/profile')
@login_required
def profile():
    user = query_db('SELECT id, username, email, role FROM users WHERE id = ?', 
                   (session['user_id'],), one=True)
    
    stats = query_db(
        """
        SELECT
            (SELECT COUNT(*) FROM reservations WHERE user_id = ? AND status = 'reserved') AS active,
            (SELECT COUNT(*) FROM reservations WHERE user_id = ? AND status = 'returned') AS returned,
            (SELECT COUNT(*) FROM favorites WHERE user_id = ?) AS favorites
        """,
        (session['user_id'], session['user_id'], session['user_id']),
        one=True,
    )
    reviews = get_user_reviews(session['user_id'])
    return render_template('profile.html', user=user, stats=stats, reviews=reviews)


@user_bp.route('/recommended')
@login_required
def recommended():
    books = get_recommendations(session['user_id'])
    return render_template('recommended.html', books=books)