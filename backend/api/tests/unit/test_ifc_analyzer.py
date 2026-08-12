import asyncio
import json

from app.models.materials import AreaMateriaisObra, ListaMateriaisObra, MaterialObra
from app.services.ifc import prompts
from app.services.ifc.analyzer import (
    IfcMaterialAnalyzer,
    _merge_material_lists,
    _prompt_json,
)


def test_prompt_json_compacts_payload_without_changing_data():
    payload = {
        "build_digest_result": {"materiais": ["Concreto", "Aco"]},
        "lista_base": {"areas": []},
    }

    content = _prompt_json(payload)

    assert json.loads(content) == payload
    assert "\n" not in content
    assert ": " not in content


def test_prompt_json_clips_oversized_payload(monkeypatch):
    from app.settings import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "LLM_MAX_CONTENT_CHARS", 20)

    content = _prompt_json({"texto": "x" * 100})

    assert json.loads(content) == {
        "conteudo_truncado": True,
        "limite_caracteres": 20,
        "conteudo_json_prefixo": '{"texto":"xxxxxxxxxx',
    }


def test_merge_material_lists_combines_areas_and_deduplicates_references():
    first = ListaMateriaisObra(
        observacoes="obs",
        areas=[
            AreaMateriaisObra(
                area="Alvenaria",
                materiais=[
                    MaterialObra(
                        nome="Bloco de concreto",
                        medida="un",
                        referencias_ifc=["IfcWall #1"],
                    ),
                ],
            ),
        ],
    )
    second = ListaMateriaisObra(
        areas=[
            AreaMateriaisObra(
                area="Alvenaria",
                materiais=[
                    MaterialObra(
                        nome="bloco de concreto",
                        medida="un",
                        referencias_ifc=["IfcWall #2"],
                    ),
                ],
            ),
            AreaMateriaisObra(
                area="Cobertura",
                materiais=[MaterialObra(nome="Telha ceramica", medida="un")],
            ),
        ],
    )

    merged = _merge_material_lists([first, second])

    assert merged.observacoes == "obs"
    assert [area.area for area in merged.areas] == ["Alvenaria", "Cobertura"]
    assert len(merged.areas[0].materiais) == 1
    assert merged.areas[0].materiais[0].referencias_ifc == [
        "IfcWall #1",
        "IfcWall #2",
    ]


class FakeStructuredMaterialModel:
    def __init__(self):
        self.calls = []

    async def ainvoke(self, messages):
        self.calls.append(messages)
        payload = json.loads(messages[1].content.split("\n", 1)[1])
        slug = payload["bloco"]["slug"]
        area = payload["bloco"]["areas_esperadas"][0]
        return ListaMateriaisObra(
            observacoes="lista parcial",
            areas=[
                AreaMateriaisObra(
                    area=area,
                    materiais=[
                        MaterialObra(
                            nome=f"Material {slug}",
                            medida="un",
                            origem="ia",
                            referencias_ifc=[slug],
                        ),
                    ],
                ),
            ],
        ).model_dump(mode="json")


class FakeChatModel:
    def __init__(self):
        self.structured = FakeStructuredMaterialModel()
        self.structured_output_kwargs = None

    def with_structured_output(self, *_args, **kwargs):
        self.structured_output_kwargs = kwargs
        return self.structured


def test_generate_material_list_runs_one_call_per_prompt_block():
    chat_model = FakeChatModel()
    analyzer = IfcMaterialAnalyzer(chat_model=chat_model)
    lista_base = ListaMateriaisObra(
        areas=[
            AreaMateriaisObra(
                area="Alvenaria",
                materiais=[MaterialObra(nome="Bloco base", medida="un")],
            ),
            AreaMateriaisObra(
                area="Instalacoes hidraulicas",
                materiais=[MaterialObra(nome="Tubo base", medida="barra 6 m")],
            ),
        ],
    )

    result = asyncio.run(
        analyzer.generate_material_list(
            build_digest_result={"materiais": ["Concreto"]},
            lista_base=lista_base,
        ),
    )

    assert chat_model.structured_output_kwargs == {
        "method": "json_schema",
        "strict": True,
    }
    assert len(chat_model.structured.calls) == len(prompts.MATERIAL_LIST_PROMPT_BLOCKS)
    assert [area.area for area in result.areas] == [
        block["areas_lista_base"][0] for block in prompts.MATERIAL_LIST_PROMPT_BLOCKS
    ]
    assert [material.nome for material in result.materiais] == [
        f"Material {block['slug']}" for block in prompts.MATERIAL_LIST_PROMPT_BLOCKS
    ]
