from flask import Blueprint, render_template, request, session

from decorators import login_required
from helpers import normalize_text, build_filters
from db_utils import query_db

# ==================== BLUEPRINT ====================
catalog_bp = Blueprint('catalog', __name__)

@catalog_bp.route('/catalog', methods=['GET', 'POST'])
@login_required
def catalog():
    selected_genres = [int(value) for value in request.values.getlist('genres') if value.isdigit()]
    search = normalize_text(request.values.get('search', ''))
    favorite_mode = request.args.get('favorites') == 'true'

    favorite_ids = {
        row['book_id']
        for row in query_db('SELECT book_id FROM favorites WHERE user_id = ?', (session['user_id'],))
    }

    query = [
        'SELECT b.*,',
        '       GROUP_CONCAT(DISTINCT g.name) AS genre_names',
        'FROM books b',
        'LEFT JOIN book_genres bg ON b.id = bg.book_id',
        'LEFT JOIN genres g ON bg.genre_id = g.id',
    ]
    filters = []
    params = []

    if favorite_mode:
        query.insert(3, 'JOIN favorites f ON f.book_id = b.id')
        filters.append('f.user_id = ?')
        params.append(session['user_id'])

    if selected_genres:
        placeholders = ','.join('?' for _ in selected_genres)
        filters.append(f'bg.genre_id IN ({placeholders})')
        params.extend(selected_genres)

    if search:
        filters.append('(b.title LIKE ? OR b.author LIKE ?)')
        params.extend([f'%{search}%', f'%{search}%'])

    if filters:
        query.append('WHERE ' + build_filters(filters))

    query.append('GROUP BY b.id')
    query.append('ORDER BY b.title')

    books = query_db(' '.join(query), tuple(params))
    genres = query_db('SELECT id, name FROM genres ORDER BY name')

    return render_template(
        'catalog.html',
        books=books,
        genres=genres,
        selected_genres=selected_genres,
        search=search,
        favorite_mode=favorite_mode,
        favorite_ids=favorite_ids,
    )