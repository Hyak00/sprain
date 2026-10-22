"""Cotas configuradas nao podem ser ultrapassadas em chamadas concorrentes."""

import asyncio
from uuid import uuid4

import asyncpg
import pytest
from fastapi import HTTPException

from app.config import settings
from app.services.cotas_plano import verificar_cota
from app.services.medicao_api_externa import reservar_osrm, concluir
from app.services.planos_empresa import SCHEMA, SCHEMA_CHAMADAS, resumo


@pytest.mark.asyncio
async def test_cota_de_usuario_serializa_duas_replicas_e_isola_empresa():
    tenant = "TEST_QUOTA_" + uuid4().hex[:12]
    outro = "TEST_FREE_" + uuid4().hex[:12]
    codigo = "QUOTA_" + uuid4().hex[:12].upper()
    setup = await asyncpg.connect(settings.database_url)
    try:
        await setup.execute(SCHEMA)
        await setup.execute("""
            INSERT INTO planos_servico(codigo,nome,limite_usuarios_ativos)
            VALUES($1,'Cota sintetica',1)
        """, codigo)
        await setup.execute("""
            INSERT INTO assinaturas_empresa(tenant_id,plano_codigo,status,inicio_em)
            VALUES($1,$2,'ATIVA',now())
        """, tenant, codigo)

        async def cadastrar(numero):
            conn = await asyncpg.connect(settings.database_url)
            try:
                async with conn.transaction():
                    await verificar_cota(conn, tenant, "usuarios")
                    await asyncio.sleep(0.03)
                    await conn.execute("""
                        INSERT INTO painel_usuarios(id,email,empresa,tenant_id,papel,senha_hash)
                        VALUES($1,$2,'TESTE',$3,'VIEWER','hash-inutil-de-teste')
                    """, uuid4(), f"{uuid4()}@teste.invalid", tenant)
                return "criado"
            except HTTPException as erro:
                return erro.status_code
            finally:
                await conn.close()

        resultados = await asyncio.gather(cadastrar(1), cadastrar(2))
        assert sorted(resultados, key=str) == sorted(["criado", 429], key=str)
        assert await setup.fetchval("SELECT count(*) FROM painel_usuarios WHERE tenant_id=$1", tenant) == 1
        async with setup.transaction():
            assert (await verificar_cota(setup, outro, "usuarios"))["limite"] is None
    finally:
        await setup.execute("DELETE FROM painel_usuarios WHERE tenant_id=$1", tenant)
        await setup.execute("DELETE FROM assinaturas_empresa WHERE tenant_id=$1", tenant)
        await setup.execute("DELETE FROM planos_servico WHERE codigo=$1", codigo)
        await setup.close()


@pytest.mark.asyncio
async def test_cota_corredor_ativo_e_consulta_mensal():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction()
    await tx.start()
    tenant = "TEST_QUOTA_" + uuid4().hex[:12]
    codigo = "QUOTA_" + uuid4().hex[:12].upper()
    try:
        await conn.execute(SCHEMA)
        await conn.execute("""
            INSERT INTO planos_servico(codigo,nome,limite_corredores_ativos,limite_consultas_mes)
            VALUES($1,'Cota sintetica',1,1)
        """, codigo)
        await conn.execute("""
            INSERT INTO assinaturas_empresa(tenant_id,plano_codigo,status,inicio_em)
            VALUES($1,$2,'ATIVA',now())
        """, tenant, codigo)
        assert (await verificar_cota(conn, tenant, "corredores"))["uso_antes"] == 0
        await conn.execute("""
            INSERT INTO painel_corredores(id,tenant_id,dados,geometria)
            VALUES($1,$2,'{"ativo":true}'::jsonb,'{}'::jsonb)
        """, uuid4(), tenant)
        with pytest.raises(HTTPException) as corredor:
            await verificar_cota(conn, tenant, "corredores")
        assert corredor.value.status_code == 429
        assert (await verificar_cota(conn, tenant, "consultas"))["uso_antes"] == 0
        await conn.execute("""
            INSERT INTO painel_consultas(id,tenant_id,id_operacao,perfil,snapshot)
            VALUES($1,$2,'TESTE','VIEWER','{}'::jsonb)
        """, uuid4(), tenant)
        with pytest.raises(HTTPException) as consulta:
            await verificar_cota(conn, tenant, "consultas")
        assert consulta.value.status_code == 429
    finally:
        await tx.rollback()
        await conn.close()


@pytest.mark.asyncio
async def test_reserva_externa_conta_por_empresa_e_bloqueia_segunda_tentativa():
    conn = await asyncpg.connect(settings.database_url)
    tx = conn.transaction()
    await tx.start()
    tenant = "TEST_EXTERNAL_" + uuid4().hex[:12]
    outro = "TEST_OTHER_" + uuid4().hex[:12]
    codigo = "QUOTA_" + uuid4().hex[:12].upper()
    try:
        await conn.execute(SCHEMA)
        await conn.execute(SCHEMA_CHAMADAS)
        await conn.execute("""
            INSERT INTO planos_servico(codigo,nome,limite_chamadas_externas_mes)
            VALUES($1,'Cota sintetica',1)
        """, codigo)
        await conn.execute("""
            INSERT INTO assinaturas_empresa(tenant_id,plano_codigo,status,inicio_em)
            VALUES($1,$2,'ATIVA',now())
        """, tenant, codigo)
        reserva = await reservar_osrm(conn, tenant)
        await concluir(conn, tenant, reserva, False)
        assert (await resumo(conn, tenant))["uso"]["chamadas_externas_mes"] == 1
        assert (await resumo(conn, outro))["uso"]["chamadas_externas_mes"] == 0
        assert await conn.fetchval("SELECT status FROM chamadas_api_externa WHERE id=$1", reserva) == "FALHA"
        with pytest.raises(HTTPException) as erro:
            await reservar_osrm(conn, tenant)
        assert erro.value.status_code == 429
    finally:
        await tx.rollback()
        await conn.close()
