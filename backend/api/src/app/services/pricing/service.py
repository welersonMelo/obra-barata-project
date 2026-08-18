"""Application service for supplier pricing."""

from typing import Protocol

from app.models.materials import ListaMateriaisObra


class SupplierPricingAgent(Protocol):
    """Agent contract used by PricingService."""

    async def fill_suppliers(
        self,
        lista_materiais: ListaMateriaisObra,
        max_fornecedores_por_material: int = 3,
        max_materiais_processados: int | None = None,
        use_serper_fallback: bool = False,
    ) -> ListaMateriaisObra:
        """Fill supplier offers for a quantified material list."""


class PricingService:
    """Application entry point for ReAct supplier-pricing."""

    def __init__(
        self,
        agent: SupplierPricingAgent | None = None,
    ) -> None:
        self.agent = agent

    async def fill_suppliers(
        self,
        lista_materiais: ListaMateriaisObra,
        max_fornecedores_por_material: int = 3,
        max_materiais_processados: int | None = None,
        use_serper_fallback: bool = False,
    ) -> ListaMateriaisObra:
        """Run the supplier-pricing ReAct agent."""

        agent = self.agent
        if agent is None:  # pragma: no cover - integration path
            from app.services.pricing.agent import SupplierPricingReActAgent

            agent = SupplierPricingReActAgent()
        return await agent.fill_suppliers(
            lista_materiais=lista_materiais,
            max_fornecedores_por_material=max_fornecedores_por_material,
            max_materiais_processados=max_materiais_processados,
            use_serper_fallback=use_serper_fallback,
        )
