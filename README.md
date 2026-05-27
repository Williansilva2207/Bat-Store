# Bat-Store 🦇
Trabalho Prático - Arquitetura de Sistemas

Este repositório contém a solução baseada em microsserviços para a **Bat-Store**. A arquitetura conta com 5 serviços independentes comunicando-se de forma síncrona (HTTP/FastAPI) e assíncrona (Mensageria com Redis).

---

# Variáveis de Ambiente

Antes de subir os containers, crie um arquivo `.env` na raiz do projeto a partir do modelo disponibilizado em `.env.example`:
```bash
cp .env.example .env

```

### Variáveis Disponíveis:

| Variável | Descrição |
| --- | --- |
| `APP_HOST` | Host usado pelo Uvicorn dentro dos containers. |
| `APP_PORT` | Porta interna usada pelos serviços da API. |
| `CATALOG_HOST_PORT` | Porta exposta no host para o serviço de catálogo. |
| `ORDER_HOST_PORT` | Porta exposta no host para o serviço de pedidos. |
| `PAYMENT_HOST_PORT` | Porta exposta no host para o serviço de pagamentos. |
| `NOTIFICATION_HOST_PORT` | Porta exposta no host para o serviço de notificações. |
| `AUTH_HOST_PORT` | Porta exposta no host para o serviço de autenticação. |
| `REDIS_HOST_PORT` | Porta exposta no host para o Redis. |
| `JWT_SECRET` | Chave secreta usada para assinar tokens JWT. Troque o valor do exemplo em ambientes reais. |
| `JWT_ALGORITHM` | Algoritmo usado para assinar e validar o JWT. |
| `JWT_EXPIRATION_HOURS` | Tempo de expiração do token JWT em horas. |
| `INITIAL_ADMIN_USERNAME` | Usuário administrador inicial criado no banco de autenticação. |
| `INITIAL_ADMIN_PASSWORD` | Senha do usuário administrador inicial. Troque o valor em ambientes reais. |
| `INITIAL_USER_USERNAME` | Usuário comum inicial criado no banco de autenticação. |
| `INITIAL_USER_PASSWORD` | Senha do usuário comum inicial. Troque o valor em ambientes reais. |
| `INITIAL_SUPPORT_USERNAME` | Segundo usuário comum inicial criado no banco de autenticação. |
| `INITIAL_SUPPORT_PASSWORD` | Senha do segundo usuário comum inicial. Troque o valor em ambientes reais. |
| `REDIS_HOST` | Host do Redis usado pelos serviços. |
| `REDIS_PORT` | Porta do Redis. |
| `QUEUE_NAME` | Nome da fila do Redis usada para eventos de pedidos. |
| `REDIS_BLOCK_TIMEOUT` | Timeout de bloqueio do consumidor de notificações. |
| `CATALOG_CONSUMER_BLOCK_TIMEOUT` | Timeout de bloqueio do consumidor de catálogo. |
| `CATALOG_SERVICE_URL` | URL interna do serviço de catálogo. |
| `CATALOG_REQUEST_TIMEOUT` | Timeout das chamadas HTTP para o catálogo. |
| `AUTH_DB_FILE` | Nome/caminho do banco SQLite do serviço de autenticação. |
| `CATALOG_DB_FILE` | Nome/caminho do banco SQLite do serviço de catálogo. |
| `ORDERS_DB_FILE` | Nome/caminho do banco SQLite do serviço de pedidos. |
| `PAYMENTS_DB_FILE` | Nome/caminho do banco SQLite do serviço de pagamentos. |
| `NOTIFICATIONS_DB_FILE` | Nome/caminho do banco SQLite do serviço de notificações. |

---

# Como Executar o Projeto (Docker)

> **Nota:** As instruções abaixo pressupõem que você já possui o **Docker** e o **VS Code** instalados na sua máquina.

## Caso 1: Primeira Execução (Criar e Rodar do Zero)

### 1° Passo: Criar as imagens do sistema

Abra o terminal na raiz do projeto e execute o comando build:

```bash
docker compose build

```

*(Nota: Caso utilize uma versão mais antiga do Docker Docker, o comando pode ser `docker-compose build`)*

### 2° Passo: Inicializar os containers e serviços

Com as imagens prontas, suba a orquestração dos serviços:

```bash
docker compose up

```

### 3° Passo: Abrir os containers no Visual Studio Code (Opcional)

Se precisar inspecionar ou alterar os ambientes isolados:

1. Vá até a aba de **Extensões** no VS Code (`Ctrl + Shift + X`).
2. Pesquise por **"Dev Containers"** (identificador: `ms-vscode-remote.remote-containers`) e instale-a.
3. Abra a paleta de comandos usando `Ctrl + Shift + P`.
4. Procure por: `Dev Containers: Attach to Running Container`.
5. Selecione o container desejado na lista.

> 💡 **Obs.:** Se o VS Code não abrir os arquivos automaticamente ao se conectar, vá no menu superior em **File > Open Folder...** e busque pelo caminho do diretório declarado no `WORKDIR` do Dockerfile correspondente (ex: `/app`).

---

## Caso 2: Inicializações Posteriores (Containers já existentes)

Se você já rodou o projeto antes e os containers estão parados, não há necessidade de buildar novamente.

### 1° Passo: Iniciar os Containers Existentes

Escolha uma das abordagens no terminal:

* **Abordagem 1:** Iniciar todos os containers de uma única vez (apenas os que estão parados):
```bash
docker start $(docker ps -q -f "status=exited")

```


* **Abordagem 2:** Iniciar um container específico por vez:
```bash
docker start <nome_do_container>

```



### 2° Passo: Conectar via VS Code

Caso queira debugar por dentro do container, basta repetir o **3° Passo do Caso 1**.
