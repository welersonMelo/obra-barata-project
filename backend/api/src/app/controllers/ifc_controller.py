"""IFC upload and analysis endpoints."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from openai import APITimeoutError

from app.models.ifc import AnalyzeIfcRequest, IfcUploadResponse
from app.models.materials import ListaMateriaisObra
from app.repositories.ifc_repository import IfcRecordNotFoundError
from app.services.ifc.extractor import IfcExtractionError
from app.services.ifc.llm_client import OpenAIConfigurationError
from app.services.ifc.service import IfcService


router = APIRouter(tags=["IFC"])


def get_ifc_service() -> IfcService:
    """Dependency provider for IFC service."""

    return IfcService()


@router.post("/upload_ifc", response_model=IfcUploadResponse)
async def upload_ifc(
    file: UploadFile = File(...),
    service: IfcService = Depends(get_ifc_service),
) -> IfcUploadResponse:
    """Upload an IFC file and return its general extracted information."""

    try:
        return await service.upload_ifc(file)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except IfcExtractionError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


@router.post("/analisar_ifc", response_model=ListaMateriaisObra)
async def analisar_ifc(
    payload: AnalyzeIfcRequest,
    service: IfcService = Depends(get_ifc_service),
) -> ListaMateriaisObra:
    """Run the IFC material analysis sequence for a previously uploaded IFC."""

    try:
        return await service.analyze_ifc(payload.ifc_id)
    except IfcRecordNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
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
                "A analise por IA demorou mais que o limite configurado. "
                "Tente novamente ou aumente LLM_REQUEST_TIMEOUT_SECONDS."
            ),
        ) from exc
