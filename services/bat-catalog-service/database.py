import os
import sqlite3

DB_FILE = os.environ["CATALOG_DB_FILE"]

def get_db_connect():
    conecta = sqlite3.connect(DB_FILE)
    conecta.row_factory = sqlite3.Row
    return conecta

def init_db():
    conecta = get_db_connect()
    cursor = conecta.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            stock INTEGER NOT NULL
        )
    ''')
    cursor.execute("SELECT COUNT(*) FROM items")
    if cursor.fetchone()[0] == 0:
        initial_items = [
            ("bat-01", "Action Figure Batman", "Miniatura articulada escala 1:6", 299.90, 10),
            ("bat-02", "Camiseta Bat-Sinal", "Camiseta preta 100% algodão", 79.90, 25),
            ("bat-03", "Caneca Coringa", "Caneca de porcelana para café", 45.00, 3),
            ("bat-04", "HQ O Cavaleiro das Trevas", "Edição definitiva encadernada", 120.00, 15),
            ("bat-05", "Batmóvel: The Tumbler", "Réplica Oficial Limitada da trilogia de Christopher Nolan", 17000000.00, 1)
        ]
        cursor.executemany("INSERT INTO items VALUES (?, ?, ?, ?, ?)", initial_items)
        conecta.commit()
        print("banco de dados do catalogo ta feito")
    conecta.close()
