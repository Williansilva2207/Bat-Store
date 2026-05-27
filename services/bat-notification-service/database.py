import os
import sqlite3

DB_FILE = os.environ["NOTIFICATIONS_DB_FILE"]

def get_db_connect():
    conecta = sqlite3.connect(DB_FILE)
    conecta.row_factory = sqlite3.Row
    return conecta

def init_db():
    conecta = get_db_connect()
    cursor = conecta.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            item_id TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            status TEXT NOT NULL,
            sent_at TEXT NOT NULL
        )
    ''')
    conecta.commit()
    conecta.close()
    print("banco de dados de notificacoes ta feito")

def save_notification(order_id: int, item_id: str, quantity: int, status: str, sent_at: str) -> int:
    conecta = get_db_connect()
    cursor = conecta.cursor()
    cursor.execute(
        "INSERT INTO notifications (order_id, item_id, quantity, status, sent_at) VALUES (?, ?, ?, ?, ?)",
        (order_id, item_id, quantity, status, sent_at)
    )
    conecta.commit()
    notification_id = cursor.lastrowid
    conecta.close()
    return notification_id

def get_notifications_by_order(order_id: int):
    conecta = get_db_connect()
    cursor = conecta.cursor()
    cursor.execute("SELECT * FROM notifications WHERE order_id = ?", (order_id,))
    notifications = cursor.fetchall()
    conecta.close()
    return notifications
