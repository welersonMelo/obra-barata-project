"""IFC extraction helpers based on IfcOpenShell."""

import math
from pathlib import Path
from typing import Any

try:
    import ifcopenshell
    import ifcopenshell.geom
except ImportError:  # pragma: no cover - depends on runtime image
    ifcopenshell = None


class IfcExtractionError(RuntimeError):
    """Raised when the IFC file cannot be processed."""


ENTITY_ALIASES = {
    "IfcPipeSegment": ["IfcPipeSegment", "IfcFlowSegment"],
    "IfcPipeFitting": ["IfcPipeFitting", "IfcFlowFitting"],
    "IfcFlowTerminal": ["IfcFlowTerminal"],
    "IfcSwitchingDevice": ["IfcSwitchingDevice", "IfcSwitchDevice"],
}


def open_ifc(path: Path):
    """Open an IFC file with IfcOpenShell."""

    if ifcopenshell is None:
        raise IfcExtractionError("ifcopenshell is not installed.")
    try:
        return ifcopenshell.open(str(path))
    except Exception as exc:
        raise IfcExtractionError(f"Could not open IFC file: {exc}") from exc


def _entity_id(entity) -> int | None:
    try:
        return entity.id()
    except Exception:
        return None


def _entity_name(entity) -> str | None:
    if entity is None:
        return None
    for attr in ("Name", "LongName", "Description"):
        value = getattr(entity, attr, None)
        if value:
            return str(value)
    try:
        return f"{entity.is_a()} #{entity.id()}"
    except Exception:
        return str(entity)


def _entity_is_a(entity, type_name: str) -> bool:
    try:
        return entity.is_a(type_name)
    except Exception:
        return False


def _safe_by_type(ifc_file, entity_name: str) -> list[Any]:
    try:
        return list(ifc_file.by_type(entity_name))
    except Exception:
        return []


def _entity_exists(schema_name: str, entity_name: str) -> bool:
    if ifcopenshell is None:
        return False
    try:
        schema = ifcopenshell.ifcopenshell_wrapper.schema_by_name(schema_name)
        return schema.declaration_by_name(entity_name) is not None
    except Exception:
        return False


def _safe_count(ifc_file, *entity_names: str) -> int:
    total = 0
    for entity_name in entity_names:
        if _entity_exists(ifc_file.schema, entity_name):
            total += len(_safe_by_type(ifc_file, entity_name))
    return total


def _layers_from_material_select(material_select) -> tuple[Any | None, list[Any]]:
    if material_select is None:
        return None, []

    layer_set = material_select
    if _entity_is_a(material_select, "IfcMaterialLayerSetUsage"):
        layer_set = getattr(material_select, "ForLayerSet", None)

    if _entity_is_a(layer_set, "IfcMaterialLayerSet"):
        return layer_set, list(getattr(layer_set, "MaterialLayers", []) or [])

    if _entity_is_a(material_select, "IfcMaterialLayer"):
        return None, [material_select]

    return None, []


def _layer_to_dict(layer) -> dict[str, Any]:
    material = getattr(layer, "Material", None)
    return {
        "id": _entity_id(layer),
        "nome": _entity_name(layer),
        "material": _entity_name(material),
        "material_id": _entity_id(material),
        "espessura": getattr(layer, "LayerThickness", None),
        "categoria": getattr(layer, "Category", None),
        "prioridade": getattr(layer, "Priority", None),
        "ventilada": getattr(layer, "IsVentilated", None),
    }


def _usage_to_dict(material_select) -> dict[str, Any] | None:
    if not _entity_is_a(material_select, "IfcMaterialLayerSetUsage"):
        return None
    return {
        "id": _entity_id(material_select),
        "layer_set_direction": getattr(material_select, "LayerSetDirection", None),
        "direction_sense": getattr(material_select, "DirectionSense", None),
        "offset_from_reference_line": getattr(
            material_select,
            "OffsetFromReferenceLine",
            None,
        ),
    }


def _element_ref(element) -> dict[str, Any]:
    return {
        "id": _entity_id(element),
        "global_id": getattr(element, "GlobalId", None),
        "tipo": element.is_a() if hasattr(element, "is_a") else None,
        "nome": _entity_name(element),
    }


def _safe_value(value) -> Any:
    if hasattr(value, "wrappedValue"):
        return value.wrappedValue
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _vector_subtract(a: tuple[float, float, float], b: tuple[float, float, float]):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _vector_cross(a: tuple[float, float, float], b: tuple[float, float, float]):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _vector_dot(a: tuple[float, float, float], b: tuple[float, float, float]):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _vector_norm(a: tuple[float, float, float]) -> float:
    return math.sqrt(_vector_dot(a, a))


def _round_quantity(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(value, 6)


def _geometry_settings():
    if ifcopenshell is None:
        return None
    try:
        settings = ifcopenshell.geom.settings()
        try:
            settings.set(settings.USE_WORLD_COORDS, True)
        except Exception:
            pass
        return settings
    except Exception:
        return None


def _infer_geometry_quantities(element) -> dict[str, Any]:
    """Infer basic quantities from the generated IfcOpenShell mesh."""

    if ifcopenshell is None or getattr(element, "Representation", None) is None:
        return {}

    settings = _geometry_settings()
    if settings is None:
        return {}

    try:
        shape = ifcopenshell.geom.create_shape(settings, element)
        geometry = shape.geometry
        raw_vertices = list(getattr(geometry, "verts", []) or [])
        raw_faces = list(getattr(geometry, "faces", []) or [])
    except Exception:
        return {}

    if len(raw_vertices) < 9 or len(raw_faces) < 3:
        return {}

    vertices = [
        (
            float(raw_vertices[index]),
            float(raw_vertices[index + 1]),
            float(raw_vertices[index + 2]),
        )
        for index in range(0, len(raw_vertices) - 2, 3)
    ]

    triangle_count = len(raw_faces) // 3
    surface_area = 0.0
    signed_volume = 0.0
    for index in range(0, triangle_count * 3, 3):
        try:
            a = vertices[int(raw_faces[index])]
            b = vertices[int(raw_faces[index + 1])]
            c = vertices[int(raw_faces[index + 2])]
        except (IndexError, ValueError, TypeError):
            continue

        ab = _vector_subtract(b, a)
        ac = _vector_subtract(c, a)
        surface_area += _vector_norm(_vector_cross(ab, ac)) / 2
        signed_volume += _vector_dot(a, _vector_cross(b, c)) / 6

    xs = [vertex[0] for vertex in vertices]
    ys = [vertex[1] for vertex in vertices]
    zs = [vertex[2] for vertex in vertices]
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    dz = max(zs) - min(zs)
    horizontal_dimensions = sorted([dx, dy])
    inferred_volume = abs(signed_volume)
    if inferred_volume <= 1e-9:
        inferred_volume = None

    return {
        "origem": "ifcopenshell.geom",
        "metodo": "mesh_triangulation",
        "observacao": (
            "Valores inferidos pela geometria triangulada quando o IFC nao "
            "fornece IfcElementQuantity direto."
        ),
        "unidade_assumida": "unidade_de_comprimento_do_modelo_ifc",
        "vertices": len(vertices),
        "triangulos": triangle_count,
        "bounding_box": {
            "x": _round_quantity(dx),
            "y": _round_quantity(dy),
            "z": _round_quantity(dz),
            "volume": _round_quantity(dx * dy * dz),
        },
        "valores": {
            "surface_area": _round_quantity(surface_area),
            "volume": _round_quantity(inferred_volume),
            "largest_dimension": _round_quantity(max(dx, dy, dz)),
            "horizontal_length": _round_quantity(horizontal_dimensions[-1]),
            "horizontal_thickness": _round_quantity(horizontal_dimensions[0]),
            "height": _round_quantity(dz),
        },
    }


def _quantity_value_types(quantity_sets: dict[str, Any]) -> set[str]:
    value_types: set[str] = set()
    for quantities in quantity_sets.values():
        if not isinstance(quantities, dict):
            continue
        for quantity in quantities.values():
            if isinstance(quantity, dict) and quantity.get("tipo"):
                value_types.add(str(quantity["tipo"]))
    return value_types


def _quantity_names(quantity_sets: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for quantities in quantity_sets.values():
        if isinstance(quantities, dict):
            names.update(str(quantity_name) for quantity_name in quantities)
    return names


def _has_quantity_name(direct_quantity_names: set[str], aliases: tuple[str, ...]) -> bool:
    normalized_aliases = tuple(
        "".join(char for char in alias.lower() if char.isalnum())
        for alias in aliases
    )
    for quantity_name in direct_quantity_names:
        normalized_name = "".join(
            char for char in quantity_name.lower() if char.isalnum()
        )
        if any(alias in normalized_name for alias in normalized_aliases):
            return True
    return False


def _geometry_quantities_for_missing_direct_values(
    geometry: dict[str, Any],
    direct_value_types: set[str],
    direct_quantity_names: set[str],
) -> dict[str, Any]:
    values = geometry.get("valores", {})
    quantities: dict[str, Any] = {}

    volume = values.get("volume")
    if "VolumeValue" not in direct_value_types and volume is not None:
        quantities["InferredVolume"] = {
            "tipo": "VolumeValue",
            "valor": volume,
            "origem": "geometry",
            "metodo": "volume_assinado_da_malha_triangulada",
        }

    surface_area = values.get("surface_area")
    if "AreaValue" not in direct_value_types and surface_area is not None:
        quantities["InferredSurfaceArea"] = {
            "tipo": "AreaValue",
            "valor": surface_area,
            "origem": "geometry",
            "metodo": "soma_das_areas_dos_triangulos_da_malha",
        }

    for quantity_name, value_key, direct_aliases in (
        ("InferredLength", "horizontal_length", ("length", "comprimento")),
        ("InferredHeight", "height", ("height", "altura")),
        (
            "InferredThickness",
            "horizontal_thickness",
            ("thickness", "width", "espessura", "largura"),
        ),
    ):
        value = values.get(value_key)
        if value is not None and not _has_quantity_name(
            direct_quantity_names,
            direct_aliases,
        ):
            quantities[quantity_name] = {
                "tipo": "LengthValue",
                "valor": value,
                "origem": "geometry",
                "metodo": f"bounding_box_{value_key}",
            }

    return quantities


def extract_layersets(ifc_file) -> list[dict[str, Any]]:
    """Extract material layer sets in a serializable format."""

    layer_sets: dict[Any, dict[str, Any]] = {}

    def add_layer_set(material_select, related_objects=None) -> None:
        layer_set, layers = _layers_from_material_select(material_select)
        if not layers:
            return

        layers_data = [_layer_to_dict(layer) for layer in layers]
        key_entity = layer_set or material_select
        key = _entity_id(key_entity) or f"anon-{len(layer_sets) + 1}"
        if key not in layer_sets:
            layer_sets[key] = {
                "id": _entity_id(layer_set),
                "nome": _entity_name(layer_set) or _entity_name(material_select),
                "tipo_origem": (
                    material_select.is_a()
                    if hasattr(material_select, "is_a")
                    else None
                ),
                "uso": _usage_to_dict(material_select),
                "camadas": layers_data,
                "espessura_total": sum(
                    layer.get("espessura") or 0 for layer in layers_data
                ),
                "aplicado_em": [],
            }

        if related_objects:
            existing = {
                item.get("global_id") or item.get("id")
                for item in layer_sets[key]["aplicado_em"]
            }
            for obj in related_objects:
                obj_data = _element_ref(obj)
                obj_key = obj_data.get("global_id") or obj_data.get("id")
                if obj_key not in existing:
                    layer_sets[key]["aplicado_em"].append(obj_data)
                    existing.add(obj_key)

    for rel in _safe_by_type(ifc_file, "IfcRelAssociatesMaterial"):
        add_layer_set(
            getattr(rel, "RelatingMaterial", None),
            getattr(rel, "RelatedObjects", None),
        )

    for layer_set in _safe_by_type(ifc_file, "IfcMaterialLayerSet"):
        add_layer_set(layer_set)

    return sorted(
        layer_sets.values(),
        key=lambda item: (item.get("nome") or "", item.get("id") or 0),
    )


def build_digest(ifc_file) -> dict[str, Any]:
    """Build a safe digest for IFC2X3 and IFC4 files."""

    def resolve_type(type_name: str) -> str | None:
        aliases = ENTITY_ALIASES.get(type_name, [type_name])
        return next(
            (alias for alias in aliases if _entity_exists(ifc_file.schema, alias)),
            None,
        )

    areas = {
        "fundacao": {"tipos": ["IfcFooting", "IfcPile"]},
        "estrutura": {"tipos": ["IfcColumn", "IfcBeam"]},
        "alvenaria": {"tipos": ["IfcWall", "IfcWallStandardCase"]},
        "cobertura": {"tipos": ["IfcRoof"]},
        "portas_janelas": {"tipos": ["IfcDoor", "IfcWindow"]},
        "hidraulicas": {
            "tipos": ["IfcPipeSegment", "IfcPipeFitting", "IfcFlowTerminal"],
        },
        "eletricas": {
            "tipos": [
                "IfcLightFixture",
                "IfcOutlet",
                "IfcSwitchingDevice",
                "IfcCableCarrierSegment",
            ],
        },
        "revestimentos": {"tipos": ["IfcCovering"]},
        "loucas_metais": {"tipos": ["IfcSanitaryTerminal"]},
    }

    for area in areas.values():
        resolved = [
            resolved_name
            for type_name in area["tipos"]
            if (resolved_name := resolve_type(type_name))
        ]
        area["tipos_resolvidos"] = resolved
        area["presente"] = _safe_count(ifc_file, *resolved) > 0
        area["n"] = _safe_count(ifc_file, *resolved)

    return {
        "schema": ifc_file.schema,
        "pavimentos": [
            _entity_name(storey) for storey in _safe_by_type(ifc_file, "IfcBuildingStorey")
        ],
        "areas": areas,
        "materiais": sorted(
            {
                material.Name
                for material in _safe_by_type(ifc_file, "IfcMaterial")
                if getattr(material, "Name", None)
            },
        ),
        "camadas_material": extract_layersets(ifc_file),
    }


def _extract_properties_and_quantities(element) -> dict[str, Any]:
    data: dict[str, Any] = {"property_sets": {}, "quantities": {}}
    for rel in getattr(element, "IsDefinedBy", []) or []:
        definition = getattr(rel, "RelatingPropertyDefinition", None)
        if definition is None:
            continue

        name = getattr(definition, "Name", None) or definition.is_a()
        if _entity_is_a(definition, "IfcPropertySet"):
            props = {}
            for prop in getattr(definition, "HasProperties", []) or []:
                prop_name = getattr(prop, "Name", None)
                if not prop_name:
                    continue
                props[prop_name] = _safe_value(getattr(prop, "NominalValue", None))
            if props:
                data["property_sets"][name] = props

        if _entity_is_a(definition, "IfcElementQuantity"):
            qtos = {}
            for quantity in getattr(definition, "Quantities", []) or []:
                qto_name = getattr(quantity, "Name", None)
                if not qto_name:
                    continue
                for attr in (
                    "AreaValue",
                    "VolumeValue",
                    "LengthValue",
                    "CountValue",
                    "WeightValue",
                    "TimeValue",
                ):
                    value = getattr(quantity, attr, None)
                    if value is not None:
                        qtos[qto_name] = {"tipo": attr, "valor": _safe_value(value)}
                        break
            if qtos:
                data["quantities"][name] = qtos

    inferred_geometry = _infer_geometry_quantities(element)
    if inferred_geometry:
        data["inferred_geometry"] = inferred_geometry
        inferred_quantities = _geometry_quantities_for_missing_direct_values(
            geometry=inferred_geometry,
            direct_value_types=_quantity_value_types(data["quantities"]),
            direct_quantity_names=_quantity_names(data["quantities"]),
        )
        if inferred_quantities:
            data["quantities"]["InferredGeometry"] = inferred_quantities
    return data


def _spatial_container_name(element) -> str | None:
    for rel in getattr(element, "ContainedInStructure", []) or []:
        container = getattr(rel, "RelatingStructure", None)
        if container is not None:
            return _entity_name(container)
    return None


def extract_spatial_data(ifc_file) -> dict[str, Any]:
    """Extract spaces, storeys, spatial containment, and element quantities."""

    storeys = []
    for storey in _safe_by_type(ifc_file, "IfcBuildingStorey"):
        contained = []
        for rel in getattr(storey, "ContainsElements", []) or []:
            contained.extend(getattr(rel, "RelatedElements", []) or [])
        counts: dict[str, int] = {}
        for element in contained:
            element_type = element.is_a() if hasattr(element, "is_a") else "Unknown"
            counts[element_type] = counts.get(element_type, 0) + 1
        storeys.append(
            {
                "id": _entity_id(storey),
                "global_id": getattr(storey, "GlobalId", None),
                "nome": _entity_name(storey),
                "elevacao": getattr(storey, "Elevation", None),
                "contagem_elementos": counts,
            },
        )

    spaces = []
    for space in _safe_by_type(ifc_file, "IfcSpace"):
        contained = []
        for rel in getattr(space, "ContainsElements", []) or []:
            contained.extend(getattr(rel, "RelatedElements", []) or [])
        spaces.append(
            {
                "id": _entity_id(space),
                "global_id": getattr(space, "GlobalId", None),
                "nome": _entity_name(space),
                "long_name": getattr(space, "LongName", None),
                "object_type": getattr(space, "ObjectType", None),
                "pavimento": _spatial_container_name(space),
                "dados": _extract_properties_and_quantities(space),
                "elementos_contidos": [_element_ref(element) for element in contained],
            },
        )

    element_types = [
        "IfcWall",
        "IfcWallStandardCase",
        "IfcSlab",
        "IfcRoof",
        "IfcCovering",
        "IfcDoor",
        "IfcWindow",
        "IfcColumn",
        "IfcBeam",
        "IfcFooting",
        "IfcPile",
        "IfcFlowSegment",
        "IfcFlowFitting",
        "IfcFlowTerminal",
        "IfcSanitaryTerminal",
        "IfcLightFixture",
        "IfcOutlet",
    ]
    elements = []
    for entity_name in element_types:
        for element in _safe_by_type(ifc_file, entity_name):
            elements.append(
                {
                    **_element_ref(element),
                    "pavimento_ou_ambiente": _spatial_container_name(element),
                    "dados": _extract_properties_and_quantities(element),
                },
            )

    return {
        "schema": ifc_file.schema,
        "pavimentos": storeys,
        "ambientes": spaces,
        "elementos_com_quantitativos": elements,
    }
