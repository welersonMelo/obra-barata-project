# README Governanca IA

## Objetivo

Este documento descreve a arquitetura da solucao Obra Barata com foco no fluxo de dados e nos mecanismos de apoio a governanca de IA ja implementados. A descricao foi consolidada a partir da configuracao definida em `docker-compose-dev.yml` e dos componentes atualmente presentes no frontend e backend.

## Visao Geral da Solucao

A solucao Obra Barata e uma aplicacao full stack containerizada para apoiar o cadastro e a qualificacao de startups a partir da leitura automatizada de seus sites institucionais. A plataforma combina coleta automatica de conteudo web, geracao assistida por modelo de linguagem, revisao humana e persistencia estruturada dos resultados.

Em termos funcionais, a solucao opera em quatro etapas principais:

1. recepcao da URL e dos dados iniciais da startup no frontend;
2. raspagem automatica do site e extracao de conteudo pelo backend;
3. geracao de respostas por IA com base em questionario versionado;
4. revisao humana e gravacao das respostas finais confirmadas.

Esse desenho estabelece um fluxo no qual a IA atua como mecanismo de apoio ao preenchimento, enquanto a confirmacao final permanece no processo de revisao da aplicacao.

## Requisitos Funcionais

- Interface web em React/Vite para iniciar a avaliacao, acompanhar o processamento e revisar respostas.
- Backend Python com FastAPI/Uvicorn para orquestrar scraping, processamento de IA e persistencia dos resultados.
- API exposta internamente na porta `8000`.
- Frontend exposto internamente na porta `3000`.
- Roteamento interno por Nginx, com backend publicado sob o prefixo `/api`.
- Processamento assincrono de scraping por filas Redis/ARQ, com workers dedicados para coleta HTTP e coleta via navegador.
- Integracao com Azure OpenAI por variaveis de ambiente para geracao de respostas com base no conteudo raspado.
- Uso de questionario versionado para estruturar a geracao e a validacao das respostas.
- Persistencia separada de respostas geradas pela IA e respostas finais confirmadas em arquivos CSV versionados.
- Disponibilizacao de status de job e arquivos gerados pela API.

## Requisitos Nao Funcionais

- Arquitetura containerizada em Docker Compose, com separacao entre frontend, backend, proxy, Redis e workers.
- Processamento desacoplado da interface por meio de filas assincronas.
- Cache e controle de concorrencia centralizados em Redis para reduzir retrabalho e organizar a raspagem por dominio.
- Persistencia de dados operacionais em volumes montados para logs, arquivos CSV e dados do Redis.
- Parametrizacao da operacao por variaveis de ambiente, incluindo filas, timeouts, limites e configuracao do modelo.
- Escalabilidade horizontal por funcao, com possibilidade de ampliar API e workers conforme a carga.

Para expansao de capacidade, as alternativas principais sao:

- Aumentar os recursos computacionais do host Docker.
- Separar servicos em multiplas maquinas ou ambientes dedicados.
- Migrar a composicao para uma plataforma de orquestracao de containers.

## Arquitetura da Solucao

### Base arquitetural

A arquitetura da solucao em ambiente de desenvolvimento e definida pelo arquivo `docker-compose-dev.yml`, com os seguintes servicos:

- `frontend`
- `backend`
- `nginx-proxy`
- `redis`
- `worker-http`
- `worker-browser`

Todos os servicos compartilham a rede `shared_network`, enquanto os dados operacionais sao persistidos em volumes e diretorios montados.

## Componentes

### Frontend

O frontend, implementado em React com Vite, concentra a experiencia do usuario durante o cadastro. Ele recebe os dados iniciais, inicia o processamento de leitura do site, acompanha o job em execucao, apresenta as respostas geradas e permite a revisao final antes do envio definitivo.

### Backend API

O backend, implementado com FastAPI, centraliza as regras da aplicacao. Ele normaliza URLs, consulta cache, cria jobs assincronos, fornece status de processamento, valida respostas finais e controla a persistencia dos artefatos produzidos.

### Nginx Proxy

O Nginx atua como ponto unico de entrada HTTP da solucao. Ele encaminha o trafego para o frontend e para a API dentro da rede interna do ambiente Docker.

### Redis

O Redis exerce papel central na arquitetura. Ele sustenta as filas ARQ, armazena cache de conteudo e resultados, guarda status dos jobs, controla a concorrencia por dominio e fornece locks para gravacao segura dos CSVs.

### Worker HTTP

O `worker-http` executa a etapa inicial de raspagem web. Seu papel e realizar a coleta principal de paginas por meio da camada HTTP e preparar o conteudo para as etapas seguintes do fluxo.

### Worker Browser

O `worker-browser` executa a raspagem em navegador automatizado quando a coleta inicial nao produz conteudo suficiente. Esse componente amplia a cobertura para paginas que dependem de renderizacao em browser.

### Camada de LLM

A camada de geracao por IA recebe o conteudo raspado e o questionario correspondente, processando as perguntas por bloco e produzindo respostas estruturadas associadas a nivel de confianca.

### Arquivos CSV

Os CSVs representam os artefatos persistidos da governanca operacional da solucao:

- `llm_generated_answers_<version>.csv`: respostas geradas automaticamente;
- `final_answers_<version>.csv`: respostas revisadas e confirmadas no fluxo final.

## Fluxo de Dados

O fluxo de dados da solucao ocorre da seguinte forma:

1. o usuario informa nome e URL da startup no frontend;
2. o frontend envia a requisicao `POST /scrape` para o backend;
3. o backend normaliza a URL e consulta o Redis para verificar conteudo ou resultado em cache;
4. quando necessario, o backend cria um job e o encaminha para a fila de processamento;
5. o `worker-http` realiza a coleta inicial do site;
6. se o conteudo obtido ficar abaixo do limiar configurado, o processamento e escalado para o `worker-browser`;
7. o conteudo capturado e armazenado no Redis para reutilizacao no job e em chamadas futuras;
8. a cadeia de geracao por IA e iniciada por blocos do questionario;
9. cada bloco produz respostas estruturadas com base no conteudo coletado;
10. as respostas geradas pela IA sao persistidas em CSV proprio;
11. o frontend consulta periodicamente o status do job e exibe o progresso ao usuario;
12. as respostas sao apresentadas para revisao, ajuste e complementacao;
13. o frontend envia as respostas finais para a API;
14. o backend valida e grava as respostas confirmadas no CSV final.

## Governanca de IA Materializada na Solucao

Os mecanismos de governanca de IA implementados na solucao aparecem diretamente no desenho funcional e arquitetural:

### Separacao entre sugestao automatica e resposta final

A plataforma mantem arquivos distintos para as respostas produzidas pela IA e para as respostas efetivamente confirmadas no processo final.

### Revisao humana no fluxo

As respostas geradas sao exibidas ao usuario para conferencia e edicao antes da gravacao definitiva do cadastro.

### Versionamento do questionario

O questionario utilizado pela aplicacao possui versao associada, refletida no processamento e nos nomes dos arquivos de saida.

### Rastreabilidade de execucao

Os registros persistidos incluem identificadores de execucao, URL processada, identificacao da pergunta e data de geracao ou confirmacao.

### Processamento por blocos

A organizacao por blocos permite acompanhar a execucao de forma granular e manter a estruturacao tematica do questionario no fluxo de IA.

### Indicacao de confianca nas respostas geradas

As respostas produzidas automaticamente sao registradas com `confidence_level`, compondo a trilha de apoio a analise posterior.

### Reaproveitamento controlado por cache

O uso de cache permite reutilizar artefatos previamente processados, mantendo consistencia operacional para URLs ja tratadas.

## Estrutura de Implantacao no Compose

No `docker-compose-dev.yml`, a solucao e organizada da seguinte forma:

- `backend`: executa a API FastAPI na porta interna `8000`;
- `frontend`: executa a aplicacao React em modo preview na porta interna `3000`;
- `nginx-proxy`: publica a porta `80` e atua como gateway HTTP;
- `redis`: fornece filas, cache e mecanismos de controle distribuidos;
- `worker-http`: processa jobs de raspagem HTTP;
- `worker-browser`: processa jobs de raspagem via navegador;
- `redis_data`: volume nomeado para persistencia do Redis;
- `./logs` e `./data`: diretorios montados para logs e dados operacionais.

## Conclusao

A solucao Obra Barata implementa uma arquitetura distribuida e orientada a processamento assincrono para apoiar a qualificacao de startups com uso de IA. Seu fluxo combina captura automatizada de conteudo, geracao estruturada de respostas, acompanhamento por job e bloco, revisao humana e persistencia versionada dos resultados. A organizacao entre frontend, API, workers, Redis e arquivos de saida sustenta um modelo operacional em que a IA participa como apoio ao processo de avaliacao dentro de uma trilha rastreavel e estruturada.
