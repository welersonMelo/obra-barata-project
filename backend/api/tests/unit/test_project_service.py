import pytest

from app.database import password_hash
from app.models.projects import LoginRequest, ProjectCreate, ProjectResponse, ProjectUpdate
from app.services.projects.service import InvalidCredentialsError, ProjectService


TEST_USER_ID = "00000000-0000-0000-0000-000000000001"


def _project() -> ProjectResponse:
    return ProjectResponse(
        id="project-1",
        name="Casa",
        type="Residencial",
        address="Centro",
        areaBuilt="120 m2",
        finishProfile="Medio custo",
        status="rascunho",
        createdAt="2026-08-17T00:00:00",
        updatedAt="2026-08-17T00:00:00",
    )


class FakeProjectRepository:
    def __init__(self, user=None):
        self.user = user or {
            "id": TEST_USER_ID,
            "username": "teste",
            "password_hash": password_hash("teste"),
        }
        self.calls = []

    def get_user_by_username(self, username):
        self.calls.append(("get_user_by_username", username))
        return self.user if username == "teste" else None

    def list_projects(self, user_id):
        self.calls.append(("list_projects", user_id))
        return [_project()]

    def get_project(self, user_id, project_id):
        self.calls.append(("get_project", user_id, project_id))
        return _project()

    def create_project(self, user_id, payload):
        self.calls.append(("create_project", user_id, payload))
        return _project().model_copy(update={"name": payload.name})

    def update_project(self, user_id, project_id, updates):
        self.calls.append(("update_project", user_id, project_id, updates))
        return _project().model_copy(update=updates)


def test_login_accepts_single_test_user():
    service = ProjectService(repository=FakeProjectRepository())

    response = service.login(LoginRequest(username="teste", password="teste"))

    assert response.id == TEST_USER_ID
    assert response.username == "teste"


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("outro", "teste"),
        ("teste", "errada"),
    ],
)
def test_login_rejects_any_other_credentials(username, password):
    service = ProjectService(repository=FakeProjectRepository())

    with pytest.raises(InvalidCredentialsError):
        service.login(LoginRequest(username=username, password=password))


def test_login_rejects_missing_seeded_user():
    service = ProjectService(repository=FakeProjectRepository(user=None))
    service.repository.user = None

    with pytest.raises(InvalidCredentialsError):
        service.login(LoginRequest(username="teste", password="teste"))


def test_project_methods_use_test_user():
    repository = FakeProjectRepository()
    service = ProjectService(repository=repository)

    assert service.list_projects()[0].id == "project-1"
    assert service.get_project("project-1").id == "project-1"
    assert service.create_project(ProjectCreate(name="Obra")).name == "Obra"
    assert service.update_project("project-1", ProjectUpdate(status="analisado")).status == "analisado"

    assert ("list_projects", TEST_USER_ID) in repository.calls
    assert ("get_project", TEST_USER_ID, "project-1") in repository.calls
    assert repository.calls[-1] == (
        "update_project",
        TEST_USER_ID,
        "project-1",
        {"status": "analisado"},
    )
