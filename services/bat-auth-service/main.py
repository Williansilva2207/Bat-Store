import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import bcrypt
import jwt
from datetime import datetime, timedelta
from database import init_db, get_user

JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALGORITHM = os.environ["JWT_ALGORITHM"]
JWT_EXPIRATION_HOURS = int(os.environ["JWT_EXPIRATION_HOURS"])

security = HTTPBearer()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Bat-Auth-Service", version="1.0.0", lifespan=lifespan)

class LoginRequest(BaseModel):
    username: str
    password: str

def create_token(username: str, role: str) -> str:
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
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
    user = get_user(data.username)
    if user is None:
        raise HTTPException(status_code=401, detail="Usuário não encontrado.")

    if not bcrypt.checkpw(data.password.encode(), user["password"].encode()):
        raise HTTPException(status_code=401, detail="Senha incorreta.")

    token = create_token(user["username"], user["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"]
    }

@app.get("/validate")
def validate_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    return {
        "username": payload["sub"],
        "role": payload["role"],
        "valid": True
    }

@app.get("/validate/admin")
def validate_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    payload = decode_token(credentials.credentials)
    if payload["role"] != "admin":
        raise HTTPException(status_code=403, detail="Acesso negado. Apenas administradores.")
    return {
        "username": payload["sub"],
        "role": payload["role"],
        "valid": True
    }
