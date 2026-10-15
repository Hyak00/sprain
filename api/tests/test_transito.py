import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1/transito"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
HEADERS_ADMIN = {"X-API-Key": "key_admin_demo"}

@pytest.mark.asyncio
async def test_cliente_transito_isolado_e_cache():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers=HEADERS_ADMIN) as client:
        payload = {
            "origem_lat": -23.542,
            "origem_lon": -46.468,
            "destino_lat": -23.535,
            "destino_lon": -46.452
        }
        resp = await client.post("/comparar", json=payload)
        assert resp.status_code in [200, 502]
        if resp.status_code == 200:
            data = resp.json()
            assert "transito" in data
            
        resp_met = await client.get("/metricas")
        assert resp_met.status_code == 200
        assert "total_consultas_realizadas" in resp_met.json()