from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from database import init_db, get_db_connect

app = FastAPI(title="Bat-Order-Service", version="1.0.0")

CATALOG_SERVICE_URL = "http://127.0.0.1:8001/items"

class OrderRequest(BaseModel):
    item_id: str
    quantity: int

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/")
def home():
    return {"service": "Bat-Order-Service", "status": "Online"}

@app.post("/orders")
def create_order(order: OrderRequest):
    try:
        url_catalogo = f"{CATALOG_SERVICE_URL}/{order.item_id}"
        response = requests.get(url_catalogo)
    except requests.exceptions.ConnetionError:
        raise HTTPException(
            status_code=503,
            detail="Serviço de Catálogo temporariamente indisponível. Falha na comunicação."           
        )

    if response.status_code == 404:
        raise HTTPException(status_code=400, detail="Pedido rejeitado: O item solicitado não existe.")

    item_catalogo = response.json()

    if item_catalogo["stock"] < order.quantity:
        raise HTTPException(
            status_code=400, 
            detail=f"Pedido rejeitado: Estoque insuficiente. Estoque atual: {item_catalogo['stock']}"
        )

    conecta = get_db_connect()
    cursor = conecta.cursor()
    cursor.execute(
        "INSERT INTO orders (item_id, quantity, status) VALUES (?, ?, ?)",
        (order.item_id, order.quantity, "APPROVED")
    )
    conecta.commit()
    new_order_id = cursor.lastrowid
    conecta.close()

    return {
        "message": "Pedido realizado com sucesso!",
        "order_id": new_order_id,
        "item_name": item_catalogo["name"],
        "quantity": order.quantity,
        "status": "APPROVED"
    }