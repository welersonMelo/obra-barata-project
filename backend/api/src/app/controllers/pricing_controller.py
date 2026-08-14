"""Supplier pricing endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from openai import APITimeoutError

from app.models.materials import ListaMateriaisObra
from app.services.ifc.llm_client import OpenAIConfigurationError
from app.services.pricing.service import PricingService


router = APIRouter(tags=["Precos"])


def get_pricing_service() -> PricingService:
    """Dependency provider for pricing service."""

    return PricingService()


@router.post("/buscar_fornecedores", response_model=ListaMateriaisObra)
async def buscar_fornecedores(
    payload: ListaMateriaisObra,
    max_materials: int = Query(
        default=3,
        ge=0,
        le=10,
        description="Quantidade maxima de ofertas em lista_fornecedores por material.",
    ),
    max_materiais_processados: int | None = Query(
        default=None,
        ge=1,
        description="Limite opcional de materiais processados na chamada.",
    ),
    use_serper_fallback: bool = Query(
        default=False,
        description="Usar Serper quando fornecedores especificos nao retornarem preco.",
    ),
    service: PricingService = Depends(get_pricing_service),
) -> ListaMateriaisObra:
    """Fill supplier offers for a quantified material list."""

    try:
        return await service.fill_suppliers(
            lista_materiais=payload,
            max_fornecedores_por_material=max_materials,
            max_materiais_processados=max_materiais_processados,
            use_serper_fallback=use_serper_fallback,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except OpenAIConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except APITimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=(
                "A busca de fornecedores por IA demorou mais que o limite configurado. "
                "Tente novamente ou aumente LLM_REQUEST_TIMEOUT_SECONDS."
            ),
        ) from exc
