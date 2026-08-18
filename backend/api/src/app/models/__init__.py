"""Data models for the application."""

from app.models.ifc import AnalyzeIfcRequest, IfcRecord, IfcUploadResponse
from app.models.materials import (
    AreaMateriaisObra,
    AreaObra,
    ListaMateriaisObra,
    MaterialObra,
    OfertaFornecedor,
    OrigemMaterial,
    PerfilProduto,
)

__all__ = [
    "AnalyzeIfcRequest",
    "AreaMateriaisObra",
    "AreaObra",
    "IfcRecord",
    "IfcUploadResponse",
    "ListaMateriaisObra",
    "MaterialObra",
    "OfertaFornecedor",
    "OrigemMaterial",
    "PerfilProduto",
]
