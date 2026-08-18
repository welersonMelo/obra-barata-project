"""ReAct supplier-pricing agent ported from the pricing notebook."""

# coverage: ignore file

from __future__ import annotations

import asyncio
import ast
import hashlib
import json
import logging
import math
import re
from datetime import date
from typing import Annotated, Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from app.models.materials import ListaMateriaisObra, MaterialObra, OfertaFornecedor
from app.services.ifc.llm_client import build_openai_chat_model
from app.services.pricing.suppliers import (
    _parse_amount_unit,
    _parse_unit_family,
    build_product_search_text,
    normalize_search_text,
)
from app.services.pricing.tools import default_supplier_pricing_tools


logger = logging.getLogger(__name__)


class SupplierReasoningState(TypedDict):
    messages: Annotated[list, add_messages]


SUPPLIER_REASONING_SYSTEM_PROMPT = """
You are the base Reasoning agent for supplier discovery in Obra Barata.
Your job is to control the available tools, search supplier offers for one material at a time,
compare the evidence, and return only a JSON object that can update MaterialObra.

Rules:
- Use tools before choosing suppliers whenever a search tool is available.
- Choose supplier-specific tools by product domain before using a generic web search.
- Use search_supplier_casa_eletricidade_tool, when available, only for electrical or adjacent materials: fios, cabos, disjuntores, quadros de distribuicao, caixas eletricas, interruptores, tomadas, iluminacao/LED, lampadas, chuveiros ou torneiras eletricas, sensores, transformadores, fita isolante, equipamentos de seguranca/comunicacao, ferramentas eletricas/manuais, instrumentos de medicao, hidraulica, irrigacao e jardinagem.
- Do not call search_supplier_casa_eletricidade_tool for paint/coatings, floors, masonry, cement, sand, doors/windows, or general finishing unless the material is explicitly electrical or in an adjacent category above.
- Prefer supplier-specific tools before Serper: Casa da Eletricidade for electrical/similar items; Pisolar and Comercial Alianca for broader construction/finishing items; Serper only when supplier-specific tools are unavailable or return no good offers.
- Before supplier search, use prepare_product_search_text_tool to turn MaterialObra fields into one concise product query. Use the returned text as product_name in supplier tools and avoid duplicating quantity/medida there; for example, 'Pintura interna (tinta acrilica)' + medida 'lata 18 L' should be searched as 'tinta acrilica 18L'.
- Use tools to make calculations, conversions, and percentage computations; do not calculate in your head, when possible.
- Do not invent supplier quotes, product links, freight, installments, or availability.
- Exception for no-results cases: if all relevant supplier/site search tools return no relevant priced offers, create exactly one estimated offer with fornecedor="Estimativa IA". Use your construction-pricing knowledge to suggest a reasonable average market price for budgeting, based on the material name, description, quantity, unit/measure, product profile, and common Brazilian construction-market units. This is not a supplier quote.
- For an estimated offer, set link_produto=null, marca=null, frete=null, num_parcelas=1, disponibilidade="Estimativa de preco medio gerada por IA; cotacao real nao encontrada nos fornecedores consultados.", and data_consulta=today.
- For an estimated offer, use material.medida as unidade. If material.quantidade is available, set offer.quantidade=material.quantidade, valor_unitario as the average price for one material.medida, and calculate valor_total/preco_a_vista/preco_a_prazo = quantidade * valor_unitario. If quantity is null, set quantidade=1, total fields equal to valor_unitario, and explain the uncertainty.
- In justificativa, explicitly say which supplier tools did not return a usable price, why a site quote was not reliable for this item, the assumption behind the average unit price, and that the value must be reviewed with a real supplier before purchase.
- Never include "Estimativa IA" when at least one relevant real supplier offer with price exists; real quotes are preferred over estimates.
- Prefer offers that match product name, unit,and product profile.
- When you recieve a list of offers, choose the best based on location, name match, unit match, and price.
- Do not stop after the first supplier tool if another relevant supplier-specific search tool is available.
- For broad construction, finishing, painting, tools, hydraulic or similar materials, call both search_supplier_pisolar_tool and search_supplier_comercial_alianca_tool when both are available, then compare the offers.
- For electrical or adjacent materials, call search_supplier_casa_eletricidade_tool when available; if it does not provide enough good priced offers, also call other relevant supplier tools.
- The top-level fornecedor and prices must represent the best offer, but lista_fornecedores must be a short ranked list of alternatives for the same material.
- Keep distinct offers from the same store when brand, model, package size, unit, price or link differs, because those differences matter to the user.
- Include offers from different suppliers in lista_fornecedores whenever they are available and relevant, even if the cheapest offer is from only one supplier.
- When deciding purchase quantity, compare material.quantidade + material.medida with each offer.unidade.
- Treat offer.valor_unitario as the price of one commercial package described by offer.unidade/title, not necessarily the price of one material.medida.
- If material.quantidade=30 and material.medida='L', then an offer.unidade='30 L' means quantidade=1; offer.unidade='20 L' means quantidade=2. Always round up so the purchase covers the required amount.
- Use purchase_quantity_tool whenever material.quantidade, material.medida, offer.unidade and offer.valor_unitario are available.
- Recalculate valor_total, preco_a_vista and preco_a_prazo from package price * purchase quantidade when package size is known.
- If package size cannot be inferred from offer.unidade or title, keep quantidade=1 for that offer and explain the uncertainty in justificativa.
- Return JSON only, with this shape:
{
  "fornecedor": "best supplier name or empty string",
  "lista_fornecedores": [
    {
      "fornecedor": "supplier name",
      "descricao": "product description",
      "marca": "brand or null",
      "unidade": "commercial unit",
      "quantidade": 1,
      "valor_unitario": 0,
      "valor_total": 0,
      "preco_a_vista": 0,
      "preco_a_prazo": 0,
      "num_parcelas": 1,
      "frete": 0,
      "disponibilidade": "availability text",
      "data_consulta": "YYYY-MM-DD",
      "link_produto": "source URL"
    }
  ],
  "valor_unitario": 0,
  "valor_total": 0,
  "preco_a_vista": 0,
  "preco_a_prazo": 0,
  "num_parcelas": 1,
  "frete": 0,
  "justificativa": "short evidence-based explanation"
}
""".strip()


class SupplierPricingReActAgent:
    """Service object that runs the notebook ReAct agent for supplier pricing."""

    def __init__(
        self,
        reasoning_llm=None,
        supplier_search_tools: list | None = None,
    ) -> None:
        self.reasoning_llm = reasoning_llm
        self.supplier_search_tools = supplier_search_tools

    async def fill_suppliers(
        self,
        lista_materiais: ListaMateriaisObra,
        max_fornecedores_por_material: int = 3,
        max_materiais_processados: int | None = None,
        use_serper_fallback: bool = False,
    ) -> ListaMateriaisObra:
        """Run the ReAct agent without blocking the FastAPI event loop."""

        tools = self.supplier_search_tools
        if tools is None:
            tools = default_supplier_pricing_tools(
                use_serper_fallback=use_serper_fallback,
            )
        return await asyncio.to_thread(
            preencher_fornecedores_com_reasoning_agent,
            lista_materiais=lista_materiais,
            reasoning_llm=self.reasoning_llm,
            supplier_search_tools=tools,
            max_fornecedores_por_material=max_fornecedores_por_material,
            max_materiais_processados=max_materiais_processados,
        )


def _preview_for_log(value: Any, max_chars: int = 1200) -> str:
    """Return a compact printable preview for reasoning/tool logs."""

    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except TypeError:
            text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        return text[:max_chars] + "... [truncated]"
    return text


def _log_reasoning_event(title: str, payload: Any | None = None) -> None:
    if payload is None:
        logger.info("[reasoning] %s", title)
    else:
        logger.info("[reasoning] %s %s", title, _preview_for_log(payload))


def _log_tool_calls(response) -> None:
    tool_calls = getattr(response, "tool_calls", None) or []
    if not tool_calls:
        _log_reasoning_event("LLM did not request tools")
        return

    _log_reasoning_event(f"LLM requested {len(tool_calls)} tool call(s)")
    for index, tool_call in enumerate(tool_calls, start=1):
        name = (
            tool_call.get("name")
            if isinstance(tool_call, dict)
            else getattr(tool_call, "name", "unknown")
        )
        args = (
            tool_call.get("args")
            if isinstance(tool_call, dict)
            else getattr(tool_call, "args", None)
        )
        logger.info(
            "[reasoning][tool_call:%s] %s args=%s",
            index,
            name,
            _preview_for_log(args),
        )


def build_supplier_reasoning_agent(
    reasoning_llm,
    supplier_search_tools: list | None = None,
    checkpointer: MemorySaver | None = None,
):
    """Build the base ReAct graph that controls supplier search tools."""

    tools = list(supplier_search_tools or [])
    llm_with_tools = reasoning_llm.bind_tools(tools)
    tool_node = ToolNode(tools)

    def reasoning_agent(state: SupplierReasoningState) -> dict:
        messages = state["messages"]
        last_message = messages[-1] if messages else None
        _log_reasoning_event(
            f"Calling LLM with {len(messages)} message(s); last={type(last_message).__name__}",
            _message_text(last_message) if last_message is not None else None,
        )
        response = llm_with_tools.invoke(state["messages"])
        _log_reasoning_event("LLM visible response", _message_text(response))
        _log_tool_calls(response)
        return {"messages": [response]}

    def tools_with_logging(state: SupplierReasoningState) -> dict:
        _log_reasoning_event("Executing requested tool(s)")
        try:
            result = tool_node.invoke(state)
        except Exception as exc:
            _log_reasoning_event(
                "Tool execution failed",
                {"error_type": type(exc).__name__, "error": str(exc)},
            )
            raise
        tool_messages = result.get("messages", []) if isinstance(result, dict) else []
        for index, tool_message in enumerate(tool_messages, start=1):
            tool_name = (
                getattr(tool_message, "name", None)
                or getattr(tool_message, "tool_call_id", "unknown")
            )
            logger.info(
                f"[reasoning][tool_result:{index}] "
                f"{tool_name}: {_preview_for_log(_message_text(tool_message))}"
            )
        return result

    graph = StateGraph(SupplierReasoningState)
    graph.add_node("reasoning_agent", reasoning_agent)
    graph.add_node("tools", tools_with_logging)
    graph.add_edge(START, "reasoning_agent")
    graph.add_conditional_edges("reasoning_agent", tools_condition)
    graph.add_edge("tools", "reasoning_agent")
    return graph.compile(checkpointer=checkpointer)


def _message_text(message) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _extract_json_object(text: str) -> dict:
    fenced_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced_match:
        return json.loads(fenced_match.group(1))

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {"lista_fornecedores": [], "justificativa": text.strip()}
    return json.loads(text[start : end + 1])


def _material_prompt(
    area_name: str,
    material: MaterialObra,
    max_fornecedores_por_material: int = 3,
) -> str:
    payload = {
        "area": area_name,
        "material": material.model_dump(mode="json"),
        "data_consulta": date.today().isoformat(),
    }
    return (
        "Find supplier offers for this MaterialObra and return the JSON update only. "
        "Use material.quantidade + material.medida as the required amount, and use offer.unidade "
        "to decide how many commercial packages must be bought. "
        f"Return up to {max_fornecedores_por_material} offers in lista_fornecedores for this material. "
        "lista_fornecedores is the final alternatives list, not only the selected winner. "
        "Include different suppliers when available, and keep relevant same-store brand/package variants.\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )


def _valid_offer_payloads(update_payload: dict) -> list[OfertaFornecedor]:
    raw_offers = update_payload.get("lista_fornecedores") or update_payload.get("ofertas") or []
    offers = []
    for raw_offer in raw_offers:
        if not isinstance(raw_offer, dict) or raw_offer.get("status") == "tool_not_implemented":
            continue
        try:
            offers.append(OfertaFornecedor.model_validate(raw_offer))
        except Exception as exc:
            logger.warning("Skipping invalid supplier offer: %s", exc)
    return offers


def _best_offer(offers: list[OfertaFornecedor]) -> OfertaFornecedor | None:
    priced_offers = [offer for offer in offers if _offer_rank_value(offer) < float("inf")]
    if priced_offers:
        return min(priced_offers, key=_offer_rank_value)
    return offers[0] if offers else None


def _is_ai_estimate_offer(offer: OfertaFornecedor) -> bool:
    """Return whether an offer is the LLM-generated average-price fallback."""

    supplier = normalize_search_text(offer.fornecedor)
    return supplier == "estimativa ia" or supplier.startswith("estimativa ia ")


def _discard_ai_estimates_when_real_priced_offers_exist(
    offers: list[OfertaFornecedor],
) -> list[OfertaFornecedor]:
    """Keep LLM estimates only when no real priced supplier offer exists."""

    real_priced_offers = [
        offer
        for offer in offers
        if not _is_ai_estimate_offer(offer)
        and _offer_rank_value(offer) < float("inf")
    ]
    if not real_priced_offers:
        return offers
    return [offer for offer in offers if not _is_ai_estimate_offer(offer)]


def _offer_rank_value(offer: OfertaFornecedor) -> float:
    """Return the best comparable price for ranking an offer."""

    for value in (
        offer.valor_total,
        offer.preco_a_vista,
        offer.preco_a_prazo,
        offer.valor_unitario,
    ):
        if value is not None:
            return float(value)
    return float("inf")


def _offer_identity(offer: OfertaFornecedor) -> tuple[str, str, str, str]:
    """Build a stable identity to avoid repeated offer cards."""

    return (
        normalize_search_text(offer.fornecedor),
        normalize_search_text(offer.link_produto or ""),
        normalize_search_text(offer.descricao or ""),
        normalize_search_text(offer.unidade or ""),
    )


def _raw_offer_identity(raw_offer: dict) -> tuple[str, str, str, str]:
    """Build a stable identity for raw dict offers before model validation."""

    return (
        normalize_search_text(raw_offer.get("fornecedor", "")),
        normalize_search_text(raw_offer.get("link_produto") or ""),
        normalize_search_text(raw_offer.get("descricao") or ""),
        normalize_search_text(raw_offer.get("unidade") or ""),
    )


def _enrich_offer_for_material(
    material: MaterialObra,
    offer: OfertaFornecedor,
) -> OfertaFornecedor:
    """Fill purchase quantity and totals when the commercial package unit is clear."""

    updates: dict[str, Any] = {}
    purchase_quantity = offer.quantidade

    if (
        purchase_quantity is None
        and material.quantidade is not None
        and material.medida
        and offer.unidade
    ):
        required_family = _parse_unit_family(material.medida)
        offer_size, offer_family = _parse_amount_unit(offer.unidade)
        if required_family and offer_family and required_family == offer_family and offer_size:
            purchase_quantity = math.ceil(material.quantidade / offer_size)
            updates["quantidade"] = float(purchase_quantity)

    if purchase_quantity is not None and offer.valor_unitario is not None:
        total_price = round(float(offer.valor_unitario) * float(purchase_quantity), 2)
        if offer.valor_total is None:
            updates["valor_total"] = total_price
        if offer.preco_a_vista is None:
            updates["preco_a_vista"] = total_price
        if offer.preco_a_prazo is None:
            updates["preco_a_prazo"] = total_price

    return offer.model_copy(update=updates) if updates else offer


def _select_offer_options(
    offers: list[OfertaFornecedor],
    limit: int | None,
) -> list[OfertaFornecedor]:
    """Rank offers, keep supplier diversity, then cap the alternatives list."""

    if not offers:
        return []
    if limit is None:
        limit = 3
    limit = max(int(limit), 0)
    if limit == 0:
        return []

    deduped: list[OfertaFornecedor] = []
    seen = set()
    for offer in offers:
        key = _offer_identity(offer)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(offer)

    ranked = sorted(
        deduped,
        key=lambda offer: (
            _offer_rank_value(offer),
            normalize_search_text(offer.fornecedor),
            normalize_search_text(offer.descricao or ""),
        ),
    )
    selected: list[OfertaFornecedor] = []
    selected_keys = set()
    selected_suppliers = set()

    def add_offer(offer: OfertaFornecedor) -> None:
        key = _offer_identity(offer)
        if key in selected_keys or len(selected) >= limit:
            return
        selected.append(offer)
        selected_keys.add(key)
        selected_suppliers.add(normalize_search_text(offer.fornecedor))

    add_offer(ranked[0])
    for offer in ranked[1:]:
        supplier_key = normalize_search_text(offer.fornecedor)
        if supplier_key not in selected_suppliers:
            add_offer(offer)
        if len(selected) >= limit:
            return selected
    for offer in ranked[1:]:
        add_offer(offer)
        if len(selected) >= limit:
            break
    return selected


def _parse_tool_payload(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(content)
        except (ValueError, SyntaxError):
            return None


def _supplier_tool_offer_payloads(messages: list) -> list[dict]:
    """Extract raw supplier offers from search tool messages."""

    offers: list[dict] = []
    for message in messages:
        tool_name = getattr(message, "name", None)
        if not tool_name or not str(tool_name).startswith("search_supplier_"):
            continue
        payload = _parse_tool_payload(_message_text(message))
        raw_offers = (
            payload
            if isinstance(payload, list)
            else payload.get("lista_fornecedores", [])
            if isinstance(payload, dict)
            else []
        )
        for raw_offer in raw_offers:
            if isinstance(raw_offer, dict) and raw_offer.get("status") != "tool_not_implemented":
                offers.append(raw_offer)
    return offers


def _merge_supplier_offer_payloads(update_payload: dict, extra_offers: list[dict]) -> dict:
    """Merge LLM-selected offers with raw search-tool offers, preserving unique options."""

    if not extra_offers:
        return update_payload
    merged_payload = dict(update_payload)
    primary_offers = merged_payload.get("lista_fornecedores") or merged_payload.get("ofertas") or []
    if isinstance(primary_offers, dict):
        primary_offers = list(primary_offers.values())
    if not isinstance(primary_offers, list):
        primary_offers = []

    merged_offers = []
    seen = set()
    for raw_offer in [*primary_offers, *extra_offers]:
        if not isinstance(raw_offer, dict):
            continue
        key = _raw_offer_identity(raw_offer)
        if key in seen:
            continue
        seen.add(key)
        merged_offers.append(raw_offer)
    if merged_offers:
        merged_payload["lista_fornecedores"] = merged_offers
    return merged_payload


ELECTRICAL_SUPPLIER_TERMS = {
    "eletrica",
    "eletrico",
    "fio",
    "fios",
    "cabo",
    "cabos",
    "disjuntor",
    "disjuntores",
    "quadro",
    "tomada",
    "tomadas",
    "interruptor",
    "interruptores",
    "lampada",
    "lampadas",
    "led",
    "iluminacao",
    "chuveiro",
    "torneira eletrica",
    "sensor",
    "transformador",
    "fita isolante",
    "caixa eletrica",
    "eletroduto",
}


def _tool_name(tool) -> str:
    """Return a stable LangChain/plain-function tool name."""

    return getattr(tool, "name", None) or getattr(tool, "__name__", "")


def _is_electrical_supplier_material(area_name: str, material: MaterialObra) -> bool:
    """Return whether Casa da Eletricidade is a relevant supplier for the material."""

    haystack = normalize_search_text(f"{area_name} {material.nome} {material.descricao}")
    return any(term in haystack for term in ELECTRICAL_SUPPLIER_TERMS)


def _supplier_tool_relevant_for_material(
    tool_name: str,
    area_name: str,
    material: MaterialObra,
) -> bool:
    """Decide which supplier-specific tools should be present in the alternatives list."""

    if tool_name == "search_supplier_serp_tool":
        return False
    if tool_name == "search_supplier_casa_eletricidade_tool":
        return _is_electrical_supplier_material(area_name, material)
    return tool_name in {
        "search_supplier_pisolar_tool",
        "search_supplier_comercial_alianca_tool",
    }


def _payload_has_supplier_for_tool(update_payload: dict, tool_name: str) -> bool:
    """Check whether update_payload already contains offers from the supplier behind tool_name."""

    expected_terms = {
        "search_supplier_pisolar_tool": ("pisolar",),
        "search_supplier_comercial_alianca_tool": ("comercial alianca",),
        "search_supplier_casa_eletricidade_tool": ("casa da eletricidade",),
    }.get(tool_name, ())
    if not expected_terms:
        return False
    raw_offers = update_payload.get("lista_fornecedores") or update_payload.get("ofertas") or []
    if isinstance(raw_offers, dict):
        raw_offers = list(raw_offers.values())
    if not isinstance(raw_offers, list):
        return False
    suppliers = [
        normalize_search_text(raw_offer.get("fornecedor", ""))
        for raw_offer in raw_offers
        if isinstance(raw_offer, dict)
    ]
    return any(any(term in supplier for term in expected_terms) for supplier in suppliers)


def _raw_offers_from_tool_result(result: Any) -> list[dict]:
    """Normalize a direct tool result into raw offer dicts."""

    if isinstance(result, str):
        parsed = _parse_tool_payload(result)
        if parsed is None:
            return []
        result = parsed
    raw_offers = (
        result
        if isinstance(result, list)
        else result.get("lista_fornecedores", [])
        if isinstance(result, dict)
        else []
    )
    return [raw_offer for raw_offer in raw_offers if isinstance(raw_offer, dict)]


def _invoke_supplier_tool_for_material(tool, material: MaterialObra) -> list[dict]:
    """Call a supplier search tool directly for fallback/complementary alternatives."""

    profile = (
        getattr(material.perfil_produto, "value", None)
        or material.perfil_produto
        or "Medio custo"
    )
    search_text = build_product_search_text(
        nome=material.nome,
        descricao=material.descricao,
        quantidade=material.quantidade,
        medida=material.medida or "",
    )
    args = {
        "product_name": search_text,
        "unit": "",
        "quantity": None,
        "profile": profile,
    }
    if hasattr(tool, "invoke"):
        return _raw_offers_from_tool_result(tool.invoke(args))
    return _raw_offers_from_tool_result(tool(**args))


def _missing_relevant_supplier_tool_offers(
    supplier_search_tools: list | None,
    area_name: str,
    material: MaterialObra,
    update_payload: dict,
) -> list[dict]:
    """Search relevant supplier-specific tools that the LLM did not include."""

    extra_offers: list[dict] = []
    for tool in supplier_search_tools or []:
        tool_name = _tool_name(tool)
        if not _supplier_tool_relevant_for_material(tool_name, area_name, material):
            continue
        if _payload_has_supplier_for_tool(update_payload, tool_name):
            continue
        _log_reasoning_event(
            "Complementary supplier search",
            {"tool": tool_name, "material": material.nome, "area": area_name},
        )
        try:
            tool_offers = _invoke_supplier_tool_for_material(tool, material)
        except Exception as exc:
            _log_reasoning_event(
                "Complementary supplier search failed",
                {"tool": tool_name, "error_type": type(exc).__name__, "error": str(exc)},
            )
            continue
        _log_reasoning_event(
            "Complementary supplier search result",
            {"tool": tool_name, "offers": len(tool_offers)},
        )
        extra_offers.extend(tool_offers)
    return extra_offers


def _apply_supplier_update(
    material: MaterialObra,
    update_payload: dict,
    max_fornecedores_por_material: int | None = 3,
) -> MaterialObra:
    offers = [
        _enrich_offer_for_material(material, offer)
        for offer in _valid_offer_payloads(update_payload)
    ]
    offers = _discard_ai_estimates_when_real_priced_offers_exist(offers)
    offers = _select_offer_options(offers, max_fornecedores_por_material)
    best_offer = _best_offer(offers)
    material_updates: dict[str, Any] = {}

    if offers:
        material_updates["lista_fornecedores"] = offers

    if update_payload.get("justificativa") not in (None, ""):
        material_updates["justificativa"] = update_payload["justificativa"]

    if best_offer is None and bool(update_payload.get("fornecedor")):
        for field in (
            "fornecedor",
            "valor_unitario",
            "valor_total",
            "preco_a_vista",
            "preco_a_prazo",
            "num_parcelas",
            "frete",
        ):
            value = update_payload.get(field)
            if value not in (None, ""):
                material_updates[field] = value

    if best_offer is not None:
        best_values = {
            "fornecedor": best_offer.fornecedor,
            "valor_unitario": best_offer.valor_unitario,
            "valor_total": best_offer.valor_total,
            "preco_a_vista": best_offer.preco_a_vista,
            "preco_a_prazo": best_offer.preco_a_prazo,
            "num_parcelas": best_offer.num_parcelas,
            "frete": best_offer.frete,
        }
        for field, value in best_values.items():
            if value not in (None, ""):
                material_updates[field] = value

    return material.model_copy(update=material_updates)


def reason_about_material_suppliers(
    agent,
    area_name: str,
    material: MaterialObra,
    thread_id: str,
    max_fornecedores_por_material: int = 3,
) -> dict:
    _log_reasoning_event(
        f"Starting supplier reasoning thread={thread_id}",
        {
            "area": area_name,
            "material": material.model_dump(mode="json"),
        },
    )
    result = agent.invoke(
        {
            "messages": [
                SystemMessage(content=SUPPLIER_REASONING_SYSTEM_PROMPT),
                HumanMessage(
                    content=_material_prompt(
                        area_name=area_name,
                        material=material,
                        max_fornecedores_por_material=max_fornecedores_por_material,
                    )
                ),
            ]
        },
        config={"configurable": {"thread_id": thread_id}},
    )
    update_payload = _extract_json_object(_message_text(result["messages"][-1]))
    tool_offers = _supplier_tool_offer_payloads(result.get("messages", []))
    if tool_offers:
        update_payload = _merge_supplier_offer_payloads(update_payload, tool_offers)
        _log_reasoning_event(
            "Merged supplier search tool offers",
            {
                "tool_offers": len(tool_offers),
                "merged_offers": len(update_payload.get("lista_fornecedores", [])),
            },
        )
    _log_reasoning_event("Extracted supplier update JSON", update_payload)
    return update_payload


def preencher_fornecedores_com_reasoning_agent(
    lista_materiais: ListaMateriaisObra,
    reasoning_llm=None,
    supplier_search_tools: list | None = None,
    max_materials: int | None = None,
    max_fornecedores_por_material: int | None = None,
    max_materiais_processados: int | None = None,
) -> ListaMateriaisObra:
    """Receive ListaMateriaisObra, run the ReAct reasoning agent, and fill supplier fields.

    max_materials is kept as the public shortcut for how many offers to keep in
    each material.lista_fornecedores. Use max_materiais_processados only when
    you need to limit how many materials from ListaMateriaisObra are processed.
    """

    offer_limit = (
        max_fornecedores_por_material
        if max_fornecedores_por_material is not None
        else max_materials
    )
    if offer_limit is None:
        offer_limit = 3
    offer_limit = max(int(offer_limit), 0)
    material_processing_limit = max_materiais_processados

    agent = build_supplier_reasoning_agent(
        reasoning_llm=reasoning_llm or build_openai_chat_model(),
        supplier_search_tools=supplier_search_tools,
        checkpointer=MemorySaver(),
    )
    _log_reasoning_event(
        "Supplier fill limits",
        {
            "max_fornecedores_por_material": offer_limit,
            "max_materiais_processados": material_processing_limit,
        },
    )

    processed = 0
    updated_areas = []
    for area_index, area in enumerate(lista_materiais.areas):
        updated_materials = []
        for material_index, material in enumerate(area.materiais):
            if material_processing_limit is not None and processed >= material_processing_limit:
                updated_materials.append(material)
                continue

            thread_id = (
                f"supplier-reasoning-{area_index}-{material_index}-"
                f"{hashlib.md5(material.nome.encode()).hexdigest()}"
            )
            _log_reasoning_event(
                "Processing material",
                {
                    "index": processed + 1,
                    "area": area.area,
                    "nome": material.nome,
                    "medida": material.medida,
                    "quantidade": material.quantidade,
                    "perfil": material.perfil_produto,
                },
            )
            update_payload = reason_about_material_suppliers(
                agent=agent,
                area_name=area.area,
                material=material,
                thread_id=thread_id,
                max_fornecedores_por_material=offer_limit,
            )
            complementary_offers = _missing_relevant_supplier_tool_offers(
                supplier_search_tools=supplier_search_tools,
                area_name=area.area,
                material=material,
                update_payload=update_payload,
            )
            if complementary_offers:
                update_payload = _merge_supplier_offer_payloads(
                    update_payload,
                    complementary_offers,
                )
                _log_reasoning_event(
                    "Merged complementary supplier offers",
                    {
                        "complementary_offers": len(complementary_offers),
                        "merged_offers": len(update_payload.get("lista_fornecedores", [])),
                    },
                )
            updated_material = _apply_supplier_update(
                material=material,
                update_payload=update_payload,
                max_fornecedores_por_material=offer_limit,
            )
            _log_reasoning_event(
                "Applied supplier update",
                updated_material.model_dump(mode="json"),
            )
            updated_materials.append(updated_material)
            processed += 1

        updated_areas.append(area.model_copy(update={"materiais": updated_materials}))

    return lista_materiais.model_copy(update={"areas": updated_areas})
