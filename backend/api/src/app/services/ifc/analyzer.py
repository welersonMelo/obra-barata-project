"""LLM-backed IFC material analysis."""

import asyncio
import json
import logging
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.models.materials import AreaMateriaisObra, ListaMateriaisObra, MaterialObra
from app.settings import get_settings
from app.services.ifc import prompts
from app.services.ifc.llm_client import build_openai_chat_model
from app.services.ifc.progress import StageProgressLogger


logger = logging.getLogger(__name__)


def _structured_material_model(model: BaseChatModel):
    try:
        return model.with_structured_output(
            ListaMateriaisObra,
            method="json_schema",
            strict=True,
        )
    except TypeError:
        return model.with_structured_output(ListaMateriaisObra)


def _prompt_json(payload: dict[str, Any]) -> str:
    """Serialize LLM input compactly and keep oversized prompts bounded."""

    settings = get_settings()
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(content) <= settings.LLM_MAX_CONTENT_CHARS:
        return content

    clipped_payload = {
        "conteudo_truncado": True,
        "limite_caracteres": settings.LLM_MAX_CONTENT_CHARS,
        "conteudo_json_prefixo": content[: settings.LLM_MAX_CONTENT_CHARS],
    }
    return json.dumps(clipped_payload, ensure_ascii=False, separators=(",", ":"))


def _lista_base_for_block(
    lista_base: ListaMateriaisObra,
    area_names: tuple[str, ...],
) -> ListaMateriaisObra:
    """Keep the base catalog focused on the material block being generated."""

    selected_areas = [area for area in lista_base.areas if area.area in area_names]
    if not selected_areas:
        return lista_base
    return lista_base.model_copy(update={"areas": selected_areas})


def _material_key(material: MaterialObra) -> str:
    return material.nome.strip().casefold()


def _merge_references(
    existing: list[str],
    incoming: list[str],
) -> list[str]:
    references = list(existing)
    for reference in incoming:
        if reference not in references:
            references.append(reference)
    return references


def _merge_observations(partials: list[ListaMateriaisObra]) -> str | None:
    observations = [
        partial.observacoes.strip()
        for partial in partials
        if partial.observacoes and partial.observacoes.strip()
    ]
    unique_observations = list(dict.fromkeys(observations))
    if not unique_observations:
        return None
    return " ".join(unique_observations)


def _merge_material_lists(partials: list[ListaMateriaisObra]) -> ListaMateriaisObra:
    """Join parallel block outputs into the same contract returned previously."""

    if not partials:
        return ListaMateriaisObra(areas=[])

    first = partials[0]
    area_map: dict[str, AreaMateriaisObra] = {}
    material_keys_by_area: dict[str, set[str]] = {}

    for partial in partials:
        for area in partial.areas:
            if area.area not in area_map:
                area_map[area.area] = AreaMateriaisObra(area=area.area, materiais=[])
                material_keys_by_area[area.area] = set()

            area_materials = area_map[area.area].materiais
            seen_keys = material_keys_by_area[area.area]
            for material in area.materiais:
                key = _material_key(material)
                if key not in seen_keys:
                    area_materials.append(material)
                    seen_keys.add(key)
                    continue

                for index, existing in enumerate(area_materials):
                    if _material_key(existing) == key:
                        area_materials[index] = existing.model_copy(
                            update={
                                "referencias_ifc": _merge_references(
                                    existing.referencias_ifc,
                                    material.referencias_ifc,
                                ),
                            },
                        )
                        break

    return ListaMateriaisObra(
        obra=first.obra,
        responsavel=first.responsavel,
        data=first.data,
        moeda=first.moeda,
        observacoes=_merge_observations(partials),
        areas=list(area_map.values()),
    )


class IfcMaterialAnalyzer:
    """Generate and quantify material lists from IFC-derived data."""

    def __init__(self, chat_model: BaseChatModel | None = None) -> None:
        self.chat_model = chat_model

    async def generate_material_list(
        self,
        build_digest_result: dict[str, Any],
        lista_base: ListaMateriaisObra,
    ) -> ListaMateriaisObra:
        """Generate a material list from the IFC digest."""

        progress = StageProgressLogger(
            workflow="gerar_lista_materiais_ia",
            logger=logger,
            blocos=len(prompts.MATERIAL_LIST_PROMPT_BLOCKS),
        )
        progress.step("preparar_modelo_estruturado")
        model = _structured_material_model(self.chat_model or build_openai_chat_model())
        progress.step("executar_blocos_ia")
        partials = await asyncio.gather(
            *(
                self._generate_material_list_block(
                    model=model,
                    block=block,
                    build_digest_result=build_digest_result,
                    lista_base=lista_base,
                )
                for block in prompts.MATERIAL_LIST_PROMPT_BLOCKS
            ),
        )
        progress.step("unir_respostas_blocos")
        result = _merge_material_lists(list(partials))
        progress.finish(areas=len(result.areas), materiais=len(result.materiais))
        return result

    async def _generate_material_list_block(
        self,
        model,
        block: dict[str, Any],
        build_digest_result: dict[str, Any],
        lista_base: ListaMateriaisObra,
    ) -> ListaMateriaisObra:
        """Generate one focused material-list block."""

        progress = StageProgressLogger(
            workflow="gerar_lista_materiais_bloco_ia",
            logger=logger,
            bloco=block["slug"],
            titulo=block["titulo"],
        )
        progress.step("montar_payload")
        block_areas = tuple(block["areas_lista_base"])
        payload = {
            "bloco": {
                "slug": block["slug"],
                "titulo": block["titulo"],
                "areas_esperadas": block_areas,
            },
            "build_digest_result": build_digest_result,
            "lista_base": _lista_base_for_block(
                lista_base,
                block_areas,
            ).model_dump(mode="json"),
        }
        progress.step("chamar_llm_bloco")
        raw = await model.ainvoke(
            [
                SystemMessage(content=block["system_prompt"]),
                HumanMessage(
                    content=(
                        "Preencha somente a parte da ListaMateriaisObra deste bloco. "
                        "Nao inclua materiais fora do escopo do bloco.\n"
                        + _prompt_json(payload)
                    ),
                ),
            ],
        )
        progress.step("validar_resposta_bloco")
        result = ListaMateriaisObra.model_validate(raw)
        progress.finish(areas=len(result.areas), materiais=len(result.materiais))
        return result

    async def estimate_quantities(
        self,
        lista_materiais: ListaMateriaisObra,
        spatial_data: dict[str, Any],
        build_digest_result: dict[str, Any],
    ) -> ListaMateriaisObra:
        """Estimate quantities for an already generated material list."""

        progress = StageProgressLogger(
            workflow="estimar_quantidades_ia",
            logger=logger,
            areas=len(lista_materiais.areas),
            materiais=len(lista_materiais.materiais),
        )
        progress.step("preparar_modelo_estruturado")
        model = _structured_material_model(self.chat_model or build_openai_chat_model())
        progress.step("montar_payload")
        payload = {
            "lista_materiais": lista_materiais.model_dump(mode="json"),
            "dados_espaciais_ifc": spatial_data,
            "build_digest_result": build_digest_result,
        }
        progress.step("chamar_llm_quantidades")
        raw = await model.ainvoke(
            [
                SystemMessage(content=prompts.QUANTITY_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        "Preencha as quantidades da ListaMateriaisObra usando estes dados:\n"
                        + _prompt_json(payload)
                    ),
                ),
            ],
        )
        progress.step("validar_resposta")
        result = ListaMateriaisObra.model_validate(raw)
        progress.finish(
            areas_resultado=len(result.areas),
            materiais_resultado=len(result.materiais),
        )
        return result
