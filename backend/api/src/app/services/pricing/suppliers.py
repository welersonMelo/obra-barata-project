"""Supplier search integrations used by the pricing flow."""

# coverage: ignore file

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from difflib import SequenceMatcher
from typing import Any, Protocol
from urllib.parse import quote, quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.models.materials import MaterialObra, OfertaFornecedor
from app.settings import get_settings


logger = logging.getLogger(__name__)

DEFAULT_SCRAPING_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

PISOLAR_BASE_URL = "https://www.pisolar.com.br/"
COMERCIAL_ALIANCA_BASE_URL = "https://www.comercialalianca.com/"
COMERCIAL_ALIANCA_STORE_ID = "1387054"
CASA_ELETRICIDADE_BASE_URL = "https://www.casadaeletricidade.com.br/"


class SupplierSearchError(RuntimeError):
    """Raised when a supplier search cannot be completed."""


class SupplierProvider(Protocol):
    """Common interface for supplier search providers."""

    name: str

    async def search(
        self,
        product_name: str,
        unit: str = "",
        quantity: float | None = None,
        profile: str = "Medio custo",
        limit: int = 5,
    ) -> list[OfertaFornecedor]:
        """Search offers for a material."""


class SupplierHttpClient:
    """Small HTTP client wrapper with storefront-friendly defaults."""

    def __init__(self, timeout_seconds: int | None = None) -> None:
        settings = get_settings()
        self.timeout_seconds = timeout_seconds or settings.SUPPLIER_SEARCH_TIMEOUT_SECONDS

    async def get_html(self, url: str) -> str:
        """Fetch HTML from a storefront page."""

        logger.info("supplier_http_html_request url=%s timeout=%s", url, self.timeout_seconds)
        async with httpx.AsyncClient(
            headers=DEFAULT_SCRAPING_HEADERS,
            follow_redirects=True,
            timeout=self.timeout_seconds,
        ) as client:
            response = await client.get(url)
        logger.info(
            "supplier_http_html_response url=%s status_code=%s content_type=%s bytes=%s",
            url,
            response.status_code,
            response.headers.get("content-type"),
            len(response.content or b""),
        )
        response.raise_for_status()
        return response.text

    async def get_json(self, url: str) -> Any:
        """Fetch JSON from a supplier endpoint."""

        logger.info("supplier_http_json_request url=%s timeout=%s", url, self.timeout_seconds)
        async with httpx.AsyncClient(
            headers=DEFAULT_SCRAPING_HEADERS,
            follow_redirects=True,
            timeout=self.timeout_seconds,
        ) as client:
            response = await client.get(url)
        logger.info(
            "supplier_http_json_response url=%s status_code=%s content_type=%s bytes=%s",
            url,
            response.status_code,
            response.headers.get("content-type"),
            len(response.content or b""),
        )
        response.raise_for_status()
        return response.json()

    async def post_json(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> Any:
        """Post JSON and return the decoded response."""

        logger.info("supplier_http_json_post url=%s timeout=%s", url, self.timeout_seconds)
        async with httpx.AsyncClient(
            headers={**DEFAULT_SCRAPING_HEADERS, **headers},
            follow_redirects=True,
            timeout=self.timeout_seconds,
        ) as client:
            response = await client.post(url, json=payload)
        logger.info(
            "supplier_http_json_post_response url=%s status_code=%s bytes=%s",
            url,
            response.status_code,
            len(response.content or b""),
        )
        response.raise_for_status()
        return response.json()


def clean_scraped_text(value: Any) -> str:
    """Normalize whitespace from scraped text."""

    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_search_text(value: str | None) -> str:
    """Normalize text for accent-insensitive matching."""

    normalized = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_accents.casefold()).strip()


def text_match_score(query: str, *texts: str | None) -> float:
    """Score how well scraped texts match a query."""

    query_normalized = normalize_search_text(query)
    haystack = normalize_search_text(" ".join(text for text in texts if text))
    if not query_normalized:
        return 1.0
    if not haystack:
        return 0.0

    query_tokens = set(query_normalized.split())
    haystack_tokens = set(haystack.split())
    token_score = len(query_tokens & haystack_tokens) / max(len(query_tokens), 1)
    sequence_score = SequenceMatcher(None, query_normalized, haystack).ratio()
    return max(token_score, sequence_score)


UNIT_AND_PACKAGING_QUERY_TOKENS = {
    "caixa",
    "cx",
    "fardo",
    "g",
    "kg",
    "kilo",
    "kilos",
    "l",
    "litro",
    "litros",
    "m",
    "m2",
    "m3",
    "metro",
    "metros",
    "ml",
    "pacote",
    "rolo",
    "saco",
    "un",
    "und",
    "unidade",
    "unidades",
}

PRODUCT_QUERY_STOPWORDS = {
    "a",
    "ao",
    "aos",
    "as",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "na",
    "nas",
    "no",
    "nos",
    "o",
    "os",
    "para",
    "por",
    "sem",
}


def _meaningful_query_tokens(query: str | None) -> set[str]:
    """Return query tokens that should appear in a product title."""

    tokens = set(normalize_search_text(query).split())
    return {
        token
        for token in tokens
        if len(token) >= 3
        and not any(char.isdigit() for char in token)
        and token not in UNIT_AND_PACKAGING_QUERY_TOKENS
        and token not in PRODUCT_QUERY_STOPWORDS
    }


def _tokens_match_flexibly(query_token: str, title_token: str) -> bool:
    """Compare product tokens while tolerating short singular/plural variations."""

    if query_token == title_token:
        return True
    shorter, longer = sorted([query_token, title_token], key=len)
    return len(shorter) >= 5 and len(longer) - len(shorter) <= 2 and longer.startswith(shorter)


def _title_matches_material_query(query: str, title: str | None) -> bool:
    """Return whether a scraped title is related to the searched material."""

    query_tokens = _meaningful_query_tokens(query)
    if not query_tokens:
        return True
    normalized_title = normalize_search_text(title)
    title_tokens = set(normalized_title.split())

    # A pipe search can otherwise accept accessories such as "abracadeira para
    # tubo" because they repeat some of the requested pipe attributes.
    pipe_query_tokens = {"tubo", "cano"}
    if query_tokens & pipe_query_tokens:
        accessory_prefixes = (
            "abracadeira",
            "adaptador",
            "cap",
            "conexao",
            "joelho",
            "luva",
            "reducao",
            "registro",
            "te",
            "tampa",
            "uniao",
            "valvula",
        )
        if any(normalized_title.startswith(f"{prefix} ") for prefix in accessory_prefixes):
            return False

    return any(
        _tokens_match_flexibly(query_token, title_token)
        for query_token in query_tokens
        for title_token in title_tokens
    )


def _format_query_quantity(quantity: float | int | str | None) -> str:
    """Format quantity for storefront search terms."""

    if quantity is None or quantity == "":
        return ""
    try:
        numeric_quantity = float(quantity)
    except (TypeError, ValueError):
        return str(quantity).strip().replace(".", ",")
    if numeric_quantity.is_integer():
        return str(int(numeric_quantity))
    return str(numeric_quantity).rstrip("0").rstrip(".").replace(".", ",")


def _compact_unit_for_query(unit: str | None) -> str:
    """Convert verbose units into compact search tokens, e.g. litros -> L."""

    if not unit:
        return ""
    normalized_unit = normalize_search_text(unit.strip().replace("\u00b2", "2"))
    compact_units = {
        "l": "L",
        "lt": "L",
        "lts": "L",
        "litro": "L",
        "litros": "L",
        "ml": "ml",
        "mililitro": "ml",
        "mililitros": "ml",
        "kg": "kg",
        "quilo": "kg",
        "quilos": "kg",
        "kilo": "kg",
        "kilos": "kg",
        "quilograma": "kg",
        "quilogramas": "kg",
        "g": "g",
        "grama": "g",
        "gramas": "g",
        "m2": "m2",
        "metro quadrado": "m2",
        "metros quadrados": "m2",
        "m3": "m3",
        "metro cubico": "m3",
        "metros cubicos": "m3",
        "m": "m",
        "metro": "m",
        "metros": "m",
        "un": "un",
        "und": "un",
        "unidade": "un",
        "unidades": "un",
    }
    return compact_units.get(normalized_unit, unit.strip())


def compact_quantity_unit_for_query(
    quantity: float | int | str | None,
    unit: str = "",
) -> str:
    """Join quantity and unit in the storefront-friendly form, e.g. 30 + litros -> 30L."""

    quantity_text = _format_query_quantity(quantity)
    compact_unit = _compact_unit_for_query(unit)
    if quantity_text and compact_unit:
        return f"{quantity_text}{compact_unit}"
    if quantity_text:
        return quantity_text
    return compact_unit


def build_supplier_site_query(
    product_name: str,
    unit: str = "",
    quantity: float | None = None,
) -> str:
    """Build a search query like the storefront search bar would receive."""

    query_parts = [product_name]
    quantity_unit = compact_quantity_unit_for_query(quantity=quantity, unit=unit)
    if quantity_unit:
        query_parts.append(quantity_unit)
    return " ".join(str(part).strip() for part in query_parts if str(part).strip())


def build_supplier_search_queries(
    product_name: str,
    unit: str = "",
    quantity: float | None = None,
) -> list[str]:
    """Build increasingly broad storefront search queries."""

    return list(
        dict.fromkeys(
            [
                build_supplier_site_query(
                    product_name=product_name,
                    unit=unit,
                    quantity=quantity,
                ),
                build_supplier_site_query(
                    product_name=product_name,
                    unit="",
                    quantity=quantity,
                ),
                build_supplier_site_query(
                    product_name=product_name,
                    unit=unit,
                    quantity=None,
                ),
                product_name.strip(),
            ]
        )
    )


CONSTRUCTION_SEARCH_CONTEXT_PHRASES = (
    "pintura interna",
    "pintura externa",
    "pintura de parede",
    "pintura para parede",
    "para paredes internas",
    "para paredes externas",
    "paredes internas",
    "paredes externas",
    "uso interno",
    "uso externo",
    "preenchimento de juntas",
    "revestimento ceramico",
    "revestimento ceramicos",
    "revestimentos ceramicos",
)

CONSTRUCTION_SEARCH_CONTEXT_TOKENS = {
    "acabamento",
    "acabamentos",
    "ambiente",
    "ambientes",
    "area",
    "areas",
    "ceramico",
    "ceramicos",
    "externa",
    "externas",
    "externo",
    "externos",
    "interna",
    "internas",
    "interno",
    "internos",
    "obra",
    "obras",
    "parede",
    "paredes",
    "para",
    "pintura",
    "preenchimento",
    "revestimento",
    "revestimentos",
    "uso",
}

PRODUCT_IDENTITY_HINTS = {
    "acrilica",
    "acrilico",
    "argamassa",
    "cimento",
    "concreto",
    "dobradica",
    "eletroduto",
    "fio",
    "rejunte",
    "selador",
    "tinta",
    "tomada",
}


def _component_without_parentheses(text: str) -> str:
    """Remove parenthetical details from a text component."""

    return clean_scraped_text(re.sub(r"\([^)]*\)", " ", text or ""))


def _parenthetical_components(text: str) -> list[str]:
    """Return non-empty parenthetical components from text."""

    return [
        clean_scraped_text(match)
        for match in re.findall(r"\(([^)]*)\)", text or "")
        if clean_scraped_text(match)
    ]


def _has_product_identity_hint(text: str | None) -> bool:
    normalized_tokens = set(normalize_search_text(text).split())
    return any(
        any(_tokens_match_flexibly(hint, token) for token in normalized_tokens)
        for hint in PRODUCT_IDENTITY_HINTS
    )


def _clean_product_search_component(text: str | None) -> str:
    """Remove obra/category context that tends to hurt storefront search."""

    cleaned = clean_scraped_text(text)
    if not cleaned:
        return ""

    for phrase in CONSTRUCTION_SEARCH_CONTEXT_PHRASES:
        cleaned = re.sub(
            rf"\b{re.escape(phrase)}\b",
            " ",
            cleaned,
            flags=re.IGNORECASE,
        )

    meaningful_tokens = _meaningful_query_tokens(cleaned)
    if meaningful_tokens and any(
        _tokens_match_flexibly("tinta", token)
        or _tokens_match_flexibly("rejunte", token)
        or _tokens_match_flexibly("argamassa", token)
        for token in meaningful_tokens
    ):
        words = []
        for word in cleaned.split():
            normalized_word = normalize_search_text(word)
            if normalized_word in CONSTRUCTION_SEARCH_CONTEXT_TOKENS:
                continue
            words.append(word)
        cleaned = " ".join(words)

    cleaned = re.sub(r"\s*[-,/]\s*$", "", cleaned)
    return clean_scraped_text(cleaned)


def _select_product_search_base(nome: str, descricao: str = "") -> str:
    """Choose the most product-like part of a material name/description."""

    name = clean_scraped_text(nome)
    description = clean_scraped_text(descricao)
    parenthetical_parts = _parenthetical_components(name)
    for part in parenthetical_parts:
        if _has_product_identity_hint(part):
            return _clean_product_search_component(part)

    name_without_parentheses = _component_without_parentheses(name)
    cleaned_name = _clean_product_search_component(name_without_parentheses)
    if _has_product_identity_hint(cleaned_name):
        return cleaned_name

    cleaned_description = _clean_product_search_component(description)
    if _has_product_identity_hint(cleaned_description):
        return cleaned_description

    return cleaned_name or cleaned_description or name


def _format_package_amount(amount_text: str, suffix: str) -> str:
    amount = amount_text.replace(",", ".")
    try:
        numeric_amount = float(amount)
    except ValueError:
        return f"{amount_text}{suffix}"
    if numeric_amount.is_integer():
        amount = str(int(numeric_amount))
    else:
        amount = str(numeric_amount).rstrip("0").rstrip(".").replace(".", ",")
    return f"{amount}{suffix}"


def _package_size_for_search(medida: str | None) -> str:
    """Extract commercial package size from units like 'lata 18 L' or 'saco 1 kg'."""

    if not medida:
        return ""
    normalized_measure = (medida or "").replace("\u00b2", "2")
    package_patterns = [
        (r"(\d+(?:[\.,]\d+)?)\s*(?:litros?|lts?|lt|l)\b", "L"),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:quilogramas?|kilos?|kg)\b", "kg"),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:gramas?|g)\b", "g"),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:mililitros?|ml)\b", "ml"),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:metros?\s*quadrados?|m2)\b", "m2"),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:metros?\s*cubicos?|m3)\b", "m3"),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:metros?|m)\b", "m"),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:unidades?|und|un)\b", "un"),
    ]
    for pattern, suffix in package_patterns:
        match = re.search(pattern, normalized_measure, flags=re.IGNORECASE)
        if match:
            return _format_package_amount(match.group(1), suffix)
    return ""


def build_product_search_text(
    nome: str,
    descricao: str = "",
    quantidade: float | int | None = None,
    medida: str = "",
    fornecedor: str = "",
) -> str:
    """Build one concise storefront search text for a material."""

    base = _select_product_search_base(nome=nome, descricao=descricao)
    package_size = _package_size_for_search(medida)
    base_package_size = _package_size_for_search(base)
    parts = [base]
    if package_size and normalize_search_text(package_size) != normalize_search_text(
        base_package_size
    ):
        parts.append(package_size)
    return clean_scraped_text(" ".join(part for part in parts if part))


def parse_brazilian_price(price_text: str | None) -> float | None:
    """Parse a Brazilian currency string into float."""

    if not price_text:
        return None
    price_match = re.search(r"\d[\d\.]*,\d{2}", price_text)
    if not price_match:
        return None
    normalized = price_match.group(0).replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except ValueError:
        return None


def _coerce_price(value: Any) -> float | None:
    """Coerce a scraped price-like value into float."""

    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if not text:
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return parse_brazilian_price(text)


def _secure_same_site_url(base_url: str, raw_url: str | None) -> str | None:
    """Build an absolute same-site URL and prefer https."""

    if not raw_url:
        return None
    absolute_url = urljoin(base_url, raw_url)
    if absolute_url.startswith("http://"):
        absolute_url = "https://" + absolute_url[len("http://") :]
    return absolute_url


def _same_site_url(url: str, base_url: str) -> bool:
    """Return whether url belongs to the same storefront host."""

    url_host = urlparse(url).netloc.replace("www.", "")
    base_host = urlparse(base_url).netloc.replace("www.", "")
    return bool(url_host and base_host and url_host == base_host)


def _infer_brand_from_title(title: str | None) -> str | None:
    """Infer brand from common title suffixes, e.g. Produto - CORAL."""

    if not title or " - " not in title:
        return None
    candidate = title.rsplit(" - ", 1)[-1].strip()
    if 2 <= len(candidate) <= 30:
        return candidate
    return None


def infer_commercial_unit(text: str | None, fallback_unit: str = "") -> str | None:
    """Infer commercial package unit from product text."""

    if not text:
        return fallback_unit or None

    normalized_text = text.replace("\u00b2", "2")
    unit_patterns = [
        (r"(\d+(?:[\.,]\d+)?)\s*(?:mililitros?|ml)\b", "ml"),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:litros?|lts?|lt|l)\b", "L"),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:quilogramas?|kilos?|kg)\b", "kg"),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:gramas?|g)\b", "g"),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:metros?\s*quadrados?|m2)\b", "m2"),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:metros?\s*cubicos?|m3)\b", "m3"),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:metros?|m)\b", "m"),
        (r"(\d+(?:[\.,]\d+)?)\s*(?:unidades?|und|un)\b", "un"),
    ]

    for pattern, suffix in unit_patterns:
        match = re.search(pattern, normalized_text, flags=re.IGNORECASE)
        if match:
            amount = match.group(1).replace(",", ".")
            return f"{amount} {suffix}"

    return fallback_unit or None


def _parse_amount_unit(unit_text: str | None) -> tuple[float | None, str | None]:
    """Parse an amount/unit pair into a normalized family."""

    if not unit_text:
        return None, None

    text = unit_text.casefold().replace(",", ".").replace("\u00b2", "2")
    patterns = [
        (r"(\d+(?:\.\d+)?)\s*(?:m3|metros?\s+cubicos?)\b", "m3", 1),
        (r"(\d+(?:\.\d+)?)\s*(?:m2|metros?\s+quadrados?)\b", "m2", 1),
        (r"(\d+(?:\.\d+)?)\s*(?:ml|mililitros?)\b", "L", 0.001),
        (r"(\d+(?:\.\d+)?)\s*(?:litros?|lts?|lt|l)\b", "L", 1),
        (r"(\d+(?:\.\d+)?)\s*(?:gramas?|g)\b", "kg", 0.001),
        (r"(\d+(?:\.\d+)?)\s*(?:quilogramas?|kilos?|kg)\b", "kg", 1),
        (r"(\d+(?:\.\d+)?)\s*(?:metros?|m)\b", "m", 1),
        (r"(\d+(?:\.\d+)?)\s*(?:unidades?|und|un)\b", "un", 1),
    ]
    for pattern, family, multiplier in patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1)) * multiplier, family
    if re.search(r"\b(?:unidades?|und|un)\b", text):
        return 1, "un"
    return None, None


def _parse_unit_family(unit_text: str | None) -> str | None:
    """Infer the normalized unit family for a material unit."""

    _amount, family = _parse_amount_unit(f"1 {unit_text}" if unit_text else None)
    return family


_COMMERCIAL_PACKAGE_TYPES = (
    ("saco", ("saco", "sacos")),
    ("lata", ("lata", "latas")),
    ("caixa", ("caixa", "caixas", "cx")),
    ("pacote", ("pacote", "pacotes", "pct", "pcts")),
    ("rolo", ("rolo", "rolos")),
    ("fardo", ("fardo", "fardos")),
    ("galao", ("galao", "galoes")),
    ("balde", ("balde", "baldes")),
    ("barra", ("barra", "barras")),
)


def _commercial_package_type(unit_text: str | None) -> str | None:
    """Return the package type explicitly stated in a commercial unit."""

    tokens = set(normalize_search_text(unit_text).split())
    for package_type, aliases in _COMMERCIAL_PACKAGE_TYPES:
        if tokens.intersection(aliases):
            return package_type
    return None


def purchase_quantity_for_material(
    required_quantity: float | int | None,
    required_unit: str | None,
    offer_unit: str | None,
) -> int | None:
    """Calculate purchase packages without treating package counts as base units.

    For example, "8 barra 6 m" means eight commercial bars, not eight metres.
    """

    if required_quantity is None or required_quantity <= 0 or not required_unit or not offer_unit:
        return None

    required_package_type = _commercial_package_type(required_unit)
    offer_package_type = _commercial_package_type(offer_unit)
    required_size, required_family = _parse_amount_unit(required_unit)
    offer_size, offer_family = _parse_amount_unit(offer_unit)

    if required_package_type:
        if required_package_type == offer_package_type:
            return math.ceil(float(required_quantity))
        if (
            required_size is not None
            and offer_size is not None
            and required_family == offer_family
            and math.isclose(required_size, offer_size, rel_tol=0, abs_tol=0.001)
        ):
            return math.ceil(float(required_quantity))
        return None

    if (
        required_family
        and offer_family
        and required_family == offer_family
        and offer_size
    ):
        return math.ceil(float(required_quantity) / offer_size)
    return None


def _extract_js_array_assignment(script_text: str, variable_name: str) -> str | None:
    """Extract a JavaScript array assigned to variable_name from a script string."""

    assignment = re.search(rf"\b{re.escape(variable_name)}\s*=", script_text)
    if not assignment:
        return None
    start = script_text.find("[", assignment.end())
    if start == -1:
        return None

    depth = 0
    in_string = False
    quote_char = ""
    escaped = False
    for position, char in enumerate(script_text[start:], start=start):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote_char:
                in_string = False
            continue

        if char in {'"', "'"}:
            in_string = True
            quote_char = char
        elif char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return script_text[start : position + 1]
    return None


def _parse_html(html: str) -> BeautifulSoup:
    """Parse HTML into a BeautifulSoup document."""

    return BeautifulSoup(html, "html.parser")


def _extract_tray_datalayer_products(html: str) -> list[dict]:
    """Extract Tray dataLayer listProducts entries from a search/category page."""

    soup = _parse_html(html)
    products: list[dict] = []
    for script in soup.find_all("script"):
        script_text = script.string or script.get_text("\n")
        if "dataLayer" not in script_text or "listProducts" not in script_text:
            continue
        array_text = _extract_js_array_assignment(script_text, "dataLayer")
        if not array_text:
            continue
        try:
            data_layer = json.loads(array_text)
        except json.JSONDecodeError as exc:
            logger.warning("tray_datalayer_parse_failed error=%s", exc)
            continue
        if not isinstance(data_layer, list):
            continue
        for item in data_layer:
            if isinstance(item, dict) and isinstance(item.get("listProducts"), list):
                products.extend(
                    product for product in item["listProducts"] if isinstance(product, dict)
                )
    return products


def _tray_datalayer_product_to_offer(
    product: dict,
    supplier_name: str,
    base_url: str,
    fallback_unit: str = "",
    default_installments: int | None = None,
) -> OfertaFornecedor | None:
    """Convert a Tray listProducts item into an offer."""

    title = clean_scraped_text(product.get("nameProduct") or product.get("item_name") or "")
    if not title:
        return None
    link_produto = _secure_same_site_url(
        base_url,
        product.get("urlProduct") or product.get("item_url"),
    )
    combined_text = " ".join(
        clean_scraped_text(value)
        for value in [
            title,
            product.get("category"),
            product.get("item_category"),
            product.get("item_category2"),
        ]
        if value
    )
    availability = product.get("availability")
    disponibilidade = (
        "Disponivel"
        if availability in ("YES", "IN_STOCK", True)
        else "Indisponivel"
        if availability
        else None
    )
    return OfertaFornecedor(
        fornecedor=supplier_name,
        descricao=title,
        marca=product.get("brand") or product.get("item_brand") or _infer_brand_from_title(title),
        unidade=infer_commercial_unit(combined_text, fallback_unit),
        valor_unitario=_coerce_price(product.get("sellPrice") or product.get("price")),
        num_parcelas=default_installments,
        disponibilidade=disponibilidade or "Produto encontrado na busca do fornecedor.",
        data_consulta=date.today().isoformat(),
        link_produto=link_produto,
    )


def _scrape_tray_datalayer_offers(
    html: str,
    query: str,
    supplier_name: str,
    base_url: str,
    fallback_unit: str = "",
    default_installments: int | None = None,
    limit: int = 5,
) -> list[OfertaFornecedor]:
    """Build supplier offers from Tray dataLayer products."""

    products = _extract_tray_datalayer_products(html)
    logger.info(
        "tray_datalayer_products_extracted supplier=%s query=%s products=%s",
        supplier_name,
        query,
        len(products),
    )
    offers = []
    for product in products:
        offer = _tray_datalayer_product_to_offer(
            product=product,
            supplier_name=supplier_name,
            base_url=base_url,
            fallback_unit=fallback_unit,
            default_installments=default_installments,
        )
        if offer and _title_matches_material_query(query, offer.descricao):
            offers.append(offer)
    return sorted(
        offers,
        key=lambda offer: text_match_score(query, offer.descricao, offer.unidade),
        reverse=True,
    )[:limit]


def _scrape_schema_org_product_offers(
    html: str,
    query: str,
    supplier_name: str,
    base_url: str,
    fallback_unit: str = "",
    availability_text: str = "Produto encontrado na busca do fornecedor.",
    default_installments: int | None = None,
    limit: int = 5,
) -> list[OfertaFornecedor]:
    """Build offers from schema.org Product cards in storefront HTML."""

    soup = _parse_html(html)
    containers = soup.select(".product-box, [itemscope][itemtype*='Product']")
    offers_by_url: dict[str, OfertaFornecedor] = {}

    for container in containers:
        title_node = (
            container.select_one('[itemprop="name"] strong')
            or container.select_one('[itemprop="name"]')
            or container.select_one(".product-name")
        )
        title = clean_scraped_text(title_node.get_text(" ") if title_node else "")
        if len(title) < 8:
            continue
        if not _title_matches_material_query(query, title):
            continue

        meta_url = container.select_one('meta[itemprop="url"][content]')
        link_node = (
            container.select_one('a[itemprop="url"][href]')
            or container.select_one("a.product-name[href]")
            or container.select_one("a[href]")
        )
        raw_url = (
            meta_url.get("content")
            if meta_url
            else link_node.get("href")
            if link_node
            else None
        )
        link_produto = _secure_same_site_url(base_url, raw_url)
        if not link_produto or not _same_site_url(link_produto, base_url):
            continue

        brand_node = (
            container.select_one('[itemprop="brand"] [itemprop="name"]')
            or container.select_one('[itemprop="brand"]')
        )
        brand = clean_scraped_text(
            brand_node.get_text(" ") if brand_node else ""
        ) or _infer_brand_from_title(title)
        price_meta = container.select_one(
            '[itemprop="offers"] meta[itemprop="price"][content], '
            'meta[itemprop="price"][content]'
        )
        price = _coerce_price(price_meta.get("content") if price_meta else None)

        container_text = clean_scraped_text(container.get_text(" "))
        class_text = " ".join(container.get("class", [])).casefold()
        availability = (
            "Indisponivel"
            if "not-available" in class_text or "esgotado" in container_text.casefold()
            else availability_text
        )
        combined_text = " ".join([title, brand or "", container_text])
        offers_by_url.setdefault(
            link_produto,
            OfertaFornecedor(
                fornecedor=supplier_name,
                descricao=title,
                marca=brand or None,
                unidade=infer_commercial_unit(combined_text, fallback_unit),
                valor_unitario=price,
                num_parcelas=default_installments,
                disponibilidade=availability,
                data_consulta=date.today().isoformat(),
                link_produto=link_produto,
            ),
        )

    offers = sorted(
        offers_by_url.values(),
        key=lambda offer: text_match_score(query, offer.descricao, offer.unidade),
        reverse=True,
    )
    logger.info(
        "schema_org_product_offers_extracted supplier=%s query=%s offers=%s",
        supplier_name,
        query,
        len(offers),
    )
    return offers[:limit]


MAX_PRODUCT_CONTAINER_TEXT_CHARS = 1600
STOREFRONT_CHROME_ANCESTOR_CLASSES = (
    "breadcrumb",
    "categor",
    "departament",
    "filter",
    "footer",
    "header",
    "menu",
    "nav",
    "sidebar",
)


def _is_storefront_chrome_node(node) -> bool:
    """Return whether a node is likely navigation, filters, or layout chrome."""

    node_name = (getattr(node, "name", "") or "").casefold()
    if node_name in {"header", "footer", "nav", "aside"}:
        return True
    class_text = " ".join(getattr(node, "get", lambda *_: [])("class", [])).casefold()
    node_id = str(getattr(node, "get", lambda *_: "")("id", "")).casefold()
    haystack = f"{class_text} {node_id}"
    return any(marker in haystack for marker in STOREFRONT_CHROME_ANCESTOR_CLASSES)


def _candidate_container_text(anchor) -> str:
    """Climb from an anchor and return nearby text containing a price."""

    node = anchor
    fallback_text = clean_scraped_text(anchor.get_text(" "))
    for _level in range(5):
        if node is None:
            break
        if node is not anchor and _is_storefront_chrome_node(node):
            break
        text = clean_scraped_text(node.get_text(" "))
        if "R$" in text and len(text) <= MAX_PRODUCT_CONTAINER_TEXT_CHARS:
            return text
        node = getattr(node, "parent", None)
    return fallback_text


def _title_from_candidate_text(anchor_text: str, container_text: str) -> str:
    """Extract a product title from anchor/container text."""

    source_text = anchor_text if anchor_text and "R$" not in anchor_text else container_text
    title = re.split(r"\s+R\$\s*", source_text, maxsplit=1)[0]
    title = re.sub(r"\s+Por:\s*$", "", title, flags=re.IGNORECASE)
    return clean_scraped_text(title)


def _scrape_storefront_search_offers(
    html: str,
    query: str,
    base_url: str,
    supplier_name: str,
    fallback_unit: str = "",
    availability_text: str = "Produto encontrado na busca do fornecedor.",
    default_installments: int | None = None,
    limit: int = 5,
) -> list[OfertaFornecedor]:
    """Generic HTML storefront scraper for visible price cards."""

    soup = _parse_html(html)
    offers_by_url: dict[str, OfertaFornecedor] = {}
    for anchor in soup.find_all("a", href=True):
        absolute_url = urljoin(base_url, anchor.get("href"))
        if not _same_site_url(absolute_url, base_url):
            continue
        if "/loja/busca.php" in absolute_url or "javascript:" in absolute_url:
            continue

        anchor_text = clean_scraped_text(anchor.get_text(" "))
        container_text = _candidate_container_text(anchor)
        price = parse_brazilian_price(container_text)
        if price is None:
            continue

        title = _title_from_candidate_text(anchor_text, container_text)
        if len(title) < 8:
            continue
        if not _title_matches_material_query(query, title):
            continue
        if normalize_search_text(title) in {"comprar", "adicionar ao carrinho", "produto"}:
            continue
        if absolute_url in offers_by_url:
            continue

        combined_text = " ".join([title, container_text])
        offers_by_url[absolute_url] = OfertaFornecedor(
            fornecedor=supplier_name,
            descricao=title,
            marca=_infer_brand_from_title(title),
            unidade=infer_commercial_unit(combined_text, fallback_unit),
            valor_unitario=price,
            num_parcelas=default_installments,
            disponibilidade=availability_text,
            data_consulta=date.today().isoformat(),
            link_produto=absolute_url,
        )
        if len(offers_by_url) >= limit * 3:
            break

    offers = sorted(
        offers_by_url.values(),
        key=lambda offer: text_match_score(query, offer.descricao, offer.unidade),
        reverse=True,
    )
    logger.info(
        "storefront_html_offers_extracted supplier=%s query=%s offers=%s",
        supplier_name,
        query,
        len(offers),
    )
    return offers[:limit]


GENERIC_STOREFRONT_LINK_TEXTS = {
    "comprar",
    "adicionar ao carrinho",
    "espiar",
    "ver detalhes",
    "produto",
    "todos os produtos",
    "departamentos",
    "categorias",
    "marcas",
    "preco",
    "voltar a pagina inicial",
}


def _is_generic_storefront_text(text: str | None) -> bool:
    """Return whether text is storefront chrome instead of a product title."""

    normalized = normalize_search_text(text or "")
    if not normalized or normalized in GENERIC_STOREFRONT_LINK_TEXTS:
        return True
    generic_prefixes = (
        "product id",
        "product sku",
        "new in stock",
        "image",
        "input",
        "classificar por",
    )
    return normalized.startswith(generic_prefixes)


def _product_card_lines(anchor, max_levels: int = 5) -> tuple[list[str], bool]:
    """Return nearby product-card text lines and whether a product marker was found."""

    node = anchor
    fallback_lines = [clean_scraped_text(anchor.get_text(" "))]
    markers = ("product id", "product sku", "esgotado", "espiar", "comprar", "r$")
    for _level in range(max_levels):
        if node is None:
            break
        raw_lines = getattr(node, "get_text")("\n")
        lines = [clean_scraped_text(line) for line in raw_lines.splitlines()]
        lines = [line for line in lines if line]
        joined = " ".join(lines).lower()
        if any(marker in joined for marker in markers):
            return lines, True
        node = getattr(node, "parent", None)
    return [line for line in fallback_lines if line], False


def _best_title_from_product_lines(query: str, anchor_text: str, lines: list[str]) -> str:
    """Choose the most product-like title from a card's text lines."""

    candidates = []
    for raw_text in [anchor_text, *lines]:
        text = clean_scraped_text(raw_text)
        if len(text) < 8 or _is_generic_storefront_text(text):
            continue
        if re.fullmatch(r"R\$\s*\d[\d\.]*,\d{2}", text):
            continue
        title = _title_from_candidate_text(text, text)
        if len(title) < 8 or _is_generic_storefront_text(title):
            continue
        candidates.append(title)

    if not candidates:
        return ""
    return max(candidates, key=lambda title: (text_match_score(query, title), len(title)))


def _scrape_storefront_product_card_offers(
    html: str,
    query: str,
    base_url: str,
    supplier_name: str,
    fallback_unit: str = "",
    availability_text: str = "Produto encontrado na busca do fornecedor.",
    default_installments: int | None = None,
    limit: int = 5,
) -> list[OfertaFornecedor]:
    """Fallback scraper for product cards without visible prices."""

    soup = _parse_html(html)
    offers_by_url: dict[str, OfertaFornecedor] = {}
    for anchor in soup.find_all("a", href=True):
        absolute_url = urljoin(base_url, anchor.get("href"))
        if not _same_site_url(absolute_url, base_url):
            continue
        if "/loja/busca.php" in absolute_url or "javascript:" in absolute_url or "#" in absolute_url:
            continue

        anchor_text = clean_scraped_text(anchor.get_text(" "))
        lines, marker_found = _product_card_lines(anchor)
        if not marker_found:
            continue
        title = _best_title_from_product_lines(
            query=query,
            anchor_text=anchor_text,
            lines=lines,
        )
        if not title or text_match_score(query, title) <= 0:
            continue
        if not _title_matches_material_query(query, title):
            continue
        if absolute_url in offers_by_url:
            continue

        combined_text = " ".join([title, *lines])
        availability = "Esgotado" if "esgotado" in combined_text.lower() else availability_text
        offers_by_url[absolute_url] = OfertaFornecedor(
            fornecedor=supplier_name,
            descricao=title,
            marca=_infer_brand_from_title(title),
            unidade=infer_commercial_unit(combined_text, fallback_unit),
            valor_unitario=parse_brazilian_price(combined_text),
            num_parcelas=default_installments,
            disponibilidade=availability,
            data_consulta=date.today().isoformat(),
            link_produto=absolute_url,
        )
        if len(offers_by_url) >= limit * 3:
            break

    offers = sorted(
        offers_by_url.values(),
        key=lambda offer: text_match_score(query, offer.descricao, offer.unidade),
        reverse=True,
    )
    logger.info(
        "storefront_product_card_offers_extracted supplier=%s query=%s offers=%s",
        supplier_name,
        query,
        len(offers),
    )
    return offers[:limit]


class PisolarSupplier:
    """Search Pisolar using VTEX APIs and HTML fallback."""

    name = "Pisolar"

    def __init__(self, http_client: SupplierHttpClient | None = None) -> None:
        self.http_client = http_client or SupplierHttpClient()

    async def search(
        self,
        product_name: str,
        unit: str = "",
        quantity: float | None = None,
        profile: str = "Medio custo",
        limit: int = 5,
    ) -> list[OfertaFornecedor]:
        """Search Pisolar through its site search."""

        search_queries = build_supplier_search_queries(
            product_name=product_name,
            unit=unit,
            quantity=quantity,
        )
        logger.info(
            "pisolar_search_start product_name=%s unit=%s quantity=%s profile=%s queries=%s",
            product_name,
            unit,
            quantity,
            profile,
            search_queries,
        )
        selected_query = search_queries[0] if search_queries else product_name
        products: list[dict] = []
        for query in search_queries:
            selected_query = query
            products = await self._search_vtex_products(query=query, limit=limit)
            if products:
                break

        if products:
            return [
                self._product_to_offer(product, fallback_unit=unit)
                for product in products[:limit]
            ]
        return await self._scrape_search_page(query=selected_query, limit=limit)

    async def _search_vtex_products(self, query: str, limit: int = 5) -> list[dict]:
        """Search Pisolar VTEX public endpoints."""

        to_index = max(limit - 1, 0)
        encoded_query_param = quote_plus(query)
        encoded_path = quote(query, safe="")
        urls = [
            urljoin(
                PISOLAR_BASE_URL,
                "api/catalog_system/pub/products/search"
                f"?ft={encoded_query_param}&_from=0&_to={to_index}",
            ),
            urljoin(
                PISOLAR_BASE_URL,
                f"api/catalog_system/pub/products/search/{encoded_path}?_from=0&_to={to_index}",
            ),
        ]
        for url in urls:
            try:
                products = await self.http_client.get_json(url)
            except (httpx.HTTPError, json.JSONDecodeError) as exc:
                logger.warning(
                    "pisolar_vtex_endpoint_failed url=%s error_type=%s error=%s",
                    url,
                    type(exc).__name__,
                    exc,
                )
                continue
            if isinstance(products, list) and products:
                logger.info(
                    "pisolar_vtex_search_success query=%s products=%s",
                    query,
                    len(products),
                )
                return products[:limit]
        return []

    @staticmethod
    def _first_available_seller(item: dict) -> dict:
        """Return the first seller with stock, or the first seller."""

        sellers = item.get("sellers") or []
        if not sellers:
            return {}
        available = [
            seller
            for seller in sellers
            if ((seller.get("commertialOffer") or {}).get("AvailableQuantity") or 0) > 0
        ]
        return available[0] if available else sellers[0]

    def _best_vtex_item(self, product: dict) -> dict:
        """Return the lowest priced item from a VTEX product."""

        items = product.get("items") or []
        if not items:
            return {}
        priced_items = []
        for item in items:
            seller = self._first_available_seller(item)
            offer = seller.get("commertialOffer") or {}
            price = offer.get("Price")
            if price not in (None, 0):
                priced_items.append((price, item))
        if priced_items:
            return min(priced_items, key=lambda price_item: price_item[0])[1]
        return items[0]

    def _product_to_offer(
        self,
        product: dict,
        fallback_unit: str = "",
    ) -> OfertaFornecedor:
        """Convert a VTEX product into an offer."""

        item = self._best_vtex_item(product)
        seller = self._first_available_seller(item)
        commercial_offer = seller.get("commertialOffer") or {}
        title = product.get("productName") or item.get("nameComplete") or item.get("name") or ""
        description = clean_scraped_text(
            product.get("description") or product.get("metaTagDescription") or title
        )
        combined_text = " ".join(
            str(part)
            for part in [title, item.get("nameComplete"), item.get("complementName"), description]
            if part
        )
        price = commercial_offer.get("Price")
        if price in (None, 0):
            price = commercial_offer.get("spotPrice") or commercial_offer.get("ListPrice")
        installments = commercial_offer.get("Installments") or []
        installment_count = max(
            (installment.get("NumberOfInstallments", 0) for installment in installments),
            default=None,
        )
        available_quantity = commercial_offer.get("AvailableQuantity")
        return OfertaFornecedor(
            fornecedor=seller.get("sellerName") or "Grupo Pisolar",
            descricao=title,
            marca=product.get("brand"),
            unidade=infer_commercial_unit(combined_text, fallback_unit),
            valor_unitario=float(price) if price not in (None, "") else None,
            num_parcelas=installment_count or None,
            frete=0,
            disponibilidade=(
                "Disponivel"
                if available_quantity and available_quantity > 0
                else "Indisponivel"
            ),
            data_consulta=date.today().isoformat(),
            link_produto=product.get("link")
            or urljoin(PISOLAR_BASE_URL, f"{product.get('linkText', '')}/p"),
        )

    async def _scrape_search_page(
        self,
        query: str,
        limit: int = 5,
    ) -> list[OfertaFornecedor]:
        """Fallback scraper for Pisolar search pages."""

        search_url = urljoin(PISOLAR_BASE_URL, f"{quote(query, safe='')}?map=ft")
        html = await self.http_client.get_html(search_url)
        soup = _parse_html(html)
        product_links: list[dict[str, str]] = []
        seen_urls = set()
        for anchor in soup.find_all("a", href=True):
            absolute_url = urljoin(PISOLAR_BASE_URL, anchor.get("href"))
            if not re.search(r"/\d+/p(?:$|[?#])", absolute_url):
                continue
            if absolute_url in seen_urls:
                continue
            seen_urls.add(absolute_url)
            text = clean_scraped_text(anchor.get_text(" "))
            if text:
                product_links.append({"url": absolute_url, "title": text})
            if len(product_links) >= limit:
                break

        return [
            OfertaFornecedor(
                fornecedor="Grupo Pisolar",
                descricao=product["title"],
                unidade=infer_commercial_unit(product["title"]),
                disponibilidade="Produto encontrado na busca da Pisolar.",
                data_consulta=date.today().isoformat(),
                link_produto=product["url"],
            )
            for product in product_links
        ]


@dataclass
class TraySupplier:
    """Search a Tray storefront through its search page."""

    name: str
    base_url: str
    store_id: str | None = None
    default_installments: int | None = None
    schema_first: bool = False
    product_card_fallback: bool = False
    http_client: SupplierHttpClient | None = None

    async def search(
        self,
        product_name: str,
        unit: str = "",
        quantity: float | None = None,
        profile: str = "Medio custo",
        limit: int = 5,
    ) -> list[OfertaFornecedor]:
        """Search the Tray storefront."""

        search_queries = build_supplier_search_queries(
            product_name=product_name,
            unit=unit,
            quantity=quantity,
        )
        logger.info(
            "tray_supplier_search_start supplier=%s product_name=%s unit=%s quantity=%s profile=%s queries=%s",
            self.name,
            product_name,
            unit,
            quantity,
            profile,
            search_queries,
        )
        for query in search_queries:
            try:
                offers = await self._search_html_products(
                    query=query,
                    unit=unit,
                    limit=limit,
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "tray_supplier_query_failed supplier=%s query=%s error_type=%s error=%s",
                    self.name,
                    query,
                    type(exc).__name__,
                    exc,
                )
                continue
            if offers:
                logger.info(
                    "tray_supplier_query_selected supplier=%s query=%s offers=%s",
                    self.name,
                    query,
                    len(offers),
                )
                return offers[:limit]
        return []

    @property
    def _http_client(self) -> SupplierHttpClient:
        if self.http_client is None:
            self.http_client = SupplierHttpClient()
        return self.http_client

    def _build_search_url(self, query: str, page: int = 1) -> str:
        """Build a Tray search URL."""

        params = []
        if self.store_id:
            params.append(f"loja={self.store_id}")
        params.append(f"palavra_busca={quote_plus(query)}")
        if page > 1:
            params.append(f"pg={page}")
        return f"{self.base_url.rstrip('/')}/loja/busca.php?{'&'.join(params)}"

    async def _search_html_products(
        self,
        query: str,
        unit: str = "",
        limit: int = 5,
    ) -> list[OfertaFornecedor]:
        """Search and parse one HTML query."""

        search_url = self._build_search_url(query=query)
        html = await self._http_client.get_html(search_url)
        offer_steps = (
            (
                lambda: _scrape_schema_org_product_offers(
                    html=html,
                    query=query,
                    supplier_name=self.name,
                    base_url=self.base_url,
                    fallback_unit=unit,
                    availability_text=f"Produto encontrado na busca da {self.name}.",
                    default_installments=self.default_installments,
                    limit=limit,
                ),
                lambda: _scrape_tray_datalayer_offers(
                    html=html,
                    query=query,
                    supplier_name=self.name,
                    base_url=self.base_url,
                    fallback_unit=unit,
                    default_installments=self.default_installments,
                    limit=limit,
                ),
            )
            if self.schema_first
            else (
                lambda: _scrape_tray_datalayer_offers(
                    html=html,
                    query=query,
                    supplier_name=self.name,
                    base_url=self.base_url,
                    fallback_unit=unit,
                    default_installments=self.default_installments,
                    limit=limit,
                ),
                lambda: _scrape_schema_org_product_offers(
                    html=html,
                    query=query,
                    supplier_name=self.name,
                    base_url=self.base_url,
                    fallback_unit=unit,
                    availability_text=f"Produto encontrado na busca da {self.name}.",
                    default_installments=self.default_installments,
                    limit=limit,
                ),
            )
        )
        for step in offer_steps:
            offers = step()
            if offers:
                return offers

        offers = _scrape_storefront_search_offers(
            html=html,
            query=query,
            base_url=self.base_url,
            supplier_name=self.name,
            fallback_unit=unit,
            availability_text=f"Produto encontrado na busca da {self.name}.",
            default_installments=self.default_installments,
            limit=limit,
        )
        if offers or not self.product_card_fallback:
            return offers
        return _scrape_storefront_product_card_offers(
            html=html,
            query=query,
            base_url=self.base_url,
            supplier_name=self.name,
            fallback_unit=unit,
            availability_text=(
                f"Produto encontrado na busca da {self.name}; "
                "preco nao visivel no HTML."
            ),
            default_installments=self.default_installments,
            limit=limit,
        )


class SerperSupplier:
    """Search Google Shopping through Serper as a fallback."""

    name = "Serper"

    def __init__(self, http_client: SupplierHttpClient | None = None) -> None:
        self.http_client = http_client or SupplierHttpClient()

    async def search(
        self,
        product_name: str,
        unit: str = "",
        quantity: float | None = None,
        profile: str = "Medio custo",
        limit: int = 5,
    ) -> list[OfertaFornecedor]:
        """Search Serper Shopping and return up to limit offers."""

        settings = get_settings()
        api_key = settings.serper_api_key
        if not api_key:
            logger.info("serper_search_skipped reason=missing_api_key")
            return []

        query_parts = [
            product_name,
            compact_quantity_unit_for_query(quantity=quantity, unit=unit),
            profile,
            "Aracaju - SE",
        ]
        query = " ".join(str(part).strip() for part in query_parts if str(part).strip())
        payload = await self.http_client.post_json(
            "https://google.serper.dev/shopping",
            headers={
                "X-API-KEY": api_key,
                "Content-Type": "application/json",
            },
            payload={
                "q": query,
                "gl": "br",
                "hl": "pt-br",
                "num": limit,
            },
        )
        shopping_results = payload.get("shopping") or payload.get("shopping_results") or []
        offers = []
        for item in shopping_results[:limit]:
            title = item.get("title")
            offers.append(
                OfertaFornecedor(
                    fornecedor=item.get("source") or item.get("seller") or "",
                    descricao=title,
                    unidade=infer_commercial_unit(title, unit),
                    valor_unitario=_coerce_price(item.get("price")),
                    disponibilidade=item.get("delivery") or item.get("availability"),
                    data_consulta=date.today().isoformat(),
                    link_produto=item.get("link") or item.get("product_link"),
                )
            )
        return offers


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
    "hidraulica",
    "hidraulico",
    "irrigacao",
    "jardinagem",
}


def is_casa_eletricidade_material(area_name: str, material: MaterialObra) -> bool:
    """Return whether Casa da Eletricidade is relevant for this material."""

    haystack = normalize_search_text(f"{area_name} {material.nome} {material.descricao}")
    return any(term in haystack for term in ELECTRICAL_SUPPLIER_TERMS)


def create_default_supplier_providers(
    http_client: SupplierHttpClient | None = None,
) -> tuple[SupplierProvider, SupplierProvider, SupplierProvider, SupplierProvider]:
    """Create the default supplier provider set."""

    shared_http_client = http_client or SupplierHttpClient()
    return (
        TraySupplier(
            name="Casa da Eletricidade",
            base_url=CASA_ELETRICIDADE_BASE_URL,
            schema_first=True,
            product_card_fallback=True,
            http_client=shared_http_client,
        ),
        PisolarSupplier(http_client=shared_http_client),
        TraySupplier(
            name="Comercial Alianca",
            base_url=COMERCIAL_ALIANCA_BASE_URL,
            store_id=COMERCIAL_ALIANCA_STORE_ID,
            default_installments=10,
            http_client=shared_http_client,
        ),
        SerperSupplier(http_client=shared_http_client),
    )


class SupplierSearchService:
    """Coordinate supplier-provider searches for a material."""

    def __init__(
        self,
        casa_provider: SupplierProvider | None = None,
        pisolar_provider: SupplierProvider | None = None,
        comercial_alianca_provider: SupplierProvider | None = None,
        serper_provider: SupplierProvider | None = None,
    ) -> None:
        defaults: tuple[
            SupplierProvider,
            SupplierProvider,
            SupplierProvider,
            SupplierProvider,
        ] | None = None

        def default_provider(index: int) -> SupplierProvider:
            nonlocal defaults
            if defaults is None:
                defaults = create_default_supplier_providers()
            return defaults[index]

        self.casa_provider = casa_provider or default_provider(0)
        self.pisolar_provider = pisolar_provider or default_provider(1)
        self.comercial_alianca_provider = (
            comercial_alianca_provider or default_provider(2)
        )
        self.serper_provider = serper_provider or default_provider(3)

    def providers_for_material(
        self,
        area_name: str,
        material: MaterialObra,
    ) -> list[SupplierProvider]:
        """Return supplier-specific providers relevant for a material."""

        providers: list[SupplierProvider] = []
        if is_casa_eletricidade_material(area_name, material):
            providers.append(self.casa_provider)
        providers.extend([self.pisolar_provider, self.comercial_alianca_provider])
        return providers

    async def search_material(
        self,
        area_name: str,
        material: MaterialObra,
        limit_per_provider: int = 5,
        use_serper_fallback: bool = True,
    ) -> list[OfertaFornecedor]:
        """Search all relevant suppliers for a material."""

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
        providers = self.providers_for_material(area_name, material)
        search_tasks = [
            provider.search(
                product_name=search_text,
                unit="",
                quantity=None,
                profile=str(profile),
                limit=limit_per_provider,
            )
            for provider in providers
        ]
        provider_results = await asyncio.gather(*search_tasks, return_exceptions=True)
        offers: list[OfertaFornecedor] = []
        for provider, result in zip(providers, provider_results, strict=False):
            if isinstance(result, Exception):
                logger.warning(
                    "supplier_provider_failed supplier=%s material=%s error_type=%s error=%s",
                    provider.name,
                    material.nome,
                    type(result).__name__,
                    result,
                )
                continue
            logger.info(
                "supplier_provider_done supplier=%s material=%s offers=%s",
                provider.name,
                material.nome,
                len(result),
            )
            offers.extend(result)

        has_priced_offer = any(offer.valor_unitario is not None for offer in offers)
        if use_serper_fallback and not has_priced_offer:
            try:
                serper_offers = await self.serper_provider.search(
                    product_name=search_text,
                    unit="",
                    quantity=None,
                    profile=str(profile),
                    limit=limit_per_provider,
                )
            except Exception as exc:
                logger.warning(
                    "serper_provider_failed material=%s error_type=%s error=%s",
                    material.nome,
                    type(exc).__name__,
                    exc,
                )
            else:
                offers.extend(serper_offers)
        return offers


def enrich_offer_for_material(
    material: MaterialObra,
    offer: OfertaFornecedor,
) -> OfertaFornecedor:
    """Fill purchase quantity and totals when the package unit is clear."""

    updates: dict[str, Any] = {}
    offer_unit = offer.unidade or infer_commercial_unit(offer.descricao, "")
    if offer_unit and offer.unidade != offer_unit:
        updates["unidade"] = offer_unit

    purchase_quantity = offer.quantidade
    calculated_quantity = purchase_quantity_for_material(
        required_quantity=material.quantidade,
        required_unit=material.medida,
        offer_unit=offer_unit,
    )
    if calculated_quantity is not None:
        purchase_quantity = calculated_quantity
        if offer.quantidade != purchase_quantity:
            updates["quantidade"] = float(purchase_quantity)
    elif purchase_quantity is None and offer.valor_unitario is not None and not offer_unit:
        purchase_quantity = 1
        updates["quantidade"] = 1

    if purchase_quantity is not None and offer.valor_unitario is not None:
        total_price = round(float(offer.valor_unitario) * float(purchase_quantity), 2)
        if calculated_quantity is not None or offer.valor_total is None:
            updates["valor_total"] = total_price
        if calculated_quantity is not None or offer.preco_a_vista is None:
            updates["preco_a_vista"] = total_price
        if calculated_quantity is not None or offer.preco_a_prazo is None:
            updates["preco_a_prazo"] = total_price

    return offer.model_copy(update=updates) if updates else offer


def offer_rank_value(offer: OfertaFornecedor) -> float:
    """Return the best comparable price for ranking an offer."""

    for value in (
        offer.valor_total,
        offer.preco_a_vista,
        offer.preco_a_prazo,
        offer.valor_unitario,
    ):
        if value is not None:
            rank = float(value)
            availability = normalize_search_text(offer.disponibilidade or "")
            if "indisponivel" in availability or "esgotado" in availability:
                return rank + 1_000_000
            return rank
    return float("inf")


def offer_identity(offer: OfertaFornecedor) -> tuple[str, str, str, str]:
    """Build a stable identity to avoid repeated offer cards."""

    return (
        normalize_search_text(offer.fornecedor),
        normalize_search_text(offer.link_produto or ""),
        normalize_search_text(offer.descricao or ""),
        normalize_search_text(offer.unidade or ""),
    )


def select_offer_options(
    offers: list[OfertaFornecedor],
    limit: int,
) -> list[OfertaFornecedor]:
    """Rank offers, keep supplier diversity, then cap alternatives."""

    if limit <= 0 or not offers:
        return []

    deduped: list[OfertaFornecedor] = []
    seen = set()
    for offer in offers:
        key = offer_identity(offer)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(offer)

    ranked = sorted(
        deduped,
        key=lambda offer: (
            offer_rank_value(offer),
            normalize_search_text(offer.fornecedor),
            normalize_search_text(offer.descricao or ""),
        ),
    )
    selected: list[OfertaFornecedor] = []
    selected_keys = set()
    selected_suppliers = set()

    def add_offer(offer: OfertaFornecedor) -> None:
        key = offer_identity(offer)
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


def best_offer(offers: list[OfertaFornecedor]) -> OfertaFornecedor | None:
    """Return the best offer from an already selected list."""

    priced_offers = [offer for offer in offers if offer_rank_value(offer) < float("inf")]
    if priced_offers:
        return min(priced_offers, key=offer_rank_value)
    return offers[0] if offers else None
