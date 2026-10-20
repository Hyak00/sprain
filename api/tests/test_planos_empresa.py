"""Assinatura e uso por empresa, sem dados reais ou gravacao permanente."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import asyncpg
import httpx
import pytest

from app.config import settings
from app.services.planos_empresa import SCHEMA, periodo_atual, resumo


def test_mes_de_consumo_usa_fuso_da_empresa():
    antes = datetime(2026, 10, 1, 2, 59, tzinfo=timezone.utc)
    depois = datetime(2026, 10, 1, 3, 1, tzinfo=timezone.utc)
    assert periodo_atual(antes)[2] == "2026-09"
    assert periodo_atual(depois)[2] == "2026-10"


@pytest.mark.asyncio
async def test_resumo_isola_empresa_e_nao_inventa_custo_ou_chamadas_externas():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction()
    await tx.start()
    tenant = "TEST_PLAN_" + uuid4().hex[:12]
    outro = "TEST_OTHER_" + uuid4().hex[:12]
    codigo = "PLAN_" + uuid4().hex[:12].upper()
    inicio, fim, periodo = periodo_atual()
    try:
        await conn.execute(SCHEMA)
        await conn.execute(SCHEMA)
        await conn.execute("""
            INSERT INTO planos_servico(codigo,nome,funcionalidades,limite_usuarios_ativos,
                limite_corredores_ativos,limite_consultas_mes)
            VALUES($1,'Plano sintético',ARRAY['PAINEL'],3,2,10)
        """, codigo)
        await conn.execute("""
            INSERT INTO assinaturas_empresa(tenant_id,plano_codigo,status,inicio_em)
            VALUES($1,$2,'ATIVA',now()-interval '1 day')
        """, tenant, codigo)
        for alvo in (tenant, tenant, outro):
            ident = uuid4()
            await conn.execute("""
                INSERT INTO painel_usuarios(id,email,empresa,tenant_id,papel,senha_hash)
                VALUES($1,$2,'TESTE',$3,'VIEWER','hash-inutil-de-teste')
            """, ident, str(ident) + "@teste.invalid", alvo)
            await conn.execute("""
                INSERT INTO painel_corredores(id,tenant_id,dados,geometria)
                VALUES($1,$2,'{"ativo":true}'::jsonb,'{}'::jsonb)
            """, uuid4(), alvo)
            await conn.execute("""
                INSERT INTO painel_consultas(id,tenant_id,id_operacao,perfil,snapshot,criado_em)
                VALUES($1,$2,'TESTE','VIEWER','{}'::jsonb,$3)
            """, uuid4(), alvo, inicio + timedelta(hours=1))
        await conn.execute("""
            INSERT INTO painel_consultas(id,tenant_id,id_operacao,perfil,snapshot,criado_em)
            VALUES($1,$2,'ANTIGA','VIEWER','{}'::jsonb,$3)
        """, uuid4(), tenant, inicio - timedelta(seconds=1))
        resposta = await resumo(conn, tenant)
        assert resposta["situacao"] == "REGISTRADA"
        assert resposta["periodo"] == periodo
        assert resposta["assinatura"]["codigo"] == codigo
        assert resposta["assinatura"]["limites"]["consultas_mes"] == 10
        assert resposta["uso"]["usuarios_ativos"] == 2
        assert resposta["uso"]["corredores_ativos"] == 2
        assert resposta["uso"]["consultas_mes"] == 2
        assert resposta["uso"]["chamadas_externas_mes"] is None
        assert resposta["uso"]["custo_servir_brl"] is None
        sem_plano = await resumo(conn, outro)
        assert sem_plano["assinatura"] is None
        assert sem_plano["situacao"] == "SEM_ASSINATURA_CONFIGURADA"
        assert sem_plano["uso"]["consultas_mes"] == 1
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_endpoint_plano_somente_admin_e_sem_selecao_de_outro_tenant():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=20) as client:
        url = "/api/v1/operacional/plano?tenant_id=log_express"
        assert (await client.get(url)).status_code == 401
        assert (await client.get(url, headers={"X-API-Key": "key_viewer_demo"})).status_code == 403
        response = await client.get(url, headers={"X-API-Key": "key_admin_demo"})
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.json()["empresa"] == "demo_corp"
