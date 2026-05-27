import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from database import init_db, save_order
from middleware.broker import BatBrokerMiddleware

CATALOG_SERVICE_URL = os.environ["CATALOG_SERVICE_URL"]
CATALOG_REQUEST_TIMEOUT = float(os.environ["CATALOG_REQUEST_TIMEOUT"])
REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
QUEUE_NAME = os.environ["QUEUE_NAME"]

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
        response = requests.get(f"{CATALOG_SERVICE_URL}/{order.item_id}", timeout=CATALOG_REQUEST_TIMEOUT)
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        raise HTTPException(status_code=503, detail="Serviço de Catálogo indisponível.")

    if response.status_code == 404:
        raise HTTPException(status_code=400, detail="O item solicitado não existe.")

    item_catalogo = response.json()

    if item_catalogo["stock"] < order.quantity:
        raise HTTPException(status_code=400, detail="Estoque insuficiente.")

    new_order_id = save_order(order.item_id, order.quantity, "PROCESSANDO")

    broker.publish_event(queue_name=QUEUE_NAME, payload={
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
