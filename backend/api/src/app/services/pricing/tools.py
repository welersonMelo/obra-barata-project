"""LangChain tools used by the supplier-pricing ReAct agent."""

# coverage: ignore file

from __future__ import annotations

import asyncio
import math
import re
import threading
from collections.abc import Awaitable, Callable
from contextvars import copy_context
from typing import Any

from langchain_core.tools import tool

from app.models.materials import OfertaFornecedor
from app.services.pricing.suppliers import (
    CASA_ELETRICIDADE_BASE_URL,
    COMERCIAL_ALIANCA_BASE_URL,
    COMERCIAL_ALIANCA_STORE_ID,
    PisolarSupplier,
    SerperSupplier,
    TraySupplier,
    _parse_amount_unit,
    _parse_unit_family,
    build_product_search_text,
)


def _run_async_sync(factory: Callable[[], Awaitable[Any]]) -> Any:
    """Run an async supplier search from a sync LangChain tool."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(factory())

    result_box: dict[str, Any] = {}

    def runner() -> None:
        try:
            result_box["value"] = asyncio.run(factory())
        except BaseException as exc:
            result_box["error"] = exc

    context = copy_context()
    thread = threading.Thread(target=lambda: context.run(runner))
    thread.start()
    thread.join()
    if "error" in result_box:
        raise result_box["error"]
    return result_box.get("value")


def _offers_to_payload(offers: list[OfertaFornecedor]) -> list[dict]:
    """Serialize offers into tool-message-friendly dictionaries."""

    return [offer.model_dump(mode="json") for offer in offers]


@tool
def prepare_product_search_text_tool(
    nome: str,
    descricao: str = "",
    quantidade: float | None = None,
    medida: str = "",
    fornecedor: str = "",
) -> str:
    """Return one concise product search text from MaterialObra fields.

    Use antes das tools de fornecedores quando o nome tiver contexto de obra,
    ambiente ou tarefa, por exemplo: nome='Pintura interna (tinta acrilica)',
    descricao='Tinta para paredes internas', quantidade=3, medida='lata 18 L'
    retorna 'tinta acrilica 18L'. O texto retornado deve ser usado como
    product_name nas buscas; nao duplique quantidade/medida na chamada de busca.
    """

    return build_product_search_text(
        nome=nome,
        descricao=descricao,
        quantidade=quantidade,
        medida=medida,
        fornecedor=fornecedor,
    )


@tool
def calculator_tool(expression: str) -> str:
    """Use para qualquer calculo aritmetico direto; nao faca calculo numerico de cabeca."""

    import numexpr

    local_dict = {"pi": math.pi, "e": math.e}
    return str(
        numexpr.evaluate(
            expression.strip(),
            global_dict={},
            local_dict=local_dict,
        )
    )


@tool
def percentage_tool(base_value: float, percent: float) -> dict:
    """Use para calcular porcentagem aplicada sobre um valor base; nao faca calculo de cabeca."""

    percentage_value = base_value * (percent / 100)
    total_with_percentage = base_value + percentage_value
    return {
        "base_value": base_value,
        "percent": percent,
        "percentage_value": percentage_value,
        "total_with_percentage": total_with_percentage,
    }


@tool
def percent_change_tool(initial_value: float, final_value: float) -> dict:
    """Use para calcular variacao percentual entre dois valores; nao faca calculo de cabeca."""

    if initial_value == 0:
        return {
            "error": "initial_value nao pode ser zero para calcular variacao percentual."
        }

    absolute_change = final_value - initial_value
    percent_change = (absolute_change / initial_value) * 100
    return {
        "initial_value": initial_value,
        "final_value": final_value,
        "absolute_change": absolute_change,
        "percent_change": percent_change,
    }


@tool
def purchase_quantity_tool(
    required_quantity: float,
    required_unit: str,
    offer_unit: str,
    unit_price: float | None = None,
) -> dict:
    """Calculate how many commercial packages to buy based on required amount and offer unit."""

    required_family = _parse_unit_family(required_unit)
    offer_size, offer_family = _parse_amount_unit(offer_unit)

    if required_quantity is None or required_quantity <= 0:
        return {"error": "required_quantity must be greater than zero."}
    if not required_family:
        return {"error": f"Could not infer required unit family from '{required_unit}'."}
    if offer_size is None or not offer_family:
        return {"error": f"Could not infer package size from offer_unit '{offer_unit}'."}
    if required_family != offer_family:
        return {
            "error": "required_unit and offer_unit are not compatible.",
            "required_unit": required_unit,
            "offer_unit": offer_unit,
            "required_family": required_family,
            "offer_family": offer_family,
        }

    purchase_quantity = math.ceil(required_quantity / offer_size)
    covered_quantity = purchase_quantity * offer_size
    total_price = unit_price * purchase_quantity if unit_price is not None else None
    return {
        "required_quantity": required_quantity,
        "required_unit": required_unit,
        "offer_unit": offer_unit,
        "package_size": offer_size,
        "unit_family": required_family,
        "purchase_quantity": purchase_quantity,
        "covered_quantity": covered_quantity,
        "unit_price": unit_price,
        "total_price": total_price,
    }


@tool
def search_supplier_pisolar_tool(
    product_name: str,
    unit: str = "",
    quantity: float | None = None,
    profile: str = "Medio custo",
) -> list[dict]:
    """Search Pisolar through its site search and return supplier offers in the same shape as Serper.
    Pisolar e uma loja de materiais de construcao com um portfolio amplo para obras residenciais
    oferecendo pisos e revestimentos ceramicos, porcelanatos, argamassas e rejuntes, alem de materiais hidraulicos
    e eletricos, tintas, impermeabilizantes, ferramentas, iluminacao, portas, janelas, telhas e itens de acabamento.
    Considere que todos os produtos podem ser parcelados em 8x.
    E o frete e gratis.
    """

    provider = PisolarSupplier()
    search_text = build_product_search_text(
        nome=product_name,
        quantidade=quantity,
        medida=unit,
    )
    offers = _run_async_sync(
        lambda: provider.search(
            product_name=search_text,
            unit="",
            quantity=None,
            profile=profile,
            limit=5,
        )
    )
    return _offers_to_payload(offers)


@tool
def search_supplier_comercial_alianca_tool(
    product_name: str,
    unit: str = "",
    quantity: float | None = None,
    profile: str = "Medio custo",
) -> list[dict]:
    """Search Comercial Alianca through its site search and return supplier offers in the same shape as Serper.
    Comercial Alianca e uma loja de materiais de construcao, pintura, eletrica, hidraulica,
    acabamentos, ferramentas e ferragens. A busca usa a barra de pesquisa do site, sem cidade.
    Considere que os produtos podem ser parcelados em ate 10x sem juros quando o site permitir.
    """

    provider = TraySupplier(
        name="Comercial Alianca",
        base_url=COMERCIAL_ALIANCA_BASE_URL,
        store_id=COMERCIAL_ALIANCA_STORE_ID,
        default_installments=10,
    )
    search_text = build_product_search_text(
        nome=product_name,
        quantidade=quantity,
        medida=unit,
        fornecedor="Comercial Alianca",
    )
    offers = _run_async_sync(
        lambda: provider.search(
            product_name=search_text,
            unit="",
            quantity=None,
            profile=profile,
            limit=5,
        )
    )
    return _offers_to_payload(offers)


@tool
def search_supplier_casa_eletricidade_tool(
    product_name: str,
    unit: str = "",
    quantity: float | None = None,
    profile: str = "Medio custo",
) -> list[dict]:
    """Search Casa da Eletricidade through its site search and return supplier offers in the same shape as Serper.
    Use esta tool para materiais eletricos ou similares: fios, cabos, disjuntores, quadros,
    caixas eletricas, interruptores, tomadas, iluminacao LED, lampadas, chuveiros eletricos,
    torneiras eletricas, sensores, transformadores, fita isolante, equipamentos de seguranca,
    ferramentas, instrumentos de medicao, hidraulica, irrigacao e jardinagem.
    Nao use para pintura, pisos, alvenaria, cimento, areia, portas, janelas ou acabamento geral,
    exceto quando o material for explicitamente eletrico ou de uma categoria similar acima.
    A busca usa a barra de pesquisa do site, sem cidade.
    """

    provider = TraySupplier(
        name="Casa da Eletricidade",
        base_url=CASA_ELETRICIDADE_BASE_URL,
        schema_first=True,
        product_card_fallback=True,
    )
    search_text = build_product_search_text(
        nome=product_name,
        quantidade=quantity,
        medida=unit,
        fornecedor="Casa da Eletricidade",
    )
    offers = _run_async_sync(
        lambda: provider.search(
            product_name=search_text,
            unit="",
            quantity=None,
            profile=profile,
            limit=5,
        )
    )
    return _offers_to_payload(offers)


@tool
def search_supplier_serp_tool(
    product_name: str,
    unit: str = "",
    quantity: float | None = None,
    profile: str = "Medio custo",
    city: str = "Aracaju - SE",
) -> list[dict]:
    """Search for suppliers of a product using Serper Shopping and return the first 5 offers.
       Prefer supplier-specific tools such as Pisolar, Comercial Alianca or Casa da Eletricidade before Serper.
       Use somente quando nao encontrar em tools especificas de fornecedores, como a tool da Pisolar.
    """

    provider = SerperSupplier()
    search_text = build_product_search_text(
        nome=product_name,
        quantidade=quantity,
        medida=unit,
    )
    if city and not re.search(r"\b(aracaju|se)\b", city, flags=re.IGNORECASE):
        profile = f"{profile} {city}"
    offers = _run_async_sync(
        lambda: provider.search(
            product_name=search_text,
            unit="",
            quantity=None,
            profile=profile,
            limit=5,
        )
    )
    return _offers_to_payload(offers)


def default_supplier_pricing_tools(
    use_serper_fallback: bool = False,
) -> list:
    """Return the default tool list used by the supplier ReAct agent."""

    tools = [
        prepare_product_search_text_tool,
        search_supplier_casa_eletricidade_tool,
        search_supplier_pisolar_tool,
        search_supplier_comercial_alianca_tool,
    ]
    if use_serper_fallback:
        tools.append(search_supplier_serp_tool)
    tools.extend(
        [
            purchase_quantity_tool,
            calculator_tool,
            percentage_tool,
            percent_change_tool,
        ]
    )
    return tools


def default_supplier_pricing_tools_without_serper() -> list:
    """Return the notebook-style supplier tool list without the Serper fallback."""

    return default_supplier_pricing_tools(use_serper_fallback=False)
