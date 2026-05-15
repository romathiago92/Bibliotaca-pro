from flask import g
from database import get_db_connection


def get_db():
    if 'db' not in g:
        g.db = get_db_connection()
    return g.db


def close_db(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def query_db(query, args=(), one=False):
    cursor = get_db().execute(query, args)
    rows = cursor.fetchall()
    cursor.close()
    if one:
        return rows[0] if rows else None
    return rows


def execute_db(query, args=()):
    conn = get_db()
    cursor = conn.execute(query, args)
    conn.commit()
    cursor.close()
    return cursor
