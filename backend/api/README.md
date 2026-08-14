# Obra Barata API

Backend FastAPI do projeto Obra Barata.

## Endpoints principais

- `POST /upload_ifc`: envia um arquivo IFC e retorna o identificador da analise.
- `POST /analisar_ifc`: recebe um `ifc_id` e retorna uma `ListaMateriaisObra` quantificada.
- `POST /buscar_fornecedores`: recebe uma `ListaMateriaisObra` ja quantificada, executa o agente ReAct de precos com tools de fornecedores e retorna o mesmo contrato com `lista_fornecedores`, melhor fornecedor e precos preenchidos.

Exemplo:

```json
{
  "obra": "Casa exemplo",
  "moeda": "BRL",
  "areas": [
    {
      "area": "Pintura",
      "materiais": [
        {
          "nome": "Tinta acrilica branca",
          "quantidade": 30,
          "medida": "litros"
        }
      ]
    }
  ]
}
```

Use `max_materials` como query param em `/buscar_fornecedores` para controlar quantas ofertas entram em `lista_fornecedores` por material.

O endpoint usa `OPENAI_API_KEY` para o agente ReAct. `SERPER_API_KEY` e opcional e habilita a busca Serper quando o fallback estiver ativo.
