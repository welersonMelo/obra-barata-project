"""Supplier pricing endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from openai import APITimeoutError

from app.models.materials import ListaMateriaisObra
from app.services.ifc.llm_client import OpenAIConfigurationError
from app.services.pricing.request_logging import (
    create_pricing_request_log_file,
    ensure_pricing_request_log_handler,
    pricing_request_log_context,
)
from app.services.pricing.service import PricingService


router = APIRouter(tags=["Precos"])
logger = logging.getLogger(__name__)
ensure_pricing_request_log_handler()


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

    log_path = create_pricing_request_log_file()
    materiais_count = len(payload.materiais)
    try:
        with pricing_request_log_context(log_path):
            logger.info(
                "buscar_fornecedores_request_started log_file=%s areas=%s materiais=%s "
                "max_fornecedores_por_material=%s max_materiais_processados=%s "
                "use_serper_fallback=%s",
                log_path,
                len(payload.areas),
                materiais_count,
                max_materials,
                max_materiais_processados,
                use_serper_fallback,
            )
            result = await service.fill_suppliers(
                lista_materiais=payload,
                max_fornecedores_por_material=max_materials,
                max_materiais_processados=max_materiais_processados,
                use_serper_fallback=use_serper_fallback,
            )
            logger.info(
                "buscar_fornecedores_request_finished log_file=%s areas=%s materiais=%s",
                log_path,
                len(result.areas),
                len(result.materiais),
            )
            return result
    except ValueError as exc:
        with pricing_request_log_context(log_path):
            logger.exception(
                "buscar_fornecedores_request_failed status_code=%s log_file=%s",
                status.HTTP_400_BAD_REQUEST,
                log_path,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except OpenAIConfigurationError as exc:
        with pricing_request_log_context(log_path):
            logger.exception(
                "buscar_fornecedores_request_failed status_code=%s log_file=%s",
                status.HTTP_503_SERVICE_UNAVAILABLE,
                log_path,
            )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except APITimeoutError as exc:
        with pricing_request_log_context(log_path):
            logger.exception(
                "buscar_fornecedores_request_failed status_code=%s log_file=%s",
                status.HTTP_504_GATEWAY_TIMEOUT,
                log_path,
            )
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=(
                "A busca de fornecedores por IA demorou mais que o limite configurado. "
                "Tente novamente ou aumente LLM_REQUEST_TIMEOUT_SECONDS."
            ),
        ) from exc
