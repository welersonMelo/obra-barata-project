import pytest

import app.services.pricing.agent as pricing_agent_module
from app.models.materials import AreaMateriaisObra, ListaMateriaisObra, MaterialObra
from app.services.pricing.agent import (
    AI_MARKET_ESTIMATE_ONLY_ITEMS,
    SUPPLIER_REASONING_SYSTEM_PROMPT,
    _apply_supplier_update,
    _is_ai_market_estimate_only_material,
    _material_prompt,
    _tools_without_supplier_store_search,
    preencher_fornecedores_com_reasoning_agent,
)


def test_supplier_prompt_allows_ai_estimate_when_no_supplier_offer_exists():
    assert 'fornecedor="Estimativa IA"' in SUPPLIER_REASONING_SYSTEM_PROMPT
    assert "all relevant supplier/site search tools return no relevant priced offers" in (
        SUPPLIER_REASONING_SYSTEM_PROMPT
    )


def test_supplier_prompt_has_direct_ai_market_estimate_rule_and_reference_table():
    assert "PRECIFICACAO_DIRETA_IA=true" in SUPPLIER_REASONING_SYSTEM_PROMPT
    assert "SINAPI (CAIXA/IBGE" in SUPPLIER_REASONING_SYSTEM_PROMPT


@pytest.mark.parametrize("item_name", AI_MARKET_ESTIMATE_ONLY_ITEMS)
def test_ai_market_estimate_only_materials_skip_store_tools(item_name):
    material = MaterialObra(
        nome=item_name,
        descricao="Item de obra para composicao de orcamento",
        quantidade=2,
        medida="m2",
    )

    assert _is_ai_market_estimate_only_material("Alvenaria", material)


def test_ai_market_estimate_only_match_handles_close_format_variations():
    material = MaterialObra(
        nome="Vidro liso 4 mm",
        descricao="placa transparente comum",
        quantidade=3,
        medida="m2",
    )

    assert _is_ai_market_estimate_only_material("Vidros", material)


def test_ai_market_estimate_only_does_not_match_short_term_inside_other_words():
    material = MaterialObra(
        nome="Haste de aterramento",
        descricao="Componente eletrico",
        quantidade=1,
        medida="un",
    )

    assert not _is_ai_market_estimate_only_material("Instalacoes eletricas", material)


def test_direct_ai_material_prompt_forbids_supplier_search_tools():
    prompt = _material_prompt(
        area_name="Estrutura",
        material=MaterialObra(nome="Concreto, Moldado no local", quantidade=4, medida="m3"),
        force_ai_market_estimate=True,
    )

    assert "PRECIFICACAO_DIRETA_IA=true" in prompt
    assert "Do not call supplier search tools or site/store tools" in prompt
    assert "SINAPI" in prompt


def test_estimate_only_tool_list_removes_store_search_tools():
    class FakeTool:
        def __init__(self, name):
            self.name = name

    tools = [
        FakeTool("prepare_product_search_text_tool"),
        FakeTool("search_supplier_pisolar_tool"),
        FakeTool("calculator_tool"),
        FakeTool("purchase_quantity_tool"),
    ]

    assert [tool.name for tool in _tools_without_supplier_store_search(tools)] == [
        "calculator_tool",
        "purchase_quantity_tool",
    ]


def test_estimate_only_flow_skips_complementary_supplier_tools(monkeypatch):
    class FakeTool:
        def __init__(self, name):
            self.name = name

    built_tool_names = []
    reason_calls = []

    def fake_build_supplier_reasoning_agent(**kwargs):
        built_tool_names.append([tool.name for tool in kwargs["supplier_search_tools"]])
        return {"tools": kwargs["supplier_search_tools"]}

    def fake_reason_about_material_suppliers(**kwargs):
        reason_calls.append(kwargs)
        return {
            "fornecedor": "Estimativa IA",
            "lista_fornecedores": [
                {
                    "fornecedor": "Estimativa IA",
                    "descricao": "Preco medio SINAPI para concreto moldado no local",
                    "unidade": "m3",
                    "quantidade": 2,
                    "valor_unitario": 650,
                    "valor_total": 1300,
                    "preco_a_vista": 1300,
                    "preco_a_prazo": 1300,
                    "num_parcelas": 1,
                    "disponibilidade": "Estimativa de preco medio gerada por IA.",
                    "data_consulta": "2026-08-18",
                }
            ],
            "justificativa": "Estimativa direta pela tabela SINAPI.",
        }

    def fail_complementary_supplier_search(**_kwargs):
        raise AssertionError("Fornecedor de loja nao deve ser chamado.")

    monkeypatch.setattr(
        pricing_agent_module,
        "build_supplier_reasoning_agent",
        fake_build_supplier_reasoning_agent,
    )
    monkeypatch.setattr(
        pricing_agent_module,
        "reason_about_material_suppliers",
        fake_reason_about_material_suppliers,
    )
    monkeypatch.setattr(
        pricing_agent_module,
        "_missing_relevant_supplier_tool_offers",
        fail_complementary_supplier_search,
    )
    lista = ListaMateriaisObra(
        areas=[
            AreaMateriaisObra(
                area="Estrutura",
                materiais=[
                    MaterialObra(
                        nome="Concreto, Moldado no local",
                        quantidade=2,
                        medida="m3",
                    )
                ],
            )
        ]
    )

    result = preencher_fornecedores_com_reasoning_agent(
        lista_materiais=lista,
        reasoning_llm=object(),
        supplier_search_tools=[
            FakeTool("search_supplier_pisolar_tool"),
            FakeTool("calculator_tool"),
        ],
    )

    assert built_tool_names == [
        ["search_supplier_pisolar_tool", "calculator_tool"],
        ["calculator_tool"],
    ]
    assert reason_calls[0]["force_ai_market_estimate"] is True
    assert result.areas[0].materiais[0].fornecedor == "Estimativa IA"


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


def test_apply_supplier_update_discards_pipe_accessory_and_keeps_bar_count():
    material = MaterialObra(
        nome="Tubo PVC soldavel 25 mm",
        quantidade=8,
        medida="barra 6 m",
    )
    update_payload = {
        "lista_fornecedores": [
            {
                "fornecedor": "Grupo Pisolar",
                "descricao": "Abracadeira para Tubo Soldavel 25mm - Tigre",
                "unidade": "barra 6 m",
                "quantidade": 2,
                "valor_unitario": 9.95,
                "valor_total": 19.9,
            },
            {
                "fornecedor": "Grupo Pisolar",
                "descricao": "Cano PVC 25 mm x 6 m Soldavel - Tigre",
                "unidade": "6 m",
                "quantidade": 2,
                "valor_unitario": 28.45,
                "valor_total": 56.9,
            },
        ]
    }

    result = _apply_supplier_update(material, update_payload)

    assert result.fornecedor == "Grupo Pisolar"
    assert len(result.lista_fornecedores) == 1
    assert result.lista_fornecedores[0].descricao == "Cano PVC 25 mm x 6 m Soldavel - Tigre"
    assert result.lista_fornecedores[0].quantidade == 8
    assert result.lista_fornecedores[0].valor_total == 227.6
