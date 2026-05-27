# Bat-Store
Arquutetura de Sistemas

# Variaveis de ambiente

Antes de subir os containers, crie um arquivo `.env` a partir do `.env.example`.

Variaveis disponiveis:

| Variavel | Descricao |
| --- | --- |
| `APP_HOST` | Host usado pelo Uvicorn dentro dos containers. |
| `APP_PORT` | Porta interna usada pelos servicos da API. |
| `CATALOG_HOST_PORT` | Porta exposta no host para o servico de catalogo. |
| `ORDER_HOST_PORT` | Porta exposta no host para o servico de pedidos. |
| `PAYMENT_HOST_PORT` | Porta exposta no host para o servico de pagamentos. |
| `NOTIFICATION_HOST_PORT` | Porta exposta no host para o servico de notificacoes. |
| `AUTH_HOST_PORT` | Porta exposta no host para o servico de autenticacao. |
| `REDIS_HOST_PORT` | Porta exposta no host para o Redis. |
| `JWT_SECRET` | Chave secreta usada para assinar tokens JWT. Troque o valor do exemplo em ambientes reais. |
| `JWT_ALGORITHM` | Algoritmo usado para assinar e validar JWT. |
| `JWT_EXPIRATION_HOURS` | Tempo de expiracao do token JWT em horas. |
| `INITIAL_ADMIN_USERNAME` | Usuario administrador inicial criado no banco de autenticacao. |
| `INITIAL_ADMIN_PASSWORD` | Senha do usuario administrador inicial. Troque o valor do exemplo em ambientes reais. |
| `INITIAL_USER_USERNAME` | Usuario comum inicial criado no banco de autenticacao. |
| `INITIAL_USER_PASSWORD` | Senha do usuario comum inicial. Troque o valor do exemplo em ambientes reais. |
| `INITIAL_SUPPORT_USERNAME` | Segundo usuario comum inicial criado no banco de autenticacao. |
| `INITIAL_SUPPORT_PASSWORD` | Senha do segundo usuario comum inicial. Troque o valor do exemplo em ambientes reais. |
| `REDIS_HOST` | Host do Redis usado pelos servicos. |
| `REDIS_PORT` | Porta do Redis. |
| `QUEUE_NAME` | Nome da fila Redis usada para eventos de pedidos. |
| `REDIS_BLOCK_TIMEOUT` | Timeout de bloqueio do consumidor de notificacoes. |
| `CATALOG_CONSUMER_BLOCK_TIMEOUT` | Timeout de bloqueio do consumidor de catalogo. |
| `CATALOG_SERVICE_URL` | URL interna do servico de catalogo. |
| `CATALOG_REQUEST_TIMEOUT` | Timeout das chamadas HTTP para o catalogo. |
| `AUTH_DB_FILE` | Nome/caminho do banco SQLite do servico de autenticacao. |
| `CATALOG_DB_FILE` | Nome/caminho do banco SQLite do servico de catalogo. |
| `ORDERS_DB_FILE` | Nome/caminho do banco SQLite do servico de pedidos. |
| `PAYMENTS_DB_FILE` | Nome/caminho do banco SQLite do servico de pagamentos. |
| `NOTIFICATIONS_DB_FILE` | Nome/caminho do banco SQLite do servico de notificacoes. |

# Docker

## Caso 1 Uso do Docker (Caso não tenha rodado antes)
Vale ressaltar que as seguintes instruções presumem que o Docker e o VS Code já estão instaldos em sua máquina.
### 1° Passo: Criar as imagens
- Abrir o terminial
- Por o comando a seguir
> docker composer build

### 2° Passo: Criar Containers e rodar
- No terminal por:
> docker composer up

### 3° Passo: Abrir Container no Visual Studio Code
- Ir em extensões
- Pesquise por "Dev Containers" (identificador ms-vscode-remote.remote-containers) e instale-a
- Use o seguinte comando:
> Ctrl + shift + p
- Pesquise por Dev Container: Attach to Running Container
- Escolha o container

**Obs.: Se o VS Code não abrir os arquivos, vá na aba File, clique em Open Folder... e procure pelo nome da pasta que está declarado no WORKDIR do Dockerfile**

## Caso 2: Uso do Docker (Após já ter utilizado)

### 1° Passo: Rodar os Containers Já Criados
Você pode seguir dois caminhos:
- 1° Rodar um container de cada vez:
> docker start <nome do container>
- 2° Rodar todos em um só comando (somente os que não estão sendo executados)
> docker start $(docker ps -q -f "status=exited")

### 2° Passo: Abrir Container no Visual Studio Code
- Só seguir as dicas do 3° Passo do Caso 1.
