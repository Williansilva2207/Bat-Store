# Bat-Store
Arquutetura de Sistemas

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
> ocker start $(docker ps -q -f "status=exited")

### 2° Passo: Abrir Container no Visual Studio Code
- Só seguir as dicas do 3° Passo do Caso 1.
