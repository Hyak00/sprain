import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
HEADERS_ADMIN = {"X-API-Key": "key_admin_demo"}

@pytest.mark.asyncio
async def test_indicadores_qualidade_e_demo():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers=HEADERS_ADMIN) as client:
        resp_ind = await client.get("/indicadores/qualidade")
        assert resp_ind.status_code == 200
        data_ind = resp_ind.json()
        assert "percentual_fontes_atualizadas_prazo" in data_ind
        assert "total_registros_base" in data_ind
        
        resp_demo = await client.post("/demonstracao/cenario-historico-sp310")
        # O banco de CI não é uma base reservada de demonstração.
        assert resp_demo.status_code == 503
        estado = await client.get('/demonstracao/estado')
        assert estado.status_code == 200 and not estado.json()['demo_isolada']
        assert (await client.post('/demonstracao/preparar',headers={'X-API-Key':'key_viewer_demo'})).status_code == 403
        assert (await client.post('/demonstracao/reproduzir',headers={'X-API-Key':'key_viewer_demo'},json={'etapa':'BLOQUEIO'})).status_code == 503
        assert (await client.post('/demonstracao/reproduzir',json={'etapa':'INVALIDA'})).status_code == 422
