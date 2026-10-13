import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1/logistica"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)

@pytest.mark.asyncio
async def test_login_corporativo_e_busca_vias():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        falha = await client.post("/auth/login", json={"email": "operacoes@democorp.com.br", "senha": "errada"})
        assert falha.status_code == 401

        ok = await client.post("/auth/login", json={"email": "operacoes@democorp.com.br", "senha": "sprain2026"})
        assert ok.status_code == 200
        dados_login = ok.json()
        assert dados_login["autenticado"] is True
        assert dados_login["tenant_id"] == "demo_corp"
        api_key = dados_login["api_key"]

        vias = await client.get("/vias/buscar?q=Rua", headers={"X-API-Key": api_key})
        assert vias.status_code == 200
        lista = vias.json()
        assert len(lista) > 0
        assert "lat" in lista[0] and "lon" in lista[0]
