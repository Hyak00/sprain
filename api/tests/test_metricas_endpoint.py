"""Agregados por template de rota persistem sem expor outras empresas."""

from datetime import datetime, timezone
from uuid import uuid4

import asyncpg
import httpx
import pytest
from fastapi import FastAPI, Request

from app.config import settings
from app.services.medicao_processamento import registrar_atendimento, resumo_por_endpoint
from app.services import observabilidade
from app.services.planos_empresa import SCHEMA_TEMPO, SCHEMA_METRICAS_ENDPOINT


@pytest.mark.asyncio
async def test_metricas_por_endpoint_isolam_empresa_e_mes():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction()
    await tx.start()
    tenant = "TEST_METRIC_" + uuid4().hex[:12]
    outro = "TEST_OTHER_" + uuid4().hex[:12]
    setembro = datetime(2026, 10, 1, 2, 59, tzinfo=timezone.utc)
    outubro = datetime(2026, 10, 1, 3, 1, tzinfo=timezone.utc)
    try:
        await conn.execute(SCHEMA_TEMPO)
        await conn.execute(SCHEMA_METRICAS_ENDPOINT)
        await registrar_atendimento(conn, tenant, 200, 11, setembro,
                                    metodo="GET", rota_template="/api/v1/rotas/{id}")
        await registrar_atendimento(conn, tenant, 500, 29, outubro,
                                    metodo="GET", rota_template="/api/v1/rotas/{id}")
        await registrar_atendimento(conn, tenant, 200, 9, outubro,
                                    metodo="GET", rota_template="/api/v1/rotas/{id}")
        await registrar_atendimento(conn, outro, 503, 99, outubro,
                                    metodo="GET", rota_template="/api/v1/rotas/{id}")
        antigo = await resumo_por_endpoint(conn, tenant, setembro)
        atual = await resumo_por_endpoint(conn, tenant, outubro)
        assert (antigo["periodo"], antigo["endpoints"][0]["tempo_medio_ms"]) == ("2026-09", 11)
        assert atual["endpoints"] == [{
            "metodo": "GET", "rota_template": "/api/v1/rotas/{id}",
            "requisicoes": 2, "erros": 1, "tempo_medio_ms": 19.0,
            "tempo_max_ms": 29.0,
        }]
        assert atual["truncado"] is False
        assert (await resumo_por_endpoint(conn, outro, outubro))["endpoints"][0]["erros"] == 1
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_metricas_endpoint_so_admin_da_propria_empresa():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30) as client:
        url = "/api/v1/operacional/metricas-endpoints"
        assert (await client.get(url)).status_code == 401
        assert (await client.get(url, headers={"X-API-Key": "key_viewer_demo"})).status_code == 403
        resposta = await client.get(url, headers={"X-API-Key": "key_admin_demo"})
        assert resposta.status_code == 200
        assert resposta.headers["cache-control"] == "no-store"
        assert resposta.json()["empresa"] == "demo_corp"


@pytest.mark.asyncio
async def test_falha_inesperada_entra_na_contagem_sem_expor_id(monkeypatch):
    tenant = "TEST_FAILURE_" + uuid4().hex[:12]
    app = FastAPI()
    app.add_middleware(observabilidade.ObservabilidadeMiddleware)
    gravacoes = []
    monkeypatch.setattr(observabilidade, "_agendar_medicao", lambda *args: gravacoes.append(args))

    @app.get("/falha/{item}")
    async def falhar(request: Request):
        request.state.authenticated_tenant_id = tenant
        raise RuntimeError("falha de ensaio")

    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://test") as client:
            with pytest.raises(Exception):
                await client.get("/falha/id-privado-123")
        resumo = observabilidade.MetricsCollector.obter_metricas(tenant)
        assert resumo["total_requisicoes"] == resumo["total_erros"] == 1
        assert len(gravacoes) == 1 and gravacoes[0][1] == 500
        assert "id-privado-123" not in str(resumo) + str(gravacoes)
    finally:
        observabilidade.MetricsCollector.resetar(tenant)
