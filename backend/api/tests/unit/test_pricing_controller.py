import re

import httpx
import pytest
from fastapi.testclient import TestClient
from openai import APITimeoutError

from app.app import app
from app.controllers.pricing_controller import get_pricing_service
from app.models.materials import AreaMateriaisObra, ListaMateriaisObra, MaterialObra
from app.services.ifc.llm_client import OpenAIConfigurationError
from app.settings import get_settings


class FakePricingService:
    def __init__(self):
        self.calls = []

    async def fill_suppliers(
        self,
        lista_materiais,
        max_fornecedores_por_material=3,
        max_materiais_processados=None,
        use_serper_fallback=False,
    ):
        self.calls.append(
            {
                "max_fornecedores_por_material": max_fornecedores_por_material,
                "max_materiais_processados": max_materiais_processados,
                "use_serper_fallback": use_serper_fallback,
            }
        )
        updated_area = lista_materiais.areas[0].model_copy(
            update={
                "materiais": [
                    lista_materiais.areas[0].materiais[0].model_copy(
                        update={"fornecedor": "Loja Teste"}
                    )
                ]
            }
        )
        return lista_materiais.model_copy(update={"areas": [updated_area]})


class FailingPricingService:
    async def fill_suppliers(self, *args, **kwargs):
        raise ValueError("limite invalido")


class MissingOpenAIPricingService:
    async def fill_suppliers(self, *args, **kwargs):
        raise OpenAIConfigurationError("Missing OPENAI_API_KEY or openai_api_key.")


class TimeoutPricingService:
    async def fill_suppliers(self, *args, **kwargs):
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        raise APITimeoutError(request=request)


def _payload():
    return ListaMateriaisObra(
        areas=[
            AreaMateriaisObra(
                area="Pintura",
                materiais=[MaterialObra(nome="Tinta acrilica", quantidade=30, medida="litros")],
            )
        ]
    ).model_dump(mode="json")


@pytest.fixture(autouse=True)
def pricing_request_log_dir(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "PRICING_REQUEST_LOG_DIR", tmp_path)
    return tmp_path


def test_buscar_fornecedores_returns_priced_material_list():
    fake_service = FakePricingService()
    app.dependency_overrides[get_pricing_service] = lambda: fake_service
    try:
        response = TestClient(app).post(
            "/buscar_fornecedores?max_materials=2&max_materiais_processados=1&use_serper_fallback=false",
            json=_payload(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["areas"][0]["materiais"][0]["fornecedor"] == "Loja Teste"
    assert fake_service.calls == [
        {
            "max_fornecedores_por_material": 2,
            "max_materiais_processados": 1,
            "use_serper_fallback": False,
        }
    ]


def test_buscar_fornecedores_writes_timestamped_log_file(pricing_request_log_dir):
    fake_service = FakePricingService()
    app.dependency_overrides[get_pricing_service] = lambda: fake_service
    try:
        response = TestClient(app).post(
            "/buscar_fornecedores?max_materials=2",
            json=_payload(),
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    log_files = list(pricing_request_log_dir.glob("*.log"))
    assert len(log_files) == 1
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}-\d{6}\.log",
        log_files[0].name,
    )
    log_content = log_files[0].read_text(encoding="utf-8")
    assert "buscar_fornecedores_request_started" in log_content
    assert "buscar_fornecedores_request_finished" in log_content
    assert "max_fornecedores_por_material=2" in log_content


def test_buscar_fornecedores_returns_bad_request_for_service_value_error():
    app.dependency_overrides[get_pricing_service] = lambda: FailingPricingService()
    try:
        response = TestClient(app).post("/buscar_fornecedores", json=_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "limite invalido"


def test_buscar_fornecedores_returns_unavailable_for_missing_openai_key():
    app.dependency_overrides[get_pricing_service] = lambda: MissingOpenAIPricingService()
    try:
        response = TestClient(app).post("/buscar_fornecedores", json=_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["detail"] == "Missing OPENAI_API_KEY or openai_api_key."


def test_buscar_fornecedores_returns_gateway_timeout_for_openai_timeout():
    app.dependency_overrides[get_pricing_service] = lambda: TimeoutPricingService()
    try:
        response = TestClient(app).post("/buscar_fornecedores", json=_payload())
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 504
    assert "busca de fornecedores por IA demorou" in response.json()["detail"]
