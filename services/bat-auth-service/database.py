import os
import sqlite3

DB_FILE = os.environ["AUTH_DB_FILE"]

def get_db_connect():
    conecta = sqlite3.connect(DB_FILE)
    conecta.row_factory = sqlite3.Row
    return conecta

def init_db():
    conecta = get_db_connect()
    cursor = conecta.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
    ''')
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        import bcrypt
        initial_users = [
            (
                os.environ["INITIAL_ADMIN_USERNAME"],
                bcrypt.hashpw(os.environ["INITIAL_ADMIN_PASSWORD"].encode(), bcrypt.gensalt()).decode(),
                "admin"
            ),
            (
                os.environ["INITIAL_USER_USERNAME"],
                bcrypt.hashpw(os.environ["INITIAL_USER_PASSWORD"].encode(), bcrypt.gensalt()).decode(),
                "user"
            ),
            (
                os.environ["INITIAL_SUPPORT_USERNAME"],
                bcrypt.hashpw(os.environ["INITIAL_SUPPORT_PASSWORD"].encode(), bcrypt.gensalt()).decode(),
                "user"
            ),
        ]
        cursor.executemany("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", initial_users)
        conecta.commit()
        print("banco de dados de auth ta feito")
    conecta.close()

def get_user(username: str):
    conecta = get_db_connect()
    cursor = conecta.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conecta.close()
    return user
