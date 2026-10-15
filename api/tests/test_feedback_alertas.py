import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1/alertas"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
HEADERS_ADMIN = {"X-API-Key": "key_admin_demo"}

@pytest.mark.asyncio
async def test_feedback_e_precisao_alertas():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers=HEADERS_ADMIN) as client:
        resp_prec = await client.get("/precisao")
        assert resp_prec.status_code == 200
        data = resp_prec.json()
        assert "metricas_precisao" in data
        assert "precisao_alertas_pct" in data["metricas_precisao"]