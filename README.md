# Obra Barata

Obra Barata e uma aplicacao full-stack para transformar arquivos IFC em uma lista de compras orcada para obras residenciais e reformas. O sistema extrai informacoes do modelo, usa LLM para estruturar e complementar materiais, pesquisa fornecedores reais e gera um resumo financeiro para apoiar a decisao de compra.

O produto ainda esta em desenvolvimento. Hoje o backend e funcional para upload/analisador IFC e busca de fornecedores; o frontend React usa login mockado e salva projetos apenas em memoria.

## O que existe hoje

- Frontend React + Vite + TypeScript, baseado no prototipo `Obra Barata.dc.html`.
- Login mockado, sem cadastro real de usuarios.
- Projetos mantidos em memoria no navegador enquanto a sessao estiver aberta.
- Upload de arquivo IFC pelo endpoint `/upload_ifc`.
- Analise de IFC com LLM pelo endpoint `/analisar_ifc`.
- Remocao automatica, na resposta de `/analisar_ifc`, de materiais com `quantidade` exatamente `0`.
- Revisao manual no frontend para remover/restaurar materiais antes da cotacao.
- Busca de fornecedores pelo endpoint `/buscar_fornecedores`.
- Integracoes de fornecedores com Pisolar, Comercial Alianca e Casa da Eletricidade.
- Fallback opcional com Serper Shopping.
- Geracao de oferta `Estimativa IA` quando nenhum fornecedor real retorna preco utilizavel.
- Logs por chamada de `/buscar_fornecedores`, com um arquivo por requisicao.
- Resumo financeiro por categoria, total a vista, total a prazo e exportacao CSV.

## Fluxo principal

1. O usuario entra no frontend com login mockado.
2. Cria um projeto em memoria com nome, tipo, endereco, area e perfil de acabamento.
3. Envia um arquivo `.ifc`.
4. O backend salva o arquivo em `data/ifc`, extrai um digest tecnico e retorna metadados do modelo.
5. O usuario aciona a analise IFC.
6. A LLM transforma o digest em uma `ListaMateriaisObra`, estima quantidades e registra origem, justificativa, confianca e referencias IFC.
7. Materiais com quantidade `0` sao removidos da resposta.
8. O usuario revisa a lista e remove itens que nao deseja cotar.
9. O frontend envia a lista revisada para `/buscar_fornecedores`.
10. O agente de precos consulta tools de fornecedores, monta alternativas e escolhe a melhor oferta por material.
11. Se nao houver preco real confiavel, o agente cria uma oferta `Estimativa IA` com justificativa.
12. O frontend mostra fornecedores, permite trocar a oferta selecionada e consolida o resumo financeiro.

## Arquitetura

```text
obra-barata-project/
+-- backend/
|   +-- api/                  # FastAPI, modelos Pydantic, servicos IFC e precos
|   +-- ml/                   # Notebooks e arquivos de experimentacao
+-- frontend/                 # React, Vite e TypeScript
+-- nginx/                    # Proxy reverso para frontend e backend
+-- cloudflare/               # Infra opcional para Cloudflare Tunnel
+-- data/                     # Arquivos IFC e registros locais gerados em runtime
+-- logs/                     # Logs locais gerados em runtime
+-- docker-compose-dev.yml    # Stack principal de desenvolvimento local
+-- docker-compose-test.yml   # Infra experimental/local com tunnel, Redis e workers
+-- README_GOVERNANCA_IA.md   # Diretrizes de governanca de IA
```

## Backend

O backend fica em `backend/api` e usa:

- FastAPI
- Pydantic
- ifcopenshell
- LangChain/LangGraph
- OpenAI via `langchain-openai`
- httpx e BeautifulSoup para busca em fornecedores
- uv para instalacao e execucao

### Endpoints

#### `GET /health`

Health check simples.

Resposta:

```json
{"status":"ok"}
```

#### `POST /upload_ifc`

Recebe um arquivo IFC via `multipart/form-data`, salva o arquivo e retorna informacoes tecnicas extraidas.

Campo do form:

- `file`: arquivo `.ifc` ou `.ifczip`

Resposta principal:

```json
{
  "ifc_id": "string",
  "filename": "modelo.ifc",
  "schema": "IFC4",
  "pavimentos": [],
  "areas": {},
  "materiais": [],
  "camadas_material": []
}
```

#### `POST /analisar_ifc`

Recebe o `ifc_id` retornado pelo upload e executa a analise por LLM.

Request:

```json
{
  "ifc_id": "string"
}
```

Resposta: `ListaMateriaisObra`.

Observacao importante: materiais com `quantidade: 0` sao filtrados antes da resposta do endpoint.

#### `POST /buscar_fornecedores`

Recebe uma `ListaMateriaisObra` ja quantificada e preenche fornecedores, alternativas, precos e justificativas.

Query params:

- `max_materials`: quantidade maxima de ofertas mantidas em `lista_fornecedores` por material. Padrao: `3`. Limite: `0` a `10`.
- `max_materiais_processados`: limite opcional de materiais processados na chamada. Util para testes e execucoes parciais.
- `use_serper_fallback`: quando `true`, permite busca via Serper se os fornecedores especificos nao retornarem preco. Padrao: `false`.

Exemplo de request:

```json
{
  "obra": "Casa exemplo",
  "moeda": "BRL",
  "areas": [
    {
      "area": "Pintura",
      "materiais": [
        {
          "nome": "Pintura interna (tinta acrilica)",
          "descricao": "Tinta para paredes internas",
          "quantidade": 3,
          "medida": "lata 18 L",
          "fornecedor": "",
          "lista_fornecedores": []
        }
      ]
    }
  ]
}
```

### Contrato `ListaMateriaisObra`

A API trafega materiais agrupados por area de compra:

```json
{
  "obra": "string",
  "responsavel": "string",
  "data": "string",
  "moeda": "BRL",
  "observacoes": "string",
  "areas": [
    {
      "area": "Pintura",
      "materiais": [
        {
          "nome": "Tinta acrilica",
          "descricao": "Tinta para paredes internas",
          "quantidade": 3,
          "medida": "lata 18 L",
          "fornecedor": "",
          "lista_fornecedores": [],
          "valor_unitario": null,
          "valor_total": null,
          "preco_a_vista": null,
          "preco_a_prazo": null,
          "num_parcelas": null,
          "frete": null,
          "perfil_produto": "Medio custo",
          "origem": "ifc",
          "justificativa": null,
          "nivel_confianca": null,
          "referencias_ifc": []
        }
      ]
    }
  ]
}
```

Valores aceitos para `perfil_produto`:

- `Baixo custo`
- `Medio custo`
- `Alto custo`

Valores aceitos para `origem`:

- `ifc`
- `ia`
- `usuario`
- `fornecedor`
- `template`

### Logica de precos

O agente de precos usa uma abordagem ReAct com tools:

- `prepare_product_search_text_tool`: transforma nome, descricao, quantidade e medida em um texto unico e mais adequado para busca. Exemplo: `Pintura interna (tinta acrilica)` + `lata 18 L` vira algo como `tinta acrilica 18L`.
- `search_supplier_pisolar_tool`: busca produtos no site da Pisolar.
- `search_supplier_comercial_alianca_tool`: busca produtos no site da Comercial Alianca.
- `search_supplier_casa_eletricidade_tool`: busca produtos na Casa da Eletricidade, principalmente para itens eletricos e categorias adjacentes.
- `search_supplier_serp_tool`: fallback opcional via Serper Shopping.
- `purchase_quantity_tool`: calcula quantos pacotes comerciais comprar com base na unidade exigida e na unidade da oferta.
- tools de calculo para percentuais e aritmetica.

Regras importantes:

- Fornecedores especificos sao preferidos antes de Serper.
- Casa da Eletricidade so deve ser usada para itens eletricos ou adjacentes.
- Pisolar e Comercial Alianca sao consultados para construcao, acabamento, pintura, hidraulica, ferramentas e similares.
- O agente preserva alternativas relevantes em `lista_fornecedores`.
- O melhor fornecedor do material e preenchido nos campos principais do material.
- Quando existe oferta real com preco, a oferta `Estimativa IA` e descartada.
- Quando nao existe preco real aproveitavel, o agente pode criar exatamente uma oferta `Estimativa IA`, com justificativa e aviso de revisao com fornecedor real.

### Logs de `/buscar_fornecedores`

Cada chamada cria um arquivo proprio de log com data e hora no nome.

Diretorio padrao:

```text
logs/buscar_fornecedores/
```

No container, o caminho configurado e:

```text
/logs/buscar_fornecedores
```

O nome segue o formato:

```text
YYYY-MM-DD_HH-MM-SS-microsegundos.log
```

Se o diretorio configurado nao puder ser criado/escrito, a aplicacao tenta usar um diretorio temporario do sistema.

## Frontend

O frontend fica em `frontend` e usa:

- React 18
- TypeScript
- Vite
- lucide-react

Telas atuais:

- Login mockado
- Lista/criacao de projetos
- Upload IFC
- Revisao de materiais retornados pela IA
- Busca e escolha de fornecedores
- Resumo financeiro e exportacao CSV

Regras atuais do frontend:

- Login e apenas local/mockado.
- Projetos ficam apenas em memoria.
- Materiais, quantidades, fornecedores e precos vem do backend.
- O frontend nao usa dados mockados para materiais, fornecedores ou precos.
- A URL da API e definida por `VITE_API_BASE_URL`; no Docker, ela fica como `/api`.

## Como rodar com Docker

Crie o arquivo `.env` a partir do exemplo:

```bash
cp .env.example .env
```

No PowerShell:

```powershell
Copy-Item .env.example .env
```

Preencha ao menos:

```env
PROJECT_NAME=obra-barata
DEPLOY_ENV=dev
ROOT_PATH_BACKEND=/api
OPENAI_API_KEY=sua_chave_openai
OPENAI_MODEL=gpt-4.1
```

Suba a stack principal:

```bash
docker compose -f docker-compose-dev.yml up -d --build
```

Acesse:

- Frontend: `http://localhost/`
- API/Swagger: `http://localhost/api`
- Health check: `http://localhost/api/health`

Para acompanhar logs do backend:

```bash
docker compose -f docker-compose-dev.yml logs -f backend
```

Para parar:

```bash
docker compose -f docker-compose-dev.yml down
```

## Execucao local sem Docker

Backend:

```bash
cd backend/api
uv sync
uv run uvicorn app.app:app --host 0.0.0.0 --port 8000
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

Nesse modo, ajuste a URL da API se necessario:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Variaveis de ambiente

Principais variaveis:

| Variavel | Obrigatoria | Padrao | Uso |
| --- | --- | --- | --- |
| `PROJECT_NAME` | Sim no Docker | vazio | Prefixo dos containers/imagens |
| `DEPLOY_ENV` | Sim no Docker | vazio | Ambiente usado nos nomes dos containers |
| `ROOT_PATH_BACKEND` | Recomendado | vazio | Base path da API atras do nginx; use `/api` no Docker |
| `OPENAI_API_KEY` | Sim para IA | vazio | Chave usada pela analise IFC e agente de precos |
| `OPENAI_MODEL` | Nao | `gpt-4.1` | Modelo usado nas chamadas LLM |
| `LLM_TEMPERATURE` | Nao | `0.2` | Temperatura do modelo |
| `LLM_REASONING_EFFORT` | Nao | `low` | Esforco de raciocinio para modelos que suportam |
| `LLM_REQUEST_TIMEOUT_SECONDS` | Nao | `300` | Timeout das chamadas LLM |
| `LLM_MAX_RETRIES` | Nao | `3` | Tentativas das chamadas LLM |
| `LLM_MAX_CONTENT_CHARS` | Nao | `120000` | Limite de conteudo enviado ao LLM |
| `IFC_STORAGE_DIR` | Nao | `/data/ifc` | Onde os IFCs sao armazenados |
| `PRICING_REQUEST_LOG_DIR` | Nao | `/logs/buscar_fornecedores` | Onde ficam os logs por chamada de precos |
| `SUPPLIER_SEARCH_TIMEOUT_SECONDS` | Nao | `20` | Timeout das buscas em fornecedores |
| `SUPPLIER_SEARCH_RESULTS_PER_PROVIDER` | Nao | `5` | Quantidade base de resultados por fornecedor |
| `SERPER_API_KEY` | Nao | vazio | Habilita fallback Serper quando solicitado |
| `CLOUDFLARED_TOKEN` | Nao | vazio | Token para uso com Cloudflare Tunnel |

## Testes e validacao

Backend:

```bash
cd backend/api
uv run pytest
```

Frontend:

```bash
cd frontend
npm run build
```

Validacao Docker usada no desenvolvimento:

```bash
docker build -t obra-barata-frontend-check frontend
docker compose -f docker-compose-dev.yml config
docker compose -f docker-compose-dev.yml up -d --build frontend nginx-proxy
```

Checks rapidos:

```bash
curl http://localhost/
curl http://localhost/api/health
```

## Dados gerados

- `data/ifc`: arquivos IFC e registros de processamento.
- `logs/buscar_fornecedores`: logs por chamada do endpoint de busca de fornecedores.
- `frontend/dist`: build de producao do frontend, criado durante build local.

Esses dados sao de runtime e nao devem ser versionados quando contiverem entradas reais de usuario, logs, chaves, resultados de scraping ou arquivos de obra.

## Seguranca e governanca de IA

Nunca publique:

- `.env`
- chaves OpenAI, Serper ou Cloudflare
- arquivos IFC reais de clientes
- logs com dados de obra, URLs de consulta ou respostas de LLM
- certificados privados

A IA e usada como apoio, nao como fonte final de verdade. Materiais inferidos, quantidades estimadas e precos medios devem ser revisados pelo usuario antes de qualquer compra.

As diretrizes completas estao em `README_GOVERNANCA_IA.md`.

## Limitacoes atuais

- Nao ha autenticacao real.
- Nao ha persistencia real de usuarios/projetos no frontend.
- O projeto salvo no frontend se perde ao recarregar a pagina.
- O frontend ainda nao permite edicao completa de todos os campos retornados pelo backend.
- Os fornecedores dependem da estrutura HTML/API dos sites consultados, que pode mudar.
- `Estimativa IA` e apenas referencia orcamentaria quando nao ha cotacao real.
- `docker-compose-test.yml` contem infraestrutura de tunnel, Redis e workers ainda experimental para o estado atual do codigo.

## Licenca

Distribuido sob a licenca MIT. Veja `LICENSE`.
