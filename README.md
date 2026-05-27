# Bat-Store
**Trabalho Prático - Arquitetura de Sistemas Distribuídos**

Implementação completa de um middleware distribuído em Python com FastAPI, demonstrando comunicação síncrona (HTTP/REST) e assíncrona (Redis Pub/Sub), resiliência, observabilidade e segurança com JWT.

---

## Equipe


---

## Visão Geral da Arquitetura

A **Bat-Store** é um sistema de e-commerce temático (Batman 🦇) implementado como **5 microsserviços independentes**:

| Serviço | Porta | Descrição | Status |
|---------|-------|-----------|--------|
| **bat-auth-service** | 8004 | Autenticação JWT e autorização | ✅ |
| **bat-catalog-service** | 8000 | Catálogo de produtos e estoque | ✅ |
| **bat-order-service** | 8001 | Criação e gestão de pedidos | ✅ |
| **bat-payment-service** | 8002 | Processamento de pagamentos | ✅ |
| **bat-notification-service** | 8003 | Consumidor de fila de eventos | ✅ |

### Infraestrutura Adicional

| Componente | Porta | Descrição |
|-----------|-------|-----------|
| **Redis** | 6379 | Fila de mensagens (pub/sub) |
| **Prometheus** | 9090 | Coleta de métricas |
| **Grafana** | 3000 | Dashboard de métricas |
| **Jaeger** | 16686 | Tracing distribuído |
| **Interface Flask** | 5000 | Web UI para testes |

---

## Quick Start

### Pré-requisitos

- Docker e Docker Compose instalados
- Git instalado

### 1. Clonar e Configurar Repositório

```bash
git clone https://github.com/Williansilva2207/Bat-Store.git
cd Bat-Store

# Criar arquivo .env a partir do template
cp .env.example .env
```

### 2. Subir Todos os Serviços

```bash
# Build das imagens
docker compose build

# Subir containers
docker compose up -d

# Ou tudo de uma vez
docker compose up --build -d
```

### 3. Verificar Status

```bash
# Ver status dos containers
docker compose ps

# Ver logs
docker compose logs -f
```

---

## Como Usar o Sistema

### Acesso à Interface Web

```
http://localhost:5000
```

Página inicial mostra status de todos os serviços em tempo real.

### Fluxo Completo: Criar um Pedido

#### 1. Fazer Login

```bash
curl -X POST http://localhost:8004/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "batman",
    "password": "change-me"
  }'

# Resposta:
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "role": "admin"
}
```

**Usuários de teste:**
- `batman` / `change-me` (admin)
- `robin` / `change-me` (user)
- `alfred` / `change-me` (support)

#### 2. Criar um Pedido (requer token JWT)

```bash
export TOKEN="eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."

curl -X POST http://localhost:8001/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "item_id": "bat-01",
    "quantity": 1,
    "method": "credit_card"
  }'

# Resposta:
{
  "message": "Pedido realizado com sucesso!",
  "order_id": 1,
  "status": "PROCESSANDO",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "degraded": false
}
```

#### 3. Consultar Notificação

```bash
curl http://localhost:8003/notifications/1
# Resposta:
[
  {
    "notification_id": 1,
    "order_id": 1,
    "item_id": "bat-01",
    "quantity": 1,
    "status": "APPROVED",
    "sent_at": "2024-05-27T10:30:45.123Z"
  }
]
```

#### 4. Consultar Pagamento (requer token admin)

```bash
curl http://localhost:8002/payments/1 \
  -H "Authorization: Bearer $TOKEN"

# Resposta:
{
  "payment_id": 1,
  "order_id": 1,
  "item_id": "bat-01",
  "quantity": 1,
  "total": 299.90,
  "method": "credit_card",
  "status": "APROVADO"
}
```

---

## Endpoints Protegidos

### Autenticação (sem proteção)
- `POST /login` - Faz login e retorna JWT token
- `GET /validate` - Valida token genérico
- `GET /validate/admin` - Valida token admin (retorna 403 se não admin)
- `GET /validate/user` - Valida token de usuário

### Pedidos (protegido com JWT)
- `POST /orders` - Criar novo pedido (requer token válido)

### Pagamentos (protegido com JWT + admin)
- `GET /payments/{order_id}` - Consultar pagamento (requer token admin)

---

## Observabilidade

### Grafana - Dashboard de Métricas

```
http://localhost:3000
Credenciais: admin / admin
```

**Painéis disponíveis:**
- Requisições por segundo (RPS) por serviço
- Latência p50, p95, p99
- Taxa de erros (4xx, 5xx)
- Status de circuit breaker
- Cache hit rate

### Jaeger - Tracing Distribuído

```
http://localhost:16686
```

**Recursos:**
- Traces completos para fluxo de pedido
- Propagação de X-Correlation-ID
- Latência por span
- Identificação de gargalos

### Prometheus - Métricas Brutas

```
http://localhost:9090
```

**Endpoints de métricas em cada serviço:**
- `GET http://localhost:8000/metrics` (catalog)
- `GET http://localhost:8001/metrics` (order)
- `GET http://localhost:8002/metrics` (payment)
- `GET http://localhost:8003/metrics` (notification)
- `GET http://localhost:8004/metrics` (auth)

---

## Testando Resiliência

### Teste 1: Catalog Service Fica Indisponível

```bash
# Derrubar serviço
docker pause catalog

# Tentar criar pedido (deve retornar 503 ou usar cache)
curl -X POST http://localhost:8001/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"item_id": "bat-01", "quantity": 1}'

# Ver tentativas de retry nos logs
docker compose logs order | grep retry

# Trazer de volta
docker unpause catalog

# Próxima requisição funciona normalmente
```

### Teste 2: Redis Fica Indisponível

```bash
# Derrubar Redis
docker stop redis

# Criar pedido (será criado mas notificação não será enviada)
curl -X POST http://localhost:8001/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"item_id": "bat-01", "quantity": 1}'

# Ver erro de reconexão nos logs
docker compose logs order | grep redis_connection_failed

# Trazer de volta
docker start redis

# Verificar que events acumulados são processados
docker compose logs notification | grep Mensagem
```

### Teste 3: Verificar Propagação de Correlation ID

```bash
# Criar pedido com verbose
curl -v -X POST http://localhost:8001/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"item_id": "bat-01", "quantity": 1}' 2>&1 | grep correlation_id

# Ver no Jaeger que o mesmo ID propaga nos spans
# http://localhost:16686 → Search → bat-order-service
```

---

## Variáveis de Ambiente

Arquivo `.env.example` contém todas as variáveis com padrões sensatos:

```env
# App / Uvicorn
APP_HOST=0.0.0.0
APP_PORT=8000

# Docker host ports
CATALOG_HOST_PORT=8000
ORDER_HOST_PORT=8001
PAYMENT_HOST_PORT=8002
NOTIFICATION_HOST_PORT=8003
AUTH_HOST_PORT=8004
REDIS_HOST_PORT=6379
PROMETHEUS_HOST_PORT=9090
GRAFANA_HOST_PORT=3000
JAEGER_HOST_PORT=16686

# Auth / JWT
JWT_SECRET=change-me-to-a-secure-secret
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

# Service URLs
CATALOG_SERVICE_URL=http://catalog:8000/items
AUTH_SERVICE_URL=http://auth:8000
PAYMENT_SERVICE_URL=http://payment:8000
ORDER_SERVICE_URL=http://order:8000
NOTIFICATION_SERVICE_URL=http://notification:8000
CATALOG_REQUEST_TIMEOUT=3.0
REQUEST_TIMEOUT=3.0

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_RECONNECT_INTERVAL=5
QUEUE_NAME=fila_pedidos
REDIS_BLOCK_TIMEOUT=5
```

---

## Documentação Técnica

### Comunicação Síncrona (HTTP/REST)

- **Order → Catalog**: Validar estoque via `GET /items/{id}`
- **Order → Payment**: Processar pagamento via `POST /payments`
- **Payment → Catalog**: Consultar preço via `GET /items/{id}`
- **Order → Auth**: Validar token via `GET /validate`

Todos com **retry automático** + **circuit breaker** + **fallback para cache**.

### Comunicação Assíncrona (Fila Redis)

- **Order → Notification**: Publica evento em `fila_pedidos`
- **Notification**: Consumidor daemon que processa eventos
- Garante entrega eventual de notificações mesmo com falhas temporárias

### Segurança

- **JWT (HS256)** com assinatura via JWT_SECRET
- **Bcrypt** para hash de senhas (nunca em plaintext)
- **Roles**: admin, user, support
- **Proteção de endpoints**: Validação obrigatória de token

### Resiliência

- **Retry**: até 3 tentativas com backoff exponencial (0.5s, 1s, 2s)
- **Circuit Breaker**: Abre após 5 falhas, fecha após 30s
- **Cache**: Armazena respostas recentes para fallback
- **Reconexão automática**: Thread daemon para Redis

### Observabilidade

- **Logs estruturados**: JSON com timestamp, level, service, correlation_id
- **Métricas Prometheus**: Requisições, latência, erros
- **Tracing Jaeger**: Traces distribuídos com X-Correlation-ID
- **Dashboard Grafana**: Visualização de métricas em tempo real

---

## Estrutura do Projeto

```
Bat-Store/
├── services/
│   ├── bat-auth-service/
│   │   ├── main.py              # Autenticação JWT
│   │   ├── database.py          # SQLite users
│   │   ├── requirements.txt
│   │   └── dockerfile
│   ├── bat-catalog-service/
│   │   ├── main.py              # GET /items/{id}
│   │   ├── database.py          # SQLite items
│   │   ├── requirements.txt
│   │   └── dockerfile
│   ├── bat-order-service/
│   │   ├── main.py              # POST /orders (protegido)
│   │   ├── database.py          # SQLite orders
│   │   ├── requirements.txt
│   │   └── dockerfile
│   ├── bat-payment-service/
│   │   ├── main.py              # POST /payments, GET /payments/{id}
│   │   ├── database.py          # SQLite payments
│   │   ├── requirements.txt
│   │   └── dockerfile
│   └── bat-notification-service/
│       ├── main.py              # GET /notifications/{id}
│       ├── database.py          # SQLite notifications
│       ├── requirements.txt
│       └── dockerfile
├── middleware/
│   ├── broker.py                # BatBrokerMiddleware (Redis pub/sub)
│   ├── resilient_http.py        # ResilientHttpClient (retry + circuit breaker)
│   └── structured_logging.py    # Logs JSON
├── interface/
│   ├── app.py                   # Interface Flask
│   ├── requirements.txt
│   ├── Dockerfile
│   └── templates/
│       ├── index.html
│       ├── auth.html
│       ├── catalog.html
│       ├── orders.html
│       └── observability.html
├── docs/
│   └── fault-tolerance.md       # Documentação de resiliência
├── prometheus.yml               # Config Prometheus
├── docker-compose.yml           # Orquestração
├── .env.example                 # Template de variáveis
└── README.md                    # Este arquivo
```

---

## Testes da Implementação

### 1. Fluxo Completo (sem falhas)
```bash
# 1. Login
# 2. Criar pedido
# 3. Validar notificação gerada
# 4. Consultar pagamento (como admin)
```

### 2. Tolerância a Falhas
```bash
# 1. Derrubar catalog-service
# 2. Tentar criar pedido (verifica retry + fallback + 503)
# 3. Trazer catalog de volta
# 4. Pedido agora funciona
```

### 3. Observabilidade
```bash
# 1. Criar 10 pedidos
# 2. Acessar Grafana
# 3. Verificar RPS, latência, erros
# 4. Acessar Jaeger
# 5. Rastrear trace completo com correlation_id
```

---

## Troubleshooting

### "Connection refused" ao chamar serviço

Verifique se container está rodando:
```bash
docker compose ps

# Se não estiver, veja logs:
docker compose logs <service_name>
```

### "Token inválido" ou "Token expirado"

Gere novo token com POST /login. Tokens expiram em 24 horas (JWT_EXPIRATION_HOURS).

### Notificações não aparecem

Verifique se Redis está rodando:
```bash
docker compose ps redis

# Verifique logs do notification-service:
docker compose logs notification | grep "Mensagem consumida"
```

### Métricas não aparecem em Prometheus

Aguarde 15-30 segundos para primeira coleta. Prometheus scrape de 15 em 15 segundos.

---

## Status de Implementação

### Obrigatórios Implementados
- [x] 2 serviços independentes
- [x] Docker + docker-compose
- [x] Comunicação síncrona (HTTP/REST)
- [x] Comunicação assíncrona (Redis Pub/Sub)
- [x] Retry com backoff exponencial
- [x] Circuit breaker
- [x] Fallback para cache
- [x] JWT (autenticação e autorização)
- [x] Proteção de endpoints (401/403)
- [x] Logs estruturados JSON
- [x] Correlation ID propagado
- [x] docs/fault-tolerance.md
- [x] README completo

### Bônus Implementados
- [x] Mais de 3 serviços (5 serviços)
- [x] Configuração externalizada (.env)
- [x] Mais de 1 mecanismo de resiliência
- [x] Prometheus + Grafana
- [x] Jaeger (tracing distribuído)

---