import pytest
import httpx

BASE_URL = "http://127.0.0.1:8000/api/v1/rotas"
TIMEOUT = httpx.Timeout(15.0, connect=5.0)
HEADERS_ADMIN = {"X-API-Key": "key_admin_demo"}


@pytest.mark.asyncio
async def test_corredor_nao_inventa_tempo_desvio_nem_meteorologia():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers=HEADERS_ADMIN) as client:
        resp = await client.get("/intermunicipal")
        assert resp.status_code == 200
        data = resp.json()
        assert data["modalidade"] == "CONSULTA_CORREDOR_REFERENCIA"
        assert data["resumo"]["distancia_total_km"] > 0
        assert data["resumo"]["tempo_real_estimado_min"] is None
        assert data["resumo"]["motivo_indisponivel"]
        assert data["decisao_logistica"]["recomendacao"] == "INDISPONIVEL"
        assert data["decisao_logistica"]["desvio"] is None
        assert data["decisao_logistica"]["analise_financeira"]["beneficio_liquido_reais"] is None
        assert data["pedagios"]["cobertura_completa"] is False
        assert all(s["status"] == "SEM_DADO_METEOROLOGICO" for s in data["segmentos"])
        assert all(s["precipitacao_mm_h"] is None for s in data["segmentos"])


@pytest.mark.asyncio
async def test_corredor_recusa_cidades_fora_da_cobertura():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers=HEADERS_ADMIN) as client:
        resp = await client.get("/intermunicipal", params={"origem": "Curitiba", "destino": "Sao Paulo"})
        assert resp.status_code == 422


@pytest.mark.asyncio
async def test_corredor_recusa_categoria_invalida():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers=HEADERS_ADMIN) as client:
        resp = await client.get("/intermunicipal", params={"tipo_veiculo": "BICICLETA"})
        assert resp.status_code == 422