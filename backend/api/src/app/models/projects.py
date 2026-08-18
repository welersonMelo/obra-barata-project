"""Pydantic contracts for persisted frontend projects."""

from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.ifc import IfcUploadResponse
from app.models.materials import ListaMateriaisObra, PerfilProduto


class ProjectStatus(StrEnum):
    """Frontend project lifecycle persisted in PostgreSQL."""

    RASCUNHO = "rascunho"
    IFC_ENVIADO = "ifc_enviado"
    ANALISADO = "analisado"
    PRECIFICADO = "precificado"


class LoginRequest(BaseModel):
    """Login payload for the single test user."""

    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class UserResponse(BaseModel):
    """Authenticated user response."""

    id: str
    username: str


class ProjectCreate(BaseModel):
    """Project fields created by the frontend form."""

    name: str = Field(min_length=1)
    type: str = "Residencial"
    address: str = ""
    areaBuilt: str = ""
    finishProfile: PerfilProduto = PerfilProduto.MEDIO_CUSTO


class ProjectUpdate(BaseModel):
    """Partial update for generated project state."""

    name: str | None = None
    type: str | None = None
    address: str | None = None
    areaBuilt: str | None = None
    finishProfile: PerfilProduto | None = None
    status: ProjectStatus | None = None
    upload: IfcUploadResponse | None = None
    materialList: ListaMateriaisObra | None = None
    pricedList: ListaMateriaisObra | None = None
    removedMaterialIds: list[str] | None = None


class ProjectResponse(ProjectCreate):
    """Project payload returned to the React frontend."""

    id: str
    status: ProjectStatus
    createdAt: str
    updatedAt: str
    upload: IfcUploadResponse | None = None
    materialList: ListaMateriaisObra | None = None
    pricedList: ListaMateriaisObra | None = None
    removedMaterialIds: list[str] = Field(default_factory=list)
