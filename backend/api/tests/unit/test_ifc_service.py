from app.models.materials import AreaMateriaisObra, ListaMateriaisObra, MaterialObra
from app.services.ifc.service import remove_zero_quantity_materials


def test_remove_zero_quantity_materials_keeps_null_and_positive_quantities():
    lista = ListaMateriaisObra(
        areas=[
            AreaMateriaisObra(
                area="Alvenaria",
                materiais=[
                    MaterialObra(
                        nome="Unidades de alvenaria de concreto",
                        quantidade=0,
                        medida="un",
                    ),
                    MaterialObra(
                        nome="Argamassa pendente",
                        quantidade=None,
                        medida="saco 20 kg",
                    ),
                    MaterialObra(
                        nome="Bloco quantificado",
                        quantidade=12,
                        medida="un",
                    ),
                ],
            )
        ],
    )

    result = remove_zero_quantity_materials(lista)

    assert [material.nome for material in result.areas[0].materiais] == [
        "Argamassa pendente",
        "Bloco quantificado",
    ]
