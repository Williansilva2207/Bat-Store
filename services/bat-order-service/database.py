import os
import sqlite3

DB_FILE = os.environ["ORDERS_DB_FILE"]

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

def save_order(item_id: str, quantity: int, status: str) -> int:
    conecta = get_db_connect()
    cursor = conecta.cursor()
    cursor.execute(
        "INSERT INTO orders (item_id, quantity, status) VALUES (?, ?, ?)",
        (item_id, quantity, status)
    )
    conecta.commit()
    order_id = cursor.lastrowid
    conecta.close()
    return order_id
