import pytest
import httpx
from app.services.routing_engine import RoutingEngine

BASE_URL = "http://127.0.0.1:8000/api/v1/logistica"
TIMEOUT = httpx.Timeout(45.0, connect=10.0)
HEADERS_ADMIN = {"X-API-Key": "key_admin_demo"}

def test_cache_key_isolada_por_tenant():
    RoutingEngine.clear_cache()
    k1 = RoutingEngine._make_cache_key(-46.46, -23.54, -46.45, -23.53, "FASTEST", 0.0, "VUC", "demo_corp")
    k2 = RoutingEngine._make_cache_key(-46.46, -23.54, -46.45, -23.53, "FASTEST", 0.0, "VUC", "log_express")
    assert k1 != k2
    RoutingEngine._set_cache(k1, {"distancia_km": 5.0})
    assert RoutingEngine._get_from_cache(k2) is None
    assert RoutingEngine.cache_stats("demo_corp")["total_entradas"] == 1
    assert RoutingEngine.cache_stats("log_express")["total_entradas"] == 0
    RoutingEngine.clear_cache("demo_corp")
    assert RoutingEngine.cache_stats("demo_corp")["total_entradas"] == 0

@pytest.mark.asyncio
async def test_sumario_executivo_nao_acumula_simulacoes_repetidas():
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=TIMEOUT, headers=HEADERS_ADMIN) as client:
        payload = {
            "precipitacao_mm": 75.0,
            "parametros_custo": {"prejuizo_potencial_alagamento": 1000.0}
        }
        await client.post("/simular-impacto", json=payload)
        s1 = (await client.get("/relatorios/sumario-executivo")).json()["kpis"]
        await client.post("/simular-impacto", json=payload)
        s2 = (await client.get("/relatorios/sumario-executivo")).json()["kpis"]
        assert s1["prejuizo_estimado_evitado_brl"] == s2["prejuizo_estimado_evitado_brl"]
        assert s1["tempo_total_desvios_min"] == s2["tempo_total_desvios_min"]
