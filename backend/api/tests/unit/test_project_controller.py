from fastapi.testclient import TestClient

from app.app import app
from app.controllers.project_controller import get_project_service
from app.database import DatabaseUnavailableError
from app.models.projects import ProjectResponse, UserResponse
from app.repositories.project_repository import ProjectNotFoundError
from app.services.projects.service import InvalidCredentialsError


def _project(**updates) -> ProjectResponse:
    return ProjectResponse(
        id=updates.get("id", "project-1"),
        name=updates.get("name", "Casa"),
        type=updates.get("type", "Residencial"),
        address=updates.get("address", "Centro"),
        areaBuilt=updates.get("areaBuilt", "120 m2"),
        finishProfile=updates.get("finishProfile", "Medio custo"),
        status=updates.get("status", "rascunho"),
        createdAt=updates.get("createdAt", "2026-08-17T00:00:00"),
        updatedAt=updates.get("updatedAt", "2026-08-17T00:00:00"),
        upload=updates.get("upload"),
        materialList=updates.get("materialList"),
        pricedList=updates.get("pricedList"),
        removedMaterialIds=updates.get("removedMaterialIds", []),
    )


class FakeProjectService:
    def login(self, payload):
        return UserResponse(id="user-1", username=payload.username)

    def list_projects(self):
        return [_project()]

    def create_project(self, payload):
        return _project(name=payload.name)

    def get_project(self, project_id):
        return _project(id=project_id)

    def update_project(self, project_id, payload):
        return _project(id=project_id, **payload.model_dump(exclude_unset=True, mode="json"))


class InvalidLoginProjectService(FakeProjectService):
    def login(self, payload):
        raise InvalidCredentialsError("Usuario ou senha invalidos.")


class UnavailableLoginProjectService(FakeProjectService):
    def login(self, payload):
        raise DatabaseUnavailableError("DATABASE_URL nao configurada.")


class UnavailableListProjectService(FakeProjectService):
    def list_projects(self):
        raise DatabaseUnavailableError("DATABASE_URL nao configurada.")


class InvalidCreateProjectService(FakeProjectService):
    def create_project(self, payload):
        raise InvalidCredentialsError("Usuario de teste nao inicializado.")


class MissingGetProjectService(FakeProjectService):
    def get_project(self, project_id):
        raise ProjectNotFoundError("Projeto nao encontrado.")


class UnavailableGetProjectService(FakeProjectService):
    def get_project(self, project_id):
        raise DatabaseUnavailableError("DATABASE_URL nao configurada.")


class MissingUpdateProjectService(FakeProjectService):
    def update_project(self, project_id, payload):
        raise ProjectNotFoundError("Projeto nao encontrado.")


class UnavailableUpdateProjectService(FakeProjectService):
    def update_project(self, project_id, payload):
        raise InvalidCredentialsError("Usuario de teste nao inicializado.")


def _client(service):
    app.dependency_overrides[get_project_service] = lambda: service
    return TestClient(app)


def _clear_overrides():
    app.dependency_overrides.clear()


def test_login_returns_test_user():
    client = _client(FakeProjectService())
    try:
        response = client.post("/auth/login", json={"username": "teste", "password": "teste"})
    finally:
        _clear_overrides()

    assert response.status_code == 200
    assert response.json() == {"id": "user-1", "username": "teste"}


def test_login_returns_unauthorized_for_invalid_credentials():
    client = _client(InvalidLoginProjectService())
    try:
        response = client.post("/auth/login", json={"username": "teste", "password": "errada"})
    finally:
        _clear_overrides()

    assert response.status_code == 401
    assert response.json()["detail"] == "Usuario ou senha invalidos."


def test_login_returns_unavailable_for_database_error():
    client = _client(UnavailableLoginProjectService())
    try:
        response = client.post("/auth/login", json={"username": "teste", "password": "teste"})
    finally:
        _clear_overrides()

    assert response.status_code == 503
    assert response.json()["detail"] == "DATABASE_URL nao configurada."


def test_project_crud_endpoints_return_project_payloads():
    client = _client(FakeProjectService())
    try:
        list_response = client.get("/projects")
        create_response = client.post(
            "/projects",
            json={
                "name": "Obra Nova",
                "type": "Residencial",
                "address": "",
                "areaBuilt": "",
                "finishProfile": "Medio custo",
            },
        )
        get_response = client.get("/projects/project-1")
        update_response = client.patch("/projects/project-1", json={"status": "analisado"})
    finally:
        _clear_overrides()

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == "project-1"
    assert create_response.status_code == 200
    assert create_response.json()["name"] == "Obra Nova"
    assert get_response.status_code == 200
    assert get_response.json()["id"] == "project-1"
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "analisado"


def test_list_projects_returns_unavailable_for_database_error():
    client = _client(UnavailableListProjectService())
    try:
        response = client.get("/projects")
    finally:
        _clear_overrides()

    assert response.status_code == 503
    assert response.json()["detail"] == "DATABASE_URL nao configurada."


def test_create_project_returns_unavailable_for_missing_test_user():
    client = _client(InvalidCreateProjectService())
    try:
        response = client.post("/projects", json={"name": "Obra Nova"})
    finally:
        _clear_overrides()

    assert response.status_code == 503
    assert response.json()["detail"] == "Usuario de teste nao inicializado."


def test_get_project_returns_not_found():
    client = _client(MissingGetProjectService())
    try:
        response = client.get("/projects/missing")
    finally:
        _clear_overrides()

    assert response.status_code == 404
    assert response.json()["detail"] == "Projeto nao encontrado."


def test_get_project_returns_unavailable_for_database_error():
    client = _client(UnavailableGetProjectService())
    try:
        response = client.get("/projects/project-1")
    finally:
        _clear_overrides()

    assert response.status_code == 503
    assert response.json()["detail"] == "DATABASE_URL nao configurada."


def test_update_project_returns_not_found():
    client = _client(MissingUpdateProjectService())
    try:
        response = client.patch("/projects/missing", json={"status": "analisado"})
    finally:
        _clear_overrides()

    assert response.status_code == 404
    assert response.json()["detail"] == "Projeto nao encontrado."


def test_update_project_returns_unavailable_for_missing_test_user():
    client = _client(UnavailableUpdateProjectService())
    try:
        response = client.patch("/projects/project-1", json={"status": "analisado"})
    finally:
        _clear_overrides()

    assert response.status_code == 503
    assert response.json()["detail"] == "Usuario de teste nao inicializado."
