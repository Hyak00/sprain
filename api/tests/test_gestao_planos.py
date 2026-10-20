"""A configuracao manual so grava apos aplicacao explicita e deixa historico."""

from datetime import datetime, timezone
from uuid import uuid4

import asyncpg
import pytest

from app.config import settings
from app.services.gestao_planos import registrar_assinatura, registrar_plano
from app.services.planos_empresa import SCHEMA, SCHEMA_AUDITORIA


@pytest.mark.asyncio
async def test_previa_aplicacao_e_auditoria_sao_atomicas():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction()
    await tx.start()
    codigo = "PLAN_" + uuid4().hex[:12].upper()
    tenant = "TEST_PLAN_" + uuid4().hex[:12]
    plano = {
        "codigo": codigo, "nome": "Plano de teste", "funcionalidades": ["PAINEL"],
        "limite_usuarios_ativos": 3, "limite_corredores_ativos": 2,
        "limite_consultas_mes": 10, "limite_chamadas_externas_mes": None,
    }
    assinatura = {
        "tenant_id": tenant, "plano_codigo": codigo, "status": "ATIVA",
        "inicio_em": datetime(2026, 10, 1, tzinfo=timezone.utc), "fim_em": None,
    }
    try:
        await conn.execute(SCHEMA)
        await conn.execute(SCHEMA_AUDITORIA)
        previa = await registrar_plano(conn, plano, "operador-teste", "contrato de teste")
        assert previa["alterado"] and not previa["aplicado"]
        assert await conn.fetchval("SELECT count(*) FROM planos_servico WHERE codigo=$1", codigo) == 0
        with pytest.raises(ValueError, match="Plano inexistente"):
            await registrar_assinatura(conn, assinatura, "operador-teste", "contrato de teste", True)

        aplicado = await registrar_plano(conn, plano, "operador-teste", "contrato de teste", True)
        assert aplicado["aplicado"]
        assert not (await registrar_plano(conn, plano, "operador-teste", "contrato de teste", True))["alterado"]
        assert (await registrar_assinatura(conn, assinatura, "operador-teste", "contrato de teste"))["aplicado"] is False
        assert await conn.fetchval("SELECT count(*) FROM assinaturas_empresa WHERE tenant_id=$1", tenant) == 0
        await registrar_assinatura(conn, assinatura, "operador-teste", "contrato de teste", True)
        linhas = await conn.fetch("""
            SELECT tipo,anterior,posterior,ator,motivo FROM planos_auditoria
            WHERE (tipo='PLANO' AND chave=$1) OR (tipo='ASSINATURA' AND chave=$2)
            ORDER BY id
        """, codigo, tenant)
        assert [r["tipo"] for r in linhas] == ["PLANO", "ASSINATURA"]
        assert all(r["anterior"] is None for r in linhas)
        assert all(r["ator"] == "operador-teste" and r["motivo"] == "contrato de teste" for r in linhas)
    finally:
        await tx.rollback()
        await conn.close()
