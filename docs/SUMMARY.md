# Sumário Executivo - Bat-Store

## Visão Geral do Projeto

O **Bat-Store** é uma implementação completa de arquitetura de microsserviços distribuídos em Python/FastAPI, demonstrando:

- ✅ **5 serviços independentes** com responsabilidades bem definidas
- ✅ **Comunicação síncrona e assíncrona** (HTTP/REST + Redis Pub/Sub)
- ✅ **Resiliência** (retry, circuit breaker, fallback, auto-reconexão)
- ✅ **Observabilidade** (Prometheus, Grafana, Jaeger, logs estruturados)
- ✅ **Segurança** (JWT, autenticação, autorização por role)
- ✅ **Documentação técnica** completa
- ✅ **Interface web** funcional para testes e demonstração

---

## Escopo Implementado

### OBRIGATÓRIOS

#### Arquitetura e Infraestrutura
- ✅ 5 serviços em containers Docker independentes
- ✅ `docker compose up` funciona sem intervenção manual
- ✅ Backend 100% em Python (FastAPI)
- ✅ Nenhuma ferramenta de middleware pronta como substituto

#### Comunicação Síncrona
- ✅ Order → Catalog (GET /items/{id})
- ✅ Order → Payment (POST /payments)
- ✅ Payment → Catalog (GET /items/{id})
- ✅ Order → Auth (GET /validate)
- ✅ Todas URLs via `os.getenv()`
- ✅ Documentação de APIs completa

#### Comunicação Assíncrona
- ✅ Order publica em `fila_pedidos` após aprovar
- ✅ Notification consome em daemon thread
- ✅ Redis persistente com replicação
- ✅ Variáveis de ambiente para Redis

#### Resiliência
- ✅ Retry com backoff exponencial (3 tentativas)
- ✅ Circuit breaker (5 falhas → 30s pause)
- ✅ Fallback para cache em modo degradado
- ✅ Timeout configurável (3s padrão)
- ✅ Reconexão automática ao Redis (5s interval)

#### Observabilidade
- ✅ Logs estruturados em JSON
- ✅ Correlation ID (UUID) em todas as chamadas
- ✅ Métricas Prometheus em `/metrics`
- ✅ X-Correlation-ID propagado em headers
- ✅ Correlation ID em payload da fila
- ✅ Notification loga correlation_id

#### Segurança
- ✅ POST /login gera JWT HS256
- ✅ GET /validate valida token
- ✅ GET /validate/admin retorna 403 se não admin
- ✅ GET /validate/user para usuários
- ✅ POST /orders protegido com JWT
- ✅ GET /payments/{id} protegido (admin)
- ✅ JWT_SECRET via `os.getenv()`
- ✅ Bcrypt para hash de senhas

#### Tolerância a Falhas
- ✅ docs/fault-tolerance.md documentado
- ✅ Estratégia de eventual consistency explicada
- ✅ Comportamento por serviço documentado
- ✅ Middleware descrição completa
- ✅ Implementação verificada

#### Repositório e Documentação
- ✅ README.md completo
- ✅ .env.example com todas variáveis
- ✅ Passo a passo: cp .env.example .env && docker compose up
- ✅ Lista de serviços com portas
- ✅ Instrução de teste de resiliência
- ✅ Como acessar Grafana e Jaeger
- ✅ Demonstração de token JWT

---

### BÔNUS

#### Bônus 1: Mais de 3 Serviços ✅
- Implementado: **5 serviços** (auth, catalog, order, payment, notification)
- Documentação de responsabilidades no README

#### Bônus 2: Configuração Externalizada ✅
- .env.example com 40+ variáveis
- docker-compose.yml lê de .env
- Zero hardcoded em código

#### Bônus 3: Mais de 1 Mecanismo de Resiliência ✅
- Retry com backoff exponencial
- Circuit breaker com threshold
- Fallback para cache local
- Reconexão automática ao Redis
- Timeout configurável

#### Bônus 4: Prometheus + Grafana ✅
- Container Prometheus configurado
- prometheus.yml scrapeando todos os serviços
- Container Grafana no 3000
- Dashboard com métricas de RPS, latência, erros
- Credentials: admin/admin

#### Bônus 5: Tracing Distribuído Jaeger ✅
- Container Jaeger no 16686
- OpenTelemetry collector ativo
- Correlation ID mapeado como atributo
- Traces visíveis para fluxo completo

---

## Componentes Implementados

### Serviços Backend

| Serviço | Porta | Principais Features |
|---------|-------|-------------------|
| **bat-auth-service** | 8004 | JWT, autenticação, 3 usuários teste |
| **bat-catalog-service** | 8000 | 5 produtos, controle estoque, logs |
| **bat-order-service** | 8001 | Orquestração, JWT, correlation ID, fila |
| **bat-payment-service** | 8002 | Processamento, proteção admin |
| **bat-notification-service** | 8003 | Consumidor async, persistência |

### Middleware Distribuído

| Componente | Arquivo | Funcionalidade |
|-----------|---------|-----------------|
| **BatBrokerMiddleware** | middleware/broker.py | Pub/sub Redis com auto-reconexão |
| **ResilientHttpClient** | middleware/resilient_http.py | Retry, circuit breaker, cache, fallback |
| **Structured Logging** | middleware/structured_logging.py | JSON logs com metadados |

### Infraestrutura

| Componente | Porta | Versão |
|-----------|-------|--------|
| **Redis** | 6379 | 7-alpine |
| **Redis Replica** | 6380 | 7-alpine |
| **Prometheus** | 9090 | latest |
| **Grafana** | 3000 | latest |
| **Jaeger** | 16686 | all-in-one |

### Interface

| Componente | Porta | Framework |
|-----------|-------|-----------|
| **Web Interface** | 5000 | Flask |
| **Templates** | - | Jinja2 |

---

## Métricas e Observabilidade

### Prometheus Metrics
- `http_requests_total` - Total requisições
- `http_request_duration_seconds` - Latência (p50, p95, p99)
- `http_requests_created` - Timestamp
- Custom: circuit breaker status, cache hits, retry count

### Dashboards Grafana
- Requisições por segundo por serviço
- Latência média/p95/p99
- Taxa de erros (4xx, 5xx)
- Status de health checks

### Logs Estruturados
- Timestamp ISO 8601
- Nivel (INFO, ERROR, WARN)
- Service name
- Correlation ID
- Mensagem + metadados JSON

### Traces Jaeger
- Propagação de correlation_id
- Spans para cada chamada HTTP
- Visualização de latência
- Identificação de gargalos

---

## Segurança Implementada

### Autenticação
- ✅ JWT HS256
- ✅ Tokens com expiração (24h)
- ✅ Bcrypt para senhas (never plaintext)

### Autorização
- ✅ Role-based access control (admin, user, support)
- ✅ Endpoints protegidos com JWT
- ✅ 403 para permissões insuficientes

### Proteção de Dados
- ✅ Senhas hasheadas com bcrypt
- ✅ Variáveis sensíveis via .env
- ✅ SQLite com isolamento por serviço

---

## Testes Validados

### Fluxo End-to-End
✅ Login → Criar Pedido → Notificação → Consulta → Pagamento

### Segurança
✅ Token inválido → 401  
✅ User sem admin → 403  
✅ Sem token → 401

### Resiliência
✅ Catalog down → fallback + 503  
✅ Redis down → reconexão automática  
✅ Retry com backoff funciona

### Observabilidade
✅ Correlation ID propagado  
✅ Métricas coletadas  
✅ Traces visíveis em Jaeger  
✅ Logs em JSON

---

## Documentação Fornecida

| Documento | Localização | Conteúdo |
|-----------|-------------|----------|
| **README.md** | `/` | Setup, uso, exemplos cURL |
| **DEPLOYMENT.md** | `/docs/` | Checklist deployment, troubleshooting |
| **APIs.md** | `/docs/` | Especificação detalhada de endpoints |
| **ARCHITECTURE.md** | `/docs/` | Diagrama, fluxos, componentes |
| **fault-tolerance.md** | `/docs/` | Estratégia resiliência, análise falhas |
| **prometheus.yml** | `/` | Config Prometheus |
| **.env.example** | `/` | Template variáveis (40+) |

---

##  Como Usar

### Iniciar Sistema
```bash
git clone ...
cd Bat-Store
cp .env.example .env
docker compose build
docker compose up -d
```

### Testar Fluxo Completo
```bash
# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8004/login \
  -d '{"username":"batman","password":"change-me"}' | jq -r .access_token)

# 2. Criar pedido
curl -X POST http://localhost:8001/orders \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"item_id":"bat-01","quantity":1}'

# 3. Consultar notificação
curl http://localhost:8003/notifications/1

# 4. Acessar dashboards
# Grafana: http://localhost:3000 (admin/admin)
# Jaeger: http://localhost:16686
```

---

## Estatísticas do Projeto

| Métrica | Valor |
|---------|-------|
| Serviços | 5 |
| Endpoints | 15+ |
| Bancos de dados | 5 (SQLite) |
| Componentes infraestrutura | 4 (Redis, Prometheus, Grafana, Jaeger) |
| Mecanismos resiliência | 4 |
| Linhas de código | ~3000 |
| Documentação | 5 docs + README |
| Templates HTML | 5 páginas |
| Variáveis configuráveis | 40+ |

---

## Diferenciais Técnicos

1. **Middleware Personalizado**
   - BatBrokerMiddleware com auto-reconexão
   - ResilientHttpClient com circuit breaker + cache

2. **Propagação de Contexto**
   - Correlation ID gerado e propagado end-to-end
   - Visível em logs, headers e traces

3. **Observabilidade Completa**
   - Logs estruturados JSON
   - Métricas Prometheus
   - Traces distribuídos Jaeger
   - Dashboard Grafana

4. **Segurança Defense-in-Depth**
   - JWT com assinatura
   - Bcrypt para senhas
   - Role-based authorization
   - Proteção de endpoints

5. **Documentação Executável**
   - API docs com exemplos cURL
   - Architecture diagrams ASCII
   - Deployment checklist
   - Troubleshooting guide

---

## Aprendizados Aplicados

✅ Padrão Microsserviços  
✅ Comunicação Síncrona e Assíncrona  
✅ Padrão Circuit Breaker  
✅ Padrão Bulkhead (isolamento por serviço)  
✅ Eventual Consistency  
✅ Distributed Tracing  
✅ Observabilidade (Logs, Métricas, Traces)  
✅ Autenticação JWT  
✅ Docker & Docker Compose  
✅ RESTful API Design  

---