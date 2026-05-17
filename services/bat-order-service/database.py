import sqlite3

DB_FILE = "orders.db"

def get_db_connect():
    conecta = sqlite3.connect(DB_FILE)
    conecta.row_factory = sqlite3.Row
    return conecta

def init_db():
    conecta = get_db_connect()
    cursor = conecta.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT NOT NULL
        )
    ''')
    conecta.commit()
    conecta.close()
    print("banco de dados do pedidos ta feito")