"""Material template loading."""

from pathlib import Path
import json

from app.models.materials import ListaMateriaisObra


def load_material_template() -> ListaMateriaisObra:
    """Load the base material template shipped with the API package."""

    template_path = (
        Path(__file__).resolve().parent
        / "templates"
        / "IFC_construction_details.json"
    )
    payload = json.loads(template_path.read_text(encoding="utf-8"))
    return ListaMateriaisObra.model_validate(payload)
