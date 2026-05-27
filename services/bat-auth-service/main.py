import os
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import bcrypt
import jwt
from prometheus_fastapi_instrumentator import Instrumentator
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource

from database import init_db, get_user

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_HOURS = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

SERVICE_NAME = "bat-auth-service"

security = HTTPBearer()


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

app = FastAPI(title="Bat-Auth-Service", version="1.0.0", lifespan=lifespan)
Instrumentator().instrument(app).expose(app)
setup_tracing(app)


class LoginRequest(BaseModel):
    username: str
    password: str


def create_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido.")


@app.get("/")
def home():
    return {"service": "Bat-Auth-Service", "status": "Online"}


@app.post("/login")
def login(data: LoginRequest):
    log_json("INFO", "Tentativa de login", username=data.username)
    user = get_user(data.username)
    if user is None:
        log_json("WARNING", "Usuário não encontrado", username=data.username)
        raise HTTPException(status_code=401, detail="Usuário não encontrado.")

    if not bcrypt.checkpw(data.password.encode(), user["password"].encode()):
        log_json("WARNING", "Senha incorreta", username=data.username)
        raise HTTPException(status_code=401, detail="Senha incorreta.")

    token = create_token(user["username"], user["role"])
    log_json("INFO", "Login realizado com sucesso", username=user["username"], role=user["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"]
    }


@app.get("/validate")
def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    log_json("INFO", "Token validado", username=payload["sub"], role=payload["role"])
    return {
        "username": payload["sub"],
        "role": payload["role"],
        "valid": True
    }


@app.get("/validate/admin")
def validate_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if payload["role"] != "admin":
        log_json("WARNING", "Acesso admin negado", username=payload["sub"], role=payload["role"])
        raise HTTPException(status_code=403, detail="Acesso negado. Apenas administradores.")
    log_json("INFO", "Acesso admin validado", username=payload["sub"])
    return {
        "username": payload["sub"],
        "role": payload["role"],
        "valid": True
    }


@app.get("/validate/user")
def validate_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    log_json("INFO", "Dados do usuário retornados", username=payload["sub"], role=payload["role"])
    return {
        "username": payload["sub"],
        "role": payload["role"],
        "valid": True
    }
