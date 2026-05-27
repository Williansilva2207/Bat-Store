import json
import time
from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, HTTPException, Request
from database import init_db, get_db_connect

CORRELATION_ID_HEADER = "X-Correlation-ID"

def log_json(level: str, correlation_id: str, message: str, **extra):
    print(json.dumps({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": level,
        "service": "bat-catalog-service",
        "correlation_id": correlation_id,
        "message": message,
        **extra
    }, ensure_ascii=False))

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Bat-Catalog-Service", version="1.0.0", lifespan=lifespan)

@app.get("/")
def home():
    return {"service": "Bat-Catalog-Service", "status": "Online"}

@app.get("/items/{id}")
def get_itemID(id: str, request: Request):
    correlation_id = request.headers.get(CORRELATION_ID_HEADER, "sem-correlation-id")
    inicio = time.perf_counter()
    log_json("INFO", correlation_id, "Consulta de item iniciada", item_id=id)

    conecta = get_db_connect()
    cursor = conecta.cursor()
    cursor.execute("SELECT id, name, price, stock FROM items WHERE id = ?", (id,))
    item = cursor.fetchone()
    conecta.close()

    if item is None:
        log_json(
            "INFO",
            correlation_id,
            "Item nao encontrado no catalogo",
            item_id=id,
            status_code=404,
            latency_ms=round((time.perf_counter() - inicio) * 1000, 2)
        )
        raise HTTPException(status_code=404, detail="Item não encontrado no catálogo da Bat-Store")
    
    log_json(
        "INFO",
        correlation_id,
        "Item encontrado no catalogo",
        item_id=item["id"],
        stock=item["stock"],
        status_code=200,
        latency_ms=round((time.perf_counter() - inicio) * 1000, 2)
    )

    return {
        "id": item["id"],
        "name": item["name"],
        "price": item["price"],
        "stock": item["stock"]
    }
