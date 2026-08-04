# README Governanca IA

## Objetivo

Este documento registra a governanca de IA da solucao Obra Barata para a primeira versao do produto. Ele consolida a descricao funcional recebida para a aplicacao: uma plataforma web que transforma um arquivo Revit em um planejamento inteligente de compras para obras residenciais de pequeno e medio porte.

A IA deve atuar como apoio ao levantamento e qualificacao de materiais, nao como decisora autonoma de compra. O usuario permanece responsavel por revisar, aceitar, editar ou remover as sugestoes antes da geracao do planejamento de compras.

## Escopo da Primeira Versao

A primeira versao tem como objetivo reduzir drasticamente o tempo gasto para levantar materiais, pesquisar precos e montar um orcamento de compras confiavel.

Fora do escopo inicial:

- substituir um ERP de construcao civil;
- controlar toda a execucao da obra;
- realizar compras automaticamente em nome do cliente;
- dividir a compra de um mesmo material entre varios fornecedores.

A plataforma apenas sugere fornecedores, produtos, quantidades e precos. A compra continua sendo realizada pelo cliente diretamente na loja fisica ou online.

## Papel da IA na Solucao

O fluxo principal da aplicacao comeca pelo upload de um arquivo Revit. O modelo nao precisa estar completamente detalhado, pois a IA interpreta o projeto e complementa materiais, insumos e consumiveis que normalmente nao aparecem modelados.

Exemplos de itens que podem ser inferidos:

- argamassas;
- rejuntes;
- impermeabilizantes;
- fixadores;
- parafusos;
- perdas de materiais;
- insumos de instalacao;
- demais componentes necessarios para execucao da obra.

Toda inclusao automatica deve ser tratada como estimativa e nunca como verdade final. A governanca da aplicacao deve tornar essa diferenca visivel ao usuario.

## Principios de Governanca

### Transparencia

Todo item sugerido pela IA deve ser identificado como estimativa. A interface e os dados persistidos devem diferenciar claramente itens extraidos do modelo Revit de itens complementados automaticamente.

### Justificabilidade

Cada sugestao da IA deve apresentar uma justificativa explicando por que o item foi sugerido. A justificativa deve ser compreensivel para o usuario final e relacionada ao contexto do projeto.

### Rastreabilidade

Cada item inferido deve registrar sua origem, como extracao direta do Revit, inferencia por IA, edicao manual do usuario ou pesquisa de fornecedor.

### Confianca explicita

Cada sugestao da IA deve apresentar um indicador de confianca. Esse indicador ajuda o usuario a priorizar revisoes e entender quais itens exigem maior cuidado.

### Revisao humana

O usuario deve poder aceitar, editar ou remover qualquer sugestao antes da geracao do planejamento de compras. A versao final do planejamento deve refletir escolhas confirmadas pelo usuario.

### Controle manual

Mesmo apos a pesquisa automatica de precos, o usuario deve poder alterar fornecedor, preco, descricao, quantidade, perfil do produto e condicoes de pagamento.

## Dados e Informacoes Tratadas

A solucao trabalha com os seguintes grupos de dados:

- dados do usuario e autenticacao;
- dados basicos do projeto/obra;
- arquivo Revit enviado;
- elementos e quantitativos extraidos do modelo;
- materiais e insumos inferidos por IA;
- justificativas, origens e niveis de confianca;
- fornecedores configurados pelo usuario;
- resultados de pesquisa de precos;
- escolhas finais de fornecedor e produto;
- condicoes de pagamento a vista e a prazo;
- resumo consolidado por categoria e fornecedor.

## Fluxo Governado de Dados

1. O usuario cadastra ou acessa sua conta.
2. O usuario cadastra um projeto com informacoes basicas da obra.
3. O usuario envia um arquivo Revit.
4. A aplicacao interpreta o modelo e extrai os quantitativos disponiveis.
5. A IA identifica materiais e insumos ausentes que podem ser necessarios.
6. Cada sugestao gerada pela IA recebe justificativa, origem e nivel de confianca.
7. O usuario revisa as sugestoes e pode aceitar, editar ou remover itens.
8. Os materiais consolidados sao organizados nas categorias de compra da obra.
9. A aplicacao pesquisa precos nos fornecedores habilitados pelo usuario.
10. O usuario escolhe ou ajusta fornecedores, precos, descricoes, quantidades e perfis.
11. O usuario informa ou ajusta condicoes de pagamento a vista e a prazo.
12. A aplicacao gera o resumo consolidado de custos e materiais por fornecedor.

## Categorias de Compra

Os materiais devem ser organizados automaticamente nas seguintes categorias:

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

Essa categorizacao facilita revisao, comparacao de custos e planejamento de compras por etapa da obra.

## Pesquisa de Precos

Para cada material consolidado, a plataforma deve realizar pesquisa automatica de precos usando fornecedores previamente configurados pelo usuario.

A pesquisa pode ser hibrida:

- APIs oficiais, quando disponiveis;
- extracao automatica de dados;
- web scraping;
- integracoes equivalentes para fornecedores sem API publica.

Sempre que possivel, cada resultado deve conter fornecedor, descricao do produto, marca, unidade, quantidade, preco unitario, preco total, disponibilidade, data da consulta e link do produto.

## Perfil do Produto

Cada material possui um **Perfil do Produto**, que orienta a pesquisa conforme o padrao de acabamento desejado.

Perfis iniciais:

- Baixo custo
- Medio custo
- Alto custo

O perfil pode ser alterado individualmente por material ou aplicado a uma categoria inteira. Sempre que houver alteracao, a plataforma deve executar nova pesquisa de precos para refletir o padrao escolhido.

## Regras de Compra e Decisao

Cada material deve ser comprado integralmente em apenas um fornecedor. A aplicacao nao deve dividir um mesmo item entre varios estabelecimentos, pois a regra de produto privilegia descontos por volume, simplificacao logistica e a pratica comum em obras residenciais.

A pesquisa automatica nao fecha pedidos nem substitui a decisao do cliente. O usuario pode editar:

- fornecedor;
- preco;
- descricao;
- quantidade;
- perfil do produto;
- pagamento a vista;
- pagamento a prazo;
- valor a vista;
- valor a prazo;
- percentual de desconto a vista.

## Saidas Consolidadas

Ao final do fluxo, a aplicacao deve apresentar:

- custo por categoria;
- total geral a vista;
- total geral a prazo;
- economia obtida no pagamento a vista;
- lista de materiais por fornecedor.

Essas saidas devem ser derivadas dos dados confirmados pelo usuario, mantendo separacao conceitual entre sugestoes automatizadas e decisoes finais.

## Requisitos Funcionais Relacionados a IA

### RF03 - Upload de arquivo Revit

O arquivo Revit e a fonte principal das informacoes do projeto.

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

## Controles Recomendados para Implementacao

- Persistir separadamente itens extraidos do Revit, itens sugeridos pela IA e itens confirmados pelo usuario.
- Registrar data e hora de cada inferencia e pesquisa de preco.
- Guardar o fornecedor consultado e o metodo de consulta usado.
- Exibir alerta visual para itens com baixa confianca.
- Permitir historico de edicoes manuais relevantes.
- Evitar que uma sugestao de IA seja promovida a item final sem revisao ou confirmacao do usuario.
- Reexecutar a pesquisa de precos quando o perfil do produto, fornecedor ou quantidade for alterado.

## Conclusao

A governanca de IA do Obra Barata deve garantir que a automacao acelere o levantamento e a pesquisa de compras sem retirar o controle do usuario. A IA complementa o projeto, explica suas sugestoes e indica confianca; o usuario revisa, ajusta e confirma as decisoes que compoem o planejamento final.
