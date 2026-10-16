"""Telemetria não expõe dados de outras empresas ou IDs de operações."""

import httpx
import pytest

from app.main import app
from app.services.observabilidade import MetricsCollector


BASE = "/api/v1/logistica"
ADMIN_DEMO = {"X-API-Key": "key_admin_demo"}
ADMIN_EXPRESS = {"X-API-Key": "key_admin_express"}
VIEWER_DEMO = {"X-API-Key": "key_viewer_demo"}


@pytest.mark.asyncio
async def test_metricas_isoladas_e_sem_identificador_de_operacao():
    MetricsCollector.resetar("demo_corp")
    MetricsCollector.resetar("log_express")
    marker = "OPERACAO_PRIVADA_DEMO_123456"
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            denied = await client.post(
                f"{BASE}/operacoes/{marker}/decisao",
                json={"decisao": "AGUARDAR_MELHORA"},
                headers=VIEWER_DEMO,
            )
            assert denied.status_code == 403

            demo = await client.get(f"{BASE}/observabilidade/metricas", headers=ADMIN_DEMO)
            express = await client.get(f"{BASE}/observabilidade/metricas", headers=ADMIN_EXPRESS)
            assert demo.status_code == express.status_code == 200
            assert demo.json()["total_erros"] == 1
            assert express.json()["total_erros"] == 0
            assert marker not in demo.text
            assert marker not in express.text
            assert any("{id_operacao}" in key for key in demo.json()["detalhamento_por_rota"])

            cross_tenant = await client.get(
                f"{BASE}/observabilidade/metricas?tenant_id=log_express", headers=ADMIN_DEMO
            )
            assert cross_tenant.status_code == 403

            await client.get(f"{BASE}/performance/cache", headers=ADMIN_EXPRESS)
            before = (await client.get(
                f"{BASE}/observabilidade/metricas", headers=ADMIN_EXPRESS
            )).json()["total_requisicoes"]
            forbidden = await client.post(f"{BASE}/observabilidade/reset", headers=VIEWER_DEMO)
            assert forbidden.status_code == 403
            reset = await client.post(f"{BASE}/observabilidade/reset", headers=ADMIN_DEMO)
            assert reset.status_code == 200
            after = (await client.get(
                f"{BASE}/observabilidade/metricas", headers=ADMIN_EXPRESS
            )).json()["total_requisicoes"]
            assert after == before + 1
    finally:
        MetricsCollector.resetar("demo_corp")
        MetricsCollector.resetar("log_express")
