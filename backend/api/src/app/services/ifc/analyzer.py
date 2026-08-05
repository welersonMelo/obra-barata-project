"""LLM-backed IFC material analysis."""

from typing import Any
import json

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.models.materials import ListaMateriaisObra
from app.services.ifc import prompts
from app.services.ifc.llm_client import build_openai_chat_model


def _structured_material_model(model: BaseChatModel):
    try:
        return model.with_structured_output(
            ListaMateriaisObra,
            method="json_schema",
            strict=True,
        )
    except TypeError:
        return model.with_structured_output(ListaMateriaisObra)


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

        model = _structured_material_model(self.chat_model or build_openai_chat_model())
        payload = {
            "build_digest_result": build_digest_result,
            "lista_base": lista_base.model_dump(mode="json"),
        }
        raw = await model.ainvoke(
            [
                SystemMessage(content=prompts.MATERIAL_LIST_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        "Preencha a ListaMateriaisObra a partir deste JSON:\n"
                        + json.dumps(payload, ensure_ascii=False, indent=2)
                    ),
                ),
            ],
        )
        return ListaMateriaisObra.model_validate(raw)

    async def estimate_quantities(
        self,
        lista_materiais: ListaMateriaisObra,
        spatial_data: dict[str, Any],
        build_digest_result: dict[str, Any],
    ) -> ListaMateriaisObra:
        """Estimate quantities for an already generated material list."""

        model = _structured_material_model(self.chat_model or build_openai_chat_model())
        payload = {
            "lista_materiais": lista_materiais.model_dump(mode="json"),
            "dados_espaciais_ifc": spatial_data,
            "build_digest_result": build_digest_result,
        }
        raw = await model.ainvoke(
            [
                SystemMessage(content=prompts.QUANTITY_SYSTEM_PROMPT),
                HumanMessage(
                    content=(
                        "Preencha as quantidades da ListaMateriaisObra usando estes dados:\n"
                        + json.dumps(payload, ensure_ascii=False, indent=2)
                    ),
                ),
            ],
        )
        return ListaMateriaisObra.model_validate(raw)
