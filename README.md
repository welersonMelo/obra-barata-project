# Obra Barata

Aplicacao full-stack para transformar projetos Revit em um planejamento inteligente de compras para obras residenciais de pequeno e medio porte, como casas em condominio, pequenos comercios, clinicas e escritorios.

O foco da primeira versao e reduzir o tempo gasto para levantar materiais, pesquisar precos e montar um orcamento de compras confiavel. A plataforma nao pretende substituir um ERP de construcao civil nem controlar toda a execucao da obra.

## Visao Geral do Produto

O fluxo principal comeca com o upload de um arquivo Revit. A aplicacao interpreta os elementos do modelo, extrai quantitativos disponiveis e usa Inteligencia Artificial para complementar materiais, insumos e consumiveis que normalmente nao estao modelados.

Exemplos de itens inferidos pela IA incluem argamassas, rejuntes, impermeabilizantes, fixadores, parafusos, perdas de materiais, insumos de instalacao e demais componentes necessarios para execucao da obra.

Todo item sugerido automaticamente pela IA deve ser identificado como estimativa, com justificativa, origem da informacao e nivel de confianca. O usuario pode aceitar, editar ou remover qualquer sugestao antes da geracao do planejamento de compras.

## Planejamento de Compras

Apos consolidar os materiais, o sistema organiza automaticamente os itens em categorias que representam etapas naturais da obra:

- Fundacao
- Estrutura
- Alvenaria
- Cobertura
- Esquadrias
- Instalacoes hidraulicas
- Instalacoes eletricas
- Revestimentos internos
- Revestimentos externos
- Pisos e revestimentos ceramicos
- Loucas e metais
- Pintura
- Gesso e forros
- Vidros
- Impermeabilizacao
- Area externa e paisagismo
- Ferragens e fixadores
- Materiais complementares

Para cada material, a plataforma realiza pesquisa automatica de precos usando fornecedores configurados pelo usuario. A pesquisa pode combinar APIs oficiais, quando disponiveis, com extracao automatica de dados ou integracoes equivalentes para fornecedores sem API publica.

Cada resultado deve apresentar, sempre que possivel:

- fornecedor;
- descricao do produto;
- marca;
- unidade;
- quantidade;
- preco unitario;
- preco total;
- disponibilidade;
- data da consulta;
- link do produto.

## Perfil do Produto

Cada material possui um campo **Perfil do Produto**, usado para definir o padrao desejado para aquele item.

Perfis iniciais:

- Baixo custo
- Medio custo
- Alto custo

O perfil escolhido influencia a pesquisa de precos, priorizando produtos compativeis com o padrao de acabamento. Ele pode ser alterado por material ou aplicado a uma categoria inteira. Sempre que houver alteracao, a plataforma deve executar uma nova pesquisa de precos.

## Edicao e Compra

Depois da pesquisa, o usuario pode:

- escolher qual fornecedor deseja utilizar;
- alterar manualmente fornecedor;
- alterar manualmente preco;
- alterar descricao do produto;
- alterar quantidade;
- alterar o perfil do produto.

Cada material deve ser adquirido integralmente em apenas um fornecedor. A aplicacao nao divide a compra de um mesmo item entre varios estabelecimentos, privilegiando descontos por volume, simplificacao logistica e a pratica comum em obras residenciais.

Cada compra tambem permite informar:

- pagamento a vista;
- pagamento a prazo;
- valor a vista;
- valor a prazo;
- percentual de desconto a vista.

Todos esses valores podem ser editados manualmente.

Ao final, a aplicacao apresenta um resumo consolidado contendo:

- custo por categoria;
- total geral a vista;
- total geral a prazo;
- economia obtida no pagamento a vista;
- lista de materiais por fornecedor.

A plataforma apenas sugere fornecedores e precos. A compra continua sendo realizada pelo cliente diretamente na loja fisica ou online.

## Requisitos Funcionais

### RF01 - Cadastro de usuarios

A aplicacao deve permitir o cadastro, autenticacao e gerenciamento de usuarios.

### RF02 - Cadastro de projetos

A aplicacao deve permitir o cadastro de projetos contendo informacoes basicas da obra.

### RF03 - Upload de arquivo Revit

A aplicacao deve permitir o envio de arquivos Revit como fonte principal das informacoes do projeto.

### RF04 - Leitura do projeto

A aplicacao deve interpretar automaticamente os elementos presentes no modelo Revit e extrair os quantitativos disponiveis.

### RF05 - Complementacao por Inteligencia Artificial

A IA deve complementar automaticamente materiais e insumos ausentes no projeto sempre que identificar sua necessidade.

### RF06 - Justificativa das inferencias

Todo item criado pela IA deve apresentar justificativa, origem da informacao e nivel de confianca. O usuario pode aceitar, editar ou remover cada sugestao.

### RF07 - Organizacao automatica das compras

Os materiais devem ser agrupados automaticamente nas categorias de compra da obra.

### RF08 - Configuracao de fornecedores

O usuario pode cadastrar e habilitar os fornecedores usados durante as pesquisas de precos.

## Estrutura

```text
obra-barata-project/
+-- backend/                  # Backend FastAPI
+-- cloudflare/               # Configuracao opcional de Cloudflare Tunnel
+-- frontend/                 # Frontend React/Vite
+-- nginx/                    # Proxy Nginx
+-- docker-compose-dev.yml
+-- docker-compose-test.yml
```

## Uso Local

Copie `.env.example` para `.env` e preencha apenas valores locais:

```bash
cp .env.example .env
```

Ambiente de desenvolvimento:

```bash
docker compose -f docker-compose-dev.yml up
```

Ambiente local com tunnel HTTPS:

```bash
docker compose -f docker-compose-test.yml up
```

## Seguranca

Nao publique o arquivo `.env`, tokens de tunnel, chaves de API, certificados privados, logs ou arquivos gerados em `data/`.

## Governanca de IA

As diretrizes de uso de IA, rastreabilidade, revisao humana e criterios de confianca estao documentadas em `README_GOVERNANCA_IA.md`.

## Licenca

Distribuido sob a licenca MIT. Veja `LICENSE`.
