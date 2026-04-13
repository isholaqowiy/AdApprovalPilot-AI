import sqlite3

def init_db():
    conn = sqlite3.connect("users.db", check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            status TEXT DEFAULT 'unauthorized'
        )
    ''')
    conn.commit()
    conn.close()

def get_user_status(user_id):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 'unauthorized'

def update_user_status(user_id, username, status):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO users (user_id, username, status) 
        VALUES (?, ?, ?) 
        ON CONFLICT(user_id) DO UPDATE SET status=excluded.status
    ''', (user_id, username, status))
    conn.commit()
    conn.close()
