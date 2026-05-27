import os
import json
import threading
import traceback
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException
import redis
from database import init_db, save_notification, get_notifications_by_order

REDIS_HOST = os.environ["REDIS_HOST"]
REDIS_PORT = int(os.environ["REDIS_PORT"])
QUEUE_NAME = os.environ["QUEUE_NAME"]
REDIS_BLOCK_TIMEOUT = int(os.environ["REDIS_BLOCK_TIMEOUT"])

def log_json(level: str, correlation_id: str, message: str, **extra):
    print(json.dumps({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "service": "bat-notification-service",
        "correlation_id": correlation_id,
        "message": message,
        **extra
    }, ensure_ascii=False))

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
        correlation_id,
        "Mensagem consumida da fila e notificacao salva",
        order_id=order_id,
        item_id=item_id,
        quantity=quantity,
        status=status,
        notification_id=notification_id
    )

def consumir_fila():
    cliente_redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    print(f"[NOTIFICATION] Aguardando mensagens na fila '{QUEUE_NAME}'...")
    while True:
        try:
            mensagem_raw = cliente_redis.blpop(QUEUE_NAME, timeout=REDIS_BLOCK_TIMEOUT)
            if mensagem_raw:
                _, mensagem_json = mensagem_raw
                mensagem = json.loads(mensagem_json)
                processar_mensagem(mensagem)
        except Exception as e:
            log_json(
                "ERROR",
                "sem-correlation-id",
                "Erro ao consumir fila",
                error=str(e),
                stack_trace=traceback.format_exc()
            )

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    thread = threading.Thread(target=consumir_fila, daemon=True)
    thread.start()
    yield

app = FastAPI(title="Bat-Notification-Service", version="1.0.0", lifespan=lifespan)

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
