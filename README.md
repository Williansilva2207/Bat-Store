# Bat-Store Middleware Distribuído

Uma arquitetura de microsserviços tolerante a falhas usando Python, FastAPI, Redis e SQLite.

## Pré-requisitos
Docker e docker-compose instalados.

## Como rodar

```bash
# 1. Prepare as variáveis de ambiente
cp .env.example .env

# 2. Suba todos os containers (o docker vai buildar as imagens primeiro)
docker compose up --build -d
```

## Serviços e portas

| Serviço | Porta | URL | Descrição |
|---|---|---|---|
| Interface | 5000 | http://localhost:5000 | Frontend simples (1 única página) |
| Auth | 8001 | http://localhost:8001 | JWT, login e validação |
| Catalog | 8002 | http://localhost:8002 | Gestão de itens e estoque |
| Order | 8003 | http://localhost:8003 | Criação de pedidos |
| Payment | 8004 | http://localhost:8004 | Processamento financeiro |
| Notification | 8005 | http://localhost:8005 | Consumidor da fila do Redis |
| Grafana | 3000 | http://localhost:3000 | Dashboards de monitoramento |
| Jaeger | 16686 | http://localhost:16686 | Tracing distribuído (OpenTelemetry) |

---

## Passo a Passo Explícito de Testes

Para testar o fluxo de ponta a ponta e a resiliência do sistema, siga estes passos em ordem:

### 1. Teste o Fluxo Completo pela Interface Web
1. Abra o navegador em `http://localhost:5000`
2. **Seção 2 (Login)**: Faça login com o usuário `batman` e a senha `batman123`. Você verá um token JWT gerado na caixa de texto.
3. **Seção 3 (Catálogo)**: Coloque `bat-01` e clique em "Buscar Item". Deve retornar as informações e o estoque do Batman.
4. **Seção 4 (Criar Pedido)**: Insira `bat-01`, a quantidade `1`, escolha um método de pagamento e clique em "Criar Pedido". Deve aparecer "Pedido realizado com sucesso!".
5. **Seção 5 (Consultas)**:
   - Digite o ID do pedido (ex: `1`) em "Buscar Notificação".
   - Digite o ID do pedido (ex: `1`) em "Buscar Pagamento".

### 2. Testar Resiliência e Modo Degradado (Circuit Breaker / Cache)

O sistema foi feito para tolerar quedas no catálogo, utilizando cache e exibindo um status de "PROCESSANDO_DEGRADADO".

```bash
# 1. Pare propositalmente o serviço de Catálogo
docker stop bat-catalog-service

# 2. Vá na interface (localhost:5000) e tente criar outro pedido do "bat-01"
# O sistema deve demorar um pouco (retries) e em seguida criar o pedido usando o CACHE!
# A resposta vai exibir a mensagem "Pedido realizado com sucesso em modo degradado (cache do catálogo)." e o status PROCESSANDO_DEGRADADO.

# 3. Volte a ligar o serviço do Catálogo
docker start bat-catalog-service

# 4. Crie mais um pedido, tudo deve voltar a funcionar rápido e normalmente (STATUS: PROCESSANDO).
```

### Testando Observabilidade e Tolerância a Falhas

Além da interface, você pode monitorar o tráfego e os logs dos serviços:

1. **Acompanhamento de Logs em Tempo Real:**
   Abra um novo terminal e execute:
   ```bash
   docker compose logs -f
   ```
   *Isso vai mostrar tudo o que está acontecendo nos serviços em tempo real, sendo excelente para testes.*

2. **Testando o Prometheus:**
   Acesse [http://localhost:9090](http://localhost:9090) (ou pelo link gerado no Codespace) e vá na aba **Explore** (ou na tela principal de Query).
   - Digite `http_requests_total` no campo de busca e clique em **Execute**.
   - Você verá os dados absolutos das requisições interceptadas por cada serviço.

3. **Painéis do Grafana:**
   Acesse [http://localhost:3000](http://localhost:3000) (usuário: `admin`, senha: `admin`), vá em **Dashboards** e abra o **Bat-Store Dashboard**. Gere tráfego na Interface e veja os dados aparecerem nos painéis de Total de Requisições, Latência P95 e Erros.

4. **Testando o Circuit Breaker:**
   - **Jaeger**: Acesse `http://localhost:16686`. Selecione "bat-order-service" em Service e clique em "Find Traces". Clique em um Trace para ver a jornada completa da requisição, desde o Order passando pelo Auth, Catalog e Payment.

---

## Contratos das APIs

### 1. bat-auth-service (Autenticação)

**POST /login**
- **Payload In**: `{"username": "batman", "password": "batman123"}`
- **Payload Out**: `{"access_token": "eyJ...", "token_type": "bearer", "role": "admin"}`
- **Respostas**: `200 OK`, `401 Unauthorized`.

**GET /validate**
- **Header**: `Authorization: Bearer <token>`
- **Payload Out**: `{"username": "batman", "role": "admin", "valid": true}`
- **Respostas**: `200 OK`, `401 Unauthorized`, `403 Forbidden`.

### 2. bat-catalog-service (Catálogo)

**GET /items/{id}**
- **URL Param**: `id` do item (ex: `bat-01`).
- **Header Opcional**: `X-Correlation-ID`.
- **Payload Out**: `{"id": "bat-01", "name": "Action Figure Batman", "price": 299.9, "stock": 10}`
- **Respostas**: `200 OK`, `404 Not Found`.

### 3. bat-order-service (Pedidos)

**POST /orders**
- **Header**: `Authorization: Bearer <token>`
- **Header Opcional**: `X-Correlation-ID`
- **Payload In**: `{"item_id": "bat-01", "quantity": 1, "method": "credit_card"}`
- **Payload Out**: `{"message": "Pedido realizado...", "order_id": 1, "status": "PROCESSANDO", "degraded": false, "correlation_id": "uuid"}`
- **Respostas**: `200 OK`, `400 Bad Request`, `401 Unauthorized`, `503 Service Unavailable`.

### 4. bat-payment-service (Pagamentos)

**POST /payments**
- **Header Opcional**: `X-Correlation-ID`
- **Payload In**: `{"order_id": 1, "item_id": "bat-01", "quantity": 1, "method": "credit_card"}`
- **Payload Out**: `{"message": "Pagamento...", "payment_id": 1, "order_id": 1, "status": "APROVADO", "degraded": false}`
- **Respostas**: `200 OK`, `400 Bad Request`, `409 Conflict`, `503 Service Unavailable`.

**GET /payments/{order_id}**
- **Header**: `Authorization: Bearer <token>` (Requer ROLE Admin)
- **Payload Out**: `{"payment_id": 1, "order_id": 1, "item_id": "bat-01", "quantity": 1, "total": 299.9, "method": "credit_card", "status": "APROVADO"}`
- **Respostas**: `200 OK`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`.

### 5. bat-notification-service (Notificações)

**GET /notifications/{order_id}**
- **URL Param**: `order_id` do pedido (ex: `1`).
- **Payload Out**: `[{"notification_id": 1, "order_id": 1, "item_id": "bat-01", "quantity": 1, "status": "APPROVED", "sent_at": "2024-05-27T10:30:45Z"}]`
- **Respostas**: `200 OK`, `404 Not Found`.