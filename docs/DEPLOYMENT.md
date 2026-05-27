# Guia de Deployment - Bat-Store

## Checklist Pré-Deployment

### Ambiente Local
- [ ] Docker instalado (versão 20.10+)
- [ ] Docker Compose instalado (versão 1.29+)
- [ ] Git instalado
- [ ] Pelo menos 4GB RAM disponível

### Repositório
- [ ] Clone do repositório atualizado
- [ ] Arquivo `.env` criado a partir de `.env.example`
- [ ] `JWT_SECRET` alterado de "change-me"
- [ ] Senhas de administrador alteradas

---

## Processo de Deployment

### Fase 1: Preparação

```bash
# Clonar repositório
git clone https://github.com/Williansilva2207/Bat-Store.git
cd Bat-Store

# Criar arquivo .env
cp .env.example .env

# Editar .env com valores seguros
nano .env  # ou use seu editor favorito
```

### Fase 2: Build e Inicialização

```bash
# Fazer build de todas as imagens
docker compose build

# Subir todos os containers
docker compose up -d

# Verificar status
docker compose ps

# Ver logs
docker compose logs -f
```

**Tempo esperado:** 2-3 minutos para todos os containers ficarem healthy

### Fase 3: Validação

```bash
# Verificar saúde de cada serviço
curl http://localhost:8000/  # catalog
curl http://localhost:8001/  # order
curl http://localhost:8002/  # payment
curl http://localhost:8003/  # notification
curl http://localhost:8004/  # auth
```

**Resposta esperada:** `{"service": "...", "status": "Online"}`

---

## Testes Funcionais

### Teste 1: Fluxo Completo de Pedido

```bash
# 1. Fazer login
TOKEN=$(curl -s -X POST http://localhost:8004/login \
  -H "Content-Type: application/json" \
  -d '{"username":"batman","password":"change-me"}' \
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

# 2. Criar pedido
curl -X POST http://localhost:8001/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"item_id":"bat-01","quantity":1,"method":"credit_card"}'

# Resposta esperada: HTTP 200 com order_id e status PROCESSANDO

# 3. Consultar notificação (aguarde 1-2 segundos)
curl http://localhost:8003/notifications/1

# Resposta esperada: HTTP 200 com notificação salva

# 4. Consultar pagamento (requer admin)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8002/payments/1

# Resposta esperada: HTTP 200 com dados de pagamento
```

### Teste 2: Segurança JWT

```bash
# Teste 2a: Token inválido
curl -H "Authorization: Bearer invalid-token" \
  http://localhost:8002/payments/1
# Resposta esperada: HTTP 401 Unauthorized

# Teste 2b: User sem acesso admin
TOKEN_USER=$(curl -s -X POST http://localhost:8004/login \
  -H "Content-Type: application/json" \
  -d '{"username":"robin","password":"change-me"}' \
  | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

curl -H "Authorization: Bearer $TOKEN_USER" \
  http://localhost:8002/payments/1
# Resposta esperada: HTTP 403 Forbidden

# Teste 2c: Token expirado (aguarde 24h ou ajuste JWT_EXPIRATION_HOURS)
# Será testado naturalmente com o tempo
```

### Teste 3: Observabilidade

```bash
# Prometheus: Verificar scrape de métricas
curl http://localhost:9090/api/v1/targets | jq '.data.activeTargets[] | .labels.job'
# Resposta esperada: jobs para auth, catalog, order, payment, notification

# Grafana: Acessar dashboard
open http://localhost:3000
# Login: admin / admin
# Verificar painéis de requisições e latência

# Jaeger: Ver traces
open http://localhost:16686
# Search → bat-order-service → Ver traces
```

### Teste 4: Resiliência

```bash
# Teste 4a: Circuit Breaker - Derrubar Catalog
docker pause catalog

# Tentar criar pedido (deve usar cache/fallback)
curl -X POST http://localhost:8001/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"item_id":"bat-01","quantity":1}'
# Resposta esperada: HTTP 200 com status PROCESSANDO_DEGRADADO OU HTTP 503

# Trazer de volta
docker unpause catalog

# Próxima requisição funciona normalmente
curl -X POST http://localhost:8001/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"item_id":"bat-02","quantity":1}'
# Resposta esperada: HTTP 200 com status PROCESSANDO

# Teste 4b: Redis Indisponível
docker stop redis

# Criar pedido
curl -X POST http://localhost:8001/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"item_id":"bat-03","quantity":1}'
# Resposta esperada: HTTP 200 (pedido criado, mas notificação não é enviada)

# Trazer Redis de volta
docker start redis

# Verificar que notificação foi processada
docker compose logs notification | grep "Mensagem consumida"

# Teste 4c: Verificar Correlation ID
curl -v -X POST http://localhost:8001/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"item_id":"bat-04","quantity":1}' 2>&1 | grep correlation_id
# Deve aparecer no response JSON
```

---

## Verificação de Métricas

### Prometheus

```
http://localhost:9090/graph

# Queries úteis:
- http_requests_total{service="bat-order-service"}
- http_request_duration_seconds_bucket{le="0.1", service="bat-payment-service"}
- rate(http_requests_total[1m])  # RPS
```

### Grafana

```
http://localhost:3000

# Painéis pré-configurados:
- Requisições por segundo
- Latência p95
- Taxa de erros
```

### Jaeger

```
http://localhost:16686

# Buscar por:
- Service: bat-order-service
- Operation: POST /orders
# Verificar propagação de X-Correlation-ID em spans
```

---

## 🔍 Troubleshooting

### Container não inicia
```bash
# Ver logs detalhados
docker compose logs <service_name>

# Comum: porta já em uso
netstat -tlnp | grep 8000
sudo lsof -i :8000

# Solução: liberar porta ou ajustar docker-compose.yml
```

### Serviço retorna 503
```bash
# Verificar se serviço de dependência está up
docker compose ps

# Verificar logs de retry
docker compose logs order | grep "retry\|circuit"

# Aguardar reconexão (max 30s para circuit breaker)
```

### Métricas não aparecem em Prometheus
```bash
# Aguardar 15-30 segundos (scrape interval)
sleep 30

# Verificar se endpoint /metrics está respondendo
curl http://localhost:8000/metrics
curl http://localhost:8001/metrics
# Etc...

# Se não responder, verificar logs do serviço
docker compose logs catalog | grep "metrics\|error"
```

### Redis acumula mensagens
```bash
# Conectar ao Redis
docker compose exec redis redis-cli

# Ver tamanho da fila
LLEN fila_pedidos

# Limpar fila (cuidado!)
DEL fila_pedidos

# Verificar replicação
INFO replication
```

---

## 🧹 Limpeza e Reset

### Parar sem remover dados
```bash
docker compose down

# Reiniciar
docker compose up -d
```

### Remover tudo (incluindo dados)
```bash
docker compose down -v

# Remover bancos de dados locais
rm -f auth.db catalog.db orders.db payments.db notifications.db

# Novo deployment
docker compose build
docker compose up -d
```

### Resetar bancos de dados
```bash
# Apenas deletar e deixar recriar
docker compose exec auth rm -f auth.db
docker compose exec catalog rm -f catalog.db
# Etc...

# Reiniciar serviços
docker compose restart
```

---

## 📈 Monitoramento Contínuo

### Logs em Tempo Real
```bash
# Todos os serviços
docker compose logs -f

# Apenas order-service
docker compose logs -f order

# Com timestamp
docker compose logs -f --timestamps
```

### Verificação de Saúde Periódica
```bash
#!/bin/bash
while true; do
  echo "=== $(date) ==="
  docker compose ps
  sleep 60
done
```

### Alertas Recomendados (Configurar em Prometheus/Grafana)
- CPU > 80%
- Memory > 80%
- Taxa de erro > 5%
- Latência p95 > 1s
- Circuit breaker aberto
- Redis desconectado

---

## Otimizações Pós-Deployment

### Performance
- Aumentar replicas em docker-compose.yml se tráfego alto
- Aumentar cache size em ResilientHttpClient
- Ajustar timeouts conforme latência de rede

### Segurança
- Trocar JWT_SECRET para valor único forte
- Trocar senhas de admin
- Usar HTTPS em produção (adicionar proxy reverso)
- Implementar rate limiting

### Escalabilidade
- Adicionar load balancer (nginx, haproxy)
- Separar Prometheus em instância dedicada
- Backup automático de bancos SQLite
- Monitoramento centralizado (ELK stack)

---

## Checklist Final de Go-Live

- [ ] Todos os containers iniciando com sucesso
- [ ] Endpoints respondendo HTTP 200 OK
- [ ] Fluxo completo de pedido testado
- [ ] JWT funcionando corretamente
- [ ] Métricas sendo coletadas por Prometheus
- [ ] Grafana mostrando dados
- [ ] Jaeger capturando traces
- [ ] Redis funcionando e consumidor processando eventos
- [ ] Resiliência testada (falhas simuladas)
- [ ] Logs estruturados em JSON aparecendo
- [ ] Interface Flask acessível e funcional
- [ ] Documentação atualizada
- [ ] Backup de .env em local seguro
