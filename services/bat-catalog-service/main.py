import os
import json
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource

from database import init_db, get_db_connect

CORRELATION_ID_HEADER = "X-Correlation-ID"
SERVICE_NAME = "bat-catalog-service"


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

app = FastAPI(title="Bat-Catalog-Service", version="1.0.0", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)
setup_tracing(app)


@app.get("/")
def home():
    return {"service": "Bat-Catalog-Service", "status": "Online"}


@app.get("/items/{id}")
def get_item(id: str, request: Request):
    correlation_id = request.headers.get(CORRELATION_ID_HEADER, "sem-correlation-id")
    inicio = time.perf_counter()
    log_json("INFO", "Consulta de item iniciada", correlation_id=correlation_id, item_id=id)

    conecta = get_db_connect()
    cursor = conecta.cursor()
    cursor.execute("SELECT id, name, price, stock FROM items WHERE id = ?", (id,))
    item = cursor.fetchone()
    conecta.close()

    latency_ms = round((time.perf_counter() - inicio) * 1000, 2)

    if item is None:
        log_json(
            "WARNING",
            "Item não encontrado no catálogo",
            correlation_id=correlation_id,
            item_id=id,
            status_code=404,
            latency_ms=latency_ms,
        )
        raise HTTPException(status_code=404, detail="Item não encontrado no catálogo da Bat-Store")

    log_json(
        "INFO",
        "Item encontrado no catálogo",
        correlation_id=correlation_id,
        item_id=item["id"],
        stock=item["stock"],
        status_code=200,
        latency_ms=latency_ms,
    )

    return {
        "id": item["id"],
        "name": item["name"],
        "price": item["price"],
        "stock": item["stock"]
    }
