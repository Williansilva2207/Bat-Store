import sqlite3

DB_FILE = "payments.db"

def get_db_connect():
    conecta = sqlite3.connect(DB_FILE)
    conecta.row_factory = sqlite3.Row
    return conecta

def init_db():
    conecta = get_db_connect()
    cursor = conecta.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            item_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            total REAL NOT NULL,
            method TEXT NOT NULL,
            status TEXT NOT NULL
        )
    ''')
    conecta.commit()
    conecta.close()
    print("banco de dados de pagamentos ta feito")

def save_payment(order_id: int, item_id: str, quantity: int, total: float, method: str, status: str) -> int:
    conecta = get_db_connect()
    cursor = conecta.cursor()
    cursor.execute(
        "INSERT INTO payments (order_id, item_id, quantity, total, method, status) VALUES (?, ?, ?, ?, ?, ?)",
        (order_id, item_id, quantity, total, method, status)
    )
    conecta.commit()
    payment_id = cursor.lastrowid
    conecta.close()
    return payment_id

def get_payment_by_order(order_id: int):
    conecta = get_db_connect()
    cursor = conecta.cursor()
    cursor.execute("SELECT * FROM payments WHERE order_id = ?", (order_id,))
    payment = cursor.fetchone()
    conecta.close()
    return payment