import httpx
from fastapi.testclient import TestClient
from openai import APITimeoutError

from app.app import app
from app.controllers.ifc_controller import get_ifc_service


class TimeoutIfcService:
    async def analyze_ifc(self, ifc_id: str):
        request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
        raise APITimeoutError(request=request)


def test_analisar_ifc_returns_gateway_timeout_for_openai_timeout():
    app.dependency_overrides[get_ifc_service] = lambda: TimeoutIfcService()
    try:
        response = TestClient(app).post("/analisar_ifc", json={"ifc_id": "ifc-1"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 504
    assert "demorou mais que o limite configurado" in response.json()["detail"]
