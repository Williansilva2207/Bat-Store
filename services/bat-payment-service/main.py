import os
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from database import init_db, save_payment, get_payment_by_order
from middleware.resilient_http import ResilientFallback, ResilientHttpClient

CATALOG_SERVICE_URL = os.environ["CATALOG_SERVICE_URL"]
CATALOG_REQUEST_TIMEOUT = float(os.environ["CATALOG_REQUEST_TIMEOUT"])

catalog_client = ResilientHttpClient(
    service_name="bat-payment-service",
    timeout_seconds=CATALOG_REQUEST_TIMEOUT,
)

METODOS_ACEITOS = ["credit_card", "debit_card", "bat_coins"]

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Bat-Payment-Service", version="1.0.0", lifespan=lifespan)

class PaymentRequest(BaseModel):
    order_id: int
    item_id: str
    quantity: int
    method: str

@app.get("/")
def home():
    return {"service": "Bat-Payment-Service", "status": "Online"}

@app.post("/payments")
def process_payment(payment: PaymentRequest):
    if payment.method not in METODOS_ACEITOS:
        raise HTTPException(
            status_code=400,
            detail=f"Método de pagamento inválido. Aceitos: {METODOS_ACEITOS}"
        )

    existing = get_payment_by_order(payment.order_id)
    if existing:
        raise HTTPException(status_code=409, detail="Pagamento para esse pedido já foi processado.")

    try:
        catalog_result = catalog_client.get_json(
            f"{CATALOG_SERVICE_URL}/{payment.item_id}",
            cache_key=payment.item_id,
        )
        item = catalog_result.payload
        degraded_mode = catalog_result.fallback
    except ResilientFallback as fallback:
        if fallback.payload is not None:
            item = fallback.payload
            degraded_mode = True
        else:
            raise HTTPException(
                status_code=503,
                detail="Serviço de Catálogo indisponível. Operação em modo degradado.",
            )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=400, detail="Item não encontrado no catálogo.")
        raise HTTPException(
            status_code=503,
            detail="Serviço de Catálogo indisponível. Operação em modo degradado.",
        )

    total = item["price"] * payment.quantity

    payment_id = save_payment(
        payment.order_id,
        payment.item_id,
        payment.quantity,
        total,
        payment.method,
        "APROVADO"
    )

    response_message = (
        "Pagamento processado com sucesso em modo degradado (cache do catálogo)."
        if degraded_mode
        else "Pagamento processado com sucesso!"
    )

    return {
        "message": response_message,
        "payment_id": payment_id,
        "order_id": payment.order_id,
        "item": item["name"],
        "quantity": payment.quantity,
        "total": total,
        "method": payment.method,
        "status": "APROVADO",
        "degraded": degraded_mode,
    }

@app.get("/payments/{order_id}")
def get_payment(order_id: int):
    payment = get_payment_by_order(order_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="Pagamento não encontrado para esse pedido.")
    return {
        "payment_id": payment["id"],
        "order_id": payment["order_id"],
        "item_id": payment["item_id"],
        "quantity": payment["quantity"],
        "total": payment["total"],
        "method": payment["method"],
        "status": payment["status"]
    }
