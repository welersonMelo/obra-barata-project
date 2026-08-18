"""Authentication and project persistence endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.database import DatabaseUnavailableError
from app.models.projects import LoginRequest, ProjectCreate, ProjectResponse, ProjectUpdate, UserResponse
from app.repositories.project_repository import ProjectNotFoundError
from app.services.projects.service import InvalidCredentialsError, ProjectService


router = APIRouter(tags=["Projetos"])


def get_project_service() -> ProjectService:
    """Dependency provider for project service."""

    return ProjectService()


@router.post("/auth/login", response_model=UserResponse)
def login(
    payload: LoginRequest,
    service: ProjectService = Depends(get_project_service),
) -> UserResponse:
    """Validate the single test user."""

    try:
        return service.login(payload)
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc
    except DatabaseUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects(
    service: ProjectService = Depends(get_project_service),
) -> list[ProjectResponse]:
    """List persisted projects for the test user."""

    try:
        return service.list_projects()
    except (InvalidCredentialsError, DatabaseUnavailableError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.post("/projects", response_model=ProjectResponse)
def create_project(
    payload: ProjectCreate,
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """Create a persisted project."""

    try:
        return service.create_project(payload)
    except (InvalidCredentialsError, DatabaseUnavailableError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """Return one persisted project."""

    try:
        return service.get_project(project_id)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (InvalidCredentialsError, DatabaseUnavailableError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


@router.patch("/projects/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    payload: ProjectUpdate,
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """Persist generated project state."""

    try:
        return service.update_project(project_id, payload)
    except ProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (InvalidCredentialsError, DatabaseUnavailableError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
