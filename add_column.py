import sqlite3
conn = sqlite3.connect('library.db')
try:
    conn.execute('ALTER TABLE users ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP')
    conn.commit()
    print('Columna agregada')
except sqlite3.OperationalError as e:
    print(f'Error: {e}')
conn.close()