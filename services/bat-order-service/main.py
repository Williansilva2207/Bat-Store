import os
import json
import uuid
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource

from database import init_db, save_order
from middleware.broker import BatBrokerMiddleware
from middleware.resilient_http import ResilientFallback, ResilientHttpClient

AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://bat-auth-service:8000")
CATALOG_SERVICE_URL = os.getenv("CATALOG_SERVICE_URL", "http://bat-catalog-service:8000")
PAYMENT_SERVICE_URL = os.getenv("PAYMENT_SERVICE_URL", "http://bat-payment-service:8000")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "3"))
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
QUEUE_NAME = os.getenv("QUEUE_NAME", "fila_pedidos")
CORRELATION_ID_HEADER = "X-Correlation-ID"

SERVICE_NAME = "bat-order-service"

security = HTTPBearer()

catalog_client = ResilientHttpClient(
    service_name=SERVICE_NAME,
    timeout_seconds=REQUEST_TIMEOUT,
)

payment_client = ResilientHttpClient(
    service_name=SERVICE_NAME,
    timeout_seconds=REQUEST_TIMEOUT,
)

broker = BatBrokerMiddleware(host=REDIS_HOST, port=REDIS_PORT, service_name=SERVICE_NAME)


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


def validate_token_via_auth(token: str, correlation_id: str) -> dict:
    """Valida token JWT chamando bat-auth-service via REST (GET /validate)."""
    try:
        response = httpx.get(
            f"{AUTH_SERVICE_URL}/validate",
            headers={
                "Authorization": f"Bearer {token}",
                CORRELATION_ID_HEADER: correlation_id,
            },
            timeout=REQUEST_TIMEOUT,
        )
        if response.status_code == 401:
            detail = response.json().get("detail", "Token inválido.")
            raise HTTPException(status_code=401, detail=detail)
        if response.status_code == 403:
            detail = response.json().get("detail", "Acesso negado.")
            raise HTTPException(status_code=403, detail=detail)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail="Falha na validação do token.")
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        log_json("ERROR", "Auth Service indisponível", correlation_id=correlation_id, error=str(exc))
        raise HTTPException(status_code=503, detail="Serviço de autenticação indisponível.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log_json("INFO", "Serviço iniciado")
    yield
    log_json("INFO", "Serviço encerrado")

app = FastAPI(title="Bat-Order-Service", version="1.0.0", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)
setup_tracing(app)


class OrderRequest(BaseModel):
    item_id: str
    quantity: int
    method: str = "credit_card"


@app.get("/")
def home():
    return {"service": "Bat-Order-Service", "status": "Online"}


@app.post("/orders")
def create_order(order: OrderRequest, request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    # Gerar correlation ID
    correlation_id = request.headers.get(CORRELATION_ID_HEADER)
    if not correlation_id:
        correlation_id = str(uuid.uuid4())

    inicio = time.perf_counter()
    log_json("INFO", "Início do processamento de pedido", correlation_id=correlation_id,
             item_id=order.item_id, quantity=order.quantity, method=order.method)

    # 1. Validar token via Auth Service (REST call)
    auth_data = validate_token_via_auth(credentials.credentials, correlation_id)
    username = auth_data.get("username", "desconhecido")
    log_json("INFO", "Token validado via Auth Service", correlation_id=correlation_id, username=username)

    # 2. Consultar Catalog Service com X-Correlation-ID (resiliência)
    degraded_mode = False
    try:
        catalog_result = catalog_client.get_json(
            f"{CATALOG_SERVICE_URL}/items/{order.item_id}",
            cache_key=order.item_id,
            headers={CORRELATION_ID_HEADER: correlation_id}
        )
        item_catalogo = catalog_result.payload
        degraded_mode = catalog_result.fallback
    except ResilientFallback as fallback:
        if fallback.payload is not None:
            item_catalogo = fallback.payload
            degraded_mode = True
        else:
            log_json("ERROR", "Catálogo indisponível após retries", correlation_id=correlation_id)
            raise HTTPException(
                status_code=503,
                detail="Serviço de Catálogo indisponível. Tente novamente mais tarde.",
            )
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status_code=400, detail="O item solicitado não existe.")
        raise HTTPException(
            status_code=503,
            detail="Serviço de Catálogo indisponível.",
        )

    log_json("INFO", "Catálogo consultado", correlation_id=correlation_id,
             item_id=order.item_id, stock=item_catalogo.get("stock"), degraded=degraded_mode)

    # 3. Verificar estoque
    if item_catalogo["stock"] < order.quantity:
        raise HTTPException(status_code=400, detail="Estoque insuficiente.")

    # 4. Salvar pedido
    status_pedido = "PROCESSANDO_DEGRADADO" if degraded_mode else "PROCESSANDO"
    new_order_id = save_order(order.item_id, order.quantity, status_pedido)

    # 5. Chamar Payment Service com X-Correlation-ID (resiliência)
    try:
        payment_result = payment_client.post_json(
            f"{PAYMENT_SERVICE_URL}/payments",
            json_data={
                "order_id": new_order_id,
                "item_id": order.item_id,
                "quantity": order.quantity,
                "method": order.method,
            },
            headers={CORRELATION_ID_HEADER: correlation_id},
        )
        log_json("INFO", "Pagamento processado", correlation_id=correlation_id,
                 order_id=new_order_id, payment=payment_result.payload)
    except ResilientFallback:
        log_json("WARNING", "Payment Service indisponível", correlation_id=correlation_id,
                 order_id=new_order_id)
    except httpx.HTTPStatusError as exc:
        log_json("WARNING", "Erro no Payment Service", correlation_id=correlation_id,
                 order_id=new_order_id, status_code=exc.response.status_code)

    # 6. Publicar evento na fila_pedidos com correlation_id
    broker.publish_event(queue_name=QUEUE_NAME, payload={
        "order_id": new_order_id,
        "item_id": order.item_id,
        "quantity": order.quantity,
        "status": "APPROVED",
        "degraded": degraded_mode,
        "correlation_id": correlation_id,
    })

    latency_ms = round((time.perf_counter() - inicio) * 1000, 2)
    response_message = (
        "Pedido realizado com sucesso em modo degradado (cache do catálogo)."
        if degraded_mode
        else "Pedido realizado com sucesso!"
    )

    log_json("INFO", "Pedido criado", correlation_id=correlation_id,
             order_id=new_order_id, status=status_pedido, latency_ms=latency_ms)

    return {
        "message": response_message,
        "order_id": new_order_id,
        "status": status_pedido,
        "degraded": degraded_mode,
        "correlation_id": correlation_id,
    }
