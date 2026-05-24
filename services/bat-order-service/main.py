import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from database import init_db, save_order
from middleware.broker import BatBrokerMiddleware

CATALOG_SERVICE_URL = os.getenv("CATALOG_SERVICE_URL", "http://bat-catalog-service:8001/items")
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

broker = BatBrokerMiddleware(host=REDIS_HOST, port=REDIS_PORT)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Bat-Order-Service", version="1.0.0", lifespan=lifespan)

class OrderRequest(BaseModel):
    item_id: str
    quantity: int

@app.get("/")
def home():
    return {"service": "Bat-Order-Service", "status": "Online"}

@app.post("/orders")
def create_order(order: OrderRequest):
    try:
        response = requests.get(f"{CATALOG_SERVICE_URL}/{order.item_id}", timeout=3.0)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        raise HTTPException(status_code=503, detail="Serviço de Catálogo indisponível.")

    if response.status_code == 404:
        raise HTTPException(status_code=400, detail="O item solicitado não existe.")

    item_catalogo = response.json()

    if item_catalogo["stock"] < order.quantity:
        raise HTTPException(status_code=400, detail="Estoque insuficiente.")

    new_order_id = save_order(order.item_id, order.quantity, "PROCESSANDO")

    broker.publish_event(queue_name="fila_pedidos", payload={
        "order_id": new_order_id,
        "item_id": order.item_id,
        "quantity": order.quantity,
        "status": "APPROVED"
    })

    return {
        "message": "Pedido realizado com sucesso!",
        "order_id": new_order_id,
        "status": "PROCESSANDO"
    }