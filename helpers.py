import os
import requests
from datetime import date, timedelta
from flask import current_app
from db_utils import query_db


def normalize_text(value):
    return value.strip() if isinstance(value, str) else value


def auto_detect_genres(title, author, desc=''):
    texto = ' '.join([
        normalize_text(title),
        normalize_text(author),
        normalize_text(desc),
    ]).lower()
    palabras_clave = {
        1: ['fantasy', 'fantasía', 'dragón', 'dragon'],
        2: ['sci-fi', 'science fiction', 'ciencia ficción', 'espacio', 'space'],
        3: ['romance', 'amor', 'novela romántica'],
        4: ['terror', 'miedo', 'horror', 'sobrenatural'],
        5: ['misterio', 'misterio', 'detective', 'policial'],
        7: ['clásico', 'clasico', 'shakespeare', 'literatura clásica'],
        11: ['ficción', 'ficcion', 'fiction', 'novel', 'novela'],
        33: ['distopía', 'distopia', 'dystopia', 'utopía', 'utopia'],
    }

    detectados = []
    for genre_id, claves in palabras_clave.items():
        if any(clave in texto for clave in claves):
            detectados.append(genre_id)

    return detectados[:5] or [11, 7]


def build_filters(filters):
    return ' AND '.join(filters) if filters else ''


def get_dashboard_stats():
    totals = query_db(
        """
        SELECT
            (SELECT COUNT(*) FROM users) AS users,
            (SELECT COUNT(*) FROM books) AS books,
            (SELECT COUNT(*) FROM reservations WHERE status = 'returned') AS returns,
            (SELECT COUNT(*) FROM reservations WHERE status = 'reserved') AS reserved
        """,
        one=True,
    )
    return {
        'users': totals['users'],
        'books': totals['books'],
        'returns': totals['returns'],
        'reservations': totals['reserved'],
    }


def _svg_color_for_label(label):
    palette = {
        'Usuarios Nuevos': '#2563eb',
        'Libros Devueltos': '#16a34a',
        'Libros Pendientes': '#f59e0b',
        'Socios Nuevos': '#7c3aed',
    }
    return palette.get(label, '#111827')


def _create_activity_svg(file_path, dates, series):
    width, height = 1000, 520
    margin = 60
    chart_width = width - margin * 2
    chart_height = height - margin * 2
    max_count = max((count for _, counts, _ in series for count in counts), default=1)
    max_count = max(1, max_count)

    def point(index, value):
        x = margin + chart_width * (index / max(1, len(dates) - 1))
        y = margin + chart_height * (1 - value / max_count)
        return x, y

    date_ticks = [dates[i] for i in range(0, len(dates), 7)]

    lines = []
    for label, counts, color in series:
        path = []
        for index, value in enumerate(counts):
            x, y = point(index, value)
            path.append(f'{x:.1f},{y:.1f}')
        lines.append((label, color, 'M ' + ' L '.join(path)))

    labels = []
    for index, tick in enumerate(date_ticks):
        x, _ = point(index * 7, 0)
        labels.append(f'<text x="{x:.1f}" y="{height - margin + 28}" text-anchor="middle" font-size="12" fill="#4b5563">{tick.strftime("%d/%m")}</text>')

    grid_lines = []
    for i in range(6):
        y = margin + chart_height * i / 5
        grid_lines.append(f'<line x1="{margin}" y1="{y:.1f}" x2="{width - margin}" y2="{y:.1f}" stroke="#e5e7eb" stroke-width="1" />')

    legend_items = []
    for index, (label, _, color) in enumerate(series):
        lx = margin + index * 220
        ly = 30
        legend_items.append(
            f'<rect x="{lx}" y="{ly - 12}" width="14" height="14" fill="{color}" rx="4" />'
            f'<text x="{lx + 20}" y="{ly}" font-size="13" fill="#111827">{label}</text>'
        )

    content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}">
        <style>
            .axis {{ stroke: #6b7280; stroke-width: 1.5; }}
            .line {{ fill: none; stroke-width: 3; }}
            .marker {{ stroke: #ffffff; stroke-width: 1.5; }}
        </style>
        <rect width="100%" height="100%" fill="#ffffff" />
        <text x="{margin}" y="30" font-size="22" font-weight="700" fill="#111827">Actividad - Últimos 30 Días</text>
        {''.join(legend_items)}
        <g>
            <line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height - margin}" class="axis" />
            <line x1="{margin}" y1="{height - margin}" x2="{width - margin}" y2="{height - margin}" class="axis" />
            {''.join(grid_lines)}
            {''.join(labels)}
        </g>
        {''.join(f'<path d="{path}" class="line" stroke="{color}" />' for _, color, path in lines)}
        {''.join(
            f'<circle cx="{point(index, value)[0]:.1f}" cy="{point(index, value)[1]:.1f}" r="4" fill="{color}" class="marker" />'
            for _, counts, color in series for index, value in enumerate(counts)
        )}
    </svg>'''

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)


def generate_activity_graph():
    today = date.today()
    window_start = today - timedelta(days=29)

    user_rows = query_db(
        """
        SELECT DATE(created_at) AS date, COUNT(*) AS count
        FROM users
        WHERE created_at >= ?
        GROUP BY DATE(created_at)
        ORDER BY date
        """,
        (window_start.isoformat(),),
    )

    return_rows = query_db(
        """
        SELECT DATE(return_date) AS date, COUNT(*) AS count
        FROM reservations
        WHERE status = 'returned' AND return_date >= ?
        GROUP BY DATE(return_date)
        ORDER BY date
        """,
        (window_start.isoformat(),),
    )

    pending_rows = query_db(
        """
        SELECT DATE(loan_date) AS date, COUNT(*) AS count
        FROM reservations
        WHERE status = 'pending' AND loan_date >= ?
        GROUP BY DATE(loan_date)
        ORDER BY date
        """,
        (window_start.isoformat(),),
    )

    dates = [window_start + timedelta(days=i) for i in range(30)]

    def get_counts(rows):
        counts_by_day = {row['date']: row['count'] for row in rows}
        return [counts_by_day.get(d.isoformat(), 0) for d in dates]

    user_counts = get_counts(user_rows)
    return_counts = get_counts(return_rows)
    pending_counts = get_counts(pending_rows)
    member_counts = user_counts

    graph_dir = os.path.join(current_app.static_folder, 'graphs')
    os.makedirs(graph_dir, exist_ok=True)
    graph_path = os.path.join(graph_dir, 'activity.svg')

    try:
        _create_activity_svg(graph_path, dates, [
            ('Usuarios Nuevos', user_counts, _svg_color_for_label('Usuarios Nuevos')),
            ('Libros Devueltos', return_counts, _svg_color_for_label('Libros Devueltos')),
            ('Libros Pendientes', pending_counts, _svg_color_for_label('Libros Pendientes')),
            ('Socios Nuevos', member_counts, _svg_color_for_label('Socios Nuevos')),
        ])
        return '/static/graphs/activity.svg'
    except Exception as exc:
        current_app.logger.error('Error generando el gráfico SVG: %s', exc)
        return None


def get_book_details(book_id):
    row = query_db(
        """
        SELECT b.*, GROUP_CONCAT(DISTINCT g.name) AS genre_names,
               COALESCE(ROUND(AVG(r.rating), 1), 0) AS average_rating,
               COUNT(r.id) AS review_count
        FROM books b
        LEFT JOIN book_genres bg ON b.id = bg.book_id
        LEFT JOIN genres g ON bg.genre_id = g.id
        LEFT JOIN ratings r ON r.book_id = b.id
        WHERE b.id = ?
        GROUP BY b.id
        """,
        (book_id,),
        one=True,
    )
    print(f"get_book_details for {book_id}: {row}")
    return row


def get_book_reviews(book_id):
    return query_db(
        """
        SELECT c.id, c.comment, r.rating, c.created_at, u.username
        FROM comments c
        JOIN users u ON c.user_id = u.id
        JOIN ratings r ON r.user_id = c.user_id AND r.book_id = c.book_id
        WHERE c.book_id = ?
        ORDER BY c.created_at DESC
        """,
        (book_id,),
    )


def get_user_reviews(user_id):
    return query_db(
        """
        SELECT c.id, c.comment, r.rating, c.created_at, b.title AS book_title
        FROM comments c
        JOIN books b ON c.book_id = b.id
        JOIN ratings r ON r.user_id = c.user_id AND r.book_id = c.book_id
        WHERE c.user_id = ?
        ORDER BY c.created_at DESC
        """,
        (user_id,),
    )


def user_has_favorite(user_id, book_id):
    row = query_db(
        "SELECT 1 FROM favorites WHERE user_id = ? AND book_id = ?",
        (user_id, book_id),
        one=True,
    )
    return row is not None


def get_user_reservations(user_id):
    return query_db(
        """
        SELECT r.*, b.title, b.author, b.copies, b.available
        FROM reservations r
        LEFT JOIN books b ON r.book_id = b.id
        WHERE r.user_id = ?
        ORDER BY r.loan_date DESC
        """,
        (user_id,),
    )


def get_recommendations(user_id):
    user_genres = query_db(
        """
        SELECT DISTINCT g.id
        FROM genres g
        JOIN book_genres bg ON g.id = bg.genre_id
        JOIN favorites f ON bg.book_id = f.book_id
        WHERE f.user_id = ?
        UNION
        SELECT DISTINCT g.id
        FROM genres g
        JOIN book_genres bg ON g.id = bg.genre_id
        JOIN reservations r ON bg.book_id = r.book_id
        WHERE r.user_id = ?
        """,
        (user_id, user_id),
    )

    if not user_genres:
        return query_db(
            """
            SELECT b.*, GROUP_CONCAT(DISTINCT g.name) AS genre_names
            FROM books b
            LEFT JOIN book_genres bg ON b.id = bg.book_id
            LEFT JOIN genres g ON bg.genre_id = g.id
            WHERE b.available > 0
            GROUP BY b.id
            ORDER BY b.copies DESC
            LIMIT 10
            """,
        )

    genre_ids = [genre['id'] for genre in user_genres]
    placeholders = ','.join(['?' for _ in genre_ids])

    return query_db(
        f"""
        SELECT DISTINCT b.*, GROUP_CONCAT(DISTINCT g.name) AS genre_names
        FROM books b
        LEFT JOIN book_genres bg ON b.id = bg.book_id
        LEFT JOIN genres g ON bg.genre_id = g.id
        WHERE b.available > 0
          AND bg.genre_id IN ({placeholders})
          AND b.id NOT IN (
              SELECT book_id FROM favorites WHERE user_id = ?
              UNION
              SELECT book_id FROM reservations WHERE user_id = ?
          )
        GROUP BY b.id
        ORDER BY RANDOM()
        LIMIT 10
        """,
        tuple(genre_ids) + (user_id, user_id),
    )
