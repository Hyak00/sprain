import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1/ocorrencias"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
HEADERS_ADMIN = {"X-API-Key": "key_admin_demo"}

@pytest.mark.asyncio
async def test_ciclo_alertas_confianca():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers=HEADERS_ADMIN) as client:
        await client.post("/resetar-todas")
        payload = {"latitude": -23.542, "longitude": -46.468, "nivel": "VERMELHO", "corporacao": "Waze"}
        resp_post = await client.post("/alerta-rapido", json=payload)
        assert resp_post.status_code == 200
        data_post = resp_post.json()
        assert data_post["confianca"] == 0.90
        assert "id_evento" in data_post
        resp_get = await client.get("/ativas")
        assert resp_get.status_code == 200
        ativas = resp_get.json()
        assert len(ativas) >= 1
        alerta = ativas[0]
        assert alerta["fonte"] == "Waze"
        assert "idade_minutos" in alerta
        assert alerta["status_evento"] == "CONFIRMADO"