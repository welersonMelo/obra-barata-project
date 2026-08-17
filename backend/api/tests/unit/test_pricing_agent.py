from app.models.materials import MaterialObra
from app.services.pricing.agent import (
    SUPPLIER_REASONING_SYSTEM_PROMPT,
    _apply_supplier_update,
)


def test_supplier_prompt_allows_ai_estimate_when_no_supplier_offer_exists():
    assert 'fornecedor="Estimativa IA"' in SUPPLIER_REASONING_SYSTEM_PROMPT
    assert "all relevant supplier/site search tools return no relevant priced offers" in (
        SUPPLIER_REASONING_SYSTEM_PROMPT
    )


def test_apply_supplier_update_accepts_ai_estimate_when_it_is_the_only_offer():
    material = MaterialObra(
        nome="Concreto moldado no local",
        descricao="Concreto para laje",
        quantidade=4,
        medida="m3",
    )
    update_payload = {
        "fornecedor": "Estimativa IA",
        "lista_fornecedores": [
            {
                "fornecedor": "Estimativa IA",
                "descricao": "Preco medio estimado de concreto usinado para orcamento",
                "marca": None,
                "unidade": "m3",
                "quantidade": 4,
                "valor_unitario": 650,
                "valor_total": 2600,
                "preco_a_vista": 2600,
                "preco_a_prazo": 2600,
                "num_parcelas": 1,
                "frete": None,
                "disponibilidade": "Estimativa de preco medio gerada por IA.",
                "data_consulta": "2026-08-17",
                "link_produto": None,
            }
        ],
        "justificativa": "Fornecedores consultados nao retornaram cotacao real.",
    }

    result = _apply_supplier_update(material, update_payload)

    assert result.fornecedor == "Estimativa IA"
    assert result.valor_unitario == 650
    assert result.valor_total == 2600
    assert result.lista_fornecedores[0].fornecedor == "Estimativa IA"
    assert "nao retornaram cotacao real" in result.justificativa


def test_apply_supplier_update_discards_ai_estimate_when_real_priced_offer_exists():
    material = MaterialObra(
        nome="Concreto moldado no local",
        quantidade=4,
        medida="m3",
    )
    update_payload = {
        "lista_fornecedores": [
            {
                "fornecedor": "Estimativa IA",
                "descricao": "Preco medio estimado",
                "unidade": "m3",
                "quantidade": 4,
                "valor_unitario": 650,
                "valor_total": 2600,
                "preco_a_vista": 2600,
                "preco_a_prazo": 2600,
                "num_parcelas": 1,
                "disponibilidade": "Estimativa de preco medio gerada por IA.",
                "data_consulta": "2026-08-17",
            },
            {
                "fornecedor": "Fornecedor Real",
                "descricao": "Concreto usinado FCK 25 MPa",
                "unidade": "m3",
                "quantidade": 4,
                "valor_unitario": 700,
                "valor_total": 2800,
                "preco_a_vista": 2800,
                "preco_a_prazo": 2800,
                "num_parcelas": 1,
                "disponibilidade": "Cotacao real encontrada.",
                "data_consulta": "2026-08-17",
                "link_produto": "https://example.com/concreto",
            },
        ],
    }

    result = _apply_supplier_update(material, update_payload)

    assert result.fornecedor == "Fornecedor Real"
    assert [offer.fornecedor for offer in result.lista_fornecedores] == [
        "Fornecedor Real"
    ]
