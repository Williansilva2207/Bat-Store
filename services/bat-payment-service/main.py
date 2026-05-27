import os
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
import jwt
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource

from database import init_db, save_payment, get_payment_by_order
from middleware.resilient_http import ResilientFallback, ResilientHttpClient


CATALOG_SERVICE_URL = os.getenv("CATALOG_SERVICE_URL", "http://bat-catalog-service:8000")
CATALOG_REQUEST_TIMEOUT = float(os.getenv("CATALOG_REQUEST_TIMEOUT", "3.0"))
CORRELATION_ID_HEADER = "X-Correlation-ID"
JWT_SECRET = os.getenv("JWT_SECRET", "change-me")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
SERVICE_NAME = "bat-payment-service"

security = HTTPBearer()

catalog_client = ResilientHttpClient(
    service_name=SERVICE_NAME,
    timeout_seconds=CATALOG_REQUEST_TIMEOUT,
)

METODOS_ACEITOS = ["credit_card", "debit_card", "bat_coins"]


def log_json(level: str, message: str, correlation_id=None, **extra):
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "level": level.upper(),
        "service": SERVICE_NAME,
        "correlation_id": correlation_id or "sem-correlation-id",
        "message": message,
    }
    if extra:
        payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False), flush=True)


def setup_tracing(app: FastAPI):
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        resource = Resource.create({"service.name": SERVICE_NAME})
        provider = TracerProvider(resource=resource)
        exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        FastAPIInstrumentor.instrument_app(app)
        log_json("INFO", "OpenTelemetry tracing configurado", endpoint=otlp_endpoint)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log_json("INFO", "Serviço iniciado")
    yield
    log_json("INFO", "Serviço encerrado")

app = FastAPI(title="Bat-Payment-Service", version="1.0.0", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)
setup_tracing(app)


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
        "Inicio do processamento de pagamento",
        correlation_id=correlation_id,
        order_id=payment.order_id,
        item_id=payment.item_id,
        quantity=payment.quantity,
        method=payment.method
    )

    if payment.method not in METODOS_ACEITOS:
        log_json(
            "WARNING",
            "Metodo de pagamento invalido",
            correlation_id=correlation_id,
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
            "WARNING",
            "Pagamento duplicado detectado",
            correlation_id=correlation_id,
            order_id=payment.order_id,
            status_code=409,
            latency_ms=round((time.perf_counter() - inicio) * 1000, 2)
        )
        raise HTTPException(status_code=409, detail="Pagamento para esse pedido já foi processado.")

    try:
        catalog_result = catalog_client.get_json(
            f"{CATALOG_SERVICE_URL}/items/{payment.item_id}",
            cache_key=payment.item_id,
            headers={CORRELATION_ID_HEADER: correlation_id}
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

    log_json(
        "INFO",
        "Pagamento processado com sucesso",
        correlation_id=correlation_id,
        payment_id=payment_id,
        order_id=payment.order_id,
        total=total,
        method=payment.method,
        status_code=200,
        latency_ms=round((time.perf_counter() - inicio) * 1000, 2)
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
def get_payment(order_id: int, request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    correlation_id = request.headers.get(CORRELATION_ID_HEADER, "sem-correlation-id")
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get("role") != "admin":
            log_json("WARNING", "Acesso não autorizado aos pagamentos", correlation_id=correlation_id)
            raise HTTPException(status_code=403, detail="Apenas administradores podem consultar pagamentos.")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido.")
    
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
