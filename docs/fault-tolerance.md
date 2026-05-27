# Tolerância a Falhas - Bat-Store

## Estratégia de Consistência

O Bat-Store adota **Eventual Consistency** (Consistência Eventual) como estratégia de consistência de dados distribuídos.

### Justificativa

1. **Escalabilidade**: Permite que cada serviço operada independentemente sem sincronização síncrona
2. **Disponibilidade**: Sistema continua funcional mesmo se alguns serviços estiverem temporariamente indisponíveis
3. **Particionamento**: Graceful degradation em caso de falhas de rede
4. **Performance**: Evita latências longas de sincronização síncrona

### Implementação

- Comunicação síncrona (HTTP/REST) para operações críticas que precisam de resposta imediata (ex: validação de estoque)
- Comunicação assíncrona (Filas Redis) para operações não-críticas (ex: notificações)
- Cache local em memória para fallback em modo degradado

---

## Análise de Falhas por Serviço

### 1. bat-auth-service (Autenticação)

**Se o serviço cair:**
- Login ❌ - Não será possível autenticar novos usuários
- Validação de tokens ❌ - Chamadas downstream falharão na validação
- **Impacto**: Bloqueador crítico para toda operação

**Como o middleware lida:**
- ResilientHttpClient mantém circuit breaker para chamadas falhadas
- Após 5 falhas consecutivas, para de tentar por 30 segundos
- Retorna HTTP 503 com mensagem clara

**Recuperação:**
- Quando o serviço volta, circuit breaker reseta
- Próxima requisição tenta novamente
- Sistema volta ao funcionamento normal

---

### 2. bat-catalog-service (Catálogo)

**Se o serviço cair:**
- GET /items/{id} ❌ - Consultas falhm
- bat-order-service não consegue validar estoque ❌
- bat-payment-service não consegue calcular preço ❌

**Como o middleware lida:**
- ResilientHttpClient implementa **retry com backoff exponencial** (até 3 tentativas)
- Backoff: 0.5s, 1s, 2s (com jitter aleatório)
- **Fallback para cache**: Se todas as tentativas falharem, usa cache local se disponível
- Se não há cache, retorna HTTP 503

**Implementação no código:**
```python
try:
    catalog_result = catalog_client.get_json(url, cache_key=item_id)
    # Sucesso: retorna dados remotos
except ResilientFallback:
    # Fallback: usa dados em cache se disponível
    # Caso contrário, retorna 503 Serviço Indisponível
```

**Recuperação:**
1. Tentativas automáticas com backoff exponencial
2. Circuit breaker fecha após 30 segundos
3. Cache mantém dados recentes para modo degradado
4. Quando serviço volta, consultas bem-sucedidas limpam circuit breaker

---

### 3. bat-order-service (Pedidos)

**Se o serviço cair:**
- POST /orders ❌ - Novos pedidos não podem ser criados
- Eventos não são publicados na fila ❌

**Como o middleware lida:**
- JWT validation falha sem token → HTTP 401
- Chama catalog-service com retry + fallback
- Chama payment-service (atualmente sem validação, tolerante a falhas)
- Publica evento na fila com correlation_id para rastreamento

**Recuperação:**
- Quando volta, aceita novos pedidos normalmente
- Eventos passados já foram processados pelos consumidores

---

### 4. bat-payment-service (Pagamentos)

**Se o serviço cair:**
- POST /payments ❌ - Pagamentos não são processados
- GET /payments/{id} ❌ - Consultas falham (requer admin)

**Como o middleware lida:**
- Chama catalog-service com retry + fallback
- Se catalog-service estiver fora, usa cache para calcular preço
- Retorna 503 se não conseguir processar

**Recuperação:**
- Quando volta, novos pagamentos são aceitos
- Pedidos aguardando pagamento serão reprocessados

---

### 5. bat-notification-service (Notificações)

**Se o serviço cair:**
- GET /notifications/{order_id} ❌ - Consultas falham
- **Consumidor de fila para** - Mensagens acumulam no Redis

**Como o middleware lida:**
- Evento publicado na fila fica armazenado no Redis (persistente)
- Consumidor se reconecta automaticamente ao Redis
- Reconexão com retry a cada 5 segundos (REDIS_RECONNECT_INTERVAL)

**Implementação:**
```python
def conectar_redis():
    while True:
        try:
            cliente = redis.Redis(...)
            cliente.ping()
            return cliente
        except redis.RedisError:
            time.sleep(REDIS_RECONNECT_INTERVAL)

def consumir_fila():
    cliente_redis = conectar_redis()  # Reconecta automaticamente
    while True:
        try:
            mensagem = cliente_redis.blpop(QUEUE_NAME, REDIS_BLOCK_TIMEOUT)
            # Processa...
        except redis.RedisError:
            cliente_redis = conectar_redis()  # Tenta reconectar
```

**Recuperação:**
1. Fila persiste no Redis até ser consumida
2. Serviço volta → se reconecta ao Redis
3. Processa todas as mensagens pendentes
4. Sistema fica consistente

---

### 6. Redis (Fila de Mensagens)

**Se cair:**
- Eventos novos não podem ser publicados ❌
- Notificações não são processadas ❌

**Como o middleware lida:**
- BatBrokerMiddleware detecta falha em publish_event
- Log de aviso, mas continua aceitando pedidos
- Redis replica oferece redundância (redis-replica)

**Implementação:**
```python
def publish_event(self, queue_name, payload):
    if not self.client:
        self._connect()
        if not self.client:
            log_json("warning", "publish_event_deferred", ...)
            return False
    
    try:
        self.client.lpush(queue_name, json.dumps(payload))
    except redis.RedisError:
        self._schedule_reconnect()  # Tenta reconectar
        return False
```

**Recuperação:**
1. Thread daemon tenta reconectar a cada 5 segundos
2. Quando reconecta, publica eventos pendentes (se mantidos em buffer)
3. Redis-replica está pronto para failover

---

## Fluxo Completo de Tolerância a Falhas

### Cenário 1: Catalog Service Cai durante POST /orders

```
1. Cliente chama POST /orders com token JWT
2. Order Service valida token (Auth disponível)
3. Order Service tenta chamar Catalog (FALHA!)
4. ResilientHttpClient inicia retry:
   - Tentativa 1: FALHA → sleep 0.5s
   - Tentativa 2: FALHA → sleep 1s
   - Tentativa 3: FALHA → sleep 2s
5. Circuit Breaker se abre (5 falhas acumuladas)
6. Fallback para cache:
   - Se cache existe: retorna dados em cache, status PROCESSANDO_DEGRADADO
   - Se não: HTTPException 503
7. Pedido é criado com status PROCESSANDO ou PROCESSANDO_DEGRADADO
8. Evento é publicado na fila com correlation_id
9. Notification Service consome (se rodando)
```

### Cenário 2: Notification Service Cai

```
1. Ordem Service publica evento na fila Redis
2. Notification Service está inativo
3. Evento fica armazenado no Redis (persistente)
4. Notification Service volta:
   - Tenta reconectar ao Redis
   - Sucesso → começa a consumir fila
   - Processa todos os eventos pendentes
   - Sistema fica consistente
5. Queries GET /notifications/{id} começam a funcionar
```

### Cenário 3: Redis Cai

```
1. Order Service tenta publicar evento
2. Redis está fora
3. publish_event detecta erro
4. Log de aviso
5. Pedido ainda é criado (degradado)
6. Notification não pode ser enviada até Redis voltar
7. Redis volta:
   - BatBrokerMiddleware tenta reconectar
   - Sucesso → operações normalizadas
8. Novos pedidos começam a publicar eventos novamente
```

---

## Métricas de Observabilidade

### Prometheus Metrics

- `http_requests_total` - Total de requisições por serviço
- `http_request_duration_seconds` - Latência por endpoint
- `http_requests_created` - Timestamp de criação
- Circuit breaker status (custom)
- Cache hit rate (custom)
- Retry count (custom)

### Traces Distribuídos (Jaeger)

- X-Correlation-ID propagado em todas as chamadas
- Spans criados para:
  - Entrada em POST /orders
  - Chamada para catalog-service
  - Chamada para payment-service
  - Publicação na fila
- Permite rastrear um pedido desde criação até notificação

### Logs Estruturados

```json
{
  "timestamp": "2024-05-27T10:30:45.123Z",
  "level": "INFO",
  "service": "bat-order-service",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Order created successfully",
  "order_id": 42,
  "degraded": false
}
```

---

## Checklist de Verificação

- ✅ Retry com backoff exponencial implementado
- ✅ Circuit breaker com limite de falhas
- ✅ Fallback para cache em modo degradado
- ✅ Reconexão automática ao Redis
- ✅ Correlation ID propagado
- ✅ Logs estruturados com JSON
- ✅ Métricas Prometheus expostas
- ✅ Traces distribuídos com Jaeger
- ✅ Fila persistente no Redis
- ✅ Consumidor daemon com auto-reconexão

---

## Recomendações de Operação

1. **Monitoramento**: Use Grafana para acompanhar taxa de erros e latência
2. **Alertas**: Configure alertas para circuit breaker aberto
3. **Logs**: Acompanhe X-Correlation-ID para rastrear pedidos
4. **Backup**: Mantenha backup regular do banco de dados
5. **Testes de Caos**: Execute docker stop em serviços para validar resiliência
6. **Escalabilidade**: Réplicas (replicas: 2) em docker-compose distribuem carga
