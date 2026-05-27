import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from database import init_db, save_order
from middleware.broker import BatBrokerMiddleware
from middleware.resilient_http import ResilientFallback, ResilientHttpClient

CATALOG_SERVICE_URL = os.environ["CATALOG_SERVICE_URL"]
CATALOG_REQUEST_TIMEOUT = float(os.environ["CATALOG_REQUEST_TIMEOUT"])
REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
QUEUE_NAME = os.environ["QUEUE_NAME"]

catalog_client = ResilientHttpClient(
    service_name="bat-order-service",
    timeout_seconds=CATALOG_REQUEST_TIMEOUT,
)
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
        catalog_result = catalog_client.get_json(
            f"{CATALOG_SERVICE_URL}/{order.item_id}",
            cache_key=order.item_id,
        )
        item_catalogo = catalog_result.payload
        degraded_mode = catalog_result.fallback
    except ResilientFallback as fallback:
        if fallback.payload is not None:
            item_catalogo = fallback.payload
            degraded_mode = True
        else:
            raise HTTPException(
                status_code=503,
                detail="Serviço de Catálogo indisponível. Operação em modo degradado.",
            )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=400, detail="O item solicitado não existe.")
        raise HTTPException(
            status_code=503,
            detail="Serviço de Catálogo indisponível. Operação em modo degradado.",
        )

    if item_catalogo["stock"] < order.quantity:
        raise HTTPException(status_code=400, detail="Estoque insuficiente.")

    new_order_id = save_order(order.item_id, order.quantity, "PROCESSANDO_DEGRADADO" if degraded_mode else "PROCESSANDO")

    broker.publish_event(queue_name=QUEUE_NAME, payload={
        "order_id": new_order_id,
        "item_id": order.item_id,
        "quantity": order.quantity,
        "status": "APPROVED",
        "degraded": degraded_mode,
    })

    response_message = (
        "Pedido realizado com sucesso em modo degradado (cache do catálogo)."
        if degraded_mode
        else "Pedido realizado com sucesso!"
    )

    return {
        "message": response_message,
        "order_id": new_order_id,
        "status": "PROCESSANDO_DEGRADADO" if degraded_mode else "PROCESSANDO",
        "degraded": degraded_mode,
    }
