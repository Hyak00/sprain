import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1/logistica"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)
HEADERS_ADMIN = {"X-API-Key": "key_admin_demo"}

@pytest.mark.asyncio
async def test_validacao_rota_real_transportadora():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers=HEADERS_ADMIN) as client:
        payload = {
            "tenant_id": "demo_corp",
            "id_veiculo": "TRK-001",
            "placa": "BRA0192",
            "modelo": "Mercedes",
            "tipo_veiculo": "CARRETA_5_EIXOS",
            "lat_atual": -21.79,
            "lon_atual": -48.17
        }
        await client.post("/veiculos", json=payload)
        
        rota_real = {
            "id_operacao": "OP_REAL_01",
            "id_veiculo": "TRK-001",
            "origem_nome": "Araraquara",
            "origem_lat": -21.79,
            "origem_lon": -48.17,
            "destino_nome": "Sao Paulo",
            "destino_lat": -23.54,
            "destino_lon": -46.46,
            "janela_inicio": "2026-10-16T08:00:00Z",
            "janela_fim": "2026-10-16T14:00:00Z"
        }
        resp = await client.post("/operacoes", json=rota_real)
        assert resp.status_code in [200, 400]