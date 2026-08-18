# Agentes ReAct do Obra Barata

Esta documentacao descreve como o modelo de agentes ReAct esta organizado hoje no Obra Barata, quais tools sao usadas, onde ficam os prompts e como o resultado volta para o contrato `ListaMateriaisObra`.

## Escopo

Atualmente o fluxo ReAct principal do projeto e o agente de precificacao e fornecedores, usado pelo endpoint:

```text
POST /buscar_fornecedores
```

O fluxo de analise IFC tambem usa LLM e prompts estruturados, mas nao e ReAct: ele chama o modelo com saida estruturada para gerar materiais e depois estimar quantidades. Esse fluxo IFC esta documentado no fim deste arquivo como dependencia anterior ao agente ReAct.

## Arquivos principais

| Arquivo | Papel |
| --- | --- |
| `backend/api/src/app/controllers/pricing_controller.py` | Endpoint `/buscar_fornecedores`, cria log por chamada e chama `PricingService`. |
| `backend/api/src/app/services/pricing/service.py` | Fachada de aplicacao para executar o agente de precos. |
| `backend/api/src/app/services/pricing/agent.py` | Implementacao do agente ReAct com LangGraph, prompts, ranking e aplicacao do resultado. |
| `backend/api/src/app/services/pricing/tools.py` | Tools LangChain disponiveis para o agente. |
| `backend/api/src/app/services/pricing/suppliers.py` | Integracoes/scrapers dos fornecedores e funcoes de normalizacao de busca. |
| `backend/api/src/app/services/pricing/request_logging.py` | Log por requisicao de `/buscar_fornecedores`. |
| `backend/api/src/app/services/ifc/prompts.py` | Prompts da etapa IFC, que alimenta a lista antes da precificacao. |
| `backend/api/src/app/services/ifc/analyzer.py` | Orquestracao das chamadas LLM da analise IFC. |

## Entrada e saida

O agente recebe uma `ListaMateriaisObra` ja quantificada. Cada material deve conter, quando possivel:

- `nome`
- `descricao`
- `quantidade`
- `medida`
- `perfil_produto`
- `origem`
- `justificativa`
- `referencias_ifc`

O agente retorna a mesma estrutura, preenchendo por material:

- `fornecedor`
- `lista_fornecedores`
- `valor_unitario`
- `valor_total`
- `preco_a_vista`
- `preco_a_prazo`
- `num_parcelas`
- `frete`
- `justificativa`

O endpoint aceita parametros de controle:

| Parametro | Padrao | Descricao |
| --- | --- | --- |
| `max_materials` | `3` | Quantidade maxima de ofertas em `lista_fornecedores` por material. |
| `max_materiais_processados` | `None` | Limite opcional de materiais processados na chamada. Util para testes. |
| `use_serper_fallback` | `false` | Quando `true`, inclui a tool Serper Shopping como fallback. |

## Modelo ReAct

O agente usa LangGraph com dois nos principais:

1. `reasoning_agent`
   - Recebe o historico de mensagens.
   - Chama o LLM com as tools bindadas.
   - Registra em log a resposta visivel e as tool calls solicitadas.

2. `tools`
   - Executa as tools solicitadas pelo LLM via `ToolNode`.
   - Registra em log os resultados das tools.

O grafo segue este ciclo:

```text
START
  -> reasoning_agent
  -> tools, se o LLM pediu tool calls
  -> reasoning_agent
  -> ...
  -> final, quando o LLM retorna JSON sem novas tool calls
```

Referencia no codigo:

- `SupplierReasoningState`
- `build_supplier_reasoning_agent`
- `tools_condition`
- `ToolNode`
- `MemorySaver`

Arquivo:

```text
backend/api/src/app/services/pricing/agent.py
```

## Fluxo por material

Para cada material da lista:

1. O servico monta um `thread_id` estavel com indice da area, indice do material e hash do nome.
2. O agente recebe:
   - `SystemMessage` com o prompt ReAct de fornecedores.
   - `HumanMessage` com payload JSON do material, area e data da consulta.
3. O LLM decide quais tools chamar.
4. As tools buscam fornecedores, calculam quantidades ou fazem contas auxiliares.
5. O LLM retorna apenas um JSON de atualizacao para `MaterialObra`.
6. O codigo extrai o JSON com `_extract_json_object`.
7. O codigo tambem coleta ofertas brutas vindas das mensagens das tools com `_supplier_tool_offer_payloads`.
8. As ofertas do LLM e das tools sao mescladas com `_merge_supplier_offer_payloads`.
9. Se alguma tool especifica relevante nao apareceu no payload final, o codigo roda uma busca complementar direta com `_missing_relevant_supplier_tool_offers`.
10. `_apply_supplier_update` valida, enriquece, ranqueia e aplica o resultado no material.

Funcoes relevantes:

- `preencher_fornecedores_com_reasoning_agent`
- `reason_about_material_suppliers`
- `_material_prompt`
- `_supplier_tool_offer_payloads`
- `_missing_relevant_supplier_tool_offers`
- `_apply_supplier_update`

## Prompts do agente ReAct

### Prompt principal de fornecedores

Constante:

```text
SUPPLIER_REASONING_SYSTEM_PROMPT
```

Arquivo:

```text
backend/api/src/app/services/pricing/agent.py
```

Esse prompt define o papel do agente:

- controlar tools;
- pesquisar um material por vez;
- comparar evidencias;
- retornar apenas JSON compativel com `MaterialObra`.

Regras importantes do prompt:

- Usar tools antes de escolher fornecedores quando houver tool disponivel.
- Preferir tools especificas de fornecedor antes de Serper.
- Usar Casa da Eletricidade apenas para materiais eletricos ou adjacentes.
- Para itens amplos de construcao/acabamento, consultar Pisolar e Comercial Alianca quando disponiveis.
- Usar `prepare_product_search_text_tool` antes das buscas em fornecedores.
- Nao inventar cotacoes reais, links, frete, parcelas ou disponibilidade.
- Criar `Estimativa IA` somente quando nenhuma busca real retornar preco aproveitavel.
- Descartar `Estimativa IA` quando existir oferta real precificada.
- Retornar o melhor fornecedor nos campos principais e alternativas em `lista_fornecedores`.
- Usar quantidade do material e unidade da oferta para decidir quantos pacotes comprar.
- Recalcular total como preco do pacote vezes quantidade de compra quando o pacote for identificado.

### Prompt humano por material

Funcao:

```text
_material_prompt(area_name, material, max_fornecedores_por_material)
```

Arquivo:

```text
backend/api/src/app/services/pricing/agent.py
```

Esse prompt monta um payload com:

- area da obra;
- `material.model_dump(mode="json")`;
- `data_consulta`;
- limite de ofertas desejado.

Ele reforca que:

- a resposta deve ser somente JSON de atualizacao;
- a quantidade exigida e `material.quantidade + material.medida`;
- `offer.unidade` deve ser usada para decidir a quantidade de pacotes;
- `lista_fornecedores` e a lista final de alternativas, nao apenas a oferta vencedora.

### Prompts das tools

As docstrings das funcoes marcadas com `@tool` tambem entram como instrucao para o LLM. Elas ficam em:

```text
backend/api/src/app/services/pricing/tools.py
```

Essas docstrings explicam quando usar cada tool, o dominio de cada fornecedor e restricoes de busca.

## Tools disponiveis

### `prepare_product_search_text_tool`

Entrada:

- `nome`
- `descricao`
- `quantidade`
- `medida`
- `fornecedor`

Saida:

- texto unico e compacto para busca.

Objetivo:

Limpar nomes com contexto de obra e manter o termo comercial realmente buscavel.

Exemplo conceitual:

```text
nome: "Pintura interna (tinta acrilica)"
medida: "lata 18 L"
saida: "tinta acrilica 18L"
```

A implementacao usa `build_product_search_text` em:

```text
backend/api/src/app/services/pricing/suppliers.py
```

### `search_supplier_pisolar_tool`

Fornecedor:

```text
Grupo Pisolar
```

Uso:

- materiais de construcao em geral;
- pisos e revestimentos;
- argamassas e rejuntes;
- hidraulica e eletrica;
- tintas;
- impermeabilizantes;
- ferramentas;
- iluminacao;
- portas, janelas, telhas e acabamento.

Implementacao:

- instancia `PisolarSupplier`;
- busca no site da Pisolar;
- retorna lista de `OfertaFornecedor` serializada.

### `search_supplier_comercial_alianca_tool`

Fornecedor:

```text
Comercial Alianca
```

Uso:

- materiais de construcao;
- pintura;
- eletrica;
- hidraulica;
- acabamentos;
- ferramentas;
- ferragens.

Implementacao:

- usa `TraySupplier`;
- `base_url = COMERCIAL_ALIANCA_BASE_URL`;
- `store_id = COMERCIAL_ALIANCA_STORE_ID`;
- parcelas padrao ate 10x quando o site permitir.

### `search_supplier_casa_eletricidade_tool`

Fornecedor:

```text
Casa da Eletricidade
```

Uso recomendado:

- fios e cabos;
- disjuntores;
- quadros;
- caixas eletricas;
- interruptores e tomadas;
- iluminacao;
- lampadas;
- chuveiros e torneiras eletricas;
- sensores;
- transformadores;
- fita isolante;
- ferramentas e instrumentos de medicao;
- itens hidraulicos, irrigacao e jardinagem quando coerentes com o fornecedor.

Restricao:

Nao deve ser usada para pintura, pisos, alvenaria, cimento, areia, portas, janelas ou acabamento geral, salvo quando o item for explicitamente eletrico ou adjacente.

Implementacao:

- usa `TraySupplier`;
- `base_url = CASA_ELETRICIDADE_BASE_URL`;
- `schema_first=True`;
- `product_card_fallback=True`.

### `search_supplier_serp_tool`

Fornecedor:

```text
Serper Shopping
```

Uso:

- fallback opcional quando fornecedores especificos nao retornam preco bom.

Condicao:

So entra na lista de tools se `use_serper_fallback=True`.

Dependencia:

```text
SERPER_API_KEY
```

### `purchase_quantity_tool`

Entrada:

- `required_quantity`
- `required_unit`
- `offer_unit`
- `unit_price`

Saida:

- tamanho do pacote;
- familia de unidade;
- quantidade de compra;
- quantidade coberta;
- preco total, quando `unit_price` foi informado.

Uso:

Calcular quantos pacotes comerciais comprar. Exemplo:

```text
material.quantidade = 30
material.medida = "L"
offer.unidade = "20 L"
resultado: purchase_quantity = 2
```

### `calculator_tool`

Uso:

Calculos aritmeticos diretos via `numexpr`.

### `percentage_tool`

Uso:

Aplicar percentual sobre valor base.

### `percent_change_tool`

Uso:

Calcular variacao percentual entre valor inicial e final.

## Conjunto padrao de tools

Funcao:

```text
default_supplier_pricing_tools(use_serper_fallback=False)
```

Arquivo:

```text
backend/api/src/app/services/pricing/tools.py
```

Sem Serper:

```text
prepare_product_search_text_tool
search_supplier_casa_eletricidade_tool
search_supplier_pisolar_tool
search_supplier_comercial_alianca_tool
purchase_quantity_tool
calculator_tool
percentage_tool
percent_change_tool
```

Com Serper:

```text
prepare_product_search_text_tool
search_supplier_casa_eletricidade_tool
search_supplier_pisolar_tool
search_supplier_comercial_alianca_tool
search_supplier_serp_tool
purchase_quantity_tool
calculator_tool
percentage_tool
percent_change_tool
```

## Pos-processamento das ofertas

Mesmo depois do LLM retornar JSON, o backend faz pos-processamento defensivo:

### Validacao

Funcao:

```text
_valid_offer_payloads
```

Cada oferta e validada como `OfertaFornecedor`. Ofertas invalidas sao descartadas com warning em log.

### Enriquecimento de quantidade e total

Funcao:

```text
_enrich_offer_for_material
```

Quando a unidade do material e a unidade da oferta sao compativeis, o sistema calcula:

```text
quantidade_de_compra = ceil(material.quantidade / tamanho_do_pacote)
valor_total = valor_unitario * quantidade_de_compra
preco_a_vista = valor_total
preco_a_prazo = valor_total
```

### Estimativa IA

Funcoes:

```text
_is_ai_estimate_offer
_discard_ai_estimates_when_real_priced_offers_exist
```

Regra:

- `Estimativa IA` so permanece quando nao ha oferta real precificada.
- Se existir oferta real com preco, a estimativa e descartada.

### Deduplicacao e ranking

Funcoes:

```text
_offer_identity
_offer_rank_value
_select_offer_options
_best_offer
```

O sistema:

- remove ofertas repetidas;
- ordena por melhor preco comparavel;
- tenta preservar diversidade de fornecedores;
- limita a quantidade final de alternativas conforme `max_materials`;
- preenche os campos principais do material com a melhor oferta.

### Busca complementar

Funcoes:

```text
_missing_relevant_supplier_tool_offers
_invoke_supplier_tool_for_material
```

Se o LLM nao inclui uma tool especifica relevante no payload final, o backend pode executar a busca complementar diretamente. Isso reduz casos em que o agente chama so um fornecedor mesmo quando outro tambem deveria ser comparado.

## Logs do agente

Cada chamada de `/buscar_fornecedores` cria um arquivo proprio:

```text
logs/buscar_fornecedores/YYYY-MM-DD_HH-MM-SS-microsegundos.log
```

Configuracao:

```text
PRICING_REQUEST_LOG_DIR=/logs/buscar_fornecedores
```

Os logs incluem:

- inicio e fim da chamada;
- quantidade de areas e materiais;
- limites configurados;
- chamadas ao LLM;
- tool calls solicitadas;
- resultados das tools;
- JSON extraido;
- ofertas mescladas;
- atualizacao aplicada ao material;
- excecoes do endpoint.

Arquivos:

```text
backend/api/src/app/controllers/pricing_controller.py
backend/api/src/app/services/pricing/request_logging.py
backend/api/src/app/services/pricing/agent.py
```

## Fluxo IFC anterior ao ReAct

O endpoint `/analisar_ifc` gera a lista usada como entrada do agente ReAct. Esse fluxo nao usa tools ReAct, mas usa prompts importantes.

### Geracao da lista de materiais

Arquivo de prompts:

```text
backend/api/src/app/services/ifc/prompts.py
```

Prompts/constantes:

- `MATERIAL_LIST_COMMON_SYSTEM_PROMPT`
- `VEDACAO_ACABAMENTOS_PROMPT`
- `ABERTURAS_PROMPT`
- `INSTALACOES_PROMPT`
- `ESTRUTURA_COBERTURA_PROMPT`
- `MATERIAL_LIST_PROMPT_BLOCKS`

Orquestracao:

```text
backend/api/src/app/services/ifc/analyzer.py
```

Funcao principal:

```text
IfcMaterialAnalyzer.generate_material_list
```

Como funciona:

1. Carrega o modelo estruturado com `ListaMateriaisObra`.
2. Executa blocos em paralelo com `asyncio.gather`.
3. Cada bloco recebe um system prompt proprio.
4. Cada bloco recebe um human prompt com `build_digest_result` e uma parte filtrada da `lista_base`.
5. As listas parciais sao mescladas por `_merge_material_lists`.

### Estimativa de quantidades

Prompt:

```text
QUANTITY_SYSTEM_PROMPT
```

Arquivo:

```text
backend/api/src/app/services/ifc/prompts.py
```

Orquestracao:

```text
IfcMaterialAnalyzer.estimate_quantities
```

Esse prompt manda o LLM preencher quantidades usando:

- QTO do IFC;
- geometria inferida;
- contagens de portas, janelas e outros elementos;
- premissas de mercado declaradas;
- justificativas e referencias IFC.

Depois da estimativa, o servico IFC remove materiais com quantidade exatamente zero antes de responder:

```text
remove_zero_quantity_materials
```

Arquivo:

```text
backend/api/src/app/services/ifc/service.py
```

## Modelo LLM

A construcao do chat model fica em:

```text
backend/api/src/app/services/ifc/llm_client.py
```

Funcao:

```text
build_openai_chat_model
```

Variaveis relevantes:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `LLM_TEMPERATURE`
- `LLM_REASONING_EFFORT`
- `LLM_REQUEST_TIMEOUT_SECONDS`
- `LLM_MAX_RETRIES`
- `LLM_MAX_CONTENT_CHARS`

## Pontos de atencao

- O agente depende da estabilidade dos sites dos fornecedores.
- `valor_unitario` representa o preco de um pacote/unidade comercial, nao necessariamente o custo total do material.
- O backend tenta calcular totais quando consegue inferir o tamanho do pacote.
- O frontend tambem possui uma regra defensiva para exibir e somar o total correto quando a API retorna total igual ao unitario.
- `Estimativa IA` nao e cotacao real: e apenas uma referencia orcamentaria quando nao foi encontrada oferta aproveitavel.
- Os prompts devem ser mantidos junto com testes de regressao, porque pequenas mudancas podem alterar chamadas de tools, ranking e formato de saida.
