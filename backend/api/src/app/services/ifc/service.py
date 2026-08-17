"""Application service for IFC upload and analysis."""

import logging

from fastapi import UploadFile

from app.models.ifc import IfcRecord, IfcUploadResponse
from app.models.materials import ListaMateriaisObra
from app.repositories.ifc_repository import IfcRepository
from app.services.ifc.analyzer import IfcMaterialAnalyzer
from app.services.ifc.extractor import build_digest, extract_spatial_data, open_ifc
from app.services.ifc.material_template import load_material_template
from app.services.ifc.progress import StageProgressLogger


logger = logging.getLogger(__name__)


def remove_zero_quantity_materials(
    lista_materiais: ListaMateriaisObra,
) -> ListaMateriaisObra:
    """Remove materials with exact zero quantity from the IFC endpoint result."""

    filtered_areas = []
    for area in lista_materiais.areas:
        filtered_materials = [
            material
            for material in area.materiais
            if material.quantidade is None or material.quantidade != 0
        ]
        filtered_areas.append(area.model_copy(update={"materiais": filtered_materials}))
    return lista_materiais.model_copy(update={"areas": filtered_areas})


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
        progress = StageProgressLogger(
            workflow="upload_ifc",
            logger=logger,
            ifc_id=ifc_id,
            filename=upload.filename or "model.ifc",
        )
        progress.step("ler_upload")
        content = await upload.read()
        if not content:
            raise ValueError("Uploaded IFC file is empty.")

        progress.step("salvar_arquivo", bytes=len(content))
        ifc_path = self.repository.save_ifc_bytes(
            ifc_id=ifc_id,
            filename=upload.filename or "model.ifc",
            content=content,
        )
        progress.step("abrir_ifc")
        ifc_file = open_ifc(ifc_path)
        progress.step("montar_digest")
        digest = build_digest(ifc_file)
        progress.step("extrair_dados_espaciais")
        spatial_data = extract_spatial_data(ifc_file)
        progress.step("salvar_registro")
        record = IfcRecord(
            ifc_id=ifc_id,
            filename=upload.filename or "model.ifc",
            ifc_path=ifc_path,
            digest=digest,
            spatial_data=spatial_data,
        )
        self.repository.save_record(record)
        progress.finish()
        return record.to_upload_response()

    async def analyze_ifc(self, ifc_id: str) -> ListaMateriaisObra:
        """Analyze a previously uploaded IFC and return a quantified material list."""

        progress = StageProgressLogger(
            workflow="analisar_ifc",
            logger=logger,
            ifc_id=ifc_id,
        )
        progress.step("carregar_registro")
        record = self.repository.get_record(ifc_id)
        progress.step("carregar_template_materiais")
        lista_base = load_material_template()
        progress.step("gerar_lista_materiais_ia")
        lista_materiais = await self.analyzer.generate_material_list(
            build_digest_result=record.digest,
            lista_base=lista_base,
        )
        progress.step("estimar_quantidades_ia")
        result = await self.analyzer.estimate_quantities(
            lista_materiais=lista_materiais,
            spatial_data=record.spatial_data,
            build_digest_result=record.digest,
        )
        result = remove_zero_quantity_materials(result)
        progress.finish()
        return result
