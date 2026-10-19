import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1/logistica"
TIMEOUT = httpx.Timeout(20.0, connect=5.0)

@pytest.mark.asyncio
async def test_alertas_meteorologicos_feed():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers={"X-API-Key": "key_admin_demo"}) as client:
        resp = await client.get("/alertas-meteorologicos?precipitacao_mm=85.0&rajada_vento_kmh=60.0", headers={"X-API-Key": "key_admin_demo"})
        assert resp.status_code == 200
        data = resp.json()
        assert "alerta" in data
        assert data["alerta"]["nivel_alerta"] == "VERMELHO_EXTRAORDINARIO"
        assert data["alerta"]["classificacao_risco"] == "CRITICO"

@pytest.mark.asyncio
async def test_alertas_meteorologicos_rejeita_parametros_invalidos():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers={"X-API-Key": "key_admin_demo"}) as client:
        consultas = (
            "precipitacao_mm=nan",
            "precipitacao_mm=inf",
            "precipitacao_mm=-1",
            "precipitacao_mm=1500",
            "rajada_vento_kmh=nan",
            "rajada_vento_kmh=-3",
            "rajada_vento_kmh=400",
        )
        for consulta in consultas:
            resp = await client.get(f"/alertas-meteorologicos?{consulta}")
            assert resp.status_code == 422, consulta


@pytest.mark.asyncio
async def test_alertas_meteorologicos_aceita_limites_validos():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers={"X-API-Key": "key_admin_demo"}) as client:
        resp = await client.get("/alertas-meteorologicos?precipitacao_mm=0&rajada_vento_kmh=0")
        assert resp.status_code == 200
        assert resp.json()["alerta"]["nivel_alerta"] == "VERDE_ESTAVEL"
        resp = await client.get("/alertas-meteorologicos?precipitacao_mm=1000&rajada_vento_kmh=300")
        assert resp.status_code == 200
        assert resp.json()["alerta"]["nivel_alerta"] == "VERMELHO_EXTRAORDINARIO"