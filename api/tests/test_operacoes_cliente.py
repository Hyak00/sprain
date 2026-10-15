import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1/cliente/operacoes"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)

@pytest.mark.asyncio
async def test_isolamento_tenant_operacoes_cliente():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT) as client:
        payload = {"id_viagem": "V_TEST_01", "origem": "Araraquara", "destino": "Sao Paulo", "atraso_minutos": 15.5}
        
        resp_demo = await client.post("", json=payload, headers={"X-API-Key": "key_admin_demo"})
        assert resp_demo.status_code == 200
        assert resp_demo.json()["tenant_id"] == "demo_corp"
        
        resp_express = await client.get("", headers={"X-API-Key": "key_admin_express"})
        assert resp_express.status_code == 200
        viagens_express = resp_express.json()
        assert not any(v["id_viagem"] == "V_TEST_01" for v in viagens_express)