import asyncio

from app.models.materials import AreaMateriaisObra, ListaMateriaisObra, MaterialObra
from app.services.pricing.service import PricingService
from app.services.pricing.suppliers import SupplierSearchService


class FakePricingAgent:
    def __init__(self):
        self.calls = []

    async def fill_suppliers(
        self,
        lista_materiais,
        max_fornecedores_por_material=3,
        max_materiais_processados=None,
        use_serper_fallback=False,
    ):
        self.calls.append(
            {
                "max_fornecedores_por_material": max_fornecedores_por_material,
                "max_materiais_processados": max_materiais_processados,
                "use_serper_fallback": use_serper_fallback,
            }
        )
        updated_area = lista_materiais.areas[0].model_copy(
            update={
                "materiais": [
                    lista_materiais.areas[0].materiais[0].model_copy(
                        update={"fornecedor": "Loja via ReAct"}
                    )
                ]
            }
        )
        return lista_materiais.model_copy(update={"areas": [updated_area]})


class FakeProvider:
    def __init__(self, name):
        self.name = name

    async def search(self, *args, **kwargs):
        return []


class RecordingProvider(FakeProvider):
    def __init__(self, name):
        super().__init__(name)
        self.calls = []

    async def search(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return []


def _lista_quantificada():
    return ListaMateriaisObra(
        areas=[
            AreaMateriaisObra(
                area="Pintura",
                materiais=[
                    MaterialObra(
                        nome="Tinta acrilica branca",
                        quantidade=30,
                        medida="litros",
                    ),
                ],
            ),
        ],
    )


def test_pricing_service_delegates_to_react_agent():
    agent = FakePricingAgent()
    service = PricingService(agent=agent)

    result = asyncio.run(
        service.fill_suppliers(
            lista_materiais=_lista_quantificada(),
            max_fornecedores_por_material=2,
            max_materiais_processados=1,
            use_serper_fallback=False,
        )
    )

    assert result.areas[0].materiais[0].fornecedor == "Loja via ReAct"
    assert agent.calls == [
        {
            "max_fornecedores_por_material": 2,
            "max_materiais_processados": 1,
            "use_serper_fallback": False,
        }
    ]


def test_supplier_search_service_uses_casa_only_for_relevant_materials():
    service = SupplierSearchService(
        casa_provider=FakeProvider("Casa da Eletricidade"),
        pisolar_provider=FakeProvider("Pisolar"),
        comercial_alianca_provider=FakeProvider("Comercial Alianca"),
        serper_provider=FakeProvider("Serper"),
    )

    pintura_providers = service.providers_for_material(
        "Pintura",
        MaterialObra(nome="Tinta acrilica", medida="litros"),
    )
    eletrica_providers = service.providers_for_material(
        "Instalacoes eletricas",
        MaterialObra(nome="Disjuntor bipolar", medida="unidades"),
    )

    assert [provider.name for provider in pintura_providers] == [
        "Pisolar",
        "Comercial Alianca",
    ]
    assert [provider.name for provider in eletrica_providers] == [
        "Casa da Eletricidade",
        "Pisolar",
        "Comercial Alianca",
    ]


def test_supplier_search_service_uses_prepared_search_text_for_providers():
    pisolar = RecordingProvider("Pisolar")
    comercial_alianca = RecordingProvider("Comercial Alianca")
    service = SupplierSearchService(
        casa_provider=RecordingProvider("Casa da Eletricidade"),
        pisolar_provider=pisolar,
        comercial_alianca_provider=comercial_alianca,
        serper_provider=RecordingProvider("Serper"),
    )

    asyncio.run(
        service.search_material(
            "Pintura",
            MaterialObra(
                nome="Pintura interna (tinta acrilica)",
                descricao="Tinta para paredes internas",
                quantidade=3,
                medida="lata 18 L",
            ),
            use_serper_fallback=False,
        )
    )

    assert pisolar.calls[0]["kwargs"]["product_name"] == "tinta acrilica 18L"
    assert pisolar.calls[0]["kwargs"]["unit"] == ""
    assert pisolar.calls[0]["kwargs"]["quantity"] is None
    assert comercial_alianca.calls[0]["kwargs"]["product_name"] == "tinta acrilica 18L"
