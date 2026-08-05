"""Models for IFC upload and analysis endpoints."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeIfcRequest(BaseModel):
    """Request body for IFC analysis."""

    ifc_id: str = Field(min_length=1)


class IfcUploadResponse(BaseModel):
    """Information returned after a successful IFC upload."""

    ifc_id: str
    filename: str
    schema_name: str = Field(alias="schema")
    pavimentos: list[str]
    areas: dict[str, dict[str, Any]]
    materiais: list[str]
    camadas_material: list[dict[str, Any]]


class IfcRecord(BaseModel):
    """Stored IFC processing state."""

    model_config = ConfigDict(extra="forbid")

    ifc_id: str
    filename: str
    ifc_path: Path
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    digest: dict[str, Any]
    spatial_data: dict[str, Any]

    def to_upload_response(self) -> IfcUploadResponse:
        """Build the public upload response from the stored digest."""

        return IfcUploadResponse(
            ifc_id=self.ifc_id,
            filename=self.filename,
            schema=self.digest.get("schema", ""),
            pavimentos=list(self.digest.get("pavimentos", [])),
            areas=dict(self.digest.get("areas", {})),
            materiais=list(self.digest.get("materiais", [])),
            camadas_material=list(self.digest.get("camadas_material", [])),
        )
