from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from database import init_db, save_order

import sys
sys.path.append("../../")
from middleware.broker import BatBrokerMiddleware

app = FastAPI(title="Bat-Order-Service", version="1.0.0")

CATALOG_SERVICE_URL = "http://127.0.0.1:8001/items"

broker = BatBrokerMiddleware(host="localhost", port=6379)

class OrderRequest(BaseModel):
    item_id: str
    quantity: int

@app.on_event("startup")
def startup_event():
    init_db()

@app.post("/orders")
def create_order(order: OrderRequest):
    try:
        url_catalogo = f"{CATALOG_SERVICE_URL}/{order.item_id}"
        response = requests.get(url_catalogo, timeout=3.0)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        raise HTTPException(status_code=503, detail="Serviço de Catálogo indisponível.")

    if response.status_code == 404:
        raise HTTPException(status_code=400, detail="O item solicitado não existe.")

    item_catalogo = response.json()

    if item_catalogo["stock"] < order.quantity:
        raise HTTPException(status_code=400, detail="Estoque insuficiente.")

    new_order_id = save_order(order.item_id, order.quantity, "APPROVED")

    payload_evento = {
        "order_id": new_order_id,
        "item_id": order.item_id,
        "quantity": order.quantity,
        "status": "APPROVED"
    }
    broker.publish_event(queue_name="fila_pedidos", payload=payload_evento)

    return {
        "message": "Pedido realizado com sucesso!",
        "order_id": new_order_id,
        "status": "APPROVED"
    }