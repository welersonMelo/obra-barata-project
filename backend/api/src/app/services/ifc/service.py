"""Application service for IFC upload and analysis."""

from fastapi import UploadFile

from app.models.ifc import IfcRecord, IfcUploadResponse
from app.models.materials import ListaMateriaisObra
from app.repositories.ifc_repository import IfcRepository
from app.services.ifc.analyzer import IfcMaterialAnalyzer
from app.services.ifc.extractor import build_digest, extract_spatial_data, open_ifc
from app.services.ifc.material_template import load_material_template


class IfcService:
    """Coordinate IFC storage, extraction, and material analysis."""

    def __init__(
        self,
        repository: IfcRepository | None = None,
        analyzer: IfcMaterialAnalyzer | None = None,
    ) -> None:
        self.repository = repository or IfcRepository()
        self.analyzer = analyzer or IfcMaterialAnalyzer()

    async def upload_ifc(self, upload: UploadFile) -> IfcUploadResponse:
        """Store an uploaded IFC and return the extracted general information."""

        ifc_id = self.repository.create_ifc_id()
        content = await upload.read()
        if not content:
            raise ValueError("Uploaded IFC file is empty.")

        ifc_path = self.repository.save_ifc_bytes(
            ifc_id=ifc_id,
            filename=upload.filename or "model.ifc",
            content=content,
        )
        ifc_file = open_ifc(ifc_path)
        digest = build_digest(ifc_file)
        spatial_data = extract_spatial_data(ifc_file)
        record = IfcRecord(
            ifc_id=ifc_id,
            filename=upload.filename or "model.ifc",
            ifc_path=ifc_path,
            digest=digest,
            spatial_data=spatial_data,
        )
        self.repository.save_record(record)
        return record.to_upload_response()

    async def analyze_ifc(self, ifc_id: str) -> ListaMateriaisObra:
        """Analyze a previously uploaded IFC and return a quantified material list."""

        record = self.repository.get_record(ifc_id)
        lista_base = load_material_template()
        lista_materiais = await self.analyzer.generate_material_list(
            build_digest_result=record.digest,
            lista_base=lista_base,
        )
        return await self.analyzer.estimate_quantities(
            lista_materiais=lista_materiais,
            spatial_data=record.spatial_data,
            build_digest_result=record.digest,
        )
