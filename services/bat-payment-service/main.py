import os
import json
import time
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel
from database import init_db, save_payment, get_payment_by_order

CATALOG_SERVICE_URL = os.environ["CATALOG_SERVICE_URL"]
CATALOG_REQUEST_TIMEOUT = float(os.environ["CATALOG_REQUEST_TIMEOUT"])
CORRELATION_ID_HEADER = "X-Correlation-ID"

METODOS_ACEITOS = ["credit_card", "debit_card", "bat_coins"]

def log_json(level: str, correlation_id: str, message: str, **extra):
    print(json.dumps({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "service": "bat-payment-service",
        "correlation_id": correlation_id,
        "message": message,
        **extra
    }, ensure_ascii=False))

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
def process_payment(payment: PaymentRequest, request: Request):
    correlation_id = request.headers.get(CORRELATION_ID_HEADER, "sem-correlation-id")
    inicio = time.perf_counter()

    log_json(
        "INFO",
        correlation_id,
        "Inicio do processamento de pagamento",
        order_id=payment.order_id,
        item_id=payment.item_id,
        quantity=payment.quantity,
        method=payment.method
    )

    if payment.method not in METODOS_ACEITOS:
        log_json(
            "INFO",
            correlation_id,
            "Metodo de pagamento invalido",
            method=payment.method,
            status_code=400,
            latency_ms=round((time.perf_counter() - inicio) * 1000, 2)
        )
        raise HTTPException(
            status_code=400,
            detail=f"Método de pagamento inválido. Aceitos: {METODOS_ACEITOS}"
        )

    existing = get_payment_by_order(payment.order_id)
    if existing:
        log_json(
            "INFO",
            correlation_id,
            "Pagamento duplicado detectado",
            order_id=payment.order_id,
            status_code=409,
            latency_ms=round((time.perf_counter() - inicio) * 1000, 2)
        )
        raise HTTPException(status_code=409, detail="Pagamento para esse pedido já foi processado.")

    import requests
    inicio_catalogo = time.perf_counter()
    try:
        response = requests.get(
            f"{CATALOG_SERVICE_URL}/{payment.item_id}",
            timeout=CATALOG_REQUEST_TIMEOUT,
            headers={CORRELATION_ID_HEADER: correlation_id}
        )
        log_json(
            "INFO",
            correlation_id,
            "Fim da chamada ao catalogo",
            status_code=response.status_code,
            latency_ms=round((time.perf_counter() - inicio_catalogo) * 1000, 2)
        )
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        log_json(
            "ERROR",
            correlation_id,
            "Erro na chamada ao catalogo",
            latency_ms=round((time.perf_counter() - inicio_catalogo) * 1000, 2),
            stack_trace=traceback.format_exc()
        )
        raise HTTPException(status_code=503, detail="Serviço de Catálogo indisponível.")

    if response.status_code == 404:
        log_json(
            "INFO",
            correlation_id,
            "Pagamento rejeitado porque o item nao existe",
            item_id=payment.item_id,
            status_code=400,
            latency_ms=round((time.perf_counter() - inicio) * 1000, 2)
        )
        raise HTTPException(status_code=400, detail="Item não encontrado no catálogo.")

    item = response.json()
    total = item["price"] * payment.quantity

    payment_id = save_payment(
        payment.order_id,
        payment.item_id,
        payment.quantity,
        total,
        payment.method,
        "APROVADO"
    )

    log_json(
        "INFO",
        correlation_id,
        "Pagamento processado com sucesso",
        payment_id=payment_id,
        order_id=payment.order_id,
        total=total,
        method=payment.method,
        status_code=200,
        latency_ms=round((time.perf_counter() - inicio) * 1000, 2)
    )

    return {
        "message": "Pagamento processado com sucesso!",
        "payment_id": payment_id,
        "order_id": payment.order_id,
        "item": item["name"],
        "quantity": payment.quantity,
        "total": total,
        "method": payment.method,
        "status": "APROVADO"
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
