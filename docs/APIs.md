# Documentação de APIs - Bat-Store

## Overview

Todas as APIs seguem padrão REST/HTTP com respostas em JSON. Autenticação via JWT Bearer Token para endpoints protegidos.

---

## Autenticação (bat-auth-service)

**Base URL:** `http://localhost:8004`

### 1. Health Check
```
GET /
Sem autenticação

Response: 200 OK
{
  "service": "Bat-Auth-Service",
  "status": "Online"
}
```

### 2. Login
```
POST /login
Sem autenticação
Content-Type: application/json

Body:
{
  "username": "batman",
  "password": "change-me"
}

Response: 200 OK
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "role": "admin"
}

Response: 401 Unauthorized
{
  "detail": "Usuário não encontrado." | "Senha incorreta."
}
```

### 3. Validar Token (Genérico)
```
GET /validate
Autenticação: Bearer Token obrigatória

Response: 200 OK
{
  "username": "batman",
  "role": "admin",
  "valid": true
}

Response: 401 Unauthorized
{
  "detail": "Token expirado." | "Token inválido."
}
```

### 4. Validar Token (Admin)
```
GET /validate/admin
Autenticação: Bearer Token obrigatória
Requer role: admin

Response: 200 OK
{
  "username": "batman",
  "role": "admin",
  "valid": true
}

Response: 401 Unauthorized
{
  "detail": "Token inválido."
}

Response: 403 Forbidden
{
  "detail": "Acesso negado. Apenas administradores."
}
```

### 5. Validar Token (User)
```
GET /validate/user
Autenticação: Bearer Token obrigatória

Response: 200 OK
{
  "username": "robin",
  "role": "user",
  "valid": true
}

Response: 401 Unauthorized
{
  "detail": "Token inválido."
}
```

### 6. Métricas Prometheus
```
GET /metrics
Sem autenticação

Response: 200 OK
# TYPE http_requests_total counter
http_requests_total{method="post",path="/login",...} 42
...
```

---

## Catálogo (bat-catalog-service)

**Base URL:** `http://localhost:8000`

### 1. Health Check
```
GET /
Sem autenticação

Response: 200 OK
{
  "service": "Bat-Catalog-Service",
  "status": "Online"
}
```

### 2. Consultar Item por ID
```
GET /items/{id}
Sem autenticação
Headers: X-Correlation-ID (opcional, gerado se não enviado)

Exemplo:
GET /items/bat-01

Response: 200 OK
{
  "id": "bat-01",
  "name": "Action Figure Batman",
  "description": "Miniatura articulada escala 1:6",
  "price": 299.90,
  "stock": 10
}

Response: 404 Not Found
{
  "detail": "Item não encontrado no catálogo da Bat-Store"
}
```

### 3. Métricas Prometheus
```
GET /metrics
Sem autenticação

Response: 200 OK
# Métricas de requisições, latência, etc.
```

**Produtos Pré-cadastrados:**
| ID | Nome | Preço | Estoque |
|---|---|---|---|
| bat-01 | Action Figure Batman | R$ 299.90 | 10 |
| bat-02 | Camiseta Bat-Sinal | R$ 79.90 | 25 |
| bat-03 | Caneca Coringa | R$ 45.00 | 3 |
| bat-04 | HQ O Cavaleiro das Trevas | R$ 120.00 | 15 |
| bat-05 | Batmóvel: The Tumbler | R$ 17.000.000,00 | 1 |

---

## Pedidos (bat-order-service)

**Base URL:** `http://localhost:8001`

### 1. Health Check
```
GET /
Sem autenticação

Response: 200 OK
{
  "service": "Bat-Order-Service",
  "status": "Online"
}
```

### 2. Criar Pedido
```
POST /orders
Autenticação: Bearer Token obrigatória
Content-Type: application/json
Headers: X-Correlation-ID (opcional, gerado se não enviado)

Body:
{
  "item_id": "bat-01",
  "quantity": 1,
  "method": "credit_card"
}

Response: 200 OK
{
  "message": "Pedido realizado com sucesso!",
  "order_id": 1,
  "status": "PROCESSANDO",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "degraded": false
}

Response: 200 OK (modo degradado)
{
  "message": "Pedido realizado com sucesso em modo degradado (cache do catálogo).",
  "order_id": 1,
  "status": "PROCESSANDO_DEGRADADO",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "degraded": true
}

Response: 400 Bad Request
{
  "detail": "O item solicitado não existe." | "Estoque insuficiente."
}

Response: 401 Unauthorized
{
  "detail": "Token ausente, expirado ou inválido."
}

Response: 503 Service Unavailable
{
  "detail": "Serviço de Catálogo indisponível. Operação em modo degradado."
}
```

**Métodos de Pagamento Aceitos:**
- credit_card
- debit_card
- bat_coins

### 3. Métricas Prometheus
```
GET /metrics
Sem autenticação

Response: 200 OK
# Métricas de requisições, latência, circuit breaker, etc.
```

---

## Pagamentos (bat-payment-service)

**Base URL:** `http://localhost:8002`

### 1. Health Check
```
GET /
Sem autenticação

Response: 200 OK
{
  "service": "Bat-Payment-Service",
  "status": "Online"
}
```

### 2. Processar Pagamento
```
POST /payments
Sem autenticação (interno)
Content-Type: application/json
Headers: X-Correlation-ID (opcional)

Body:
{
  "order_id": 1,
  "item_id": "bat-01",
  "quantity": 1,
  "method": "credit_card"
}

Response: 200 OK
{
  "message": "Pagamento processado com sucesso!",
  "payment_id": 1,
  "order_id": 1,
  "item": "Action Figure Batman",
  "quantity": 1,
  "total": 299.90,
  "method": "credit_card",
  "status": "APROVADO",
  "degraded": false
}

Response: 400 Bad Request
{
  "detail": "Método de pagamento inválido. Aceitos: [credit_card, debit_card, bat_coins]" |
            "Item não encontrado no catálogo."
}

Response: 409 Conflict
{
  "detail": "Pagamento para esse pedido já foi processado."
}

Response: 503 Service Unavailable
{
  "detail": "Serviço de Catálogo indisponível. Operação em modo degradado."
}
```

### 3. Consultar Pagamento por Order ID
```
GET /payments/{order_id}
Autenticação: Bearer Token obrigatória
Requer role: admin

Exemplo:
GET /payments/1

Response: 200 OK
{
  "payment_id": 1,
  "order_id": 1,
  "item_id": "bat-01",
  "quantity": 1,
  "total": 299.90,
  "method": "credit_card",
  "status": "APROVADO"
}

Response: 401 Unauthorized
{
  "detail": "Token ausente ou inválido."
}

Response: 403 Forbidden
{
  "detail": "Apenas administradores podem consultar pagamentos."
}

Response: 404 Not Found
{
  "detail": "Pagamento não encontrado para esse pedido."
}
```

### 4. Métricas Prometheus
```
GET /metrics
Sem autenticação

Response: 200 OK
# Métricas de requisições, latência, circuit breaker, etc.
```

---

## Notificações (bat-notification-service)

**Base URL:** `http://localhost:8003`

### 1. Health Check
```
GET /
Sem autenticação

Response: 200 OK
{
  "service": "Bat-Notification-Service",
  "status": "Online"
}
```

### 2. Consultar Notificações por Order ID
```
GET /notifications/{order_id}
Sem autenticação

Exemplo:
GET /notifications/1

Response: 200 OK
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

Response: 404 Not Found
{
  "detail": "Nenhuma notificação encontrada para esse pedido."
}
```

### 3. Métricas Prometheus
```
GET /metrics
Sem autenticação

Response: 200 OK
# Métricas de requisições, latência, etc.
```

---

## Interface Web (Flask)

**Base URL:** `http://localhost:5000`

### Páginas Disponíveis
- `GET /` - Página inicial com status dos serviços
- `GET /auth` - Página de login
- `GET /catalog` - Lista de produtos
- `GET /orders` - Criar pedidos e consultar notificações/pagamentos
- `GET /observability` - Links para Grafana e Jaeger

### API Endpoints da Interface
```
POST /api/login - Login (form)
GET /api/get-notification/{order_id} - Consultar notificação
GET /api/get-payment/{order_id} - Consultar pagamento (admin)
POST /api/create-order - Criar pedido (form)
POST /logout - Logout
```

---

## Observabilidade

### Prometheus
```
GET http://localhost:9090/
```

**Métricas Disponíveis:**
- `http_requests_total` - Total de requisições por serviço
- `http_request_duration_seconds` - Latência por endpoint
- `http_requests_created` - Timestamp de criação
- `http_request_duration_seconds_bucket` - Buckets de latência

### Grafana
```
GET http://localhost:3000/
Credentials: admin / admin
```

**Dashboards:**
- Requisições por segundo
- Latência p95
- Taxa de erros
- Status de serviços

### Jaeger
```
GET http://localhost:16686/
```

**Recursos:**
- Traces distribuídos
- Busca por service, operation, correlation_id
- Propagação de headers X-Correlation-ID

---

## Headers e Convenções

### Headers Recomendados

| Header | Descrição | Obrigatório |
|--------|-----------|-----------|
| Authorization | Bearer token JWT | Sim (endpoints protegidos) |
| X-Correlation-ID | ID único para rastreamento | Não (gerado se não enviado) |
| Content-Type | application/json | Sim (POST/PUT) |

### Status Codes

| Código | Significado |
|--------|------------|
| 200 | OK - Sucesso |
| 400 | Bad Request - Erro na requisição |
| 401 | Unauthorized - Token ausente/inválido |
| 403 | Forbidden - Sem permissão |
| 404 | Not Found - Recurso não encontrado |
| 409 | Conflict - Conflito (ex: pagamento duplicado) |
| 503 | Service Unavailable - Serviço indisponível |

### Códigos de Resposta HTTP

```
1xx - Informational
2xx - Success
3xx - Redirection
4xx - Client Error
5xx - Server Error
```

---

## Fluxo de Integração Completo

```
1. POST /login (auth-service)
   ↓ Retorna JWT token
   
2. POST /orders (order-service + token)
   ├─ GET /items/{id} (catalog-service) [com retry + fallback]
   ├─ POST /payments (payment-service)
   │  └─ GET /items/{id} (catalog-service)
   └─ Publish event to Redis
   
3. Notification Service (async)
   └─ Consome evento de fila
   └─ Salva em banco
   
4. GET /notifications/{id} (notification-service)
   ↓ Retorna dados salvos
   
5. GET /payments/{id} (payment-service + admin token)
   ↓ Retorna dados de pagamento
```

---

## Exemplos cURL Completos

### Fluxo Completo

```bash
#!/bin/bash

# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8004/login \
  -H "Content-Type: application/json" \
  -d '{"username":"batman","password":"change-me"}' \
  | jq -r '.access_token')

echo "Token: $TOKEN"

# 2. Criar pedido
ORDER=$(curl -s -X POST http://localhost:8001/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"item_id":"bat-01","quantity":1,"method":"credit_card"}')

ORDER_ID=$(echo $ORDER | jq '.order_id')
CORRELATION_ID=$(echo $ORDER | jq -r '.correlation_id')

echo "Order ID: $ORDER_ID"
echo "Correlation ID: $CORRELATION_ID"

# 3. Aguardar processamento
sleep 2

# 4. Consultar notificação
curl -s -X GET http://localhost:8003/notifications/$ORDER_ID | jq

# 5. Consultar pagamento (admin)
curl -s -X GET http://localhost:8002/payments/$ORDER_ID \
  -H "Authorization: Bearer $TOKEN" | jq
```

---
