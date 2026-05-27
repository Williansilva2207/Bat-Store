import json
import os
import threading
import traceback
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis
from fastapi import FastAPI, HTTPException
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource

from database import init_db, save_notification, get_notifications_by_order

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
QUEUE_NAME = os.environ["QUEUE_NAME"]
REDIS_BLOCK_TIMEOUT = int(os.environ["REDIS_BLOCK_TIMEOUT"])
REDIS_RECONNECT_INTERVAL = int(os.environ.get("REDIS_RECONNECT_INTERVAL", "5"))

SERVICE_NAME = "bat-notification-service"


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


def processar_mensagem(mensagem: dict):
    order_id = mensagem.get("order_id")
    item_id = mensagem.get("item_id")
    quantity = mensagem.get("quantity")
    status = mensagem.get("status")
    correlation_id = mensagem.get("correlation_id", "sem-correlation-id")
    sent_at = datetime.utcnow().isoformat()

    notification_id = save_notification(order_id, item_id, quantity, status, sent_at)

    log_json(
        "INFO",
        "Mensagem consumida da fila e notificacao salva",
        correlation_id=correlation_id,
        order_id=order_id,
        item_id=item_id,
        quantity=quantity,
        status=status,
        notification_id=notification_id
    )


def conectar_redis():
    while True:
        try:
            cliente = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                decode_responses=True,
                socket_timeout=3,
            )
            cliente.ping()
            log_json("INFO", "Conexão com Redis estabelecida")
            return cliente
        except redis.RedisError as error:
            log_json("ERROR", "Falha na conexão com Redis", error=str(error))
            time.sleep(REDIS_RECONNECT_INTERVAL)


def consumir_fila():
    cliente_redis = conectar_redis()
    log_json("INFO", "Consumidor iniciado", queue_name=QUEUE_NAME)

    while True:
        try:
            mensagem_raw = cliente_redis.blpop(QUEUE_NAME, timeout=REDIS_BLOCK_TIMEOUT)
            if mensagem_raw:
                _, mensagem_json = mensagem_raw
                mensagem = json.loads(mensagem_json)
                processar_mensagem(mensagem)
        except redis.RedisError as error:
            log_json("ERROR", "Falha na conexão com Redis durante consumo", error=str(error))
            cliente_redis = conectar_redis()
        except json.JSONDecodeError as error:
            log_json("ERROR", "Falha ao decodificar mensagem JSON", error=str(error))
        except Exception as e:
            log_json(
                "ERROR",
                "Erro ao consumir fila",
                error=str(e),
                stack_trace=traceback.format_exc()
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    thread = threading.Thread(target=consumir_fila, daemon=True)
    thread.start()
    log_json("INFO", "Serviço iniciado")
    yield
    log_json("INFO", "Serviço encerrado")

app = FastAPI(title="Bat-Notification-Service", version="1.0.0", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)
setup_tracing(app)


@app.get("/")
def home():
    return {"service": "Bat-Notification-Service", "status": "Online"}


@app.get("/notifications/{order_id}")
def get_notifications(order_id: int):
    notifications = get_notifications_by_order(order_id)
    if not notifications:
        raise HTTPException(status_code=404, detail="Nenhuma notificação encontrada para esse pedido.")
    return [
        {
            "notification_id": n["id"],
            "order_id": n["order_id"],
            "item_id": n["item_id"],
            "quantity": n["quantity"],
            "status": n["status"],
            "sent_at": n["sent_at"]
        }
        for n in notifications
    ]
