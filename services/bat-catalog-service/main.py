from fastapi import FastAPI, HTTPException
from database import init_db, get_db_connect

app = FastAPI(title="Bat-Catalog-Service", version="1.0.0")

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/")
def home():
    return {"service": "Bat-Catalog-Service", "status": "Online"}

@app.get("/items/{id}")
def get_itemID(id: str):
    conecta = get_db_connect()
    cursor = conecta.cursor()
    cursor.execute("SELECT id, name, price, stock FROM items WHERE id = ?", (id,))
    item = cursor.fetchone()
    conecta.close()

    if item is None:
        raise HTTPException(status_code=404, detail="Item não encontrado no catálogo da Bat-Store")
    
    return {
        "id": item["id"],
        "name": item["name"],
        "price": item["price"],
        "stock": item["stock"]
    }