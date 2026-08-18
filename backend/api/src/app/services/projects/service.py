"""Application service for the single-user project store."""

from app.database import password_hash
from app.models.projects import LoginRequest, ProjectCreate, ProjectResponse, ProjectUpdate, UserResponse
from app.repositories.project_repository import ProjectRepository
from app.settings import get_settings


class InvalidCredentialsError(RuntimeError):
    """Raised when the test credentials do not match."""


class ProjectService:
    """Coordinate login and project persistence for the test user."""

    def __init__(self, repository: ProjectRepository | None = None) -> None:
        self.repository = repository or ProjectRepository()

    def login(self, payload: LoginRequest) -> UserResponse:
        settings = get_settings()
        if payload.username != settings.TEST_USERNAME or payload.password != settings.TEST_PASSWORD:
            raise InvalidCredentialsError("Usuario ou senha invalidos.")

        user = self.repository.get_user_by_username(settings.TEST_USERNAME)
        if user is None or user["password_hash"] != password_hash(settings.TEST_PASSWORD):
            raise InvalidCredentialsError("Usuario de teste nao inicializado.")

        return UserResponse(id=str(user["id"]), username=user["username"])

    def _test_user_id(self) -> str:
        settings = get_settings()
        user = self.repository.get_user_by_username(settings.TEST_USERNAME)
        if user is None:
            raise InvalidCredentialsError("Usuario de teste nao inicializado.")
        return str(user["id"])

    def list_projects(self) -> list[ProjectResponse]:
        return self.repository.list_projects(self._test_user_id())

    def get_project(self, project_id: str) -> ProjectResponse:
        return self.repository.get_project(
            user_id=self._test_user_id(),
            project_id=project_id,
        )

    def create_project(self, payload: ProjectCreate) -> ProjectResponse:
        return self.repository.create_project(
            user_id=self._test_user_id(),
            payload=payload,
        )

    def update_project(self, project_id: str, payload: ProjectUpdate) -> ProjectResponse:
        return self.repository.update_project(
            user_id=self._test_user_id(),
            project_id=project_id,
            updates=payload.model_dump(exclude_unset=True, mode="json", by_alias=True),
        )
