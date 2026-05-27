# Arquitetura Técnica - Bat-Store

## Visão Geral da Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                      Internet / Clientes                         │
│                      (Port 5000, 8000-8004)                      │
└────────────┬────────────────────────────────────────────────────┘
             │
        ┌────▼──────────────────────────────────────────┐
        │       Interface Web Flask (5000)              │
        │     ┌─────────────────────────────────┐       │
        │     │ • Health Check (GET /)          │       │
        │     │ • Login (POST /api/login)       │       │
        │     │ • Create Order (POST /api/...)  │       │
        │     │ • Query Notifications           │       │
        │     │ • Query Payments (admin)        │       │
        │     └─────────────────────────────────┘       │
        └────┬──────────────────────────────────────────┘
             │
   ┌─────────┴────────────────────────────────────────────────┐
   │                   Docker Network                          │
   │                   (bridge network)                        │
   │                                                            │
   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
   │  │ Auth Service │  │ Catalog      │  │ Order        │   │
   │  │ (8004)       │  │ (8000)       │  │ (8001)       │   │
   │  │              │  │              │  │              │   │
   │  │ • POST login │  │ • GET /items │  │ • POST /ord- │   │
   │  │ • GET valid- │  │   /{id}      │  │   ers        │   │
   │  │   ate        │  │              │  │ • Calls:     │   │
   │  │ • GET valid- │  │ Resilient    │  │   - Auth     │   │
   │  │   ate/admin  │  │ HTTP Client  │  │   - Catalog  │   │
   │  │ • GET valid- │  │ (retry,      │  │   - Payment  │   │
   │  │   ate/user   │  │ cache,       │  │ • Publishes  │   │
   │  │              │  │ circuit br.) │  │   events     │   │
   │  │ SQLite: auth │  │              │  │              │   │
   │  │ .db          │  │ SQLite:      │  │ SQLite:      │   │
   │  │              │  │ catalog.db   │  │ orders.db    │   │
   │  └──────────────┘  └──────────────┘  └──────────────┘   │
   │                                                            │
   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
   │  │ Payment      │  │ Notification │  │ Redis (6379)│   │
   │  │ (8002)       │  │ (8003)       │  │              │   │
   │  │              │  │              │  │ • Main:      │   │
   │  │ • POST /pay- │  │ • GET /noti- │  │   Queue      │   │
   │  │   ments      │  │   fications/ │  │   (fila_ped- │   │
   │  │ • GET /pay-  │  │   {id}       │  │   idos)      │   │
   │  │   ments/{id} │  │              │  │ • Replica:   │   │
   │  │   (admin)    │  │ Daemon:      │  │   Redundancy │   │
   │  │              │  │ • Consumes   │  │              │   │
   │  │ Calls:       │  │   events     │  │ Persistence: │   │
   │  │ • Catalog    │  │ • Saves to   │  │ RDB + AOF    │   │
   │  │              │  │   db         │  │              │   │
   │  │ SQLite:      │  │              │  └──────────────┘   │
   │  │ payments.db  │  │ SQLite:      │                      │
   │  │              │  │ notifs.db    │  ┌──────────────┐   │
   │  │              │  │              │  │ Redis-Replica│   │
   │  │              │  │              │  │ (6380)       │   │
   │  │              │  │              │  └──────────────┘   │
   │  └──────────────┘  └──────────────┘                      │
   │                                                            │
   │  ┌──────────────────────────────────────────────────┐   │
   │  │            Prometheus (9090)                      │   │
   │  │ • Scrapes /metrics endpoints                      │   │
   │  │ • Storage: prometheus_data/                       │   │
   │  │ • Interval: 15s                                   │   │
   │  └──────────────────────────────────────────────────┘   │
   │                                                            │
   │  ┌──────────────────────────────────────────────────┐   │
   │  │            Grafana (3000)                         │   │
   │  │ • Dashboard de métricas                           │   │
   │  │ • DataSource: Prometheus                          │   │
   │  │ • Credentials: admin/admin                        │   │
   │  └──────────────────────────────────────────────────┘   │
   │                                                            │
   │  ┌──────────────────────────────────────────────────┐   │
   │  │            Jaeger (16686)                         │   │
   │  │ • Tracing distribuído                             │   │
   │  │ • OTLP Collector (4317)                           │   │
   │  └──────────────────────────────────────────────────┘   │
   │                                                            │
   └────────────────────────────────────────────────────────────┘
```

---

## Fluxo de Dados - Criar Pedido

```
User (Port 5000)
    ↓
[1] POST http://localhost:5000/api/create-order
    {item_id, quantity, method}
    ↓
Interface Flask (Flask App)
    ↓
[2] POST http://order:8000/orders
    Headers: Authorization: Bearer TOKEN
            X-Correlation-ID: <uuid>
    Body: {item_id, quantity, method}
    ↓
Order Service
    ├─ [3] GET /validate (Auth Service) → Verifica JWT
    │   ├─ Response: 401 ou {username, role, valid}
    │   └─ PARAR se 401
    │
    ├─ [4] GET http://catalog:8000/items/{item_id}
    │   Headers: X-Correlation-ID
    │   ├─ ResilientHttpClient:
    │   │  ├─ Tentativa 1 (timeout 3s)
    │   │  ├─ Tentativa 2 (backoff 0.5s)
    │   │  ├─ Tentativa 3 (backoff 1s)
    │   │  ├─ Circuit Breaker check
    │   │  └─ Fallback para cache se falhar
    │   │
    │   └─ Response: {id, name, price, stock}
    │
    ├─ [5] Validar estoque
    │   └─ PARAR se quantidade > stock
    │
    ├─ [6] Salvar order em DB
    │   Order: {item_id, quantity, status: PROCESSANDO}
    │
    ├─ [7] POST http://payment:8000/payments
    │   Headers: X-Correlation-ID
    │   Body: {order_id, item_id, quantity, method}
    │   (opcional - tolerante a falhas)
    │
    ├─ [8] Publicar evento em Redis
    │   Key: fila_pedidos
    │   Value: {order_id, item_id, quantity, status, correlation_id}
    │   
    │   BatBrokerMiddleware:
    │   ├─ Conecta ao Redis
    │   ├─ LPUSH fila_pedidos <evento>
    │   └─ Log estruturado em JSON
    │
    └─ [9] Resposta HTTP 200
        {message, order_id, status, correlation_id, degraded}
        ↓
Interface Flask
    ↓
User recebe order_id
```

---

## Fluxo Assíncrono - Notificação

```
Redis Fila (fila_pedidos)
    ↓
[Startup] Notification Service
    ├─ Inicia thread daemon (consumir_fila)
    └─ Conecta ao Redis
        └─ Reconexão automática a cada 5s se falhar
    
[Loop] Enquanto rodando:
    ├─ BLPOP fila_pedidos timeout=5s
    │  └─ Aguarda evento
    │
    ├─ [Evento Recebido] {order_id, item_id, quantity, status, correlation_id}
    │  ├─ Desserializa JSON
    │  ├─ Salva em notifications.db
    │  ├─ Log estruturado com correlation_id
    │  └─ Continue próximo evento
    │
    └─ [Timeout] Sem evento por 5s → Continue loop
    
GET /notifications/{order_id}
    ├─ Query: SELECT * FROM notifications WHERE order_id = ?
    └─ Response: [{notification_id, order_id, ...}]
```

---

## Mecanismos de Resiliência

### 1. Retry com Backoff Exponencial

```python
for attempt in range(max_retries):  # 3 vezes
    try:
        response = client.get(url)  # Timeout 3s
        return response
    except (TimeoutException, ConnectError):
        if attempt < max_retries - 1:
            sleep_time = 2^attempt * base_backoff + random_jitter
            # Sleep 0.5s, 1s, 2s
            time.sleep(sleep_time)
        else:
            fallback_to_cache()
```

### 2. Circuit Breaker

```
Estados: CLOSED → OPEN → HALF_OPEN → CLOSED

CLOSED (normal):
├─ Conta falhas consecutivas
├─ Se falhas >= threshold (5):
│  └─ OPEN
├─ Se sucesso:
│  └─ Reset contador

OPEN (falha):
├─ Rejeita requisições por reset_time (30s)
├─ Retorna fallback_to_cache()
├─ Após 30s:
│  └─ HALF_OPEN (tenta 1 vez)

HALF_OPEN:
├─ Se sucesso:
│  └─ CLOSED
└─ Se falha:
   └─ OPEN novamente
```

### 3. Fallback para Cache

```
try:
    result = resilient_client.get(url)  # Remote
    cache[key] = result.payload
    return result
except ResilientFallback:
    cached = cache.get(key)
    if cached:
        return ResilientResult(cached, fallback=True)
    else:
        HTTPException(503)  # Sem cache
```

### 4. Reconexão Automática ao Redis

```python
def _schedule_reconnect():
    if not _reconnect_thread or not _reconnect_thread.alive():
        _reconnect_thread = Thread(target=_reconnect_loop, daemon=True)
        _reconnect_thread.start()

def _reconnect_loop():
    while True:
        try:
            client.ping()
            log("redis_connection_restored")
            return
        except RedisError:
            log("redis_connection_failed")
            time.sleep(5)  # Retry a cada 5s
```

---

## Segurança

### JWT (JSON Web Token)

```
Algoritmo: HS256
Assinatura: JWT_SECRET (lida de .env)

Payload:
{
  "sub": "batman",         # Username
  "role": "admin",         # Role (admin, user, support)
  "exp": 1716806400,       # Expiration (24h default)
  "iat": 1716720000        # Issued at
}

Header:
{
  "type": "JWT",
  "alg": "HS256"
}

Token completo: header.payload.signature
```

### Hash de Senhas

```
Algoritmo: bcrypt
Salt rounds: auto (gensalt padrão)

Armazenamento:
users.password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())

Verificação:
bcrypt.checkpw(password.encode(), hash.encode())
```

### Proteção de Endpoints

```
/login → Nenhuma (público)
/validate → JWT obrigatório (qualquer role)
/validate/admin → JWT + role==admin
/validate/user → JWT obrigatório
/orders → JWT obrigatório
/payments/{id} → JWT + role==admin (protegido)
```

---

## Observabilidade

### Correlation ID

```
Gerado em: Order Service (UUID v4)
Propagado em:
├─ Header HTTP: X-Correlation-ID
├─ Payload da fila: {correlation_id}
└─ Todos os logs: "correlation_id": "..."

Uso:
├─ Rastrear requisição através de serviços
├─ Correlacionar eventos na fila
├─ Link entre logs e traces
└─ Debug end-to-end
```

### Logs Estruturados (JSON)

```json
{
  "timestamp": "2024-05-27T10:30:45.123Z",
  "level": "INFO",
  "service": "bat-order-service",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Pedido criado com sucesso",
  "order_id": 42,
  "item_id": "bat-01",
  "quantity": 1,
  "degraded": false,
  "latency_ms": 150.25
}
```

### Métricas Prometheus

Coletadas via prometheus-fastapi-instrumentator:

```
# TYPE http_requests_total counter
http_requests_total{
  method="post",
  path="/orders",
  status="200",
  service="bat-order-service"
} 42

# TYPE http_request_duration_seconds histogram
http_request_duration_seconds_bucket{
  le="0.005",
  method="post",
  path="/orders"
} 5

http_request_duration_seconds_bucket{
  le="0.1",
  method="post",
  path="/orders"
} 35

# ... outros buckets e métricas
```

### Traces Distribuídos (Jaeger)

Via OpenTelemetry (experimental):

```
Trace: POST /orders

Spans:
├─ order_service.post_orders (200ms)
│  ├─ catalog.get_item (80ms)
│  ├─ payment.process_payment (50ms)
│  └─ redis.publish_event (10ms)
└─ Atributos: {correlation_id, http.status_code, ...}
```

---

## Persistência de Dados

### SQLite Databases (Local)

```
/services/bat-auth-service/auth.db
├─ users (id, username, password_hash, role)

/services/bat-catalog-service/catalog.db
├─ items (id, name, description, price, stock)

/services/bat-order-service/orders.db
├─ orders (id, item_id, quantity, status)

/services/bat-payment-service/payments.db
├─ payments (id, order_id, item_id, quantity, total, method, status)

/services/bat-notification-service/notifications.db
├─ notifications (id, order_id, item_id, quantity, status, sent_at)
```

### Redis (Fila + Cache)

```
fila_pedidos (List)
├─ [{order_id, item_id, quantity, status, correlation_id}, ...]

Cache (Hash per service)
├─ ResilientHttpClient cache:
│  └─ item-id → {id, name, price, stock}

Persistence:
├─ RDB: Snapshot periódico (60s)
├─ AOF: Append-only file (cada operação)
└─ Replication: redis-replica (6380)
```

---

## Deploymentdocker-compose

### Imagens

```
Services:
├─ python:3.11-slim (auth, catalog, order, payment, notification)
├─ python:3.11-slim (interface - Flask)

Infrastructure:
├─ redis:7-alpine (Redis main + replica)
├─ prom/prometheus:latest (Prometheus)
├─ grafana/grafana:latest (Grafana)
├─ jaegertracing/all-in-one:latest (Jaeger)
```

### Networking

```
Network: docker compose bridge network (padrão)

DNS internal:
├─ auth → http://auth:8000
├─ catalog → http://catalog:8000
├─ order → http://order:8000
├─ payment → http://payment:8000
├─ notification → http://notification:8000
├─ redis → http://redis:6379
├─ redis-replica → http://redis-replica:6379
├─ prometheus → http://prometheus:9090
├─ grafana → http://grafana:3000
└─ jaeger → http://jaeger:16686

Port Mapping (localhost):
├─ 8000: catalog
├─ 8001: order
├─ 8002: payment
├─ 8003: notification
├─ 8004: auth
├─ 5000: interface (Flask)
├─ 6379: redis
├─ 9090: prometheus
├─ 3000: grafana
└─ 16686: jaeger
```

### Dependency Order

```
[Startup]
1. redis (nenhuma dependência)
2. auth (nenhuma dependência)
3. catalog (nenhuma dependência)
4. payment (depends_on: catalog)
5. order (depends_on: catalog, redis, auth, payment)
6. notification (depends_on: redis)
7. prometheus (depends_on: todos os serviços)
8. grafana (depends_on: prometheus)
9. jaeger (nenhuma dependência)
10. interface (depends_on: todos os serviços)
```

---

## Escalabilidade

### Horizontal (Replicas)

```docker-compose.yml
deploy:
  replicas: 2  # 2 instâncias de cada serviço
```

Com replicas:
- Docker Compose cria múltiplas instâncias
- Mesma porta exposta no host (pode conflitar)
- Solução: Load balancer ou reverse proxy

### Vertical

- Aumentar CPU/RAM alocada ao container
- Aumentar timeouts em prod
- Cache size em ResilientHttpClient

### Futuros

- Kubernetes para orquestração
- Separar Prometheus/Grafana em hosts distintos
- Banco de dados centralizado (PostgreSQL)
- Message broker profissional (RabbitMQ/Kafka)
- CDN para assets estáticos

---