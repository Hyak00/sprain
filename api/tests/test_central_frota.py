import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1/logistica"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)

@pytest.mark.asyncio
async def test_painel_central_frota():
    headers = {"X-API-Key": "key_admin_demo"}
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers=headers) as client:
        resp = await client.get("/central-frota?tenant_id=demo_corp&precipitacao_referencia_mm=75.0")
        assert resp.status_code == 200
        data = resp.json()
        assert "sumario_central" in data
        assert "veiculos" in data
        assert data["sumario_central"]["total_frota"] >= 0
        assert data["sumario_central"]["economia_potencial_total_brl"] is None
        for v in data["veiculos"]:
            assert v["analise_risco"]["probabilidade_atraso_pct"] is None
            if v["status_monitoramento"] == "DISPONIVEL":
                assert v["impacto_financeiro_projetado"]["custo_desvio_brl"] is None
        resp_param = await client.get("/central-frota?tenant_id=demo_corp&precipitacao_referencia_mm=75.0&prejuizo_referencia_brl=5000.0")
        assert resp_param.status_code == 200
        data_param = resp_param.json()
        assert data_param["sumario_central"]["economia_potencial_total_brl"] is not None
